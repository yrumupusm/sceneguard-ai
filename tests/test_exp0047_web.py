"""Lifecycle viewer uses causal snapshots and isolated comparison intents."""
from copy import deepcopy
import unittest
from sceneguard.incident_lifecycle import IncidentLifecycle, lifecycle_cards_at
from test_incident_lifecycle import candidate, outcome
from webapp.incident import load_lifecycle


class LifecycleWebTests(unittest.TestCase):
    def fixture(self):
        engine = IncidentLifecycle()
        a = candidate('a'*64, 1.)
        b = candidate('b'*64, 2., 'run-2')
        engine.process(1., [a]); engine.process(2., [b])
        engine.process(3., resolutions=[outcome(ids=('a'*64,))])
        engine.process(4., resolutions=[outcome(at=4., ids=('b'*64,), key='run-2', kind='inward_loss')])
        engine.process(5., resolutions=[outcome(at=5., ids=('b'*64,), key='run-2', kind='inward_loss')])
        data = engine.export(); data['source_window'] = [0., 6.]
        return data

    def load(self, data):
        return load_lifecycle(data, dict(session_id='S', notification_enabled=False, sha256='a'*64), 'test', 'video')

    def test_prefix_release_confirmation_and_rewind(self):
        result = self.load(self.fixture()); timeline = result['timeline']
        self.assertEqual(lifecycle_cards_at(timeline, 0), [])
        c = lifecycle_cards_at(timeline, 3)[0]
        self.assertEqual(c['automatic_status'], '침입 의심')
        self.assertEqual(c['released_event_ids'], ['a'*64])
        self.assertEqual(lifecycle_cards_at(timeline, 4)[0]['automatic_status'], '침입 확인')
        self.assertEqual(lifecycle_cards_at(timeline, 1)[0]['automatic_status'], '침입 의심')
        self.assertEqual([n['kind'] for n in result['notification_intents']], ['suspicion', 'confirmation'])
        self.assertEqual(len({n['notification_key'] for n in result['notification_intents']}), 2)
        self.assertFalse(result['notification_enabled'])
        self.assertEqual(self.load(self.fixture()), result)

    def test_reject_duplicate_and_changed_intents(self):
        data = self.fixture(); data['notification_intents'].append(deepcopy(data['notification_intents'][-1]))
        with self.assertRaises(ValueError): self.load(data)
        data = self.fixture(); data['notification_intents'][-1]['kind'] = 'suspicion'
        with self.assertRaises(ValueError): self.load(data)

    def test_release_is_not_manual_non_intrusion(self):
        engine = IncidentLifecycle(); eid = 'a'*64
        engine.process(1., [candidate(eid)])
        engine.process(3., resolutions=[outcome(ids=(eid,))])
        data = engine.export(); data['source_window'] = [0., 6.]
        result = self.load(data)
        card = lifecycle_cards_at(result['timeline'], 3.)[0]
        self.assertEqual(card['automatic_status'], '의심 해제')
        self.assertEqual(card['status'], '침입 의심')
        self.assertEqual([n['kind'] for n in result['notification_intents']], ['suspicion'])

    def test_direct_confirmation_has_no_suspicion_intent(self):
        engine = IncidentLifecycle(); eid = 'a'*64
        engine.process(3., [candidate(eid, 3.)], [outcome(at=3., ids=(eid,), kind='preserved_confirmation')])
        data = engine.export(); data['source_window'] = [0., 6.]
        result = self.load(data)
        self.assertEqual([n['kind'] for n in result['notification_intents']], ['confirmation'])
        self.assertEqual(lifecycle_cards_at(result['timeline'], 3)[0]['first_confirmation_pts'], 3.)


if __name__ == '__main__': unittest.main()
