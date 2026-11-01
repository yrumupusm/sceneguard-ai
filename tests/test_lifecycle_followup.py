"""Synthetic coordinates, actual repository direction math and grouping.

The rectangular test portal is injected; actual local scene/portal/CLI contracts
and CCTV interpretation still require the local full-repository execution.
"""
import copy
import unittest
from types import SimpleNamespace

from sceneguard.directional_loss import SavedGateDirection
from sceneguard.incident_lifecycle import IncidentLifecycle, SUSPECTED, CONFIRMED, RELEASED, lifecycle_cards_at
from sceneguard.lifecycle_followup import ObservationHistory, assess_loss, followup_run
from sceneguard.exp0047_application import replay, locate_time

SCENE=dict(source_size=[100,100],line=[[.5,.1],[.5,.9]],zones=dict(
    outside=[[0,0],[.5,0],[.5,1],[0,1]],inside=[[.5,0],[1,0],[1,1],[.5,1]]))


class TestPortal:
    def locate(self,bbox):
        x,y=(bbox[0]+bbox[2])/2,(bbox[1]+bbox[3])/2
        return {'inside_birth_site':.35 <= x <= .65 and .2 <= y <= .8}


def fixture(velocity=-8., last_visible=10, total=22, split=None, raw_change=False):
    frames=[];runs={}
    for i in range(total):
        t=round(i/10,1); x=50+velocity*min(t,last_visible/10)
        b=[(x-6)/100,.35,(x+6)/100,.65]
        observed=i<=last_visible
        box=dict(cache_index=0,bbox=b,score=.9,observed=True,
                 track_ids=[17 if raw_change and i>=5 else 7])
        path=dict(window_id='w1',seed_pts=0.,seed_cache_index=0,point_ids=[0,1,2,3],
            points_original_pixels=[[x-2,45.],[x+2,45.],[x-2,55.],[x+2,55.]])
        frames.append(dict(frame_index=i,pts=t,actual_boxes=[box] if observed else [],
            point_paths=[path] if observed else [],camera_step_pixels=[0.,0.]))
        if observed:
            rid='r1' if split is None or i<split else 'r2'
            runs.setdefault(rid,[]).append(dict(frame_index=i,pts=t,cache_index=0,bbox=b))
    refs=copy.deepcopy(runs['r1'][:3])
    event=dict(event_id='portal-1',session_id='S',camera_id='C',gate_id='G',video_id='test',
        decision_time_pts=.2,status=SUSPECTED,track_ids=[],
        source_ref={'collection':'inside_birth_events'},
        source_event=dict(run_id='r1',observation_refs=refs,birth_pts=0.))
    history=dict(video_id='test',events=[],decisions=[],policy=dict(gap_seconds=3.,max_span_seconds=10.),
                 source_window=[0.,frames[-1]['pts']],available_after_pts=frames[-1]['pts'])
    baseline={'segments':[]}
    return baseline,history,[event],runs,frames


def run_fixture(**options):
    baseline,history,events,runs,frames=fixture(**options)
    return replay(baseline,history,events,runs,frames,SCENE,{},
        direction_engine=SavedGateDirection(frames,SCENE),portal_gate=TestPortal())


class FollowupTests(unittest.TestCase):
    def test_observed_outward_motion_then_loss_releases(self):
        r=run_fixture(velocity=-8.)
        self.assertEqual(r['cards'][0]['automatic_status'],RELEASED)
        self.assertEqual(r['counts']['confirmation_notifications'],0)
        self.assertEqual(r['resolutions'][0]['decision_time_pts'],2.)

    def test_inward_motion_then_loss_confirms(self):
        r=run_fixture(velocity=8.)
        self.assertEqual(r['cards'][0]['automatic_status'],CONFIRMED)
        self.assertEqual([n['kind'] for n in r['notification_intents']],['suspicion','confirmation'])

    def test_stationary_does_not_release_or_confirm(self):
        r=run_fixture(velocity=0.)
        self.assertEqual(r['cards'][0]['automatic_status'],SUSPECTED)
        self.assertEqual(r['resolutions'],[])

    def test_end_of_video_is_not_loss(self):
        r=run_fixture(total=15)
        self.assertEqual(r['cards'][0]['automatic_status'],SUSPECTED)

    def test_raw_id_change_does_not_end_observation(self):
        r=run_fixture(raw_change=True,total=15)
        self.assertEqual(r['resolutions'],[])
        self.assertEqual(r['counts']['suspicion_notifications'],1)

    def test_same_points_handoff_survives_geometry_run_split(self):
        r=run_fixture(split=6)
        self.assertEqual(r['followup_counts']['observation_handoffs'],1)
        self.assertEqual(r['evidence'][0]['observation_key'],'r2')
        self.assertEqual(r['cards'][0]['automatic_status'],RELEASED)
        self.assertEqual(r['resolutions'][-1]['last_observed_pts'],1.)

    def test_no_future_state_in_rewind(self):
        r=run_fixture()
        self.assertEqual(lifecycle_cards_at(r['timeline'],1.9)[0]['automatic_status'],SUSPECTED)
        self.assertEqual(lifecycle_cards_at(r['timeline'],2.)[0]['automatic_status'],RELEASED)

    def test_pending_observation_can_outlast_grouping_maximum(self):
        r=run_fixture(velocity=-.6,last_visible=120,total=132)
        # Small movement fails the frozen direction threshold, but grouping closure
        # cannot erase pending evidence or create an automatic timeout release.
        self.assertEqual(r['cards'][0]['automatic_status'],SUSPECTED)
        self.assertEqual(len(r['cards']),1)

    def test_missing_direction_is_explicit_in_audit(self):
        r=run_fixture(velocity=0.)
        self.assertTrue(any(a['reason']=='no_recent_target_direction' for a in r['followup_audit']))

    def test_preserved_confirmation_never_cleared(self):
        b,h,events,runs,frames=fixture()
        original=copy.deepcopy(events[0]);original['event_id']='original'
        h['events']=[original]
        h['decisions']=[dict(event_id='original',automatic_confirmation=True,decision_time_pts=.2)]
        r=replay(b,h,events,runs,frames,SCENE,{},direction_engine=SavedGateDirection(frames,SCENE),portal_gate=TestPortal())
        self.assertEqual(r['cards'][0]['automatic_status'],CONFIRMED)
        self.assertEqual(r['counts']['confirmation_notifications'],1)
        self.assertEqual(r['preserved_confirmation_source_pts'],{'original':.2})

    def test_unbound_legacy_evidence_stays_pending(self):
        b,h,events,runs,frames=fixture()
        raw=copy.deepcopy(events[0]);raw.update(event_id='unbound',source_ref={'collection':'existing_alerts'},source_event={})
        h['events']=[raw]
        r=replay(b,h,events,runs,frames,SCENE,{},direction_engine=SavedGateDirection(frames,SCENE),portal_gate=TestPortal())
        self.assertEqual(r['unbound_candidates'],1)
        self.assertEqual(r['cards'][0]['automatic_status'],SUSPECTED)
        self.assertEqual(r['cards'][0]['released_event_ids'],['portal-1'])

    def test_source_gap_cannot_clear(self):
        b,h,e,runs,frames=fixture()
        for i in range(11,len(frames)):frames[i]['pts']+=3
        r=replay(b,h,e,runs,frames,SCENE,{},direction_engine=SavedGateDirection(frames,SCENE),portal_gate=TestPortal())
        self.assertEqual(r['cards'][0]['automatic_status'],SUSPECTED)
        self.assertEqual(r['followup_counts']['source_gap_not_person_loss'],1)

    def test_actual_box_binding_must_match(self):
        _,_,_,runs,frames=fixture();runs['r1'][0]['bbox']=[0,0,.2,.2]
        with self.assertRaises(ValueError):ObservationHistory(runs,frames)

    def test_predicted_box_cannot_be_an_actual_run(self):
        _,_,_,runs,frames=fixture();frames[0]['actual_boxes'][0]['observed']=False
        with self.assertRaises(ValueError):ObservationHistory(runs,frames)

    def test_frames_cannot_be_skipped(self):
        _,_,_,runs,frames=fixture();o=ObservationHistory(runs,frames)
        with self.assertRaises(ValueError):o.advance(frames[1])

    def test_point_window_end_is_not_person_loss(self):
        b,h,e,runs,frames=fixture(total=15)
        for f in frames[6:]:f['point_paths']=[]
        r=replay(b,h,e,runs,frames,SCENE,{},direction_engine=SavedGateDirection(frames,SCENE),portal_gate=TestPortal())
        self.assertEqual(r['cards'][0]['automatic_status'],SUSPECTED)
        self.assertEqual(r['resolutions'],[])

    def test_unknown_emission_time_rejected(self):
        with self.assertRaises(ValueError):locate_time([0.,.1],.5)

    def test_alias_binding_uses_only_observed_successor(self):
        b,h,e,runs,frames=fixture(split=6);o=ObservationHistory(runs,frames)
        for frame in frames[:7]:o.advance(frame)
        o.link('r1','r2')
        event=copy.deepcopy(e[0]);event['decision_time_pts']=.6
        self.assertEqual(o.bind(event,{})['observation_key'],'r2')
        self.assertEqual(o.motion_rows('r2')[0]['frame_index'],0)
        self.assertEqual(runs['r2'][0]['frame_index'],6)

    def test_successor_must_be_actually_observed_now(self):
        _,_,_,runs,frames=fixture(split=6);o=ObservationHistory(runs,frames)
        for frame in frames[:6]:o.advance(frame)
        with self.assertRaises(ValueError):o.link('r1','r2')

    def test_mutating_export_does_not_change_input(self):
        b,h,e,runs,frames=fixture();before=copy.deepcopy((b,h,e,runs,frames))
        replay(b,h,e,runs,frames,SCENE,{},direction_engine=SavedGateDirection(frames,SCENE),portal_gate=TestPortal())
        self.assertEqual((b,h,e,runs,frames),before)

if __name__=='__main__':unittest.main()
