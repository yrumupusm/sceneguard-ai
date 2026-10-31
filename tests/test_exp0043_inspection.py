import unittest
import numpy as np
from sceneguard.exp0043_inspection import geometry_metrics, quantiles


class GeometryInspectionTests(unittest.TestCase):
    scene=dict(line=[[.5,0],[.5,1]],source_size=[100,100])

    def test_parallel_walk_has_tangent_but_no_normal_progress(self):
        p=np.array([[40,20],[40,30],[40,40.]])
        r=geometry_metrics(p,p+[0,10],self.scene,40)
        self.assertEqual(r['median_normal_px'],0)
        self.assertEqual(r['median_tangent_px'],10)
        self.assertEqual(r['progress_q75_px'],0)

    def test_approach_distance_geometry(self):
        p=np.array([[20,20],[20,30],[20,40.]])
        r=geometry_metrics(p,p+[10,0],self.scene,40)
        self.assertEqual(r['distance_px'],20)
        self.assertEqual(r['progress_q75_px'],10)
        self.assertEqual(r['distance_over_height'],.5)

    def test_waiting_zero_components(self):
        p=np.array([[40,20],[40,30],[40,40.]])
        r=geometry_metrics(p,p,self.scene,40)
        for key in ('median_dx_px','median_dy_px','deformation_q80_px','upward_q80_px'):
            self.assertEqual(r[key],0)

    def test_partial_body_uses_seed_scale_without_claiming_semantics(self):
        p=np.array([[40,20],[40,25],[40,30.]])
        r=geometry_metrics(p,p+[0,-4],self.scene,80)
        self.assertEqual(r['upward_q80_px'],4)
        self.assertEqual(r['height_px'],80)
        self.assertNotIn('intrusion',r)

    def test_nonrigid_image_change_is_visible(self):
        p=np.array([[40,20],[40,30],[40,40.]])
        r=geometry_metrics(p,p+[[0,-10],[0,0],[10,-15]],self.scene,40)
        self.assertGreater(r['deformation_q80_px'],0)
        self.assertGreater(r['upward_q80_px'],0)

    def test_finite_segment_endpoint_distance(self):
        p=np.array([[50,110],[50,110],[50,110.]])
        r=geometry_metrics(p,p,self.scene,40)
        self.assertEqual(r['distance_px'],10)
        self.assertEqual(r['beyond_segment_points'],3)

    def test_empty_distribution_is_missing(self):
        self.assertIsNone(quantiles([]))


if __name__=='__main__':unittest.main()
