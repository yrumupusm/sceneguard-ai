# SPDX-License-Identifier: AGPL-3.0-only
"""CPU contract tests; CUDA hidden, no GPU/model loading/real queue mutation."""
import copy
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from orchestration import batch07_detect_command as command
from orchestration.queue import Queue,digest,source_hash
from batch07_detect import runner
from batch07_detect.api import result_rows


class DetectionTests(unittest.TestCase):
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

    def test_fixed_public_official_arguments_no_pose(self):
        from ultralytics.cfg import get_cfg
        from ultralytics.engine.model import Model
        import inspect
        self.assertIn('stream',inspect.signature(Model.predict).parameters)
        get_cfg(overrides={k:v for k,v in command.PREDICT_KWARGS.items() if k!='stream'})
        get_cfg(overrides=command.TRAIN_KWARGS)
        t=command.TRAIN_KWARGS
        self.assertEqual([t[k] for k in ('epochs','imgsz','batch','device','workers','seed','freeze','nbs')],[20,640,2,0,0,0,10,64])
        self.assertEqual([t[k] for k in ('optimizer','lr0','lrf','weight_decay','warmup_epochs','warmup_bias_lr')],['AdamW',.0001,.1,.0005,1,0.])
        self.assertTrue(t['deterministic']);self.assertFalse(t['amp']);self.assertFalse(t['resume'])
        self.assertTrue(all(t[k]==0 for k in command.AUGMENT_ZERO));self.assertEqual(t['augmentations'],[])
        self.assertEqual(command.WEIGHT.name,'yolo26m.pt');self.assertNotIn('pose',command.WEIGHT.name)
        self.assertEqual(command.PREDICT_KWARGS['classes'],[0]);self.assertIsNone(command.PREDICT_KWARGS['quantize'])
        source=(command.ROOT/'batch07_detect/runner.py').read_text()
        self.assertIn("model=YOLO(str(WEIGHT),task='detect')",source)
        self.assertIn('fresh_unfused_train_instance',source)
        self.assertFalse(self.torch.cuda.is_initialized())

    def test_native_offset_once_empty_and_all_scores(self):
        r=self.result([[0,0,903,648,.8,0],[10,20,30,40,.3,0]])
        d=result_rows(r,(648,903,3),[537,216])
        self.assertEqual(d['offset_applications'],1);self.assertEqual(d['person_count'],2)
        self.assertEqual(d['persons'][0]['xyxy'],[537,216,1440,864])
        self.assertEqual(d['local_persons'][0]['xyxy'],[0,0,903,648])
        self.assertEqual(r.boxes.data[0,0].item(),0)
        self.assertEqual(result_rows(self.result([]),(648,903,3),[537,216])['persons'],[])
        self.assertIsNone(d['accuracy'])

    def test_reject_unknown_malformed_nonfinite_pose(self):
        for data in [[[0,0,3,4,.8,1]],[[0,0,3,4,float('nan'),0]],[[0,0,3,4,.1,0]],[[0,0,904,4,.8,0]]]:
            with self.assertRaises(ValueError):result_rows(self.result(data),(648,903,3),[537,216])
        r=self.result([]);r.keypoints=SimpleNamespace(data=[])
        with self.assertRaises(ValueError):result_rows(r,(648,903,3),[537,216])

    def test_live_lease_required_before_torch_import(self):
        p=subprocess.run([sys.executable,'-I',str(command.ROOT/'batch07_detect/runner.py'),'--stage','train_compare',
            '--attempt','a'*32,'--lock-fd','999999'],capture_output=True,text=True)
        self.assertNotEqual(p.returncode,0);self.assertIn('Bad file descriptor',p.stderr)
        self.assertNotIn('import torch',p.stderr)
        with patch('batch04_pose.runner.subprocess.check_output',return_value='4000,6143'):
            with self.assertRaisesRegex(ValueError,'6144'):runner.resources()

    def test_input_full_validation_and_no_dataset_test_loader(self):
        from batch07_detect.prepare import TREE,verify_tree
        d=verify_tree();self.assertEqual((d['train'],d['valid'],d['test_used']),(210,20,0))
        self.assertNotIn('test:',(TREE/'data.yaml').read_text());self.assertFalse((TREE/'test').exists())
        actual=command.input_contract();self.assertEqual(actual['checkpoint_sha256'],command.WEIGHT_SHA)
        changed=copy.deepcopy(json.loads(command.EVAL.read_text()));changed['frames'][0]['native_pts']+=1
        with self.assertRaisesRegex(ValueError,'native PTS'):command.validate_eval(changed)
        changed=copy.deepcopy(json.loads(command.EVAL.read_text()));changed['frames'][0]['crop_xyxy'][0]+=1
        with self.assertRaises(ValueError):command.validate_eval(changed)
        with patch.object(command,'dataset_files',return_value={}):
            with self.assertRaisesRegex(ValueError,'dataset bytes'):command.input_contract()
        self.assertFalse(self.torch.cuda.is_initialized())

    def test_authorization_exact_source_input_git_and_identity(self):
        a=dict(run_id=command.IDENTITY[0],task_id=command.IDENTITY[1],dispatch_id=command.IDENTITY[2],
            confirmed=True,training_authorized=True,D0_passed=False,sources={'a':'b'},allowed_stages=list(command.STAGES),
            input_contract_sha256=digest({'input':1}),code_sha='a'*40)
        with tempfile.TemporaryDirectory() as t,patch.object(command,'LOCAL',Path(t)),\
            patch.object(command,'sources',return_value={'a':'b'}),patch.object(command,'input_contract',return_value={'input':1}),\
            patch('orchestration.batch07_detect_command.subprocess.check_output',return_value='a'*40+'\n'):
            p=Path(t)/'execution-authorization.json';p.write_text(json.dumps(a))
            command.validate_assignment(*command.IDENTITY)
            with self.assertRaises(ValueError):command.validate_assignment(command.IDENTITY[0],'wrong',command.IDENTITY[2])
            for field,value in [('sources',{'a':'altered'}),('input_contract_sha256','0'*64),('code_sha','0'*40),('training_authorized',False),('D0_passed',True)]:
                p.write_text(json.dumps({**a,field:value}))
                with self.assertRaises(ValueError,msg=field):command.validate_assignment(*command.IDENTITY)

    def test_recovery_log_guard_aborts_before_next_action(self):
        with tempfile.TemporaryDirectory() as t:
            logger=logging.getLogger('batch07-test-recovery');logger.propagate=False
            handler=runner.RejectRecovery(Path(t));logger.addHandler(handler)
            try:
                logger.warning('ordinary warning')
                for message in ('CUDA out of memory with batch=2. Reducing to batch=1 and retrying (1/3).',
                    'Loss NaN/Inf detected (attempt 1/3), recovering from last.pt...',
                    'Fitness NaN/Inf detected but can not recover from last.pt...'):
                    next_action=[]
                    with self.assertRaisesRegex(RuntimeError,'recovery prohibited'):
                        logger.warning(message);next_action.append('rebuild-or-forward')
                    self.assertEqual(next_action,[])
                    self.assertTrue((Path(t)/'recovery-refused.local.json').exists())
            finally:logger.removeHandler(handler)

    def test_epoch_final_validation_is_not_epoch21(self):
        with tempfile.TemporaryDirectory() as t:
            summary={};callbacks=runner.make_callbacks(Path(t),summary,SimpleNamespace(cuda=SimpleNamespace(max_memory_allocated=lambda:0)))
            tr=SimpleNamespace(epoch=19,epochs=20,fitness=.1,best_fitness=.1,metrics={},lr={},tloss={},
                batch_size=2,amp=False,label_loss_items=lambda x:{})
            callbacks['on_train_epoch_start'](tr);callbacks['on_fit_epoch_end'](tr)
            self.assertEqual(summary['epochs_completed'],20)
            tr.epoch=20;callbacks['on_fit_epoch_end'](tr)
            self.assertEqual(summary['epochs_completed'],20);self.assertEqual(len(summary['epoch_metrics']),1)
            tr.loss=self.torch.tensor(float('nan'))
            with self.assertRaisesRegex(ValueError,'nonfinite'):callbacks['on_train_epoch_end'](tr)
            validator=SimpleNamespace(args=SimpleNamespace(quantize=None),metrics=SimpleNamespace(fitness=.1))
            callbacks['on_val_end'](validator);self.assertEqual(summary['validation_calls'],1)
            validator.args.quantize=16
            with self.assertRaisesRegex(ValueError,'FP32'):callbacks['on_val_end'](validator)

    def test_queue_additive_migration_history_retry_and_finish(self):
        with tempfile.TemporaryDirectory() as t:
            q=Queue.initialize(t);q.enqueue(job_key='historical',run_id='r',task_id='t',dispatch_id='d',owner='cpu');q.supervise_once()
            q.migrate_commands(include_vlm_batch02=True);q.migrate_commands(include_pose=True)
            q.migrate_commands(include_public_pose=True);q.migrate_commands(include_roi_pose=True);q.migrate_commands(include_resolution_pose=True)
            before=q.status();q.migrate_commands(include_detect=True);q.migrate_commands(include_detect=True)
            self.assertEqual(q.status(),before)
            self.assertEqual(len(list(Path(t).glob('queue-before-batch07-detect-*.sqlite3'))),1)
            with q.connection() as db:
                self.assertFalse(list(db.execute('PRAGMA foreign_key_check')))
                job=dict(db.execute("SELECT * FROM jobs").fetchone())
                db.execute("UPDATE jobs SET command='batch07-detect',config_json=? WHERE job_id=?",(json.dumps(dict(stage='train_compare',settings=command.SETTINGS)),job['job_id']))
                attempt=db.execute('SELECT attempt_id FROM attempts').fetchone()[0]
            q._finish(attempt,'failed',1,'synthetic failure only')
            result=q.status();manifest=json.loads(Path(result['attempts'][0]['result_manifest']).read_text())
            self.assertFalse(manifest['synthetic']);self.assertIn('batch07_detect/runner.py',manifest['registration']['script'])
            with self.assertRaisesRegex(ValueError,'no automatic retry'):q.retry(job['job_id'])

    def test_execution_guard_and_source_digest(self):
        class DB:
            def __init__(self,rows):self.rows=rows
            def execute(self,*a):return SimpleNamespace(fetchall=lambda:self.rows)
        row=(command.job_key(),*command.IDENTITY,'a'*32,1)
        command.execution_guard(DB([row]),{'job_key':row[0]},'a'*32)
        for bad in ([(*row[:-1],2)],[row,row],[(row[0],*row[1:3],'wrong',*row[4:])]):
            with self.assertRaises(ValueError):command.execution_guard(DB(bad),{'job_key':row[0]},'a'*32)
        self.assertEqual(source_hash('batch07-detect'),digest(command.sources()))
        with patch.object(command,'sources',return_value={'changed':'hash'}):
            self.assertEqual(source_hash('batch07-detect'),digest({'changed':'hash'}))
        with self.assertRaises(ValueError):command.output_path('train_compare','../bad')
        with self.assertRaises(ValueError):command.job_key('test')


if __name__=='__main__':unittest.main()
