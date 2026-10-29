"""Synthetic cache/video/encoder integration; never calls a learned model."""
from contextlib import contextmanager
from fractions import Fraction
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from sceneguard import run_tracklet_linking as runner
from sceneguard.tracklet_linking import LinkSettings, build_tracklets


@contextmanager
def cwd(path):
    old=Path.cwd();os.chdir(path)
    try:yield
    finally:os.chdir(old)


def fixture(root):
    cache=root/'cache';cache.mkdir()
    source=root/'source.mp4';source.write_bytes(b'fake-source-read-through-injected-decoder')
    weights=root/'reid.onnx';weights.write_bytes(b'fake-checkpoint-no-inference')
    cached=[];tracked=[]
    for i in range(46):
        pts=i/10
        tid=1 if i<7 else 9 if i>=39 else None
        boxes=[];scores=[];rows=[]
        if tid:
            box=[.25,.1,.35,.5] if tid==1 else [.65,.1,.75,.5]
            boxes=[(np.array(box)*[100,80,100,80]).tolist()];scores=[.9]
            rows=[dict(track_id=tid,bbox=box,score=.9,cache_index=0,observed=True,confirmed=True)]
        timing=dict(pts=pts,native_pts=i,time_base='1/10')
        cached.append(dict(**timing,source_size=[100,80],boxes=boxes,scores=scores))
        tracked.append(dict(**timing,detections=rows,states=[]))
    cp=cache/'person_cache.jsonl';tp=root/'frames.jsonl'
    cp.write_text(''.join(json.dumps(r)+'\n' for r in cached))
    tp.write_text(''.join(json.dumps(r)+'\n' for r in tracked))
    meta=dict(status='complete',model_sha256=runner.FCOS_SHA,source_sha256=runner.sha256(source),
              video_id='synthetic',frames=len(cached),person_cache=dict(schema=1,stage=runner.CACHE_STAGE,sha256=runner.sha256(cp)))
    (cache/'run.json').write_text(json.dumps(meta))
    zp=root/'regions.json';zp.write_text(json.dumps(dict(source_sha256=runner.sha256(source),source_size=[100,80],
        outside=[[0,0],[.4,0],[.4,1],[0,1]],inside=[[.6,0],[1,0],[1,1],[.6,1]])))
    return cache,tp,source,weights,zp,cached,tracked


def decoder(source,cached):
    for i in range(len(cached)):yield i,np.full((80,100,3),140,dtype=np.uint8)


class Encoder:
    def __init__(self):self.calls=[]
    def __call__(self,img,dets):
        self.calls.append(dets.copy())
        return [np.array([1.,0.]) for _ in dets]


class RunnerTests(unittest.TestCase):
    def test_synthetic_end_to_end_with_video_and_regions(self):
        with tempfile.TemporaryDirectory() as directory,cwd(directory):
            root=Path(directory);cache,tp,src,w,z,c,t=fixture(root)
            encoder=Encoder()
            with patch.object(runner,'REID_SHA',runner.sha256(w)):
                summary=runner.run(cache,tp,src,w,Path('outputs/test'),zones_path=z,render=True,
                                   encoder_factory=lambda *a:encoder,decoder=decoder)
            self.assertEqual(summary['accepted_links'],1)
            self.assertEqual(summary['candidates'],1)
            self.assertEqual(summary['unlinked_region_candidates'],0)
            self.assertEqual(summary['render']['decoded_frames'],46)
            self.assertEqual(summary['render']['codec'],'h264')
            self.assertEqual(summary['render']['pixel_format'],'yuv420p')
            self.assertTrue(summary['render']['regions_visible'])
            self.assertEqual(summary['render']['available_after_pts'],4.5)
            self.assertEqual(summary['render']['unlinked_candidates'],0)
            self.assertEqual(summary['render']['linked_candidates'],1)
            import av
            with av.open('outputs/test/original_raw_linked.mp4') as container:
                frames=list(container.decode(video=0))
                self.assertAlmostEqual(float(frames[-1].pts*frames[-1].time_base),4.5)
            media=Path('outputs/test/original_raw_linked.mp4').read_bytes()
            self.assertLess(media.index(b'moov'),media.index(b'mdat'))
            self.assertFalse(summary['identity_verified'])
            self.assertTrue((Path('outputs/test')/'representatives').is_dir())

    def test_no_regions_still_links_but_no_events_claim(self):
        with tempfile.TemporaryDirectory() as directory,cwd(directory):
            cache,tp,src,w,z,c,t=fixture(Path(directory))
            with patch.object(runner,'REID_SHA',runner.sha256(w)):
                summary=runner.run(cache,tp,src,w,Path('outputs/test'),encoder_factory=lambda *a:Encoder(),decoder=decoder)
            self.assertEqual(summary['accepted_links'],1)
            self.assertEqual(summary['region_status'],'not_configured_no_event_claim')
            self.assertEqual(summary['candidates'],0)

    def test_features_reused_without_encoder_call(self):
        with tempfile.TemporaryDirectory() as directory,cwd(directory):
            cache,tp,src,w,z,c,t=fixture(Path(directory))
            with patch.object(runner,'REID_SHA',runner.sha256(w)):
                runner.run(cache,tp,src,w,Path('outputs/first'),encoder_factory=lambda *a:Encoder(),decoder=decoder)
                summary=runner.run(cache,tp,src,w,Path('outputs/second'),zones_path=z,
                                   features_path=Path('outputs/first/features.local.json'),
                                   encoder_factory=lambda *a:self.fail('must not load encoder'))
            self.assertEqual(summary['extraction']['encoder_calls'],0)
            self.assertTrue(summary['extraction']['reused'])
            self.assertEqual(summary['candidates'],1)

    def test_incomplete_reused_features_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as directory,cwd(directory):
            cache,tp,src,w,z,c,t=fixture(Path(directory))
            with patch.object(runner,'REID_SHA',runner.sha256(w)):
                runner.run(cache,tp,src,w,Path('outputs/first'),encoder_factory=lambda *a:Encoder(),decoder=decoder)
                fp=Path('outputs/first/features.local.json')
                original=json.loads(fp.read_text())
                for damage in ('missing_segment','extra_segment','missing_end','extra_end','count','dimension'):
                    record=json.loads(json.dumps(original));features=record['features']
                    sid=next(iter(features))
                    if damage=='missing_segment':del features[sid]
                    elif damage=='extra_segment':features['unrequested']=features[sid]
                    elif damage=='missing_end':del features[sid]['tail']
                    elif damage=='extra_end':features[sid]['extra']=features[sid]['head']
                    elif damage=='count':features[sid]['head'].pop()
                    elif damage=='dimension':features[sid]['head']=[[1.,0.,0.] for _ in features[sid]['head']]
                    damaged=Path('damaged.json');damaged.write_text(json.dumps(record))
                    with self.subTest(damage=damage),self.assertRaises(ValueError):
                        runner.run(cache,tp,src,w,Path('outputs/rejected'),features_path=damaged,
                                   encoder_factory=lambda *a:self.fail('must not infer'))
                    self.assertFalse(Path('outputs/rejected').exists())

    def test_encoder_receives_center_xywh(self):
        with tempfile.TemporaryDirectory() as directory:
            _,_,src,_,_,cached,tracked=fixture(Path(directory))
            encoder=Encoder()
            runner.encode_selected(src,cached,build_tracklets(tracked),LinkSettings(),encoder,decoder)
            self.assertTrue(encoder.calls)
            np.testing.assert_allclose(encoder.calls[0][0],[30.,24.,10.,32.])

    def test_output_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory,cwd(directory):
            Path('outputs/existing').mkdir(parents=True)
            with self.assertRaises(FileExistsError):
                runner.run('bad','bad','bad','bad',Path('outputs/existing'))

    def test_render_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);_,_,src,_,_,cached,tracked=fixture(root)
            output=root/'comparison.mp4';output.write_bytes(b'existing-media')
            with self.assertRaises(FileExistsError):
                runner.render_comparison(src,cached,tracked,[],{},[],output,decoder)
            self.assertEqual(output.read_bytes(),b'existing-media')

    def test_outside_outputs_rejected(self):
        with tempfile.TemporaryDirectory() as directory,cwd(directory):
            with self.assertRaises(FileExistsError):
                runner.run('bad','bad','bad','bad',Path('data/unsafe'))

    def test_measured_cache_mapping_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            cache,tp,src,w,z,c,t=fixture(Path(directory))
            t[0]['detections'][0]['bbox'][0]=.1
            tp.write_text(''.join(json.dumps(r)+'\n' for r in t))
            with self.assertRaisesRegex(ValueError,'measured'):
                runner.load_inputs(cache,tp,src)

    def test_wrong_timestamp_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            cache,tp,src,w,z,c,t=fixture(Path(directory))
            t[0]['native_pts']=3
            tp.write_text(''.join(json.dumps(r)+'\n' for r in t))
            with self.assertRaisesRegex(ValueError,'timing'):
                runner.load_inputs(cache,tp,src)

    def test_wrong_source_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            cache,tp,src,w,z,c,t=fixture(Path(directory))
            src.write_bytes(b'changed')
            with self.assertRaises(ValueError):runner.load_inputs(cache,tp,src)

    def test_invalid_encoder_output_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            cache,tp,src,w,z,c,t=fixture(Path(directory))
            with self.assertRaises(ValueError):
                runner.encode_selected(src,c,build_tracklets(t),LinkSettings(),lambda *a:[None],decoder)

    def test_zone_source_binding_checked(self):
        with tempfile.TemporaryDirectory() as directory,cwd(directory):
            cache,tp,src,w,z,c,t=fixture(Path(directory))
            zones=json.loads(z.read_text());zones['source_sha256']='wrong';z.write_text(json.dumps(zones))
            with patch.object(runner,'REID_SHA',runner.sha256(w)),self.assertRaisesRegex(ValueError,'Regions'):
                runner.run(cache,tp,src,w,Path('outputs/test'),zones_path=z)


if __name__=='__main__':unittest.main()
