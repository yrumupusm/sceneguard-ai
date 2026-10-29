# SPDX-License-Identifier: AGPL-3.0-only
"""Meaningful CPU contract tests; no model instances and no real queue writes."""
import copy
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from orchestration import exp27_detect_command as command
from orchestration.queue import Queue,digest,source_hash
from exp27_detect import runner
from exp27_detect.api import result_rows,score_bin,BINS,compare_cached,official_audit
from batch04_pose.api import bgr_source


class DetectionDiagnosisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise RuntimeError('hide CUDA for CPU tests')
        import numpy as np
        import torch
        from ultralytics.engine.results import Results
        cls.np,cls.torch,cls.Results=np,torch,Results

    def result(self,rows):
        return self.Results(self.np.zeros((648,903,3),self.np.uint8),path='synthetic',names={0:'person'},
            boxes=self.torch.tensor(rows,dtype=self.torch.float32).reshape(-1,6))

    def test_kwargs_only_conf_diff_and_official_installed_audit(self):
        from orchestration.batch07_detect_command import PREDICT_KWARGS as old
        self.assertEqual([k for k in old if old[k]!=command.PREDICT_KWARGS[k]],['conf'])
        self.assertEqual(old['conf'],.25);self.assertEqual(command.PREDICT_KWARGS['conf'],.05)
        self.assertEqual(command.PREDICT_KWARGS['classes'],[0]);self.assertIsNone(command.PREDICT_KWARGS['quantize'])
        self.assertEqual([command.PREDICT_KWARGS[k] for k in ('device','imgsz','rect','batch','max_det','iou','nms')],['cuda:0',640,False,1,300,.7,False])
        audit=official_audit();self.assertEqual(audit['model_constructions'],0)
        self.assertIn('empty does not establish',audit['limitation']);self.assertFalse(self.torch.cuda.is_initialized())

    def test_official_strict_conf_class_filter_max_det_and_head_topk(self):
        from ultralytics.utils.nms import non_max_suppression
        from ultralytics.nn.modules.head import Detect
        prediction=self.torch.tensor([[[0,0,1,1,.05,0],[0,0,1,1,.10,1],[0,0,1,1,.25,0],[0,0,1,1,.8,0]]])
        low=non_max_suppression(prediction.clone(),conf_thres=.05,classes=[0],max_det=1,end2end=True)[0]
        self.assertEqual(len(low),1);self.assertEqual(low[0,4].item(),.25)  # Preserve order after masks, no sorting.
        high=non_max_suppression(prediction.clone(),conf_thres=.25,classes=[0],end2end=True)[0]
        self.assertEqual(len(high),1);self.assertGreater(high[0,4].item(),.25)
        scores=self.torch.zeros((1,3,80));scores[0,0,0]=.2;scores[0,1,1]=.9;scores[0,2,2]=.8
        fake=SimpleNamespace(agnostic_nms=False,export=False,_grouped_topk=Detect._grouped_topk)
        fake._gather=lambda x,index:Detect._gather(fake,x,index)
        _,labels,_=Detect.get_topk_index(fake,scores,2)
        self.assertEqual(labels.flatten().tolist(),[1.,2.])  # Person row can vanish before classes[0].
        self.assertFalse(self.torch.cuda.is_initialized())

    def test_model_hashes_and_classes_public_boundary(self):
        public=json.loads(command.MANIFEST.read_text())
        self.assertEqual(public['models'],command.MODELS)
        self.assertEqual([s['nc'] for s in command.MODELS.values()],[80,1])
        for spec in command.MODELS.values():
            self.assertNotIn('pose',spec['path']);command.checked(spec['path'],spec['sha256'])
            with self.assertRaises(ValueError):command.checked(spec['path'],'0'*64)
        self.assertNotIn('xyxy',command.MANIFEST.read_text())
        self.assertNotIn('confidence_bins',command.MANIFEST.read_text())

    def test_bins_boundaries_empty_all_rows_offset_and_no_mutation(self):
        self.assertEqual([score_bin(x) for x in (.05,.099999,.1,.249999,.25,1)],[BINS[0],BINS[0],BINS[1],BINS[1],BINS[2],BINS[2]])
        for x in (.04999,1.001,float('nan')):
            with self.assertRaises(ValueError):score_bin(x)
        r=self.result([[0,0,903,648,.05,0],[10,20,30,40,.1,0],[20,30,40,50,.25,0]])
        before=r.boxes.data.clone();d=result_rows(r,(648,903,3),[537,216])
        self.assertEqual(list(d['confidence_bins'].values()),[1,1,1]);self.assertEqual(d['person_count'],3)
        self.assertEqual(d['offset_applications'],1);self.assertEqual(d['persons'][0]['xyxy'],[537,216,1440,864])
        self.assertTrue(self.torch.equal(before,r.boxes.data));self.assertIsNone(d['accuracy'])
        empty=result_rows(self.result([]),(648,903,3),[537,216])
        self.assertEqual(empty['persons'],[]);self.assertEqual(sum(empty['confidence_bins'].values()),0)

    def test_reject_unknown_malformed_nonfinite_classes_and_shapes(self):
        for data in [[[0,0,3,4,.8,1]],[[0,0,3,4,float('nan'),0]],[[0,0,3,4,.01,0]],[[0,0,904,4,.8,0]],[[3,0,3,4,.8,0]]]:
            with self.assertRaises(ValueError):result_rows(self.result(data),(648,903,3),[537,216])
        for change in ('pose','shape','none','nx7'):
            r=self.result([])
            if change=='pose':r.keypoints=SimpleNamespace(data=[])
            if change=='shape':r.orig_shape=(1,1)
            if change=='none':r.boxes=None
            if change=='nx7':r.boxes=SimpleNamespace(data=self.torch.empty((0,7)))
            with self.assertRaises(ValueError):result_rows(r,(648,903,3),[537,216])

    def test_rgb_bgr_contiguous_and_exact_crop(self):
        rgb=self.np.array([[[10,20,30],[40,50,60]]],dtype=self.np.uint8)
        bgr=bgr_source(rgb);self.assertEqual(bgr.tolist(),[[[30,20,10],[60,50,40]]]);self.assertTrue(bgr.flags.c_contiguous)
        self.assertEqual(rgb.tolist(),[[[10,20,30],[40,50,60]]])
        for invalid in (rgb.astype(float),rgb[:,:,0],'http://input'):
            with self.assertRaises(ValueError):bgr_source(invalid)

    def test_exact_input_contract_native_pts_crop_order_and_old_immutability(self):
        before=command.file_hash(command.OLD_SUMMARY)
        contract=command.input_contract();self.assertEqual(contract['evaluation_manifest_sha256'],command.EVAL_SHA)
        d=command.evaluation();self.assertEqual(tuple(f['frame_id'] for f in d['frames']),command.FRAMES)
        for i in (0,5):
            x=copy.deepcopy(d);x['frames'][i]['native_pts']+=1
            with self.assertRaisesRegex(ValueError,'native PTS'):command.validate_eval(x)
            x=copy.deepcopy(d);x['frames'][i]['crop_xyxy'][0]+=1
            with self.assertRaises(ValueError):command.validate_eval(x)
        with patch.object(command,'dataset_files',return_value={}):
            with self.assertRaisesRegex(ValueError,'dataset bytes'):command.input_contract()
        self.assertEqual(command.file_hash(command.OLD_SUMMARY),before)
        self.assertFalse(self.torch.cuda.is_initialized())

    def test_cached_comparison_order_exact_tolerance_deltas_boundary_and_immutability(self):
        low=[dict(xyxy=[1.,2.,3.,4.],confidence=.5,class_id=0),dict(xyxy=[2.,3.,4.,5.],confidence=.25,class_id=0),dict(xyxy=[1.,2.,3.,4.],confidence=.1,class_id=0)]
        old=copy.deepcopy(low[:2]);snapshot=copy.deepcopy((low,old))
        exact=compare_cached(low,old);self.assertTrue(exact['exact_ordered_equal']);self.assertEqual(exact['boundary_exact_025_count'],1)
        self.assertEqual((low,old),snapshot)
        old[0]['xyxy'][0]+=.0001;old[0]['confidence']+=.0000001
        close=compare_cached(low,old);self.assertFalse(close['exact_ordered_equal']);self.assertTrue(close['tolerance_ordered_equal'])
        self.assertGreater(close['max_abs_position_delta'],0)
        self.assertFalse(compare_cached(low,list(reversed(old)))['tolerance_ordered_equal'])
        old[0]['xyxy'][0]+=1;self.assertFalse(compare_cached(low,old)['tolerance_ordered_equal'])
        self.assertFalse(compare_cached(low,old[:1])['tolerance_ordered_equal'])
        self.assertTrue(compare_cached([],[])['exact_ordered_equal'])

    def test_lease_and_resource_gate_before_model_import(self):
        p=subprocess.run([sys.executable,'-I',str(command.ROOT/'exp27_detect/runner.py'),'--stage','diagnose','--attempt','a'*32,'--lock-fd','999999'],capture_output=True,text=True)
        self.assertNotEqual(p.returncode,0);self.assertIn('Bad file descriptor',p.stderr);self.assertNotIn('import torch',p.stderr)
        with patch('batch04_pose.runner.subprocess.check_output',return_value='4000,6143'):
            with self.assertRaisesRegex(ValueError,'6144'):runner.resources()
        with patch('batch04_pose.runner.subprocess.check_output',return_value='4000,6144'):
            self.assertEqual(runner.resources()['free_mib'],6144)

    def test_authorization_exact_identity_source_input_review_freeze_budget(self):
        a=dict(run_id=command.IDENTITY[0],task_id=command.IDENTITY[1],dispatch_id=command.IDENTITY[2],confirmed=True,
            inference_authorized=True,independent_review_passed=True,maximum_sample_calls=14,sources={'a':'b'},
            allowed_stages=list(command.STAGES),input_contract_sha256=digest({'input':1}),code_sha='a'*40)
        with tempfile.TemporaryDirectory() as t,patch.object(command,'LOCAL',Path(t)),patch.object(command,'sources',return_value={'a':'b'}),\
            patch.object(command,'input_contract',return_value={'input':1}),patch('orchestration.exp27_detect_command.subprocess.check_output',return_value='a'*40+'\n'):
            p=Path(t)/'execution-authorization.json';p.write_text(json.dumps(a));command.validate_assignment(*command.IDENTITY)
            with self.assertRaises(ValueError):command.validate_assignment(command.IDENTITY[0],'wrong',command.IDENTITY[2])
            for k,v in [('sources',{}),('code_sha','0'*40),('input_contract_sha256','0'*64),('inference_authorized',False),('independent_review_passed',False),('maximum_sample_calls',15),('allowed_stages',['train_compare'])]:
                p.write_text(json.dumps({**a,k:v}))
                with self.assertRaises(ValueError,msg=k):command.validate_assignment(*command.IDENTITY)

    def test_command_fixed_canonical_runtime_and_output_paths(self):
        with patch.object(command,'input_contract',return_value={'i':1}),patch.object(command,'validate_assignment'):
            cfg=dict(stage='diagnose',settings=command.SETTINGS)
            argv=command.command(cfg,{'i':1},command.RUNTIME,'a'*32,123)
            self.assertIn('exp27_detect/runner.py',' '.join(argv));self.assertNotIn('batch07_detect/runner.py',' '.join(argv))
            for bad in (Path('/tmp/other'),command.ROOT):
                with self.assertRaises(ValueError):command.validate(cfg,{'i':1},bad)
            altered=copy.deepcopy(cfg);altered['settings']['predict_kwargs']['conf']=.01
            with self.assertRaises(ValueError):command.validate(altered,{'i':1},command.RUNTIME)
        for stage in ('train_compare','test'):
            with self.assertRaises(ValueError):command.job_key(stage)
        with self.assertRaises(ValueError):command.output_path('diagnose','../bad')

    def test_exclusive_start_markers_and_partial_failure_never_retry(self):
        with tempfile.TemporaryDirectory() as t,patch.object(runner,'ROOT',Path(t)):
            folder=Path(t)/'outputs/exp0027/EXP-0027/diagnose'/('a'*32);folder.mkdir(parents=True)
            runner.start_marker(folder,'pretrained-030_084','a'*32)
            with self.assertRaises(ValueError):runner.start_marker(folder,'pretrained-030_084','a'*32)
            other=folder.parent/('b'*32);other.mkdir()
            with self.assertRaises(ValueError):runner.start_marker(other,'pretrained-030_084','b'*32)
            runner.start_marker(folder,'fine_tuned-030_084','a'*32)
        with self.assertRaisesRegex(ValueError,'no automatic retry'):command.retry_guard(None,{})

    def test_execution_guard_budget_identity_and_source_digest(self):
        class DB:
            def __init__(self,rows):self.rows=rows
            def execute(self,*a):return SimpleNamespace(fetchall=lambda:self.rows)
        row=(command.job_key(),*command.IDENTITY,'a'*32,1)
        command.execution_guard(DB([row]),{'job_key':row[0]},'a'*32)
        for bad in ([(*row[:-1],2)],[row,row],[(row[0],*row[1:3],'wrong',*row[4:])]):
            with self.assertRaises(ValueError):command.execution_guard(DB(bad),{'job_key':row[0]},'a'*32)
        self.assertEqual(source_hash('exp27-detect'),digest(command.sources()))

    def test_migration_copy_preserves_all_43_historical_jobs_attempts_and_finish(self):
        # SQLite backup is read-only at source. Migrate a disposable real-history copy only.
        with tempfile.TemporaryDirectory() as t:
            q=Queue.initialize(t)
            with sqlite3.connect('file:'+str(command.RUNTIME/'queue.sqlite3')+'?mode=ro',uri=True) as source,sqlite3.connect(q.db) as dest:source.backup(dest)
            before=q.status();historical_ids={j['job_id'] for j in before['jobs'] if j['command']!='exp27-detect'}
            self.assertEqual(len(historical_ids),43)
            self.assertEqual(sum(a['job_id'] in historical_ids for a in before['attempts']),43)
            q.migrate_commands(include_exp27_detect=True);q.migrate_commands(include_exp27_detect=True)
            self.assertEqual(q.status(),before)
            self.assertEqual(len(list(Path(t).glob('queue-before-exp27-detect-*.sqlite3'))),1)
            with q.connection() as db:
                self.assertFalse(list(db.execute('PRAGMA foreign_key_check')))
            # Use fresh synthetic queue for finish/retry contract, never edit historical rows.
        with tempfile.TemporaryDirectory() as t:
            q=Queue.initialize(t);q.enqueue(job_key='synthetic',run_id='r',task_id='t',dispatch_id='d',owner='cpu');q.supervise_once()
            for flag in ('include_vlm_batch02','include_pose','include_public_pose','include_roi_pose','include_resolution_pose','include_detect','include_exp27_detect'):q.migrate_commands(**{flag:True})
            with q.connection() as db:
                job=dict(db.execute('SELECT * FROM jobs').fetchone());attempt=db.execute('SELECT attempt_id FROM attempts').fetchone()[0]
                db.execute("UPDATE jobs SET command='exp27-detect',config_json=? WHERE job_id=?",(json.dumps(dict(stage='diagnose',settings=command.SETTINGS)),job['job_id']))
            q._finish(attempt,'failed',1,'synthetic failure')
            manifest=json.loads(Path(q.status()['attempts'][0]['result_manifest']).read_text())
            self.assertFalse(manifest['synthetic']);self.assertIn('exp27_detect/runner.py',manifest['registration']['script'])
            with self.assertRaisesRegex(ValueError,'no automatic retry'):q.retry(job['job_id'])

    def test_offline_transport_and_settings_no_model_construction(self):
        import ultralytics.utils as utils
        # Snapshot both environment and integration settings. Use fresh dummy store for test.
        class Store(dict):
            pass
        with tempfile.TemporaryDirectory() as t,patch.object(runner,'LOCAL',Path(t)),patch.dict(os.environ,{},clear=False),\
            patch.object(utils,'SETTINGS',Store()),patch.object(socket.socket,'connect'),patch.object(socket.socket,'connect_ex'),\
            patch.object(socket.socket,'sendto'),patch.object(socket,'create_connection'),patch.object(socket,'getaddrinfo'):
            report=runner.configure_offline()
            self.assertFalse(utils.SETTINGS['sync']);self.assertFalse(utils.SETTINGS['wandb']);self.assertEqual(utils.SETTINGS['api_key'],'')
            with self.assertRaises(RuntimeError):socket.getaddrinfo('example.com',443)
            self.assertIn('denied',report['network'])
        self.assertFalse(self.torch.cuda.is_initialized())


if __name__=='__main__':unittest.main()
