"""Synthetic whole-source guards; no model or real queue execution."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('full_run', ROOT / 'scripts/mvp_full_run.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class Guards(unittest.TestCase):
    def setUp(self):
        self.clock = [dict(frame_index=i, native_pts=i * 512, time_base='1/15360', pts=i / 30)
                      for i in range(30)]

    def test_missing_first_cache_frame_rejected(self):
        with self.assertRaises(ValueError):
            runner.assert_clock(self.clock, self.clock[1:])

    def test_missing_last_cache_frame_rejected(self):
        with self.assertRaises(ValueError):
            runner.assert_clock(self.clock, self.clock[:-1])

    def test_same_count_changed_pts_rejected(self):
        changed = copy.deepcopy(self.clock)
        changed[12]['native_pts'] += 1
        with self.assertRaises(ValueError):
            runner.assert_clock(self.clock, changed)

    def test_exact_native_partition_accepted(self):
        runner.assert_clock(self.clock, copy.deepcopy(self.clock), indexed=True)

    def test_reordered_frame_index_rejected(self):
        changed = copy.deepcopy(self.clock)
        changed[12]['frame_index'] = 13
        with self.assertRaises(ValueError):
            runner.assert_clock(self.clock, changed, indexed=True)

    def test_docs_only_commit_keeps_frozen_analysis_admissible(self):
        with patch.object(runner, 'head', return_value='later-docs-and-wrapper-only-commit'):
            self.assertTrue(runner.frozen_analysis_bytes())
            runner.verify_plan(dict(execution_revision=runner.head(),
                code_sha256=runner.code_files(), input_sha256={}))

    def test_analysis_mutation_rejected_even_on_later_commit(self):
        changed = runner.code_files()
        changed[str(ROOT / 'sceneguard/mvp_pipeline.py')] = 'altered-analysis-hash'
        with patch.object(runner, 'code_files', return_value=changed), \
             patch.object(runner, 'head', return_value='later-commit'):
            with self.assertRaisesRegex(ValueError, 'frozen f05d430'):
                runner.frozen_analysis_bytes()

    def run_mock(self, cached):
        with tempfile.TemporaryDirectory() as temporary:
            local = Path(temporary)
            plan = local / 'plan.json'
            plan.write_text(json.dumps({'videos': []}))
            output = local / 'output'
            row = dict(video_id='synthetic', execution_status='not_run',
                detector_required=not cached, video_path='/synthetic.mp4', camera_id='C3',
                scene='/synthetic-scene.json', portal='/synthetic-portal.json',
                output_path=str(output), cache='/synthetic-cache' if cached else None,
                duration_seconds=1.0)
            ledger = dict(plan_sha256=runner.vc.sha256(plan), videos=[row])
            (local / 'execution-ledger.local.json').write_text(json.dumps(ledger))
            with patch.object(runner, 'LOCAL', local), patch.object(runner, 'verify_plan'), \
                 patch.object(runner, 'gpu', return_value={'available': False, 'free_mib': 784}), \
                 patch.object(runner, 'Queue') as queue, \
                 patch.object(runner, 'queue_snapshot', return_value={'jobs': [], 'attempts': []}), \
                 patch.object(runner, 'costs', return_value={}), \
                 patch.object(runner.subprocess, 'run') as process:
                queue.return_value.status.return_value = {'jobs': [dict(job_id='other', status='running')]}
                process.return_value.returncode = 1
                result = runner.execute(plan, {'dispatch_id': 'synthetic'})
                return process.call_count, result['videos'][0]['execution_status']

    def test_uncached_busy_gpu_never_starts_pipeline_or_queue_job(self):
        calls, status = self.run_mock(False)
        self.assertEqual((calls, status), (0, 'not_run'))

    def test_full_cache_cpu_path_is_admitted_with_busy_gpu_and_queue(self):
        calls, status = self.run_mock(True)
        self.assertEqual((calls, status), (1, 'failed'))  # Stub process fails after admission.


if __name__ == '__main__':
    unittest.main(verbosity=2)
