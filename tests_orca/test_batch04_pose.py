# SPDX-License-Identifier: AGPL-3.0-only
"""CPU-only public API regressions, actual Results contracts and queue isolation."""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from orchestration import batch04_pose_command as command
from orchestration.queue import Queue
from batch04_pose import api, runner


class PublicPoseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
            raise RuntimeError('CPU preflight requires CUDA_VISIBLE_DEVICES empty')
        import numpy as np
        import torch
        from ultralytics.engine.results import Results
        cls.np, cls.torch, cls.Results = np, torch, Results

    def native(self, n=1):
        boxes = self.torch.tensor([[100,50,500,400,.8,0]]*n).reshape(n,6)
        kp = self.torch.tensor([[[200,100,.8]]*17]*n).reshape(n,17,3)
        return self.Results(self.np.zeros((480,960,3),self.np.uint8),path='synthetic',names={0:'person'},boxes=boxes,keypoints=kp)

    def test_complete_installed_config_and_signatures(self):
        d = api.official_audit()
        self.assertFalse(d['cuda_initialized'])
        self.assertEqual(d['model_constructions'],0)
        self.assertEqual(d['kwargs'],command.PREDICT_KWARGS)
        self.assertIn('visualize',d['regression'])
        self.assertEqual(len(d['signatures']),11)

    def test_rgb_bgr_roundtrip_and_external_source_rejection(self):
        rgb = self.np.array([[[12,34,56],[1,2,3]]],dtype=self.np.uint8)
        bgr = api.bgr_source(rgb)
        self.assertTrue(bgr.flags.c_contiguous)
        self.assertEqual(bgr.tolist(),[[[56,34,12],[3,2,1]]])
        self.assertEqual(rgb.tolist(),[[[12,34,56],[1,2,3]]])
        for invalid in ('https://invalid/image.jpg',None,[rgb],rgb.astype('float32'),rgb[:,:,0]):
            with self.assertRaises(ValueError): api.bgr_source(invalid)

    def test_official_preprocess_rgb_and_square_tensor_without_model(self):
        from ultralytics.engine.predictor import BasePredictor
        # No __init__/YOLO/weights; run only installed official CPU preprocessing.
        predictor = BasePredictor.__new__(BasePredictor)
        predictor.imgsz = [640,640]
        predictor.args = SimpleNamespace(rect=False)
        predictor.device = self.torch.device('cpu')
        predictor.model = SimpleNamespace(fp16=False,stride=32,format='pt')
        rgb = self.np.zeros((320,640,3),dtype=self.np.uint8)
        rgb[:,:,:] = [12,34,56]
        tensor = predictor.preprocess([api.bgr_source(rgb)])
        self.assertEqual(list(tensor.shape),[1,3,640,640])
        self.assertEqual(tensor.dtype,self.torch.float32)
        self.assertTrue(self.torch.allclose(tensor[0,:,320,320],self.torch.tensor([12,34,56])/255))
        self.assertTrue(self.torch.allclose(tensor[0,:,0,0],self.torch.tensor([114,114,114])/255))

    def test_native_results_preserve_original_coordinates_no_scaling(self):
        r = self.native()
        p = api.result_rows(r,(480,960,3))[0]
        self.assertEqual(p['xyxy'],[100,50,500,400])
        self.assertEqual(p['keypoints'][0]['observed_xy'],[200,100])
        self.assertIn('not track',p['correspondence'])
        self.assertEqual(len(p['keypoints']),17)

    def test_zero_people_is_valid_results(self):
        self.assertEqual(api.result_rows(self.native(0),(480,960,3)),[])

    def test_missing_mismatched_or_bad_shape_results_rejected(self):
        r = self.native(); r.keypoints = None
        with self.assertRaises(ValueError): api.result_rows(r,(480,960,3))
        r = self.native(); r.keypoints.data = self.torch.zeros(0,17,3)
        with self.assertRaises(ValueError): api.result_rows(r,(480,960,3))
        r = self.native(); r.keypoints.data = self.torch.zeros(1,16,3)
        with self.assertRaises(ValueError): api.result_rows(r,(480,960,3))
        with self.assertRaises(ValueError): api.result_rows(self.native(),(640,640,3))

    def test_nonfinite_class_box_confidence_rejected(self):
        for where,value in [('box',float('nan')),('joint',float('inf')),('class',1),('conf',.25),('range',961)]:
            r = self.native()
            if where == 'box': r.boxes.data[0,0] = value
            if where == 'joint': r.keypoints.data[0,0,0] = value
            if where == 'class': r.boxes.data[0,5] = value
            if where == 'conf': r.boxes.data[0,4] = value
            if where == 'range': r.boxes.data[0,2] = value
            with self.assertRaises(ValueError): api.result_rows(r,(480,960,3))

    def test_unknown_low_zero_outside_joint_preserves_raw(self):
        r = self.native()
        r.keypoints.data[0,0] = self.torch.tensor([0,0,.99])
        r.keypoints.data[0,1] = self.torch.tensor([20,30,.499])
        r.keypoints.data[0,2] = self.torch.tensor([1000,30,.8])
        r.keypoints.data[0,3] = self.torch.tensor([20,30,.5])
        p = api.result_rows(r,(480,960,3))[0]
        self.assertTrue(all(p['keypoints'][i]['observed_xy'] is None for i in range(3)))
        self.assertEqual(p['keypoints'][2]['raw_xy'],[1000,30])
        self.assertEqual(p['keypoints'][3]['observed_xy'],[20,30])

    def test_no_private_forward_or_rescale_in_new_path(self):
        path = command.ROOT/'batch04_pose/runner.py'
        tree = ast.parse(path.read_text())
        calls = [n for n in ast.walk(tree) if isinstance(n,ast.Call)]
        self.assertFalse(any(isinstance(n.func,ast.Name) and n.func.id in ('inner','non_max_suppression','LetterBox') for n in calls))
        self.assertFalse(any(isinstance(n.func,ast.Attribute) and n.func.attr in ('set_head_attr','scale_boxes','scale_coords','forward','fuse') for n in calls))
        predicts = [n for n in calls if isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=='model' and n.func.attr=='predict']
        self.assertEqual(len(predicts),1)
        self.assertEqual([k.arg for k in predicts[0].keywords],['source',None])

    def test_canonical_lease_before_torch_import(self):
        p = subprocess.run([sys.executable,'-I',str(command.ROOT/'batch04_pose/runner.py'),
            '--stage','smoke','--attempt','a'*32,'--lock-fd','999999'],capture_output=True,text=True)
        self.assertNotEqual(p.returncode,0)
        self.assertIn('Bad file descriptor',p.stderr)
        self.assertNotIn('import torch',p.stderr)

    def test_resource_gate_unchanged(self):
        with patch.object(runner.subprocess,'check_output',return_value='4000,6143'):
            with self.assertRaisesRegex(ValueError,'no model loaded'): runner.resources()
        with patch.object(runner.subprocess,'check_output',return_value='4000,6144'):
            self.assertEqual(runner.resources()['free_mib'],6144)

    def test_no_retry_and_no_unreviewed_remaining(self):
        with self.assertRaisesRegex(ValueError,'CPU correction'): command.retry_guard(None,{})
        config = dict(stage='remaining',settings=command.SETTINGS)
        with patch.object(command,'input_contract',return_value={}),patch.object(command,'validate_assignment',return_value={'allowed_stages':['smoke']}):
            with self.assertRaisesRegex(ValueError,'authorization'): command.validate(config,{},command.RUNTIME)
        with patch.object(command,'input_contract',return_value={}),patch.object(command,'validate_assignment',return_value={'allowed_stages':['remaining']}),patch.object(command,'successful_smoke',return_value=('a'*32,'hash')):
            with self.assertRaisesRegex(ValueError,'usefulness'): command.validate(config,{},command.RUNTIME)

    def test_additive_queue_migration_and_historical_rows_preserved(self):
        with tempfile.TemporaryDirectory() as t:
            q = Queue.initialize(t)
            q.enqueue(job_key='old',run_id='r',task_id='t',dispatch_id='d',owner='cpu')
            q.supervise_once()
            q.migrate_commands(include_vlm_batch02=True)
            q.migrate_commands(include_pose=True)
            before = q.status()
            q.migrate_commands(include_public_pose=True)
            self.assertEqual(before,q.status())
            q.migrate_commands(include_public_pose=True)
            self.assertEqual(len(list(Path(t).glob('queue-before-batch04-pose-*.sqlite3'))),1)
            with q.connection() as db:
                self.assertFalse(list(db.execute('PRAGMA foreign_key_check')))

    def test_profiler_unwraps_decorators_and_distinguishes_failed_returns(self):
        import functools
        import inspect
        from ultralytics.engine.predictor import BasePredictor
        def wrapped(fn):
            @functools.wraps(fn)
            def shared(*args,**kwargs):
                return fn(*args,**kwargs)
            return shared
        @wrapped
        def network(fail=False):
            if fail:
                raise ValueError('synthetic error')
            return 'synthetic result'
        @wrapped
        def warmup():
            return network()
        @wrapped
        def unrelated():
            return None
        fake_torch = SimpleNamespace(cuda=SimpleNamespace(synchronize=lambda:None))
        with tempfile.TemporaryDirectory() as t:
            observer = runner.ObserveOfficial(fake_torch,Path(t),'synthetic',None)
            self.assertIn(inspect.unwrap(BasePredictor.setup_model).__code__,observer.codes)
            if hasattr(BasePredictor.setup_model,'__wrapped__'):
                self.assertNotIn(BasePredictor.setup_model.__code__,observer.codes)
            observer.codes = {inspect.unwrap(network).__code__:'network_predict',inspect.unwrap(warmup).__code__:'warmup'}
            with observer:
                unrelated()
                warmup()
                network()
                try:
                    network(fail=True)
                except ValueError:
                    pass
            calls = [e for e in observer.attempts if e['stage']=='network_predict']
            returned = [e for e in observer.events if e['stage']=='network_predict' and e['returned_value']]
            self.assertEqual(len(calls),3)
            self.assertEqual(len(returned),2)
            self.assertEqual(sum(e['warmup'] for e in returned),1)
            self.assertEqual(observer.starts,{})
            self.assertIsNone(sys.getprofile())

    def test_execution_budget_and_success_regeneration_guards(self):
        class DB:
            def __init__(self,rows): self.rows=rows
            def execute(self,*args): return SimpleNamespace(fetchall=lambda:self.rows)
        job = {'config_json':json.dumps({'stage':'smoke'}),'job_key':command.job_key('smoke')}
        row = (command.job_key('smoke'),'run_3d23462a014a','task_5df19346a61c','ctx_9a8df3d90186','a'*32,1)
        command.execution_guard(DB([row]),job,'a'*32)
        for changed in [(*row[:-1],2),('alternate',*row[1:])]:
            with self.assertRaises(ValueError): command.execution_guard(DB([changed]),job,'a'*32)
        with tempfile.TemporaryDirectory() as t,patch.object(command,'ROOT',Path(t)):
            p=Path(t)/'outputs/batch0004/EXP-0022/smoke/first'
            p.mkdir(parents=True)
            command.ensure_unprocessed('030_090')
            (p/'030_090-predict-started.json').write_text('{}')
            with self.assertRaises(ValueError): command.ensure_unprocessed('030_090')

    def test_manifest_exact_267_native_pts_rgb_environment(self):
        d = command.manifest()
        self.assertEqual(len(d['frames']),267)
        inp = command.input_contract('smoke')
        self.assertEqual(inp['frames'],['030_090','007_064'])
        remaining = command.input_contract('remaining')['frames']
        self.assertEqual(len(remaining),265)
        self.assertFalse(set(remaining)&set(command.SMOKE))
        self.assertFalse(self.torch.cuda.is_initialized())


if __name__ == '__main__':
    unittest.main()
