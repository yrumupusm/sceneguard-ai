from copy import deepcopy
import unittest
from sceneguard.exp0049_media import snapshot, specs_for, validate_mapping, CONTRACT
from test_exp0049_application import make_prior, frames


class MediaTests(unittest.TestCase):
    def row(self):
        return dict(source_pts=2.,native_pts=20,time_base='1/10',presentation_pts=0.,
            frame_index=1, exp48=dict(cards=[dict(first_alert_pts=1.,lifecycle_updated_pts=1.)],
                evidence=[dict(opened_pts=1.,last_state_change_pts=1.)]),
            exp49=dict(cards=[dict(first_alert_pts=1.,lifecycle_updated_pts=2.,
                first_confirmation_pts=None,observation_closed_pts=None,
                last_gate_observation_pts=1.,last_gate_observation_refs=[dict(pts=1.)])],
                evidence=[dict(opened_pts=1.,last_state_change_pts=1.)]),
            actual_boxes=[dict(actual_pts=2.)],last_gate_boxes=[dict(actual_pts=1.)],
            portal_observation_refs=[dict(pts=2.,frame_index=1,cache_index=0)],
            routing=[dict(decision_time_pts=2.)])

    def test_all_cards_evidence_not_only_latest_card_snapshot(self):
        prior=make_prior()
        for row in prior['timeline']:
            row['card']=dict(incident_id=row['incident_id'])
        self.assertEqual(len(snapshot(prior,14.)['evidence']),2)
        self.assertEqual(len(snapshot(prior,4.)['evidence']),1)
        self.assertIsNone(snapshot(prior,4.)['evidence'][0]['first_confirmation_pts'])
        self.assertEqual(snapshot(prior,.1)['evidence'],[])

    def test_contract_and_bounded_changed_windows(self):
        result=dict(video_id='E01_030',closed_cards=[],source_to_activity_cards={})
        specs=specs_for([dict(pts=84.),dict(pts=99.966667)],result)
        self.assertIn('EXP0049',CONTRACT)
        self.assertEqual([s['kind'] for s in specs],['full_comparison','changed_grouping'])
        self.assertEqual(specs[1]['start'],96.)

    def test_valid_causal_mapping(self): validate_mapping([self.row()])

    def test_future_state_closure_box_and_routing_rejected(self):
        mutations=[lambda r:r['exp49']['cards'][0].update(first_confirmation_pts=3.),
            lambda r:r['exp49']['cards'][0].update(observation_closed_pts=3.),
            lambda r:r['exp49']['cards'][0].update(last_gate_observation_pts=3.),
            lambda r:r['exp49']['cards'][0]['last_gate_observation_refs'][0].update(pts=3.),
            lambda r:r['exp48']['evidence'][0].update(last_state_change_pts=3.),
            lambda r:r['exp49']['evidence'][0].update(first_confirmation_pts=3.),
            lambda r:r['last_gate_boxes'][0].update(actual_pts=3.),
            lambda r:r['actual_boxes'][0].update(actual_pts=1.),
            lambda r:r['portal_observation_refs'][0].update(pts=1.),
            lambda r:r['routing'][0].update(decision_time_pts=3.)]
        for change in mutations:
            row=self.row();change(row)
            with self.assertRaises(ValueError): validate_mapping([row])

    def test_native_presentation_and_order_mismatch_rejected(self):
        for key,value in [('native_pts',21),('presentation_pts',1.)]:
            row=self.row();row[key]=value
            with self.assertRaises(ValueError): validate_mapping([row])
        with self.assertRaises(ValueError): validate_mapping([self.row(),self.row()])

if __name__=='__main__': unittest.main()
