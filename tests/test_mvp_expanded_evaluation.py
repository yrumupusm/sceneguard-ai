from copy import deepcopy
import unittest
from scripts.mvp_expanded_evaluation import mapped_row, rebind_gate


class ExpandedTruthTests(unittest.TestCase):
    def test_only_gate_identity_changes_in_truth(self):
        truth = dict(events=[dict(gate_id='unknown', start=1.25, end=3.75)],
                     unresolved_reference_events=1, original_event_frame=[[4,9]],
                     verified_non_event_intervals=[dict(gate_id='unknown',start=0,end=1)])
        frozen = deepcopy(truth)
        new = rebind_gate(truth, 'C8_fence')
        self.assertEqual(truth, frozen)
        self.assertEqual(new['events'][0],dict(gate_id='C8_fence',start=1.25,end=3.75))
        self.assertEqual(new['unresolved_reference_events'],1)
        self.assertEqual(new['original_event_frame'],[[4,9]])

    def test_source_binding_split_and_media_duration_preserved(self):
        row = dict(path='/synthetic/source.mp4',sha256='a',split='prior_use_unknown',
                   media=dict(average_rate='30000/1001',duration_seconds=.06673333333333333))
        registry = dict(sources={row['path']:dict(sha256='a',camera_id='C8')},
                        cameras=dict(C8=dict(legacy_boundary_config=dict(boundary_id='C8_fence'))))
        clocks = dict(native_pts=[0,3003,6006],time_base='1/90000')
        new = mapped_row(row,registry,clocks)
        self.assertEqual(new['split'],row['split'])
        self.assertEqual(new['media']['duration_seconds'],row['media']['duration_seconds'])
        self.assertAlmostEqual(new['media']['full_native_end_seconds'],.1001)
        self.assertNotIn('full_native_end_seconds',row['media'])
        registry['sources'][row['path']]['sha256']='different'
        with self.assertRaisesRegex(ValueError,'same original source'):
            mapped_row(row,registry,clocks)
