# SPDX-License-Identifier: AGPL-3.0-only
"""Three new 960 calls, three immutable 640 cached Results, canonical queue only."""
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
from orchestration.batch04_pose_command import ROOT,RUNTIME,INTERPRETER,WEIGHT,WEIGHT_SHA,PREDICT_KWARGS as BASE_KWARGS
from orchestration.vlm_command import file_hash
from orchestration.queue import digest
from batch05_pose.geometry import ROI,PIXELS,crop

LOCAL=ROOT/'runtime/BATCH-0006'
MANIFEST=ROOT/'configs/batch0006_pose_manifest.json'
IDENTITY=('run_3d23462a014a','task_259c3da684ec','ctx_4941141147c8')
STAGES=('comparison',)
CONDITIONS=('030_090_C6_960','030_084_C6_960','030_094_C6_960')
PREDICT_KWARGS=deepcopy(BASE_KWARGS)
PREDICT_KWARGS['imgsz']=960
SETTINGS=dict(api='YOLO.predict',ultralytics='8.4.192',predict_kwargs=PREDICT_KWARGS,
    dtype='float32',joint_confidence=.5,minimum_gpu_free_mib=6144,
    roi=ROI,crop_xyxy=list(PIXELS),execution_error_retries_max=1)
OLD_SUMMARY='outputs/batch0005/EXP-0023/comparison/90784d50902748b9956101771e27662b/summary.json'
OLD_SUMMARY_SHA='1c08d87413a2bc399c2a426f63b865e7f3e2f817c8fc35801781ef206d67c46a'


def manifest():
    public=json.loads(MANIFEST.read_text())
    raw=LOCAL/'input-manifest.local.json'
    if file_hash(raw)!=public['input_manifest_sha256']:
        raise ValueError('local input manifest binding differs')
    d=json.loads(raw.read_text())
    old_path=ROOT/'configs/batch0005_pose_manifest.json'
    if file_hash(old_path)!=d['historical_manifest_sha256'] or public['baseline_manifest_sha256']!=file_hash(old_path):
        raise ValueError('historical manifest differs')
    old=json.loads(old_path.read_text())
    for k in ('frames','model','environment','camera','camera_config_sha256','crop_bytes_sha256'):
        if d[k]!=old[k]:raise ValueError('historical input/model/environment differs: '+k)
    if public['conditions']!=list(CONDITIONS) or public['cached_summary_sha256']!=OLD_SUMMARY_SHA or public['checkpoint_sha256']!=WEIGHT_SHA:
        raise ValueError('fixed conditions/cache/checkpoint differ')
    if len(PREDICT_KWARGS)!=22 or set(PREDICT_KWARGS)!=set(BASE_KWARGS) or [k for k in BASE_KWARGS if BASE_KWARGS[k]!=PREDICT_KWARGS[k]]!=['imgsz'] or PREDICT_KWARGS['imgsz']!=960:
        raise ValueError('only imgsz may change')
    for r,t in zip(d['frames'],(84,90,94)):
        if Fraction(r['native_pts'])*Fraction(r['time_base'])!=t or r['rgb_shape']!=[1080,1920,3]:
            raise ValueError('exact native PTS/shape differs')
    camera=json.loads((ROOT/'configs/mvp0001_cameras.json').read_text())['cameras']['C6']
    if camera!=d['camera'] or camera['roi']!=ROI:raise ValueError('fixed C6 differs')
    return d


def cached_records(d=None):
    d=manifest() if d is None else d
    if d['cached_summary_path']!=OLD_SUMMARY or d['cached_summary_sha256']!=OLD_SUMMARY_SHA or file_hash(ROOT/OLD_SUMMARY)!=OLD_SUMMARY_SHA:
        raise ValueError('cached native summary hash differs')
    s=json.loads((ROOT/OLD_SUMMARY).read_text())
    if not s['technical_pass'] or s['status']!='succeeded':raise ValueError('successful cached run required')
    lookup={r['frame_id']:r for r in s['results'] if r['view']=='C6'}
    if set(lookup)!={r['frame_id'] for r in d['frames']}:raise ValueError('three cached C6 Results required')
    for f in d['frames']:
        r=lookup[f['frame_id']];pin=d['cached'][f['frame_id']]
        if r['condition_id']!=pin['condition_id'] or r['artifacts']!=pin['artifacts'] or r['offset_applications']!=1:
            raise ValueError('cached C6 artifact/offset differs')
        for k in ('source_id','native_pts','time_base','pts_seconds','rgb_sha256','rgb_bytes_sha256'):
            if r[k]!=f[k]:raise ValueError('cached source provenance differs')
        for a in pin['artifacts'].values():
            if file_hash(ROOT/a['path'])!=a['sha256']:raise ValueError('cached artifact hash differs')
    return lookup


def input_contract(stage='comparison'):
    if stage not in STAGES:raise ValueError('fixed stage required')
    import numpy as np
    d=manifest();cached_records(d)
    pins={**d['environment']['files'],**d['historical_source_sha256'],
        'weights/yolo26m-pose.pt':WEIGHT_SHA,'configs/mvp0001_cameras.json':d['camera_config_sha256'],
        'configs/batch0005_pose_manifest.json':d['historical_manifest_sha256']}
    for r in d['frames']:pins[r['source_path']]=r['source_sha256'];pins[r['rgb_path']]=r['rgb_sha256']
    for name,expected in pins.items():
        p=ROOT/name
        if not p.resolve().is_relative_to(ROOT.resolve()) or file_hash(p)!=expected:raise ValueError('source/input/environment hash differs: '+name)
    for name,expected in json.loads((ROOT/d['environment']['file_index']).read_text()).items():
        if not name.startswith('.venv-pose-batch03/') or file_hash(ROOT/name)!=expected:raise ValueError('installed environment differs: '+name)
    if WEIGHT.stat().st_size!=49036866:raise ValueError('checkpoint size differs')
    for r in d['frames']:
        rgb=np.load(ROOT/r['rgb_path'],allow_pickle=False)
        if list(rgb.shape)!=r['rgb_shape'] or hashlib.sha256(rgb.tobytes()).hexdigest()!=r['rgb_bytes_sha256']:raise ValueError('native RGB hash differs')
        if hashlib.sha256(crop(rgb).tobytes()).hexdigest()!=d['crop_bytes_sha256'][r['frame_id']]:raise ValueError('fixed crop RGB hash differs')
    return dict(manifest_sha256=file_hash(MANIFEST),input_manifest_sha256=file_hash(LOCAL/'input-manifest.local.json'),
        files=pins,conditions=list(CONDITIONS),crop_bytes_sha256=d['crop_bytes_sha256'],cached=d['cached'],cached_summary_sha256=OLD_SUMMARY_SHA)


def sources(config=None):
    names=['orchestration/queue.py','orchestration/mock_job.py','orchestration/vlm_command.py',
        'orchestration/batch06_pose_command.py','orchestration/batch05_pose_command.py','orchestration/batch04_pose_command.py',
        'orchestration/batch03_pose_command.py','batch03_pose/prepare.py','configs/batch0003_pose_manifest.json',
        'configs/batch0004_pose_manifest.json','configs/batch0005_pose_manifest.json','configs/batch0006_pose_manifest.json',
        'configs/mvp0001_cameras.json','requirements-pose-batch03-lock.txt','tests_orca/test_batch06_pose.py']
    names += [str(p.relative_to(ROOT)) for folder in ('batch04_pose','batch05_pose','batch06_pose') for p in sorted((ROOT/folder).glob('*.py'))]
    return {n:file_hash(ROOT/n) for n in names}


def validate_assignment(run,task,dispatch):
    a=json.loads((LOCAL/'execution-authorization.json').read_text())
    if (run,task,dispatch)!=IDENTITY or tuple(a[k] for k in ('run_id','task_id','dispatch_id'))!=IDENTITY or a.get('confirmed') is not True:
        raise ValueError('current coordinator-confirmed native identity required')
    if a['sources']!=sources() or a.get('allowed_stages')!=['comparison'] or a.get('input_contract_sha256')!=digest(input_contract()):
        raise ValueError('reviewed exact source/input/stage authorization required')
    return a


def job_key(stage):
    if stage not in STAGES:raise ValueError('fixed stage required')
    return 'batch0006-exp0025-c6-960-comparison'


def output_path(stage,attempt):
    job_key(stage)
    if not re.fullmatch('[0-9a-f]{32}',attempt):raise ValueError('invalid attempt')
    return ROOT/'outputs/batch0006/EXP-0025'/stage/attempt


def validate(config,inputs,runtime):
    if config!=dict(stage='comparison',settings=SETTINGS) or Path(runtime).resolve()!=RUNTIME or not INTERPRETER.is_file():raise ValueError('fixed settings/canonical queue/interpreter required')
    if inputs!=input_contract():raise ValueError('fixed input contract differs')
    validate_assignment(*IDENTITY)
    return 'comparison'


def execution_guard(db,job,attempt):
    rows=db.execute("SELECT j.job_key,j.run_id,j.task_id,j.dispatch_id,a.attempt_id,a.attempt_no FROM jobs j LEFT JOIN attempts a USING(job_id) WHERE j.command='batch06-pose'").fetchall()
    if len(rows)!=1 or tuple(rows[0])!=(job_key('comparison'),*IDENTITY,attempt,1) or job['job_key']!=job_key('comparison'):
        raise ValueError('one exact initial attempt required; no automatic retry')


def ensure_unprocessed(condition):
    if condition not in CONDITIONS:raise ValueError('unapproved condition')
    base=ROOT/'outputs/batch0006/EXP-0025'
    if list(base.glob('*/*/'+condition+'-predict-started.json')) or list(base.glob('*/*/'+condition+'-results.pt')):raise ValueError('condition already attempted; preserve partial successes')


def retry_guard(db,job):
    raise ValueError('no automatic retry; at most one separately reviewed CPU correction/freeze')


def command(config,inputs,runtime,attempt,lock_fd):
    stage=validate(config,inputs,runtime);output_path(stage,attempt)
    return [str(INTERPRETER),'-I',str(ROOT/'batch06_pose/runner.py'),'--stage',stage,'--attempt',attempt,'--lock-fd',str(lock_fd)]
