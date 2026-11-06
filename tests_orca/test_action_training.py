"""Focused action adapter checks. GPU execution is replaced by a CPU FD probe."""
import copy
import fcntl
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from orchestration import action_training_command as command
from orchestration.queue import Queue, digest, source_hash

CONTEXT = dict(run_id='run_3d23462a014a',task_id='task-test',dispatch_id='ctx-test',owner='term-test')


class ActionQueueTests(unittest.TestCase):
    def config(self):
        return dict(stage='smoke',execution_revision=command.EXECUTION_REVISION,context=copy.deepcopy(CONTEXT),
                    files={k:dict(path='/tmp/'+k,sha256='a'*64) for k in command.FILE_KEYS},
                    authorization=dict(path='/tmp/authorization',sha256='b'*64))

    def test_live_assignment_rejects_stale_owner_revoked_and_finished_dispatch(self):
        dispatch=dict(runId=CONTEXT['run_id'],taskId=CONTEXT['task_id'],assigneeHandle=CONTEXT['owner'],
                      status='dispatched',capabilityRevokedAt=None)
        for change in ({},{'assigneeHandle':'old'},{'status':'completed'},{'capabilityRevokedAt':'revoked'}):
            with patch.object(command.subprocess,'check_output',return_value=json.dumps(dict(ok=True,result=dict(dispatch={**dispatch,**change},projection=dict(liveness=dict(verdict='live')),
                                observation=dict(status='live',exactWorker=True))))):
                if change:
                    with self.assertRaises(ValueError):command.validate_assignment(CONTEXT)
                else:command.validate_assignment(CONTEXT)
        for verdict in ('exited','unverifiable'):
            response=dict(ok=True,result=dict(dispatch=dispatch,projection=dict(liveness=dict(verdict=verdict)),
                                              observation=dict(status='live',exactWorker=True)))
            with patch.object(command.subprocess,'check_output',return_value=json.dumps(response)):
                with self.assertRaisesRegex(ValueError,'liveness'):command.validate_assignment(CONTEXT)
        with patch.object(command.subprocess,'check_output',side_effect=subprocess.TimeoutExpired('orca',25)):
            with self.assertRaises(subprocess.TimeoutExpired):command.validate_assignment(CONTEXT)

    def test_resource_gate_exactly_6144(self):
        for free in (6143,6144):
            with patch.object(command.subprocess,'check_output',return_value=str(free)):
                if free==6143:
                    with self.assertRaisesRegex(ValueError,'6144'):command.resources()
                else:self.assertEqual(command.resources()['free_mib'],6144)

    def test_release_authorization_requires_current_committed_sources_and_go(self):
        config=self.config();inputs=dict(bound='input');content=b'reviewed-source'
        import hashlib
        sources={'owned.py':hashlib.sha256(content).hexdigest()}
        authorization=dict(context=CONTEXT,stage='smoke',execution_revision=command.EXECUTION_REVISION,
                           recovery_from_attempt=command.RECOVERY_ATTEMPT,input_hash=digest(inputs),sources=sources,code_sha='a'*40,
                           confirmed=True,training_authorized=True,independent_review_passed=True,explicit_gpu_go=True)
        def git(argv,**kwargs):return 'a'*40 if argv[1]=='rev-parse' else content
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'authorization.json'
            def write(value):
                path.write_text(json.dumps(value));config['authorization']=dict(path=str(path),sha256=command.file_hash(path))
            with patch.object(command,'input_contract',return_value=inputs),patch.object(command,'sources',return_value=sources),\
                 patch.object(command,'validate_assignment'),patch.object(command,'validate_recovery_parent',return_value={}),patch.object(command.subprocess,'check_output',side_effect=git):
                write(authorization);command.validate(config,inputs,command.RUNTIME)
                for key,value in [('explicit_gpu_go',False),('training_authorized',False),('code_sha','b'*40),
                                  ('independent_review_passed',False),('input_hash','old'),('sources',{}),
                                  ('execution_revision','unreviewed'),('recovery_from_attempt','other-attempt')]:
                    write({**authorization,key:value})
                    with self.assertRaises(ValueError,msg=key):command.validate(config,inputs,command.RUNTIME)
                write(authorization)
                with self.assertRaises(ValueError):command.validate(config,{'changed':True},command.RUNTIME)
                with self.assertRaises(ValueError):command.validate(config,inputs,Path(t))

    def test_command_uses_real_smoke_mode_external_release_and_attempt_output(self):
        config=self.config()
        with tempfile.TemporaryDirectory() as t,patch.object(command,'validate',return_value={}),patch.object(command,'resources'):
            with (Path(t)/'lock').open('a+') as lock:
                argv=command.command(config,{},t,'a'*32,lock.fileno())
                self.assertEqual(argv[0],str(command.INTERPRETER));self.assertEqual(argv[argv.index('--mode')+1],'smoke')
                self.assertEqual(argv[argv.index('--output')+1],str(command.output_path('smoke','a'*32)))
                self.assertIn('--review-release-sha256',argv);self.assertIn('--queue-config-sha256',argv)
        with self.assertRaises(ValueError):command.output_path('smoke','../bad')
        self.assertNotEqual(command.output_path('smoke','a'*32),command.output_path('train','a'*32))

    def test_runner_rejects_unheld_or_wrong_inherited_lock_before_model_import(self):
        with tempfile.TemporaryDirectory() as t,patch.object(command,'RUNTIME',Path(t)):
            with (Path(t)/'gpu.lock').open('a+') as lock,patch.dict(os.environ,SCENEGUARD_GPU_LOCK_FD=str(lock.fileno())):
                with self.assertRaisesRegex(ValueError,'not held'):command.runner_guard(SimpleNamespace())
            with (Path(t)/'other.lock').open('a+') as lock,patch.dict(os.environ,SCENEGUARD_GPU_LOCK_FD=str(lock.fileno())):
                with self.assertRaisesRegex(ValueError,'Wrong'):command.runner_guard(SimpleNamespace())

    def test_migration_private_snapshot_preserves_every_existing_job_and_attempt(self):
        with tempfile.TemporaryDirectory() as t:
            q=Queue.initialize(t)
            with sqlite3.connect('file:'+str(command.RUNTIME/'queue.sqlite3')+'?mode=ro',uri=True) as src,sqlite3.connect(q.db) as dst:
                src.backup(dst)
            before=q.status()
            self.assertGreater(len(before['jobs']),0)
            q.migrate_commands(include_action_train=True);q.migrate_commands(include_action_train=True)
            self.assertEqual(q.status(),before)
            with q.connection() as db:
                self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
                self.assertIn("'action-train'",db.execute("SELECT sql FROM sqlite_master WHERE name='jobs'").fetchone()[0])

    def test_cpu_probe_supervision_inherits_fd_env_and_preserves_prior_jobs(self):
        with tempfile.TemporaryDirectory() as t:
            q=Queue.initialize(t)
            old=q.enqueue(job_key='old',command='cpu-mock',input_value={},config=dict(seconds=0,exit_code=0),
                          run_id='old-run',task_id='old-task',dispatch_id='old-dispatch',owner='old-owner')
            q.supervise_once(old['job_id']);before=q.status()
            config=self.config();config['stage']='smoke'
            with patch.object(command,'validate'):
                job=q.enqueue(job_key=command.job_key(config),command='action-train',input_value={},config=config,timeout=10,**CONTEXT)
            def probe(config,inputs,runtime,attempt,lock_fd):
                script=Path(t)/'probe.py'
                script.write_text('import os\nfd=int(os.environ["SCENEGUARD_GPU_LOCK_FD"])\nos.fstat(fd)\nassert os.environ["CUDA_VISIBLE_DEVICES"] == "0"\n')
                return [sys.executable,str(script)]
            with patch.object(command,'command',side_effect=probe):
                result=q.supervise_once(job['job_id'])
            self.assertEqual(result['status'],'succeeded')
            after=q.status();self.assertEqual(after['jobs'][0],before['jobs'][0]);self.assertEqual(after['attempts'][0],before['attempts'][0])
            receipt=json.loads(Path(after['attempts'][-1]['result_manifest']).read_text())
            self.assertFalse(receipt['synthetic']);self.assertEqual(receipt['registration']['command'],'action-train')
            with self.assertRaisesRegex(ValueError,'separately reviewed'):command.retry_guard(None,job)

    def test_train_requires_actual_matching_smoke_with_full_microbatches(self):
        config=self.config();config['stage']='train'
        with tempfile.TemporaryDirectory() as t:
            settings=Path(t)/'config.json';settings.write_text('{"batch_size":4}')
            config['files']['config']=dict(path=str(settings),sha256=command.file_hash(settings))
            path=Path(t)/'smoke.json'
            result=dict(status='smoke_passed',test_accessed=False,real_train_clips=32,real_validation_clips=4,
                        manifest_sha256=config['files']['manifest']['sha256'],config_sha256=config['files']['config']['sha256'],
                        actual_microbatch_sizes=[4]*8,accumulation=4,optimizer_steps=2)
            def bind(value):
                path.write_text(json.dumps(value));return dict(path=str(path),sha256=command.file_hash(path))
            command.validate_smoke(bind(result),config)
            with self.assertRaisesRegex(ValueError,'smoke'):command.validate_smoke(None,config)
            for key,value in [('actual_microbatch_sizes',[2]),('test_accessed',True),('optimizer_steps',0),('config_sha256','old')]:
                with self.assertRaisesRegex(ValueError,'smoke'):command.validate_smoke(bind({**result,key:value}),config)

    def test_source_hash_includes_adapter_and_trainer(self):
        self.assertEqual(source_hash('action-train'),digest(command.sources()))
        self.assertIn('scripts/train_action_recognizer.py',command.sources())


if __name__=='__main__':unittest.main()
