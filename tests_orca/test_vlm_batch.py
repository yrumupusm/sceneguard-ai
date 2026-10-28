"""CPU-only regression tests; fixtures never load a model or touch real runtime."""
import fcntl
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock

from orchestration.queue import Queue
from orchestration import vlm_command as command
from vlm_batch.run import verify_lease


class MigrationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.queue = Queue.initialize(temp.name)
        self.job = self.queue.enqueue(job_key='history', run_id='r', task_id='t', dispatch_id='d',
                                     owner='o', config={'seconds': 0, 'exit_code': 0})
        self.queue.supervise_once()
        with self.queue.connection() as db:
            sql = db.execute("SELECT sql FROM sqlite_master WHERE name='jobs'").fetchone()[0]
            db.execute('PRAGMA foreign_keys=OFF')
            db.execute('BEGIN IMMEDIATE')
            db.execute(sql.replace('CREATE TABLE jobs', 'CREATE TABLE jobs_old').replace(
                "CHECK(command IN ('cpu-mock','vlm-batch01'))", "CHECK(command='cpu-mock')"))
            db.execute('INSERT INTO jobs_old SELECT * FROM jobs')
            db.execute('DROP TABLE jobs')
            db.execute('ALTER TABLE jobs_old RENAME TO jobs')
            db.commit()
        self.before = self.queue.status()

    def test_preserves_all_rows_and_backup_and_cpu_jobs_still_run(self):
        Queue.initialize(self.queue.runtime)
        self.assertEqual(self.queue.status(), self.before)
        backups = list(self.queue.runtime.glob('queue-before-vlm-*.sqlite3'))
        self.assertEqual(len(backups), 1)
        with sqlite3.connect(backups[0]) as db:
            self.assertEqual(db.execute('SELECT job_id FROM jobs').fetchone()[0], self.job['job_id'])
            self.assertEqual(db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0], 1)
            self.assertIn("CHECK(command='cpu-mock')", db.execute(
                "SELECT sql FROM sqlite_master WHERE name='jobs'").fetchone()[0])
        Queue.initialize(self.queue.runtime)
        self.assertEqual(len(list(self.queue.runtime.glob('queue-before-vlm-*'))), 1)
        self.queue.enqueue(job_key='new', run_id='r', task_id='t', dispatch_id='d', owner='o')
        self.assertEqual(self.queue.supervise_once()['status'], 'succeeded')

    def test_schema_failure_rolls_back_every_row(self):
        with self.queue.connection() as db:
            db.execute('CREATE TABLE jobs_vlm (conflicting TEXT)')
        with self.assertRaises(sqlite3.OperationalError):
            self.queue.migrate_commands()
        self.assertEqual(self.queue.status(), self.before)
        with self.queue.connection() as db:
            self.assertIn("CHECK(command='cpu-mock')", db.execute(
                "SELECT sql FROM sqlite_master WHERE name='jobs'").fetchone()[0])
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])

    def test_busy_or_unknown_queue_cannot_migrate(self):
        with self.queue.gpu_lock():
            with self.assertRaises(ValueError):
                self.queue.migrate_commands()
        with self.queue.connection() as db:
            db.execute("UPDATE jobs SET status='unknown'")
        with self.assertRaises(ValueError):
            self.queue.migrate_commands()
        self.assertEqual(list(self.queue.runtime.glob('queue-before-vlm-*')), [])


class CommandTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.assets = self.root / 'assets'
        self.runtime = self.root / 'canonical'
        self.runtime.mkdir()
        for name in ('ASSETS', 'RUNTIME'):
            patch = mock.patch.object(command, name, getattr(self, name.lower()))
            patch.start()
            self.addCleanup(patch.stop)
        for adapter, (_, interpreter, model) in command.MODELS.items():
            path = self.assets / interpreter
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'fixture interpreter')
            model_dir = self.assets / 'weights' / model
            model_dir.mkdir(parents=True, exist_ok=True)
            (model_dir / 'model.safetensors').write_bytes(b'CPU fixture only')
        for clip in command.CLIPS:
            path = self.assets / 'outputs/vlm_exp0007' / clip
            path.mkdir(parents=True)
            (path / 'rgb.npy').write_bytes(clip.encode())
            (path / 'input.json').write_text('{}')
        self.inputs = command.input_contract('qwen')
        self.config = {'adapter': 'qwen', 'settings': command.SETTINGS.copy()}

    def test_fixed_paths_argv_and_unique_attempt_output(self):
        argv = command.command(self.config, self.inputs, self.runtime, 'a' * 32, 12)
        self.assertEqual(argv[0], str(self.assets / '.venv-vlm/bin/python'))
        self.assertIn('-I', argv)
        self.assertNotIn('shell', argv)
        self.assertNotEqual(command.output_path('qwen', 'a' * 32), command.output_path('qwen', 'b' * 32))
        for bad in ('../escape', '', 'x' * 32):
            with self.assertRaises(ValueError):
                command.command(self.config, self.inputs, self.runtime, bad, 12)

    def test_reject_arbitrary_paths_models_settings_and_runtime(self):
        for config in ({**self.config, 'model': '/tmp/untrusted'},
                       {**self.config, 'adapter': 'arbitrary'},
                       {**self.config, 'settings': {**command.SETTINGS, 'do_sample': True}},
                       {**self.config, 'settings': {**command.SETTINGS, 'seed': False}}):
            with self.assertRaises(ValueError):
                command.validate(config, self.inputs, self.runtime)
        with self.assertRaises(ValueError):
            command.validate(self.config, self.inputs, self.root)

    def test_actual_assets_are_rehashed_before_launch(self):
        (self.assets / 'outputs/vlm_exp0007/clip03/rgb.npy').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            command.command(self.config, self.inputs, self.runtime, 'a' * 32, 12)

    def test_high_pixels_reuses_exact_qwen_assets_and_settings(self):
        self.assertEqual(command.MODELS['qwen'],
                         ('EXP-0008', '.venv-vlm/bin/python', 'Qwen3-VL-2B-Instruct'))
        self.assertEqual(command.MODELS['smol'],
                         ('EXP-0009', '.venv-vlm-batch01/bin/python', 'SmolVLM2-2.2B-Instruct'))
        self.assertEqual(command.input_contract('qwen_high_pixels'), self.inputs)
        config = {**self.config, 'adapter': 'qwen_high_pixels'}
        argv = command.command(config, self.inputs, self.runtime, 'a' * 32, 12)
        self.assertEqual(argv[0], str(self.assets / '.venv-vlm/bin/python'))
        self.assertIn('qwen_high_pixels', argv)
        self.assertEqual(command.output_path('qwen_high_pixels', 'a' * 32),
                         self.assets / 'outputs/vlm_batch01/EXP-0010' / ('a' * 32))
        self.assertNotEqual(command.output_path('qwen', 'a' * 32),
                            command.output_path('qwen_high_pixels', 'a' * 32))
        with self.assertRaises(ValueError):
            command.validate({**config, 'size': 7168000}, self.inputs, self.runtime)

    def test_high_pixels_hashes_adapter_and_true_base_dependency(self):
        baseline = command.sources('qwen')
        smol = command.sources('smol')
        high = command.sources('qwen_high_pixels')
        self.assertEqual(set(high) - set(baseline), {'vlm_batch/qwen_high_pixels.py'})
        self.assertEqual(high['vlm_batch/qwen.py'], baseline['vlm_batch/qwen.py'])
        self.assertNotIn('vlm_batch/qwen.py', smol)
        self.assertNotIn('vlm_batch/qwen_high_pixels.py', baseline)
        original = command.file_hash
        with mock.patch.object(command, 'file_hash', side_effect=lambda path:
                               'changed' if path.name == 'qwen.py' else original(path)):
            self.assertNotEqual(command.sources('qwen_high_pixels'), high)
            self.assertEqual(command.sources('smol'), smol)

    def test_vlm_timeout_cap_and_inherited_one_retry(self):
        q = Queue.initialize(self.runtime)
        with self.assertRaises(ValueError):
            q.enqueue(job_key='bad', run_id='r', task_id='t', dispatch_id='d', owner='o',
                      command='vlm-batch01', config=self.config, input_value=self.inputs, timeout=901)
        job = q.enqueue(job_key='bounded', run_id='r', task_id='t', dispatch_id='d', owner='o',
                        command='vlm-batch01', config=self.config, input_value=self.inputs, timeout=900)
        _, attempt = q._claim()
        q._finish(attempt, 'failed', 7, 'fixture execution error; no model run')
        q.retry(job['job_id'])
        _, attempt2 = q._claim()
        q._finish(attempt2, 'failed', 7, 'fixture execution error')
        with self.assertRaises(ValueError):
            q.retry(job['job_id'])

    def test_runner_refuses_no_lease_before_model_import(self):
        (self.runtime / 'gpu.lock').touch()
        with mock.patch('vlm_batch.run.RUNTIME', self.runtime), open('/dev/null') as other:
            with self.assertRaises(ValueError):
                verify_lease('qwen', 'a' * 32, other.fileno())
        with mock.patch('vlm_batch.run.RUNTIME', self.runtime), (self.runtime / 'gpu.lock').open('a+') as lock:
            with self.assertRaises(ValueError):
                verify_lease('qwen', 'a' * 32, lock.fileno())


if __name__ == '__main__':
    unittest.main()
