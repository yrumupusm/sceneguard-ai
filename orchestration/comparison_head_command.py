"""EXP0066 comparison-head canonical contract. Queue registration belongs to root later."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess

from orchestration.queue import digest,process_state
from orchestration.action_training_command import checked_file,file_hash,resources,validate_assignment
from orchestration.model_comparison_command import JOINT,MODEL_IDS,interpreter,model_contract,environment_contract
from scripts.prepare_comparison_head_data import embargo,select_smoke

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=Path('/home/jhc7484/dev/sceneguard-orca-lab/runtime/orca-lab/gpu-queue')
OUTPUT=ROOT/'outputs/model-comparison/exp0066/head-preparation/queued'
PLAN=ROOT/'outputs/model-comparison/exp0066/head-plan-v2/manifest.json'
PLAN_SHA='28cd2ad0f57ec2230c8de5acf18dae56046ecf512e0e46f917de6c4c577add18'
STAGES={'feature-smoke','feature-full','train'}
MODELS=MODEL_IDS-{'r3d18_exp0064'}
BASE_FILES={'plan','preparation','model_spec','release'}


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def sources(config=None):
    names=['orchestration/queue.py','orchestration/mock_job.py','orchestration/action_training_command.py',
           'orchestration/model_comparison_command.py','orchestration/comparison_head_command.py',
           'scripts/run_model_comparison.py','scripts/prepare_comparison_head_data.py',
           'scripts/extract_comparison_head_features.py','scripts/train_comparison_heads.py',
           'tests/test_comparison_head_data.py','tests/test_comparison_heads.py',
           'tests_orca/test_comparison_head_command.py','docs/experiments/EXP-0066-head-protocol.md']
    names+=['scripts/exp0066_joint_models.py' if config and config['model_id'] in JOINT else 'scripts/exp0066_encoders.py']
    return {name:file_hash(ROOT/name) for name in names}


def selected_windows(config,plan):
    return [w for w in plan['windows'] if config['stage']!='feature-smoke' or w['window_id'] in plan['smoke_window_ids']]


def input_contract(config):
    required=BASE_FILES|({'features'} if config['stage']=='train' else set())
    if config['stage'] not in STAGES or config['model_id'] not in MODELS or set(config['files'])!=required:raise ValueError('Exact head stage/model/input bindings required')
    paths={k:checked_file(v) for k,v in config['files'].items()}
    if paths['plan']!=PLAN or config['files']['plan']['sha256']!=PLAN_SHA:raise ValueError('Frozen head plan v2 required')
    plan=read(paths['plan']);embargo(plan)
    if (plan['schema_version']!=2 or len(plan['windows'])!=3984 or plan['training_release'] is not False
            or plan['smoke_window_ids']!=select_smoke(plan['windows'])
            or plan['fullframe_negative_semantics_human_verified'] is not False):raise ValueError('Exact protected weak-reference plan required')
    prepared=read(paths['preparation']);release=read(paths['release'])
    if (prepared.get('status')!='cpu_pixels_verified_not_training_release' or prepared.get('windows')!=3984
            or prepared.get('unique_source_hashes')!=792 or prepared.get('label_files_verified')!=797
            or prepared.get('plan')!=config['files']['plan'] or prepared.get('semantic_ground_truth_verified') is not False
            or prepared.get('protected_test_pixels_or_labels_read') is not False):raise ValueError('Complete actual native-pixel CPU preparation required')
    if (release.get('plan')!=config['files']['plan'] or release.get('preparation')!=config['files']['preparation']
            or any(release.get(k) is not True for k in ('training_release','weak_reference_training_authorized','independent_review_passed','root_go'))
            or release.get('semantic_ground_truth_verified') is not False):raise ValueError('Explicit reviewed weak-reference training release required')
    proof_bindings={};proofs={};covered=set()
    for b in prepared['sources']:
        p=checked_file({k:b[k] for k in ('path','sha256')});proof=read(p);proof_bindings[str(p)]=b['sha256']
        if proof['source_sha256'] in proofs:raise ValueError('Duplicate CPU source receipt')
        proofs[proof['source_sha256']]=proof
        for w in proof['windows']:
            if w['window_id'] in covered or w['observed_unique_frames']!=7 or not re.fullmatch('[0-9a-f]{64}',w['rgb_slots_sha256']):raise ValueError('Invalid native window receipt')
            covered.add(w['window_id'])
    if covered!={w['window_id'] for w in plan['windows']} or len(proofs)!=792:raise ValueError('Incomplete CPU pixel receipts')
    for w in plan['windows']:
        proof=proofs[w['source_sha256']]
        if proof['source_path']!=w['source_path'] or proof['source_size']!=w['source_size'] or proof['time_base']!=w['time_base']:raise ValueError('CPU source geometry/clock changed')
        frames={f['pts_tick']:f for f in proof['frames']}
        if any(t not in frames for t in w['sample_pts_ticks']):raise ValueError('Missing native RGB receipt')
    # Hash each selected source path once per contract, including alternate-name targets.
    pixels={};labels={}
    for w in selected_windows(config,plan):
        pixels[w['source_path']]=w['source_sha256']
        for t in w['targets']:
            pixels[t['source_path']]=t['source_sha256'];labels[t['label_path']]=t['label_sha256']
    for p,h in {**pixels,**labels}.items():checked_file(dict(path=p,sha256=h))
    spec=model_contract(config)
    native_binding=None
    if config['stage']=='train':
        native=paths['features'].parent/'native-outputs.jsonl'
        native_binding=dict(path=str(native),sha256=file_hash(native))
        checked_file(native_binding)
    return dict(files={k:v['sha256'] for k,v in config['files'].items()},selected_sources=pixels,
                selected_labels=labels,pixel_receipts=proof_bindings,model_inputs=spec['bindings'],
                environment_sha256=environment_contract(config,spec),feature_native_output=native_binding)


def output_path(stage,attempt):
    if stage not in STAGES or not re.fullmatch('[0-9a-f]{32}',attempt):raise ValueError('Exact head stage/attempt required')
    return OUTPUT/stage/attempt


def canonical_proof(binding,receipt_binding,stage,config):
    path=checked_file(binding);receipt_path=checked_file(receipt_binding);proof=read(path);receipt=read(receipt_path)
    attempt=proof.get('queue_attempt','')
    if (path!=output_path(stage,attempt)/'result.json' or receipt_path!=RUNTIME/'attempts'/attempt/'manifest.json'
            or proof.get('stage')!=stage or proof.get('queue_command')!='comparison-head'
            or proof.get('model_id')!=config['model_id'] or proof.get('source_hash')!=digest(sources(config))
            or proof.get('model_spec_sha256')!=config['files']['model_spec']['sha256']
            or proof.get('plan_sha256')!=PLAN_SHA or receipt.get('execution_status')!='succeeded'
            or receipt.get('attempt_id')!=attempt or receipt.get('result_sha256')!=file_hash(path)
            or receipt.get('result_path')!=str(path.parent)):raise ValueError('Exact canonical head result/receipt required')
    with sqlite3.connect('file:'+str(RUNTIME/'queue.sqlite3')+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        row=db.execute('SELECT j.*,a.status AS attempt_status,a.result_manifest FROM jobs j JOIN attempts a USING(job_id) WHERE a.attempt_id=?',(attempt,)).fetchone()
    if (row is None or row['command']!='comparison-head' or row['status']!='succeeded' or row['attempt_status']!='succeeded'
            or row['result_manifest']!=str(receipt_path) or row['source_hash']!=proof['source_hash']
            or row['input_hash']!=proof['input_hash'] or row['code_sha']!=proof['code_sha']
            or any(receipt['registration'].get(k)!=row[k] for k in ('command','job_id','run_id','task_id','dispatch_id','owner','code_sha','source_hash','input_hash','config_hash'))):raise ValueError('Actual successful canonical head queue row required')
    prior=json.loads(row['config_json']);prior_inputs=json.loads(row['input_json'])
    if (prior['stage']!=stage or {k:prior['files'][k] for k in BASE_FILES}!={k:config['files'][k] for k in BASE_FILES}
            or digest(prior_inputs)!=proof['input_hash'] or digest(prior)!=row['config_hash']):raise ValueError('Prior canonical input/config selection changed')
    features=path.parent/'features.jsonl'
    if file_hash(features)!=proof['features_sha256']:raise ValueError('Canonical features changed')
    native=path.parent/'native-outputs.jsonl'
    if file_hash(native)!=proof['native_outputs_sha256']:raise ValueError('Canonical native outputs changed')
    plan=read(config['files']['plan']['path']);expected=selected_windows({**config,'stage':stage},plan)
    if (proof.get('status')!=('feature_smoke_passed' if stage=='feature-smoke' else 'features_complete')
            or proof.get('windows')!=len(expected) or set(proof.get('window_ids',[]))!={w['window_id'] for w in expected}
            or len(proof.get('window_ids',[]))!=len(expected) or not proof.get('feature_dimension')):raise ValueError('Complete finite canonical features required')
    # Parse actual bytes: a receipt cannot promote an empty/nonfinite feature stream.
    from scripts.train_comparison_heads import feature_dataset
    feature_dataset(features,{**plan,'windows':expected},config['model_id'] in JOINT,require_both=False)
    from scripts.extract_comparison_head_features import audit_native_outputs
    coverage=audit_native_outputs(native,features,{**plan,'windows':expected},config['model_id'] in JOINT)
    if coverage!=proof['coverage_by_split']:raise ValueError('Native matching coverage summary differs')
    return features,proof


def validate(config,inputs,runtime):
    if (set(config)!={'stage','context','files','authorization','model_id','execution_revision'}
            or config['stage'] not in STAGES or config['model_id'] not in MODELS
            or not re.fullmatch('[a-z0-9-]{1,64}',config['execution_revision'])
            or Path(runtime).resolve()!=RUNTIME or not interpreter(config).is_file()):raise ValueError('Canonical head runtime/model/stage/interpreter required')
    if input_contract(config)!=inputs:raise ValueError('Head input contract changed')
    auth=read(checked_file(config['authorization']))
    flags=('confirmed','head_authorized','independent_review_passed','root_go')+(() if config['stage']=='train' else ('explicit_gpu_go',))
    if (auth.get('context')!=config['context'] or auth.get('stage')!=config['stage'] or auth.get('model_id')!=config['model_id']
            or auth.get('execution_revision')!=config['execution_revision'] or auth.get('input_hash')!=digest(inputs)
            or auth.get('sources')!=sources(config) or any(auth.get(k) is not True for k in flags)):
        raise ValueError('Independent reviewed exact source/input/context and root GO required')
    if config['stage']=='train' and auth.get('cpu_training_authorized') is not True:raise ValueError('Explicit CPU head fitting authorization required')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if auth.get('code_sha')!=head:raise ValueError('Reviewed committed source HEAD differs')
    for name,h in auth['sources'].items():
        if hashlib.sha256(subprocess.check_output(['git','show',head+':'+name],cwd=ROOT)).hexdigest()!=h:raise ValueError('Reviewed source must be committed: '+name)
    if config['stage']=='feature-full':canonical_proof(auth['smoke_result'],auth['smoke_receipt'],'feature-smoke',config)
    if config['stage']=='train':
        features,_=canonical_proof(auth['feature_result'],auth['feature_receipt'],'feature-full',config)
        if features!=Path(config['files']['features']['path']):raise ValueError('Exact completed full features required')
    return dict(authorization=auth,live_assignment=validate_assignment(config['context']))


def job_key(config):
    return 'exp0066-head-'+config['model_id']+'-'+config['stage']+'-'+config['execution_revision']+'-'+digest(config['files'])


def command(config,inputs,runtime,attempt,lock_fd):
    provenance=validate(config,inputs,runtime);os.fstat(lock_fd)
    if config['stage']!='train':resources()
    directory=Path(runtime)/'attempts'/attempt;directory.mkdir(parents=True,exist_ok=True)
    snapshot=directory/'comparison-head-config.json'
    with snapshot.open('x',encoding='utf-8') as stream:json.dump(config,stream,sort_keys=True,indent=2)
    with (directory/'comparison-head-assignment.json').open('x',encoding='utf-8') as stream:json.dump(provenance,stream,sort_keys=True,indent=2)
    argv=[str(interpreter(config)),'-I',str(ROOT/'scripts/extract_comparison_head_features.py'),
          '--queue-config',str(snapshot),'--queue-config-sha256',file_hash(snapshot),
          '--queue-attempt',attempt,'--output',str(output_path(config['stage'],attempt))]
    return ['/usr/bin/env','CUDA_VISIBLE_DEVICES=','OMP_NUM_THREADS=2','OPENBLAS_NUM_THREADS=2',*argv] if config['stage']=='train' else argv


def runner_guard(args):
    fd=int(os.environ['SCENEGUARD_GPU_LOCK_FD']);actual=(RUNTIME/'gpu.lock').stat();held=os.fstat(fd)
    if (actual.st_dev,actual.st_ino)!=(held.st_dev,held.st_ino):raise ValueError('Wrong reservation FD')
    with (RUNTIME/'gpu.lock').open('a+') as probe:
        try:fcntl.flock(probe,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:pass
        else:raise ValueError('Canonical reservation is not held')
    fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    snapshot=Path(args.queue_config)
    if snapshot!=RUNTIME/'attempts'/args.queue_attempt/'comparison-head-config.json':raise ValueError('Canonical attempt snapshot required')
    if file_hash(snapshot)!=args.queue_config_sha256:raise ValueError('Queue snapshot changed')
    config=read(snapshot)
    if args.output.resolve()!=output_path(config['stage'],args.queue_attempt):raise ValueError('Output differs')
    with sqlite3.connect('file:'+str(RUNTIME/'queue.sqlite3')+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        row=db.execute('SELECT j.*,a.status AS attempt_status,a.supervisor_pid,a.supervisor_identity FROM jobs j JOIN attempts a USING(job_id) WHERE a.attempt_id=?',(args.queue_attempt,)).fetchone()
    if row is None:raise ValueError('Actual running canonical attempt required')
    inputs=json.loads(row['input_json']);provenance=validate(config,inputs,RUNTIME)
    if (row['command']!='comparison-head' or row['status']!='running' or row['attempt_status']!='running'
            or json.loads(row['config_json'])!=config or row['config_hash']!=digest(config)
            or row['input_hash']!=digest(inputs) or row['source_hash']!=digest(sources(config))
            or row['job_key']!=job_key(config) or row['code_sha']!=provenance['authorization']['code_sha']
            or any(row[k]!=v for k,v in config['context'].items())
            or process_state(row['supervisor_pid'],row['supervisor_identity'])!='live'):raise ValueError('Actual running canonical head attempt required')
    if os.environ.get('CUDA_VISIBLE_DEVICES')!=('' if config['stage']=='train' else '0'):raise ValueError('Canonical head device visibility required')
    if config['stage']!='train':resources()
    return config,inputs


def retry_guard(db,job):raise ValueError('Head retry needs separately reviewed execution revision')
