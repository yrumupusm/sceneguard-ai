"""Target-box binding requires a coherent source-moving cohort and actual boxes."""
from copy import deepcopy
import unittest
from tests.test_gate_observation import fixture, scene
from sceneguard.gate_observation import GateObservationDirection


def background_case(giant=False, disappear=False):
    frames, source, event = fixture()
    for i, frame in enumerate(frames):
        path = frame['point_paths'][0]
        # Six fixed scene points + three points moving with the actual source.
        x = [440, 450, 460][i] if i < 3 else 700
        path['point_ids'] = list(range(9))
        path['points_original_pixels'] = [[460,510+j] for j in range(6)] + [[x,520+j] for j in range(3)]
        if i >= 3:
            frame['actual_boxes'][0]['bbox'] = [.4,.05,.49,.95] if giant else [.425,.35,.495,.55]
        if disappear and i > 6:
            frame['actual_boxes'] = []
    return frames, source, event


class TargetBindingContracts(unittest.TestCase):
    def assert_not_strongly_bound(self, engine, source, index):
        details = engine.continuation_details(source, index)
        self.assertNotIn(engine.continuation(source,index), (
            'same_side_continuation','recent_bound_continuation',
            'boundary_unclear_continuation','cross_side_observation'))
        advanced = engine.latest_bound_loss_context(source, details)
        self.assertTrue(advanced is None or advanced['rows'][-1]['pts'] == source['rows'][-1]['pts'])
        self.assertIsNone(engine.observed_crossing(source,index,details))

    def test_stationary_background_majority_cannot_bind_other_box(self):
        frames, source, _ = background_case()
        self.assert_not_strongly_bound(GateObservationDirection(frames,scene()),source,12)

    def test_background_points_in_incompatible_box_cannot_advance_clock(self):
        frames, source, _ = background_case(giant=True)
        engine = GateObservationDirection(frames,scene())
        self.assertFalse(engine._connected_boxes(source['rows'][-1],dict(pts=.3,bbox=frames[3]['actual_boxes'][0]['bbox'])))
        self.assert_not_strongly_bound(engine,source,12)

    def test_expired_background_only_match_is_not_recent_target_visibility(self):
        frames, source, _ = background_case(disappear=True)
        self.assert_not_strongly_bound(GateObservationDirection(frames,scene()),source,12)

    def test_valid_moving_target_can_stop_after_source_fragment(self):
        frames, source, _ = fixture([440,450,460]+[470]*10)
        engine = GateObservationDirection(frames,scene())
        self.assertEqual(engine.continuation(source,12),'same_side_continuation')
        self.assertEqual(engine.latest_bound_loss_context(source,engine.continuation_details(source,12))['rows'][-1]['pts'],1.2)

    def test_camera_only_motion_cannot_supply_target_motion_cohort(self):
        frames, source, _ = fixture([440,450,460]+[470]*10)
        for i, frame in enumerate(frames):
            frame['camera_step_pixels'] = [0 if i == 0 or i > 3 else 10,0]
        self.assert_not_strongly_bound(GateObservationDirection(frames,scene()),source,12)

    def test_actual_box_chain_gap_cannot_be_bridged_by_point_survival(self):
        frames, source, _ = fixture([440,450,460]+[470]*10)
        for i in range(3,8):frames[i]['actual_boxes']=[]
        self.assert_not_strongly_bound(GateObservationDirection(frames,scene()),source,12)

    def test_no_historical_target_motion_is_ambiguous_not_confirmation(self):
        frames, source, event = fixture([470]*13)
        engine = GateObservationDirection(frames,scene())
        self.assert_not_strongly_bound(engine,source,12)
        self.assertFalse(engine.classify(event,source)['automatic_confirmation'])

    def test_valid_finite_visible_crossing_remains_confirmable(self):
        frames, source, _ = fixture()
        self.assertTrue(GateObservationDirection(frames,scene()).observed_crossing(source,7)['automatic_confirmation'])


if __name__ == '__main__':unittest.main()
