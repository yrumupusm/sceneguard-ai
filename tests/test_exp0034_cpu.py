import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from sceneguard.exp0034_application import validate_scene_binding, enrich_timing
from sceneguard.exp0034_evidence import crop_bounds, measured_row, annotate, prepare_crops
from sceneguard.run_tracklet_linking import sha256


def scene():
    return dict(source_size=[100,100],line=[[.5,0],[.5,1]],approach_polygon=[[.1,.1],[.9,.1],[.9,.9],[.1,.9]],
        zones=dict(outside=[[0,0],[.4,0],[.4,1],[0,1]],inside=[[.6,0],[1,0],[1,1],[.6,1]]),
        directions=['outside_to_inside','inside_to_outside'],occlusions=[])


class CpuContractTests(unittest.TestCase):
    def test_scene_rejects_any_changed_user_polygon_roi_line_or_size(self):
        s=scene();camera=dict(legacy_boundary_config=dict(line=s['line'],roi=[.1,.1,.9,.9]))
        cache=[dict(source_size=[100,100])]
        validate_scene_binding(s,cache,s['zones'],camera)
        for field in ('line','approach_polygon','zones','source_size','directions'):
            changed=copy.deepcopy(s)
            if field=='zones':changed[field]['inside'][0][0]=.61
            elif field=='source_size':changed[field][0]=101
            elif field=='directions':changed[field]=['outside_to_inside']
            else:changed[field][0][0]+=.001
            with self.subTest(field=field),self.assertRaises(ValueError):validate_scene_binding(changed,cache,s['zones'],camera)

    def test_loss_wait_maps_to_first_available_native_frame_not_nearest(self):
        cached=[dict(pts=i/3,native_pts=i,time_base='1/3') for i in range(7)]
        result=dict(policy=dict(loss_wait=1),events=[dict(segment='s',pts=1.05,last_observed_pts=.05,reason='approach_to_known_occlusion_loss')],
            losses=[dict(last_pts=.05)],segments=[dict(id='s',rows=[dict(pts=0,frame_index=0,bbox=[.2,.2,.4,.6])])],pairs=[])
        enrich_timing(result,cached,scene())
        self.assertEqual(result['events'][0]['decision_time_pts'],4/3)
        self.assertEqual(result['losses'][0]['decision_time_pts'],4/3)
        self.assertEqual(result['events'][0]['available_after_pts'],2)

    def test_crop_uses_whole_bbox_floor_ceil_with_no_body_split(self):
        self.assertEqual(crop_bounds([.101,.201,.799,.899],[100,100]),[10,20,80,90])
        with self.assertRaises(ValueError):crop_bounds([.1,.1,.2,.9],[100,100])

    def test_no_crop_of_predicted_or_wrong_segment_frame(self):
        r=dict(segments=[dict(id='s1',raw_id=1,rows=[dict(frame_index=2)])])
        for sid,fi in [('s1',3),('s2',2)]:
            with self.assertRaises(ValueError):measured_row(r,sid,fi)

    def test_future_event_and_direction_do_not_leak_into_earlier_render(self):
        s=scene();frame=dict(pts=0,detections=[],states=[]);base=dict(segments=[],losses=[],events=[])
        future=copy.deepcopy(base)
        future['events']=[dict(decision_time_pts=5,status='침입 의심',raw_id=1,source_observed_pts=4)]
        future['losses']=[dict(last_pts=4,decision_time_pts=5,motion=dict(reliable=True,origin_pixels=[50,50],velocity_pixels_per_second=[2,0]))]
        original=Image.new('RGB',(100,100),'black')
        a=annotate(original,frame,base,s,0,True);b=annotate(original,frame,future,s,0,True)
        self.assertTrue(np.array_equal(np.asarray(a),np.asarray(b)))

    def test_native_crop_export_binds_decoded_frame_box_and_hash(self):
        import av
        with tempfile.TemporaryDirectory(dir='outputs') as directory:
            root=Path(directory);video=root/'synthetic.mp4'
            with av.open(str(video),'w') as container:
                stream=container.add_stream('libx264',rate=10);stream.width=100;stream.height=100;stream.pix_fmt='yuv420p'
                for i in range(4):
                    rgb=np.full((100,100,3),i*50,np.uint8);frame=av.VideoFrame.from_ndarray(rgb,format='rgb24')
                    frame.pts=i;frame.time_base=Fraction(1,10)
                    for packet in stream.encode(frame):container.mux(packet)
                for packet in stream.encode():container.mux(packet)
            with av.open(str(video)) as container:
                native=list(container.decode(video=0));cached=[dict(pts=float(f.pts*f.time_base),native_pts=f.pts,time_base=str(f.time_base),source_size=[100,100]) for f in native]
                expected=native[1].to_ndarray(format='rgb24')[20:80,10:90]
            rows=[dict(frame_index=i,pts=cached[i]['pts'],cache_index=0,bbox=[.1,.2,.9,.8]) for i in (1,3)]
            result=dict(video_id='E01_030',source_size=[100,100],pairs=[dict(pair_id='s1__s2',before='s1',after='s2')],segments=[dict(id='s1',raw_id=1,rows=[rows[0]]),dict(id='s2',raw_id=2,rows=[rows[1]])])
            data=dict(cached=cached,hashes=dict(video=sha256(video),tracks='f'*64));spec=dict(video=str(video),tracks='synthetic')
            selection=root/'selection.json';selection.write_text(json.dumps(dict(pairs=[dict(pair_id='E01_030:s1__s2',source_id='E01_030',before='s1',after='s2',before_frames=[1],after_frames=[3])])),encoding='utf-8')
            manifest=Path('runtime')/('test-exp0034-'+root.name+'.json')
            try:
                with patch('sceneguard.exp0034_evidence.bound_result',return_value=(result,spec,data,scene())):
                    prepare_crops(selection,[selection],root/'crops',manifest)
                exported=json.loads(manifest.read_text());meta=exported['pairs'][0]['before_images'][0]
                actual=np.load(meta['path'],allow_pickle=False)
                self.assertTrue(np.array_equal(expected,actual))
                self.assertEqual(meta['decoded_index'],1)
                self.assertEqual(meta['rgb_sha256'],hashlib.sha256(expected.tobytes()).hexdigest())
                self.assertEqual(meta['sha256'],sha256(meta['path']))
                self.assertNotIn('angle_degrees',json.dumps(exported))
                self.assertEqual(exported['candidate_pairs'][0]['pair_id'],'E01_030:s1__s2')
            finally:
                if manifest.exists():manifest.unlink()


class ApprovedAnalyzerCorrections(unittest.TestCase):
    @staticmethod
    def scene():
        return dict(source_size=[1000,500],line=[[.5,.1],[.5,.9]],approach_polygon=[[.2,.1],[.8,.1],[.8,.9],[.2,.9]],
            zones=dict(outside=[[0,0],[.48,0],[.48,1],[0,1]],inside=[[.52,0],[1,0],[1,1],[.52,1]]),
            directions=['outside_to_inside','inside_to_outside'],occlusions=[])

    @staticmethod
    def frame(i,x,y=.5,height=.2):
        return dict(pts=i*.1,detections=[dict(track_id=1,observed=True,confirmed=True,cache_index=0,
            bbox=[x-.02,y-height/2,x+.02,y+height/2])])

    def test_unestablished_side_exit_stays_unknown(self):
        from sceneguard.approach_disappearance import analyze
        result=analyze([self.frame(0,.5),self.frame(1,.5,.9)],self.scene())
        self.assertEqual(result['events'],[])

    def test_future_box_growth_cannot_rewrite_past_transition(self):
        from sceneguard.approach_disappearance import analyze
        base=[self.frame(i,x,.99,.01) for i,x in enumerate([.4]*4+[.6]*4)]
        extended=base+[self.frame(i,.6,.5,.8) for i in range(8,28)]
        s=self.scene();s['approach_polygon']=[[0,0],[1,0],[1,1],[0,1]]
        before=analyze(base,s)['events']
        after=[e for e in analyze(extended,s)['events'] if e['pts']<=.7+1e-9]
        self.assertEqual(before,after)
        self.assertEqual(before,[])

    def test_terminal_scale_jump_or_gap_invalidates_old_direction(self):
        from sceneguard.approach_disappearance import motion, Policy
        rows=[dict(pts=i*.1,bbox=[.2+i*.01,.4,.24+i*.01,.6]) for i in range(6)]
        self.assertTrue(motion(rows,(1000,500),Policy())['reliable'])
        for last in [dict(pts=.6,bbox=[.3,.2,.34,.8]),dict(pts=.9,bbox=[.3,.4,.34,.6])]:
            result=motion(rows+[last],(1000,500),Policy())
            self.assertFalse(result['reliable'])
            self.assertTrue(result['terminal_step_rejected'])


if __name__=='__main__':unittest.main()
