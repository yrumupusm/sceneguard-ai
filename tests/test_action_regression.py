"""CPU counterexamples for full-video advisory sampling, coverage, pixels and state."""
import copy
from fractions import Fraction
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

plan=load('prepare_action_regression');infer=load('infer_action_regression')


def fixture(n=80, rate=Fraction(30)):
    frames=[dict(native_pts=i,time_base=str(1/rate),pts=float(i/rate),
                 states=[dict(track_id=7,observed=True,bbox=[.3,.2,.4,.5])]) for i in range(n)]
    samples=plan.sample_grid(frames);windows,missing,counts=plan.plan_windows(samples,{'7'},32,24)
    row=dict(video_id='fixture',width=32,height=24,samples=samples,windows=windows,
             counts=counts,source_sha256='fixture-source',tracking_path='/fixture',input_hashes={'/fixture':'tracking'},
             native_frames=n,first_pts=0.,last_pts=frames[-1]['pts'],duration_seconds=float(n/rate))
    return frames,row,missing


class ActionRegressionTests(unittest.TestCase):
    def test_2997_uses_global_nearest_actual_pts_no_synthetic_3fps(self):
        frames,row,_=fixture(301,Fraction(30000,1001))
        samples=row['samples']
        self.assertEqual(samples[0]['pts'],0)
        self.assertAlmostEqual(samples[1]['target_pts'],1/3)
        self.assertAlmostEqual(samples[1]['pts'],1001/3000)
        for s in samples:
            distances=[abs(f['pts']-s['target_pts']) for f in frames]
            self.assertAlmostEqual(distances[s['frame_index']],min(distances))
        self.assertEqual(row['windows'][0]['available_after_pts'],samples[7]['pts'])
        self.assertGreater(samples[7]['pts'],samples[7]['target_pts'])
        self.assertEqual([w['start_target_index'] for w in row['windows']],list(range(0,len(samples)-7,3)))

    def test_earlier_tie_and_invalid_or_incomplete_pts(self):
        frames,_,_=fixture(31)
        frames[10]['native_pts']=9
        with self.assertRaisesRegex(ValueError,'strictly'):plan.sample_grid(frames)
        with self.assertRaises(ValueError):plan.sample_grid([])
        frames,_,_=fixture(31);frames[0]['native_pts']=1
        with self.assertRaises(ValueError):plan.sample_grid(frames)

    def test_predicted_box_cannot_fill_missing_observation_or_switch_id(self):
        frames,row,_=fixture(140)
        selected=row['samples'][4]['frame_index']
        frames[selected]['states'][0]['observed']=False
        frames[selected]['states'].append(dict(track_id=8,observed=True,bbox=[.3,.2,.4,.5]))
        samples=plan.sample_grid(frames)
        windows,missing,counts=plan.plan_windows(samples,{'7','8'},32,24)
        self.assertFalse(any(w['track_id']=='7' and w['start_target_index']==0 for w in windows))
        self.assertTrue(any(m['track_id']=='7' and 4 in m['missing_target_indices'] for m in missing))
        self.assertEqual(counts['track_window_denominator'],2*counts['global_windows'])
        self.assertEqual(counts['eligible_windows']+counts['missing_observation_windows'],counts['track_window_denominator'])
        self.assertEqual(counts['partial_observations_windows']+counts['no_observations_windows'],counts['missing_observation_windows'])
        self.assertEqual(counts['observation_sample_denominator'],8*counts['track_window_denominator'])
        self.assertEqual(counts['active_observation_window_denominator'],counts['eligible_windows']+counts['partial_observations_windows'])
        self.assertEqual(counts['insufficient_active_observation_windows'],counts['partial_observations_windows'])

    def test_first_observation_does_not_reanchor_window_or_use_later_boxes(self):
        frames,row,_=fixture(140)
        for f in frames[:40]:f['states']=[]
        samples=plan.sample_grid(frames);windows,_,_=plan.plan_windows(samples,{'7'},32,24)
        self.assertTrue(all(w['start_target_index']%3==0 for w in windows))
        for w in windows:
            self.assertEqual(w['roi_xyxy'],plan.roi([s['observed']['7'] for s in samples[w['start_target_index']:w['end_target_index']+1]],32,24))
        windows0=copy.deepcopy(windows)
        frames[-1]['states'][0]['bbox']=[0,0,1,1]
        changed,_,_=plan.plan_windows(plan.sample_grid(frames),{'7'},32,24)
        self.assertEqual(windows0,changed)

    def test_roi_geometric_union_clamp_matches_training_builder(self):
        builder=load('build_action_training_clips')
        boxes=[[.2,.3,.3,.5],[.25,.4,.5,.6]];w,h=1000,500
        annotations=[dict(bbox=[[b[0]*w,b[1]*h],[b[2]*w,b[3]*h]]) for b in boxes]
        self.assertEqual(plan.roi(boxes,w,h),builder.contextual_roi(annotations,w,h)[0])
        self.assertEqual(plan.roi([[0,0,1,1]],100,60),[0,0,100,60])
        for bad in ([0,0,0,.5],[0,0,float('nan'),1],[-.1,0,.5,1]):
            with self.assertRaises(ValueError):plan.roi([bad],100,60)

    def test_streaming_once_ring8_batch4_score_semantics_and_no_future_pixels(self):
        import numpy as np
        frames,row,_=fixture(400);seen=[];scored=[];emitted=[]
        def decode():
            for i,f in enumerate(frames):
                seen.append(i);yield f['pts'],np.full((24,32,3),i%255,dtype=np.uint8)
        def score(arrays):
            self.assertLessEqual(len(arrays),4)
            self.assertTrue(all(a.shape==(8,112,112,3) for a in arrays))
            scored.append(len(arrays));return [.5]*len(arrays)
        def sink(record):
            self.assertLessEqual(record['sample_frame_indices'][-1],seen[-1]);emitted.append(record)
        report=infer.process_video(row,decode(),score,sink,[])
        self.assertEqual(len(seen),len(frames));self.assertEqual(report['decoded_native_frames'],400)
        self.assertEqual(report['candidate_windows'],len(row['windows']))
        self.assertEqual(report['scored_windows'],sum(scored));self.assertLessEqual(report['peak_sampled_frame_buffer'],8)
        self.assertLessEqual(report['peak_clip_batch'],4)
        self.assertTrue(all(r['action']=='climbing_action_candidate' and not r['baseline_state_modified'] for r in emitted))
        self.assertIsNone(report['precision']);self.assertIsNone(report['human_confirmed_detector_false_negatives'])
        for r in emitted:
            self.assertEqual(r['available_after_pts'],r['sample_pts'][-1])
            self.assertGreaterEqual(r['batch_flushed_at_source_pts'],r['available_after_pts'])
        self.assertTrue(any(r['batch_flushed_at_source_pts']>r['available_after_pts'] for r in emitted))
        self.assertEqual(emitted[-1]['batch_flushed_at_source_pts'],row['last_pts'])

    def test_incomplete_decode_and_nonfinite_scores_fail(self):
        import numpy as np
        frames,row,_=fixture()
        pixels=lambda fs:((f['pts'],np.zeros((24,32,3),dtype=np.uint8)) for f in fs)
        with self.assertRaisesRegex(ValueError,'coverage'):infer.process_video(row,pixels(frames[:-1]),lambda xs:[.1]*len(xs),lambda r:None,[])
        with self.assertRaisesRegex(ValueError,'score'):infer.process_video(row,pixels(frames),lambda xs:[float('nan')]*len(xs),lambda r:None,[])

    def test_letterbox_matches_trainer_decode_pixels(self):
        import av
        import numpy as np
        trainer=load('train_action_recognizer')
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'fixture.mp4'
            with av.open(str(p),'w') as container:
                stream=container.add_stream('libx264',rate=3);stream.width=32;stream.height=24;stream.pix_fmt='yuv420p'
                for i in range(8):
                    f=av.VideoFrame.from_ndarray(np.full((24,32,3),i*20,dtype=np.uint8),format='rgb24')
                    for packet in stream.encode(f):container.mux(packet)
                for packet in stream.encode():container.mux(packet)
            row=dict(source_path=str(p),sample_pts=[i/3 for i in range(8)],roi_xyxy=[3,2,26,21])
            expected=trainer.decode_clip(row,112)
            with av.open(str(p)) as container:actual=np.stack([infer.letterbox(f.to_ndarray(format='rgb24'),row['roi_xyxy']) for f in container.decode(video=0)])
            np.testing.assert_array_equal(actual,expected)

    def test_all_baseline_bytes_preserved_even_future_states_and_no_input_mutation(self):
        with tempfile.TemporaryDirectory() as t:
            folder=Path(t);source=folder/'cards.json';output=folder/'out';output.mkdir()
            source.write_bytes(b'{"status":"confirmed", "first_notice":1, "confirm":2,"release":null}\n')
            original=source.read_bytes();row=dict(baseline_hashes={str(source):plan.sha(source)})
            copied=infer.preserve_baseline(row,output,plan)
            self.assertEqual(source.read_bytes(),original)
            self.assertEqual((output/'baseline/cards.json').read_bytes(),original)
            self.assertEqual(len(copied),1)
        cards=[dict(incident_id='current',first_notification_pts=1,observation_closed_pts=4,status='confirmed'),
               dict(incident_id='future',first_notification_pts=5,observation_closed_pts=None)]
        before=copy.deepcopy(cards)
        relation=infer.card_relations(dict(sample_pts=[2,3]),cards,10)
        self.assertEqual([r['incident_id'] for r in relation],['current']);self.assertEqual(cards,before)
        self.assertNotIn('status',relation[0])

    def test_native_decode_matches_tracking_every_pts_and_reads_eof(self):
        import av
        import numpy as np
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'native.mp4';tracking=Path(t)/'frames.jsonl'
            with av.open(str(p),'w') as c:
                s=c.add_stream('libx264',rate=Fraction(30000,1001));s.width=32;s.height=24;s.pix_fmt='yuv420p'
                for i in range(31):
                    f=av.VideoFrame.from_ndarray(np.zeros((24,32,3),dtype=np.uint8),format='rgb24')
                    for packet in s.encode(f):c.mux(packet)
                for packet in s.encode():c.mux(packet)
            with av.open(str(p)) as c:records=[dict(native_pts=f.pts,time_base=str(f.time_base)) for f in c.decode(video=0)]
            tracking.write_text(''.join(json.dumps(r)+'\n' for r in records))
            row=dict(source_path=str(p),tracking_path=str(tracking));self.assertEqual(len(list(infer.native_frames(row))),31)
            records[4]['native_pts']+=1;tracking.write_text(''.join(json.dumps(r)+'\n' for r in records))
            with self.assertRaisesRegex(ValueError,'PTS'):list(infer.native_frames(row))


if __name__=='__main__':unittest.main()
