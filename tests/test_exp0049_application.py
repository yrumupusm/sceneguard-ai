from copy import deepcopy
import unittest

from sceneguard.exp0049_application import activity_references, frozen_schedule, replay_activity, source_state
from sceneguard.gate_activity_episodes import SUSPECTED, CONFIRMED, RELEASED, activity_cards_at

SCOPE=dict(session_id='session',camera_id='camera',gate_id='gate')


class RectanglePortalFixture:
    """Only a geometry fixture. Actual runner imports the existing PortalGate."""
    def locate(self,b):
        x,y=(b[0]+b[2])/2,(b[1]+b[3])/2
        area=max(0,min(.6,b[2])-max(.4,b[0]))*max(0,min(.7,b[3])-max(.3,b[1]))
        fraction=area/((b[2]-b[0])*(b[3]-b[1]))
        return {'inside_birth_site':(.4<=x<=.6 and .3<=y<=.7) or fraction>=.5}


def frames(end=16.,present=lambda at:True):
    output=[]
    for i in range(round(end*10)+1):
        at=round(i/10,10)
        boxes=[dict(cache_index=0,bbox=[.44,.4,.52,.6],score=.8,observed=True,track_ids=[i])] if present(at) else []
        output.append(dict(frame_index=i,pts=at,actual_boxes=boxes,native_pts=i,time_base='1/10'))
    return output


def make_prior():
    events=[dict(SCOPE,event_id='a',decision_time_pts=.2,status=SUSPECTED,track_ids=[1],source_event={'keep':'a'}),
            dict(SCOPE,event_id='b',decision_time_pts=14.,status=SUSPECTED,track_ids=[2],source_event={'keep':'b'})]
    def s(e,cid):
        return dict(event_id=e['event_id'],incident_id=cid,automatic_status=SUSPECTED,
            opened_pts=e['decision_time_pts'],last_state_change_pts=e['decision_time_pts'],
            first_confirmation_pts=None,released_pts=None,observation_key='original',binding={},
            release_protected=False,human_verified=False,identity_verified=False)
    initial=s(events[0],'source-one');confirmed=deepcopy(initial)
    confirmed.update(automatic_status=CONFIRMED,last_state_change_pts=5.,first_confirmation_pts=5.,resolution_id='confirmation-a')
    second=s(events[1],'source-two')
    return dict(experiment='EXP-0048',video_id='synthetic-recording',source_window=[0.,16.1],
        events=events,evidence=[confirmed,second],
        timeline=[dict(incident_id='source-one',decision_time_pts=.2,evidence=[initial]),
                  dict(incident_id='source-one',decision_time_pts=5.,evidence=[confirmed]),
                  dict(incident_id='source-two',decision_time_pts=14.,evidence=[second])],
        resolutions=[dict(resolution_id='confirmation-a',owner_incident_id='source-one')],
        outcome_routing=[dict(source='preserved')],preserved_confirmation_source_pts={'a':5.})


class ReplayTests(unittest.TestCase):
    def test_actual_boxes_only_and_no_score_lowering(self):
        f=frames(0.)[0]
        f['actual_boxes'] += [dict(cache_index=1,bbox=[.44,.4,.52,.6],score=.2),
            dict(cache_index=2,bbox=[.44,.4,.52,.6],score=.8,observed=False),
            dict(cache_index=3,bbox=[.44,.4,.52,.6],score=.8,predicted=True)]
        self.assertEqual([r['cache_index'] for r in activity_references(f,RectanglePortalFixture())],[0])

    def test_far_pedestrian_not_gate_presence(self):
        f=frames(0.)[0];f['actual_boxes'][0]['bbox']=[.01,.4,.15,.8]
        self.assertEqual(activity_references(f,RectanglePortalFixture()),[])

    def test_changed_id_does_not_break_activity(self):
        r=replay_activity(make_prior(),frames(),RectanglePortalFixture())
        self.assertEqual(len(r['cards']),1)
        self.assertEqual(r['counts']['confirmation_notifications'],1)

    def test_one_confirmed_episode_absorbs_later_pending_card_without_promoting_it(self):
        prior=make_prior();r=replay_activity(prior,frames(),RectanglePortalFixture())
        self.assertEqual(r['cards'][0]['automatic_status'],CONFIRMED)
        self.assertEqual(r['cards'][0]['unresolved_event_ids'],['b'])
        self.assertEqual(r['source_to_activity_cards']['source-one'],r['source_to_activity_cards']['source-two'])
        self.assertEqual([n['decision_time_pts'] for n in r['notification_intents']],[.2,5.])

    def test_every_evidence_field_and_original_times_are_preserved(self):
        prior=make_prior();copy=deepcopy(prior);data=frames();data_copy=deepcopy(data)
        r=replay_activity(prior,data,RectanglePortalFixture())
        self.assertEqual([source_state(e) for e in r['evidence']],prior['evidence'])
        self.assertEqual(r['events'],prior['events'])
        self.assertEqual(r['source_resolution_log'],prior['resolutions'])
        self.assertEqual(r['preserved_confirmation_source_pts'],{'a':5.})
        self.assertEqual(r['evidence_prefix_checks'],len(data))
        self.assertEqual(prior,copy);self.assertEqual(data,data_copy)

    def test_no_final_evidence_leakage_on_seek(self):
        r=replay_activity(make_prior(),frames(),RectanglePortalFixture())
        self.assertEqual(activity_cards_at(r['timeline'],4.9)[0]['automatic_status'],SUSPECTED)
        self.assertEqual(activity_cards_at(r['timeline'],5.)[0]['automatic_status'],CONFIRMED)
        self.assertEqual(activity_cards_at(r['timeline'],13.9)[0]['event_ids'],['a'])

    def test_real_empty_interval_yields_two_episodes(self):
        r=replay_activity(make_prior(),frames(present=lambda at:at<=6. or at>=14.),RectanglePortalFixture())
        self.assertEqual(len(r['cards']),2)
        self.assertEqual(r['cards'][0]['observation_closed_pts'],9.)
        self.assertEqual(r['cards'][1]['automatic_status'],SUSPECTED)

    def test_many_fresh_ordinary_pedestrian_boxes_do_not_keep_gate_open(self):
        data=frames(present=lambda at:at<=6. or at>=14.)
        for f in data:
            if 6.<f['pts']<14.:
                f['actual_boxes']=[dict(cache_index=0,score=.9,bbox=[.02,.3,.2,.8],observed=True)]
        r=replay_activity(make_prior(),data,RectanglePortalFixture())
        self.assertEqual(r['cards'][0]['observation_closed_pts'],9.)
        self.assertEqual(len(r['cards']),2)

    def test_bad_score_rejected(self):
        f=frames(0.)[0];f['actual_boxes'][0]['score']=float('nan')
        with self.assertRaises(ValueError):activity_references(f,RectanglePortalFixture())

    def test_incomplete_source_timeline_rejected(self):
        p=make_prior();p['timeline'].pop(0)
        with self.assertRaises(ValueError):frozen_schedule(p,frames())

    def test_final_evidence_mismatch_rejected(self):
        p=make_prior();p['evidence']=deepcopy(p['evidence']);p['evidence'][1]['observation_key']='unrecorded'
        with self.assertRaises(ValueError):frozen_schedule(p,frames())

    def test_conflicting_same_time_evidence_rejected(self):
        p=make_prior();bad=deepcopy(p['timeline'][1]);bad['evidence'][0]['observation_key']='other'
        p['timeline'].insert(2,bad)
        with self.assertRaises(ValueError):frozen_schedule(p,frames())

    def test_unordered_snapshot_rejected(self):
        p=make_prior();p['timeline']=p['timeline'][::-1]
        with self.assertRaises(ValueError):frozen_schedule(p,frames())

    def test_future_or_unknown_event_in_snapshot_rejected(self):
        p=make_prior();p['timeline'][0]['evidence'].append(deepcopy(p['evidence'][1]))
        with self.assertRaises(ValueError):frozen_schedule(p,frames())

    def test_different_recording_stream_rejected(self):
        p=make_prior();p['events'][1]['session_id']='another'
        with self.assertRaises(ValueError):frozen_schedule(p,frames())

    def test_duplicate_candidate_payload_rejected(self):
        p=make_prior();p['events'].append(deepcopy(p['events'][0]))
        with self.assertRaises(ValueError):frozen_schedule(p,frames())

    def test_source_snapshot_at_missing_frame_rejected(self):
        p=make_prior();p['timeline'][1]['decision_time_pts']=5.03
        with self.assertRaises(ValueError):frozen_schedule(p,frames())

    def test_presence_statistics_are_frames_not_people(self):
        r=replay_activity(make_prior(),frames(),RectanglePortalFixture())
        self.assertEqual(r['source_frames_with_portal_presence'],161)
        self.assertIsNone(r['cards'][0]['person_count'])
        self.assertIsNone(r['accuracy'])

    def test_no_extra_synthetic_frame_at_eof(self):
        r=replay_activity(make_prior(),frames(),RectanglePortalFixture())
        self.assertEqual(len(r['activity_audit']),161)
        self.assertEqual(r['source_end_pts'],16.)
        self.assertEqual(r['cards'][0]['observation_status'],'open')
        self.assertFalse(r['source_end_forced_release'])


if __name__=='__main__':unittest.main()
