import unittest
from scripts.summarize_model_comparison_events import event_diagnostic


class EventSummaryTest(unittest.TestCase):
    def event(self):
        return dict(video_id='x', reference_id='r', gate_id='g', start=10., end=12., baseline_confirmation_matched=False)

    def row(self, anchor, action=True, person=True, role='fullvideo_regular'):
        return dict(window=dict(window_id=str(anchor), role=role, anchor_pts=anchor, available_after_pts=anchor+.933333),
                    action_candidate=action, person_and_action_candidate=person, maximum_action_score=.9 if action else .1)

    def test_other_person_time_candidate_never_success(self):
        result = event_diagnostic(self.event(), [self.row(11)], True)
        self.assertEqual(result['diagnostic'], 'temporal_candidate_identity_unverified')
        self.assertIsNone(result['action_true_positive'])
        self.assertIsNone(result['intrusion_completed'])
        self.assertFalse(result['same_person_and_gate_verified'])
        self.assertAlmostEqual(result['first_candidate_input_available_pts'], 11.933333)

    def test_future_context_and_extra_anchor_do_not_inflate_count(self):
        result = event_diagnostic(self.event(), [self.row(9.5), self.row(11, role='diagnostic')], True)
        self.assertEqual(result['regular_anchor_windows'], 0)
        self.assertEqual(result['diagnostic'], 'no_regular_anchor_in_reference')

    def test_unlocalized_and_low_score_are_distinct(self):
        high = event_diagnostic(self.event(), [self.row(11, person=False)], True)
        low = event_diagnostic(self.event(), [self.row(11, action=False, person=False)], True)
        scene = event_diagnostic(self.event(), [self.row(11, person=False)], False)
        self.assertEqual(high['diagnostic'], 'action_candidate_without_native_person_candidate')
        self.assertEqual(low['diagnostic'], 'input_present_below_action_threshold')
        self.assertEqual(scene['diagnostic'], 'temporal_candidate_identity_unverified')
        self.assertIsNone(scene['person_and_action_candidate_windows'])


if __name__ == '__main__': unittest.main()
