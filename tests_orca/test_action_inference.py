"""CPU-only fail-closed advisory adapter checks; never modifies the real queue."""
import copy
import fcntl
import hashlib
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

from orchestration import action_inference_command as command
from orchestration.queue import Queue, digest, source_hash

CONTEXT=dict(run_id='run_3d23462a014a',task_id='task-test',dispatch_id='ctx-test',owner='term-test')


class ActionInferenceTests(unittest.TestCase):
    def config(self):
        return dict(stage='all45',context=copy.deepcopy(CONTEXT),
                    files={k:dict(path='/tmp/'+k,sha256='a'*64) for k in command.FILE_KEYS},
                    authorization=dict(path='/tmp/auth',sha256='b'*64))

    def test_live_current_exact_assignment_and_resource_limits_reused(self):
        dispatch=dict(runId=CONTEXT['run_id'],taskId=CONTEXT['task_id'],assigneeHandle=CONTEXT['owner'],
                      status='dispatched',capabilityRevokedAt=None)
        response=dict(ok=True,result=dict(dispatch=dispatch,projection=dict(liveness=dict(verdict='live')),
                                         observation=dict(status='live',exactWorker=True)))
        for change in ({},{'status':'completed'},{'assigneeHandle':'stale'},{'capabilityRevokedAt':'revoked'}):
            data=copy.deepcopy(response);data['result']['dispatch'].update(change)
            with patch.object(command.subprocess,'check_output',return_value=json.dumps(data)):
                if change:
                    with self.assertRaises(ValueError):command.validate_assignment(CONTEXT)
                else:command.validate_assignment(CONTEXT)
        response['result']['projection']['liveness']['verdict']='unverifiable'
        with patch.object(command.subprocess,'check_output',return_value=json.dumps(response)):
            with self.assertRaisesRegex(ValueError,'liveness'):command.validate_assignment(CONTEXT)
        with patch.object(command.subprocess,'check_output',side_effect=subprocess.TimeoutExpired('orca',25)):
            with self.assertRaises(subprocess.TimeoutExpired):command.validate_assignment(CONTEXT)
        for free in (6143,6144):
            with patch.object(command.subprocess,'check_output',return_value=str(free)):
                if free==6143:
                    with self.assertRaisesRegex(ValueError,'6144'):command.resources()
                else:self.assertEqual(command.resources()['free_mib'],6144)

    def test_exact_committed_source_review_standalone_and_root_GO_required(self):
        config=self.config();inputs=dict(selected_sources={'source':'hash'});content=b'owned-source'
        sources={'owned.py':hashlib.sha256(content).hexdigest()}
        authorization=dict(stage='all45',context=CONTEXT,input_hash=digest(inputs),sources=sources,code_sha='a'*40,
            confirmed=True,inference_authorized=True,standalone_evaluation_complete=True,
            independent_review_passed=True,root_go=True,explicit_gpu_go=True)
        def git(argv,**kwargs):return 'a'*40 if argv[1]=='rev-parse' else content
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'auth.json'
            def write(value):
                path.write_text(json.dumps(value));config['authorization']=dict(path=str(path),sha256=command.file_hash(path))
            with patch.object(command,'input_contract',return_value=inputs),patch.object(command,'sources',return_value=sources),\
                 patch.object(command,'validate_assignment'),patch.object(command.subprocess,'check_output',side_effect=git):
                write(authorization);command.validate(config,inputs,command.RUNTIME)
                for key,value in [('root_go',False),('explicit_gpu_go',False),('inference_authorized',False),
                                  ('standalone_evaluation_complete',False),('independent_review_passed',False),
                                  ('sources',{}),('code_sha','b'*40),('input_hash','old')]:
                    write({**authorization,key:value})
                    with self.assertRaises(ValueError,msg=key):command.validate(config,inputs,command.RUNTIME)
                write(authorization)
                with self.assertRaises(ValueError):command.validate(config,{'modified':1},command.RUNTIME)
                with self.assertRaises(ValueError):command.validate(config,inputs,t)
                with self.assertRaises(ValueError):command.validate({**config,'stage':'single-video'},inputs,command.RUNTIME)
                with patch.object(command.subprocess,'check_output',side_effect=lambda argv,**kw:'a'*40 if argv[1]=='rev-parse' else b'dirty'):
                    with self.assertRaisesRegex(ValueError,'committed'):command.validate(config,inputs,command.RUNTIME)

    def test_command_snapshot_and_fresh_attempt_output_no_model_import(self):
        config=self.config()
        with tempfile.TemporaryDirectory() as t,patch.object(command,'validate',return_value={}),patch.object(command,'resources'):
            with (Path(t)/'lock').open('a+') as lock:
                argv=command.command(config,{},t,'a'*32,lock.fileno())
                self.assertEqual(argv[:2],[str(command.INTERPRETER),'-I'])
                self.assertEqual(argv[argv.index('--output')+1],str(command.output_path('all45','a'*32)))
                self.assertIn('--queue-config-sha256',argv)
                with self.assertRaises(FileExistsError):command.command(config,{},t,'a'*32,lock.fileno())
        for stage,attempt in [('train','a'*32),('all45','../bad')]:
            with self.assertRaises(ValueError):command.output_path(stage,attempt)
        with self.assertRaisesRegex(ValueError,'separately reviewed'):command.retry_guard(None,None)

    def test_unheld_wrong_or_absent_fd_fails_before_input_or_model_access(self):
        with tempfile.TemporaryDirectory() as t,patch.object(command,'RUNTIME',Path(t)):
            with (Path(t)/'gpu.lock').open('a+') as lock,patch.dict(os.environ,SCENEGUARD_GPU_LOCK_FD=str(lock.fileno())):
                with self.assertRaisesRegex(ValueError,'not held'):command.runner_guard(SimpleNamespace())
            with (Path(t)/'other.lock').open('a+') as lock,patch.dict(os.environ,SCENEGUARD_GPU_LOCK_FD=str(lock.fileno())):
                with self.assertRaisesRegex(ValueError,'Wrong'):command.runner_guard(SimpleNamespace())

    def test_actual_running_readonly_queue_row_and_held_inherited_fd_required(self):
        config=self.config();inputs=dict(source='bound');attempt='a'*32
        with tempfile.TemporaryDirectory() as t,patch.object(command,'RUNTIME',Path(t)):
            runtime=Path(t);directory=runtime/'attempts'/attempt;directory.mkdir(parents=True)
            snapshot=directory/'action-inference-config.json';snapshot.write_text(json.dumps(config))
            args=SimpleNamespace(queue_config=snapshot,queue_config_sha256=command.file_hash(snapshot),
                                 queue_attempt=attempt,output=command.output_path('all45',attempt))
            row=dict(command='action-infer',status='running',config_json=json.dumps(config),config_hash=digest(config),
                input_json=json.dumps(inputs),input_hash=digest(inputs),source_hash=digest(command.sources()),
                job_key=command.job_key(config),code_sha='c'*40,**CONTEXT)
            with sqlite3.connect(runtime/'queue.sqlite3') as db:
                columns=','.join(k+' TEXT' for k in row)
                db.execute('CREATE TABLE jobs(job_id TEXT,'+columns+')')
                db.execute('CREATE TABLE attempts(job_id TEXT,attempt_id TEXT,status TEXT,supervisor_pid INTEGER,supervisor_identity TEXT)')
                db.execute('INSERT INTO jobs VALUES ('+','.join('?' for _ in range(len(row)+1))+')',['job',*row.values()])
                db.execute('INSERT INTO attempts VALUES (?,?,?,?,?)',['job',attempt,'running',123,'identity'])
            before=command.file_hash(runtime/'queue.sqlite3')
            with (runtime/'gpu.lock').open('a+') as lock,\
                 patch.dict(os.environ,SCENEGUARD_GPU_LOCK_FD=str(lock.fileno()),CUDA_VISIBLE_DEVICES='0'),\
                 patch.object(command,'validate',return_value=dict(authorization=dict(code_sha='c'*40))),\
                 patch.object(command,'resources'),patch.object(command,'process_state',return_value='live'),\
                 patch('orchestration.queue.source_hash',return_value=digest(command.sources())):
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                self.assertEqual(command.runner_guard(args),(config,inputs))
                self.assertEqual(command.file_hash(runtime/'queue.sqlite3'),before)
                # Current queue remains unregistered, so fallback source hashes must fail closed.
                with patch('orchestration.queue.source_hash',return_value='unregistered'):
                    with self.assertRaisesRegex(ValueError,'running'):command.runner_guard(args)
                with patch.object(command,'process_state',return_value='unknown'):
                    with self.assertRaisesRegex(ValueError,'running'):command.runner_guard(args)
                with patch.dict(os.environ,CUDA_VISIBLE_DEVICES='1'):
                    with self.assertRaisesRegex(ValueError,'GPU0'):command.runner_guard(args)
                for key,value in [('status','succeeded'),('command','action-train'),('input_hash','changed'),
                                  ('config_hash','changed'),('source_hash','changed'),('owner','stale'),('code_sha','old')]:
                    with sqlite3.connect(runtime/'queue.sqlite3') as db:db.execute('UPDATE jobs SET '+key+'=?',(value,))
                    with self.assertRaises(ValueError,msg=key):command.runner_guard(args)
                    with sqlite3.connect(runtime/'queue.sqlite3') as db:db.execute('UPDATE jobs SET '+key+'=?',(row[key],))

    def test_standalone_requires_completed_ten_epochs_test_and_selected_checkpoint(self):
        config=self.config();module=command.planner()
        with tempfile.TemporaryDirectory() as t,patch.object(command,'ROOT',Path(t)),patch.object(command,'RUNTIME',Path(t)/'queue'),patch.object(command,'planner',return_value=module):
            train=Path(t)/'outputs/action-recognition/exp0063/queued-training/train'/('b'*32);train.mkdir(parents=True)
            paths={k:train/name for k,name in [('training_result','result.json'),('checkpoint','best.pt'),
                     ('training_history','history.json'),('test_scores','test-scores.json'),
                     ('training_config','config.json'),('training_manifest','manifest.json')]}
            paths['training_receipt']=command.RUNTIME/'attempts'/train.name/'manifest.json';paths['training_receipt'].parent.mkdir(parents=True)
            paths['training_queue_config']=paths['training_receipt'].parent/'action-training-config.json'
            snapshot=dict(stage='train',files={key:config['files'][name] for key,name in
                          (('manifest','training_manifest'),('config','training_config'),('baseline_lock','baseline_lock'))})
            paths['training_queue_config'].write_text(json.dumps(snapshot))
            history=[dict(epoch=i,validation_loss=10-i if i<7 else i) for i in range(1,11)]
            test_rows=[dict(clip_id='test'+str(i),label=i,split='test',location='place',source_id='s'+str(i),event_group='g'+str(i)) for i in range(2)]
            scores=[dict(clip_id='test0',label=0,score=.1),dict(clip_id='test1',label=1,score=.9)]
            result=dict(status='trained',best_epoch=6,test=command.trainer().evaluation_report(scores,test_rows,set()),weights_sha256='a'*64)
            settings=json.loads((Path(__file__).resolve().parents[1]/'configs/exp0063_action_training.json').read_text())
            receipt=dict(execution_status='succeeded',synthetic=False,registration=dict(command='action-train',config_hash=digest(snapshot)),
                         attempt_id=train.name,result_path=str(train))
            values=dict(training_result=result,training_history=history,test_scores=scores,training_config=settings,
                        training_manifest=dict(baseline_lock_sha256=module.LOCK_SHA,config_sha256='a'*64,clips=test_rows),training_receipt=receipt)
            for k,v in values.items():paths[k].write_text(json.dumps(v))
            self.assertEqual(command.standalone_contract(paths,config)['selected_epoch'],6)
            for key,value in [('status','smoke_passed'),('best_epoch',8),('test',{}),('weights_sha256','wrong')]:
                paths['training_result'].write_text(json.dumps({**result,key:value}))
                with self.assertRaises(ValueError):command.standalone_contract(paths,config)
            paths['training_result'].write_text(json.dumps(result))
            paths['training_history'].write_text(json.dumps(history[:-1]))
            with self.assertRaises(ValueError):command.standalone_contract(paths,config)
            paths['training_history'].write_text(json.dumps(history))
            for invalid in ([],scores[:1],[scores[0],scores[0]],[{**scores[0],'label':1},scores[1]],
                            [{**scores[0],'score':float('nan')},scores[1]],[{**scores[0],'score':1.1},scores[1]]):
                paths['test_scores'].write_text(json.dumps(invalid))
                with self.assertRaises(ValueError):command.standalone_contract(paths,config)
            paths['test_scores'].write_text(json.dumps(scores))
            for key in ('manifest','config','baseline_lock'):
                altered=copy.deepcopy(snapshot);altered['files'][key]['sha256']='wrong'
                paths['training_queue_config'].write_text(json.dumps(altered))
                # Also update receipt to ensure mismatched input bindings themselves are rejected.
                altered_receipt=copy.deepcopy(receipt);altered_receipt['registration']['config_hash']=digest(altered)
                paths['training_receipt'].write_text(json.dumps(altered_receipt))
                with self.assertRaisesRegex(ValueError,'contract differs'):command.standalone_contract(paths,config)
            paths['training_queue_config'].write_text(json.dumps(snapshot));paths['training_receipt'].write_text(json.dumps(receipt))
            wrong=dict(values['training_manifest'],config_sha256='wrong')
            paths['training_manifest'].write_text(json.dumps(wrong))
            with self.assertRaisesRegex(ValueError,'baseline/config'):command.standalone_contract(paths,config)

    def test_all45_plan_recomputation_and_actual_selected_source_hash_verification(self):
        config=self.config();real=command.planner()
        with tempfile.TemporaryDirectory() as t:
            folder=Path(t);output=folder/'plan';output.mkdir();lock=folder/'baseline.json'
            originals=[dict(video_id=f'E01_{i:03d}') for i in range(1,46)]
            lock.write_text(json.dumps(dict(regression_only_videos=originals,verified_paths={'/huge/unused/archive':'not-read'})))
            expected={};entries=[]
            for e in originals:
                video=folder/(e['video_id']+'.mp4');video.write_bytes(e['video_id'].encode())
                row=dict(video_id=e['video_id'],input_hashes={str(video):command.file_hash(video)},baseline_hashes={})
                expected[e['video_id']]=row;path=output/(e['video_id']+'.json');path.write_text(json.dumps(row))
                entries.append(dict(video_id=e['video_id'],path=str(path),sha256=command.file_hash(path)))
            module=SimpleNamespace(OUTPUT=output,LOCK=lock,LOCK_SHA=command.file_hash(lock),POLICY=real.POLICY,
                                   source_plan=lambda e,l:expected[e['video_id']])
            manifest=dict(policy=real.POLICY,ground_truth_used=False,baseline_lock=dict(path=str(lock),sha256=module.LOCK_SHA),
                          status='cpu_plan_only_no_inference',videos=entries)
            path=output/'manifest.json';path.write_text(json.dumps(manifest))
            for name in config['files']:
                f=path if name=='manifest' else lock if name=='baseline_lock' else folder/(name+'.json')
                if name not in ('manifest','baseline_lock'):f.write_text('{}')
                config['files'][name]=dict(path=str(f),sha256=command.file_hash(f))
            with patch.object(command,'planner',return_value=module),patch.object(command,'standalone_contract',return_value={}):
                result=command.input_contract(config)
                self.assertEqual(len(result['selected_sources']),45)
                # Actual selected media must be verified; historical unrelated archives are not rehashed.
                changed=folder/'E01_007.mp4';changed.write_bytes(b'changed-source')
                with self.assertRaisesRegex(ValueError,'input'):command.input_contract(config)
                changed.write_bytes(b'E01_007')
                # Even a newly hash-bound altered plan must equal the independently recomputed observation plan.
                entry=entries[6];plan_path=Path(entry['path']);forged={**expected['E01_007'],'forged_window':True}
                plan_path.write_text(json.dumps(forged));entry['sha256']=command.file_hash(plan_path)
                path.write_text(json.dumps(manifest));config['files']['manifest']['sha256']=command.file_hash(path)
                with self.assertRaisesRegex(ValueError,'plan changed'):command.input_contract(config)

    def test_private_canonical_snapshot_migration_preserves_all_prior_rows(self):
        with tempfile.TemporaryDirectory() as t:
            q=Queue.initialize(t)
            with sqlite3.connect('file:'+str(command.RUNTIME/'queue.sqlite3')+'?mode=ro',uri=True) as src,sqlite3.connect(q.db) as dst:
                src.backup(dst)
            before=q.status()
            self.assertGreaterEqual(len(before['jobs']),95)
            q.migrate_commands(include_action_infer=True);q.migrate_commands(include_action_infer=True)
            q.migrate_commands(include_action_train=True)
            self.assertEqual(q.status(),before)
            with q.connection() as db:
                self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
                schema=db.execute("SELECT sql FROM sqlite_master WHERE name='jobs'").fetchone()[0]
                self.assertIn("'action-infer'",schema);self.assertIn("'action-train'",schema)
            self.assertEqual(len(list(Path(t).glob('queue-before-action-infer-*.sqlite3'))),1)

    def test_private_supervisor_fd_env_receipt_preserves_old_job_and_no_implicit_retry(self):
        with tempfile.TemporaryDirectory() as t:
            q=Queue.initialize(t)
            old=q.enqueue(job_key='old',command='cpu-mock',input_value={},config=dict(seconds=0,exit_code=0),
                          run_id='old-run',task_id='old-task',dispatch_id='old-dispatch',owner='old-owner')
            q.supervise_once(old['job_id']);before=q.status();config=self.config()
            with patch.object(command,'validate'):
                job=q.enqueue(job_key=command.job_key(config),command='action-infer',input_value={},config=config,timeout=10,**CONTEXT)
                with self.assertRaisesRegex(ValueError,'assignment'):
                    q.enqueue(job_key=command.job_key(config),command='action-infer',input_value={},config=config,timeout=10,
                              **{**CONTEXT,'owner':'stale'})
                with self.assertRaisesRegex(ValueError,'3600'):
                    q.enqueue(job_key=command.job_key(config),command='action-infer',input_value={},config=config,timeout=3601,**CONTEXT)
            def probe(config,inputs,runtime,attempt,lock_fd):
                script=Path(t)/'probe.py'
                script.write_text('import os,fcntl,pathlib\nfd=int(os.environ["SCENEGUARD_GPU_LOCK_FD"])\n'
                    'held=os.fstat(fd)\nassert os.environ["CUDA_VISIBLE_DEVICES"] == "0"\n'
                    'path=pathlib.Path('+repr(str(Path(t)/'gpu.lock'))+')\n'
                    'actual=path.stat()\nassert (actual.st_dev,actual.st_ino)==(held.st_dev,held.st_ino)\n'
                    'with path.open("a+") as p:\n'
                    ' try: fcntl.flock(p,fcntl.LOCK_EX|fcntl.LOCK_NB)\n'
                    ' except BlockingIOError: pass\n'
                    ' else: raise AssertionError("not held")\n')
                return [sys.executable,str(script)]
            with patch.object(command,'command',side_effect=probe):result=q.supervise_once(job['job_id'])
            self.assertEqual(result['status'],'succeeded')
            after=q.status();self.assertEqual(after['jobs'][0],before['jobs'][0]);self.assertEqual(after['attempts'][0],before['attempts'][0])
            receipt=json.loads(Path(after['attempts'][-1]['result_manifest']).read_text())
            self.assertFalse(receipt['synthetic']);self.assertEqual(receipt['registration']['command'],'action-infer')
            self.assertEqual(receipt['result_path'],str(command.output_path('all45',receipt['attempt_id'])))
            failed=self.config();failed['files']['checkpoint']['sha256']='c'*64
            with patch.object(command,'validate'):
                second=q.enqueue(job_key=command.job_key(failed),command='action-infer',input_value={},config=failed,timeout=10,**CONTEXT)
            with patch.object(command,'command',return_value=[sys.executable,'-c','raise SystemExit(1)']):
                self.assertEqual(q.supervise_once(second['job_id'])['status'],'failed')
            with self.assertRaisesRegex(ValueError,'separately reviewed'):q.retry(second['job_id'])

    def test_private_migration_rejects_held_reservation_or_unknown_job(self):
        with tempfile.TemporaryDirectory() as t:
            q=Queue.initialize(t)
            with q.gpu_lock():
                with self.assertRaisesRegex(ValueError,'reservation'):q.migrate_commands(include_action_infer=True)
            old=q.enqueue(job_key='unknown',command='cpu-mock',input_value={},config=dict(seconds=0,exit_code=0),
                          run_id='r',task_id='t',dispatch_id='d',owner='o')
            with q.connection() as db:db.execute("UPDATE jobs SET status='unknown' WHERE job_id=?",(old['job_id'],))
            before=q.status()
            with self.assertRaisesRegex(ValueError,'unresolved'):q.migrate_commands(include_action_infer=True)
            self.assertEqual(q.status(),before)

    def test_sources_bind_runtime_decode_builder_trainer_and_tests(self):
        expected={'orchestration/queue.py','scripts/infer_action_regression.py','scripts/prepare_action_regression.py',
                  'scripts/train_action_recognizer.py','scripts/build_action_training_clips.py',
                  'orchestration/action_training_command.py','tests/test_action_regression.py','tests_orca/test_action_inference.py'}
        self.assertTrue(expected.issubset(command.sources()))
        self.assertEqual(source_hash('action-infer'),digest(command.sources()))


if __name__=='__main__':unittest.main()
