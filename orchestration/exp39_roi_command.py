"""One fixed EXP-0039 ROI comparison job in the existing canonical queue."""
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import subprocess
from orchestration.queue import digest
from orchestration.vlm_command import file_hash

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=Path('/home/jhc7484/dev/sceneguard-orca-lab/runtime/orca-lab/gpu-queue')
LOCAL=ROOT/'runtime/EXP-0039'
INTERPRETER=ROOT/'.venv/bin/python'
VIDEO=ROOT/'data/TS_침입/E01_030.mp4'
CACHE=ROOT/'outputs/cv_phase2d/cache030'
WEIGHT=ROOT/'weights/fcos_resnet50_fpn_coco-99b0c9b7.pth'
WEIGHT_SHA='99b0c9b7cfb1527d782db86b91d207f00547c792fb4103fc612b651d0a07b9e7'
IDENTITY=('run_3d23462a014a','task_a9481fc1a850','ctx_e81e74bdb8d9')
OWNER='term_3c9ab7f0-76bf-42cc-9652-be98f515a993'
WINDOWS=(('s0003',240,282),('s0008',415,457))
SETTINGS=dict(detector='fcos800',precision='float32',batch_size=1,seed=0,threads=2,
    device='cuda',roi=[.28,.2,.75,.8],min_size=800,max_size=1333,
    model_postprocess=dict(score_thresh=.2,topk_candidates=1000,nms_thresh=.6,detections_per_img=100),
    diagnostic_views=[.5,.25],warmup_frames=10,warmup_source='first10approvedROIframes',
    maximum_sample_calls=86,maximum_model_loads=1,minimum_gpu_free_mib=6144,
    automatic_retry=False,execution_error_retries_max=1,tracker_calls=0,alarm_changes=0)


def schedule(cached):
    result=[]
    if len(cached)!=480:raise ValueError('Original 480-frame cache required')
    for sid,first,last in WINDOWS:
        rows=[]
        for index in range(first,last+1):
            row=cached[index]
            native=1290240+index*512
            if (row['native_pts']!=native or row['time_base']!='1/15360'
                or row['pts']!=float(Fraction(native,15360)) or row['source_size']!=[1920,1080]):
                raise ValueError('Exact original native schedule required')
            rows.append({k:row[k] for k in ('pts','native_pts','time_base','source_size')}|dict(frame_index=index))
        result.append(dict(segment=sid,rows=rows))
    return result


def input_contract():
    from orchestration.exp29_cache_command import environment
    freeze=LOCAL/'roi-input-freeze.json'
    frozen=json.loads(freeze.read_text())
    if frozen['settings']!=SETTINGS:raise ValueError('Frozen ROI settings differ')
    for name,expected in frozen['files'].items():
        path=ROOT/name
        if path.is_symlink() or file_hash(path)!=expected:raise ValueError('Frozen input differs: '+name)
    if file_hash(WEIGHT)!=WEIGHT_SHA:raise ValueError('Original FCOS weights required')
    if environment()!=json.loads((LOCAL/'roi-environment.json').read_text()):
        raise ValueError('Original .venv installed bytes differ')
    cached=[json.loads(line) for line in (CACHE/'person_cache.jsonl').read_text().splitlines()]
    meta=json.loads((CACHE/'run.json').read_text())
    if (meta['model_sha256']!=WEIGHT_SHA or meta['model_postprocess']!=SETTINGS['model_postprocess']
        or meta['model_input']!={'min_size':800,'max_size':1333} or meta['config']['roi']!=SETTINGS['roi']
        or frozen['schedule']!=schedule(cached)):
        raise ValueError('Baseline model/ROI/native schedule differs')
    gate=json.loads((LOCAL/'user-visibility-gate.json').read_text())
    if (gate['selected_roi_runs']!=2 or len(gate['observations'])!=2
        or {r['segment'] for r in gate['observations']}!={'s0003','s0008'}
        or any(r.get('visible_during_part_of_interval') is not True for r in gate['observations'])):
        raise ValueError('Current bounded human visibility gate required')
    for window in frozen['schedule']:
        support=json.loads((ROOT/'outputs/exp0039/030-v1'/(window['segment']+'-support.json')).read_text())
        audit=support['detector_audit'];waiting=len(audit['timeline'])
        observation=next(r for r in gate['observations'] if r['segment']==window['segment'])
        if (audit['counts'].get('no_local_box_in_saved_cache',0)*2<waiting
            or audit['decision_time_pts']!=window['rows'][-1]['pts']
            or observation['source_window']!=[window['rows'][0]['pts'],window['rows'][-1]['pts']]):
            raise ValueError('Numerical missing-cache and human window gate differs')
    return dict(freeze_sha256=file_hash(freeze),environment_sha256=file_hash(LOCAL/'roi-environment.json'),
                schedule=frozen['schedule'],files=frozen['files'])


def sources(config=None):
    names=['orchestration/queue.py','orchestration/mock_job.py','orchestration/vlm_command.py',
        'orchestration/exp39_roi_command.py','orchestration/exp29_cache_command.py',
        'sceneguard/exp0039_roi_gpu.py','sceneguard/detectors.py','sceneguard/run_tracklet_linking.py',
        'sceneguard/tracklet_linking.py','orchestration/batch03_pose_command.py',
        'batch04_pose/runner.py','orchestration/batch04_pose_command.py','batch04_pose/api.py',
        'tests/test_exp0039_roi.py','tests_orca/test_exp39_roi.py']
    return {n:file_hash(ROOT/n) for n in names}


def validate_assignment(run,task,dispatch):
    a=json.loads((LOCAL/'roi-execution-authorization.json').read_text())
    if (run,task,dispatch)!=IDENTITY or tuple(a.get(k) for k in ('run_id','task_id','dispatch_id'))!=IDENTITY or a.get('owner')!=OWNER:
        raise ValueError('Current EXP39 Run/Task/Dispatch/owner required')
    if any(a.get(k) is not True for k in ('confirmed','inference_authorized','independent_review_passed','explicit_gpu_go')):
        raise ValueError('Explicit coordinator GPU GO and independent review required')
    if (a.get('sources')!=sources() or a.get('input_contract_sha256')!=digest(input_contract())
        or a.get('maximum_sample_calls')!=86 or a.get('maximum_warmup_calls')!=10 or a.get('maximum_model_loads')!=1):
        raise ValueError('Exact reviewed source/input/call bounds required')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if a.get('code_sha')!=head:raise ValueError('Reviewed committed HEAD differs')
    for name,expected in a['sources'].items():
        committed=subprocess.check_output(['git','show',head+':'+name],cwd=ROOT)
        if hashlib.sha256(committed).hexdigest()!=expected:raise ValueError('Reviewed source must be committed: '+name)
    return a


def job_key(stage='roi030'):
    if stage!='roi030':raise ValueError('Only two frozen 030 ROI windows allowed')
    return 'exp0039-fcos-roi030-two-windows'


def output_path(stage,attempt):
    job_key(stage)
    if not re.fullmatch('[0-9a-f]{32}',attempt):raise ValueError('Invalid attempt')
    return ROOT/'outputs/exp0039/roi030'/attempt


def validate(config,inputs,runtime):
    if config!=dict(stage='roi030',settings=SETTINGS) or Path(runtime).resolve()!=RUNTIME or not INTERPRETER.is_file():
        raise ValueError('Fixed ROI settings/original environment/canonical queue required')
    if inputs!=input_contract():raise ValueError('Frozen ROI input contract differs')
    validate_assignment(*IDENTITY)
    return 'roi030'


def execution_guard(db,job,attempt):
    rows=db.execute("SELECT j.job_key,j.run_id,j.task_id,j.dispatch_id,j.owner,a.attempt_id,a.attempt_no "
        "FROM jobs j LEFT JOIN attempts a USING(job_id) WHERE j.command='exp39-roi'").fetchall()
    if (not 1<=len(rows)<=2 or any(tuple(r[:5])!=(job_key(),*IDENTITY,OWNER) for r in rows)
        or sum(r[5]==attempt and r[6] in (1,2) for r in rows)!=1 or job['job_key']!=job_key()):
        raise ValueError('One fixed ROI job and at most two explicitly approved attempts required')


def retry_guard(db,job):
    a=validate_assignment(job['run_id'],job['task_id'],job['dispatch_id'])
    rows=db.execute('SELECT attempt_id,status FROM attempts WHERE job_id=? ORDER BY attempt_no',(job['job_id'],)).fetchall()
    if len(rows)!=1 or rows[0][1]!='failed' or a.get('execution_error_retry_authorized_for')!=rows[0][0]:
        raise ValueError('Only one separately diagnosed and approved error retry; no automatic retry')


def command(config,inputs,runtime,attempt,lock_fd):
    stage=validate(config,inputs,runtime);output_path(stage,attempt)
    return [str(INTERPRETER),'-I',str(ROOT/'sceneguard/exp0039_roi_gpu.py'),'--stage',stage,
            '--attempt',attempt,'--lock-fd',str(lock_fd)]
