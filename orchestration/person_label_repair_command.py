"""Exact75-frame draft-only person proposals, exclusively through the shared queue."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess

from orchestration.action_training_command import checked_file,file_hash,resources,validate_assignment
from orchestration.queue import digest,process_state
from orchestration import model_comparison_command as comparison

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=comparison.RUNTIME
OUTPUT=ROOT/'outputs/model-comparison/exp0066/label-repair-v1/queued'
PREPARATION=ROOT/'outputs/model-comparison/exp0066/label-repair-v1/prepared-v1/manifest.json'
PREPARATION_SHA='758660c56333e6712c980c6f0f8eddaff93fcc9d7594fcc8dadf5c8191324aa8'
MODEL_SPEC=ROOT/'runtime/model-comparison/exp0066/yolo26-specs-v1/yolo26x.json'
MODEL_SPEC_SHA='e314c38d874e3a73903fb387e7f611a07c067a16d017e3a3367d04012c45136f'
CONTEXT=dict(run_id='run_3d23462a014a',task_id='task_2cc40cbc8e6e',dispatch_id='ctx_6fdc2f3a6d68',owner='term_12928c5f-4b0d-4d2d-934f-d104b905e0dc')
RELEASE_KEYS=('context','stage','model_id','execution_revision','code_sha','sources','files','inputs','input_hash','executor','queue_initial')
FLAGS=('confirmed','draft_authorized','independent_review_passed','root_go','explicit_gpu_go')


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def interpreter(config=None):return ROOT/'.venv-pose-batch03/bin/python'


def sources(config=None):
    names=['orchestration/queue.py','orchestration/mock_job.py','orchestration/action_training_command.py',
           'orchestration/model_comparison_command.py','orchestration/person_label_repair_command.py',
           'scripts/prepare_person_label_repair.py','scripts/infer_person_label_repair.py',
           'scripts/exp0066_yolo.py','scripts/prepare_model_comparison.py','tests/test_person_label_repair.py']
    return {p:file_hash(ROOT/p) for p in names}


def input_contract(config):
    from scripts.prepare_person_label_repair import validate_preparation
    if (config.get('model_id')!='yolo26x' or config.get('stage')!='draft75'
            or set(config['files'])!={'preparation','model_spec'}):raise ValueError('Bounded draft75 YOLO26x inputs required')
    if (checked_file(config['files']['preparation'])!=PREPARATION
            or config['files']['preparation']['sha256']!=PREPARATION_SHA
            or checked_file(config['files']['model_spec'])!=MODEL_SPEC
            or config['files']['model_spec']['sha256']!=MODEL_SPEC_SHA):raise ValueError('Exact frozen75 preparation/spec required')
    prepared=validate_preparation(PREPARATION)
    spec=comparison.model_contract(config)
    return dict(files={k:v['sha256'] for k,v in config['files'].items()},prepared_inputs=prepared,
                model_inputs=spec['bindings'],environment_sha256=comparison.environment_contract(config,spec))


def validate(config,inputs,runtime):
    if (set(config)!={'stage','model_id','context','execution_revision','files','authorization'}
            or config['stage']!='draft75' or config['model_id']!='yolo26x' or config['context']!=CONTEXT
            or config['execution_revision']!='label-repair-v1' or Path(runtime).resolve()!=RUNTIME
            or not interpreter(config).is_file()):raise ValueError('Exact bounded repair assignment/config required')
    if input_contract(config)!=inputs:raise ValueError('Repair input bytes changed')
    auth=read(checked_file(config['authorization']))
    if (any(auth.get(k) is not True for k in FLAGS)
            or any(auth.get(k)!=config[k] for k in ('stage','model_id','context','execution_revision'))
            or auth.get('input_hash')!=digest(inputs) or auth.get('sources')!=sources(config)):
        raise ValueError('Exact reviewed repair authorization and new root GO required')
    grant=read(checked_file(auth['root_grant']));review=read(checked_file(auth['independent_review']))
    candidate=read(checked_file(grant['candidate']))
    if (grant.get('status')!='root_authorized_person_label_repair'
            or any(grant.get(k) is not True for k in FLAGS)
            or review.get('status')!='accepted_person_label_repair_execution_release'
            or review.get('independent_review_passed') is not True
            or review.get('candidate')!=grant['candidate']
            or grant.get('independent_review')!=auth['independent_review']
            or candidate.get('status')!='person_label_repair_release_candidate'
            or auth.get('root_go_message')!=grant.get('root_go_message')
            or not str(auth.get('root_go_message','')).startswith('msg_')):
        raise ValueError('Actual independent bounded execution release and root grant required')
    for key in RELEASE_KEYS:
        if review.get(key)!=grant.get(key) or candidate.get(key)!=grant.get(key):raise ValueError('Reviewed repair grant differs: '+key)
    if (grant.get('context')!=CONTEXT or grant.get('stage')!='draft75' or grant.get('model_id')!='yolo26x'
            or grant.get('execution_revision')!=config['execution_revision'] or grant.get('files')!=config['files']
            or grant.get('sources')!=auth['sources'] or grant.get('input_hash')!=digest(inputs)
            or grant.get('code_sha')!=auth.get('code_sha')):raise ValueError('Repair grant selection differs')
    checked_file(grant['executor']);checked_file(grant['queue_initial'])
    if read(checked_file(grant['inputs']))!=inputs:raise ValueError('Reviewed actual input contract differs')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if auth.get('code_sha')!=head:raise ValueError('Reviewed committed HEAD changed')
    for path,h in auth['sources'].items():
        if hashlib.sha256(subprocess.check_output(['git','show',head+':'+path],cwd=ROOT)).hexdigest()!=h:
            raise ValueError('Uncommitted repair source '+path)
    return dict(authorization=auth,live_assignment=validate_assignment(CONTEXT))


def job_key(config):return 'exp0066-person-label-repair-'+config['execution_revision']+'-'+digest(config['files'])


def output_path(stage,attempt):
    if stage!='draft75' or not re.fullmatch('[0-9a-f]{32}',attempt):raise ValueError('Exact draft75 attempt required')
    return OUTPUT/stage/attempt


def command(config,inputs,runtime,attempt,lock_fd):
    proof=validate(config,inputs,runtime);os.fstat(lock_fd);resources()
    directory=Path(runtime)/'attempts'/attempt;directory.mkdir(parents=True,exist_ok=True)
    snapshot=directory/'person-label-repair-config.json'
    with snapshot.open('x',encoding='utf-8') as f:json.dump(config,f,sort_keys=True,indent=2);f.write('\n')
    with (directory/'person-label-repair-assignment.json').open('x',encoding='utf-8') as f:json.dump(proof,f,sort_keys=True,indent=2);f.write('\n')
    return [str(interpreter(config)),'-I',str(ROOT/'scripts/infer_person_label_repair.py'),
            '--queue-config',str(snapshot),'--queue-config-sha256',file_hash(snapshot),
            '--queue-attempt',attempt,'--output',str(output_path(config['stage'],attempt))]


def runner_guard(args):
    fd=int(os.environ['SCENEGUARD_GPU_LOCK_FD']);actual=(RUNTIME/'gpu.lock').stat();held=os.fstat(fd)
    if (actual.st_dev,actual.st_ino)!=(held.st_dev,held.st_ino):raise ValueError('Wrong canonical reservation FD')
    with (RUNTIME/'gpu.lock').open('a+') as probe:
        try:fcntl.flock(probe,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:pass
        else:raise ValueError('Canonical reservation is not held')
    fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    snapshot=Path(args.queue_config)
    if (snapshot!=RUNTIME/'attempts'/args.queue_attempt/'person-label-repair-config.json'
            or file_hash(snapshot)!=args.queue_config_sha256):raise ValueError('Canonical attempt snapshot differs')
    config=read(snapshot)
    if args.output.resolve()!=output_path(config['stage'],args.queue_attempt):raise ValueError('Canonical output differs')
    with sqlite3.connect('file:'+str(RUNTIME/'queue.sqlite3')+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        row=db.execute('SELECT j.*,a.status AS attempt_status,a.supervisor_pid,a.supervisor_identity '
                       'FROM jobs j JOIN attempts a USING(job_id) WHERE a.attempt_id=?',(args.queue_attempt,)).fetchone()
    if row is None:raise ValueError('Actual running repair attempt required')
    inputs=json.loads(row['input_json']);proof=validate(config,inputs,RUNTIME)
    if (row['command']!='person-label-repair' or row['status']!='running' or row['attempt_status']!='running'
            or json.loads(row['config_json'])!=config or row['config_hash']!=digest(config)
            or row['input_hash']!=digest(inputs) or row['source_hash']!=digest(sources(config))
            or row['job_key']!=job_key(config) or row['code_sha']!=proof['authorization']['code_sha']
            or any(row[k]!=v for k,v in CONTEXT.items())
            or process_state(row['supervisor_pid'],row['supervisor_identity'])!='live'
            or os.environ.get('CUDA_VISIBLE_DEVICES')!='0'):raise ValueError('Exact live canonical repair context required')
    resources()
    return config,inputs


def retry_guard(db,job):raise ValueError('Label repair retry requires a separately reviewed revision')
