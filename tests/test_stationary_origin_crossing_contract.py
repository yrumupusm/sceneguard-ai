"""Positive finite passage does not require motion before a source ID ends."""
import unittest
from tests.test_gate_observation import fixture,scene
from sceneguard.gate_observation import GateObservationDirection


class StationaryOriginCrossingContracts(unittest.TestCase):
    def test_stopped_outside_source_then_measured_inward_crossing(self):
        frames,source,_=fixture([460,460,460,480,500,520,540,550,560,560,560,560,560])
        engine=GateObservationDirection(frames,scene())
        decision=engine.observed_crossing(source,7)
        self.assertIsNotNone(decision)
        self.assertEqual(decision['direction'],'outside_to_inside')
        self.assertEqual(decision['decision_time_pts'],.7)
        self.assertFalse(decision['loss_wait_required'])

    def test_stopped_inside_source_then_measured_outward_crossing(self):
        frames,source,_=fixture([540,540,540,520,500,480,460,450,440,440,440,440,440])
        decision=GateObservationDirection(frames,scene()).observed_crossing(source,7)
        self.assertIsNotNone(decision)
        self.assertEqual(decision['direction'],'inside_to_outside')

    def test_stationary_origin_still_needs_future_destination_dwell(self):
        frames,source,_=fixture([460,460,460,480,500,520,540,550,560,560,560,560,560])
        self.assertIsNone(GateObservationDirection(frames[:7],scene()).observed_crossing(source,6))


if __name__=='__main__':unittest.main()
