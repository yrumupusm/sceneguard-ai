"""CPU/fake tests: no Torch import, GPU, model construction or generation."""
import copy
import fcntl
import sqlite3
import importlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from orchestration import batch02_vlm_command as c
from batch02_vlm import runner,evaluate
from orchestration.queue import digest,process_identity


class FrozenContract(unittest.TestCase):
    def test_matrix_smoke_and_baseline(self):
        d=c.manifest()
        self.assertEqual(len(d['conditions']),16)
        self.assertEqual(len(set(c.CONDITIONS)),16)
        self.assertEqual(len(set(c.CONDITIONS)-set(c.SMOKE)),14)
        self.assertEqual(len({r['condition_id'].split('_')[0] for r in d['conditions']}),10)
        for r in d['conditions']:
            if r['condition_id'].startswith('q'):
                self.assertIn('EXP-0012',r['baseline_result'])
                self.assertIsNone(r['parity_prompt'])
            else:
                self.assertIn('independent-original',r['baseline_result'])
                self.assertNotIn('revised',r['baseline_result'])
                self.assertIsNotNone(r['parity_prompt'])

    def test_manifest_tampering(self):
        original=c.manifest()
        for key,value in [('settings',{}),('prompt_sha256','0'*64),('processor_size',{}),('smoke',['q01_B'])]:
            changed=copy.deepcopy(original);changed[key]=value
            with patch.object(Path,'read_text',return_value=json.dumps(changed)),self.assertRaises(ValueError):
                c.manifest()
        changed=copy.deepcopy(original);changed['conditions'][0]['expected_metadata']['processor_frames']=8
        with patch.object(Path,'read_text',return_value=json.dumps(changed)),self.assertRaises(ValueError):
            c.manifest()

    def test_fixed_paths(self):
        for condition,attempt in [('q99_B','a'*32),('q04_C','../bad'),('q04_C','g'*32)]:
            with self.assertRaises(ValueError):c.output_path(condition,attempt)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'out').symlink_to('/tmp')
            with patch.object(c,'ROOT',root),self.assertRaises(ValueError):c.safe_file('out/result')

    def test_config_runtime_and_input(self):
        for cfg in ({},dict(condition_id='q04_C',settings={}),dict(condition_id='q04_C',settings=c.SETTINGS,path='/tmp')):
            with self.assertRaises(ValueError):c.validate(cfg,{},c.RUNTIME)
        cfg=dict(condition_id='q04_C',settings=c.SETTINGS)
        with self.assertRaises(ValueError):c.validate(cfg,{},'/tmp')
        with patch.object(c,'input_contract',return_value={'frozen':True}),self.assertRaises(ValueError):c.validate(cfg,{},c.RUNTIME)

    def test_sequence_success_cannot_regenerate(self):
        with patch.object(c,'successful',return_value=[]),patch.object(c,'prior_generated_tokens',return_value=[]):
            c.sequence_gate('q04_C')
            for condition in ('q05_B','q01_B'):
                with self.assertRaises(ValueError):c.sequence_gate(condition)
        with patch.object(c,'successful',side_effect=lambda k:['old'] if k in c.SMOKE else []),patch.object(c,'prior_generated_tokens',return_value=[]):
            c.sequence_gate('q01_B')
            with self.assertRaises(ValueError):c.sequence_gate('q04_C')

    def test_saved_tokens_block_regeneration_after_write_failure(self):
        with patch.object(c,'successful',return_value=[]),patch.object(c,'prior_generated_tokens',return_value=['failed-attempt']):
            with self.assertRaisesRegex(ValueError,'CPU recovery'):c.sequence_gate('q04_C')

    def test_assignment_freeze(self):
        a=dict(run_id='run',task_id='task',dispatch_id='dispatch',confirmed=True,sources={'x':'y'})
        with patch.object(Path,'read_text',return_value=json.dumps(a)),patch.object(c,'sources',return_value={'x':'y'}):
            c.validate_assignment('run','task','dispatch')
            with self.assertRaises(ValueError):c.validate_assignment('run','task','stale')
        with patch.object(Path,'read_text',return_value=json.dumps(a)),patch.object(c,'sources',return_value={}):
            with self.assertRaises(ValueError):c.validate_assignment('run','task','dispatch')

    def test_frozen_source_environment_and_weight_input_mutations(self):
        from orchestration.vlm_command import file_hash
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);local=root/'runtime';local.mkdir();model=root/'weights';model.mkdir()
            (root/'python').write_bytes(b'python');(root/'input').write_bytes(b'input');(root/'installed').write_bytes(b'package');(model/'shard').write_bytes(b'weights')
            env=local/'environment.json';env.write_text(json.dumps({'files':{'installed':file_hash(root/'installed')}}))
            frozen=dict(pins={},environment=dict(status='installed_verified',interpreter_sha256=file_hash(root/'python'),files={'runtime/environment.json':file_hash(env)}),conditions=[dict(condition_id='q04_C',files={'input':file_hash(root/'input')})],model=dict(files={'shard':dict(sha256=file_hash(model/'shard'))}))
            mp=root/'manifest.json';mp.write_text('{}')
            with patch.object(c,'ROOT',root),patch.object(c,'LOCAL',local),patch.object(c,'MODEL',model),patch.object(c,'INTERPRETER',root/'python'),patch.object(c,'MANIFEST',mp),patch.object(c,'manifest',return_value=frozen),patch.object(c,'SHARDS',{'shard':(7,'unused')}):
                self.assertEqual(c.input_contract('q04_C')['condition_id'],'q04_C')
                for path in (root/'input',root/'installed',model/'shard',env,root/'python'):
                    old=path.read_bytes();path.write_bytes(b'tampered')
                    with self.assertRaises(ValueError):c.input_contract('q04_C')
                    path.write_bytes(old)

    def test_preimport_guard(self):
        result=subprocess.run([sys.executable,'-c',"import sys; from batch02_vlm.runner import verify_lease;\ntry: verify_lease({'condition_id':'q04_C'},'a'*32,-1)\nexcept (ValueError,OSError): pass\nelse: raise AssertionError('unguarded')\nassert 'torch' not in sys.modules\n"],cwd=c.ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_wrong_lock_inode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'gpu.lock').touch();other=root/'other';other.touch()
            with other.open() as f,patch.object(runner,'RUNTIME',root),self.assertRaises(ValueError):
                runner.verify_lease(dict(condition_id='q04_C'),'a'*32,f.fileno())

    def test_live_exact_lease_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'gpu.lock').touch()
            config=dict(condition_id='q04_C',settings=c.SETTINGS);inputs={'frozen':'input'}
            job=dict(job_id='j',command='vlm-batch02',status='running',config_json=json.dumps(config),
                config_hash=digest(config),input_json=json.dumps(inputs),input_hash=digest(inputs),
                source_hash='source',run_id='run',task_id='task',dispatch_id='dispatch',code_sha='commit')
            db=sqlite3.connect(root/'queue.sqlite3')
            db.execute('CREATE TABLE jobs ('+','.join(k+' TEXT' for k in job)+')')
            db.execute('INSERT INTO jobs VALUES ('+','.join('?' for _ in job)+')',tuple(job.values()))
            db.execute('CREATE TABLE attempts (attempt_id TEXT,job_id TEXT,status TEXT,supervisor_pid INTEGER,supervisor_identity TEXT,child_pid INTEGER,child_identity TEXT,started_at REAL)')
            db.execute('INSERT INTO attempts VALUES (?,?,?,?,?,?,?,0)',('a'*32,'j','running',os.getppid(),process_identity(os.getppid()),os.getpid(),process_identity(os.getpid())))
            db.commit()
            with patch.object(runner,'RUNTIME',root),patch.object(runner,'validate_assignment',return_value={'source_commit':'commit'}),patch.object(runner,'input_contract',return_value=inputs),patch.object(runner,'source_hash',return_value='source'),patch.object(runner,'validate',return_value='q04_C'):
                with (root/'gpu.lock').open() as lock:
                    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                    self.assertEqual(runner.verify_lease(config,'a'*32,lock.fileno())['command'],'vlm-batch02')
                    with (root/'gpu.lock').open() as other,self.assertRaisesRegex(ValueError,'inherited reservation'):
                        runner.verify_lease(config,'a'*32,other.fileno())
                    for table,key,value in [('jobs','command','mvp-0001'),('jobs','input_hash','stale'),('jobs','source_hash','stale'),('jobs','config_hash','stale'),('jobs','code_sha','stale'),('attempts','supervisor_identity','stale'),('attempts','child_identity','stale')]:
                        old=db.execute('SELECT '+key+' FROM '+table).fetchone()[0]
                        db.execute('UPDATE '+table+' SET '+key+'=?',(value,));db.commit()
                        with self.assertRaises(ValueError):runner.verify_lease(config,'a'*32,lock.fileno())
                        db.execute('UPDATE '+table+' SET '+key+'=?',(old,));db.commit()
            db.close()

    def test_boolean_settings_are_not_integer_aliases(self):
        self.assertFalse(c.same(c.SETTINGS,{**c.SETTINGS,'do_sample':0}))
        cfg=dict(condition_id='q04_C',settings={**c.SETTINGS,'do_sample':0})
        with self.assertRaises(ValueError):c.validate(cfg,{},c.RUNTIME)

    def test_resource_gate(self):
        for free in (0,6143):
            with patch.object(subprocess,'check_output',return_value=f'4000, {free}'),self.assertRaises(ValueError):runner.resources()
        with patch.object(subprocess,'check_output',return_value='4000, 6144'):
            self.assertEqual(runner.resources()['free_mib'],6144)

    def test_quantization_arguments(self):
        torch=types.SimpleNamespace(bfloat16='BF16',uint8='U8')
        args=runner.load_kwargs(torch,lambda **kw:kw)
        q=args['quantization_config']
        self.assertEqual(args['device_map'],{'':'cuda:0'})
        self.assertEqual(q['llm_int8_skip_modules'],['model.visual','lm_head'])
        self.assertEqual(q['bnb_4bit_compute_dtype'],'BF16')
        self.assertEqual(q['bnb_4bit_quant_type'],'nf4')
        self.assertTrue(q['bnb_4bit_use_double_quant'])
        self.assertFalse(q['llm_int8_enable_fp32_cpu_offload'])
        self.assertEqual(args['attn_implementation'],'sdpa')

    def test_strict_common_and_behavior_separate(self):
        obj=dict(observed_actions=['stepping_over_boundary'],visible_evidence='example',crossing_completion='observed',uncertainties='example')
        out=evaluate.classify('```json\n'+json.dumps(obj)+'\n```')
        self.assertTrue(out['candidate']);self.assertFalse(out['strict_schema']);self.assertTrue(out['common_schema'])
        self.assertIsNone(out['evidence_consistency'])
        out=evaluate.classify('invalid')
        self.assertTrue(out['parse_failure']);self.assertIsNone(out['candidate'])
        obj['observed_actions']=['indeterminate'];out=evaluate.classify(json.dumps(obj))
        self.assertTrue(out['indeterminate']);self.assertFalse(out['candidate']);self.assertFalse(out['other'])

    def test_failure_before_construction_does_not_touch_cuda(self):
        import time
        class NoCuda:
            @property
            def cuda(self):raise AssertionError('preflight reporting touched CUDA')
        with tempfile.TemporaryDirectory() as tmp:
            now=time.perf_counter()
            record=runner.failure_record(ValueError('gate failed'),'preflight',now,{'prepare_seconds':.1},now,Path(tmp),NoCuda(),False)
            self.assertIsNone(record['gpu_memory'])
            self.assertFalse(record['oom'])
            self.assertEqual(record['timing']['prepare_seconds'],.1)
            self.assertFalse(record['generated_tokens_saved'])
        fake=types.SimpleNamespace(cuda=types.SimpleNamespace(memory_allocated=lambda:1,memory_reserved=lambda:2,max_memory_allocated=lambda:3,max_memory_reserved=lambda:4))
        with tempfile.TemporaryDirectory() as tmp:
            now=time.perf_counter()
            record=runner.failure_record(RuntimeError('CUDA out of memory'),'load',now,{},now,Path(tmp),fake,True)
            self.assertTrue(record['oom']);self.assertEqual(record['gpu_memory']['peak_reserved_bytes'],4)
            self.assertIn('load_elapsed_seconds',record['timing'])

    def test_actual_module_inventory_without_real_torch(self):
        class Tensor:
            device='cuda:0';dtype='BF16';shape=(1,)
            def is_floating_point(self):return self.dtype=='BF16'
        class Linear:pass
        class Four(Linear):
            compute_dtype='BF16'
            weight=types.SimpleNamespace(dtype='U8',quant_type='nf4',quant_state=types.SimpleNamespace(nested=True,state2=types.SimpleNamespace(absmax=Tensor(),code=Tensor(),offset=None),absmax=Tensor(),code=Tensor(),offset=Tensor()))
        parameters=[('model.visual.weight',Tensor()),('model.language_model.norm.weight',Tensor()),('lm_head.weight',Tensor())]
        modules=[('model.language_model.layers.0.linear'+str(i),Four()) for i in range(7)]
        model=types.SimpleNamespace(named_modules=lambda:iter(modules),named_parameters=lambda:iter(parameters),named_buffers=lambda:iter([]),hf_device_map={'':'cuda:0'},config=types.SimpleNamespace(text_config=types.SimpleNamespace(num_hidden_layers=1)))
        fake=types.SimpleNamespace(bfloat16='BF16',uint8='U8',nn=types.SimpleNamespace(Linear=Linear))
        with patch.dict(sys.modules,{'torch':fake,'bitsandbytes.nn':types.SimpleNamespace(Linear4bit=Four),'bitsandbytes':types.SimpleNamespace()}):
            self.assertEqual(len(runner.inventory(model)['quantized_modules']),7)
            parameters[0][1].device='cpu'
            with self.assertRaisesRegex(ValueError,'offload'):runner.inventory(model)
            parameters[0][1].device='cuda:0';parameters[0][1].dtype='F16'
            with self.assertRaisesRegex(ValueError,'BF16'):runner.inventory(model)
            parameters[0][1].dtype='BF16';modules[0]=('model.visual.linear',Four())
            with self.assertRaisesRegex(ValueError,'unexpected 4bit'):runner.inventory(model)

    @unittest.skipUnless(importlib.util.find_spec('numpy'),'NumPy only in isolated VLM environment')
    def test_processor_metadata_rgb_and_missing_history(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);frames=np.zeros((10,2,2,3),dtype='uint8')
            np.save(root/'rgb.npy',frames,allow_pickle=False)
            row=dict(expected_metadata=dict(input_tokens=1947,last_decoded_pts=5),parity_rgb='rgb.npy',parity_prompt=None)
            info=dict(input_tokens=1947,last_decoded_pts=4.5)
            with patch.object(runner,'ROOT',root):
                parity=runner.validate_prepared(row,info,frames,'anonymous')
                self.assertEqual(parity['original_baseline_processor_RGB'],'unavailable_historical_q')
                with self.assertRaises(ValueError):runner.validate_prepared(row,{**info,'input_tokens':1900},frames,'anonymous')
                altered=frames.copy();altered[0,0,0,0]=1
                with self.assertRaises(ValueError):runner.validate_prepared(row,info,altered,'anonymous')
                row['parity_prompt']='missing.txt'
                with self.assertRaises(FileNotFoundError):runner.validate_prepared(row,info,frames,'anonymous')

    def test_references_do_not_invent_truth(self):
        self.assertIsNone(evaluate.reference('v03')['boundary_candidate_reference'])
        self.assertFalse(evaluate.reference('v03')['candidate_absence_definitive_boundary_miss'])
        self.assertIn('previously unassessed',evaluate.reference('v01')['prior'])
        self.assertFalse(evaluate.reference('q04')['completion_support'])
        text=(c.ROOT/'batch02_vlm/runner.py').read_text()
        self.assertNotIn('from batch02_vlm.evaluate',text)
        self.assertNotIn('user_input_review',text)


class QueueIntegration(unittest.TestCase):
    def test_cv_schema_additive_migration_backup_preserves_history(self):
        from orchestration.queue import Queue
        with tempfile.TemporaryDirectory() as tmp:
            q=Queue.initialize(tmp)
            q.enqueue(job_key='historical',run_id='r',task_id='t',dispatch_id='d',owner='fixture',config=dict(seconds=0,exit_code=0))
            q.supervise_once();q.migrate_commands(include_cv=True)
            before=q.status()
            q.migrate_commands(include_vlm_batch02=True)
            self.assertEqual(q.status(),before)
            backups=list(Path(tmp).glob('queue-before-batch02-vlm-*.sqlite3'))
            self.assertEqual(len(backups),1)
            with q.connection() as db:
                sql=db.execute("SELECT sql FROM sqlite_master WHERE name='jobs'").fetchone()[0]
            for command in ('cpu-mock','vlm-batch01','mvp-0001','batch02-cv','vlm-batch02'):
                self.assertIn("'"+command+"'",sql)
            with sqlite3.connect(backups[0]) as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0],1)
                self.assertNotIn("'vlm-batch02'",db.execute("SELECT sql FROM sqlite_master WHERE name='jobs'").fetchone()[0])
            q.migrate_commands(include_vlm_batch02=True);q.migrate_commands(include_cv=True)
            self.assertEqual(len(list(Path(tmp).glob('queue-before-batch02-vlm-*.sqlite3'))),1)
            q.enqueue(job_key='cpu-after',run_id='r',task_id='t',dispatch_id='d',owner='fixture',config=dict(seconds=0,exit_code=0))
            self.assertEqual(q.supervise_once()['status'],'succeeded')

    def test_new_migration_rejects_lock_and_unknown_state(self):
        from orchestration.queue import Queue
        with tempfile.TemporaryDirectory() as tmp:
            q=Queue.initialize(tmp);q.migrate_commands(include_cv=True)
            with q.gpu_lock(),self.assertRaises(ValueError):q.migrate_commands(include_vlm_batch02=True)
            j=q.enqueue(job_key='unknown',run_id='r',task_id='t',dispatch_id='d',owner='fixture')
            with q.connection() as db:db.execute("UPDATE jobs SET status='unknown'")
            with self.assertRaises(ValueError):q.migrate_commands(include_vlm_batch02=True)
            self.assertFalse(list(Path(tmp).glob('queue-before-batch02-vlm-*')))

    def test_new_registration_assignment_key_hash_and_manifest(self):
        from orchestration.queue import Queue,source_hash
        with tempfile.TemporaryDirectory() as tmp:
            q=Queue.initialize(tmp);q.migrate_commands(include_cv=True)
            config=dict(condition_id='q04_C',settings=c.SETTINGS);inputs={'pinned':'input'}
            def enqueue(key=c.job_key('q04_C'),**kw):
                return q.enqueue(job_key=key,run_id='run',task_id='task',dispatch_id='dispatch',owner='fixture',command='vlm-batch02',config=config,input_value=inputs,timeout=1800,**kw)
            with patch.object(c,'validate',return_value='q04_C') as validate,patch.object(c,'validate_assignment',return_value={}) as assignment,patch.object(c,'sources',return_value={'fixture':'source'}):
                with self.assertRaisesRegex(ValueError,'fixed VLM job key'):enqueue('fresh-bypass-key')
                with self.assertRaisesRegex(ValueError,'input/config hash'):enqueue(expected_input_hash='wrong')
                with patch.object(c,'validate_assignment',side_effect=ValueError('wrong assignment')):
                    with self.assertRaisesRegex(ValueError,'assignment'):enqueue()
                job=enqueue();self.assertEqual(enqueue()['job_id'],job['job_id'])
                self.assertEqual(job['input_hash'],digest(inputs));self.assertEqual(job['config_hash'],digest(config))
                self.assertEqual(job['source_hash'],source_hash('vlm-batch02',config))
                assignment.assert_called_with('run','task','dispatch')
                with q.gpu_lock():
                    _,attempt=q._claim()
                    q._finish(attempt,'failed',None,'fixture registration only; no model executed')
                receipt=json.loads((Path(tmp)/'attempts'/attempt/'manifest.json').read_text())
                self.assertFalse(receipt['synthetic']);self.assertIsNone(receipt['mock_result'])
                self.assertEqual(receipt['registration']['script'],str(c.ROOT/'batch02_vlm/runner.py'))
                self.assertEqual(receipt['result'],str(c.output_path('q04_C',attempt)))
                with patch.object(c,'validate',side_effect=ValueError('config/input mismatch')):
                    with self.assertRaisesRegex(ValueError,'config/input'):enqueue()


if __name__=='__main__':unittest.main()
