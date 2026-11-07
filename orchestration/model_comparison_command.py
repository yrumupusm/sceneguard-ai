"""EXP-0066 fixed model comparison, exclusively through the canonical GPU queue."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess

from orchestration.queue import digest, process_state
from orchestration.action_training_command import checked_file, file_hash, resources, validate_assignment

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = Path('/home/jhc7484/dev/sceneguard-orca-lab/runtime/orca-lab/gpu-queue')
OUTPUT = ROOT/'outputs/model-comparison/exp0066/queued'
COHORT = ROOT/'outputs/model-comparison/exp0066/cohort-v1/manifest.json'
COHORT_SHA = '480b1410c568b9a038c7be6d124f7be1890b3b7375cbed43e87b165346a2aa18'
SMOKE_SHA = '8ee64caa28fed6b756aecf39c5d392c6b544f204ad12ed39ed617d727a3481c0'
BASELINE_SHA = '3799ae3eee427b60e698b21f6ee958ac5306eacba07b5d85e4c35dbfa6457b40'
MODEL_IDS = {'evad_vitb_vmaev2','evad_vitl','stmixer_vitb_vmaev2','internvideo_next_s2_l',
             'vjepa2_l','vjepa2_1_l','videomaev2_b','r3d18_exp0064'}
JOINT = {'evad_vitb_vmaev2','evad_vitl','stmixer_vitb_vmaev2'}


def read(path):
    # Native dependencies may change LC_CTYPE during a forward. Metadata is UTF-8.
    return json.loads(Path(path).read_text(encoding='utf-8'))


def interpreter(config):
    model = config['model_id']
    name = '.venv-exp0066-joint' if model in JOINT else (
        '.venv-cv-batch02' if model == 'r3d18_exp0064' else '.venv-exp0066-encoders')
    return ROOT/name/'bin/python'


def sources(config=None):
    names = ['orchestration/queue.py','orchestration/mock_job.py',
             'orchestration/action_training_command.py','orchestration/model_comparison_command.py',
             'scripts/run_model_comparison.py','docs/experiments/EXP-0066-protocol.md',
             'scripts/prepare_model_comparison.py','tests_orca/test_model_comparison.py']
    if config and config['model_id'] in JOINT:
        names += ['scripts/exp0066_joint_models.py','tests/test_exp0066_joint_models.py']
    else:
        names += ['scripts/exp0066_encoders.py']
    return {n:file_hash(ROOT/n) for n in names}


def model_contract(config):
    spec = read(checked_file(config['files']['model_spec']))
    if spec.get('model_id') != config['model_id'] or config['model_id'] not in MODEL_IDS:
        raise ValueError('Exact declared comparison model required')
    # Every external checkpoint/config/vendor Python file loaded by the adapter is bound.
    if not isinstance(spec.get('bindings'),dict) or not spec['bindings']:
        raise ValueError('Checkpoint/config/vendor dependency bindings required')
    for p,h in spec['bindings'].items(): checked_file(dict(path=p,sha256=h))
    if spec.get('checkpoint_path') not in spec['bindings']:
        raise ValueError('Checkpoint must be bound')
    if (config['model_id']=='r3d18_exp0064' and spec['bindings'][spec['checkpoint_path']]!=
            '8b4e2eb74bee656f651a172403e4ddfe1e1ce8f9a4438d70c76b5a1b17825b73'):
        raise ValueError('Preserved EXP0064 epoch6 checkpoint required')
    vendor = spec.get('vendor_path')
    if vendor:
        root = Path(vendor)
        if not root.is_absolute(): raise ValueError('Absolute vendor tree required')
        actual = {str(p):file_hash(p) for p in root.rglob('*.py') if '.git' not in p.parts}
        if not actual or any(spec['bindings'].get(p)!=h for p,h in actual.items()):
            raise ValueError('Complete vendor Python source binding required')
    return spec


def environment_contract(config,spec):
    from scripts.prepare_model_comparison import snapshot_environment
    path=spec.get('environment_path')
    if path not in spec['bindings']:raise ValueError('Bound environment snapshot required')
    if snapshot_environment(interpreter(config))!=read(path):
        raise ValueError('Interpreter dependencies/import origins changed')
    return spec['bindings'][path]


def input_contract(config):
    if set(config['files']) != {'cohort','model_spec','baseline_lock','smoke_windows'}:
        raise ValueError('Exact comparison input bindings required')
    paths = {k:checked_file(v) for k,v in config['files'].items()}
    if (paths['cohort'] != COHORT or config['files']['baseline_lock']['sha256'] != BASELINE_SHA
            or config['files']['cohort']['sha256']!=COHORT_SHA
            or config['files']['smoke_windows']['sha256']!=SMOKE_SHA):
        raise ValueError('Frozen cohort/baseline required')
    cohort = read(paths['cohort']); videos = cohort['videos']
    if len(videos)!=45 or {v['video_id'] for v in videos}!={f'E01_{i:03d}' for i in range(1,46)}:
        raise ValueError('Full original45 comparison domain required')
    baseline = read(paths['baseline_lock'])
    original = {v['video_id']:v for v in baseline['regression_only_videos']}
    bound = {}
    for v in videos:
        if v['source_sha256'] != original[v['video_id']]['sha256']:
            raise ValueError('Original source differs from regression-only baseline')
        checked_file(dict(path=v['source_path'],sha256=v['source_sha256']))
        for b in (v['native_pts_binding'],v['plan']):
            checked_file({k:b[k] for k in ('path','sha256')}); bound[b['path']]=b['sha256']
        bound[v['source_path']]=v['source_sha256']
    spec = model_contract(config)
    return dict(files={k:v['sha256'] for k,v in config['files'].items()},
                cohort_inputs=bound, model_inputs=spec['bindings'],
                environment_sha256=environment_contract(config,spec))


def validate_smoke(config,auth,inputs):
    proof_path=checked_file(auth['smoke_result']);proof=read(proof_path)
    receipt_path=checked_file(auth['smoke_receipt']);receipt=read(receipt_path)
    attempt=proof.get('queue_attempt','')
    if (proof_path!=output_path('smoke',attempt)/'result.json'
            or receipt_path!=RUNTIME/'attempts'/attempt/'manifest.json'
            or proof.get('status')!='smoke_passed' or proof.get('model_id')!=config['model_id']
            or proof.get('model_spec_sha256')!=config['files']['model_spec']['sha256']
            or proof.get('cohort_sha256')!=COHORT_SHA or proof.get('scored_windows')!=7
            or proof.get('queue_command')!='model-compare' or proof.get('input_hash')!=digest(inputs)
            or proof.get('source_hash')!=digest(sources(config))
            or receipt.get('execution_status')!='succeeded' or receipt.get('attempt_id')!=attempt
            or receipt.get('result_sha256')!=file_hash(proof_path)
            or receipt.get('result_path')!=str(proof_path.parent)):
        raise ValueError('Exact successful same-source/model/cohort smoke proof required')
    with sqlite3.connect('file:'+str(RUNTIME/'queue.sqlite3')+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        row=db.execute('SELECT j.*,a.status AS attempt_status,a.result_manifest FROM jobs j '
                       'JOIN attempts a USING(job_id) WHERE a.attempt_id=?',(attempt,)).fetchone()
    if (row is None or row['command']!='model-compare' or row['status']!='succeeded'
            or row['attempt_status']!='succeeded' or row['result_manifest']!=str(receipt_path)
            or row['source_hash']!=proof['source_hash'] or row['input_hash']!=proof['input_hash']
            or row['code_sha']!=proof['code_sha']
            or any(receipt['registration'].get(k)!=row[k] for k in
                   ('command','job_id','run_id','task_id','dispatch_id','owner','code_sha','source_hash','input_hash','config_hash'))):
        raise ValueError('Actual successful canonical smoke queue row required')
    old_config=json.loads(row['config_json'])
    if old_config['stage']!='smoke' or old_config['files']!=config['files']:
        raise ValueError('Smoke queue input selection differs')
    output=proof_path.parent/'windows.jsonl'
    if file_hash(output)!=proof['windows_sha256']:raise ValueError('Smoke windows output changed')


def validate(config, inputs, runtime):
    if (set(config)!={'stage','context','files','authorization','model_id','execution_revision'}
            or config['stage'] not in ('smoke','all45') or config['model_id'] not in MODEL_IDS
            or not re.fullmatch('[a-z0-9-]{1,64}',config['execution_revision'])
            or Path(runtime).resolve()!=RUNTIME or not interpreter(config).is_file()):
        raise ValueError('Canonical comparison runtime/model/stage/interpreter required')
    if input_contract(config)!=inputs: raise ValueError('Comparison input contract changed')
    auth = read(checked_file(config['authorization']))
    if (auth.get('context')!=config['context'] or auth.get('stage')!=config['stage']
            or auth.get('model_id')!=config['model_id'] or auth.get('input_hash')!=digest(inputs)
            or auth.get('execution_revision')!=config['execution_revision']
            or auth.get('sources')!=sources(config)
            or any(auth.get(k) is not True for k in
                   ('confirmed','comparison_authorized','independent_review_passed','root_go','explicit_gpu_go'))):
        raise ValueError('Independent reviewed exact model/input/source and GPU GO required')
    head = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if auth.get('code_sha')!=head: raise ValueError('Reviewed committed source HEAD differs')
    for name,h in auth['sources'].items():
        if hashlib.sha256(subprocess.check_output(['git','show',head+':'+name],cwd=ROOT)).hexdigest()!=h:
            raise ValueError('Reviewed source must be committed: '+name)
    if config['stage']=='all45':
        validate_smoke(config,auth,inputs)
    return dict(authorization=auth,live_assignment=validate_assignment(config['context']))


def job_key(config):
    return 'exp0066-'+config['model_id']+'-'+config['stage']+'-'+config['execution_revision']+'-'+digest(config['files'])


def output_path(stage,attempt):
    if stage not in ('smoke','all45') or not re.fullmatch('[0-9a-f]{32}',attempt):
        raise ValueError('Exact stage/attempt required')
    return OUTPUT/stage/attempt


def command(config,inputs,runtime,attempt,lock_fd):
    provenance=validate(config,inputs,runtime);os.fstat(lock_fd);resources()
    directory=Path(runtime)/'attempts'/attempt;directory.mkdir(parents=True,exist_ok=True)
    snapshot=directory/'model-comparison-config.json'
    with snapshot.open('x') as stream: json.dump(config,stream,sort_keys=True,indent=2)
    (directory/'model-comparison-assignment.json').write_text(json.dumps(provenance,sort_keys=True,indent=2)+'\n')
    return [str(interpreter(config)),'-I',str(ROOT/'scripts/run_model_comparison.py'),
            '--queue-config',str(snapshot),'--queue-config-sha256',file_hash(snapshot),
            '--queue-attempt',attempt,'--output',str(output_path(config['stage'],attempt))]


def runner_guard(args):
    from orchestration.queue import source_hash
    fd=int(os.environ['SCENEGUARD_GPU_LOCK_FD'])
    actual,held=(RUNTIME/'gpu.lock').stat(),os.fstat(fd)
    if (actual.st_dev,actual.st_ino)!=(held.st_dev,held.st_ino):raise ValueError('Wrong reservation FD')
    with (RUNTIME/'gpu.lock').open('a+') as probe:
        try:fcntl.flock(probe,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:pass
        else:raise ValueError('Canonical reservation is not held')
    fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    snapshot=Path(args.queue_config)
    if snapshot!=RUNTIME/'attempts'/args.queue_attempt/'model-comparison-config.json':
        raise ValueError('Canonical attempt snapshot required')
    if file_hash(snapshot)!=args.queue_config_sha256:raise ValueError('Queue snapshot changed')
    config=read(snapshot)
    if args.output.resolve()!=output_path(config['stage'],args.queue_attempt):raise ValueError('Output differs')
    with sqlite3.connect('file:'+str(RUNTIME/'queue.sqlite3')+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        row=db.execute('SELECT j.*,a.status AS attempt_status,a.supervisor_pid,a.supervisor_identity '
                       'FROM jobs j JOIN attempts a USING(job_id) WHERE a.attempt_id=?',(args.queue_attempt,)).fetchone()
    if row is None:raise ValueError('Actual running canonical attempt required')
    inputs=json.loads(row['input_json']);provenance=validate(config,inputs,RUNTIME)
    if (row['command']!='model-compare' or row['status']!='running' or row['attempt_status']!='running'
            or json.loads(row['config_json'])!=config or row['config_hash']!=digest(config)
            or row['input_hash']!=digest(inputs) or row['source_hash']!=source_hash('model-compare',config)
            or row['job_key']!=job_key(config) or row['code_sha']!=provenance['authorization']['code_sha']
            or any(row[k]!=v for k,v in config['context'].items())
            or process_state(row['supervisor_pid'],row['supervisor_identity'])!='live'):
        raise ValueError('Actual running canonical comparison attempt required')
    if os.environ.get('CUDA_VISIBLE_DEVICES')!='0':raise ValueError('Canonical GPU0 required')
    resources()
    return config,inputs


def retry_guard(db,job):
    raise ValueError('Comparison retry needs separately reviewed execution revision')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Read-only comparison contract; no execution')
    parser.add_argument('--queue-config',type=Path,required=True);args=parser.parse_args()
    print(json.dumps(input_contract(read(args.queue_config)),sort_keys=True,indent=2))
