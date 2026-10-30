"""Local pure-CPU validation tests; original CCTV and full repo not required."""
from copy import deepcopy
import unittest
from sceneguard.exp0035_application import validate_measured_partition


class MeasurementBindingTests(unittest.TestCase):
    def setUp(self):
        self.frames=[dict(pts=0.,detections=[dict(track_id=3,observed=True,confirmed=True,
                        bbox=[.1,.2,.3,.4],cache_index=2)])]
        self.base=dict(segments=[dict(id='s1',raw_id=3,rows=[dict(pts=0.,frame_index=0,
                            bbox=[.1,.2,.3,.4],cache_index=2)])])

    def test_exact_measurement_passes_without_mutation(self):
        copy=deepcopy(self.base)
        validate_measured_partition(self.base,self.frames)
        self.assertEqual(self.base,copy)

    def test_prediction_not_accepted_as_actual(self):
        self.frames[0]['detections'][0]['observed']=False
        with self.assertRaises(ValueError):validate_measured_partition(self.base,self.frames)

    def test_bbox_tampering_fails(self):
        self.base['segments'][0]['rows'][0]['bbox'][0]=.15
        with self.assertRaises(ValueError):validate_measured_partition(self.base,self.frames)

    def test_missing_observation_fails(self):
        self.base['segments'][0]['rows']=[]
        with self.assertRaises(ValueError):validate_measured_partition(self.base,self.frames)

    def test_duplicate_observation_fails(self):
        self.base['segments'].append(deepcopy(self.base['segments'][0]))
        with self.assertRaises(ValueError):validate_measured_partition(self.base,self.frames)

    def test_unconfirmed_track_is_not_measurement(self):
        self.frames[0]['detections'][0]['confirmed']=False
        with self.assertRaises(ValueError):validate_measured_partition(self.base,self.frames)


if __name__=='__main__':unittest.main()
