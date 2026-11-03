"""Original raw-loss retry keeps causality and remeasures its later endpoint."""
from copy import deepcopy
import unittest
from tests.test_gate_observation import fixture,scene
from sceneguard.gate_observation import GateObservationDirection


def delayed_fixture():
    frames,segment,event=fixture([440,450,460,465,470,475,480,485,490]+[490]*12)
    for f in frames[9:]:f['actual_boxes']=[];f['point_paths']=[]
    event['decision_time_pts']=1.2
    return frames,segment,event


class DelayedRawLossTests(unittest.TestCase):
    def test_actual_extension_delays_loss_and_remeasures_latest_motion(self):
        frames,segment,event=delayed_fixture();engine=GateObservationDirection(frames,scene())
        waiting=engine.delayed_raw_loss(event,segment,12)
        self.assertFalse(waiting['automatic_confirmation'])
        self.assertEqual(waiting['retry_after_pts'],1.8)
        final=engine.delayed_raw_loss(event,segment,18)
        self.assertTrue(final['automatic_confirmation'])
        self.assertEqual(final['decision_time_pts'],1.8)
        self.assertEqual(final['last_observed_pts'],.8)
        self.assertEqual(final['direction']['end_pts'],.8)
        self.assertEqual(final['direction']['reference_pts'],.3)
        self.assertEqual(final['original_source'],event)
        self.assertEqual([r['frame_index'] for r in final['measured_loss_context']],list(range(9)))
        self.assertFalse(final['identity_verified'])

    def test_future_extension_cannot_change_current_retry(self):
        f,s,e=delayed_fixture()
        a=GateObservationDirection(f[:13],scene()).delayed_raw_loss(e,s,12)
        b=GateObservationDirection(f,scene()).delayed_raw_loss(e,s,12)
        self.assertEqual(a,b)

    def test_source_and_saved_measurements_remain_immutable(self):
        f,s,e=delayed_fixture();old=deepcopy((f,s,e));engine=GateObservationDirection(f,scene())
        engine.delayed_raw_loss(e,s,12);engine.delayed_raw_loss(e,s,18)
        self.assertEqual(old,(f,s,e))

    def test_wrong_original_raw_id_or_clock_rejected(self):
        for changes in (dict(raw_id=99),dict(segment='other'),dict(last_observed_pts=.1),dict(decision_time_pts=2.)):
            f,s,e=delayed_fixture();e.update(changes)
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                GateObservationDirection(f,scene()).delayed_raw_loss(e,s,18)

    def test_clip_end_before_new_wait_cannot_confirm(self):
        f,s,e=delayed_fixture()
        self.assertFalse(GateObservationDirection(f[:18],scene()).delayed_raw_loss(e,s,17)['automatic_confirmation'])

    def test_recording_gap_cannot_count_as_person_loss(self):
        f,s,e=delayed_fixture()
        for row in f[9:]:row['pts']+=2
        self.assertFalse(GateObservationDirection(f,scene()).delayed_raw_loss(e,s,18)['automatic_confirmation'])

    def test_no_actual_extension_does_not_create_second_primary_rule(self):
        f,s,e=delayed_fixture()
        for row in f[3:]:row['actual_boxes']=[];row['point_paths']=[]
        result=GateObservationDirection(f,scene()).delayed_raw_loss(e,s,18)
        self.assertFalse(result['automatic_confirmation'])
        self.assertEqual(result['reason'],'no_trusted_continuation_extension_to_retry')

if __name__=='__main__':unittest.main()
