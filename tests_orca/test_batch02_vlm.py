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
    def setUp(self):
        guard=patch.object(c,'continuation_binding',return_value=None);guard.start();self.addCleanup(guard.stop)

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

    def test_q_aggregate_and_v_per_frame_metadata_decode_compatibility(self):
        import hashlib
        class Frame:
            def __init__(self,data):self.data=data
            def tobytes(self):return self.data
        class RGB(list):
            def tobytes(self):return b''.join(frame.tobytes() for frame in self)
        rgb=RGB(Frame(bytes([i])*12) for i in range(10))
        frames=[hashlib.sha256(f.tobytes()).hexdigest() for f in rgb]
        aggregate=hashlib.sha256(rgb.tobytes()).hexdigest()
        row=dict(source_frame_sha256=frames,roi=[0,0,1,1],expected_metadata=dict(crop_sha256=aggregate))
        runner.validate_decoded_frames(rgb,row,{'rgb_sha256':aggregate})
        runner.validate_decoded_frames(rgb,row,{'frame_sha256':frames})
        self.assertNotIn('torch',sys.modules)
        for source in ({},{'frame_sha256':frames[:-1]},{'rgb_sha256':'wrong'}):
            with self.assertRaises(ValueError):runner.validate_decoded_frames(rgb,row,source)
        with self.assertRaises(ValueError):runner.validate_decoded_frames(rgb,{**row,'roi':[0,.2,1,1]},{'frame_sha256':frames})
        altered=RGB(rgb);altered[0]=Frame(b'tampered')
        with self.assertRaises(ValueError):runner.validate_decoded_frames(altered,row,{'frame_sha256':frames})

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
    def setUp(self):
        guard=patch.object(c,'continuation_binding',return_value=None);guard.start();self.addCleanup(guard.stop)

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


class ContinuationTests(unittest.TestCase):
    def setUp(self):
        import uuid
        from batch02_vlm import continuation as m
        from orchestration.queue import Queue
        from orchestration.vlm_command import file_hash
        self.m=m;self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name);local=root/'local';local.mkdir();(root/'configs').mkdir()
        runtime=root/'runtime';self.q=Queue.initialize(runtime);self.q.migrate_commands(include_vlm_batch02=True)
        self.command=types.SimpleNamespace(ROOT=root,LOCAL=local,RUNTIME=runtime,SETTINGS=c.SETTINGS,file_hash=file_hash,
            output_path=lambda condition,attempt:root/'outputs'/condition/attempt,source_hash=lambda:'new-source',
            validate_assignment=lambda *args:None,same=c.same,prior_generated_tokens=lambda condition:[])
        (local/'execution-authorization.json').write_text(json.dumps(dict(source_commit='new-commit',run_id='run',task_id='task',dispatch_id='dispatch')))
        retained={};failed={}
        with self.q.connection() as db:
            for i in range(33):
                condition=m.Q[i] if i<12 else m.CONDITION if i==12 else None
                jobid=m.FAILED_JOB if i==12 else uuid.uuid4().hex;attempt=m.FAILED_ATTEMPT if i==12 else uuid.uuid4().hex
                status='failed' if i==12 else 'succeeded'
                cfg=dict(condition_id=condition,settings=c.SETTINGS) if condition else dict(seconds=0,exit_code=0)
                inputvalue={'frozen':True}
                db.execute('INSERT INTO jobs (job_id,job_key,run_id,task_id,dispatch_id,owner,command,input_json,config_json,input_hash,config_hash,source_hash,code_sha,timeout,status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (jobid,'batch0002-exp0020-vlm-'+condition if condition else 'old-'+str(i),'run','task','dispatch','fixture','vlm-batch02' if condition else 'cpu-mock',json.dumps(inputvalue),json.dumps(cfg),digest(inputvalue),digest(cfg),m.ORIGINAL_SOURCE,m.ORIGINAL_COMMIT,1800,status,float(i)))
                db.execute('INSERT INTO attempts (attempt_id,job_id,attempt_no,owner,status,started_at,finished_at,heartbeat,timeout) VALUES (?,?,1,?,?,0,1,1,1800)',(attempt,jobid,'fixture',status))
                if condition:
                    folder=self.command.output_path(condition,attempt);folder.mkdir(parents=True)
                    queue=runtime/'attempts'/attempt/'manifest.json';queue.parent.mkdir(parents=True);queue.write_text('{}')
                    if i<12:
                        (folder/'generated_token_ids.npy').write_bytes(b'fixture tokens')
                        artifacts={'generated_token_ids.npy':file_hash(folder/'generated_token_ids.npy')}
                        (folder/'result.json').write_text(json.dumps(dict(condition_id=condition,status='succeeded',artifacts=artifacts)))
                        (folder/'summary.json').write_text(json.dumps(dict(status='succeeded',condition_id=condition,result_sha256=file_hash(folder/'result.json'))))
                        retained[condition]=dict(job_id=jobid,attempt_id=attempt,result_sha256=file_hash(folder/'result.json'),summary_sha256=file_hash(folder/'summary.json'),queue_manifest_sha256=file_hash(queue),artifacts=artifacts)
                    else:
                        (folder/'failure.json').write_text('{}')
                        failed=dict(job_id=jobid,attempt_id=attempt,artifacts={'failure.json':file_hash(folder/'failure.json')},queue_manifest_sha256=file_hash(queue))
        snapshot=m.state(self.command)
        hp=local/'before-metadata-correction-queue.json';hp.write_text(json.dumps(snapshot))
        historysha=file_hash(hp);pin=patch.object(m,'HISTORY_SHA',historysha);pin.start();self.addCleanup(pin.stop)
        self.receipt=dict(retained=retained,failed=failed);rp=local/'continuation-receipt.json';rp.write_text(json.dumps(self.receipt))
        self.contract=dict(schema_version=1,experiment='EXP-0020',reason='v-only historical RGB metadata compatibility',original_commit=m.ORIGINAL_COMMIT,original_source_hash=m.ORIGINAL_SOURCE,history_snapshot_sha256=historysha,failed_job_id=m.FAILED_JOB,failed_attempt_id=m.FAILED_ATTEMPT,correction_condition=m.CONDITION,correction_job_key=m.RETRY_KEY,maximum_logical_attempts=2,receipt_sha256=file_hash(rp))
        (root/'configs/batch0002_vlm_continuation.json').write_text(json.dumps(self.contract))

    def correction_job(self):
        import uuid
        with self.q.connection() as db:
            old=dict(db.execute('SELECT * FROM jobs WHERE job_id=?',(self.m.FAILED_JOB,)).fetchone())
            old.update(job_id=uuid.uuid4().hex,job_key=self.m.RETRY_KEY,source_hash='new-source',code_sha='new-commit',status='queued',created_at=100)
            db.execute('INSERT INTO jobs ('+','.join(old)+') VALUES ('+','.join('?' for _ in old)+')',tuple(old.values()))
        return old

    def test_exact_retained_successes_and_tampered_rows_artifacts_receipt(self):
        binding=self.m.load(self.command);self.assertEqual(len(binding[1]['retained']),12)
        with patch.object(c,'RUNTIME',self.command.RUNTIME),patch.object(c,'output_path',self.command.output_path),patch.object(c,'source_hash',return_value='new-source'),patch.object(c,'input_contract',return_value={'frozen':True}),patch.object(c,'continuation_binding',side_effect=lambda:self.m.load(self.command)):
            self.assertEqual(c.successful('q04_C'),[self.receipt['retained']['q04_C']['attempt_id']])
        entry=self.receipt['retained']['q04_C'];p=self.command.output_path('q04_C',entry['attempt_id'])/'generated_token_ids.npy';original=p.read_bytes();p.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'artifact'):self.m.load(self.command)
        p.write_bytes(original)
        with self.q.connection() as db:db.execute('UPDATE jobs SET source_hash=? WHERE job_id=?',('wrong',entry['job_id']))
        with self.assertRaisesRegex(ValueError,'immutable'):self.m.load(self.command)
        with self.q.connection() as db:db.execute('UPDATE jobs SET source_hash=? WHERE job_id=?',(self.m.ORIGINAL_SOURCE,entry['job_id']))
        rp=self.command.LOCAL/'continuation-receipt.json';rp.write_text('{}')
        with self.assertRaisesRegex(ValueError,'receipt/history'):self.m.load(self.command)

    def test_wrong_lineage_source_and_unsupported_contract_rejected(self):
        p=self.command.ROOT/'configs/batch0002_vlm_continuation.json'
        for key,value in [('failed_attempt_id','wrong'),('original_source_hash','arbitrary'),('correction_job_key','fresh-key'),('maximum_logical_attempts',3)]:
            p.write_text(json.dumps({**self.contract,key:value}))
            with self.assertRaises(ValueError):self.m.load(self.command)
        p.write_text(json.dumps(self.contract))
        entry=self.receipt['retained']['q04_C']
        with self.q.connection() as db:db.execute('UPDATE attempts SET job_id=?,attempt_no=2 WHERE attempt_id=?',(self.m.FAILED_JOB,entry['attempt_id']))
        with self.assertRaisesRegex(ValueError,'immutable'):self.m.load(self.command)

    def test_retry_hook_preserves_history_blocks_pending_duplicates_and_third_attempt(self):
        before=self.q.status()
        hook=patch.object(c,'retry_guard',side_effect=lambda db,row:self.m.retry_guard(self.command,db,row));hook.start();self.addCleanup(hook.stop)
        with self.assertRaisesRegex(ValueError,'sole logical retry'):self.q.retry(self.m.FAILED_JOB)
        self.assertEqual(self.q.status(),before)
        job=self.correction_job();self.m.budget(self.command,self.m.load(self.command))
        with self.assertRaises(sqlite3.IntegrityError):self.correction_job()
        with self.q.connection() as db:
            db.execute("UPDATE jobs SET status='running' WHERE job_id=?",(job['job_id'],))
            db.execute("INSERT INTO attempts (attempt_id,job_id,attempt_no,owner,status,started_at,heartbeat,timeout) VALUES (?, ?,1,'fixture','running',100,100,1800)",('f'*32,job['job_id']))
        self.m.budget(self.command,self.m.load(self.command))
        with self.q.connection() as db:
            db.execute("UPDATE attempts SET status='failed' WHERE attempt_id=?",('f'*32,))
            db.execute("UPDATE jobs SET status='failed' WHERE job_id=?",(job['job_id'],))
        with self.assertRaisesRegex(ValueError,'sole logical retry'):self.q.retry(job['job_id'])
        with self.assertRaisesRegex(ValueError,'exhausted'):self.m.budget(self.command,self.m.load(self.command))
        self.assertEqual(len([a for a in self.q.status()['attempts'] if a['job_id'] in (self.m.FAILED_JOB,job['job_id'])]),2)
        with self.q.connection() as db:
            db.execute("INSERT INTO attempts (attempt_id,job_id,attempt_no,owner,status,started_at,heartbeat,timeout) VALUES (?, ?,2,'fixture','failed',101,101,1800)",('e'*32,job['job_id']))
        with self.assertRaisesRegex(ValueError,'maximum two'):self.m.budget(self.command,self.m.load(self.command))

    def test_concurrent_enqueue_has_one_fixed_pending_correction(self):
        from concurrent.futures import ThreadPoolExecutor
        expected_source=digest({'fixture':'new-source'})
        self.command.source_hash=lambda:expected_source
        config=dict(condition_id=self.m.CONDITION,settings=c.SETTINGS)
        with patch.object(c,'validate',return_value=self.m.CONDITION),patch.object(c,'validate_assignment',return_value={}),patch.object(c,'job_key',return_value=self.m.RETRY_KEY),patch.object(c,'sources',return_value={'fixture':'new-source'}),patch.object(subprocess,'run',return_value=types.SimpleNamespace(stdout='new-commit')):
            def enqueue(_):
                return self.q.enqueue(job_key=self.m.RETRY_KEY,run_id='run',task_id='task',dispatch_id='dispatch',owner='fixture',command='vlm-batch02',config=config,input_value={'frozen':True},timeout=1800)
            with ThreadPoolExecutor(max_workers=2) as pool:jobs=list(pool.map(enqueue,range(2)))
        self.assertEqual(jobs[0]['job_id'],jobs[1]['job_id'])
        binding=self.m.load(self.command);self.m.budget(self.command,binding)
        self.assertEqual(sum(j['job_key']==self.m.RETRY_KEY for j in binding[3]['jobs']),1)
        self.assertEqual(sum(a['job_id']==jobs[0]['job_id'] for a in binding[3]['attempts']),0)

    def test_pending_wrong_source_refused_and_saved_failed_tokens_never_retry(self):
        job=self.correction_job()
        with self.q.connection() as db:db.execute('UPDATE jobs SET source_hash=? WHERE job_id=?',('stale',job['job_id']))
        with self.assertRaisesRegex(ValueError,'current frozen source'):self.m.budget(self.command,self.m.load(self.command))
        folder=self.command.output_path(self.m.CONDITION,self.m.FAILED_ATTEMPT);(folder/'generated_token_ids.npy').write_bytes(b'never repeat')
        with self.assertRaisesRegex(ValueError,'receipt/tokens'):self.m.load(self.command)


if __name__=='__main__':unittest.main()
