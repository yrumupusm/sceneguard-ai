"""Real grouping integration, using causal normalized candidates (no media run)."""
import unittest
from copy import deepcopy
from sceneguard.exp0042_application import comparison_bundles, normalize_transition
from sceneguard.incident_cards import GroupPolicy
from dataclasses import asdict

class ActualGrouping(unittest.TestCase):
    def test_actual_grouping_preserves_payload_and_causal_notification(self):
        scope=dict(session_id='s',camera_id='C3',gate_id='C3_fence')
        def event(at, name):
            raw=dict(status='침입 의심',reason='gate_visual_transition',decision_time_pts=at,
                evidence_until_pts=at,evidence=dict(seed_pts=0.,reference_pts=at-.1,
                window_id=name,seed_track_ids=[7]))
            return normalize_transition(raw,scope=scope,video_id='test',source_sha256='hash')
        old=event(2.,'old'); new=event(1.,'new')
        baseline=dict(video_id='test',source_window=[0,4],policy=asdict(GroupPolicy()),events=[old])
        frozen=deepcopy(baseline)
        result=comparison_bundles(baseline,[new])
        self.assertEqual(baseline,frozen)
        self.assertIn(old,result['combined']['events'])
        self.assertEqual(result['combined']['counts']['active_alerts'],2)
        self.assertEqual(result['combined']['counts']['notification_intents'],1)
        self.assertEqual(result['combined']['cards'][0]['first_notification_pts'],1.)
        self.assertEqual(result['baseline']['cards'][0]['first_notification_pts'],2.)
        self.assertTrue(result['combined']['timeline'][0]['notify'])
        self.assertFalse(result['combined']['timeline'][1]['notify'])

if __name__=='__main__': unittest.main()
