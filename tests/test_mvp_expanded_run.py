"""Expanded runner contracts and execution gates; never use a model or real queue."""
import copy
from collections import Counter
from contextlib import ExitStack
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('expanded_run', ROOT / 'scripts/mvp_expanded_run.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
VALIDATE_RESUME = runner.validate_resume


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


class Clocks(unittest.TestCase):
    def setUp(self):
        self.clock = [dict(frame_index=i, native_pts=pts, time_base='1/90000', pts=pts / 90000)
                      for i, pts in enumerate((0, 3003, 9009, 12012))]

    def test_fractional_native_clock_and_actual_source_gap_preserved(self):
        runner.validate_source_clock(self.clock)
        runner.assert_clock(self.clock, copy.deepcopy(self.clock), indexed=True)

    def test_changed_count_rejected(self):
        for changed in (self.clock[1:], self.clock[:-1], self.clock + self.clock[-1:]):
            with self.assertRaises(ValueError):
                runner.assert_clock(self.clock, changed)

    def test_same_count_pts_change_rejected(self):
        for key, value in [('native_pts', 1), ('pts', .1), ('time_base', '1/30'), ('frame_index', 3)]:
            changed = copy.deepcopy(self.clock)
            changed[1][key] = value
            with self.assertRaises(ValueError):
                runner.assert_clock(self.clock, changed, indexed=True)

    def test_nonmonotonic_or_resampled_source_rejected(self):
        for key, value in [('native_pts', 1), ('pts', 0), ('frame_index', 12)]:
            changed = copy.deepcopy(self.clock)
            changed[1][key] = value
            with self.assertRaises(ValueError):
                runner.validate_source_clock(changed)

    def test_cached_inventory_source_hash_must_match(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            save(folder / 'synthetic.json', dict(source_sha256='original',
                 media=dict(decode_status='complete')))
            with patch.object(runner, 'NATIVE_CLOCKS', folder), self.assertRaises(ValueError):
                runner.audited_clock('/unused', 'changed', 'synthetic')

    def test_all_five_output_clocks_checked_and_cpu_index_checked(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            clock_path, cache, output = folder / 'clock.json', folder / 'cache', folder / 'output'
            save(clock_path, self.clock)
            save(output / 'source/analysis/analysis.json', {'source_paths': {'cache': str(cache)}})
            outputs = [cache / 'person_cache.jsonl', output / 'source/tracking/frames.jsonl',
                       output / 'image-paths/frame-evidence.jsonl',
                       output / 'source/evidence/source-frames.json', output / 'evidence/source-frames.json']
            for path in outputs:
                save(path, self.clock) if path.suffix == '.json' else self.write_lines(path, self.clock)
            row = dict(output_path=str(output), source_clock_path=str(clock_path), source_sha256='source')
            self.assertEqual(len(runner.coverage_receipt(row)['compared']), 5)
            for path in outputs:
                changed = copy.deepcopy(self.clock)
                changed[-1]['native_pts'] += 1
                save(path, changed) if path.suffix == '.json' else self.write_lines(path, changed)
                with self.assertRaises(ValueError):
                    runner.coverage_receipt(row)
                save(path, self.clock) if path.suffix == '.json' else self.write_lines(path, self.clock)

    @staticmethod
    def write_lines(path, rows):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows))


class InputContract(unittest.TestCase):
    def test_real_eight_profile_preparation_resolves_embedded_and_legacy_regions(self):
        registry_path = ROOT / 'runtime/MVP-0005/profiles/registry.json'
        registry = runner.vc.read(registry_path)
        self.assertEqual(len(registry['cameras']), 8)
        for camera_id, camera in registry['cameras'].items():
            scene, portal = Path(camera['scene_path']), Path(camera['portal_path'])
            size = runner.vc.read(scene)['source_size']
            files = runner.profile_inputs(camera_id, camera, scene, portal, registry_path, size)
            self.assertTrue(all(Path(p).is_file() for p in files))
            self.assertEqual(files[2], runner.vc.SCENES.get(camera_id, scene))
            if camera_id not in runner.vc.SCENES:
                self.assertEqual(files[3:], [scene, scene])

    def test_all_45_sources_required_no_truth_keys_or_missing_originals(self):
        with tempfile.TemporaryDirectory() as temporary:
            path, original = Path(temporary) / 'sources.json', Path(temporary) / 'original.json'
            rows = [dict(video_id='synthetic_' + str(i), video_path=str(ROOT / 'data' / (str(i) + '.mp4')),
                         camera_id='C1', support_provenance='synthetic static mapping') for i in range(45)]
            save(original, dict(videos=rows))
            with patch.object(runner, 'SOURCE_LIST', original):
                save(path, dict(videos=rows))
                self.assertEqual(len(runner.load_sources(path)), 45)
                for mutation in ('missing', 'extra_truth', 'duplicate', 'new_original'):
                    changed = copy.deepcopy(rows)
                    if mutation == 'missing':
                        changed.pop()
                    elif mutation == 'extra_truth':
                        changed[0]['event_frame'] = [1, 2]
                    elif mutation == 'duplicate':
                        changed[-1] = changed[0]
                    else:
                        changed[-1]['video_path'] = str(ROOT / 'data/other.mp4')
                    save(path, dict(videos=changed))
                    with self.assertRaises(ValueError):
                        runner.load_sources(path)

    def test_path_traversal_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'real').mkdir()
            (root / 'alias').symlink_to(root / 'real', target_is_directory=True)
            for path in (root / 'alias/result', root / '../escape', root.parent / 'escape'):
                with self.assertRaises(ValueError):
                    runner.local_path(path, root)

    def test_analysis_identity_binds_actual_bytes_not_legacy_sha(self):
        one = {str(ROOT / 'sceneguard/example.py'): 'one'}
        two = {str(ROOT / 'sceneguard/example.py'): 'two'}
        self.assertNotEqual(runner.analysis_code_digest(one), runner.analysis_code_digest(two))
        self.assertTrue(runner.analysis_code_digest(one).startswith('MVP-0005-sha256:'))

    def test_frozen_code_or_input_mutation_rejected(self):
        plan = dict(execution_revision='head', code_sha256={}, input_sha256={},
                    analysis_revision='head', analysis_code_digest=runner.analysis_code_digest({}), detector_settings=runner.SETTINGS,
                    queue_runtime=str(runner.RUNTIME))
        with patch.object(runner, 'head', return_value='head'), patch.object(runner, 'code_files', return_value={}):
            runner.verify_plan(plan)
            with patch.object(runner, 'code_files', return_value={'changed': 'code'}), self.assertRaises(ValueError):
                runner.verify_plan(plan)
            with patch.object(runner, 'bindings', return_value={'changed': 'source'}), self.assertRaises(ValueError):
                runner.verify_plan(plan)

    def test_ledger_immutable_source_and_all_source_count_verified(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'plan.json'
            plan = dict(analysis_revision='revision', videos=[dict(video_id='one', cache='cache',
                        execution_status='not_run', reason=None, attempts=[], output_path=None)])
            save(path, plan)
            ledger = dict(plan_sha256=runner.vc.sha256(path), analysis_revision='revision', videos=copy.deepcopy(plan['videos']))
            runner.verify_ledger(ledger, path, plan)
            ledger['videos'][0]['cache'] = 'other'
            with self.assertRaises(ValueError):
                runner.verify_ledger(ledger, path, plan)

    def test_006_eof_bound_does_not_inflate_exposure_duration(self):
        audit_path = ROOT / 'outputs/validation/mvp-all-v1/inventory/native-pts/E01_006.json'
        audit = runner.vc.read(audit_path)
        clock = audit['clocks']
        rows = [dict(native_pts=pts, time_base=clock['time_base']) for pts in clock['native_pts']]
        info = runner.source_metadata('/unused', rows, audit_path)
        self.assertEqual(info['duration_seconds'], audit['media']['duration_seconds'])
        self.assertGreater(info['source_end_exclusive'], info['duration_seconds'])
        self.assertAlmostEqual(info['source_end_exclusive'] - info['duration_seconds'], 1001 / 30000)


class Authorization(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.plan = self.root / 'plan.json'
        save(self.plan, dict(analysis_revision='new-revision'))
        self.review = self.root / 'review.json'
        save(self.review, dict(accepted_for_execution=True))
        self.context = dict(run_id='run', task_id='task', dispatch_id='dispatch', owner='owner')
        self.auth = dict(plan_sha256=runner.vc.sha256(self.plan), analysis_revision='new-revision',
                         context=self.context, profiles_code_frozen=True, independent_review_accepted=True,
                         execution_permitted=True, gpu_permitted=False,
                         independent_review=dict(path=str(self.review), sha256=runner.vc.sha256(self.review)))
        self.path = self.root / 'authorization.json'

    def check(self, value, fresh=False):
        save(self.path, value)
        return runner.verify_authorization(self.path, self.plan, runner.vc.read(self.plan), self.context, fresh=fresh)

    def test_cpu_scope_accepts_reviewed_frozen_permission(self):
        self.check(self.auth)

    def test_gpu_needs_explicit_separate_permission(self):
        with self.assertRaises(ValueError):
            self.check(self.auth, fresh=True)
        self.auth['gpu_permitted'] = True
        self.check(self.auth, fresh=True)

    def test_each_freeze_review_plan_or_context_mismatch_rejected(self):
        for key, value in [('plan_sha256', 'wrong'), ('analysis_revision', 'old'), ('context', {}),
                           ('profiles_code_frozen', False), ('independent_review_accepted', False),
                           ('execution_permitted', False), ('independent_review', {})]:
            changed = copy.deepcopy(self.auth)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.check(changed)

    def test_review_artifact_changed_rejected(self):
        save(self.review, dict(accepted_for_execution=False))
        with self.assertRaises(ValueError):
            self.check(self.auth)


class Regression(unittest.TestCase):
    def fixture(self):
        return dict(session_id='mvp-old', events=[dict(event_id='event-old', decision_time_pts=5,
                    source_event=dict(rule='rule', score=.55))],
                    cards=[dict(incident_id='card-old', event_ids=['event-old'], first_confirmation_pts=8)],
                    source_to_activity_cards={'card-old': ['event-old']}, source_candidate_sha256='derived-old')

    def test_only_generated_identity_and_candidate_provenance_digest_relabel(self):
        old = self.fixture()
        new = json.loads(json.dumps(old).replace('mvp-old', 'mvp-new').replace('event-old', 'event-new')
                         .replace('card-old', 'card-new').replace('derived-old', 'derived-new'))
        self.assertEqual(runner.regression_projection(old), runner.regression_projection(new))

    def test_changed_rule_time_geometry_or_topology_not_hidden(self):
        old = self.fixture()
        for mutation in ('time', 'rule', 'link', 'score'):
            new = copy.deepcopy(old)
            if mutation == 'time': new['events'][0]['decision_time_pts'] += .01
            elif mutation == 'rule': new['events'][0]['source_event']['rule'] = 'different'
            elif mutation == 'score': new['events'][0]['source_event']['score'] = .99
            else: new['cards'][0]['event_ids'].append('event-old')
            self.assertNotEqual(runner.regression_projection(old), runner.regression_projection(new))

    def test_resolution_and_prior_incident_ids_relabel_without_hiding_membership(self):
        old = self.fixture()
        old['resolution'] = dict(resolution_id='resolution-old', source_incident_id='prior-old')
        old['cards'][0]['source_incident_ids'] = ['prior-old']
        old['events'].append(dict(event_id='second-old', decision_time_pts=6))
        old['cards'][0]['event_ids'].append('second-old')
        new = json.loads(json.dumps(old).replace('resolution-old', 'resolution-new').replace('prior-old', 'prior-new')
                         .replace('second-old', 'second-new'))
        new['cards'][0]['event_ids'].reverse()
        self.assertEqual(runner.regression_projection(old), runner.regression_projection(new))


class ExecutionGates(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.local, self.runs = self.root / 'local', self.root / 'runs'
        self.plan_path = self.local / 'plan.json'
        self.context = dict(run_id='run', task_id='task', dispatch_id='dispatch', owner='owner')
        self.rows = [self.row(name, name in runner.REGRESSIONS) for name in ('E01_001', 'E01_007', 'E01_030', 'E01_002')]
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(runner, 'LOCAL', self.local))
        self.stack.enter_context(patch.object(runner, 'RUNS', self.runs))
        for name in ('verify_plan', 'validate_assignment', 'validate_resume', 'validate_job'):
            self.stack.enter_context(patch.object(runner, name))
        self.stack.enter_context(patch.object(runner, 'verify_authorization', return_value={}))
        self.stack.enter_context(patch.object(runner, 'regression_receipt', return_value={'state': 'passed'}))
        self.stack.enter_context(patch.object(runner, 'costs', return_value={}))
        self.stack.enter_context(patch.object(runner, 'artifact_bindings', return_value={}))
        self.snapshot = self.stack.enter_context(patch.object(runner, 'queue_snapshot', return_value={'jobs': [], 'attempts': []}))
        self.gpu = self.stack.enter_context(patch.object(runner, 'gpu', return_value={'available': True, 'free_mib': 8000}))
        self.pending = self.stack.enter_context(patch.object(runner, 'pending_jobs', return_value=[]))
        self.complete = self.stack.enter_context(patch.object(runner, 'validate_complete',
            return_value=({}, {'frames': 3}, {'cards_path': 'cards', 'source_window': [0, 1]})))
        def process(command, folder, output, persist):
            output.mkdir(parents=True)
            save(output / 'viewer-manifest.json', {})
            persist(dict(utc='now', pid=123))
            return 0
        self.process = self.stack.enter_context(patch.object(runner, 'run_process', side_effect=process))

    @staticmethod
    def row(name, cached):
        return dict(video_id=name, video_path='/synthetic/' + name + '.mp4', camera_id='C3',
                    scene='scene', portal='portal', cache='cache' if cached else None,
                    detector_required=not cached, execution_status='not_run', reason=None,
                    source_sha256='source', duration_seconds=1, decoded_frames=3,
                    processed_seconds=0, output_path=None, attempts=[])

    def execute(self, regression_only=False):
        plan = dict(analysis_revision='revision', registry_path='registry', videos=self.rows)
        save(self.plan_path, plan)
        save(self.local / 'approval.json', {})
        save(self.local / 'execution-ledger.local.json', dict(plan_sha256=runner.vc.sha256(self.plan_path),
             analysis_revision='revision', videos=self.rows))
        return runner.execute(self.plan_path, self.local / 'approval.json', self.context, regression_only=regression_only)

    def test_sequential_cached_regression_first_then_each_fresh_job_resource_gate(self):
        result = self.execute()
        order = [call.args[0][call.args[0].index('--video') + 1] for call in self.process.call_args_list]
        self.assertEqual([Path(p).stem for p in order], ['E01_007', 'E01_030', 'E01_001', 'E01_002'])
        self.assertEqual(self.gpu.call_count, 2)
        self.assertEqual(self.pending.call_count, 2)
        self.assertEqual([r['execution_status'] for r in result['videos']], ['complete'] * 4)
        for call in self.process.call_args_list:
            command = call.args[0]
            self.assertIn('--whole', command)
            self.assertIn('--camera-registry', command)

    def test_regression_only_never_queries_or_launches_gpu(self):
        result = self.execute(regression_only=True)
        self.assertEqual(self.process.call_count, 2)
        self.gpu.assert_not_called()
        self.pending.assert_not_called()
        self.assertEqual(Counter(r['execution_status'] for r in result['videos']), {'complete': 2, 'not_run': 2})

    def test_busy_gpu_stops_once_preserves_unrun_rows_no_resource_poll(self):
        self.gpu.return_value = {'available': False, 'free_mib': 6143}
        result = self.execute()
        self.assertEqual(self.process.call_count, 2)
        self.assertEqual(self.gpu.call_count, 1)
        self.assertEqual(result['videos'][0]['execution_status'], 'not_run')
        self.assertEqual(result['blocked_reason'], 'blocked_gpu_free_below_6144_mib')

    def test_busy_queue_blocks_fresh_gpu_but_allows_cached_cpu(self):
        self.pending.return_value = [dict(job_id='other', status='running')]
        result = self.execute()
        self.assertEqual(self.process.call_count, 2)
        self.assertEqual(result['blocked_reason'], 'blocked_canonical_queue_pending_work')

    def test_cpu_error_retries_once_in_distinct_preserved_attempts(self):
        self.process.side_effect = lambda *args: 1
        result = self.execute(regression_only=True)
        self.assertEqual(self.process.call_count, 4)
        self.assertTrue((self.local / 'E01_007/attempt-1').exists())
        self.assertTrue((self.local / 'E01_007/attempt-2').exists())
        self.assertTrue(all(len(r['attempts']) == 2 for r in result['videos'] if r['video_id'] in runner.REGRESSIONS))
        self.assertEqual(len(result['videos']), 4)

    def test_failed_regression_blocks_all_fresh_gpu(self):
        self.process.side_effect = lambda *args: 1
        result = self.execute()
        self.gpu.assert_not_called()
        self.assertEqual(result['blocked_reason'], 'both_cpu_regressions_must_pass_before_fresh_detector')

    def test_behavior_mismatch_is_not_retried_away(self):
        with patch.object(runner, 'regression_receipt', side_effect=ValueError('CPU regression behavior differs')):
            result = self.execute(regression_only=True)
        self.assertEqual(self.process.call_count, 2)
        self.assertTrue(all(r['execution_status'] == 'failed' for r in result['videos'] if r['video_id'] in runner.REGRESSIONS))

    def test_fresh_detector_failure_no_automatic_retry_and_continue_next_file(self):
        original = self.process.side_effect
        def process(command, *args):
            return 1 if '--cache' not in command else original(command, *args)
        self.process.side_effect = process
        result = self.execute()
        self.assertEqual(self.process.call_count, 4)
        self.assertEqual([r['execution_status'] for r in result['videos']], ['failed', 'complete', 'complete', 'failed'])
        self.assertEqual(len(result['videos'][0]['attempts']), 1)

    def test_unsettled_attempt_blocks_duplicate_or_partial_resume(self):
        self.rows[0]['attempts'] = [dict(state='running', pid=123)]
        with self.assertRaisesRegex(ValueError, 'Unsettled prior attempt'):
            self.execute()
        self.process.assert_not_called()

    def test_existing_attempt_output_never_overwritten(self):
        (self.runs / 'E01_007/attempt-1').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.execute()
        self.process.assert_not_called()

    def test_completed_resume_requires_receipt_and_exact_artifact_hashes(self):
        row = self.rows[0]
        receipt = self.local / 'receipt.json'
        save(receipt, dict(analysis_revision='revision', source_sha256='source', output_sha256={}))
        row.update(completion_receipt_path=str(receipt), completion_receipt_sha256=runner.vc.sha256(receipt), output_path=str(self.runs))
        with patch.object(runner, 'artifact_bindings', return_value={'tampered': 'hash'}):
            with self.assertRaisesRegex(ValueError, 'output bytes/bindings changed'):
                VALIDATE_RESUME(row, {'analysis_revision': 'revision'})


class DurableProgress(unittest.TestCase):
    def test_incremental_jsonl_counts_appends_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            path = output / '.image-paths-working/frame-evidence.jsonl'
            path.parent.mkdir()
            path.write_text('{"pts":0}\n')
            progress = runner.Progress()
            first = progress.snapshot(output)['observed_jsonl'][str(path)]
            self.assertEqual(first['complete_records'], 1)
            with path.open('a') as stream:
                stream.write('{"pts":0.033}\n')
            second = progress.snapshot(output)['observed_jsonl'][str(path)]
            self.assertEqual(second['complete_records'], 2)
            self.assertEqual(progress.snapshot(output)['observed_jsonl'][str(path)]['complete_records'], 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
