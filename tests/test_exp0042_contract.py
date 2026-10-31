"""Pure contract tests. Grouping adapter is injected; not a claim of local web integration."""
import unittest
from copy import deepcopy
from sceneguard.exp0042_application import normalize_transition, comparison_bundles

SCOPE=dict(session_id='s',camera_id='C3',gate_id='C3_fence')

def raw(pts=2.):
    return dict(status='침입 의심',reason='gate_visual_transition',decision_time_pts=pts,
        evidence_until_pts=pts,evidence=dict(seed_pts=0.,reference_pts=1.,window_id='w000001',seed_track_ids=[7]))

def normalized(pts=2.):
    return normalize_transition(raw(pts),scope=SCOPE,video_id='test',source_sha256='test-source')

def grouping(rows):
    # Test dependency boundary, not the existing incident implementation.
    return dict(events=deepcopy(rows),counts=dict(input_alert_rows=len(rows)))

class Contract(unittest.TestCase):
    def test_new_event_traceability(self):
        e=normalized(); self.assertEqual(e['source_ref']['collection'],'transition_events')
        self.assertEqual(e['decision_time_pts'],2.); self.assertEqual(e['track_ids'],[7])
    def test_same_input_same_event(self): self.assertEqual(normalized(),normalized())
    def test_later_pts_new_event(self): self.assertNotEqual(normalized()['event_id'],normalized(3.)['event_id'])
    def test_no_future_reference(self):
        r=raw(); r['evidence']['reference_pts']=3.
        with self.assertRaises(ValueError): normalize_transition(r,scope=SCOPE,video_id='test',source_sha256='x')
    def test_causal_time_mismatch(self):
        r=raw(); r['evidence_until_pts']=2.1
        with self.assertRaises(ValueError): normalize_transition(r,scope=SCOPE,video_id='test',source_sha256='x')
    def test_combined_preserves_original_false_and_true_candidates(self):
        baseline=dict(video_id='test',source_window=[0,4],events=[dict(event_id='old1',payload='approach'),dict(event_id='old2',payload='loss')])
        old=deepcopy(baseline); r=comparison_bundles(baseline,[normalized()],grouping)
        self.assertEqual(baseline,old); self.assertEqual(r['combined']['events'][:2],old['events'])
        self.assertEqual(len(r['transition-only']['events']),1)
        self.assertTrue(r['transition-only']['transition_only_is_diagnostic'])
        self.assertFalse(r['combined']['false_alarm_reduction_claim'])
    def test_duplicate_new_id_rejected(self):
        with self.assertRaises(ValueError): comparison_bundles(dict(events=[]),[normalized(),normalized()],grouping)
    def test_no_candidates_not_a_normal_verdict(self):
        b=dict(video_id='test',source_window=[0,4],events=[dict(event_id='old')])
        r=comparison_bundles(b,[],grouping)
        self.assertEqual(r['combined']['events'],b['events']); self.assertIsNone(r['combined']['accuracy'])

if __name__=='__main__': unittest.main()
