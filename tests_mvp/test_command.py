"""CPU queue registry, preservation and live-lease tests; no real runtime/model."""
import copy
import fcntl
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock

from orchestration import mvp_command as command
from orchestration.queue import Queue, source_hash
from mvp import runner


class RegistryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.assets = self.root / 'assets'
        self.runtime = self.root / 'queue'
        self.queue = Queue.initialize(self.runtime)
        self.model = self.assets / 'weights/Qwen3-VL-2B-Instruct'
        self.model.mkdir(parents=True)
        (self.model / 'model.safetensors').write_bytes(b'CPU fixture, not weights')
        self.interpreter = self.assets / '.venv-vlm/bin/python'
        self.interpreter.parent.mkdir(parents=True)
        self.interpreter.write_bytes(b'fixture never executed')
        for name, value in dict(ROOT=self.root, ASSETS=self.assets, RUNTIME=self.runtime,
                                MODEL_DIR=self.model, INTERPRETER=self.interpreter,
                                PINNED_MODEL_SHA256=command.file_hash(self.model / 'model.safetensors')).items():
            patch = mock.patch.object(command, name, value)
            patch.start()
            self.addCleanup(patch.stop)
        patch = mock.patch.object(runner, 'RUNTIME', self.runtime)
        patch.start()
        self.addCleanup(patch.stop)
        self.config = {'phase': 'dev', 'view': 'fixed_roi', 'settings': command.SETTINGS.copy()}
        configs = self.root / 'configs'
        configs.mkdir()
        sources = dict(schema_version=1, development_clips=[dict(clip_id=c, source_id=s, camera_id=k,
            cache_dir=f'outputs/vlm_exp0007/{c}') for c, s, k in command.DEVELOPMENT],
            continuous_sources=[dict(source_id=s, camera_id=k, relative_video_path=f'data/TS_침입/{s}.mp4',
                                      sha256='') for s, k in command.CONTINUOUS],
            window_seconds=5.0, stride_seconds=2.5, sampling_fps=2.0)
        for item in sources['development_clips']:
            path = self.assets / item['cache_dir']
            path.mkdir(parents=True)
            (path / 'rgb.npy').write_bytes(item['clip_id'].encode())
            (path / 'input.json').write_text('{}')
        for item in sources['continuous_sources']:
            path = self.assets / item['relative_video_path']
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(item['source_id'].encode())
            item['sha256'] = command.file_hash(path)
        cameras = {'cameras': {c: {'roi': roi} for c, roi in
            {'C3': [0.6, 0, 0.9, 0.6], 'C6': [0.28, 0.2, 0.75, 0.8], 'C7': [0.43, 0, 0.78, 1],
             'C1': [0, 0, 1, 1], 'C4': [0, 0, 1, 1]}.items()}}
        for name, obj in zip(command.CONFIG_NAMES, (sources, cameras, command.EXPECTED_SETTINGS)):
            (configs / name).write_text(json.dumps(obj))
        baseline = self.assets / 'baseline-fixture.json'
        baseline.write_text('{}')
        patch = mock.patch('mvp.compare.baseline_paths', return_value=[baseline])
        patch.start()
        self.addCleanup(patch.stop)
        # Exercise source hashing against real bytes without requiring another worker's files.
        for name in ('orchestration/queue.py', 'orchestration/mock_job.py', 'orchestration/mvp_command.py',
                     'orchestration/vlm_command.py', 'vlm_batch/common.py', 'vlm_batch/qwen.py', 'vlm_batch/run.py',
                     'configs/vlm_batch01_prompt.txt', *('mvp/'+s+'.py' for s in
                     ('method', 'compare', 'runner', 'windows', 'events', 'evidence', 'pipeline', 'cli'))):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('# CPU fixture '+name)
        self.inputs = command.input_contract('dev')

    def enqueue(self, **changes):
        values = dict(job_key='mvp-fixture', run_id='r', task_id='t', dispatch_id='d', owner='o',
                      command='mvp-0001', config=self.config, input_value=self.inputs, timeout=900)
        values.update(changes)
        return self.queue.enqueue(**values)

    def test_fixed_argv_outputs_and_development_baseline_no_rerun(self):
        argv = command.command(self.config, self.inputs, self.runtime, 'a'*32, 12)
        self.assertEqual(argv[:3], [str(self.interpreter), '-I', str(self.root / 'mvp/runner.py')])
        self.assertIn('fixed_roi', argv)
        self.assertIn('EXP-0011', str(command.output_path('dev', 'a'*32)))
        self.assertIn('EXP-0012', str(command.output_path('full', 'a'*32)))
        for bad in ('../escape', '', 'x'*32):
            with self.assertRaises(ValueError):
                command.command(self.config, self.inputs, self.runtime, bad, 12)
        with self.assertRaises(ValueError):
            command.validate({**self.config, 'view': 'full_frame'}, self.inputs, self.runtime)

    def test_reject_arbitrary_config_runtime_and_semantic_settings(self):
        for cfg in ({**self.config, 'path': '/tmp/other'}, {**self.config, 'phase': 'search'},
                    {**self.config, 'settings': {**command.SETTINGS, 'seed': False}}):
            with self.assertRaises(ValueError):
                command.validate(cfg, self.inputs, self.runtime)
        with self.assertRaises(ValueError):
            command.validate(self.config, self.inputs, self.root)
        path = self.root / 'configs/mvp0001_settings.json'
        changed = copy.deepcopy(command.EXPECTED_SETTINGS)
        changed['sampling_fps'] = 4.0
        path.write_text(json.dumps(changed))
        with self.assertRaises(ValueError):
            command.validate(self.config, self.inputs, self.runtime)

    def test_model_input_config_and_source_changes_are_detected(self):
        original = source_hash('mvp-0001')
        (self.root / 'mvp/method.py').write_text('# changed')
        self.assertNotEqual(source_hash('mvp-0001'), original)
        (self.assets / 'outputs/vlm_exp0007/clip02/rgb.npy').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            command.command(self.config, self.inputs, self.runtime, 'a'*32, 12)
        (self.model / 'model.safetensors').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            command.input_contract('dev')

    def test_full_sources_cannot_expand_or_change_hash(self):
        inputs = command.input_contract('full')
        self.assertEqual(set(inputs['videos']), {'E01_007', 'E01_030', 'E01_013'})
        cfg = {**self.config, 'phase': 'full', 'view': 'full_frame'}
        command.validate(cfg, inputs, self.runtime)
        (self.assets / 'data/TS_침입/E01_013.mp4').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            command.validate(cfg, inputs, self.runtime)

    def test_opt_in_migration_preserves_history_rows_indices_triggers_and_backup(self):
        historical = self.queue.enqueue(job_key='historical', run_id='r', task_id='t', dispatch_id='d', owner='o')
        with self.queue.connection() as db:
            db.execute('CREATE INDEX history_owner ON jobs(owner)')
            db.execute('CREATE TRIGGER preserve_trigger AFTER UPDATE OF owner ON jobs BEGIN SELECT 1; END')
        _, attempt = self.queue._claim()
        self.queue._finish(attempt, 'failed', 7, 'CPU fixture only')
        before = self.queue.status()
        job = self.enqueue()
        after = self.queue.status()
        self.assertEqual(after['jobs'][0], before['jobs'][0])
        self.assertEqual(after['attempts'], before['attempts'])
        self.assertEqual(job['command'], 'mvp-0001')
        backups = list(self.runtime.glob('queue-before-mvp-*.sqlite3'))
        self.assertEqual(len(backups), 1)
        with sqlite3.connect(backups[0]) as db:
            self.assertEqual(db.execute('SELECT job_id FROM jobs').fetchone()[0], historical['job_id'])
            self.assertEqual(db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0], 1)
        with self.queue.connection() as db:
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
            self.assertEqual(len(db.execute("SELECT name FROM sqlite_master WHERE name IN ('history_owner','preserve_trigger')").fetchall()), 2)
        self.queue.migrate_commands(include_mvp=True)
        self.assertEqual(len(list(self.runtime.glob('queue-before-mvp-*'))), 1)
        with self.queue.gpu_lock():
            self.assertEqual(self.enqueue()['job_id'], job['job_id'])

    def test_invalid_timeout_does_not_migrate_and_one_error_retry_only(self):
        with self.assertRaises(ValueError):
            self.enqueue(timeout=901)
        self.assertEqual(list(self.runtime.glob('queue-before-mvp-*')), [])
        job = self.enqueue()
        for number in (1, 2):
            _, attempt = self.queue._claim()
            self.queue._finish(attempt, 'failed', 7, 'CPU-only execution error fixture')
            if number == 1:
                self.queue.retry(job['job_id'])
        with self.assertRaises(ValueError):
            self.queue.retry(job['job_id'])
        cfg = {**self.config, 'phase': 'full', 'view': 'full_frame'}
        with self.assertRaises(ValueError):
            self.enqueue(job_key='too-long', config=cfg, input_value=command.input_contract('full'), timeout=1801)

    def test_queue_migration_busy_unknown_and_rollback(self):
        with self.queue.gpu_lock():
            with self.assertRaises(ValueError):
                self.queue.migrate_commands(include_mvp=True)
        job = self.queue.enqueue(job_key='unknown', run_id='r', task_id='t', dispatch_id='d', owner='o')
        with self.queue.connection() as db:
            db.execute("UPDATE jobs SET status='unknown'")
        with self.assertRaises(ValueError):
            self.queue.migrate_commands(include_mvp=True)
        with self.queue.connection() as db:
            db.execute("UPDATE jobs SET status='succeeded'")
            db.execute('CREATE TABLE jobs_vlm (conflict TEXT)')
        before = self.queue.status()
        with self.assertRaises(sqlite3.OperationalError):
            self.queue.migrate_commands(include_mvp=True)
        self.assertEqual(before, self.queue.status())

    def test_lease_rejects_fake_or_unheld_or_wrong_supervisor_before_model(self):
        self.enqueue()
        _, attempt = self.queue._claim()
        with open('/dev/null') as wrong:
            with self.assertRaises(ValueError):
                runner.verify_lease(self.config, attempt, wrong.fileno())
        with self.queue.gpu_lock() as inherited:
            with (self.runtime / 'gpu.lock').open('r') as unrelated:
                with self.assertRaises(ValueError):
                    runner.verify_lease(self.config, attempt, unrelated.fileno())
            with self.assertRaises(ValueError):
                runner.verify_lease(self.config, attempt, inherited.fileno())
            with mock.patch.object(runner.os, 'getppid', return_value=os.getpid()):
                job = runner.verify_lease(self.config, attempt, inherited.fileno())
                self.assertEqual(job['command'], 'mvp-0001')
                with self.assertRaises(ValueError):
                    runner.verify_lease({**self.config, 'view': 'full_frame'}, attempt, inherited.fileno())

    def test_constructor_refuses_missing_lease_before_torch_import(self):
        from mvp.method import QwenAnalyzer
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, 'inherited MVP queue'):
                QwenAnalyzer(self.model, command.SETTINGS)

    def test_resource_gate_failure_never_loads_model(self):
        with mock.patch.object(runner.subprocess, 'check_output', return_value='9000, 1240'):
            with self.assertRaisesRegex(ValueError, 'no model loaded'):
                runner.check_resources(command.EXPECTED_SETTINGS)

    def test_historical_budget_refactor_accepts_only_unchanged_semantics(self):
        import subprocess
        from mvp.compare import same_qwen_budget_refactor
        root = Path(__file__).resolve().parents[1]
        old = subprocess.check_output(['git', 'show', 'f33c439058d23fdb91b05ece1b6462d6c8cf6418:vlm_batch/qwen.py'], cwd=root)
        current = (root / 'vlm_batch/qwen.py').read_bytes()
        self.assertTrue(same_qwen_budget_refactor(old, current))
        self.assertFalse(same_qwen_budget_refactor(old, current.replace(b'3584000', b'7168000')))
        self.assertFalse(same_qwen_budget_refactor(old, current.replace(b'local_files_only=True', b'local_files_only=False')))

    def test_reuse_requires_native_success_exact_config_inputs_source_and_same_run(self):
        from mvp import compare
        cfg = {**self.config, 'phase': 'full', 'view': 'full_frame'}
        inputs = command.input_contract('full')
        job = self.enqueue(config=cfg, input_value=inputs, timeout=1800)
        _, attempt = self.queue._claim()
        with mock.patch.object(compare, 'RUNTIME', self.runtime):
            with self.assertRaisesRegex(ValueError, 'successful native'):
                compare.successful_baseline(attempt, 'full', 'full_frame')
            self.queue._finish(attempt, 'succeeded', 0, 'synthetic CPU fixture only; no model executed')
            compare.successful_baseline(attempt, 'full', 'full_frame')
            with self.assertRaises(ValueError):
                compare.successful_baseline(attempt, 'full', 'fixed_roi')
            folder = command.output_path('full', attempt)
            folder.mkdir(parents=True)
            (folder / 'summary.json').write_text(json.dumps({'status': 'succeeded'}))
            self.assertEqual(runner.find_full_baseline(inputs, 'r'), (attempt, folder))
            for bad_inputs, run_id in (({**inputs, 'injected': True}, 'r'), (inputs, 'other-run')):
                with self.assertRaises(ValueError):
                    runner.find_full_baseline(bad_inputs, run_id)
            (self.root / 'mvp/method.py').write_text('# changed semantic code')
            with self.assertRaises(ValueError):
                runner.find_full_baseline(inputs, 'r')


if __name__ == '__main__':
    unittest.main()
