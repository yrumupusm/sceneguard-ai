import copy
from fractions import Fraction
import unittest
from sceneguard.exp0039_roi_gpu import crop_bounds,restore_box,person_rows
from orchestration.exp39_roi_command import schedule,SETTINGS

class GeometryTests(unittest.TestCase):
    def test_actual_integer_roi_bounds(self):
        self.assertEqual(crop_bounds([1920,1080],SETTINGS['roi']),[537,216,1440,864])

    def test_offset_once_no_double_resize(self):
        row=restore_box([10,20,110,220],[537,216,1440,864],[1920,1080])
        self.assertEqual(row['bbox_original_pixels'],[547,236,647,436])
        self.assertAlmostEqual(row['bbox_normalized'][0],547/1920)
        self.assertFalse(row['touches_crop_edge'])

    def test_model_postprocess_already_restores_internal_resize(self):
        # FCOS's min800 transform is internal. A returned 903x648 crop box
        # must not be multiplied by 648/800 or any padded-tensor scale again.
        row=restore_box([0,0,903,648],[537,216,1440,864],[1920,1080])
        self.assertEqual(row['bbox_original_pixels'],[537,216,1440,864])
        self.assertTrue(row['touches_crop_edge'])

    def test_outside_box_clamped_to_actual_crop_and_invalid_retained(self):
        row=restore_box([-20,-10,1000,700],[537,216,1440,864],[1920,1080])
        self.assertEqual(row['bbox_original_pixels'],[537,216,1440,864])
        self.assertFalse(restore_box([1000,700,1100,800],[537,216,1440,864],[1920,1080])['valid'])

    def test_all_model_person_rows_before_project_filters_no_extra_nms(self):
        p=dict(boxes=[[1,2,3,4]]*5,scores=[.2,.25,.5,.9,.99],labels=[1,1,1,1,2])
        before=copy.deepcopy(p);rows,views=person_rows(p,[537,216,1440,864],[1920,1080])
        self.assertEqual(len(rows),4)
        self.assertEqual(views,{'0.5':[2,3],'0.25':[1,2,3]})
        self.assertEqual(p,before)
        self.assertEqual(rows[0]['model_returned_crop_box'],[1,2,3,4])

    def test_nan_and_invalid_crop_rejected(self):
        with self.assertRaises(ValueError):restore_box([0,0,float('nan'),3],[0,0,4,4],[10,10])
        with self.assertRaises(ValueError):crop_bounds([1920,1080],[.3,.2,.1,.8])

    def test_schedule_selects_exact_86_original_native_frames(self):
        rows=[dict(pts=float(Fraction(1290240+i*512,15360)),native_pts=1290240+i*512,
                   time_base='1/15360',source_size=[1920,1080]) for i in range(480)]
        frozen=copy.deepcopy(rows);s=schedule(rows)
        self.assertEqual([len(w['rows']) for w in s],[43,43])
        self.assertEqual([w['rows'][0]['pts'] for w in s],[92.,97.83333333333333])
        self.assertEqual([w['rows'][-1]['pts'] for w in s],[93.4,99.23333333333333])
        self.assertEqual(rows,frozen)
        rows[240]['native_pts']+=1
        with self.assertRaises(ValueError):schedule(rows)

    def test_reusable_roi_comparison_decodes_as_two_short_clips(self):
        import json
        import tempfile
        import numpy as np
        from pathlib import Path
        from unittest.mock import patch
        from sceneguard import exp0039_roi_gpu as runner
        from orchestration.vlm_command import file_hash
        cached=[dict(pts=float(Fraction(1290240+i*512,15360)),native_pts=1290240+i*512,
            time_base='1/15360',source_size=[1920,1080],boxes=[],scores=[]) for i in range(480)]
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);cache=root/'cache';cache.mkdir();result=root/'result';result.mkdir()
            (cache/'person_cache.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in cached))
            (result/'summary.json').write_text(json.dumps(dict(status='succeeded',
                existing_fullframe_cache_sha256=file_hash(cache/'person_cache.jsonl'))))
            for window in schedule(cached):
                folder=result/window['segment'];folder.mkdir()
                rows=[dict(r,boxes=[],scores=[],model_returned_person_rows=[]) for r in window['rows']]
                (folder/'person_cache.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            image=np.zeros((1080,1920,3),dtype=np.uint8)
            with patch.object(runner,'CACHE',cache),patch('sceneguard.run_tracklet_linking.decode_native',
                side_effect=lambda source,rows:iter((i,image) for i,_ in enumerate(rows))):
                receipts=runner.render_comparisons(result,root/'comparison')
            self.assertEqual([r['frames'] for r in receipts],[43,43])
            self.assertEqual([r['first_pts'] for r in receipts],[0.,0.])
            self.assertTrue(all(abs(r['last_pts']-1.4)<1e-6 for r in receipts))

    def test_mock_inference_separates_ten_approved_warmups_and_86_samples(self):
        import json
        import tempfile
        import numpy as np
        from contextlib import nullcontext
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import patch
        from sceneguard.exp0039_roi_gpu import infer_windows
        rows=[dict(pts=float(Fraction(1290240+i*512,15360)),native_pts=1290240+i*512,
            time_base='1/15360',source_size=[1920,1080]) for i in range(480)]
        contract=dict(schedule=schedule(rows));decodes=[];calls=[]
        class Tensor:
            def permute(self,*a):return self
            def to(self,*a,**k):return self
            def __truediv__(self,x):return self
        def wrapped(value):return SimpleNamespace(detach=lambda:SimpleNamespace(cpu=lambda:SimpleNamespace(tolist=lambda:value)))
        def model(tensors):
            calls.append(1)
            return [dict(boxes=wrapped([[10,20,100,200]]),scores=wrapped([.8]),labels=wrapped([1]))]
        image=np.zeros((1080,1920,3),dtype=np.uint8)
        def decode(source,selected):
            decodes.append([r['native_pts'] for r in selected])
            return iter((i,image) for i,_ in enumerate(selected))
        torch=SimpleNamespace(float32='float32',from_numpy=lambda a:Tensor(),inference_mode=nullcontext,
            cuda=SimpleNamespace(synchronize=lambda:None,reset_peak_memory_stats=lambda:None,
                max_memory_allocated=lambda:0,max_memory_reserved=lambda:0))
        summary=dict(model_loads=1,warmup_attempts=0,warmup_calls=0,sample_attempts=0,sample_calls=0,windows=[],
            last_model_transform=dict(resized_hw=[[800,1114]],padded_nchw=[1,3,800,1120]))
        with tempfile.TemporaryDirectory() as temporary,patch('sceneguard.run_tracklet_linking.decode_native',side_effect=decode):
            folder=Path(temporary);infer_windows(model,torch,contract,folder,summary)
            self.assertEqual(len(calls),96)
            self.assertEqual(summary['sample_calls'],86);self.assertEqual(summary['warmup_calls'],10)
            self.assertEqual([len(d) for d in decodes],[10,43,43])
            self.assertEqual(decodes[0],decodes[1][:10])
            first=json.loads((folder/'s0003/person_cache.jsonl').read_text().splitlines()[0])
            self.assertEqual(first['boxes'],[[547,236,637,416]])
            self.assertEqual(first['input_geometry']['crop_size'],[903,648])
