import copy
import json
import unittest

from sceneguard.incident_lifecycle import (
    IncidentLifecycle, SUSPECTED, CONFIRMED, RELEASED, lifecycle_cards_at)


def candidate(eid='e1', at=1., key='run-1', gate='G', protected=False):
    return dict(event=dict(event_id=eid,decision_time_pts=at,status=SUSPECTED,
        session_id='S',camera_id='C',gate_id=gate,track_ids=[7],
        source_ref={'source_pointer':'/'+eid},source_event={'untouched':True}),
        observation_key=key,release_protected=protected,binding={'method':'actual_ref'})


def outcome(at=3., ids=('e1',), key='run-1', kind='outward_loss', **extra):
    result=dict(resolution_id=kind+str(at)+str(ids),kind=kind,event_ids=list(ids),
        decision_time_pts=at,evidence_until_pts=at,observation_key=key,
        direction='outward' if kind=='outward_loss' else 'inward',
        last_observed_pts=at-1.,loss_wait=1.,direction_end_pts=at-1.,
        direction_history_seconds=1.,recording_continuous=True,
        observation_continues=False,recent_gate_contact=True,
        confirmation_source='EXP-0045')
    result.update(extra)
    return result


class LifecycleTests(unittest.TestCase):
    def setUp(self): self.engine=IncidentLifecycle()
    def open(self, *rows):
        for row in rows or (candidate(),):
            self.engine.process(row['event']['decision_time_pts'],[row])
    def card(self): return self.engine.export()['cards'][0]

    def test_first_suspicion_once(self):
        self.open(candidate(),candidate('e2',2.))
        self.assertEqual(len(self.engine.notifications),1)
        self.assertEqual(self.card()['automatic_status'],SUSPECTED)

    def test_outward_absence_releases(self):
        self.open(); self.engine.process(3.,resolutions=[outcome()])
        self.assertEqual(self.card()['automatic_status'],RELEASED)
        self.assertEqual(len(self.engine.notifications),1)
        self.assertEqual(self.engine.events['e1']['status'],SUSPECTED)

    def test_inward_absence_confirms(self):
        self.open(); self.engine.process(3.,resolutions=[outcome(kind='inward_loss')])
        self.assertEqual(self.card()['automatic_status'],CONFIRMED)
        self.assertEqual([n['kind'] for n in self.engine.notifications],['suspicion','confirmation'])

    def test_confirmation_does_not_create_a_card(self):
        self.open(); cid=self.card()['incident_id']
        self.engine.process(3.,resolutions=[outcome(kind='inward_loss')])
        self.assertEqual(self.card()['incident_id'],cid)
        self.assertEqual(len(self.engine.cards),1)

    def test_repeated_confirmation_notifies_once(self):
        self.open(candidate(),candidate('e2',2.))
        self.engine.process(3.,resolutions=[outcome(kind='inward_loss')])
        self.engine.process(4.,resolutions=[outcome(at=4.,ids=('e2',),kind='inward_loss')])
        self.assertEqual(sum(n['kind']=='confirmation' for n in self.engine.notifications),1)

    def test_confirmation_is_not_cleared_by_departure(self):
        self.open(); self.engine.process(3.,resolutions=[outcome(kind='inward_loss')])
        self.engine.process(5.,resolutions=[outcome(at=5.)])
        self.assertEqual(self.card()['automatic_status'],CONFIRMED)

    def test_one_person_leaves_other_suspicion_stays(self):
        self.open(candidate(),candidate('e2',2.,'run-2'))
        self.engine.process(3.,resolutions=[outcome()])
        self.assertEqual(self.card()['automatic_status'],SUSPECTED)
        self.assertEqual(self.card()['unresolved_event_ids'],['e2'])

    def test_all_affected_evidence_can_release(self):
        self.open(candidate(),candidate('e2',2.,'run-2'))
        self.engine.process(3.,resolutions=[outcome()])
        self.engine.process(4.,resolutions=[outcome(at=4.,ids=('e2',),key='run-2')])
        self.assertEqual(self.card()['automatic_status'],RELEASED)

    def test_same_observation_multiple_candidates_release_together(self):
        self.open(candidate(),candidate('e2',2.))
        self.engine.process(3.,resolutions=[outcome(ids=('e1','e2'))])
        self.assertEqual(self.card()['automatic_status'],RELEASED)

    def test_confirmation_wins_over_another_departure(self):
        self.open(candidate(),candidate('e2',2.,'run-2'))
        self.engine.process(3.,resolutions=[outcome(),outcome(ids=('e2',),key='run-2',kind='inward_loss')])
        self.assertEqual(self.card()['automatic_status'],CONFIRMED)

    def test_same_instant_initial_confirmation_only_one_notice(self):
        self.engine.process(3.,[candidate(at=3.)],[outcome(kind='preserved_confirmation')])
        self.assertEqual([n['kind'] for n in self.engine.notifications],['confirmation'])

    def test_no_timeout_release(self):
        self.open(); self.engine.process(120.)
        self.assertEqual(self.card()['automatic_status'],SUSPECTED)

    def test_outcome_after_grouping_window_still_updates(self):
        self.open(); self.engine.process(60.,resolutions=[outcome(at=60.)])
        self.assertEqual(self.card()['automatic_status'],RELEASED)
        self.assertEqual(len(self.engine.cards),1)

    def test_no_future_release_in_rewind(self):
        self.open(); self.engine.process(3.,resolutions=[outcome()])
        self.assertEqual(lifecycle_cards_at(self.engine.timeline,2.)[0]['automatic_status'],SUSPECTED)
        self.assertEqual(lifecycle_cards_at(self.engine.timeline,3.)[0]['automatic_status'],RELEASED)
        self.assertEqual(lifecycle_cards_at(self.engine.timeline,0.),[])

    def test_released_hidden_only_when_requested(self):
        self.open(); self.engine.process(3.,resolutions=[outcome()])
        self.assertEqual(lifecycle_cards_at(self.engine.timeline,3.,include_released=False),[])

    def test_snapshot_is_detached(self):
        self.open(); snap=lifecycle_cards_at(self.engine.timeline,1.)
        snap[0]['event_ids'].append('fake')
        self.assertNotIn('fake',self.card()['event_ids'])

    def test_duplicate_batch_idempotent(self):
        row=candidate(); self.engine.process(1.,[row]); before=self.engine.export()
        self.assertEqual(self.engine.process(1.,[row]),[])
        self.assertEqual(before,self.engine.export())

    def test_different_same_time_batch_rejected(self):
        self.open()
        with self.assertRaises(ValueError): self.engine.process(1.,[candidate('new')])

    def test_time_reversal_rejected(self):
        self.open()
        with self.assertRaises(ValueError): self.engine.process(.5)

    def test_untouched_raw_payload(self):
        row=candidate(); saved=copy.deepcopy(row)
        self.open(row); self.engine.process(3.,resolutions=[outcome()])
        self.assertEqual(row,saved)
        self.assertEqual(self.engine.export()['events'],[saved['event']])

    def test_bad_evidence_is_atomic(self):
        self.open(); before=self.engine.export()
        with self.assertRaises(ValueError):
            self.engine.process(3.,[candidate('e2',3.)],[outcome(evidence_until_pts=4.)])
        self.assertEqual(before,self.engine.export())

    def test_wrong_observation_cannot_release(self):
        self.open()
        with self.assertRaises(ValueError): self.engine.process(3.,resolutions=[outcome(key='other')])

    def test_different_camera_scopes_cannot_share_resolution(self):
        self.open(candidate(),candidate('e2',2.,gate='other'))
        with self.assertRaises(ValueError): self.engine.process(3.,resolutions=[outcome(ids=('e1','e2'))])

    def test_unknown_direction_cannot_release(self):
        self.open()
        with self.assertRaises(ValueError): self.engine.process(3.,resolutions=[outcome(direction='unknown')])

    def test_stationary_or_stale_direction_cannot_release(self):
        self.open()
        with self.assertRaises(ValueError):
            self.engine.process(3.,resolutions=[outcome(direction_end_pts=0.)])

    def test_source_gap_cannot_be_called_departure(self):
        self.open()
        with self.assertRaises(ValueError):
            self.engine.process(3.,resolutions=[outcome(recording_continuous=False)])

    def test_short_absence_cannot_release(self):
        self.open()
        with self.assertRaises(ValueError):
            self.engine.process(3.,resolutions=[outcome(last_observed_pts=2.9)])

    def test_visible_continuation_cannot_release(self):
        self.open()
        with self.assertRaises(ValueError):
            self.engine.process(3.,resolutions=[outcome(observation_continues=True)])

    def test_independent_boundary_evidence_is_protected(self):
        self.open(candidate(protected=True))
        self.engine.process(3.,resolutions=[outcome()])
        self.assertEqual(self.card()['automatic_status'],SUSPECTED)
        self.assertEqual(self.engine.resolution_log[0]['protected_event_ids'],['e1'])

    def test_later_positive_supersedes_provisional_release(self):
        self.open(); self.engine.process(3.,resolutions=[outcome()])
        self.engine.process(4.,resolutions=[outcome(at=4.,kind='preserved_confirmation')])
        self.assertEqual(self.card()['automatic_status'],CONFIRMED)
        self.assertEqual(lifecycle_cards_at(self.engine.timeline,3.)[0]['automatic_status'],RELEASED)

    def test_reopened_same_card_not_repeated_initial_notice(self):
        self.open(); self.engine.process(2.,resolutions=[outcome(at=2.)])
        self.engine.process(3.,[candidate('e2',3.,'run-2')])
        self.assertEqual(self.card()['automatic_status'],SUSPECTED)
        self.assertEqual(len(self.engine.notifications),1)

    def test_replay_produces_identical_notification_keys(self):
        for engine in (self.engine, other:=IncidentLifecycle()):
            engine.process(1.,[candidate()])
            engine.process(3.,resolutions=[outcome(kind='inward_loss')])
        self.assertEqual(self.engine.export(),other.export())
        json.dumps(other.export(),allow_nan=False)

    def test_inward_without_gate_context_is_not_confirmation(self):
        self.open()
        with self.assertRaises(ValueError):
            self.engine.process(3.,resolutions=[outcome(kind='inward_loss',recent_gate_contact=False)])

    def test_confirmation_precedence_same_time(self):
        self.open()
        self.engine.process(3.,resolutions=[outcome(),outcome(kind='preserved_confirmation')])
        self.assertEqual(self.card()['automatic_status'],CONFIRMED)
        self.assertIsNone(self.engine.evidence['e1']['released_pts'])

if __name__=='__main__': unittest.main()
