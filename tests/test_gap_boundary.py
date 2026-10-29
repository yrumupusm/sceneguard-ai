"""Synthetic state-machine tests, not CCTV accuracy or ReID evaluation."""
import copy
import math
import unittest

from sceneguard.boundary import ObservedBoundary
from sceneguard.gap_boundary import GapTolerantBoundary

CONFIG = dict(line=[[.2, .5], [.8, .5]], roi=[0., 0., 1., 1.], band=.01,
              dwell_seconds=.2, max_gap_seconds=.11, min_iou=.3, cooldown_seconds=2.)


def observation(tid=1, y=.4, x=.5, **extra):
    return dict(track_id=tid, bbox=[x-.05, y-.2, x+.05, y],
                observed=True, confirmed=True) | extra


class GapBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.rule = GapTolerantBoundary(CONFIG)

    def feed(self, seq, rule=None):
        result = []
        for pts, obs in seq:
            result.extend((rule or self.rule).step(pts, obs))
        return result

    def establish(self, tid=1):
        self.feed([(0., [observation(tid)]), (.1, [observation(tid)]), (.2, [observation(tid)])])

    def test_single_missing_frame_no_longer_loses_before_side(self):
        seq = [(0., [observation()]), (.1, [observation()]), (.2, [observation()]),
               (.3, []), (.4, [observation(y=.6)]), (.5, [observation(y=.6)]),
               (.6, [observation(y=.6)])]
        self.assertEqual(self.feed(seq, ObservedBoundary(CONFIG)), [])
        events = self.feed(seq)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['candidate_interval'], [.2, .4])
        self.assertTrue(events[0]['bridged_observation_gap'])

    def test_two_second_occlusion_reconnected_same_id(self):
        self.establish()
        self.rule.step(.3, [])
        events = self.feed([(2.2, [observation(y=.6)]), (2.3, [observation(y=.6)]),
                            (2.4, [observation(y=.6)])])
        self.assertEqual(len(events), 1)
        self.assertAlmostEqual(events[0]['largest_observation_gap_seconds'], 2.)
        self.assertEqual(events[0]['emitted_at_pts'], 2.4)

    def test_missing_time_is_not_dwell_evidence(self):
        self.establish()
        self.rule.step(.3, [observation(y=.6)])
        self.rule.step(.4, [])
        self.assertEqual(self.rule.step(2., [observation(y=.6)]), [])
        self.assertEqual(self.rule.step(2.1, [observation(y=.6)]), [])
        self.assertEqual(len(self.rule.step(2.2, [observation(y=.6)])), 1)

    def test_expiry_is_per_id_and_not_per_frame(self):
        self.establish()
        self.rule.step(.3, [observation(2)])
        self.rule.step(1., [])
        self.assertIn(1, self.rule.tracks)
        self.rule.step(3.21, [])
        self.assertNotIn(1, self.rule.tracks)
        self.assertIn(2, self.rule.tracks)

    def test_gap_longer_than_ttl_does_not_cross(self):
        self.establish()
        self.assertEqual(self.feed([(3.3, [observation(y=.6)]), (3.4, [observation(y=.6)]),
                                    (3.5, [observation(y=.6)])]), [])

    def test_exact_ttl_is_allowed(self):
        self.establish()
        self.assertEqual(len(self.feed([(3.2, [observation(y=.6)]), (3.3, [observation(y=.6)]),
                                        (3.4, [observation(y=.6)])])), 1)

    def test_different_id_is_not_forcibly_linked(self):
        self.establish()
        self.assertEqual(self.feed([(.3, [observation(2, .6)]), (.4, [observation(2, .6)]),
                                    (.5, [observation(2, .6)])]), [])

    def test_predictions_do_not_refresh_memory_or_trigger(self):
        self.establish()
        for t in (.3, 1., 2., 3., 3.21):
            self.assertEqual(self.rule.step(t, [observation(y=.6, observed=False)]), [])
        self.assertNotIn(1, self.rule.tracks)

    def test_unconfirmed_does_not_refresh(self):
        self.establish()
        self.rule.step(3.3, [observation(y=.6, confirmed=False)])
        self.assertNotIn(1, self.rule.tracks)

    def test_same_side_reappearance_not_crossing(self):
        self.establish()
        self.assertEqual(self.feed([(1., [observation()]), (1.1, [observation()]),
                                    (1.2, [observation()])]), [])

    def test_single_wrong_box_does_not_trigger(self):
        self.establish()
        self.assertEqual(self.feed([(.3, [observation(y=.6)]), (.4, [observation()]),
                                    (.5, [observation()])]), [])

    def test_near_boundary_not_a_confirmed_side(self):
        self.establish()
        self.assertEqual(self.feed([(.3, [observation(y=.5)]), (.4, [observation(y=.5)]),
                                    (.5, [observation(y=.5)])]), [])

    def test_quick_reverse_suppressed_but_later_reverse_allowed(self):
        self.establish()
        self.assertEqual(len(self.feed([(.3, [observation(y=.6)]), (.4, [observation(y=.6)]),
                                        (.5, [observation(y=.6)])])), 1)
        self.assertEqual(self.feed([(.6, [observation()]), (.7, [observation()]),
                                    (.8, [observation()])]), [])
        self.feed([(1., [observation(y=.6)]), (1.1, [observation(y=.6)]), (1.2, [observation(y=.6)])])
        events = self.feed([(2.6, [observation()]), (2.7, [observation()]), (2.8, [observation()])])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['direction'], 'positive_to_negative')

    def test_outside_finite_line_not_crossing(self):
        seq = [(i*.1, [observation(y=.4 if i < 3 else .6, x=.95)]) for i in range(6)]
        self.assertEqual(self.feed(seq), [])

    def test_roi_exit_resets_before_side(self):
        self.rule = GapTolerantBoundary(CONFIG | {'roi': [.2,.2,.8,.8]})
        self.establish()
        self.assertEqual(self.feed([(.3, [observation(x=.95)]), (.4, [observation(y=.6)]),
                                    (.5, [observation(y=.6)]), (.6, [observation(y=.6)])]), [])

    def test_invalid_frame_does_not_partially_mutate_state(self):
        self.establish()
        old = copy.deepcopy(self.rule.tracks)
        with self.assertRaises(ValueError):
            self.rule.step(.3, [observation(y=.6), observation(y=.6)])
        self.assertEqual(self.rule.tracks, old)
        self.assertEqual(self.rule.previous_pts, .2)

    def test_invalid_pts_and_boxes(self):
        self.establish()
        for t in (.2, .1, math.nan, math.inf):
            with self.assertRaises(ValueError): self.rule.step(t, [])
        with self.assertRaises(ValueError):
            self.rule.step(.3, [observation(bbox=[0,0,math.nan,1])])

    def test_invalid_parameters(self):
        for ttl in (0, -1, math.inf, math.nan):
            with self.assertRaises(ValueError): GapTolerantBoundary(CONFIG, ttl)
        for n in (1, 2.5, True):
            with self.assertRaises(ValueError): GapTolerantBoundary(CONFIG, min_observations=n)

    def test_input_not_mutated(self):
        seq = [(i*.1, [observation(y=.4 if i < 3 else .6)]) for i in range(6)]
        old = copy.deepcopy(seq)
        self.feed(seq)
        self.assertEqual(seq, old)


if __name__ == '__main__':
    unittest.main()
