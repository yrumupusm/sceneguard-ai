import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('augmentation', SCRIPTS / 'prepare_action_augmentation.py')
a = importlib.util.module_from_spec(spec); spec.loader.exec_module(a)


def new(sid, family=1, scenario=1, time='2021/08/01 10:00:00', place='park', **extra):
    return dict(source_id=sid, original_filename=sid + '.mp4', scenario_family=family,
                scenario_number=scenario, date_captured=time, location=place,
                declared_frames=30, fps=3, source_sha256=None, excluded=False, errors=[], **extra)


def old(sid, family=4, scenario=1, time='2021/08/01 10:00:00', place='park', hash='oldhash'):
    return dict(source_id=sid, source_path='/local/' + sid + '.mp4', source_sha256=hash,
                scenario_family=family, scenario=scenario, excluded=False,
                label={'info': dict(location=place, date_captured=time, frame=30, fps=3)})


class ProtectionTests(unittest.TestCase):
    def group(self, rows, originals, partitions):
        assignments = {r['source_id']: dict(split=p, group_id='existing-' + r['source_id'])
                       for r, p in zip(originals, partitions)}
        return a.grouped(rows, originals, assignments, {'protectedhash'})[0]

    def test_other_family_simultaneous_camera_is_test_protected(self):
        rows = self.group([new('new_other_family')], [old('test')], ['test'])
        self.assertEqual(rows[0]['proposed_partition'], 'protected_exp0064_test')

    def test_same_scenario_across_dates_protects_test(self):
        r = new('new', family=4, time='2021/09/01 12:00:00')
        self.assertEqual(self.group([r], [old('test')], ['test'])[0]['proposed_partition'], 'protected_exp0064_test')

    def test_test_protection_transitive_through_multicamera_component(self):
        originals = [old('old_test'), old('old_other', family=5, time='2021/08/01 10:00:09')]
        r = new('new', family=5, time='2021/10/01 12:00:00')
        self.assertEqual(self.group([r], originals, ['test', 'train'])[0]['proposed_partition'], 'protected_exp0064_test')

    def test_retained_partitions_are_not_silently_reshuffled(self):
        self.assertEqual(self.group([new('n')], [old('o')], ['validation'])[0]['proposed_partition'], 'retained_validation')

    def test_train_validation_conflict_is_quarantined(self):
        originals = [old('one'), old('two', family=5)]
        self.assertEqual(self.group([new('n')], originals, ['train', 'validation'])[0]['proposed_partition'], 'quarantine')

    def test_unknown_capture_is_quarantined(self):
        self.assertEqual(self.group([new('n', time='unknown')], [], [])[0]['proposed_partition'], 'quarantine')

    def test_inspected_test_place_cannot_become_augmentation_train(self):
        r = new('n', family=8, time='2021/09/01 12:00:00')
        self.assertEqual(self.group([r], [old('test')], ['test'])[0]['proposed_partition'], 'new_evaluation_exposed_test_place')

    def test_excluded_wall_scenarios_remain_excluded(self):
        for n in (19, 35, 69, 70): self.assertTrue(a.excluded(4, n))
        for n in (18, 36, 68, 71): self.assertFalse(a.excluded(4, n))
        r = new('n'); r['excluded'] = True
        self.assertEqual(self.group([r], [], [])[0]['proposed_partition'], 'excluded_user_scenario')

    def test_known_protected_hash_overrides_fresh_metadata(self):
        r = new('n'); r['source_sha256'] = 'protectedhash'
        self.assertEqual(self.group([r], [], [])[0]['proposed_partition'], 'protected45')

    def test_fresh_group_assignment_is_order_independent(self):
        rows = [new('a'), new('b', scenario=2, time='2021/08/02 12:00:00')]
        self.assertEqual(self.group(rows, [], []), self.group(rows[::-1], [], []))

    def test_filename_family_is_metadata_not_action_truth(self):
        self.assertEqual(a.family_scenario('C_4_19_something_DF1.mp4'), (4, 19))
        self.assertEqual(a.family_scenario('unknown.mp4'), (None, None))
        self.assertEqual(self.group([new('n')], [], [])[0].get('training_eligible'), None)

    def test_content_probe_never_claims_reencoding_equivalence(self):
        def frames(h): return [dict(normalized_gray_sha256=h, ahash='0000000000000000')] * 5
        self.assertTrue(a.suspicious_content(frames('one'), frames('two')))

    def test_failed_member_quarantines_sibling_from_frozen_group(self):
        candidates = [dict(source_id=sid, group_id='g', proposed_partition='augmentation_train') for sid in ('a', 'b')]
        results = [dict(source_id='a', status='quarantine_fingerprint_or_source_error'),
                   dict(source_id='b', status='bounded_duplicate_checks_passed_semantic_review_pending')]
        a.quarantine_results(results, candidates, True)
        self.assertTrue(all(r['status'] == 'quarantine_suspected_overlap_or_group' for r in results))

    def test_collision_quarantines_earlier_match_too(self):
        candidates = [dict(source_id=sid, group_id=sid, proposed_partition='augmentation_train') for sid in ('a', 'b')]
        results = [dict(source_id='a', status='bounded_duplicate_checks_passed_semantic_review_pending'),
                   dict(source_id='b', status='quarantine_suspected_overlap', suspected_content_overlap=['a'])]
        a.quarantine_results(results, candidates, True)
        self.assertTrue(all(r['status'] == 'quarantine_suspected_overlap_or_group' for r in results))

    def test_unseen_evaluation_place_does_not_split_into_training(self):
        x = new('one', place='newpark'); x['events'] = [{'class_name': 'stand'}, {'class_name': 'wall_over'}]
        y = new('two', place='newpark', scenario=2, time='2021/09/01 12:00:00'); y['events'] = []
        r = self.group([x, y], [], [])
        self.assertTrue(all(x['proposed_partition'] == 'new_evaluation_reserved_place' for x in r))


class ExplicitLabelTests(unittest.TestCase):
    def data(self):
        return dict(info=dict(filename='n.mp4', height=100, width=100, date_captured='2021/08/01 10:00:00',
                    frame=30, fps=3, location='park', video_length='00:00:10'),
                    events=[dict(actor_id=0, object_id=1, ev_start_frame=1, ev_end_frame=12,
                                 start_time='00:00:00', end_time='00:00:04')],
                    annotations=[dict(actor_id=0, object_id=1, cur_frame=i, class_name='stand',
                                      bbox=[[10, 10], [20, 30]]) for i in range(1, 13)])

    def test_stand_label_stays_actor_interval_not_training_negative(self):
        events, errors, _ = a.intervals(self.data())
        self.assertEqual(errors, []); self.assertEqual(events[0]['class_name'], 'stand')
        self.assertFalse(events[0]['training_eligible']); self.assertTrue(events[0]['both_origin_interior_eight_frames_possible'])

    def test_annotation_absence_never_becomes_negative(self):
        d = self.data(); d['annotations'] = []
        events, errors, _ = a.intervals(d)
        self.assertEqual(events[0]['class_name'], 'ambiguous_or_missing')
        self.assertIn('event_without_declared_actor_boxes', errors)

    def test_mixed_classes_require_quarantine_not_majority_label(self):
        d = self.data(); d['annotations'][0]['class_name'] = 'wall_over'
        events, _, warnings = a.intervals(d)
        self.assertEqual(events[0]['class_name'], 'ambiguous_or_missing')
        self.assertIn('event_multiple_classes', warnings)

    def test_review_anchor_needs_nine_annotations_for_both_origins(self):
        d = self.data(); event = a.intervals(d)[0][0]
        source = dict(new('n'), source_reference={}, label_reference={}, label_sha256='label',
                      width=100, height=100, group_id='g', proposed_partition='augmentation_validation')
        e = a.event_evidence(source, event, d)
        self.assertEqual(len(e['label_only_center_frame_indices']), 8)
        self.assertEqual(len(e['both_origin_required_annotation_frames']), 9)
        self.assertIsNone(e['binary_training_label']); self.assertFalse(e['native_center_decode_verified'])
        d['annotations'] = [ann for ann in d['annotations'] if ann['cur_frame'] != e['both_origin_required_annotation_frames'][0]]
        self.assertEqual(a.event_evidence(source, event, d)['status'], 'annotation_center_unavailable')


class OutputPathTests(unittest.TestCase):
    def test_fresh_owned_revision_allowed_and_outside_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'owned'; root.mkdir()
            self.assertEqual(a.checked_output(root / 'augmentation-v2', root), root / 'augmentation-v2')
            with self.assertRaises(ValueError): a.checked_output(Path(tmp) / 'augmentation-v2', root)
            with self.assertRaises(ValueError): a.checked_output(root, root)
            outside = Path(tmp) / 'elsewhere'; outside.mkdir()
            (root / 'augmentation-link').symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError): a.checked_output(root / 'augmentation-link', root)


if __name__ == '__main__': unittest.main()
