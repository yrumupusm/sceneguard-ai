from copy import deepcopy
import unittest

from sceneguard.gate_activity_episodes import (
    ActivityPolicy, GateActivityEpisodes, SUSPECTED, CONFIRMED, RELEASED, activity_cards_at)

SCOPE = dict(session_id='recording', camera_id='camera', gate_id='door')


def event(eid, pts, **changes):
    return dict(dict(SCOPE, event_id=eid, decision_time_pts=pts, status=SUSPECTED,
                     track_ids=[], source_event={'unchanged': eid}), **changes)


def state(e, status=SUSPECTED, at=None, cid='old-card'):
    at = e['decision_time_pts'] if at is None else at
    return dict(event_id=e['event_id'], incident_id=cid, automatic_status=status,
        opened_pts=e['decision_time_pts'], last_state_change_pts=at,
        first_confirmation_pts=at if status==CONFIRMED else None,
        released_pts=at if status==RELEASED else None, observation_key='run-'+e['event_id'],
        binding={'source_observation_key': 'original'}, release_protected=False,
        human_verified=False, identity_verified=False)


def refs(index, pts):
    return [dict(frame_index=index, pts=pts, cache_index=0)]


def drive(life, end, actions=None, present=lambda at: True):
    actions = actions or {}
    for i in range(life._index+1, round(end*10)+1):
        at = round(i/10, 10)
        kwargs = deepcopy(actions.get(at, {}))
        life.step(i, at, portal_refs=refs(i, at) if present(at) else [], **kwargs)
    return life.export()


def opened(e, st=None):
    return dict(candidates=[e], evidence_updates=[st or state(e)])


class ActivityTests(unittest.TestCase):
    def new(self, **kw): return GateActivityEpisodes(SCOPE, **kw)

    def test_presence_without_suspicion_has_no_card(self):
        r=drive(self.new(), 12.)
        self.assertEqual(r['counts']['incident_cards'],0)
        self.assertEqual(r['notification_intents'],[])

    def test_continuous_presence_ignores_old_ten_second_limit(self):
        e1,e2=event('a',.2),event('b',15.)
        r=drive(self.new(),16.,{.2:opened(e1),15.:opened(e2)})
        self.assertEqual(len(r['cards']),1)
        self.assertEqual(r['cards'][0]['event_ids'],['a','b'])
        self.assertEqual(r['counts']['suspicion_notifications'],1)

    def test_alert_gap_longer_than_three_is_not_observation_gap(self):
        e1,e2=event('a',.2),event('b',7.)
        r=drive(self.new(),8.,{.2:opened(e1),7.:opened(e2)})
        self.assertEqual(len(r['cards']),1)

    def test_new_candidate_after_confirmation_does_not_notify(self):
        a,b=event('a',.2),event('b',14.)
        r=drive(self.new(),15.,{.2:opened(a),5.:dict(evidence_updates=[state(a,CONFIRMED,5.)]),14.:opened(b)})
        self.assertEqual([n['kind'] for n in r['notification_intents']],['suspicion','confirmation'])
        self.assertEqual(r['cards'][0]['automatic_status'],CONFIRMED)
        self.assertEqual(r['cards'][0]['unresolved_event_ids'],['b'])

    def test_no_backdated_confirmation(self):
        a=event('a',.2);life=self.new()
        r=drive(life,6.,{.2:opened(a),5.:dict(evidence_updates=[state(a,CONFIRMED,5.)])})
        self.assertEqual(activity_cards_at(r['timeline'],4.9)[0]['automatic_status'],SUSPECTED)
        self.assertEqual(activity_cards_at(r['timeline'],5.)[0]['automatic_status'],CONFIRMED)
        self.assertEqual(r['cards'][0]['first_confirmation_pts'],5.)

    def test_empty_portal_closes_suspicion_without_release(self):
        a=event('a',.2)
        r=drive(self.new(),6.,{.2:opened(a)},present=lambda at:at<=1.)
        c=r['cards'][0]
        self.assertEqual(c['observation_closed_pts'],4.)
        self.assertEqual(c['automatic_status'],SUSPECTED)
        self.assertEqual(r['counts']['released_cards'],0)
        self.assertEqual(r['active_cards'],[])

    def test_closed_confirmed_card_keeps_confirmation(self):
        a=event('a',.2)
        r=drive(self.new(),6.,{.2:opened(a),.8:dict(evidence_updates=[state(a,CONFIRMED,.8)])},present=lambda at:at<=1.)
        self.assertEqual(r['closed_cards'][0]['automatic_status'],CONFIRMED)
        self.assertEqual(r['closed_cards'][0]['first_confirmation_pts'],.8)

    def test_reentry_after_empty_grace_starts_new_card(self):
        a,b=event('a',.2),event('b',6.)
        r=drive(self.new(),7.,{.2:opened(a),6.:opened(b)},present=lambda at:at<=1. or at>=6.)
        self.assertEqual(len(r['cards']),2)
        self.assertEqual(r['counts']['suspicion_notifications'],2)
        self.assertNotEqual(r['cards'][0]['incident_id'],r['cards'][1]['incident_id'])

    def test_brief_missing_boxes_do_not_split(self):
        a,b=event('a',.2),event('b',3.9)
        r=drive(self.new(),5.,{.2:opened(a),3.9:opened(b)},present=lambda at:at<=1. or at>=3.9)
        self.assertEqual(len(r['cards']),1)

    def test_observation_returns_at_grace_boundary(self):
        a,b=event('a',.2),event('b',4.)
        r=drive(self.new(),5.,{.2:opened(a),4.:opened(b)},present=lambda at:at<=1. or at>=4.)
        self.assertEqual(len(r['cards']),1)

    def test_empty_at_boundary_closes_before_later_return(self):
        a,b=event('a',.2),event('b',4.1)
        r=drive(self.new(),5.,{.2:opened(a),4.1:opened(b)},present=lambda at:at<=1. or at>=4.1)
        self.assertEqual(len(r['cards']),2)

    def test_candidates_do_not_refresh_empty_clock(self):
        a,b,c=event('a',.2),event('b',2.),event('c',4.2)
        r=drive(self.new(),5.,{.2:opened(a),2.:opened(b),4.2:opened(c)},present=lambda at:at<=1.)
        self.assertEqual(r['cards'][0]['observation_closed_pts'],4.)
        self.assertEqual(r['cards'][0]['event_ids'],['a','b'])
        self.assertEqual(len(r['cards']),2)

    def test_candidate_without_any_presence_has_bounded_open_interval(self):
        a,b=event('a',.2),event('b',1.)
        r=drive(self.new(),4.,{.2:opened(a),1.:opened(b)},present=lambda at:False)
        self.assertEqual(r['cards'][0]['observation_closed_pts'],3.2)
        self.assertIsNone(r['cards'][0]['last_gate_observation_pts'])

    def test_video_end_not_artificial_empty_frame(self):
        a=event('a',.2)
        r=drive(self.new(),1.5,{.2:opened(a)},present=lambda at:at<=1.)
        self.assertEqual(r['cards'][0]['observation_status'],'open')
        self.assertIsNone(r['cards'][0]['observation_closed_pts'])

    def test_source_gap_interrupts_not_releases(self):
        a,b=event('a',.1),event('b',5.)
        life=self.new();drive(life,.2,{.1:opened(a)})
        life.step(3,5.,portal_refs=refs(3,5.),**opened(b))
        r=life.export()
        self.assertEqual(len(r['cards']),2)
        self.assertEqual(r['cards'][0]['observation_close_reason'],'source_gap_not_verified_empty')
        self.assertEqual(r['cards'][0]['automatic_status'],SUSPECTED)

    def test_single_release_closes_only_when_all_evidence_released(self):
        a,b=event('a',.1),event('b',.2)
        life=self.new()
        r=drive(life,1.,{.1:opened(a),.2:opened(b),.5:dict(evidence_updates=[state(a,RELEASED,.5)])})
        self.assertEqual(r['cards'][0]['automatic_status'],SUSPECTED)
        self.assertEqual(r['cards'][0]['unresolved_event_ids'],['b'])

    def test_all_released_archives_without_new_alert(self):
        a,b=event('a',.1),event('b',.2)
        r=drive(self.new(),1.,{.1:opened(a),.2:opened(b),.5:dict(evidence_updates=[state(a,RELEASED,.5),state(b,RELEASED,.5)])})
        self.assertEqual(r['cards'][0]['automatic_status'],RELEASED)
        self.assertEqual(r['cards'][0]['observation_close_reason'],'all_linked_suspicions_released')
        self.assertEqual(len(r['notification_intents']),1)

    def test_confirmed_and_released_evidence_keeps_card_confirmed(self):
        a,b=event('a',.1),event('b',.2)
        r=drive(self.new(),1.,{.1:opened(a),.2:opened(b),.5:dict(evidence_updates=[state(a,CONFIRMED,.5),state(b,RELEASED,.5)])})
        self.assertEqual(r['cards'][0]['automatic_status'],CONFIRMED)
        self.assertEqual(r['cards'][0]['released_event_ids'],['b'])

    def test_late_confirmation_updates_closed_card_does_not_reopen(self):
        a=event('a',.2)
        r=drive(self.new(),6.,{.2:opened(a),5.:dict(evidence_updates=[state(a,CONFIRMED,5.)])},present=lambda at:at<=1.)
        self.assertEqual(r['cards'][0]['observation_closed_pts'],4.)
        self.assertEqual(r['cards'][0]['automatic_status'],CONFIRMED)
        self.assertEqual(r['active_cards'],[])

    def test_same_frame_initial_confirmation_has_one_stronger_notice(self):
        a=event('a',.1)
        r=drive(self.new(),.2,{.1:opened(a,state(a,CONFIRMED,.1))})
        self.assertEqual([n['kind'] for n in r['notification_intents']],['confirmation'])

    def test_multiple_same_time_candidates_one_card_one_notice(self):
        a,b=event('a',.1),event('b',.1)
        r=drive(self.new(),.2,{.1:dict(candidates=[b,a],evidence_updates=[state(b),state(a)])})
        self.assertEqual(len(r['cards']),1)
        self.assertEqual(len(r['notification_intents']),1)

    def test_duplicate_frame_is_idempotent(self):
        a=event('a',0.);life=self.new();args=dict(portal_refs=refs(0,0.),**opened(a))
        life.step(0,0.,**args);before=life.export()
        self.assertEqual(life.step(0,0.,**args),[])
        self.assertEqual(life.export(),before)

    def test_conflicting_duplicate_frame_rejected(self):
        life=self.new();life.step(0,0.)
        with self.assertRaises(ValueError):life.step(0,0.,portal_refs=refs(0,0.))

    def test_skipped_frame_rejected(self):
        life=self.new();life.step(0,0.)
        with self.assertRaises(ValueError):life.step(2,.2)

    def test_stale_last_box_reference_cannot_refresh_clock(self):
        life=self.new();life.step(0,0.)
        with self.assertRaises(ValueError):life.step(1,.1,portal_refs=refs(0,0.))

    def test_future_evidence_rejected_atomically(self):
        a=event('a',.1);life=self.new();life.step(0,0.);before=life.export()
        with self.assertRaises(ValueError):life.step(1,.1,**opened(a,state(a,CONFIRMED,2.)))
        self.assertEqual(life.export(),before)

    def test_final_state_cannot_initialize_past_candidate(self):
        a=event('a',.1);life=self.new();life.step(0,0.)
        s=state(a);s['observation_history']=[dict(pts=5.)]
        with self.assertRaises(ValueError):life.step(1,.1,**opened(a,s))

    def test_confirmation_cannot_be_downgraded(self):
        a=event('a',0.);life=self.new();life.step(0,0.,**opened(a,state(a,CONFIRMED,0.)))
        with self.assertRaises(ValueError):life.step(1,.1,evidence_updates=[state(a,RELEASED,.1)])

    def test_scope_isolated(self):
        a=event('a',0.,camera_id='another-camera')
        with self.assertRaises(ValueError):self.new().step(0,0.,**opened(a))

    def test_raw_events_and_input_snapshots_unchanged(self):
        a=event('a',.1);s=state(a);saved=deepcopy((a,s))
        r=drive(self.new(),.2,{.1:opened(a,s)})
        self.assertEqual((a,s),saved)
        self.assertEqual(r['events'],[a])

    def test_replay_has_stable_notification_keys(self):
        a=event('a',.1);actions={.1:opened(a),.2:dict(evidence_updates=[state(a,CONFIRMED,.2)])}
        a1,a2=drive(self.new(),.3,actions),drive(self.new(),.3,actions)
        self.assertEqual(a1['notification_intents'],a2['notification_intents'])
        self.assertEqual(len({n['notification_key'] for n in a1['notification_intents']}),2)

    def test_seek_after_close_and_rewind_does_not_mutate(self):
        a=event('a',.1);r=drive(self.new(),5.,{.1:opened(a)},present=lambda at:at<=1.)
        self.assertEqual(activity_cards_at(r['timeline'],4.,include_closed=False),[])
        past=activity_cards_at(r['timeline'],1.)
        self.assertEqual(past[0]['observation_status'],'open')
        past[0]['event_ids'].clear()
        self.assertEqual(activity_cards_at(r['timeline'],1.)[0]['event_ids'],['a'])

    def test_bad_policy_rejected(self):
        for p in (ActivityPolicy(0.,.12),ActivityPolicy(3.,4.),ActivityPolicy(float('nan'),.12)):
            with self.subTest(p=p),self.assertRaises(ValueError):self.new(policy=p)

    def test_changes_after_release_start_new_suspicion(self):
        a,b=event('a',.1),event('b',.4)
        r=drive(self.new(),.5,{.1:opened(a),.2:dict(evidence_updates=[state(a,RELEASED,.2)]),.4:opened(b)})
        self.assertEqual(len(r['cards']),2)
        self.assertEqual(r['counts']['suspicion_notifications'],2)

    def test_confirmation_does_not_confirm_unrelated_evidence(self):
        a,b=event('a',.1),event('b',.2)
        r=drive(self.new(),.4,{.1:opened(a),.2:opened(b),.3:dict(evidence_updates=[state(b,CONFIRMED,.3,cid='source-b')])})
        by_id={e['event_id']:e for e in r['evidence']}
        self.assertEqual(by_id['a']['automatic_status'],SUSPECTED)
        self.assertEqual(by_id['b']['automatic_status'],CONFIRMED)
        self.assertEqual(len(r['notification_intents']),2)


if __name__=='__main__':unittest.main()
