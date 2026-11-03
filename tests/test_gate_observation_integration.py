"""Causal observation snapshots survive handoffs; this is not video accuracy."""
from copy import deepcopy
from dataclasses import asdict
import unittest

from sceneguard.approach_disappearance import Policy
from sceneguard.exp0048_application import replay_scoped
from sceneguard.gate_observation import GateObservationDirection
from sceneguard.incident_cards import GroupPolicy
from sceneguard.incident_lifecycle import CONFIRMED,SUSPECTED
from sceneguard.portal_births import make_region
from test_gate_observation import fixture,scene


def run_case(end=13,split=True,short_origin=False):
    frames,segment,_=fixture();frames=frames[:end];sc=scene()
    runs={}
    for f in frames:
        key='a' if f['frame_index']<=(1 if short_origin else 2) else 'b' if split and f['frame_index']<=4 else 'c'
        runs.setdefault(key,[]).append(dict(pts=f['pts'],frame_index=f['frame_index'],
            cache_index=0,bbox=deepcopy(f['actual_boxes'][0]['bbox'])))
    baseline=dict(segments=[dict(segment,id='a')],policy=asdict(Policy()))
    events=[dict(event_id=eid,decision_time_pts=at,track_ids=[7],status=SUSPECTED,
        session_id='recording',camera_id='C',gate_id='G',video_id='fixture',
        source_ref=dict(collection='events',source_pointer='/'+eid),
        source_event=dict(segment='a',raw_id=7,reason='synthetic_approach_candidate'))
        for eid,at in [('old',0.),('new',.1)]]
    history=dict(video_id='fixture',events=events,decisions=[],source_window=[0.,frames[-1]['pts']],
        policy=asdict(GroupPolicy(gap_seconds=.05,max_span_seconds=10.)))
    region=make_region(sc,'C',sc['approach_polygon'],reference_pts=0.,note='Synthetic fixture')
    snapshot=deepcopy((baseline,history,runs,frames,sc,region))
    result,_=replay_scoped(baseline,history,[],runs,frames,sc,region,
        direction_engine=GateObservationDirection(frames,sc),observe_gate_crossings=True)
    assert (baseline,history,runs,frames,sc,region)==snapshot
    return result


def run_recent_case(turn_back=False,still_visible=False):
    positions=[440,450,460]+([500,480,460,440] if turn_back else [500]*4)+[500]*14
    frames,source,_=fixture(positions);sc=scene();runs={'a':deepcopy(source['rows']),'b':[],'c':[]}
    for i,f in enumerate(frames):
        if i<=2:continue
        if i>6 and not still_visible:
            f['actual_boxes']=[];f['point_paths']=[];continue
        duplicate=deepcopy(f['actual_boxes'][0]);duplicate['cache_index']=1
        f['actual_boxes'].append(duplicate)
        for key,ci in [('b',0),('c',1)]:
            runs[key].append(dict(pts=f['pts'],frame_index=i,cache_index=ci,bbox=deepcopy(duplicate['bbox'])))
    event=dict(event_id='e',decision_time_pts=.1,track_ids=[7],status=SUSPECTED,
        session_id='recording',camera_id='C',gate_id='G',video_id='fixture',
        source_ref=dict(collection='events',source_pointer='/e'),source_event=dict(segment='a',raw_id=7))
    baseline=dict(segments=[dict(source,id='a')],policy=asdict(Policy()))
    history=dict(video_id='fixture',events=[event],decisions=[],source_window=[0.,frames[-1]['pts']],
        policy=asdict(GroupPolicy()))
    region=make_region(sc,'C',sc['approach_polygon'],reference_pts=0.,note='Synthetic fixture')
    return replay_scoped(baseline,history,[],runs,frames,sc,region,
        direction_engine=GateObservationDirection(frames,sc),observe_gate_crossings=True,
        confirm_outward_crossings=True)[0]


class ObservationIntegrationTests(unittest.TestCase):
    def test_recent_visibility_is_retried_after_actual_absence(self):
        r=run_recent_case()
        self.assertEqual(r['evidence'][0]['first_confirmation_pts'],1.6)
        positive=[x for x in r['resolutions'] if x['kind']=='inward_loss']
        self.assertEqual(positive[0]['last_observed_pts'],.6)
        self.assertTrue(any(a['reason']=='waiting_since_last_bound_observation' for a in r['followup_audit']))

    def test_later_turn_back_overrides_earlier_inward_approach(self):
        r=run_recent_case(turn_back=True)
        self.assertEqual(r['counts']['confirmation_notifications'],0)
        self.assertEqual(r['evidence'][0]['automatic_status'],SUSPECTED)

    def test_still_visible_on_boundary_is_not_loss_after_id_end(self):
        r=run_recent_case(still_visible=True)
        self.assertEqual(r['counts']['confirmation_notifications'],0)

    def test_two_handoffs_preserve_source_until_destination_stabilizes(self):
        r=run_case();states={e['event_id']:e for e in r['evidence']}
        self.assertEqual(states['new']['automatic_status'],CONFIRMED)
        self.assertEqual(states['new']['first_confirmation_pts'],.7)
        self.assertEqual(states['old']['automatic_status'],SUSPECTED)
        self.assertEqual(r['counts']['confirmation_notifications'],1)
        self.assertEqual(r['followup_counts']['observation_handoffs'],2)
        proofs=[x for x in r['resolutions'] if x['kind']=='observed_gate_crossing']
        self.assertEqual(len(proofs),1)
        self.assertEqual(proofs[0]['source_decision']['source_observation_key'],'a')
        self.assertEqual(proofs[0]['observation_key'],'c')
        self.assertEqual(proofs[0]['last_observed_pts'],.2)

    def test_future_destination_cannot_confirm_earlier_prefix(self):
        r=run_case(end=7)
        self.assertEqual(r['counts']['confirmation_notifications'],0)
        self.assertTrue(all(e['automatic_status']==SUSPECTED for e in r['evidence']))

    def test_short_initial_fragment_can_gain_measured_origin_before_crossing(self):
        r=run_case(short_origin=True);states={e['event_id']:e for e in r['evidence']}
        self.assertEqual(states['new']['first_confirmation_pts'],.7)
        self.assertEqual(states['old']['automatic_status'],SUSPECTED)
        self.assertEqual(r['counts']['confirmation_notifications'],1)
        self.assertEqual(r['followup_counts']['observation_handoffs'],2)
        short=[x for x in r['resolutions'] if x['kind']=='observed_gate_crossing'][0]
        normal=[x for x in run_case()['resolutions'] if x['kind']=='observed_gate_crossing'][0]
        self.assertEqual(short['physical_crossing_ref'],normal['physical_crossing_ref'])

    def test_one_or_two_run_handoffs_keep_same_physical_crossing_owner(self):
        a,b=run_case(split=False),run_case(split=True)
        self.assertEqual(a['counts']['confirmation_notifications'],b['counts']['confirmation_notifications'])
        for r in (a,b):
            self.assertEqual([e['event_id'] for e in r['evidence'] if e['automatic_status']==CONFIRMED],['new'])
        ar=[r for r in a['resolutions'] if r['kind']=='observed_gate_crossing'][0]
        br=[r for r in b['resolutions'] if r['kind']=='observed_gate_crossing'][0]
        self.assertEqual(ar['physical_crossing_ref'],br['physical_crossing_ref'])


if __name__=='__main__':unittest.main()
