import copy
import unittest
from sceneguard.exp0048_media import validate_mapping,specs_for,CONTRACT

class MediaTests(unittest.TestCase):
    def row(self):
        return dict(source_pts=2.,native_pts=20,time_base='1/10',
            exp47=dict(cards=[dict(lifecycle_updated_pts=1.)],evidence=[dict(opened_pts=1.)]),
            exp48=dict(cards=[dict(lifecycle_updated_pts=2.)],evidence=[dict(opened_pts=1.)]),
            historical_boxes=dict(exp47=[dict(actual_pts=1.)],exp48=[dict(actual_pts=2.)]),
            actual_boxes=[dict(actual_pts=2.)],routing=[dict(decision_time_pts=2.)])
    def test_distinct_contract_and_no_fake_release(self):
        specs=specs_for([dict(pts=48.),dict(pts=104.966666)],dict(video_id='E01_007',resolutions=[]))
        self.assertIn('EXP0048',CONTRACT)
        self.assertEqual([s['kind'] for s in specs],['late_passage_diagnostic','unresolved_diagnostic','full_comparison'])
    def test_valid_current_past_mapping(self):validate_mapping([self.row()])
    def test_future_layers_boxes_evidence_routing_rejected(self):
        changes=[lambda r:r['exp47']['cards'][0].update(lifecycle_updated_pts=3.),
            lambda r:r['exp48']['evidence'][0].update(opened_pts=3.),
            lambda r:r['historical_boxes']['exp48'][0].update(actual_pts=3.),
            lambda r:r['actual_boxes'][0].update(actual_pts=1.),
            lambda r:r['routing'][0].update(decision_time_pts=3.)]
        for change in changes:
            r=self.row();change(r)
            with self.assertRaises(ValueError):validate_mapping([r])
    def test_clock_and_rewind_order_rejected(self):
        r=self.row();r['native_pts']=21
        with self.assertRaises(ValueError):validate_mapping([r])
        with self.assertRaises(ValueError):validate_mapping([self.row(),self.row()])

if __name__=='__main__':unittest.main()
