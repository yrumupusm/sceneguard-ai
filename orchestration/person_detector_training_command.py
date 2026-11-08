"""EXP68 exact75-frame confirmed person-only training, exclusively through the shared queue."""
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
OUTPUT=ROOT/'outputs/model-comparison/exp0068/queued'
DATASET=ROOT/'outputs/model-comparison/exp0067/confirmed-person-v1/manifest.json'
DATASET_SHA='1bda84cc3421bcfc1b528bfb4e4092c02e9ec22d4a09c41907ff46211381ad18'
MODEL_SPEC=ROOT/'runtime/model-comparison/exp0066/yolo26-specs-v1/yolo26m.json'
MODEL_SPEC_SHA='80525b9a4ca9951aa2bdc9d92e5af2fd4d0727c021357d3831eb442657353d7a'
CONTEXT=dict(run_id='run_3d23462a014a',task_id='task_4d59dff177fe',dispatch_id='ctx_b6e78151c35e',owner='term_0dcdcd74-7a85-4116-adb3-03f014b4546a')
RELEASE_KEYS=('context','stage','model_id','execution_revision','code_sha','sources','files','inputs','input_hash','executor','queue_initial')
FLAGS=('confirmed','training_authorized','independent_review_passed','root_go','explicit_gpu_go')


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def interpreter(config=None):return ROOT/'.venv-pose-batch03/bin/python'


def sources(config=None):
    names=['orchestration/queue.py','orchestration/mock_job.py','orchestration/action_training_command.py',
           'orchestration/model_comparison_command.py','orchestration/person_detector_training_command.py',
           'scripts/train_person_detector.py','scripts/exp0066_yolo.py','scripts/prepare_model_comparison.py',
           'tests/test_person_detector_training.py','docs/experiments/EXP-0068-protocol.md',
           'scripts/evaluate_person_detector_pair.py','tests/test_person_detector_pair.py',
           'scripts/export_confirmed_person_boxes.py','webapp/review_request_store.py']
    return {p:file_hash(ROOT/p) for p in names}


def current_review_contract(manifest):
    responses=ROOT/'runtime/model-comparison/exp0067/review-application-v1/acknowledged-answers.json'
    if file_hash(responses)!=manifest['responses_sha256']:raise ValueError('Bound EXP67 responses changed')
    # Use web environment: pinned detector environment intentionally lacks FastAPI.
    code="""import json,sys
sys.path.insert(0,sys.argv[1])
from scripts.export_confirmed_person_boxes import current_answers,read
current_answers(read(sys.argv[2]),read(sys.argv[3]))
print(json.dumps({'current_answers_verified':True}))
"""
    result=json.loads(subprocess.check_output([
        '/home/jhc7484/dev/sceneguard-orca-lab/.venv-orca-lab/bin/python','-I','-c',code,str(ROOT),
        '/home/jhc7484/dev/sceneguard-orca-lab/runtime/orca-lab/local_config.json',str(responses)],
        cwd=ROOT,text=True,timeout=30))
    if result!={'current_answers_verified':True}:raise ValueError('Current EXP67 answer check failed')
    expected={r['id']:r for r in read(responses)['requests']}
    for row in manifest['frames']:
        answer=expected[row['request_id']]
        if row['answer_version']!=answer['answer_version'] or row['source_binding_sha256']!=answer['source_binding_sha256']:
            raise ValueError('Dataset/current answer binding differs')
    return dict(responses_sha256=manifest['responses_sha256'],current_answer_versions={k:v['answer_version'] for k,v in expected.items()})


def input_contract(config):
    from scripts.train_person_detector import SETTINGS
    if (config.get('model_id')!='yolo26m' or config.get('stage')!='train5'
            or set(config['files'])!={'dataset','model_spec'}):raise ValueError('Exact person pilot inputs required')
    if (checked_file(config['files']['dataset'])!=DATASET or config['files']['dataset']['sha256']!=DATASET_SHA
            or checked_file(config['files']['model_spec'])!=MODEL_SPEC
            or config['files']['model_spec']['sha256']!=MODEL_SPEC_SHA):raise ValueError('Frozen confirmed75/spec required')
    manifest=read(DATASET);review=current_review_contract(manifest);spec=comparison.model_contract(config)
    if (manifest.get('person_boxes_human_verified') is not True or manifest.get('protected_school_or_test_used') is not False
            or manifest.get('action_ground_truth_verified') is not False or len(manifest['frames'])!=75):
        raise ValueError('Explicit confirmed person-only dataset required')
    frames=manifest['frames'];seen=set();groups={};pixels={};counts={};boxes={};source_splits={}
    for row in frames:
        if (row['frame_id'] in seen or row['split'] not in ('train','validation') or row['answer_version']!=1
                or row['person_completeness_verified'] is not True or row['action_ground_truth_verified'] is not False
                or row['identity_ground_truth_verified'] is not False):raise ValueError('Confirmed unique frame scope differs')
        seen.add(row['frame_id']);split=row['split'];groups.setdefault(split,set()).add(row['event_group'])
        source_splits.setdefault(row['source_sha256'],set()).add(split)
        counts[split]=counts.get(split,0)+1;boxes[split]=boxes.get(split,0)+len(row['confirmed_person_boxes'])
        for field in ('image','label'):
            path=DATASET.parent/row[field]
            if not path.resolve().is_relative_to(DATASET.parent.resolve()):raise ValueError('Image/label escapes dataset')
            checked_file(dict(path=str(path),sha256=row[field+'_sha256']));pixels[str(path)]=row[field+'_sha256']
    if (counts!={'train':50,'validation':25} or boxes!={'train':151,'validation':31}
            or {k:len(v) for k,v in groups.items()}!={'train':2,'validation':1}
            or groups['train'] & groups['validation'] or any(len(v)!=1 for v in source_splits.values())):
        raise ValueError('Exact75 fixed disjoint source/group split required')
    if config.get('checkpoint_path',spec['checkpoint_path'])!=spec['checkpoint_path']:
        raise ValueError('Exact pretrained checkpoint required')
    return dict(files={k:v['sha256'] for k,v in config['files'].items()},pixels=pixels,
                settings=SETTINGS,current_reviews=review,model_inputs=spec['bindings'],environment_sha256=comparison.environment_contract(config,spec))


def validate(config,inputs,runtime):
    if (set(config)!={'stage','model_id','context','execution_revision','files','authorization','checkpoint_path'}
            or config['stage']!='train5' or config['model_id']!='yolo26m' or config['context']!=CONTEXT
            or config['execution_revision']!='person-pilot-v1' or Path(runtime).resolve()!=RUNTIME
            or not interpreter(config).is_file()):raise ValueError('Exact bounded training assignment/config required')
    if input_contract(config)!=inputs:raise ValueError('Training input bytes changed')
    auth=read(checked_file(config['authorization']))
    if (any(auth.get(k) is not True for k in FLAGS)
            or any(auth.get(k)!=config[k] for k in ('stage','model_id','context','execution_revision'))
            or auth.get('input_hash')!=digest(inputs) or auth.get('sources')!=sources(config)):
        raise ValueError('Exact reviewed training authorization and new root GO required')
    grant=read(checked_file(auth['root_grant']));review=read(checked_file(auth['independent_review']))
    candidate=read(checked_file(grant['candidate']))
    if (grant.get('status')!='root_authorized_person_detector_training'
            or any(grant.get(k) is not True for k in FLAGS)
            or review.get('status')!='accepted_person_detector_training_execution_release'
            or review.get('independent_review_passed') is not True
            or review.get('candidate')!=grant['candidate']
            or grant.get('independent_review')!=auth['independent_review']
            or candidate.get('status')!='person_detector_training_release_candidate'
            or auth.get('root_go_message')!=grant.get('root_go_message')
            or not str(auth.get('root_go_message','')).startswith('msg_')):
        raise ValueError('Actual independent bounded execution release and root grant required')
    for key in RELEASE_KEYS:
        if review.get(key)!=grant.get(key) or candidate.get(key)!=grant.get(key):raise ValueError('Reviewed training grant differs: '+key)
    if (grant.get('context')!=CONTEXT or grant.get('stage')!='train5' or grant.get('model_id')!='yolo26m'
            or grant.get('execution_revision')!=config['execution_revision'] or grant.get('files')!=config['files']
            or grant.get('sources')!=auth['sources'] or grant.get('input_hash')!=digest(inputs)
            or grant.get('code_sha')!=auth.get('code_sha')):raise ValueError('Training grant selection differs')
    checked_file(grant['executor']);checked_file(grant['queue_initial'])
    if read(checked_file(grant['inputs']))!=inputs:raise ValueError('Reviewed actual input contract differs')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if auth.get('code_sha')!=head:raise ValueError('Reviewed committed HEAD changed')
    for path,h in auth['sources'].items():
        if hashlib.sha256(subprocess.check_output(['git','show',head+':'+path],cwd=ROOT)).hexdigest()!=h:
            raise ValueError('Uncommitted training source '+path)
    return dict(authorization=auth,live_assignment=validate_assignment(CONTEXT))


def job_key(config):return 'exp0068-person-detector-train-'+config['execution_revision']+'-'+digest(config['files'])


def output_path(stage,attempt):
    if stage!='train5' or not re.fullmatch('[0-9a-f]{32}',attempt):raise ValueError('Exact train5 attempt required')
    return OUTPUT/stage/attempt


def command(config,inputs,runtime,attempt,lock_fd):
    proof=validate(config,inputs,runtime);os.fstat(lock_fd);resources()
    directory=Path(runtime)/'attempts'/attempt;directory.mkdir(parents=True,exist_ok=True)
    snapshot=directory/'person-detector-train-config.json'
    with snapshot.open('x',encoding='utf-8') as f:json.dump(config,f,sort_keys=True,indent=2);f.write('\n')
    with (directory/'person-detector-train-assignment.json').open('x',encoding='utf-8') as f:json.dump(proof,f,sort_keys=True,indent=2);f.write('\n')
    return [str(interpreter(config)),'-I',str(ROOT/'scripts/train_person_detector.py'),
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
    if (snapshot!=RUNTIME/'attempts'/args.queue_attempt/'person-detector-train-config.json'
            or file_hash(snapshot)!=args.queue_config_sha256):raise ValueError('Canonical attempt snapshot differs')
    config=read(snapshot)
    if args.output.resolve()!=output_path(config['stage'],args.queue_attempt):raise ValueError('Canonical output differs')
    with sqlite3.connect('file:'+str(RUNTIME/'queue.sqlite3')+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        row=db.execute('SELECT j.*,a.status AS attempt_status,a.supervisor_pid,a.supervisor_identity '
                       'FROM jobs j JOIN attempts a USING(job_id) WHERE a.attempt_id=?',(args.queue_attempt,)).fetchone()
    if row is None:raise ValueError('Actual running training attempt required')
    inputs=json.loads(row['input_json']);proof=validate(config,inputs,RUNTIME)
    if (row['command']!='person-detector-train' or row['status']!='running' or row['attempt_status']!='running'
            or json.loads(row['config_json'])!=config or row['config_hash']!=digest(config)
            or row['input_hash']!=digest(inputs) or row['source_hash']!=digest(sources(config))
            or row['job_key']!=job_key(config) or row['code_sha']!=proof['authorization']['code_sha']
            or any(row[k]!=v for k,v in CONTEXT.items())
            or process_state(row['supervisor_pid'],row['supervisor_identity'])!='live'
            or os.environ.get('CUDA_VISIBLE_DEVICES')!='0'):raise ValueError('Exact live canonical training context required')
    resources()
    return config,inputs


def retry_guard(db,job):raise ValueError('Person pilot retry is forbidden; preserve the attempted failure')
