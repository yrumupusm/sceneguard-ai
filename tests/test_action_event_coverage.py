import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest


SOURCE = Path(__file__).resolve().parents[1] / 'scripts/audit_action_event_coverage.py'
SPEC = importlib.util.spec_from_file_location('action_event_coverage', SOURCE)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def fixture():
    points = [i / 3 for i in range(12)]
    windows = []
    for start in (0, 3):
        windows.append(dict(window_id=f'{start:06d}-a', track_id='a',
                            start_target_index=start, end_target_index=start + 7,
                            sample_pts=points[start:start + 8],
                            sample_frame_indices=list(range(start, start + 8)),
                            boxes=[[.1, .2, .3, .4]] * 8, roi_xyxy=[1, 2, 30, 40],
                            available_after_pts=points[start + 7]))
    plan = dict(video_id='E01_001', source_sha256='1' * 64, last_pts=points[-1],
                samples=[dict(pts=p) for p in points], windows=windows,
                missing_windows=[dict(track_id='b', start_target_index=0, missing_target_indices=list(range(1, 8))),
                                 dict(track_id='c', start_target_index=0, missing_target_indices=list(range(8)))],
                counts=dict(eligible_windows=2, partial_observations_windows=1, no_observations_windows=1))
    scores = [dict(**w, video_id=plan['video_id'], source_sha256=plan['source_sha256'],
                   plan_sha256='2' * 64, model_provenance=dict(sha256=AUDIT.MODEL_SHA),
                   score=score, threshold=.5, action='climbing_action_candidate' if score >= .5 else None,
                   baseline_state_modified=False, batch_flushed_at_source_pts=points[-1])
              for w, score in zip(windows, (.9, .1))]
    refs = dict(video_id=plan['video_id'], video_sha256=plan['source_sha256'],
                truth_basis='official_reference',
                events=[dict(id='event-1', gate_id='gate', start=1., end=2.)],
                verified_non_event_intervals=[], unresolved_reference_events=0)
    return plan, scores, refs


def put(path, value, jsonl=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = ('\n'.join(json.dumps(r) for r in value) + '\n') if jsonl else json.dumps(value)
    path.write_text(raw)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def saved_fixture(root):
    plan, scores, refs = fixture()
    plan_path = root / 'plan/E01_001.json'
    plan_hash = put(plan_path, plan)
    for row in scores:
        row['plan_sha256'] = plan_hash
    refs_path = root / 'baseline/after-manifest.json'
    refs_hash = put(refs_path, dict(videos=[refs]))
    report_path = root / 'baseline/after-report.json'
    report_hash = put(report_path, dict(modes=dict(confirmation=dict(by_video=[
        dict(video_id='E01_001', matches=[dict(outcome='tp', truth_id='event-1')])]))))
    lock_path = root / 'baseline/lock.json'
    lock_hash = put(lock_path, dict(status='verified', baseline_experiment='EXP-0062',
                                   verified_paths={str(refs_path): refs_hash, str(report_path): report_hash}))
    manifest_path = root / 'plan/manifest.json'
    manifest_hash = put(manifest_path, dict(videos=[dict(video_id='E01_001', path=str(plan_path), sha256=plan_hash)],
                                           baseline_lock=dict(sha256=lock_hash),
                                           policy=dict(threshold=.5, frames=8, step=3)))
    result_path = root / 'inference/result.json'
    result_hash = put(result_path, dict(status='advisory_inference_complete', baseline_state_changes=False,
                                       production_integration=False, videos=[dict(video_id='E01_001', scored_windows=2)],
                                       totals=dict(scored_windows=2, candidate_windows=1)))
    put(root / 'inference/E01_001/window-scores.jsonl', scores, jsonl=True)
    return SimpleNamespace(baseline_lock=lock_path, baseline_lock_sha256=lock_hash,
                           plan=manifest_path, plan_sha256=manifest_hash,
                           inference_result=result_path, inference_result_sha256=result_hash,
                           references=refs_path, baseline_report=report_path,
                           checkpoint_sha256=AUDIT.MODEL_SHA, expected_videos=1,
                           expected_references=1, output=root / 'new-diagnostics')


class EventCoverageTests(unittest.TestCase):
    def setUp(self):
        self.plan, self.scores, self.refs = fixture()

    def audit(self):
        return AUDIT.audit_video(self.plan, self.scores, self.refs)

    def test_temporal_overlap_does_not_certify_person_gate_or_tp(self):
        event = self.audit()['events'][0]
        self.assertEqual(event['diagnostic'], 'candidate_time_overlap')
        self.assertEqual(event['candidate_windows'], 1)
        self.assertIn('identity_and_gate_unknown', event['relation'])
        self.assertIsNone(event['action_true_positive'])
        self.assertIsNone(event['detector_false_negative'])

    def test_scored_below_threshold_is_distinct_from_missing_input(self):
        self.scores[0]['score'] = .2
        self.assertEqual(self.audit()['events'][0]['diagnostic'], 'scored_without_candidate_time_overlap')

    def test_partial_input_is_not_classifier_negative(self):
        self.plan['windows'] = []
        self.plan['counts']['eligible_windows'] = 0
        self.scores = []
        event = self.audit()['events'][0]
        self.assertEqual(event['diagnostic'], 'partial_observations_only')
        self.assertIsNone(event['max_score'])
        self.assertIsNone(event['detector_false_negative'])

    def test_absent_track_crossproducts_are_not_operational_misses(self):
        self.plan['windows'] = []
        self.plan['counts']['eligible_windows'] = 0
        self.plan['missing_windows'] = self.plan['missing_windows'][1:]
        self.plan['counts']['partial_observations_windows'] = 0
        self.scores = []
        self.assertEqual(self.audit()['events'][0]['diagnostic'], 'no_observed_window_in_reference')

    def test_half_open_boundary_and_actual_samples_not_bounding_span(self):
        self.assertFalse(AUDIT.has_sample([0., 1., 2.], (0.1, .9)))
        self.assertFalse(AUDIT.has_sample([1.], (0., 1.)))
        self.assertTrue(AUDIT.has_sample([1.], (1., 2.)))

    def test_normal_interval_requires_all_eight_samples(self):
        self.refs['verified_non_event_intervals'] = [dict(gate_id='gate', start=0., end=2.34)]
        row = self.audit()['reviewed_negative_intervals'][0]
        self.assertEqual(row['fully_contained_candidate_window_ids'], ['000000-a'])
        self.assertEqual(row['edge_overlapping_window_ids'], ['000003-a'])
        self.assertEqual(row['interpretation'], 'review_candidates_not_verified_false_alarms')

    def test_outside_positive_annotation_is_not_negative(self):
        self.refs['events'][0].update(start=3.5, end=3.6)
        result = self.audit()
        self.assertEqual(result['outside_official_reference_candidate_ids'], ['000000-a'])
        self.assertTrue(result['outside_reference_is_not_negative'])
        self.assertEqual(result['reviewed_negative_intervals'], [])

    def test_consecutive_candidates_merge_only_with_same_track(self):
        self.scores[1]['score'] = .8
        spans = AUDIT.candidate_spans(self.plan, self.scores)
        self.assertEqual(len(spans), 1)
        self.assertEqual(len(spans[0]['window_ids']), 2)
        self.scores[1]['track_id'] = 'other'
        self.assertEqual(len(AUDIT.candidate_spans(self.plan, self.scores)), 2)

    def test_candidate_gap_is_not_merged(self):
        self.scores[1].update(score=.8, start_target_index=6)
        self.assertEqual(len(AUDIT.candidate_spans(self.plan, self.scores)), 2)

    def test_frozen_score_identity_and_pixels_contract(self):
        AUDIT.validate_scores(self.plan, self.scores, '2' * 64, AUDIT.MODEL_SHA)
        for key, changed in [('source_sha256', '9' * 64), ('plan_sha256', '9' * 64),
                             ('roi_xyxy', [0, 0, 10, 10]), ('sample_pts', [0] * 8),
                             ('threshold', .4), ('score', float('nan')),
                             ('baseline_state_modified', True), ('action', None),
                             ('batch_flushed_at_source_pts', 0.)]:
            with self.subTest(key=key):
                wrong = copy.deepcopy(self.scores)
                wrong[0][key] = changed
                with self.assertRaises(ValueError):
                    AUDIT.validate_scores(self.plan, wrong, '2' * 64, AUDIT.MODEL_SHA)

    def test_missing_score_is_not_silently_filled(self):
        with self.assertRaises(ValueError):
            AUDIT.validate_scores(self.plan, self.scores[:1], '2' * 64, AUDIT.MODEL_SHA)

    def test_duplicate_score_is_rejected(self):
        with self.assertRaises(ValueError):
            AUDIT.validate_scores(self.plan, self.scores + self.scores[:1], '2' * 64, AUDIT.MODEL_SHA)

    def test_wrong_source_and_missing_counts_are_rejected(self):
        self.refs['video_sha256'] = '9' * 64
        with self.assertRaises(ValueError):
            self.audit()
        self.refs['video_sha256'] = self.plan['source_sha256']
        self.plan['counts']['partial_observations_windows'] = 2
        with self.assertRaises(ValueError):
            self.audit()

    def test_unresolved_reference_preserved_without_inventing_event(self):
        self.refs.update(events=[], truth_basis='unresolved', unresolved_reference_events=1)
        result = self.audit()
        self.assertEqual(result['events'], [])
        self.assertEqual(result['unresolved_reference_events'], 1)

    def test_baseline_matching_is_separate_from_action_candidate(self):
        row = AUDIT.audit_video(self.plan, self.scores, self.refs, set())['events'][0]
        self.assertFalse(row['baseline_confirmation_matched'])
        self.assertEqual(row['diagnostic'], 'candidate_time_overlap')
        self.assertIsNone(row['action_true_positive'])

    def test_duplicate_json_and_nonfinite_input_rejected(self):
        for raw in ('{"score": 0, "score": 1}', '{"score": NaN}', '{"score": Infinity}'):
            with self.assertRaises(ValueError):
                AUDIT.parse(raw)


class SavedInputTests(unittest.TestCase):
    def test_end_to_end_saved_json_inputs_and_output_preservation(self):
        with tempfile.TemporaryDirectory() as folder:
            args = saved_fixture(Path(folder))
            originals = {str(p): p.read_bytes() for p in Path(folder).rglob('*') if p.is_file()}
            summary = AUDIT.run(args)
            self.assertEqual(summary['official_reference_events'], 1)
            self.assertEqual(summary['event_diagnostic_counts'], {'candidate_time_overlap': 1})
            self.assertIsNone(summary['intrusion_improvement'])
            self.assertIsNone(summary['precision'])
            self.assertTrue((args.output / 'event-diagnostics.csv').is_file())
            self.assertTrue(all(Path(p).read_bytes() == data for p, data in originals.items()))
            saved = (args.output / 'summary.json').read_bytes()
            with self.assertRaises(ValueError):
                AUDIT.run(args)
            self.assertEqual((args.output / 'summary.json').read_bytes(), saved)

    def test_changed_locked_reference_fails_before_output_creation(self):
        with tempfile.TemporaryDirectory() as folder:
            args = saved_fixture(Path(folder))
            args.references.write_text('{}')
            with self.assertRaises(ValueError):
                AUDIT.run(args)
            self.assertFalse(args.output.exists())

    def test_missing_prediction_file_fails_without_fake_result(self):
        with tempfile.TemporaryDirectory() as folder:
            args = saved_fixture(Path(folder))
            (args.inference_result.parent / 'E01_001/window-scores.jsonl').unlink()
            with self.assertRaises(FileNotFoundError):
                AUDIT.run(args)
            self.assertFalse(args.output.exists())

    def test_expected_inventory_and_reference_count_are_not_relaxed(self):
        for field in ('expected_videos', 'expected_references'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                args = saved_fixture(Path(folder))
                setattr(args, field, 99)
                with self.assertRaises(ValueError):
                    AUDIT.run(args)
                self.assertFalse(args.output.exists())

    def test_unlocked_reference_path_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            args = saved_fixture(Path(folder))
            other = Path(folder) / 'new-truth.json'
            other.write_bytes(args.references.read_bytes())
            args.references = other
            with self.assertRaises(ValueError):
                AUDIT.run(args)


if __name__ == '__main__':
    unittest.main()
