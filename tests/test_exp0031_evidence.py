"""Evidence binding and official transform regression; no encoder forward."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from sceneguard.exp0031_evidence import (
    cosine_matrix, decode_exact, fresh_output, manual_draft,
    official_transforms, read, verify_measurement,
)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.row = dict(frame_index=0, cache_index=0, raw_id=11,
                        pts=1.0, bbox=[.1,.2,.4,.8], score=.8)
        self.segment = dict(raw_id=11, rows=[self.row])
        self.cached = [dict(pts=1.0, native_pts=30, time_base='1/30',
                           source_size=[100,200], boxes=[[10,40,40,160]], scores=[.8])]

    def test_binding_accepts_original_measurement(self):
        self.assertIs(verify_measurement(self.row,self.segment,self.cached),self.cached[0])

    def test_binding_rejects_wrong_frame_box_score_and_pts(self):
        for field,value in [('boxes',[[11,40,40,160]]),('scores',[.7]),('pts',1.1),('native_pts',31)]:
            with self.subTest(field=field):
                cached=copy.deepcopy(self.cached);cached[0][field]=value
                with self.assertRaises(ValueError):verify_measurement(self.row,self.segment,cached)

    def test_binding_rejects_wrong_raw_id_or_tracklet(self):
        for segment in (dict(raw_id=10,rows=[self.row]),dict(raw_id=11,rows=[])):
            with self.assertRaises(ValueError):verify_measurement(self.row,segment,self.cached)

    def test_manual_draft_never_invents_identity(self):
        draft=manual_draft(['Q02','Q08','N01'])
        self.assertFalse(draft['identity_ground_truth_created'])
        self.assertEqual(len(draft['cases']),3)
        for case in draft['cases']:
            for key in ('same_person','before_single_person_crop','after_single_person_crop','raw_id_mix_suspected'):
                self.assertEqual(case[key],'unknown')
            self.assertEqual(case['endpoint_detail']['baseline']['source_single_person'],'unknown')
        self.assertIn('baseline',draft['field_semantics']['before_single_person_crop'])

    def test_cosine_uses_unit_features_and_full_pair_matrix(self):
        matrix=cosine_matrix([[2,0],[0,3]],[[1,0],[0,-4]])
        np.testing.assert_allclose(matrix,[[1,0],[0,-1]])
        self.assertEqual(float(np.median(matrix)),0)
        with self.assertRaises(ValueError):cosine_matrix([[0,0]],[[1,0]])

    def test_output_refuses_existing_and_symlink_and_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'outputs';root.mkdir()
            made=fresh_output(root/'review-v1',root)
            self.assertTrue(made.is_dir())
            with self.assertRaises(FileExistsError):fresh_output(made,root)
            alias=Path(tmp)/'alias';alias.symlink_to(root,target_is_directory=True)
            with self.assertRaises(FileExistsError):fresh_output(alias/'review-v2',root)
            with self.assertRaises(FileExistsError):fresh_output(Path(tmp)/'escape',root)

    def test_official_transform_is_cpu_rgb_expanded_and_no_model(self):
        compatibility_path=Path('runtime/EXP-0029/encoder-compatibility.json')
        if not compatibility_path.exists():self.skipTest('Local pinned encoder audit not available')
        try:
            import torch
            from ultralytics.trackers.utils.reid import ReID
        except ImportError:
            self.skipTest('Use existing pinned ReID dependency path for official transform check')
        compatibility=read(compatibility_path)
        with patch.object(ReID,'__init__',side_effect=AssertionError('No model construction')), \
                patch.object(ReID,'__call__',side_effect=AssertionError('No forward')):
            transform,provenance=official_transforms(compatibility)
            bgr=np.zeros((80,100,3),dtype=np.uint8);bgr[:]=[17,71,209]
            box,rect,crop,pixels,tensor_bytes=transform(bgr,[.2,.25,.5,.75])
            self.assertEqual(box,[20,20,50,60])
            self.assertEqual(rect,[14,14,55,65])
            self.assertEqual(list(crop.shape),[51,41,3])
            self.assertEqual(list(pixels.shape),[448,448,3])
            np.testing.assert_array_equal(pixels[0,0],[209,71,17])
            tensor=np.frombuffer(tensor_bytes,dtype=np.float32).reshape(1,3,448,448)
            np.testing.assert_allclose(tensor[0,:,0,0],np.array([209,71,17])/255,atol=1e-7)
            self.assertFalse(torch.cuda.is_initialized())
            self.assertEqual(provenance['encoder_forwards'],0)
            _,rect,_,_,_=transform(bgr,[0,0,.05,.1])
            self.assertEqual(rect[:2],[0,0])

    def test_source_hash_change_stops_transform(self):
        compatibility_path=Path('runtime/EXP-0029/encoder-compatibility.json')
        if not compatibility_path.exists():self.skipTest('Local pinned encoder audit not available')
        try:
            import ultralytics.trackers.utils.reid  # noqa: F401
        except ImportError:self.skipTest('Pinned dependencies unavailable')
        compatibility=read(compatibility_path)
        compatibility['upstream_reid']['sha256']='0'*64
        with self.assertRaises(ValueError):official_transforms(compatibility)

    def test_native_decoder_rejects_nearest_frame(self):
        try:import av
        except ImportError:self.skipTest('PyAV unavailable')
        from fractions import Fraction
        from types import SimpleNamespace
        class Container:
            streams=SimpleNamespace(video=[object()])
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def seek(self,*args,**kwargs):pass
            def decode(self,*args):return iter([SimpleNamespace(pts=31,time_base=Fraction(1,30))])
        with patch.object(av,'open',return_value=Container()):
            with self.assertRaises(ValueError):decode_exact('unused.mp4',self.cached[0])


if __name__=='__main__':
    unittest.main()
