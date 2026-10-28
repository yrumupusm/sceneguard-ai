"""CPU contract tests; no model construction or GPU initialization."""
import fcntl
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from orchestration.queue import Queue, digest, process_identity, source_hash
from orchestration import batch02_cv_command as command
from batch02_cv import runner
from batch02_cv.compare import iou


class CVContractTests(unittest.TestCase):
    def test_fixed_resolution_score_stage_and_runtime(self):
        self.assertEqual(command.SETTINGS['resolution'], [576, 576])
        self.assertEqual(command.SETTINGS['minimum_gpu_free_mib'], 6144)
        self.assertEqual(command.SETTINGS['threshold_operator'], '>')
        self.assertIsNone(command.SETTINGS['nms'])
        self.assertEqual(len(command.EXPECTED_FRAMES), 11)
        self.assertEqual(len(command.SMOKE), 2)
        for config in ({}, {'stage': 'other', 'settings': command.SETTINGS},
                       {'stage': 'smoke', 'settings': {**command.SETTINGS, 'resolution': [320, 320]}},
                       {'stage': 'smoke', 'settings': command.SETTINGS, 'video': '/tmp/a.mp4'}):
            with self.assertRaises(ValueError):
                command.validate(config, {}, '/tmp/alternate-runtime')

    def test_sparse_coco_person_and_strict_threshold(self):
        class Detection:
            xyxy = [[1, 2, 3, 4], [2, 2, 5, 6], [0, 0, 7, 9]]
            confidence = [.5, .50001, .9]
            class_id = [1, 1, 3]
            data = {'class_name': ['person', 'person', 'car']}
        rows = runner.person_rows(Detection())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['xyxy'], [2, 2, 5, 6])
        Detection.class_id = [0, 1, 3]
        with self.assertRaisesRegex(ValueError, 'sparse person'):
            runner.person_rows(Detection())

    def test_degenerate_nonfinite_or_ambiguous_outputs_rejected(self):
        class Detection:
            xyxy = [[1, 2, 3, 4]]
            confidence = [float('nan')]
            class_id = [1]
            data = {'class_name': ['person']}
        with self.assertRaises(ValueError):
            runner.person_rows(Detection())
        Detection.confidence = [.8]
        Detection.xyxy = [[1, 2, 1, 4]]
        with self.assertRaises(ValueError):
            runner.person_rows(Detection())
        Detection.data = {}
        with self.assertRaises(ValueError):
            runner.person_rows(Detection())

    def test_resource_gate_before_import(self):
        with patch.object(runner.subprocess, 'check_output', return_value='4100, 6143'):
            with self.assertRaisesRegex(ValueError, 'no model loaded'):
                runner.resources()
        with patch.object(runner.subprocess, 'check_output', return_value='4000, 6144'):
            self.assertEqual(runner.resources()['free_mib'], 6144)

    def test_direct_child_fails_before_torch_import(self):
        result = subprocess.run([sys.executable, '-I', str(command.ROOT / 'batch02_cv/runner.py'),
            '--stage', 'smoke', '--attempt', '0'*32, '--lock-fd', '999999'],
            capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Bad file descriptor', result.stderr)
        self.assertNotIn('torch', result.stderr)

    def test_additive_migration_preserves_all_jobs_attempts_and_old_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            queue = Queue.initialize(tmp)
            job = queue.enqueue(job_key='historical', run_id='r', task_id='t', dispatch_id='d', owner='cpu')
            queue.supervise_once()
            queue.migrate_commands(include_mvp=True)
            before = queue.status()
            queue.migrate_commands(include_cv=True)
            self.assertEqual(queue.status(), before)
            self.assertEqual(len(list(Path(tmp).glob('queue-before-batch02-cv-*.sqlite3'))), 1)
            queue.migrate_commands(include_cv=True)
            self.assertEqual(len(list(Path(tmp).glob('queue-before-batch02-cv-*.sqlite3'))), 1)
            with queue.connection() as db:
                sql = db.execute("SELECT sql FROM sqlite_master WHERE name='jobs'").fetchone()[0]
            for name in ('cpu-mock', 'vlm-batch01', 'mvp-0001', 'batch02-cv'):
                self.assertIn("'" + name + "'", sql)
            with queue.connection() as db:
                before_backup = sqlite3.connect(next(Path(tmp).glob('queue-before-batch02-cv-*.sqlite3')))
                self.assertEqual(db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0],
                    before_backup.execute('SELECT COUNT(*) FROM attempts').fetchone()[0])
                before_backup.close()

    def test_migration_refuses_held_reservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            queue = Queue.initialize(tmp)
            with queue.gpu_lock():
                with self.assertRaisesRegex(ValueError, 'reservation'):
                    queue.migrate_commands(include_cv=True)

    def test_inherited_lock_and_exact_child_identity_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            queue = Queue.initialize(tmp)
            queue.migrate_commands(include_cv=True)
            config = dict(stage='smoke', settings=command.SETTINGS)
            job = queue.enqueue(job_key='lease', run_id='r', task_id='t', dispatch_id='d', owner='cpu')
            with queue.connection() as db:
                db.execute("UPDATE jobs SET command='batch02-cv',status='running',config_json=?,config_hash=?,input_hash=?,source_hash=?,code_sha='frozen' WHERE job_id=?",
                    (json.dumps(config), digest(config), digest({'synthetic': True}), 'source', job['job_id']))
                db.execute("INSERT INTO attempts (attempt_id,job_id,attempt_no,owner,status,supervisor_pid,supervisor_identity,child_pid,child_identity,started_at,heartbeat,timeout) VALUES (?, ?,1,'cpu','running',?,?,?,?,0,0,10)",
                    ('a'*32, job['job_id'], os.getppid(), process_identity(os.getppid()), os.getpid(), process_identity(os.getpid())))
            with patch.object(runner, 'RUNTIME', Path(tmp)), patch.object(runner, 'INTERPRETER', Path(sys.executable)), \
                    patch.object(runner, 'validate', return_value='smoke'), \
                    patch.object(runner, 'source_hash', return_value='source'), \
                    patch.object(runner, 'validate_assignment', return_value={'code_sha': 'frozen'}):
                with queue.gpu_lock() as lock:
                    row = runner.verify_lease(config, 'a'*32, lock.fileno())
                    self.assertEqual(row['command'], 'batch02-cv')
                    with (Path(tmp)/'gpu.lock').open() as unrelated:
                        with self.assertRaisesRegex(ValueError, 'inherited reservation'):
                            runner.verify_lease(config, 'a'*32, unrelated.fileno())
                    with queue.connection() as db:
                        db.execute('UPDATE attempts SET child_identity=?', ('wrong',))
                    with self.assertRaisesRegex(ValueError, 'child identity'):
                        runner.verify_lease(config, 'a'*32, lock.fileno())

    def test_pinned_input_mutation_rejected_and_stage_sets_disjoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            weight = root / 'weights/rf-detr-medium/rf-detr-medium.pth'
            weight.parent.mkdir(parents=True)
            weight.write_bytes(b'checkpoint fixture')
            rgb = root / 'original.npy'
            rgb.write_bytes(b'original RGB fixture')
            from batch02_cv.prepare import sha
            frames = [dict(frame_id=f, source_path='original.npy', source_sha256=sha(rgb),
                rgb_path='original.npy', rgb_sha256=sha(rgb)) for f in command.EXPECTED_FRAMES]
            frozen = dict(frames=frames, historical_pins={}, environment={'files': {}},
                model={'sha256': sha(weight), 'bytes': weight.stat().st_size})
            path = root / 'manifest.json'
            path.write_text('{}')
            with patch.object(command, 'ROOT', root), patch.object(command, 'WEIGHT', weight), \
                    patch.object(command, 'MANIFEST', path), patch.object(command, 'manifest', return_value=frozen):
                smoke = command.input_contract('smoke')
                remaining = command.input_contract('remaining')
                self.assertEqual(len(smoke['frames']), 2)
                self.assertEqual(len(remaining['frames']), 9)
                self.assertFalse(set(smoke['frames']) & set(remaining['frames']))
                rgb.write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError, 'hash differs'):
                    command.input_contract('smoke')

    def test_frozen_assignment_and_boolean_setting_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp)
            path = local / 'execution-authorization.json'
            authorization = dict(run_id='r', task_id='t', dispatch_id='d', confirmed=True, sources={'a': 'b'})
            path.write_text(json.dumps(authorization))
            with patch.object(command, 'LOCAL', local), patch.object(command, 'sources', return_value={'a': 'b'}):
                self.assertTrue(command.validate_assignment('r', 't', 'd')['confirmed'])
                with self.assertRaises(ValueError):
                    command.validate_assignment('r', 't', 'stale')
                with patch.object(command, 'sources', return_value={'a': 'changed'}):
                    with self.assertRaisesRegex(ValueError, 'freeze'):
                        command.validate_assignment('r', 't', 'd')
        self.assertFalse(command.same(command.SETTINGS, {**command.SETTINGS, 'compile': 0}))

    def test_no_network_fallback(self):
        with self.assertRaisesRegex(RuntimeError, 'forbidden'):
            runner.deny_network()

    def test_diagnostic_iou_is_not_gt(self):
        self.assertEqual(iou([0, 0, 2, 2], [0, 0, 2, 2]), 1)
        self.assertEqual(iou([0, 0, 1, 1], [2, 2, 3, 3]), 0)


if __name__ == '__main__':
    unittest.main()
