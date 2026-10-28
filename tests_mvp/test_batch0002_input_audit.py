"""Synthetic CPU integrity tests; never load private media or a model."""
import copy
from fractions import Fraction
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from scripts import audit_batch0002_inputs as audit


def sample(start=0, roi=None):
    roi = roi or [0,0,1,1]
    source = dict(pts_seconds=[start+i/2 for i in range(10)],
                  native_pts=[round((start+i/2)*100) for i in range(10)],
                  time_base=['1/100']*10, source_size=[64,32], roi=roi,
                  window_start=start,window_end=start+5,fps=30)
    pixels = np.arange(10*32*64*3,dtype=np.uint8).reshape(10,32,64,3)
    source['rgb_sha256'] = audit.sha(pixels.tobytes())
    bounds = [round(roi[0]*64),round(roi[1]*32),round(roi[2]*64),round(roi[3]*32)]
    info = dict(source_pts=source['pts_seconds'], native_pts=source['native_pts'],
                time_base=source['time_base'],source_size=source['source_size'],roi=roi,
                window_start=start,window_end=start+5,observed_frames=10,processor_frames=10,
                extra_sampling=False,temporal_padding_frames=0,
                resized_shape=[10,3,32,32],crop_bounds_xyxy=bounds,
                cropped_shape=[10,bounds[3]-bounds[1],bounds[2]-bounds[0],3],
                crop_sha256=audit.sha(pixels[:,bounds[1]:bounds[3],bounds[0]:bounds[2]].tobytes()),
                video_grid_thw=[[5,2,2]],visual_tokens=5,input_tokens=9,
                processor_timestamp_coordinates=[i*15.0 for i in range(10)],
                processor_timestamp_quantization='official pair averaging then captions rounded to 0.1 seconds')
    return source, info, pixels


def collection_fixture(root):
    indexed, parents, jobs, sources = [], [], [], {}
    def put(name, value, index=False):
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(audit.encoded(value))
        if index:indexed.append(dict(path=str(path),sha256=audit.file_sha(path)))
        return path
    def variant(directory,start,sid,old=False):
        source,info,pixels=sample(start)
        source['source_sha256']=audit.sha(sid.encode())
        sources[sid]=source['source_sha256']
        inp=put(directory/'input.json',source,index=not old)
        result=put(directory/'result.json',dict(input_metadata=info,raw_response='NEVER PUBLISH'),index=not old)
        if not old:
            path=root/directory/'processor_rgb.npy';np.save(path,pixels[:,:,:32].copy(),allow_pickle=False)
            indexed.append(dict(path=str(path),sha256=audit.file_sha(path)))
        return dict(input_file_sha256=audit.file_sha(inp),result_file_sha256=audit.file_sha(result)),source
    for method,view in [('B','full_frame'),('C','fixed_roi')]:
        directory=Path('saved')/method
        jobs.append(dict(phase='prompt-regression',view=view,state='succeeded',output_path=str(root/directory)))
        for qid,sid,wid,start,end in audit.Q:
            old=Path('old')/method/sid/'windows'/wid
            provenance,source=variant(old,start,sid,True)
            variant(directory/sid/'windows'/wid,start,sid)
            label=dict(review_clip_id=qid,source_id=sid,window_id=wid,interval_seconds=[start,end],
                       reference_label='attempt' if qid=='q04' else 'no_attempt')
            parents.append(dict(method=method,user_label_revision=dict(user_label=label),provenance=provenance,
                                decoded_source_rgb_sha256=source['rgb_sha256']))
    vlabels=[];windows=[]
    for phase in ['independent-original','independent-revised']:
        directory=Path('saved')/phase
        jobs.append(dict(phase=phase,view='full_frame',state='succeeded',output_path=str(root/directory)))
        for i,(sid,start) in enumerate([('E01_004',60),('E01_004',0),('E01_021',65),('E01_021',0)],1):
            wid=f'w{i:06d}'
            _,source=variant(directory/'windows'/wid,start,sid)
            frame_hashes=['synthetic']*10
            path=root/directory/'windows'/wid/'input.json'
            source['frame_sha256']=frame_hashes
            path.write_bytes(audit.encoded(source))
            next(x for x in indexed if x['path']==str(path))['sha256']=audit.file_sha(path)
            if phase.endswith('original'):
                vlabels.append(dict(review_clip_id=f'v{i:02d}',window_id=wid,label='attempt' if i%2 else 'non_event'))
                windows.append(dict(window_id=wid,source_id=sid,timing=source,frame_sha256=frame_hashes))
    put(Path('records/EXP-0015/window_reviews.json'),parents)
    put(Path('configs/mvp_exp0016_independent_manifest.json'),dict(windows=windows))
    put(Path('configs/mvp_exp0016_independent_evaluation.json'),dict(labels=vlabels))
    put(Path('run.json'),dict(experiment='EXP-0017',state='completed',jobs=jobs),True)
    put(Path('index.json'),dict(files=indexed))
    return dict(pins={},saved_file_index='index.json',run_index='run.json',
                historical_q_roots={m:'old/'+m for m in ['B','C']})


class InputAuditTests(unittest.TestCase):
    def test_native_timing_and_unsampled_tail_are_distinct(self):
        source,_,_=sample(62.5);row=audit.timing(source)
        self.assertEqual(row['first_to_last_span_seconds'],4.5)
        self.assertEqual(row['last_to_end_seconds'],0.5)
        self.assertEqual(row['effective_sample_fps'],2)
        for field,value in [('native_pts',[1]*10),('time_base',['1/99']*10),('pts_seconds',[0]*10)]:
            bad=copy.deepcopy(source);bad[field]=value
            with self.assertRaises(ValueError):audit.timing(bad)

    def test_geometry_roi_and_tokens_do_not_become_semantic_evidence(self):
        source,info,_=sample(roi=[0.25,0.25,0.75,0.75])
        row=audit.geometry(source,info,(10,32,32,3))
        self.assertEqual(row['source_area_retained_fraction'],0.25)
        self.assertEqual(row['resize_xy_scale'],[1,2])
        self.assertIsNone(row['action_visible']);self.assertIsNone(row['person_size_pixels'])
        self.assertEqual(row['actual_input_human_review'],'not_performed')
        for field,value in [('visual_tokens',6),('crop_bounds_xyxy',[0,0,64,32]),
                            ('extra_sampling',True),('temporal_padding_frames',2),
                            ('processor_timestamp_coordinates',list(range(10)))]:
            bad=copy.deepcopy(info);bad[field]=value
            with self.assertRaises(ValueError):audit.geometry(source,bad,(10,32,32,3))

    def test_manual_rectangle_projection_is_clipped_and_explicitly_non_GT(self):
        row=audit.project_location([10,10,30,40],[100,100],[200,200],[40,40,100,100],[30,30])
        self.assertEqual(row['source_rectangle_wh'],[40,60])
        self.assertEqual(row['projected_visible_rectangle_wh'],[10,20])
        self.assertAlmostEqual(row['rectangle_area_retained_fraction'],1/3)
        self.assertIn('not GT',row['interpretation'])

    def test_source_and_crop_hashes_are_independent_bindings(self):
        source,info,pixels=sample()
        rgb={key:value for key,value in zip(zip(source['native_pts'],source['time_base']),pixels)}
        self.assertEqual(len(audit.verify_pixels(source,info,rgb)),10)
        bad=copy.deepcopy(info);bad['crop_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'crop differs'):audit.verify_pixels(source,bad,rgb)
        rgb[(0,'1/100')]=pixels[0].copy();rgb[(0,'1/100')][0,0,0]^=1
        with self.assertRaisesRegex(ValueError,'source RGB differs'):audit.verify_pixels(source,info,rgb)

    def test_v_per_frame_hashes_checked(self):
        source,info,pixels=sample();source.pop('rgb_sha256')
        source['frame_sha256']=[audit.sha(p.tobytes()) for p in pixels]
        rgb=dict(zip(zip(source['native_pts'],source['time_base']),pixels))
        audit.verify_pixels(source,info,rgb)
        source['frame_sha256'][4]='0'*64
        with self.assertRaisesRegex(ValueError,'frame RGB differs'):audit.verify_pixels(source,info,rgb)

    def test_collect_all20_variants_excludes_model_answer_and_records_old_gap(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);config=collection_fixture(root);reader=audit.Reader(root)
            rows,requests,hashes=audit.collect(reader,config)
            self.assertEqual(len(rows),20)
            self.assertEqual(sum(map(len,requests.values())),100)
            self.assertEqual(len(hashes),4)
            public=[r[0] for r in rows]
            self.assertNotIn('NEVER PUBLISH',audit.encoded(public).decode())
            self.assertEqual(sum(r['historical_q_processor_RGB']=='unavailable_not_saved' for r in public),12)
            reader.verify()

    def test_changed_saved_RGB_cannot_pass_index(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);config=collection_fixture(root)
            path=next(root.rglob('processor_rgb.npy'));path.write_bytes(path.read_bytes()+b'bad')
            with self.assertRaisesRegex(ValueError,'SHA mismatch'):audit.collect(audit.Reader(root),config)

    def test_changed_historical_visual_metadata_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);config=collection_fixture(root)
            path=root/'old/B/E01_007/windows/w000001/result.json'
            val=json.loads(path.read_bytes());val['input_metadata']['visual_tokens']=88
            path.write_bytes(audit.encoded(val))
            with self.assertRaisesRegex(ValueError,'SHA mismatch'):audit.collect(audit.Reader(root),config)

    def test_reader_rechecks_original_bytes_and_confinement(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'a').write_bytes(b'first');reader=audit.Reader(root);reader.bind('a')
            (root/'a').write_bytes(b'changed')
            with self.assertRaises(ValueError):reader.verify()
            with self.assertRaises(ValueError):reader.path('../escape')
            (root/'link').symlink_to(root/'a')
            with self.assertRaises(ValueError):reader.path('link')

    def test_output_preservation_and_links(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);audit.safe_write(root,'result.json',b'one')
            stamp=(root/'result.json').stat().st_mtime_ns
            audit.safe_write(root,'result.json',b'one')
            self.assertEqual(stamp,(root/'result.json').stat().st_mtime_ns)
            with self.assertRaises(ValueError):audit.safe_write(root,'result.json',b'two')
            with self.assertRaises(ValueError):audit.safe_write(root,'../escape',b'x')
            (root/'linked').symlink_to(root/'result.json')
            with self.assertRaises(ValueError):audit.safe_write(root,'linked',b'one')

    def test_strict_json(self):
        for raw in [b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":Infinity}']:
            with self.assertRaises(ValueError):audit.strict_json(raw)

    def test_freeze_rejects_working_tree_source_difference(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name in audit.CODE:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'frozen')
            with patch.object(audit.subprocess,'check_output',side_effect=['a'*40+'\n']+[b'frozen']*3):
                self.assertEqual(audit.freeze(root,'a'*40)[0],'a'*40)
            (root/audit.CODE[0]).write_bytes(b'changed')
            with patch.object(audit.subprocess,'check_output',side_effect=['a'*40+'\n',b'frozen']):
                with self.assertRaisesRegex(ValueError,'frozen commit'):audit.freeze(root,'a'*40)

    def test_synthetic_clip_retains_10_frames_and_5_second_display(self):
        import av
        with tempfile.TemporaryDirectory() as temp:
            source,info,pixels=sample();row=dict(review_id='q04',source_id='synthetic',condition='synthetic_actual')
            decoded={'synthetic':dict(zip(zip(source['native_pts'],source['time_base']),pixels))}
            path=Path(temp)/'synthetic.mp4'
            audit.render_review_clip(path,'q04',[(row,source,info,pixels[:,:,:32])],decoded)
            with av.open(str(path)) as container:
                frames=list(container.decode(video=0))
                self.assertEqual(len(frames),10)
                self.assertEqual([float(f.pts*f.time_base) for f in frames],[i/2 for i in range(10)])
                self.assertEqual(float(container.duration/av.time_base),5)

    def test_synthetic_decoder_converts_only_selected_native_PTS(self):
        import av
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'source.mp4'
            with av.open(str(path),'w') as container:
                stream=container.add_stream('libx264',rate=10);stream.width=64;stream.height=32;stream.pix_fmt='yuv420p'
                for i in range(10):
                    frame=av.VideoFrame.from_ndarray(np.full((32,64,3),i*20,dtype=np.uint8),format='rgb24')
                    for packet in stream.encode(frame):container.mux(packet)
                for packet in stream.encode():container.mux(packet)
            with av.open(str(path)) as container:
                frames=list(container.decode(video=0));wanted={(f.pts,str(f.time_base)) for f in [frames[2],frames[7]]}
            actual,inventory=audit.exact_frames(path,wanted)
            self.assertEqual(set(actual),wanted);self.assertEqual(len(inventory),2)
            self.assertTrue(all(row['decoded_frames_including_seek_preroll']>1 for row in inventory))


if __name__=='__main__':
    unittest.main()
