from copy import deepcopy
import unittest
from test_gate_activity_episodes import SCOPE, event, state, drive, opened, GateActivityEpisodes, CONFIRMED
from webapp.incident import load_activity, incident_registrations
from unittest.mock import patch

class ActivityWebTests(unittest.TestCase):
    def fixture(self):
        e = event('a'*64, .2)
        result = drive(GateActivityEpisodes(SCOPE), 6., {.2: opened(e), .8: dict(evidence_updates=[state(e, CONFIRMED, .8)])}, present=lambda at: at <= 1.)
        result.update(source_window=[0, 6], source_resolution_log=[dict(decision_time_pts=.8, incident_id='incident-old')], source_resolution_ids_refer_to_prior_cards=True)
        return result

    def test_registration_listing_includes_activity(self):
        with patch('webapp.incident.config', return_value={'incident_bundles': {'new': {'experiment_id': 'EXP-0049'}}}), patch('webapp.incident.load_bundle', return_value={'source_label': '007', 'view_label': 'activity', 'source_window': [0, 6]}):
            self.assertEqual(incident_registrations('EXP-0049')[0]['id'], 'new')

    def test_snapshots_and_source_identifiers(self):
        result = self.fixture(); entry = dict(session_id='recording', notification_enabled=False, sha256='a'*64)
        loaded = load_activity(result, entry, 'new', 'video')
        self.assertEqual(loaded['contract'], 'gate_activity_episodes_v1')
        self.assertEqual(loaded['source_resolution_log'][0]['incident_id'], 'incident-old')
        before = [r['card'] for r in loaded['timeline'] if r['decision_time_pts'] < .8][-1]
        after = loaded['timeline'][-1]['card']
        self.assertEqual(before['automatic_status'], '침입 의심')
        self.assertEqual(before['observation_status'], 'open')
        self.assertIsNone(before['observation_closed_pts'])
        self.assertEqual(after['automatic_status'], '침입 확인')
        self.assertEqual(after['observation_status'], 'closed')
        bad = deepcopy(result); bad['timeline'][0]['card']['observation_closed_pts'] = 5.
        with self.assertRaises(ValueError): load_activity(bad, entry, 'new', 'video')
        bad = deepcopy(result); bad['source_resolution_ids_refer_to_prior_cards'] = False
        with self.assertRaises(ValueError): load_activity(bad, entry, 'new', 'video')

if __name__ == '__main__': unittest.main()
