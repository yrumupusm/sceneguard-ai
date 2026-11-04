"""Independent synthetic passage contracts; never CCTV accuracy or foot truth.

Run against the implementation checkout with its root first on PYTHONPATH.
The pre-implementation review revision has no dual_boundary module and skips.
"""
import unittest

try:
    from sceneguard.dual_boundary import Corridor, PassageState
except ModuleNotFoundError as error:
    if error.name != 'sceneguard.dual_boundary':
        raise
    Corridor = PassageState = None


def scene():
    return dict(source_size=[1000, 1000],
        line=[[.4, .2], [.4, .8]], inner_line=[[.6, .2], [.6, .8]],
        approach_polygon=[[.2, .05], [.8, .05], [.8, .95], [.2, .95]],
        zones={'outside': [[0, 0], [.39, 0], [.39, 1], [0, 1]],
               'inside': [[.61, 0], [1, 0], [1, 1], [.61, 1]]},
        directions=['outside_to_inside', 'inside_to_outside'])


def observe(positions):
    state = PassageState(Corridor(scene()))
    for i, (x, y) in enumerate(positions):
        # Exactly (x,y) at the documented 65%-height image proxy.
        state.step(dict(pts=i/10, frame_index=i, cache_index=0,
            bbox=[x-.03, y-.13, x+.03, y+.07], observed=True))
    return state


def mirror(positions):
    return [(1-x, y) for x, y in positions]


@unittest.skipIf(PassageState is None, 'Implementation module absent at preflight baseline')
class IndependentDualBoundaryReview(unittest.TestCase):
    def test_touch_then_walk_past_endpoint_is_not_finite_passage(self):
        inward = ([(.35, .5)]*3 + [(x, .5) for x in [.4, .45, .5, .55, .6]]
            + [(.6, y) for y in [.55, .6, .65, .7, .75, .8, .85]]
            + [(.65, .85)]
            + [(.65, y) for y in [.8, .75, .7, .65, .6, .55, .5]]
            + [(.65, .5)]*3)
        for positions in (inward, mirror(inward)):
            with self.subTest(start=positions[0]):
                decision = observe(positions).decision((len(positions)-1)/10)
                self.assertFalse(decision['automatic_confirmation'])

    def test_real_two_boundary_crossings_work_symmetrically(self):
        inward = [(.35, .5)]*3 + [(x, .5) for x in [.4, .45, .5, .55, .6]] + [(.65, .5)]*3
        for positions, expected in ((inward, 'outside_to_inside'),
                (mirror(inward), 'inside_to_outside')):
            with self.subTest(direction=expected):
                decision = observe(positions).decision((len(positions)-1)/10)
                self.assertTrue(decision['automatic_confirmation'])
                self.assertEqual(decision['direction'], expected)

    def test_corridor_dwell_retains_origin_beyond_old_three_second_window(self):
        positions = [(.35, .5)]*3 + [(.4, .5), (.45, .5)] + [(.5, .5)]*40 + [(.55, .5), (.6, .5)] + [(.65, .5)]*3
        decision = observe(positions).decision((len(positions)-1)/10)
        self.assertTrue(decision['automatic_confirmation'])

    def test_stationary_corridor_dwell_is_not_passage(self):
        for x in (.4, .5, .6, .65):
            with self.subTest(x=x):
                self.assertFalse(observe([(x, .5)]*50).decision(4.9)['automatic_confirmation'])

    def test_future_destination_dwell_cannot_confirm_prefix(self):
        positions = [(.35, .5)]*3 + [(x, .5) for x in [.4, .45, .5, .55, .6]] + [(.65, .5)]*3
        self.assertFalse(observe(positions[:-1]).decision(.9)['automatic_confirmation'])
        self.assertTrue(observe(positions).decision(1.)['automatic_confirmation'])

    def test_actual_passage_stays_positive_after_continuous_return(self):
        positions = [(.35, .5)]*3 + [(x, .5) for x in [.4, .45, .5, .55, .6]] + [(.65, .5)]*3
        positions += [(x, .5) for x in [.6, .55, .5, .45, .4]] + [(.35, .5)]*3
        for path in (positions, mirror(positions)):
            with self.subTest(start=path[0]):
                self.assertTrue(observe(path).decision((len(path)-1)/10)['automatic_confirmation'])


if __name__ == '__main__':
    unittest.main()
