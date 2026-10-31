import copy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from orchestration import exp39_roi_command as command
from orchestration.queue import Queue,digest,source_hash
from sceneguard.exp0039_roi_gpu import resources

class ROIQueueTests(unittest.TestCase):
    def test_direct_runner_without_inherited_fd_rejected_before_torch(self):
        p=subprocess.run([sys.executable,'-I',str(command.ROOT/'sceneguard/exp0039_roi_gpu.py'),
            '--stage','roi030','--attempt','a'*32,'--lock-fd','999999'],capture_output=True,text=True)
        self.assertNotEqual(p.returncode,0);self.assertIn('Bad file descriptor',p.stderr)
        self.assertNotIn('import torch',p.stderr)

    def test_resource_gate_6144_unchanged(self):
        with patch('batch04_pose.runner.subprocess.check_output',return_value='4000,6143'):
            with self.assertRaises(ValueError):resources()
        with patch('batch04_pose.runner.subprocess.check_output',return_value='4000,6144'):
            self.assertEqual(resources()['free_mib'],6144)

    def test_current_assignment_explicit_go_and_committed_sources_required(self):
        content=b'reviewed';import hashlib
        sources={'x':hashlib.sha256(content).hexdigest()}
        a=dict(zip(('run_id','task_id','dispatch_id'),command.IDENTITY))
        a.update(owner=command.OWNER,confirmed=True,inference_authorized=True,independent_review_passed=True,
            explicit_gpu_go=True,sources=sources,input_contract_sha256=digest({'i':1}),
            maximum_sample_calls=86,maximum_warmup_calls=10,maximum_model_loads=1,code_sha='a'*40)
        def git(args,**kwargs):return 'a'*40+'\n' if args[1]=='rev-parse' else content
        with tempfile.TemporaryDirectory() as t,patch.object(command,'LOCAL',Path(t)),\
             patch.object(command,'sources',return_value=sources),patch.object(command,'input_contract',return_value={'i':1}),\
             patch.object(command.subprocess,'check_output',side_effect=git):
            p=Path(t)/'roi-execution-authorization.json';p.write_text(json.dumps(a))
            command.validate_assignment(*command.IDENTITY)
            for key,value in [('explicit_gpu_go',False),('code_sha','b'*40),('sources',{}),
                ('independent_review_passed',False),('maximum_sample_calls',87),('maximum_warmup_calls',11),
                ('maximum_model_loads',2),('owner','other'),('input_contract_sha256','0'*64)]:
                p.write_text(json.dumps({**a,key:value}))
                with self.assertRaises(ValueError,msg=key):command.validate_assignment(*command.IDENTITY)
            p.write_text(json.dumps(a))
            with self.assertRaises(ValueError):command.validate_assignment(command.IDENTITY[0],'old',command.IDENTITY[2])
            with patch.object(command.subprocess,'check_output',side_effect=lambda args,**k:'a'*40 if args[1]=='rev-parse' else b'dirty'):
                with self.assertRaises(ValueError):command.validate_assignment(*command.IDENTITY)

    def test_fixed_paths_and_settings(self):
        config=dict(stage='roi030',settings=copy.deepcopy(command.SETTINGS))
        with patch.object(command,'input_contract',return_value={'i':1}),patch.object(command,'validate_assignment'):
            argv=command.command(config,{'i':1},command.RUNTIME,'a'*32,123)
            self.assertEqual(argv[0],str(command.INTERPRETER));self.assertIn('exp0039_roi_gpu.py',' '.join(argv))
            config['settings']['roi'][0]=.29
            with self.assertRaises(ValueError):command.validate(config,{'i':1},command.RUNTIME)
        with self.assertRaises(ValueError):command.output_path('roi030','../bad')
        with self.assertRaises(ValueError):command.job_key('other')
        self.assertEqual(source_hash('exp39-roi'),digest(command.sources()))

    def test_migration_on_private_copy_preserves_all_49_jobs_attempts(self):
        with tempfile.TemporaryDirectory() as t:
            q=Queue.initialize(t)
            with sqlite3.connect('file:'+str(command.RUNTIME/'queue.sqlite3')+'?mode=ro',uri=True) as src,sqlite3.connect(q.db) as dest:src.backup(dest)
            before=q.status();self.assertEqual(len(before['jobs']),49);self.assertEqual(len(before['attempts']),49)
            q.migrate_commands(include_exp39_roi=True);q.migrate_commands(include_exp39_roi=True)
            self.assertEqual(q.status(),before)
            with q.connection() as db:
                self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
                self.assertIn("'exp39-roi'",db.execute("SELECT sql FROM sqlite_master WHERE name='jobs'").fetchone()[0])

    def test_execution_guard_fixed_identity_and_bounded_attempts(self):
        class DB:
            def __init__(self,rows):self.rows=rows
            def execute(self,*args):return type('R',(),{'fetchall':lambda _:self.rows})()
        row=(command.job_key(),*command.IDENTITY,command.OWNER,'a'*32,1)
        command.execution_guard(DB([row]),{'job_key':command.job_key()},'a'*32)
        for rows in ([],[row]*3,[(row[0],'old',*row[2:])]):
            with self.assertRaises(ValueError):command.execution_guard(DB(rows),{'job_key':command.job_key()},'a'*32)

    def test_retry_refuses_without_specific_failed_attempt_approval(self):
        class DB:
            def execute(self,*args):return type('R',(),{'fetchall':lambda _: [('a'*32,'failed')]})()
        job=dict(run_id=command.IDENTITY[0],task_id=command.IDENTITY[1],dispatch_id=command.IDENTITY[2],job_id='j')
        with patch.object(command,'validate_assignment',return_value={}):
            with self.assertRaises(ValueError):command.retry_guard(DB(),job)
        with patch.object(command,'validate_assignment',return_value={'execution_error_retry_authorized_for':'a'*32}):
            command.retry_guard(DB(),job)
