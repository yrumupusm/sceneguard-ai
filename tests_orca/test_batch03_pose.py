# SPDX-License-Identifier: AGPL-3.0-only
"""CPU contracts for unknown joints, bounded native sampling and canonical lease."""
from fractions import Fraction
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from orchestration.queue import Queue,digest,process_identity
from orchestration import batch03_pose_command as command
from batch03_pose import runner
from batch03_pose.prepare import eligible,DIAGNOSTICS,WINDOWS


class PoseTests(unittest.TestCase):
    def test_unknown_and_retained_joint_contract(self):
        k=[[10,20,.5] for _ in range(17)];k[0]=[0,0,.99];k[1]=[15,25,.499]
        p=runner.pose_rows([[1,2,90,99,.8,0]],[k],100,100)[0]
        self.assertIsNone(p['keypoints'][0]['observed_xy']);self.assertIsNone(p['keypoints'][1]['observed_xy'])
        self.assertEqual(p['keypoints'][2]['observed_xy'],[10,20]);self.assertEqual(p['retained_joint_count'],15)
        self.assertEqual(p['keypoints'][9]['name'],'left_wrist');self.assertIn('not track',p['correspondence'])
        self.assertEqual(p['keypoints'][1]['raw_xy'],[15,25])

    def test_bad_shape_nan_class_or_confidence_refused(self):
        k=[[10,20,.5] for _ in range(17)]
        for box,joints in [([1,2,90,99,.8,1],k),([1,2,90,99,.25,0],k),([1,2,1,99,.8,0],k),([1,2,90,99,.8,0],k[:-1]),([1,2,90,99,.8,0],[[float('nan'),2,.8]]+k[1:])]:
            with self.assertRaises(ValueError):runner.pose_rows([box],[joints],100,100)
        with self.assertRaises(ValueError):runner.pose_rows([], [k],100,100)
        self.assertEqual(runner.pose_rows([],[],100,100),[])

    def test_exact_native_interval_and_minimum_spacing(self):
        self.assertTrue(eligible(Fraction(625,10),62.5,67.5,None))
        self.assertFalse(eligible(Fraction(675,10),62.5,67.5,None))
        self.assertFalse(eligible(Fraction(626,10),62.5,67.5,Fraction(6255,100)))
        self.assertTrue(eligible(Fraction(627,10),62.5,67.5,Fraction(626,10)))
        self.assertEqual(len(DIAGNOSTICS),11);self.assertEqual(len(WINDOWS),5)

    def test_fixed_fp32_square_end2end_settings(self):
        self.assertEqual(command.SMOKE,('030_090','007_064'))
        self.assertFalse(command.SETTINGS['rect']);self.assertTrue(command.SETTINGS['end2end'])
        self.assertFalse(command.SETTINGS['nms']);self.assertFalse(command.SETTINGS['fuse']);self.assertEqual(command.SETTINGS['warmup_frames'],0)
        for config in ({},{'stage':'other','settings':command.SETTINGS},{'stage':'smoke','settings':{**command.SETTINGS,'half':True}},{'stage':'smoke','settings':command.SETTINGS,'extra':1}):
            with self.assertRaises(ValueError):command.validate(config,{},'/tmp/not-canonical')
        self.assertFalse(command.same(command.SETTINGS,{**command.SETTINGS,'rect':0}))

    def test_vram_gate_is_unchanged(self):
        with patch.object(runner.subprocess,'check_output',return_value='4000, 6143'):
            with self.assertRaisesRegex(ValueError,'no model loaded'):runner.resources()
        with patch.object(runner.subprocess,'check_output',return_value='4000, 6144'):self.assertEqual(runner.resources()['free_mib'],6144)

    def test_direct_runner_never_imports_torch(self):
        p=subprocess.run([sys.executable,'-I',str(command.ROOT/'batch03_pose/runner.py'),'--stage','smoke','--attempt','a'*32,'--lock-fd','999999'],capture_output=True,text=True)
        self.assertNotEqual(p.returncode,0);self.assertIn('Bad file descriptor',p.stderr);self.assertNotIn('import torch',p.stderr)

    def test_additive_migration_preserves_rows_and_backup(self):
        with tempfile.TemporaryDirectory() as t:
            q=Queue.initialize(t);q.enqueue(job_key='old',run_id='r',task_id='t',dispatch_id='d',owner='cpu');q.supervise_once()
            q.migrate_commands(include_vlm_batch02=True);before=q.status();q.migrate_commands(include_pose=True)
            self.assertEqual(before,q.status());q.migrate_commands(include_pose=True)
            self.assertEqual(len(list(Path(t).glob('queue-before-batch03-pose-*.sqlite3'))),1)
            with q.connection() as db:
                sql=db.execute("SELECT sql FROM sqlite_master WHERE name='jobs'").fetchone()[0]
            for c in ('cpu-mock','vlm-batch01','mvp-0001','batch02-cv','vlm-batch02','batch03-pose'):self.assertIn("'"+c+"'",sql)

    def test_held_queue_refuses_registration(self):
        with tempfile.TemporaryDirectory() as t:
            q=Queue.initialize(t);q.migrate_commands(include_vlm_batch02=True)
            with q.gpu_lock():
                with self.assertRaisesRegex(ValueError,'reservation'):q.migrate_commands(include_pose=True)

    def test_exact_parent_child_dispatch_and_lease(self):
        with tempfile.TemporaryDirectory() as t:
            q=Queue.initialize(t);q.migrate_commands(include_vlm_batch02=True);q.migrate_commands(include_pose=True)
            job=q.enqueue(job_key='lease',run_id='r',task_id='t',dispatch_id='d',owner='cpu');config=dict(stage='smoke',settings=command.SETTINGS)
            with q.connection() as db:
                db.execute("UPDATE jobs SET command='batch03-pose',status='running',config_json=?,config_hash=?,input_hash=?,source_hash='source',code_sha='frozen' WHERE job_id=?",(json.dumps(config),digest(config),digest({'synthetic':True}),job['job_id']))
                db.execute("INSERT INTO attempts (attempt_id,job_id,attempt_no,owner,status,supervisor_pid,supervisor_identity,child_pid,child_identity,started_at,heartbeat,timeout) VALUES (?,?,1,'cpu','running',?,?,?,?,0,0,10)",('a'*32,job['job_id'],os.getppid(),process_identity(os.getppid()),os.getpid(),process_identity(os.getpid())))
            with patch.object(runner,'RUNTIME',Path(t)),patch.object(runner,'INTERPRETER',Path(sys.executable)),patch.object(runner,'validate',return_value='smoke'),patch.object(runner,'source_hash',return_value='source'),patch.object(runner,'validate_assignment',return_value={'code_sha':'frozen'}):
                with q.gpu_lock() as lock:
                    self.assertEqual(runner.verify_lease(config,'a'*32,lock.fileno())['command'],'batch03-pose')
                    with (Path(t)/'gpu.lock').open() as unrelated:
                        with self.assertRaisesRegex(ValueError,'inherited reservation'):runner.verify_lease(config,'a'*32,unrelated.fileno())
                    with q.connection() as db:db.execute("UPDATE attempts SET child_identity='wrong'")
                    with self.assertRaisesRegex(ValueError,'child identity'):runner.verify_lease(config,'a'*32,lock.fileno())

    def test_assignment_freeze_and_stale_dispatch(self):
        with tempfile.TemporaryDirectory() as t:
            Path(t,'execution-authorization.json').write_text(json.dumps(dict(run_id='r',task_id='t',dispatch_id='d',confirmed=True,sources={'a':'b'})))
            with patch.object(command,'LOCAL',Path(t)),patch.object(command,'sources',return_value={'a':'b'}):
                self.assertTrue(command.validate_assignment('r','t','d')['confirmed'])
                with self.assertRaises(ValueError):command.validate_assignment('r','t','old')
                with patch.object(command,'sources',return_value={'a':'changed'}):
                    with self.assertRaisesRegex(ValueError,'freeze'):command.validate_assignment('r','t','d')

    def test_retry_never_regenerates_started_forward(self):
        with tempfile.TemporaryDirectory() as t:
            db=sqlite3.connect(':memory:');db.execute('CREATE TABLE attempts(attempt_id TEXT,job_id TEXT)');db.execute('INSERT INTO attempts VALUES (?,?)',('a'*32,'j'))
            path=Path(t)/'output';path.mkdir();job=dict(job_id='j',config_json=json.dumps({'stage':'smoke'}))
            with patch.object(command,'output_path',return_value=path):
                command.retry_guard(db,job,for_execution=True);(path/'inference-started.json').write_text('{}')
                with self.assertRaisesRegex(ValueError,'without regeneration'):command.retry_guard(db,job,for_execution=True)

    def test_manifest_identity_source_membership_and_native_parity(self):
        from copy import deepcopy
        frames=[]
        for name in DIAGNOSTICS:
            source='E01_'+name[:3];pts=int(name[-3:])*10
            frames.append(dict(frame_id=name,source_id=source,native_pts=pts,time_base='1/10',pts_seconds=pts/10,source_path=source+'.mp4',source_sha256='source',rgb_bytes_sha256='RGB',source_size=[100,100],diagnostic=True,windows=[]))
        old=dict(frames=deepcopy(frames));windows=[]
        for alias,source,start,end in WINDOWS:
            row=dict(frame_id=alias,source_id=source,native_pts=int(start*10),time_base='1/10',pts_seconds=start,source_path=source+'.mp4',source_sha256='source',rgb_bytes_sha256='RGB',source_size=[100,100],diagnostic=False,windows=[alias])
            frames.append(row);windows.append(dict(alias=alias,source_id=source,start=start,end=end,frames=[alias]))
        binding=dict(frames=frames,windows=windows)
        command.validate_frame_contract(binding,old)
        mutations=[]
        d=deepcopy(binding);d['frames'][1]['frame_id']=d['frames'][0]['frame_id'];mutations.append(d)
        d=deepcopy(binding);d['frames'][-1]['windows']=[];mutations.append(d)
        d=deepcopy(binding);d['windows'][0]['source_id']='E01_004';mutations.append(d)
        d=deepcopy(binding);next(r for r in d['frames'] if r['diagnostic'])['rgb_bytes_sha256']='bad';mutations.append(d)
        d=deepcopy(binding);d['windows'][0]['frames'].pop();mutations.append(d)
        d=deepcopy(binding);next(r for r in d['frames'] if not r['diagnostic'])['windows']=[];mutations.append(d)
        for d in mutations:
            with self.assertRaises(ValueError):command.validate_frame_contract(d,old)

    def test_isolated_interpreter_is_pinned_inside_repository(self):
        if not command.INTERPRETER.exists():self.skipTest('local isolated interpreter not installed')
        self.assertTrue(command.INTERPRETER.resolve().is_relative_to(command.ROOT))
        self.assertFalse(command.INTERPRETER.is_symlink())

    def test_official_head_selection_without_model_construction(self):
        class Head:
            def __init__(self):self._selected=False;self.max_det=99;self.agnostic_nms=True
            @property
            def end2end(self):return self._selected
        class Model:
            def __init__(self):self.model=[Head()]
            @property
            def end2end(self):return self.model[-1].end2end
            @end2end.setter
            def end2end(self,value):self.model[-1]._selected=value
            def set_head_attr(self,**kwargs):
                for k,v in kwargs.items():setattr(self.model[-1],k,v)
        model=Model();self.assertFalse(model.end2end);runner.initialize_head(model)
        self.assertTrue(model.end2end);self.assertEqual(model.model[-1].max_det,300);self.assertFalse(model.model[-1].agnostic_nms)
        class Missing(Model):
            @Model.end2end.setter
            def end2end(self,value):pass
        with self.assertRaisesRegex(ValueError,'no fallback'):runner.initialize_head(Missing())

    def test_no_third_logical_smoke_attempt(self):
        db=sqlite3.connect(':memory:')
        for stage in ('smoke',):
            with self.assertRaises(ValueError):command.retry_guard(db,dict(config_json=json.dumps(dict(stage=stage)),job_id='j'))

    def test_network_and_output_identity(self):
        with self.assertRaises(RuntimeError):runner.deny_network()
        for stage,attempt in [('bad','a'*32),('smoke','../escape')]:
            with self.assertRaises(ValueError):command.output_path(stage,attempt)

if __name__=='__main__':unittest.main()
