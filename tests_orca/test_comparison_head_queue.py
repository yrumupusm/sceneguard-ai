"""Temporary-queue integration; no real model or canonical queue mutation."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from orchestration import queue as original
from orchestration import comparison_head_command as head

queue = original
if os.environ.get('SCENEGUARD_TEST_QUEUE_CANDIDATE'):
    spec = importlib.util.spec_from_file_location('head_queue_candidate', os.environ['SCENEGUARD_TEST_QUEUE_CANDIDATE'])
    queue = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(queue)
    queue.ROOT = original.ROOT
    queue.MOCK = original.MOCK


class HeadQueueIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.queue = queue.Queue.initialize(self.root / 'queue')
        self.context = dict(run_id='r', task_id='t', dispatch_id='d', owner='o')
        self.config = dict(stage='feature-smoke', context=self.context, model_id='vjepa2_l', files={}, execution_revision='test')
        self.addCleanup(patch.stopall)
        self.validate = patch.object(head, 'validate', return_value={}).start()
        patch.object(head, 'sources', return_value={'synthetic': 'only'}).start()
        patch.object(head, 'output_path', side_effect=lambda stage, attempt: self.root / 'out' / stage / attempt).start()
        patch.object(head, 'interpreter', return_value=Path(sys.executable)).start()

    def enqueue(self, **kwargs):
        args = dict(job_key=head.job_key(self.config), command='comparison-head', config=self.config,
                    input_value={'synthetic': True}, timeout=100, **self.context)
        args.update(kwargs)
        return self.queue.enqueue(**args)

    def test_migration_preserves_old_rows_and_is_idempotent(self):
        self.queue.enqueue(job_key='old', config={'seconds': 0, 'exit_code': 0}, **self.context)
        before = self.queue.status()
        self.queue.migrate_commands(include_comparison_head=True)
        self.assertEqual(before, self.queue.status())
        backups = list(self.queue.runtime.glob('queue-before-comparison-head-*.sqlite3'))
        self.assertEqual(len(backups), 1)
        self.queue.migrate_commands(include_comparison_head=True)
        self.assertEqual(backups, list(self.queue.runtime.glob('queue-before-comparison-head-*.sqlite3')))
        self.assertEqual(self.enqueue()['command'], 'comparison-head')

    def test_migration_refuses_held_lock_and_unresolved_old_job(self):
        with self.queue.gpu_lock() as lock:
            with self.assertRaisesRegex(ValueError, 'reservation'):
                self.queue.migrate_commands(include_comparison_head=True)
        old = self.queue.enqueue(job_key='old', config={'seconds': 0, 'exit_code': 0}, **self.context)
        with self.queue.connection() as db:
            db.execute("UPDATE jobs SET status='unknown' WHERE job_id=?", (old['job_id'],))
        with self.assertRaisesRegex(ValueError, 'unresolved'):
            self.queue.migrate_commands(include_comparison_head=True)

    def test_assignment_timeout_and_source_dispatch(self):
        with self.assertRaisesRegex(ValueError, 'assignment'):
            self.enqueue(owner='different')
        with self.assertRaisesRegex(ValueError, '14400'):
            self.enqueue(timeout=14401)
        self.config['stage'] = 'train'
        with self.assertRaisesRegex(ValueError, '1800'):
            self.enqueue(timeout=1801)
        job = self.enqueue(timeout=1800)
        self.assertEqual(job['source_hash'], queue.digest({'synthetic': 'only'}))
        self.validate.assert_called()

    def test_finish_missing_result_fails_and_retry_is_rejected(self):
        job = self.enqueue()
        claimed, attempt = self.queue._claim(job['job_id'])
        self.queue._finish(attempt, 'succeeded', 0, '')
        status = self.queue.status()
        self.assertEqual(status['jobs'][0]['status'], 'failed')
        self.assertIn('Missing comparison head result', status['attempts'][0]['reason'])
        with self.assertRaisesRegex(ValueError, 'separately reviewed'):
            self.queue.retry(job['job_id'])

    def test_receipt_binds_actual_result_and_never_upgrades_failure(self):
        for index, state in enumerate(('succeeded', 'failed', 'cancelled')):
            self.config['execution_revision'] = 'test-' + str(index)
            job = self.enqueue()
            claimed, attempt = self.queue._claim(job['job_id'])
            result = head.output_path(self.config['stage'], attempt) / 'result.json'
            result.parent.mkdir(parents=True)
            result.write_text('{"synthetic":true}', encoding='utf-8')
            self.queue._finish(attempt, state, 0 if state == 'succeeded' else 1, state)
            receipt = json.loads((self.queue.runtime / 'attempts' / attempt / 'manifest.json').read_text())
            self.assertEqual(receipt['execution_status'], state)
            self.assertEqual(receipt['result_sha256'], head.file_hash(result))
            self.assertEqual(receipt['registration']['command'], 'comparison-head')

    def test_supervisor_passes_real_held_fd_and_visibility_to_child(self):
        def synthetic_command(config, inputs, runtime, attempt, lock_fd):
            result = head.output_path(config['stage'], attempt) / 'result.json'
            script = ('import os,json,fcntl,pathlib; '
                      'fd=int(os.environ["SCENEGUARD_GPU_LOCK_FD"]); os.fstat(fd); '
                      'assert os.environ["CUDA_VISIBLE_DEVICES"]=="0"; '
                      'fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB); '
                      'p=pathlib.Path(' + repr(str(result)) + '); p.parent.mkdir(parents=True); '
                      'p.write_text(json.dumps({"synthetic":True,"held_fd":True}))')
            return [sys.executable, '-c', script]
        with patch.object(head, 'command', side_effect=synthetic_command):
            job = self.enqueue()
            self.queue.supervise_once(job['job_id'])
        status = self.queue.status()
        self.assertEqual(status['jobs'][0]['status'], 'succeeded')


if __name__ == '__main__':
    unittest.main()
