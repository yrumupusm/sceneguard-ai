# SPDX-License-Identifier: AGPL-3.0-only
"""CPU-only fixed ROI/Results/queue contracts; no model construction or weights."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from batch05_pose import geometry
from batch06_pose import runner
from batch04_pose.api import bgr_source
from batch06_pose.api import official_audit
from orchestration import batch06_pose_command as command
from orchestration.queue import Queue


class RoiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise RuntimeError('hide CUDA for CPU tests')
        import numpy as np
        import torch
        from ultralytics.engine.results import Results
        cls.np,cls.torch,cls.Results=np,torch,Results

    def native(self,n=1,full=False):
        shape=(1080,1920,3) if full else (648,903,3)
        boxes=self.torch.tensor([[0,0,903,648,.8,0]]*n).reshape(n,6)
        joints=self.torch.tensor([[[10,20,.8]]*17]*n).reshape(n,17,3)
        return self.Results(self.np.zeros(shape,self.np.uint8),path='synthetic',names={0:'person'},boxes=boxes,keypoints=joints)

    def test_crop_floor_ceil_color_and_original_immutable(self):
        rgb=self.np.zeros((1080,1920,3),self.np.uint8)
        rgb[216,537]=[12,34,56];rgb[863,1439]=[1,2,3]
        c=geometry.crop(rgb);bgr=bgr_source(c)
        self.assertEqual(geometry.bounds(rgb.shape,geometry.ROI),geometry.PIXELS)
        self.assertEqual(c.shape,(648,903,3));self.assertEqual(bgr[0,0].tolist(),[56,34,12])
        self.assertEqual(c[-1,-1].tolist(),[1,2,3]);self.assertTrue(bgr.flags.c_contiguous)
        self.assertEqual(rgb[216,537].tolist(),[12,34,56])
        for roi in ([0,0,0,1],[-1,0,1,1],[0,0,float('nan'),1],[0,0,2,1]):
            with self.assertRaises(ValueError):geometry.bounds(rgb.shape,roi)
        with self.assertRaises(ValueError):geometry.crop(rgb[:100])

    def test_offset_once_unknown_sentinel_low_conf_outside_and_boundaries(self):
        r=self.native()
        r.keypoints.data[0,:5]=self.torch.tensor([[0,0,.99],[10,20,.49],[904,10,.9],[903,648,.8],[0,20,.8]])
        p=geometry.rows(r,(648,903,3),'C6')
        self.assertEqual(p['offset_applications'],1)
        self.assertEqual(p['persons'][0]['xyxy'],[537,216,1440,864])
        self.assertEqual(p['local_persons'][0]['xyxy'],[0,0,903,648])
        kp=p['persons'][0]['keypoints']
        self.assertTrue(all(kp[i]['observed_xy'] is None for i in range(3)))
        self.assertEqual(kp[0]['raw_xy'],[537,216]);self.assertEqual(kp[3]['observed_xy'],[1440,864])
        self.assertEqual(kp[4]['observed_xy'],[537,236])
        self.assertEqual(r.boxes.data[0,0].item(),0)

    def test_full_results_unchanged_and_empty_both_views(self):
        d=geometry.rows(self.native(full=True),(1080,1920,3),'full')
        self.assertEqual(d['local_persons'],d['persons']);self.assertEqual(d['offset_applications'],0)
        for full,view,shape in [(True,'full',(1080,1920,3)),(False,'C6',(648,903,3))]:
            self.assertEqual(geometry.rows(self.native(0,full),shape,view)['persons'],[])

    def test_malformed_nonfinite_shape_class_conf_rejected(self):
        for field in ('none','mismatch','nan','class','confidence','shape'):
            r=self.native()
            if field=='none':r.keypoints=None
            if field=='mismatch':r.keypoints.data=self.torch.zeros((0,17,3))
            if field=='nan':r.keypoints.data[0,0,0]=float('nan')
            if field=='class':r.boxes.data[0,5]=1
            if field=='confidence':r.boxes.data[0,4]=.25
            if field=='shape':r.orig_shape=(10,10)
            with self.assertRaises(ValueError):geometry.rows(r,(648,903,3),'C6')

    def test_native_pts_cache_crop_hash_and_disjoint_exact_three(self):
        d=command.manifest();inp=command.input_contract()
        self.assertEqual(inp['conditions'],list(command.CONDITIONS));self.assertEqual(len(set(inp['conditions'])),3)
        self.assertNotIn('030_090_full',inp['conditions']);self.assertEqual(inp['conditions'][0],'030_090_C6_960')
        self.assertEqual([f['pts_seconds'] for f in d['frames']],[84,90,94])
        self.assertEqual([command.cached_records(d)[f'030_{t:03}']['person_count'] for t in (84,90,94)],[3,1,0])
        changed=json.loads(json.dumps(d));changed['cached_summary_sha256']='0'*64
        with self.assertRaises(ValueError):command.cached_records(changed)
        with patch.object(command,'manifest',return_value={**d,'crop_bytes_sha256':{f['frame_id']:'0'*64 for f in d['frames']}}):
            with self.assertRaisesRegex(ValueError,'crop RGB hash'):command.input_contract()
        self.assertFalse(self.torch.cuda.is_initialized())

    def test_public_signatures_and_same_kwargs_no_model(self):
        a=official_audit();self.assertEqual(a['kwargs'],command.PREDICT_KWARGS)
        self.assertEqual(a['model_constructions'],0);self.assertFalse(a['cuda_initialized'])

    def test_lease_gate_before_model_import(self):
        p=subprocess.run([sys.executable,'-I',str(command.ROOT/'batch06_pose/runner.py'),'--stage','comparison','--attempt','a'*32,'--lock-fd','999999'],capture_output=True,text=True)
        self.assertNotEqual(p.returncode,0);self.assertIn('Bad file descriptor',p.stderr)
        self.assertNotIn('import torch',p.stderr)
        with patch('batch04_pose.runner.subprocess.check_output',return_value='4000,6143'):
            with self.assertRaises(ValueError):runner.resources()

    def test_no_retry_no_regeneration_and_exact_queue_identity(self):
        with self.assertRaises(ValueError):command.retry_guard(None,{})
        class DB:
            def __init__(self,rows):self.rows=rows
            def execute(self,*a):return SimpleNamespace(fetchall=lambda:self.rows)
        row=(command.job_key('comparison'),*command.IDENTITY,'a'*32,1)
        job={'job_key':row[0]}
        command.execution_guard(DB([row]),job,'a'*32)
        for rows in ([(*row[:-1],2)],[row,row],[(row[0],*row[1:3],'wrong',*row[4:])]):
            with self.assertRaises(ValueError):command.execution_guard(DB(rows),job,'a'*32)
        with tempfile.TemporaryDirectory() as t,patch.object(command,'ROOT',Path(t)):
            base=Path(t)/'outputs/batch0006/EXP-0025/comparison/first';base.mkdir(parents=True)
            command.ensure_unprocessed(command.CONDITIONS[0])
            (base/(command.CONDITIONS[0]+'-predict-started.json')).write_text('{}')
            with self.assertRaises(ValueError):command.ensure_unprocessed(command.CONDITIONS[0])
        with self.assertRaises(ValueError):command.ensure_unprocessed('030_090_full')

    def test_additive_queue_migration_preserves_rows(self):
        with tempfile.TemporaryDirectory() as t:
            q=Queue.initialize(t);q.enqueue(job_key='old',run_id='r',task_id='t',dispatch_id='d',owner='cpu');q.supervise_once()
            q.migrate_commands(include_vlm_batch02=True);q.migrate_commands(include_pose=True);q.migrate_commands(include_public_pose=True)
            before=q.status();q.migrate_commands(include_roi_pose=True);q.migrate_commands(include_resolution_pose=True);self.assertEqual(before,q.status())
            q.migrate_commands(include_resolution_pose=True)
            self.assertEqual(len(list(Path(t).glob('queue-before-batch06-pose-*.sqlite3'))),1)
            with q.connection() as db:self.assertFalse(list(db.execute('PRAGMA foreign_key_check')))

    def test_only_imgsz_diff_no_alias_and_actual960_observer_guard(self):
        from batch06_pose.observer import ObserveOfficial
        from orchestration.batch04_pose_command import PREDICT_KWARGS as old
        self.assertEqual([k for k in old if old[k]!=command.PREDICT_KWARGS[k]],['imgsz'])
        self.assertEqual(old['imgsz'],640)
        self.assertIsNot(old['classes'],command.PREDICT_KWARGS['classes'])
        class Tensor:
            device='cuda:0'
            def __init__(self,array):self.array=array
            def detach(self):return self
            def cpu(self):return self
            def numpy(self):return self.array
        fake_torch=SimpleNamespace(cuda=SimpleNamespace(synchronize=lambda:None))
        with tempfile.TemporaryDirectory(dir=command.ROOT/'runtime') as t:
            for size in (960,640):
                observer=ObserveOfficial(fake_torch,Path(t),'synthetic',None)
                code=next(c for c,name in observer.codes.items() if name=='preprocess')
                frame=SimpleNamespace(f_code=code)
                observer.profile(frame,'call',None)
                tensor=Tensor(self.np.zeros((1,3,size,size),self.np.float32))
                if size==960:
                    observer.profile(frame,'return',tensor)
                    self.assertEqual(observer.tensor['shape'],[1,3,960,960])
                else:
                    with self.assertRaisesRegex(ValueError,'960'):observer.profile(frame,'return',tensor)
        self.assertFalse(self.torch.cuda.is_initialized())

    def test_all_rows_scores_and_local_triptychs(self):
        from batch06_pose.visuals import comparison_images
        parsed=geometry.rows(self.native(3),(648,903,3),'C6')
        record=dict(parsed,frame_id='synthetic',person_count=3)
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);self.np.save(root/'rgb.npy',self.np.zeros((1080,1920,3),self.np.uint8))
            manifest={'frames':[dict(frame_id='synthetic',rgb_path='rgb.npy',native_pts=90,time_base='1/1',pts_seconds=90)]}
            with patch('batch06_pose.visuals.ROOT',root),patch('batch06_pose.visuals.cached_records',return_value={'synthetic':record}):
                artifacts=comparison_images(manifest,[record],root)
            import cv2
            image=cv2.imread(str(root/artifacts['synthetic']['path']))
            self.assertEqual(image.shape,(1344,5760,3))
            self.assertEqual(len(record['persons']),3)


if __name__=='__main__':unittest.main()
