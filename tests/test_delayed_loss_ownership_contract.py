"""One measured endpoint cannot confirm two raw candidates or raw+run paths."""
from copy import deepcopy
from dataclasses import asdict
import unittest
from tests.test_gate_observation import fixture,scene
from sceneguard.approach_disappearance import Policy
from sceneguard.exp0048_application import replay_scoped
from sceneguard.gate_observation import GateObservationDirection
from sceneguard.incident_cards import GroupPolicy
from sceneguard.incident_lifecycle import CONFIRMED,SUSPECTED
from sceneguard.portal_births import make_region


def run_shared_endpoint(two=True,reverse=False,end=21,turn_back=False):
    xs=[440,450,460]+([480,460,440,420] if turn_back else [480,500,500,500])+[500]*14
    frames,source,_=fixture(xs);frames=frames[:end];source=dict(source,id='a')
    runs={'a':deepcopy(source['rows'])}
    for f in frames[7:]:f['actual_boxes']=[];f['point_paths']=[]
    events=[]
    for eid,at in ([('old',1.2),('new',1.3)] if two else [('new',1.2)]):
        raw=dict(segment='a',raw_id=7,decision_time_pts=at,last_observed_pts=.2,
            reason='recent_gate_presence_then_loss',status=SUSPECTED)
        events.append(dict(event_id=eid,decision_time_pts=at,track_ids=[7],status=SUSPECTED,
            session_id='recording',camera_id='C',gate_id='G',video_id='fixture',
            source_ref=dict(collection='events',source_pointer='/'+eid),source_event=raw))
    if reverse:events.reverse()
    baseline=dict(segments=[source],policy=asdict(Policy()))
    history=dict(video_id='fixture',events=events,decisions=[],source_window=[0.,frames[-1]['pts']],
        policy=asdict(GroupPolicy(gap_seconds=.05,max_span_seconds=10.)))
    sc=scene();region=make_region(sc,'C',sc['approach_polygon'],reference_pts=0.,note='Synthetic test')
    return replay_scoped(baseline,history,[],runs,frames,sc,region,
        direction_engine=GateObservationDirection(frames,sc),observe_gate_crossings=True,
        confirm_outward_crossings=True)[0]


class DelayedLossOwnershipContracts(unittest.TestCase):
    def test_two_original_candidates_share_one_measured_loss_owner(self):
        r=run_shared_endpoint();states={e['event_id']:e for e in r['evidence']}
        self.assertEqual(r['counts']['confirmation_notifications'],1)
        self.assertEqual(states['old']['automatic_status'],SUSPECTED)
        self.assertEqual(states['new']['automatic_status'],CONFIRMED)
        self.assertEqual(states['new']['first_confirmation_pts'],1.6)

    def test_candidate_iteration_order_cannot_change_physical_owner(self):
        a,b=run_shared_endpoint(),run_shared_endpoint(reverse=True)
        for r in (a,b):
            self.assertEqual([e['event_id'] for e in r['evidence'] if e['automatic_status']==CONFIRMED],['new'])
            self.assertEqual(r['counts']['confirmation_notifications'],1)

    def test_raw_and_run_paths_share_one_positive_resolution(self):
        r=run_shared_endpoint(two=False)
        positives=[x for x in r['resolutions'] if x['kind']!='observation_handoff']
        self.assertEqual(len(positives),1)
        self.assertEqual(r['counts']['confirmation_notifications'],1)
        self.assertEqual(r['evidence'][0]['first_confirmation_pts'],1.6)

    def test_future_loss_wait_cannot_confirm_earlier_prefix(self):
        r=run_shared_endpoint(end=16)
        self.assertEqual(r['counts']['confirmation_notifications'],0)

    def test_later_turnback_does_not_reuse_old_inward_motion(self):
        r=run_shared_endpoint(turn_back=True)
        self.assertEqual(r['counts']['confirmation_notifications'],0)


if __name__=='__main__':unittest.main()
