"""Independent guard against followup_run bypassing trusted point binding."""
from copy import deepcopy
import unittest
from tests.test_target_binding_contract import background_case
from tests.test_gate_observation import scene,fixture
from sceneguard.gate_observation import GateObservationDirection
from sceneguard.lifecycle_followup import ObservationHistory,followup_run


def assess(frames,source,index=3):
    runs={'source':deepcopy(source['rows']),'other':[]}
    for f in frames[3:]:
        if f['actual_boxes']:
            runs['other'].append(dict(pts=f['pts'],frame_index=f['frame_index'],cache_index=0,
                bbox=deepcopy(f['actual_boxes'][0]['bbox'])))
    history=ObservationHistory(runs,frames)
    for f in frames[:index+1]:history.advance(f)
    return followup_run(history,GateObservationDirection(frames,scene()),'source',index)


class HandoffBindingContracts(unittest.TestCase):
    def test_background_only_box_cannot_become_handoff_successor(self):
        frames,source,_=background_case()
        self.assertIsNone(assess(frames,source)['successor'])

    def test_disconnected_box_cannot_bypass_via_handoff(self):
        frames,source,_=background_case(giant=True)
        self.assertIsNone(assess(frames,source)['successor'])

    def test_measured_target_moving_then_stopping_can_handoff(self):
        frames,source,_=fixture([440,450,460]+[470]*10)
        self.assertEqual(assess(frames,source)['successor'],'other')


if __name__=='__main__':unittest.main()
