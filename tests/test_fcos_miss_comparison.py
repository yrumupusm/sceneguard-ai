import copy
from fractions import Fraction
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

SPEC = importlib.util.spec_from_file_location('prepare_cohort', Path(__file__).resolve().parents[1] / 'scripts/prepare_fcos_miss_comparison.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def fixture():
    clock = dict(time_base='1/30', native_pts=list(range(61)))
    meta = dict(video_id='E01_007', source_size=[100, 80], frames=61,
                person_boxes=1, frames_with_person=1, config=dict(roi=[0, 0, .5, .5]))
    rows = [dict(pts=i/30, native_pts=i, time_base='1/30', source_size=[100, 80],
                 boxes=[], scores=[]) for i in range(61)]
    # Raw low score remains evidence before project0.5; it is not a project observation.
    rows[1].update(boxes=[[1, 1, 10, 10], [60, 50, 90, 75]], scores=[.3, .8])
    return clock, meta, rows


class CohortTests(unittest.TestCase):
    def scan(self, rows=None, meta=None, clock=None, expected=None):
        c, m, r = fixture()
        c, m, r = clock or c, meta or m, rows if rows is not None else r
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'person_cache.jsonl'
            path.write_text(''.join(json.dumps(x)+'\n' for x in r))
            digest = MODULE.sha(path)
            sink, receipts = io.StringIO(), {}
            result, stats = MODULE.scan_cache(path, m, c, sink, receipts, expected or digest)
            self.assertEqual(receipts[str(path)], digest)
            return result, stats, [json.loads(line) for line in sink.getvalue().splitlines()]

    def test_native_inventory_retains_empty_frames_and_raw_project_roi_layers(self):
        rows, stats, written = self.scan()
        self.assertEqual(len(written), 61)
        self.assertEqual(stats['raw_person_rows'], 2)
        self.assertEqual(stats['project_person_rows'], 1)
        self.assertEqual(stats['roi_raw_person_rows'], 1)
        self.assertEqual(stats['roi_project_person_rows'], 0)
        self.assertEqual(written[0]['raw_person_rows'], 0)
        self.assertNotIn('detector_false_negative', stats)

    def test_nearest_mapping_tie_is_earlier(self):
        self.assertEqual(MODULE.nearest([Fraction(0), Fraction(2)], Fraction(1)), 0)
        self.assertEqual(MODULE.nearest([Fraction(0), Fraction(2)], Fraction(3)), 1)

    def test_native_2997_and_irregular_gap_never_use_index_divided_by30(self):
        pts = [Fraction(t, 90000) for t in (0, 3003, 9009)]
        self.assertEqual(MODULE.nearest(pts, Fraction(66, 1000)), 1)
        self.assertNotEqual(float(pts[2]), 2/30)

    def test_center_index8_and_exact_physical_spacing(self):
        ticks = list(range(121));points = [Fraction(i, 30) for i in ticks]
        row = MODULE.window('E01_007', points, ticks, '1/30', Fraction(2), 'regular', '001')
        self.assertEqual(row['sample_requested_pts'][8], 2.)
        self.assertEqual(row['sample_frame_indices'], list(range(28, 89, 4)))
        self.assertEqual(row['available_after_pts'], 88/30)
        self.assertFalse(any(row['boundary_repeat_mask']))
        self.assertFalse(row['fcos_proposals_used'])

    def test_boundary_repeats_are_marked_and_not_new_observations(self):
        ticks = list(range(61));points = [Fraction(i, 30) for i in ticks]
        row = MODULE.window('E01_007', points, ticks, '1/30', Fraction(0), 'regular', '000')
        self.assertEqual(sum(row['boundary_repeat_mask']), 8)
        self.assertEqual(sum(row['duplicate_sample_mask']), 8)
        self.assertEqual(row['unique_native_frames'], 8)
        self.assertEqual(row['sample_frame_indices'][:9], [0]*9)

    def test_no_future_frame_is_marked_available_at_anchor(self):
        ticks = list(range(121));points = [Fraction(i, 30) for i in ticks]
        row = MODULE.window('E01_007', points, ticks, '1/30', Fraction(2), 'regular', '001')
        self.assertGreater(row['available_after_pts'], row['anchor_pts'])

    def test_changed_cache_hash_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'cache hash'):
            self.scan(expected='0'*64)

    def test_missing_duplicate_or_changed_native_frame_rejected(self):
        for alteration in ('missing', 'duplicate', 'wrong_time'):
            with self.subTest(alteration=alteration):
                c, m, rows = fixture()
                if alteration == 'missing': rows.pop(10)
                elif alteration == 'duplicate': rows.insert(10, rows[9])
                else: rows[10]['pts'] += .01
                with self.assertRaises(ValueError): self.scan(rows=rows)

    def test_wrong_size_and_time_base_rejected(self):
        for key,value in [('source_size', [99,80]),('time_base', '1/29')]:
            c,m,rows=fixture();rows[0][key]=value
            with self.assertRaises(ValueError): self.scan(rows=rows)

    def test_nonfinite_or_invalid_box_score_rejected(self):
        for key,value in [('scores',[float('nan'),.8]),('scores',[.3,1.1]),
                          ('boxes',[[1,1,110,10],[60,50,90,75]])]:
            c,m,rows=fixture();rows[1][key]=value
            with self.assertRaises(ValueError): self.scan(rows=rows)

    def test_cache_counts_must_match_original_run_receipt(self):
        c,m,rows=fixture();m['person_boxes']=2
        with self.assertRaisesRegex(ValueError, 'totals'):
            self.scan(meta=m)

    def test_valid_numbers_different_from_frozen_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'a.json';path.write_text('{"score":0.2}')
            expected=MODULE.sha(path);path.write_text('{"score":0.3}')
            with self.assertRaises(ValueError): MODULE.read(path,{},expected)

    def test_duplicate_json_and_nonfinite_number_rejected(self):
        for raw in ['{"a":1,"a":2}', '{"a":NaN}']:
            with self.assertRaises(ValueError): MODULE.parse(raw)

    def test_review_versions_and_all9_bindings_required(self):
        rows=[dict(id=f'request-{i}',experiment_id='EXP-0065',version=4,answer_version=1,
                   status='applied',answer='human observation',source_binding_sha256='1'*64)
              for i in range(9)]
        self.assertEqual(len(MODULE.review_bindings(dict(requests=rows))),9)
        rows[0]['answer_version']=0
        with self.assertRaises(ValueError): MODULE.review_bindings(dict(requests=rows))
        with self.assertRaises(ValueError): MODULE.review_bindings(dict(requests=rows[1:]))

    def test_documented_failures_are_separate_from_gap_and_semantic_controls(self):
        spec=dict(primary_cohort=dict(known_cases=[dict(id='old',video_id='E01_007')]))
        rows=MODULE.case_specs(spec);byid={r['video_id']:r for r in rows}
        self.assertEqual(byid['E01_007']['cohort_role'],'historically_documented_detection_failure')
        self.assertEqual(byid['E01_039']['cohort_role'],'reviewed_box_gap_cause_unresolved')
        self.assertEqual(byid['E01_034']['cohort_role'],'reviewed_standing_action_control')
        self.assertEqual(byid['E01_021']['cohort_role'],'reviewed_sidepath_semantic_control')

    def test_existing_output_rejected_before_any_input_or_media_read(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError,'Existing outputs'):
                MODULE.run(SimpleNamespace(output=Path(folder)))


if __name__ == '__main__':
    unittest.main()
