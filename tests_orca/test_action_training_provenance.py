"""Synthetic completed-preparation and canonical-smoke proofs. No raw/video/model load."""
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from orchestration import action_training_command as command
from orchestration.queue import digest

ROOT=Path(__file__).resolve().parents[1]
WEIGHTS_SHA='b3b3357ead25631ec9c57362ff2128a92d0427e01e2cd184951a44380c3f2e9d'
CONTEXT=dict(run_id='run_3d23462a014a',task_id='task-fixture',dispatch_id='ctx-fixture',owner='term-fixture')


def save(path,value):
    Path(path).write_text(json.dumps(value,indent=2)+'\n')


def bind(path):
    return dict(path=str(path),sha256=command.file_hash(path))


class Fixture:
    def __init__(self,folder):
        self.root=Path(folder);self.pixels=self.root/'full';self.pixels.mkdir()
        self.config=dict(stage='train',context=CONTEXT,files={},authorization={})
        for key in command.FILE_KEYS:
            path=self.root/(key+'.json');save(path,{})
            self.config['files'][key]=bind(path)
        self.paths={k:Path(v['path']) for k,v in self.config['files'].items()}
        self.paths['prepared']=self.pixels/'prepared.json'
        self.rows=[]
        for split,per_class in [('train',16),('validation',2),('test',1)]:
            for label in (0,1):
                for i in range(per_class):
                    name=f'{split}-{label}-{i}';source=self.root/(name+'.mp4');annotation=self.root/(name+'-label.json')
                    # Raw video need not exist at all: completed NPY bytes are the consumed inputs.
                    save(annotation,dict(action=label))
                    self.rows.append(dict(clip_id=name,source_id=name,event_group=name,location=split,split=split,label=label,
                        actor_id=0,source_path=str(source),source_sha256=hashlib.sha256(name.encode()).hexdigest(),
                        label_path=str(annotation),label_sha256=command.file_hash(annotation),
                        sample_pts=[j/3 for j in range(8)],roi_xyxy=[0,0,32,24],verified_action_interval=[0,3],
                        label_evidence='fixture',negative_basis='explicit_action_annotation',
                        temporal_alignment='annotation_interior_both_origins',box_alignment='official_annotations_sampled_alignment_review'))
        self.manifest=dict(clips=self.rows,review_status='sampled_alignment_review_complete',
            label_policy='official_actor_action_intervals_sampled_alignment_review',review_evidence='fixture',held_out_test_locations=['test'])
        self.baseline=dict(status='verified',baseline_experiment='EXP-0062',
            regression_only_videos=[dict(path=str(self.root/f'forbidden-{i}.mp4'),sha256=hashlib.sha256(f'forbidden-{i}'.encode()).hexdigest()) for i in range(45)])
        save(self.paths['baseline_lock'],self.baseline)
        self.settings=json.loads((ROOT/'configs/exp0063_action_training.json').read_text());save(self.paths['config'],self.settings)
        self.split=dict(held_out_test_locations=['test'],assignments=[dict(source_id=r['source_id'],source_sha256=r['source_sha256'],
            group_id=r['event_group'],split=r['split'],location=r['location'],label_sha256=r['label_sha256'],excluded=False) for r in self.rows])
        save(self.paths['split_manifest'],self.split)
        self.snapshot=self.root/'reviews.json';self.policy=self.root/'policy.md';save(self.snapshot,{});self.policy.write_text('fixture')
        self.release=dict(review_snapshot=bind(self.snapshot),interpretation_policy=bind(self.policy))
        self.manifest.update(config_sha256=command.file_hash(self.paths['config']),baseline_lock_sha256=command.file_hash(self.paths['baseline_lock']),
                             source_split_sha256=command.file_hash(self.paths['split_manifest']))
        save(self.paths['manifest'],self.manifest)
        self.clips={}
        for i,row in enumerate(self.rows):
            path=self.pixels/f'clip-{i:06d}.npy';path.write_bytes(('synthetic-pixel-'+row['clip_id']).encode());self.clips[row['clip_id']]=bind(path)
        self.sequential=self.root/'sequential.json'
        save(self.sequential,dict(manifest_sha256=command.file_hash(self.paths['manifest']),clips=copy.deepcopy(self.clips)))
        self.sequential_sha=command.file_hash(self.sequential)
        self.module=command.trainer()
        self.counts=self.module.validate_manifest(self.manifest,self.baseline,8,self.split)
        self.producer=dict(mode='prepare',workers=4,expected_clips=len(self.rows),counts=self.counts,
            trainer_sha256=command.file_hash(ROOT/'scripts/train_action_recognizer.py'),
            driver_sha256=command.file_hash(ROOT/'scripts/prepare_action_pixels_parallel.py'),paths={},hashes={})
        for key in ('manifest','baseline_lock','split_manifest','config','review_release'):
            self.producer['paths'][key]=str(self.paths[key]);self.producer['hashes'][key]=command.file_hash(self.paths[key])
        for key,value in self.release.items():
            self.producer['paths'][key]=value['path'];self.producer['hashes'][key]=value['sha256']
        self.producer['paths']['sequential_snapshot']=str(self.sequential);self.producer['hashes']['sequential_snapshot']=command.file_hash(self.sequential)
        save(self.pixels/'contract.json',self.producer)
        self.prepared=dict(manifest_sha256=command.file_hash(self.paths['manifest']),config_sha256=command.file_hash(self.paths['config']),clips=self.clips,
            preparation=dict(contract=bind(self.pixels/'contract.json'),trainer_sha256=self.producer['trainer_sha256'],
                             driver_sha256=self.producer['driver_sha256'],workers=4))
        save(self.paths['prepared'],self.prepared)
        self.success=dict(status='prepared',clips=len(self.rows),workers=4,prepared_sha256=command.file_hash(self.paths['prepared']))
        save(self.pixels/'result.json',self.success)
        self.source_map={row[p]:row[h] for row in self.rows for p,h in [('source_path','source_sha256'),('label_path','label_sha256')]}
        self.gate=dict(status='passed',files=[dict(path=p,sha256=h) for p,h in self.source_map.items()]);save(self.pixels/'verified-source-hashes.json',self.gate)
        self.equivalence=dict(compared=len(self.rows),npy_sha256_equal=True,arrays_equal=True,dtype_equal=True,shape_equal=True)
        save(self.pixels/'sequential-equivalence.json',self.equivalence)
        self.evidence=dict(schema_version=1,kind='completed_action_preparation_v1',scope='full_corpus',prepared=bind(self.paths['prepared']),
            producer_contract=bind(self.pixels/'contract.json'),successful_result=bind(self.pixels/'result.json'),
            source_gate_receipt=bind(self.pixels/'verified-source-hashes.json'),
            equivalence=dict(report=bind(self.pixels/'sequential-equivalence.json'),sequential_snapshot=bind(self.sequential)))
        self.evidence_path=self.root/'evidence.json'
        self.refresh()

    def refresh(self):
        for key,path in self.paths.items():
            self.config['files'][key]=bind(path)
        self.config['files']['weights']['sha256']=WEIGHTS_SHA
        save(self.evidence_path,self.evidence);self.config['files']['preparation_evidence']=bind(self.evidence_path)
        self.paths['preparation_evidence']=self.evidence_path

    def update_artifact(self,key,path,value):
        save(path,value);self.evidence[key]=bind(path);self.refresh()

    def contract(self):
        original=command.file_hash
        def hashed(path):
            if Path(path)==self.paths['weights']:return WEIGHTS_SHA
            if Path(path).suffix=='.mp4':raise AssertionError('Raw video opened by train: '+str(path))
            return original(path)
        with patch.object(command,'FROZEN_SPLIT_SHA',self.manifest['source_split_sha256']),\
             patch.object(command,'FROZEN_SEQUENTIAL_SHA',self.sequential_sha),\
             patch.object(command,'file_hash',side_effect=hashed),\
             patch('orchestration.action_training_command.trainer',return_value=self.module) as factory:
            module=factory.return_value
            with patch.object(module,'validate_release',return_value=self.release):
                return command.input_contract(self.config)


class PreparationProvenanceTests(unittest.TestCase):
    def test_full_evidence_opens_no_raw_media_but_hashes_actual_pixels_and_annotations(self):
        with tempfile.TemporaryDirectory() as t:
            f=Fixture(t);result=f.contract()
            self.assertEqual(result['sources'],f.source_map);self.assertEqual(len(result['pixels']),38)
            self.assertEqual(result['preparation_provenance']['mode'],'verified_during_completed_preparation_not_current_raw_revalidation')
            self.assertFalse(any(Path(r['source_path']).exists() for r in f.rows))
            Path(f.rows[-1]['label_path']).write_text('modified annotation')
            with self.assertRaisesRegex(ValueError,'annotation'):f.contract()

    def test_selected_npy_change_or_missing_is_rejected_before_model(self):
        for missing in (False,True):
            with self.subTest(missing=missing),tempfile.TemporaryDirectory() as t:
                f=Fixture(t);path=Path(next(iter(f.clips.values()))['path'])
                if missing:path.unlink()
                else:path.write_bytes(b'changed')
                with self.assertRaises((ValueError,FileNotFoundError)):f.contract()

    def test_evidence_schema_binding_hash_and_stage_key_counterexamples(self):
        for change in ('version','scope','extra','unbound','bad-prepared','missing-evidence'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as t:
                f=Fixture(t)
                if change=='version':f.evidence['schema_version']=2
                elif change=='scope':f.evidence['scope']='smoke_only'
                elif change=='extra':f.evidence['silent_bypass']=True
                elif change=='unbound':f.evidence['source_gate_receipt']['sha256']='0'*64
                elif change=='bad-prepared':f.evidence['prepared']['sha256']='0'*64
                if change=='missing-evidence':f.config['files'].pop('preparation_evidence')
                else:f.refresh()
                with self.assertRaises(ValueError):f.contract()

    def test_failed_partial_smoke_or_missing_success_cannot_authorize_train(self):
        for status in ('failed','benchmark_passed','smoke_subset_prepared','prepared'):
            with self.subTest(status=status),tempfile.TemporaryDirectory() as t:
                f=Fixture(t);bad={**f.success,'status':status}
                if status=='prepared':bad['clips']-=1
                f.update_artifact('successful_result',f.pixels/'result.json',bad)
                with self.assertRaisesRegex(ValueError,'full preparation'):f.contract()
        with tempfile.TemporaryDirectory() as t:
            f=Fixture(t);(f.pixels/'result.json').unlink()
            with self.assertRaises(FileNotFoundError):f.contract()
        with tempfile.TemporaryDirectory() as t:
            f=Fixture(t);save(f.pixels/'failure.json',dict(status='failed'))
            with self.assertRaisesRegex(ValueError,'Failed'):f.contract()

    def test_source_receipt_duplicate_missing_wrong_hash_and_failed(self):
        for change in ('duplicate','missing','wrong','failed','extra'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as t:
                f=Fixture(t);bad=copy.deepcopy(f.gate)
                if change=='duplicate':bad['files'].append(bad['files'][0])
                elif change=='missing':bad['files'].pop()
                elif change=='wrong':bad['files'][0]['sha256']='0'*64
                elif change=='failed':bad['status']='failed'
                else:bad['files'].append(dict(path='/unused/source.mp4',sha256='0'*64))
                f.update_artifact('source_gate_receipt',f.pixels/'verified-source-hashes.json',bad)
                with self.assertRaisesRegex(ValueError,'source gate|Source gate'):f.contract()

    def test_producer_binding_metadata_driver_review_and_scope(self):
        for change in ('driver','trainer','review','split','manifest','counts','partial'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as t:
                f=Fixture(t);bad=copy.deepcopy(f.producer)
                if change in ('driver','trainer'):bad[change+'_sha256']='0'*64
                elif change=='review':bad['hashes']['review_snapshot']='0'*64
                elif change=='split':bad['hashes']['split_manifest']='0'*64
                elif change=='manifest':bad['hashes']['manifest']='0'*64
                elif change=='counts':bad['counts']={}
                else:bad['expected_clips']-=1
                save(f.pixels/'contract.json',bad);f.evidence['producer_contract']=bind(f.pixels/'contract.json')
                f.prepared['preparation']['contract']=f.evidence['producer_contract'];save(f.paths['prepared'],f.prepared)
                f.evidence['prepared']=bind(f.paths['prepared']);f.success['prepared_sha256']=f.evidence['prepared']['sha256']
                save(f.pixels/'result.json',f.success);f.evidence['successful_result']=bind(f.pixels/'result.json');f.refresh()
                with self.assertRaises(ValueError):f.contract()

    def test_full_clip_inventory_and_renamed_regression_leakage_still_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            f=Fixture(t);f.prepared['clips'].pop(f.rows[-1]['clip_id']);save(f.paths['prepared'],f.prepared)
            f.evidence['prepared']=bind(f.paths['prepared']);f.success['prepared_sha256']=f.evidence['prepared']['sha256']
            save(f.pixels/'result.json',f.success);f.evidence['successful_result']=bind(f.pixels/'result.json');f.refresh()
            with self.assertRaisesRegex(ValueError,'full preparation'):f.contract()
        for field,value in [('source_path','path'),('source_sha256','sha256')]:
            with self.subTest(field=field),tempfile.TemporaryDirectory() as t:
                f=Fixture(t);f.rows[0][field]=f.baseline['regression_only_videos'][0][value]
                save(f.paths['manifest'],f.manifest);f.refresh()
                with self.assertRaises(ValueError):f.contract()

    def test_equivalence_flags_count_or_pixel_hash_counterexamples(self):
        for change in ('count','flags','snapshot'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as t:
                f=Fixture(t);report=copy.deepcopy(f.equivalence)
                if change=='count':report['compared']-=1
                elif change=='flags':report['arrays_equal']=False
                else:
                    snapshot=command.read(f.sequential);snapshot['clips'][f.rows[1]['clip_id']]['sha256']='0'*64;save(f.sequential,snapshot)
                    # Rebind every layer, proving the semantic pixel comparison itself rejects the change.
                    f.evidence['equivalence']['sequential_snapshot']=bind(f.sequential)
                    f.producer['hashes']['sequential_snapshot']=command.file_hash(f.sequential)
                    save(f.pixels/'contract.json',f.producer);f.evidence['producer_contract']=bind(f.pixels/'contract.json')
                    f.prepared['preparation']['contract']=f.evidence['producer_contract'];save(f.paths['prepared'],f.prepared)
                    f.evidence['prepared']=bind(f.paths['prepared']);f.success['prepared_sha256']=f.evidence['prepared']['sha256']
                    save(f.pixels/'result.json',f.success);f.evidence['successful_result']=bind(f.pixels/'result.json')
                save(f.pixels/'sequential-equivalence.json',report);f.evidence['equivalence']['report']=bind(f.pixels/'sequential-equivalence.json');f.refresh()
                with self.assertRaisesRegex(ValueError,'equivalence|snapshot'):f.contract()

    def test_smoke_keeps_raw_verification_and_never_opens_test_npy(self):
        with tempfile.TemporaryDirectory() as t:
            f=Fixture(t);config=copy.deepcopy(f.config);config['stage']='smoke';config['files'].pop('preparation_evidence')
            selected=command.trainer().partition_rows(f.manifest,'smoke');allowed={r['source_path']:r['source_sha256'] for r in selected}
            test_paths={entry['path'] for key,entry in f.clips.items() if key.startswith('test-')}
            original=command.file_hash;seen=[]
            def hashed(path):
                path=str(path);self.assertNotIn(path,test_paths)
                if path==str(f.paths['weights']):return WEIGHTS_SHA
                if path.endswith('.mp4'):
                    self.assertIn(path,allowed);seen.append(path);return allowed[path]
                return original(path)
            module=command.trainer()
            with patch.object(command,'FROZEN_SPLIT_SHA',f.manifest['source_split_sha256']),patch.object(command,'file_hash',side_effect=hashed),\
                 patch.object(command,'trainer',return_value=module),patch.object(module,'validate_release',return_value=f.release):
                result=command.input_contract(config)
            self.assertEqual(set(seen),set(allowed));self.assertEqual(len(result['pixels']),36)
            self.assertNotIn('preparation_provenance',result)


class SmokeProof:
    def __init__(self, f):
        self.fixture=f;self.inputs=f.contract();self.runtime=f.root/'queue';self.output=f.root/'queued'
        self.attempt='a'*32;self.directory=self.runtime/'attempts'/self.attempt;self.directory.mkdir(parents=True)
        self.result_path=self.output/'smoke'/self.attempt/'result.json';self.result_path.parent.mkdir(parents=True)
        self.result=dict(status='smoke_passed',test_accessed=False,training_complete=False,real_train_clips=32,
            real_validation_clips=4,actual_microbatch_sizes=[4]*8,accumulation=4,optimizer_steps=2,
            manifest_sha256=f.config['files']['manifest']['sha256'],config_sha256=f.config['files']['config']['sha256'])
        save(self.result_path,self.result)
        selected=f.module.partition_rows(f.manifest,'smoke');self.ids={r['clip_id'] for r in selected}
        old_prepared=f.root/'smoke-prepared.json'
        save(old_prepared,dict(manifest_sha256=f.config['files']['manifest']['sha256'],
            config_sha256=f.config['files']['config']['sha256'],clips={k:f.clips[k] for k in self.ids}))
        self.config=dict(stage='smoke',context=CONTEXT,files={k:copy.deepcopy(f.config['files'][k]) for k in command.FILE_KEYS},authorization={})
        self.config['files']['prepared']=bind(old_prepared)
        self.original=dict(files={k:v['sha256'] for k,v in self.config['files'].items()},
            pixels={k:self.inputs['pixels'][k] for k in self.ids},
            sources={r[p]:r[h] for r in selected for p,h in [('source_path','source_sha256'),('label_path','label_sha256')]},
            review_snapshot_sha256=self.inputs['review_snapshot_sha256'])
        self.head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        names=('orchestration/queue.py','orchestration/mock_job.py','orchestration/action_training_command.py',
               'scripts/train_action_recognizer.py','tests/test_action_recognizer.py','tests_orca/test_action_training.py')
        self.sources={name:hashlib.sha256(subprocess.check_output(['git','show',self.head+':'+name],cwd=ROOT)).hexdigest() for name in names}
        self.authorization=dict(stage='smoke',context=CONTEXT,input_hash=digest(self.original),sources=self.sources,code_sha=self.head,
            confirmed=True,training_authorized=True,independent_review_passed=True,explicit_gpu_go=True)
        auth=self.directory/'authorization.json';save(auth,self.authorization);self.config['authorization']=bind(auth)
        self.row=dict(command='action-train',job_key=command.job_key(self.config),status='succeeded',input_json=json.dumps(self.original),config_json=json.dumps(self.config),
            input_hash=digest(self.original),config_hash=digest(self.config),source_hash=digest(self.sources),code_sha=self.head,**CONTEXT)
        self.receipt=dict(schema_version=1,synthetic=False,execution_status='succeeded',attempt_id=self.attempt,
            result_path=str(self.result_path.parent),registration={'job_id':'smoke-job',**{k:v for k,v in self.row.items()
                if k in ('command','run_id','task_id','dispatch_id','owner','code_sha','source_hash','input_hash','config_hash')}})
        save(self.directory/'manifest.json',self.receipt);save(self.directory/'action-training-config.json',self.config)
        with sqlite3.connect(self.runtime/'queue.sqlite3') as db:
            db.execute('CREATE TABLE jobs(job_id TEXT,'+','.join(k+' TEXT' for k in self.row)+')')
            db.execute('INSERT INTO jobs VALUES ('+','.join('?' for _ in range(len(self.row)+1))+')',['smoke-job',*self.row.values()])
            db.execute('CREATE TABLE attempts(job_id TEXT,attempt_id TEXT,status TEXT,result_manifest TEXT)')
            db.execute('INSERT INTO attempts VALUES (?,?,?,?)',['smoke-job',self.attempt,'succeeded',str(self.directory/'manifest.json')])

    def verify(self, inputs=None):
        before=command.file_hash(self.runtime/'queue.sqlite3');original=command.file_hash
        def hashed(path):
            if Path(path).suffix=='.mp4':raise AssertionError('Canonical smoke proof reopened original media')
            return original(path)
        with patch.object(command,'RUNTIME',self.runtime),patch.object(command,'OUTPUT',self.output),patch.object(command,'file_hash',side_effect=hashed):
            result=command.validate_canonical_smoke(bind(self.result_path),self.fixture.config,self.inputs if inputs is None else inputs)
        assert command.file_hash(self.runtime/'queue.sqlite3')==before
        return result

    def update_row(self,key,value):
        with sqlite3.connect(self.runtime/'queue.sqlite3') as db:db.execute('UPDATE jobs SET '+key+'=?',(value,))


class CanonicalSmokeProofTests(unittest.TestCase):
    def test_successful_canonical_smoke36_matches_fresh_full_pixels_with_readonly_db(self):
        with tempfile.TemporaryDirectory() as t:
            proof=SmokeProof(Fixture(t));self.assertEqual(proof.verify()['matching_pixels'],36)

    def test_result_only_or_foreign_attempt_and_wrong_counts_are_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            proof=SmokeProof(Fixture(t));proof.update_row('status','failed')
            with self.assertRaisesRegex(ValueError,'succeeded'):proof.verify()
        for key,value in [('optimizer_steps',1),('optimizer_steps',3),('training_complete',True),('test_accessed',True),('actual_microbatch_sizes',[2]*16),('real_train_clips',31)]:
            with self.subTest(key=key),tempfile.TemporaryDirectory() as t:
                proof=SmokeProof(Fixture(t));save(proof.result_path,{**proof.result,key:value})
                with self.assertRaisesRegex(ValueError,'smoke'):proof.verify()
        with tempfile.TemporaryDirectory() as t:
            proof=SmokeProof(Fixture(t));proof.result_path=Path(t)/'self-declared.json';save(proof.result_path,proof.result)
            with self.assertRaisesRegex(ValueError,'Canonical'):proof.verify()

    def test_queue_attempt_receipt_snapshot_and_input_digests_cannot_be_substituted(self):
        for change in ('synthetic','foreign-attempt','command','config','input','attempt-status'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as t:
                proof=SmokeProof(Fixture(t))
                if change=='synthetic':proof.receipt['synthetic']=True
                elif change=='foreign-attempt':proof.receipt['attempt_id']='b'*32
                elif change=='command':proof.receipt['registration']['command']='cpu-mock'
                elif change=='config':proof.update_row('config_hash','wrong')
                elif change=='input':proof.update_row('input_hash','wrong')
                else:
                    with sqlite3.connect(proof.runtime/'queue.sqlite3') as db:db.execute("UPDATE attempts SET status='failed'")
                save(proof.directory/'manifest.json',proof.receipt)
                with self.assertRaises(ValueError):proof.verify()

    def test_pixel_hash_id_inventory_and_training_input_change_rejected(self):
        for change in ('pixel','missing','extra','source','manifest','config','weights'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as t:
                f=Fixture(t);proof=SmokeProof(f);inputs=copy.deepcopy(proof.inputs)
                if change=='pixel':inputs['pixels'][next(iter(proof.ids))]='0'*64
                elif change=='missing':inputs['pixels'].pop(next(iter(proof.ids)))
                elif change=='extra':
                    # Extra queued smoke pixel is invalid even if available in full preparation.
                    proof.original['pixels'][f.rows[-1]['clip_id']]=inputs['pixels'][f.rows[-1]['clip_id']]
                    proof.update_row('input_json',json.dumps(proof.original))
                elif change=='source':
                    proof.original['sources'][next(iter(proof.original['sources']))]='0'*64
                    proof.update_row('input_json',json.dumps(proof.original))
                else:f.config['files'][change]['sha256']='0'*64
                with self.assertRaises(ValueError):proof.verify(inputs)

    def test_different_historical_training_core_is_rejected_even_with_rebound_queue_proof(self):
        with tempfile.TemporaryDirectory() as t:
            proof=SmokeProof(Fixture(t));proof.authorization['sources']['scripts/train_action_recognizer.py']='0'*64
            save(proof.directory/'authorization.json',proof.authorization)
            proof.config['authorization']=bind(proof.directory/'authorization.json')
            save(proof.directory/'action-training-config.json',proof.config)
            proof.update_row('config_json',json.dumps(proof.config));proof.update_row('config_hash',digest(proof.config))
            source_hash=digest(proof.authorization['sources']);proof.update_row('source_hash',source_hash)
            proof.receipt['registration'].update(config_hash=digest(proof.config),source_hash=source_hash)
            save(proof.directory/'manifest.json',proof.receipt)
            with self.assertRaisesRegex(ValueError,'training-core'):proof.verify()

    def test_live_train_validation_cannot_skip_canonical_smoke_proof(self):
        config=dict(stage='train',context=CONTEXT,files={},authorization={});inputs={'bound':'inputs'}
        content=b'reviewed';sources={'owned.py':hashlib.sha256(content).hexdigest()}
        auth=dict(stage='train',context=CONTEXT,input_hash=digest(inputs),sources=sources,code_sha='a'*40,
                  confirmed=True,training_authorized=True,independent_review_passed=True,explicit_gpu_go=True,
                  smoke_result=dict(path='/not-actual-smoke',sha256='0'*64))
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'auth.json';save(path,auth);config['authorization']=bind(path)
            with patch.object(command,'input_contract',return_value=inputs),patch.object(command,'sources',return_value=sources),\
                 patch.object(command.subprocess,'check_output',side_effect=lambda argv,**kwargs:'a'*40 if argv[1]=='rev-parse' else content),\
                 patch.object(command,'validate_canonical_smoke',side_effect=ValueError('canonical proof mandatory')) as proof,\
                 patch.object(command,'validate_assignment') as assignment:
                with self.assertRaisesRegex(ValueError,'canonical proof mandatory'):command.validate(config,inputs,command.RUNTIME)
                proof.assert_called_once_with(auth['smoke_result'],config,inputs);assignment.assert_not_called()

    def test_training_source_hash_binds_pixel_producer_and_new_counterexamples(self):
        self.assertIn('scripts/prepare_action_pixels_parallel.py',command.sources())
        self.assertIn('tests_orca/test_action_training_provenance.py',command.sources())

    def test_repeated_train_contracts_rehash_npys_and_never_open_raw_media(self):
        with tempfile.TemporaryDirectory() as t:
            f=Fixture(t);original=f.module.sha;opened=[]
            def checked(path):
                if Path(path).suffix=='.mp4':raise AssertionError('raw MP4 read')
                if Path(path).suffix=='.npy':opened.append(str(path))
                return original(path)
            with patch.object(f.module,'sha',side_effect=checked):
                for _ in range(4):f.contract()
            self.assertEqual(len(opened),4*len(f.rows));self.assertEqual(set(opened),{e['path'] for e in f.clips.values()})



if __name__=='__main__':unittest.main()
