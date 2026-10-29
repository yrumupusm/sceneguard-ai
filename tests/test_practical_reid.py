"""Measurement/provenance contracts; synthetic crops, no pretrained inference."""
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from sceneguard.practical_reid import CachedBoxes, PracticalReIDAdapter, SETTINGS, create_adapter
from sceneguard.practical_reid_runner import native_frames, run


def frame(pts=0., boxes=None, scores=None):
    return dict(pts=pts, native_pts=round(pts*15360), time_base='1/15360',
                source_size=[100,100], boxes=[[20,20,40,70]] if boxes is None else boxes,
                scores=[.9] if scores is None else scores)


class StubTracker:
    def __init__(self):
        self.frame_id = 0
        self.tracked_stracks = []
        self.lost_stracks = []
    def update(self, inputs, img):
        self.frame_id += 1
        self.inputs = inputs; self.image = img


class ReIDContractTests(unittest.TestCase):
    def test_results_protocol_masks_and_coordinates(self):
        boxes = CachedBoxes([[10,20,30,60,.9,0],[5,6,15,16,.3,0]])
        self.assertEqual(boxes.xywh.tolist(), [[20,40,20,40],[10,11,10,10]])
        self.assertEqual(boxes[boxes.conf >= .5].conf.tolist(), [.9])
        self.assertEqual(CachedBoxes([]).xywh.shape, (0,4))

    def test_raw_observation_does_not_use_kalman_bbox(self):
        tracker = StubTracker()
        tracker.tracked_stracks = [SimpleNamespace(frame_id=1,idx=0,track_id=7,
            score=.9,is_activated=True,xyxy=np.array([30,40,50,90]))]
        original = np.zeros((100,100,3),dtype=np.uint8)
        obs, states, unmatched = PracticalReIDAdapter(tracker).step(frame(),original)
        self.assertIs(tracker.image, original)
        self.assertEqual(obs[0]['bbox'], [.2,.2,.4,.7])
        self.assertEqual(obs[0]['filter_bbox'], [.3,.4,.5,.9])
        self.assertEqual(obs[0]['cache_index'],0)
        self.assertEqual(states,obs); self.assertEqual(unmatched,[])

    def test_lost_predictions_have_no_observed_bbox(self):
        tracker = StubTracker(); adapter = PracticalReIDAdapter(tracker)
        adapter.last_seen[7] = 0.
        tracker.lost_stracks = [SimpleNamespace(state=2,track_id=7,is_activated=True,
                                                xyxy=np.array([20,20,40,70]))]
        obs, states, _ = adapter.step(frame(1/30,[],[]),np.zeros((100,100,3),np.uint8))
        self.assertEqual(obs,[])
        self.assertIsNone(states[0]['bbox'])
        self.assertFalse(states[0]['observed'])
        self.assertEqual(states[0]['last_observed_pts'],0.)

    def test_reject_wrong_image_and_nonincreasing_pts(self):
        adapter = PracticalReIDAdapter(StubTracker())
        with self.assertRaises(ValueError): adapter.step(frame(),np.zeros((50,50,3),np.uint8))
        adapter.step(frame(),np.zeros((100,100,3),np.uint8))
        with self.assertRaises(ValueError): adapter.step(frame(),np.zeros((100,100,3),np.uint8))

    def test_wrong_weight_rejected_before_model_load(self):
        with TemporaryDirectory() as directory:
            p = Path(directory)/'bad.onnx';p.write_bytes(b'not a model')
            with self.assertRaisesRegex(ValueError,'pinned official'): create_adapter(p,1/30)

    def test_no_conditional_evidence_no_output(self):
        with self.assertRaisesRegex(ValueError,'Conditional execution'):
            run('missing','missing','outputs/nonexistent-reid-test','missing','')

    def test_unconfirmed_measurement_excluded_from_boundary(self):
        tracker = StubTracker()
        tracker.tracked_stracks = [SimpleNamespace(frame_id=1,idx=0,track_id=7,
            score=.9,is_activated=False,xyxy=np.array([20,20,40,70]))]
        obs, states, unmatched = PracticalReIDAdapter(tracker).step(frame(),np.zeros((100,100,3),np.uint8))
        self.assertEqual(obs,[]); self.assertTrue(states[0]['observed'])
        self.assertFalse(states[0]['confirmed']); self.assertEqual(unmatched,[])

    @unittest.skipUnless(importlib.util.find_spec('ultralytics'), 'optional pinned Ultralytics environment')
    def test_official_botsort_full_indices_empty_and_reobservation(self):
        from ultralytics.trackers.bot_sort import BOTSORT
        from ultralytics.trackers.utils.reid import ReID
        calls = []
        def crop_features(img, detections):
            crops = ReID._crop_detections(img,detections)
            calls.extend(crops)
            return [np.array([1.,.5]) for _ in crops]
        args = SimpleNamespace(**SETTINGS,model='explicit-test-encoder',track_buffer=90)
        with patch('ultralytics.trackers.bot_sort.build_encoder',return_value=crop_features):
            tracker = BOTSORT(args)
        adapter = PracticalReIDAdapter(tracker)
        image = np.zeros((100,100,3),np.uint8);image[:,:,0] = 123
        obs,_,_ = adapter.step(frame(),image)
        self.assertEqual(obs[0]['track_id'],1)
        # A low-score row before the high-score row verifies upstream full-set idx.
        obs,_,_ = adapter.step(frame(1/30,[[65,20,80,70],[20,20,40,70]],[.3,.9]),image)
        self.assertEqual(obs[0]['cache_index'],1)
        obs,states,_ = adapter.step(frame(2/30,[],[]),image)
        self.assertEqual(obs,[]);self.assertFalse(states[0]['observed'])
        obs,_,_ = adapter.step(frame(3/30),image)
        self.assertEqual(obs[0]['track_id'],1)
        obs,_,_ = adapter.step(frame(4/30,scores=[.3]),image)
        self.assertEqual(obs[0]['association'],'low_second')
        self.assertGreater(len(calls),0)
        self.assertTrue(all(np.all(c[:,:,0]==123) for c in calls))


class NativeDecodeTests(unittest.TestCase):
    def setUp(self):
        import av
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.source=Path(self.tmp.name)/'synthetic.mp4'
        with av.open(str(self.source),'w') as container:
            stream=container.add_stream('mpeg4',rate=30)
            stream.width=stream.height=100;stream.pix_fmt='yuv420p'
            for i in range(4):
                video=av.VideoFrame.from_ndarray(np.full((100,100,3),i*20,np.uint8),format='bgr24')
                for packet in stream.encode(video):container.mux(packet)
            for packet in stream.encode():container.mux(packet)
        with av.open(str(self.source)) as container:
            self.cached=[frame(float(v.pts*v.time_base),[],[]) | dict(native_pts=v.pts,time_base=str(v.time_base))
                         for v in container.decode(video=0)]

    def test_exact_native_frames(self):
        decoded=list(native_frames(self.source,self.cached))
        self.assertEqual([f for f,_ in decoded],self.cached)
        self.assertTrue(all(bgr.shape==(100,100,3) for _,bgr in decoded))

    def test_skipped_native_pts_rejected(self):
        self.cached[1]['native_pts']+=1
        with self.assertRaisesRegex(ValueError,'timing mismatch'):
            list(native_frames(self.source,self.cached))

    def test_cache_beyond_eof_rejected(self):
        self.cached.append(frame(4/30,[],[]))
        with self.assertRaisesRegex(ValueError,'ended'):
            list(native_frames(self.source,self.cached))


if __name__ == '__main__': unittest.main()
