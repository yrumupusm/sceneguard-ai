"""Canonical head guards and optional frozen metadata; never mutate the real queue."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from orchestration import comparison_head_command as command
from orchestration.queue import digest


class PreparedAliasTests(unittest.TestCase):
    def test_only_previously_verified_same_byte_alias_keeps_geometry_and_hash(self):
        proof=dict(source_path='canonical.mp4',source_sha256='a'*64,source_size=[1920,1080],time_base='1/12288')
        window={**proof,'source_path':'alias.mp4'}
        aliases={'alias.mp4':'a'*64}
        command.validate_prepared_window(window,proof,aliases)
        command.validate_prepared_window(proof,proof,{})
        for bad_aliases in ({},{'alias.mp4':'b'*64}):
            with self.assertRaisesRegex(ValueError,'verified same-byte alias'):
                command.validate_prepared_window(window,proof,bad_aliases)
        for field,value in [('source_sha256','b'*64),('source_size',[1080,1920]),('time_base','1/30')]:
            with self.assertRaisesRegex(ValueError,'geometry/clock/hash'):
                command.validate_prepared_window({**window,field:value},proof,aliases)

    @unittest.skipUnless(command.PLAN.is_file(),'Frozen local preparation is not present')
    def test_actual_frozen_alias_windows_use_their_own_prepared_binding(self):
        command.checked_file(dict(path=str(command.PLAN),sha256=command.PLAN_SHA))
        preparation=command.ROOT/'outputs/model-comparison/exp0066/head-preparation/native-v2/review-ready.json'
        command.checked_file(dict(path=str(preparation),sha256='2a0e0c3f71d273a68229e8982b5cd3967c8b5117d8a46f17642592611cb0bb28'))
        prepared=command.read(preparation)
        proofs={}
        for b in prepared['sources']:
            proof=command.read(command.checked_file({k:b[k] for k in ('path','sha256')}))
            proofs[proof['source_sha256']]=proof
        aliases=prepared['source_alias_bindings'];count=0
        for window in command.read(command.PLAN)['windows']:
            proof=proofs[window['source_sha256']]
            command.validate_prepared_window(window,proof,aliases)
            if window['source_path']!=proof['source_path']:
                count+=1
                with self.assertRaisesRegex(ValueError,'verified same-byte alias'):
                    command.validate_prepared_window(window,proof,{})
        self.assertEqual(count,22)


class HeadCommandTests(unittest.TestCase):
    def test_wrong_or_unheld_fd_stops_before_model_or_queue_access(self):
        with tempfile.TemporaryDirectory() as t,patch.object(command,'RUNTIME',Path(t)):
            for name,pattern in [('gpu.lock','not held'),('other.lock','Wrong')]:
                with (Path(t)/name).open('a+') as lock,patch.dict(os.environ,SCENEGUARD_GPU_LOCK_FD=str(lock.fileno())):
                    with self.assertRaisesRegex(ValueError,pattern):command.runner_guard(SimpleNamespace())

    def test_source_head_input_review_context_and_live_assignment(self):
        context=dict(run_id='run_3d23462a014a',task_id='t',dispatch_id='d',owner='o')
        config=dict(stage='feature-smoke',model_id='vjepa2_l',execution_revision='v1',context=context,files={})
        source={'code.py':hashlib.sha256(b'code').hexdigest()};inputs={'f':'h'}
        auth=dict(stage=config['stage'],model_id=config['model_id'],execution_revision='v1',context=context,
                  input_hash=digest(inputs),sources=source,code_sha='a'*40,confirmed=True,head_authorized=True,
                  independent_review_passed=True,root_go=True,explicit_gpu_go=True)
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'auth.json'
            def write(value):
                path.write_text(json.dumps(value));config['authorization']=dict(path=str(path),sha256=command.file_hash(path))
            with patch.object(command,'input_contract',return_value=inputs),patch.object(command,'sources',return_value=source),\
                 patch.object(command,'validate_assignment',return_value={}) as live,\
                 patch.object(command.subprocess,'check_output',side_effect=lambda argv,**kw:'a'*40 if argv[1]=='rev-parse' else b'code'):
                write(auth);command.validate(config,inputs,command.RUNTIME);live.assert_called_with(context)
                for key,value in [('root_go',False),('explicit_gpu_go',False),('independent_review_passed',False),
                                  ('input_hash','changed'),('sources',{}),('code_sha','b'*40),('context',{}),('model_id','evad_vitl')]:
                    write({**auth,key:value})
                    with self.assertRaises(ValueError,msg=key):command.validate(config,inputs,command.RUNTIME)
                write(auth)
                with self.assertRaises(ValueError):command.validate(config,{'changed':True},command.RUNTIME)
                with self.assertRaises(ValueError):command.validate(config,inputs,t)
                live.side_effect=ValueError('stale dispatch')
                with self.assertRaisesRegex(ValueError,'stale'):command.validate(config,inputs,command.RUNTIME)

    def test_full_and_cpu_train_require_actual_canonical_predecessors(self):
        context=dict(run_id='run_3d23462a014a',task_id='t',dispatch_id='d',owner='o');source={};inputs={}
        with tempfile.TemporaryDirectory() as t,patch.object(command,'sources',return_value=source),\
             patch.object(command,'input_contract',return_value=inputs),patch.object(command,'validate_assignment',return_value={}),\
             patch.object(command.subprocess,'check_output',return_value='a'*40),\
             patch.object(command,'canonical_proof',side_effect=ValueError('missing actual predecessor')) as proof:
            for stage in ('feature-full','train'):
                config=dict(stage=stage,model_id='vjepa2_l',execution_revision='v1',context=context,files={})
                auth=dict(stage=stage,model_id='vjepa2_l',execution_revision='v1',context=context,input_hash=digest(inputs),
                          sources=source,code_sha='a'*40,confirmed=True,head_authorized=True,independent_review_passed=True,
                          root_go=True,explicit_gpu_go=True,cpu_training_authorized=True,smoke_result={},smoke_receipt={},feature_result={},feature_receipt={})
                path=Path(t)/'auth';path.write_text(json.dumps(auth));config['authorization']=dict(path=str(path),sha256=command.file_hash(path))
                with self.assertRaisesRegex(ValueError,'predecessor'):command.validate(config,inputs,command.RUNTIME)
                self.assertEqual(proof.call_args.args[2],'feature-smoke' if stage=='feature-full' else 'feature-full')

    def test_actual_running_row_snapshot_owner_hashes_supervisor_and_device(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);attempt='a'*32;directory=root/'attempts'/attempt;directory.mkdir(parents=True)
            context=dict(run_id='r',task_id='t',dispatch_id='d',owner='o')
            config=dict(stage='feature-smoke',model_id='vjepa2_l',execution_revision='v1',context=context,files={})
            snapshot=directory/'comparison-head-config.json';snapshot.write_text(json.dumps(config));inputs={'exact':'input'}
            values=dict(command='comparison-head',status='running',attempt_status='running',supervisor_pid=12,supervisor_identity='identity',
                        config_json=json.dumps(config),config_hash=digest(config),input_json=json.dumps(inputs),input_hash=digest(inputs),
                        source_hash=digest({'code':'h'}),job_key=command.job_key(config),code_sha='c',**context)
            with sqlite3.connect(root/'queue.sqlite3') as db:
                db.execute('CREATE TABLE jobs (job_id TEXT, '+','.join(k+' TEXT' for k in values if k not in ('attempt_status','supervisor_pid','supervisor_identity'))+')')
                db.execute('CREATE TABLE attempts (job_id TEXT,attempt_id TEXT,status TEXT,supervisor_pid INTEGER,supervisor_identity TEXT)')
                fields={k:v for k,v in values.items() if k not in ('attempt_status','supervisor_pid','supervisor_identity')}
                db.execute('INSERT INTO jobs VALUES ('+','.join('?' for _ in range(len(fields)+1))+')',['job',*fields.values()])
                db.execute('INSERT INTO attempts VALUES (?,?,?,?,?)',('job',attempt,'running',12,'identity'))
            args=SimpleNamespace(queue_config=str(snapshot),queue_config_sha256=command.file_hash(snapshot),queue_attempt=attempt,output=root/'out')
            with (root/'gpu.lock').open('a+') as lock,patch.dict(os.environ,SCENEGUARD_GPU_LOCK_FD=str(lock.fileno()),CUDA_VISIBLE_DEVICES='0'),\
                 patch.object(command,'RUNTIME',root),patch.object(command,'output_path',return_value=args.output),\
                 patch.object(command,'validate',return_value={'authorization':{'code_sha':'c'}}),\
                 patch.object(command,'sources',return_value={'code':'h'}),patch.object(command,'process_state',return_value='live') as state,\
                 patch.object(command,'resources'):
                fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
                self.assertEqual(command.runner_guard(args),(config,inputs))
                for key,value in [('status','succeeded'),('command','model-compare'),('owner','wrong'),('dispatch_id','old'),
                                  ('config_hash','changed'),('source_hash','changed'),('input_hash','changed'),('code_sha','changed'),('job_key','changed')]:
                    with sqlite3.connect(root/'queue.sqlite3') as db:db.execute('UPDATE jobs SET '+key+'=?',(value,))
                    with self.assertRaises(ValueError,msg=key):command.runner_guard(args)
                    with sqlite3.connect(root/'queue.sqlite3') as db:db.execute('UPDATE jobs SET '+key+'=?',(values[key],))
                state.return_value='dead'
                with self.assertRaises(ValueError):command.runner_guard(args)
                state.return_value='live'
                with patch.dict(os.environ,CUDA_VISIBLE_DEVICES=''):
                    with self.assertRaisesRegex(ValueError,'visibility'):command.runner_guard(args)
                args.queue_config_sha256='changed'
                with self.assertRaisesRegex(ValueError,'snapshot changed'):command.runner_guard(args)

    def test_no_arbitrary_path_stage_r3d_or_retry(self):
        for stage,attempt in [('other','a'*32),('train','../bad')]:
            with self.assertRaises(ValueError):command.output_path(stage,attempt)
        for model in ('r3d18_exp0064','unknown'):
            with self.assertRaises(ValueError):command.input_contract(dict(stage='feature-smoke',model_id=model,files={}))
        with self.assertRaises(ValueError):command.retry_guard(None,None)

    def test_standalone_entry_rejects_before_adapter_load_or_output_creation(self):
        from scripts.extract_comparison_head_features import main
        with tempfile.TemporaryDirectory() as t,patch.object(command,'runner_guard',side_effect=ValueError('no canonical job')),\
             patch('scripts.run_model_comparison.load_adapter') as adapter:
            output=Path(t)/'output'
            with self.assertRaisesRegex(ValueError,'canonical job'):
                main(['--queue-config','/untrusted','--queue-config-sha256','x','--queue-attempt','x','--output',str(output)])
            adapter.assert_not_called();self.assertFalse(output.exists())



class Utf8Tests(unittest.TestCase):
    def test_non_ascii_head_json_survives_ascii_process_locale(self):
        import subprocess
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'data.json';path.write_text('{"value":"한글"}',encoding='utf-8')
            code="from orchestration.comparison_head_command import read; from scripts.prepare_comparison_head_data import read as prep; import sys; assert read(sys.argv[1])['value']==prep(sys.argv[1])['value']=='\\ud55c\\uae00'"
            env={**os.environ,'LC_ALL':'C','LC_CTYPE':'C','PYTHONUTF8':'0','PYTHONCOERCECLOCALE':'0','CUDA_VISIBLE_DEVICES':''}
            result=subprocess.run([str(command.ROOT/'.venv-exp0066-joint/bin/python'),'-c',code,str(path)],cwd=command.ROOT,env=env,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr.decode('utf-8'))

class CanonicalPredecessorTests(unittest.TestCase):
    def test_receipt_cannot_replace_real_success_row_and_native_bytes(self):
        from scripts.extract_comparison_head_features import representations,audit_native_outputs
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);attempt='b'*32;out=root/'output';out.mkdir();receipt_dir=root/'attempts'/attempt;receipt_dir.mkdir(parents=True)
            plan={'windows':[dict(window_id=str(i),split='train' if i<2 else 'validation',label=i%2,source_sha256='s') for i in range(4)]}
            plan_path=root/'plan.json';plan_path.write_text(json.dumps(plan),encoding='utf-8')
            base={k:dict(path=str(plan_path),sha256=command.file_hash(plan_path)) for k in command.BASE_FILES}
            config=dict(stage='feature-full',model_id='vjepa2_l',execution_revision='v1',context=dict(run_id='r',task_id='t',dispatch_id='d',owner='o'),files=base)
            old={**config,'stage':'feature-smoke'};prior_inputs={'bound':'input'}
            with (out/'features.jsonl').open('w',encoding='utf-8') as features,(out/'native-outputs.jsonl').open('w',encoding='utf-8') as native:
                for w in plan['windows']:
                    output={'pooled_features':[float(w['label']),2.]};samples,coverage=representations(w,output,False)
                    row=dict(window_id=w['window_id'],split=w['split'],source_sha256='s',samples=samples,coverage=coverage,
                             model_output_sha256=hashlib.sha256(json.dumps(output,sort_keys=True,allow_nan=False).encode()).hexdigest())
                    features.write(json.dumps(row)+'\n');native.write(json.dumps(dict(window_id=w['window_id'],output=output))+'\n')
            coverage=audit_native_outputs(out/'native-outputs.jsonl',out/'features.jsonl',plan,False)
            proof=dict(status='feature_smoke_passed',stage='feature-smoke',queue_command='comparison-head',queue_attempt=attempt,
                       model_id='vjepa2_l',source_hash=digest({}),input_hash=digest(prior_inputs),code_sha='c',
                       model_spec_sha256=base['model_spec']['sha256'],plan_sha256='plan',
                       features_sha256=command.file_hash(out/'features.jsonl'),native_outputs_sha256=command.file_hash(out/'native-outputs.jsonl'),
                       feature_dimension=2,windows=4,window_ids=['0','1','2','3'],coverage_by_split=coverage)
            proof_path=out/'result.json';proof_path.write_text(json.dumps(proof),encoding='utf-8')
            registration=dict(command='comparison-head',job_id='job',run_id='r',task_id='t',dispatch_id='d',owner='o',
                              code_sha='c',source_hash=digest({}),input_hash=digest(prior_inputs),config_hash=digest(old))
            receipt=dict(execution_status='succeeded',attempt_id=attempt,result_sha256=command.file_hash(proof_path),result_path=str(out),registration=registration)
            receipt_path=receipt_dir/'manifest.json';receipt_path.write_text(json.dumps(receipt),encoding='utf-8')
            bind=lambda p:dict(path=str(p),sha256=command.file_hash(p))
            with sqlite3.connect(root/'queue.sqlite3') as db:
                db.execute('CREATE TABLE jobs ('+','.join(k+' TEXT' for k in [*registration,'status','config_json','input_json'])+')')
                db.execute('CREATE TABLE attempts (job_id TEXT,attempt_id TEXT,status TEXT,result_manifest TEXT)')
            with patch.object(command,'RUNTIME',root),patch.object(command,'output_path',return_value=out),\
                 patch.object(command,'PLAN_SHA','plan'),patch.object(command,'sources',return_value={}),\
                 patch.object(command,'selected_windows',return_value=plan['windows']):
                with self.assertRaisesRegex(ValueError,'Actual successful'):
                    command.canonical_proof(bind(proof_path),bind(receipt_path),'feature-smoke',config)
                with sqlite3.connect(root/'queue.sqlite3') as db:
                    db.execute('INSERT INTO jobs VALUES ('+','.join('?' for _ in range(len(registration)+3))+')',
                               [*registration.values(),'succeeded',json.dumps(old),json.dumps(prior_inputs)])
                    db.execute('INSERT INTO attempts VALUES (?,?,?,?)',('job',attempt,'succeeded',str(receipt_path)))
                self.assertEqual(command.canonical_proof(bind(proof_path),bind(receipt_path),'feature-smoke',config)[0],out/'features.jsonl')
                (out/'native-outputs.jsonl').write_text('',encoding='utf-8')
                with self.assertRaisesRegex(ValueError,'native outputs changed'):
                    command.canonical_proof(bind(proof_path),bind(receipt_path),'feature-smoke',config)


if __name__=='__main__':unittest.main()
