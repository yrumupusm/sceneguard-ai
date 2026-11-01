from copy import deepcopy
import unittest
from sceneguard.incident_lifecycle import digest, SUSPECTED, CONFIRMED, RELEASED, lifecycle_cards_at
from sceneguard.incident_outcome_scope import ScopedIncidentLifecycle


def candidate(eid, at, key='a', source=None, camera='C3'):
    e=dict(event_id=eid,decision_time_pts=at,status=SUSPECTED,
           session_id='session',camera_id=camera,gate_id='gate',track_ids=[],source_ref={})
    return dict(event=e,observation_key=key,
                binding=dict(source_observation_key=source or key),release_protected=False)


def resolution(ids, at, key='a', kind='inward_loss', last=None, **extra):
    r=dict(event_ids=ids,decision_time_pts=at,evidence_until_pts=at,
           kind=kind,observation_key=key)
    if kind in ('inward_loss','outward_loss'):
        last = at-1 if last is None else last
        r.update(last_observed_pts=last,loss_wait=1.,recording_continuous=True,
            observation_continues=False,direction='inward' if kind=='inward_loss' else 'outward',
            direction_end_pts=last,direction_history_seconds=1.,recent_gate_contact=True)
    elif kind=='observation_handoff':
        r.update(actual_correspondence=True)
    else:r.update(confirmation_source='EXP-0045')
    r.update(extra);r['resolution_id']=digest(r);return r


class ScopeTests(unittest.TestCase):
    def setUp(self): self.s=ScopedIncidentLifecycle(namespace='test48')
    def add(self,eid,t,key='a',**kw):self.s.process(t,[candidate(eid,t,key,**kw)])
    def apply(self,ids,t,**kw):
        r=resolution(ids,t,**kw);self.s.process(t,resolutions=[r]);return r
    def state(self,eid):return self.s.evidence[eid]['automatic_status']
    def test_latest_card_only(self):
        self.add('old',1);self.add('new',12)
        self.apply(['old','new'],14)
        self.assertEqual((self.state('old'),self.state('new')),(SUSPECTED,CONFIRMED))
        self.assertEqual(self.s.export()['counts']['confirmation_notifications'],1)
    def test_retry_pending_old_cannot_confirm_old_card(self):
        self.add('old',1);self.add('new',12);self.apply(['old','new'],14,last=13)
        self.apply(['old'],14.1,last=13)
        self.assertEqual(self.state('old'),SUSPECTED)
        self.assertEqual(self.s.outcome_routing[-1]['reason'],'outcome_owned_by_other_incident')
    def test_one_anchor_not_all_approach_evidence(self):
        self.add('a1',1);self.add('a2',2)
        self.apply(['a1','a2'],4)
        self.assertEqual((self.state('a1'),self.state('a2')),(SUSPECTED,CONFIRMED))
    def test_outward_clears_single_origin(self):
        self.add('a1',1);self.add('a2',2)
        self.apply(['a1','a2'],4,kind='outward_loss')
        self.assertEqual((self.state('a1'),self.state('a2')),(RELEASED,RELEASED))
    def test_other_person_stays_pending(self):
        self.add('a1',1);self.add('b1',2,'b')
        self.apply(['a1'],4,kind='outward_loss')
        card=next(iter(self.s.cards.values()))
        self.assertEqual(card['automatic_status'],SUSPECTED)
        self.assertEqual(self.state('b1'),SUSPECTED)
    def test_one_to_one_handoff_keeps_release_available(self):
        self.add('a1',1)
        self.apply(['a1'],2,kind='observation_handoff',next_observation_key='b')
        self.apply(['a1'],4,key='b',kind='outward_loss')
        self.assertEqual(self.state('a1'),RELEASED)
    def test_sequential_fanin_cannot_blanket_release(self):
        self.add('a1',1);self.add('b1',1.2,'b')
        self.apply(['a1'],2,kind='observation_handoff',next_observation_key='b')
        self.apply(['a1','b1'],4,key='b',kind='outward_loss')
        self.assertTrue(all(self.state(e)==SUSPECTED for e in ('a1','b1')))
    def test_fanin_still_allows_incident_confirmation(self):
        self.add('a1',1);self.add('b1',1.2,'b')
        self.apply(['a1'],2,kind='observation_handoff',next_observation_key='b')
        self.apply(['a1','b1'],4,key='b')
        self.assertEqual(self.s.export()['counts']['confirmed_cards'],1)
    def test_new_candidate_on_handoff_destination_not_new_origin(self):
        self.add('a1',1);self.apply(['a1'],2,kind='observation_handoff',next_observation_key='b')
        self.add('a2',2.1,'b')
        self.apply(['a1','a2'],4,key='b',kind='outward_loss')
        self.assertEqual(self.state('a2'),RELEASED)
    def test_owner_propagates_even_when_latest_anchor_no_longer_pending(self):
        self.add('old',1);self.add('new',12);self.apply(['old','new'],14)
        self.apply(['old'],15,kind='observation_handoff',next_observation_key='b')
        self.apply(['old'],17,key='b')
        self.assertEqual(self.state('old'),SUSPECTED)
    def test_confirmation_not_cancelled(self):
        self.add('a1',1);self.apply(['a1'],3)
        self.apply(['a1'],5,kind='outward_loss')
        self.assertEqual(self.state('a1'),CONFIRMED)
    def test_preserved_confirmation_keeps_exact_source_time(self):
        self.add('a1',1)
        self.apply(['a1'],3,kind='preserved_confirmation')
        self.assertEqual(self.s.evidence['a1']['first_confirmation_pts'],3)
    def test_preserved_and_new_same_time_one_notice(self):
        self.add('a1',1)
        rs=[resolution(['a1'],3,kind='preserved_confirmation'),resolution(['a1'],3)]
        self.s.process(3,resolutions=rs)
        self.assertEqual(self.s.export()['counts']['confirmation_notifications'],1)
    def test_rewind_no_future_confirmation(self):
        self.add('a1',1);self.apply(['a1'],3)
        self.assertEqual(lifecycle_cards_at(self.s.timeline,2)[0]['automatic_status'],SUSPECTED)
    def test_rewind_no_future_release(self):
        self.add('a1',1);self.apply(['a1'],3,kind='outward_loss')
        self.assertEqual(lifecycle_cards_at(self.s.timeline,2)[0]['automatic_status'],SUSPECTED)
    def test_repeated_batch_no_duplicate(self):
        self.add('a1',1);r=self.apply(['a1'],3)
        before=deepcopy(self.s.export());self.s.process(3,resolutions=[r])
        self.assertEqual(before,self.s.export())
    def test_bad_filtered_event_not_silently_ignored(self):
        self.add('a1',1)
        with self.assertRaises(ValueError):self.apply(['missing','a1'],3)
    def test_wrong_direction_atomic_rollback(self):
        self.add('a1',1);before=deepcopy(self.s.export())
        with self.assertRaises(ValueError):self.apply(['a1'],3,direction='outward')
        self.assertEqual(before,self.s.export())
    def test_stale_direction_rejected(self):
        self.add('a1',1)
        with self.assertRaises(ValueError):self.apply(['a1'],5,direction_end_pts=1)
    def test_missing_absence_rejected(self):
        self.add('a1',1)
        with self.assertRaises(ValueError):self.apply(['a1'],2,last=1.5)
    def test_source_gap_rejected(self):
        self.add('a1',1)
        with self.assertRaises(ValueError):self.apply(['a1'],3,recording_continuous=False)
    def test_no_false_release_for_nearby_other_key(self):
        self.add('a1',1)
        with self.assertRaises(ValueError):self.apply(['a1'],3,key='b',kind='outward_loss')
    def test_cross_camera_rejected(self):
        self.add('a1',1);self.add('b1',1.1,'a',camera='C6')
        with self.assertRaises(ValueError):self.apply(['a1','b1'],3)
    def test_payloads_not_rewritten(self):
        self.add('a1',1);old=deepcopy(self.s.events)
        self.apply(['a1'],3,kind='outward_loss')
        self.assertEqual(old,self.s.events)
    def test_no_person_inference(self):
        self.add('a1',1);self.apply(['a1'],3)
        self.assertFalse(self.s.export()['identity_verified'])
        self.assertFalse(self.s.export()['ownership_is_identity_proof'])
    def test_release_after_long_observation_not_group_window_limited(self):
        self.add('a1',1);self.apply(['a1'],30,kind='outward_loss')
        self.assertEqual(self.state('a1'),RELEASED)
    def test_old_card_not_erased_by_new_card_release(self):
        self.add('a1',1);self.add('a2',12)
        self.apply(['a1','a2'],14,kind='outward_loss')
        self.assertEqual((self.state('a1'),self.state('a2')),(SUSPECTED,RELEASED))
    def test_export_is_detached(self):
        self.add('a1',1);self.apply(['a1'],3)
        out=self.s.export();out['outcome_routing'].clear()
        self.assertTrue(self.s.export()['outcome_routing'])

if __name__=='__main__':unittest.main()
