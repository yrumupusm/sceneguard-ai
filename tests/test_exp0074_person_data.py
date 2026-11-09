"""Integrity and scope checks for EXP0074 person-data exports."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from scripts import prepare_exp0074_person_data as data


class RepairScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.drafts = [data.read(data.REPAIR/f'{rid}-repaired-draft.json') for rid in ('R01', 'R02', 'R03')]
        cls.approval = data.read(data.APPROVAL)

    def export_rows(self):
        return data.integrate_repairs(self.drafts, self.approval)

    def test_exact_five_approved_replacements_without_automatic_GT(self):
        rows, removed = self.export_rows()
        confirmed = [(f, b) for f in rows for b in f['boxes'] if b['coordinate_confirmed']]
        self.assertEqual(len(confirmed), 5)
        self.assertEqual(len(rows), 72)
        self.assertTrue(all(not f['person_completeness_verified'] for f in rows))
        self.assertTrue(all(not f['standard_train_eligible'] and not f['full_frame_metrics_eligible'] for f in rows))
        day = next(f for f in rows if f['frame_id'] == 'exp0073-r01-frame-000060')
        self.assertEqual(day['boxes'][0]['xyxy'][3], 647.0)
        self.assertEqual(day['boxes'][0]['id'], 'R01-60-repair-bottom-v2')

    def test_all_other_coordinates_and_ids_preserved(self):
        rows, _ = self.export_rows()
        original = {(d['review_id'], f['decoded_index']): f for d in self.drafts for f in d['frames']}
        for f in rows:
            old = original[f['review_id'], f['decoded_index']]
            before = [(b['id'], b['xyxy']) for b in old['boxes'] if not b['id'].endswith('-repair')]
            after = [(b['id'], b['xyxy']) for b in f['boxes'] if not b['coordinate_confirmed']]
            self.assertEqual(before, after)

    def test_background_removals_are_exact_and_not_reintroduced(self):
        rows, removed = self.export_rows()
        self.assertEqual(len(removed), 17)
        self.assertEqual(len({b['frame_id'] for b in removed}), 13)
        remaining = {b['id'] for f in rows for b in f['boxes']}
        self.assertFalse(remaining & {b['id'] for b in removed})
        p01 = [f for f in rows if f['review_id'] == 'R03']
        self.assertEqual(len(p01), 24)
        self.assertTrue(all(f['disposition'] == 'held_incomplete' for f in p01))
        self.assertEqual(sum(len(f['boxes']) for f in p01), 112)

    def test_night70_entire_frame_excluded(self):
        rows, _ = self.export_rows()
        excluded = [f for f in rows if f['whole_frame_hold']]
        self.assertEqual([(f['review_id'], f['decoded_index']) for f in excluded], [('R02', 70)])
        self.assertEqual(excluded[0]['disposition'], 'excluded_whole_frame_uncertain')
        self.assertEqual(len(excluded[0]['boxes']), 2)
        self.assertFalse(excluded[0]['confirmed_person_boxes'])

    def test_wrong_source_pts_or_completeness_claim_rejected(self):
        for key, value in [('source_pts', 20.333), ('whole_frame_completeness_confirmed', True), ('source_sha256', '0'*64)]:
            approval = deepcopy(self.approval)
            approval['frames'][0][key] = value
            with self.assertRaises(ValueError):
                data.integrate_repairs(self.drafts, approval)

    def test_missing_or_extra_approval_rejected(self):
        for frames in (self.approval['frames'][:-1], self.approval['frames']+[self.approval['frames'][0]]):
            approval = deepcopy(self.approval)
            approval['frames'] = frames
            with self.assertRaises(ValueError):
                data.integrate_repairs(self.drafts, approval)

    def test_triage_does_not_change_or_confirm_proposals(self):
        rows, _ = self.export_rows()
        before = deepcopy(rows)
        candidates = data.overlap_candidates(rows)
        self.assertTrue(any(f['review_id'] == 'R03' for f in candidates))
        self.assertEqual(before, rows)
        self.assertFalse(any(f['frame_id'] == 'exp0073-r02-frame-000070' for f in candidates))

    def test_separate_export_hashes_and_excluded_frame_has_no_label(self):
        folder = data.ROOT/'outputs/model-comparison/exp0074/label-corrections-v1'
        manifest = data.read(folder/'manifest.json')
        self.assertEqual(manifest['complete_new_ground_truth_frames'], 0)
        self.assertEqual(manifest['held_incomplete_yolo_boxes'], 167)
        self.assertEqual(manifest['approved_replacement_boxes'], 5)
        self.assertFalse(manifest['standard_train_eligible'])
        self.assertFalse(manifest['full_frame_metrics_eligible'])
        self.assertEqual(len(list((folder/'incomplete-yolo').glob('*.txt'))), 71)
        for frame in manifest['frames']:
            self.assertEqual(data.sha(frame['image']), frame['image_sha256'])
            if frame['whole_frame_hold']:
                self.assertIsNone(frame['label'])
                self.assertIsNone(frame['label_sha256'])
            else:
                data.validate_frame(dict(frame, confirmed_person_boxes=frame['boxes']))
        data.preserved(manifest['input_sha256'])
        self.assertEqual(data.sha(folder/'exporter-source.py'), manifest['exporter_sha256'])
        for filename, expected in manifest['derived_files'].items():
            self.assertEqual(data.sha(folder/filename), expected)


class FrozenCohortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = data.ROOT/'outputs/model-comparison/exp0074/person-data-v1'
        cls.manifest = data.read(cls.folder/'manifest.json')

    def test_frozen197_all_original_bytes_labels_and_coordinates(self):
        rows = self.manifest['frames']
        self.assertEqual(len(rows), 197)
        originals = {f['frame_id']: f for p in (data.OLD, data.NEW) for f in data.read(p)['frames']}
        for f in rows:
            data.validate_frame(f)
            old = originals[f['frame_id']]
            self.assertEqual(f['confirmed_person_boxes'], old.get('confirmed_person_boxes', old.get('person_boxes')))
            self.assertEqual(f['image_sha256'], old['image_sha256'])
            self.assertEqual(f['label_sha256'], old['label_sha256'])
            self.assertTrue(f['person_completeness_verified'])
        data.validate_splits(rows)
        self.assertEqual(self.manifest['frame_counts'], {'train': 122, 'development': 75})
        self.assertEqual(self.manifest['box_counts'], {'train': 333, 'development': 56})
        self.assertEqual(self.manifest['explicit_empty_frame_counts'], {'train': 0, 'development': 25})

    def test_case5_reservation_is_legacy_closure_not19(self):
        case5 = [f for f in self.manifest['frames'] if f.get('case_number') == 5]
        self.assertEqual(len(case5), 25)
        for f in case5:
            self.assertEqual(f['event_group'], 'aug-409dbbc92fa789ba34f9')
            self.assertEqual(f['capture_reservation'], 'legacy-closure-aug-409dbbc92fa789ba34f9')
            self.assertTrue(f['capture_relation_unresolved'])
            self.assertEqual(f['split'], 'development')

    def test_P05_both_reviewed_people_and_explicit_empty_retained(self):
        rows = [f for f in self.manifest['frames'] if f.get('capture_reservation') == 'capture-reservation-05']
        self.assertEqual(len(rows), 50)
        self.assertEqual(sum(not f['confirmed_person_boxes'] for f in rows), 25)
        self.assertEqual(sum(len(f['confirmed_person_boxes']) for f in rows), 25)
        self.assertEqual({f['split'] for f in rows}, {'development'})

    def test_split_leakage_and_duplicate_source_frames_rejected(self):
        original = self.manifest['frames'][0]
        for key in ('source_sha256', 'event_group', 'capture_reservation'):
            other = deepcopy(next(f for f in self.manifest['frames'] if f['split'] == 'development'))
            other[key] = original[key]
            with self.assertRaises(ValueError):
                data.validate_splits([original, other])
        with self.assertRaises(ValueError):
            data.validate_splits([original, deepcopy(original)])

    def test_hash_tampering_and_existing_output_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            label = Path(tmp)/'label.txt'
            label.write_text('tampered\n')
            frame = deepcopy(self.manifest['frames'][0])
            frame['label'] = str(label)
            with self.assertRaises(ValueError):
                data.validate_frame(frame)
            with self.assertRaises(FileExistsError):
                data.save(label, {})
        with self.assertRaises(FileExistsError):
            data.freeze(self.folder)

    def test_frozen_exporter_and_all_source_evidence_preserved(self):
        data.preserved(self.manifest['input_sha256'])
        self.assertEqual(data.sha(self.folder/'exporter-source.py'), self.manifest['exporter_sha256'])
        self.assertFalse(self.manifest['protected_school_or_test_used'])
        self.assertFalse(self.manifest['physical_capture_independence_certified'])


if __name__ == '__main__':
    unittest.main()
