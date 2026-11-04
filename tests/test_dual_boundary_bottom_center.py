"""Bottom-centre geometry contracts; synthetic boxes are not physical feet."""
import unittest

from sceneguard.approach_disappearance import center
from sceneguard.directional_loss import SavedGateDirection
from sceneguard.dual_boundary import Corridor, PassageState, PROXY, connected
from sceneguard.mvp_pipeline import RuleBackend
from sceneguard.portal_births import make_region


def scene():
    return dict(source_size=[1000, 1000],
        line=[[.2, .4], [.8, .4]], inner_line=[[.2, .6], [.8, .6]],
        approach_polygon=[[.1, .1], [.9, .1], [.9, .9], [.1, .9]],
        zones={'outside': [[0, 0], [1, 0], [1, .39], [0, .39]],
               'inside': [[0, .61], [1, .61], [1, 1], [0, 1]]},
        directions=['outside_to_inside', 'inside_to_outside'])


def row(bottom, index):
    return dict(pts=index / 10, frame_index=index, cache_index=0,
                bbox=[.47, bottom - .3, .53, bottom])


class BottomCenterTests(unittest.TestCase):
    def test_bottom_crosses_while_65_percent_stays_in_corridor(self):
        corridor = Corridor(scene())
        sample = row(.65, 0)
        self.assertEqual(center(sample, [1000, 1000], 1.0), (500., 650.))
        self.assertGreater(corridor.locate(center(sample, [1000, 1000], .65), 'inner')['signed'], 0)
        self.assertEqual(corridor.classify(sample), 'inside')
        self.assertEqual(PROXY, 'actual_bbox_bottom_center_not_reconstructed_feet')

    def test_visible_passage_uses_bottom_path_with_original_box_provenance(self):
        state = PassageState(Corridor(scene()))
        samples = [row(y, i) for i, y in enumerate((.31, .32, .33, .44, .5, .56, .64, .65, .66))]
        for sample in samples:
            state.step(sample)
        decision = state.decision(.8)
        self.assertTrue(decision['automatic_confirmation'])
        self.assertEqual(decision['direction'], 'outside_to_inside')
        self.assertEqual(decision['entry']['measurement'], 'actual_bbox_bottom_center_path')
        self.assertEqual(decision['exit']['measurement'], 'actual_bbox_bottom_center_path')
        self.assertEqual(decision['passage']['destination_observation_refs'][-1], samples[-1])

    def test_association_keeps_midpoint_and_legacy_route_keeps_old_engine(self):
        a = dict(row(.4, 0), bbox=[.47, .2, .53, .4])
        b = dict(row(.56, 1), bbox=[.47, .26, .53, .56])
        # Midpoint displacement 110px fits 150px; bottom displacement 160px does not.
        self.assertAlmostEqual(center(a, [1000, 1000])[1], 300.)
        self.assertAlmostEqual(center(b, [1000, 1000])[1], 410.)
        self.assertTrue(connected(a, b, [1000, 1000]))
        legacy = scene(); legacy.pop('inner_line')
        region = make_region(legacy, 'C', legacy['approach_polygon'], reference_pts=0., note='Synthetic legacy route')
        frames = [dict(frame_index=0, pts=0., native_pts=0, time_base='1/10',
                       actual_boxes=[], point_paths=[], camera_step_pixels=[0., 0.])]
        engine, _ = RuleBackend().prepare(frames, legacy, region, 'C')
        self.assertIs(type(engine), SavedGateDirection)


if __name__ == '__main__':
    unittest.main()
