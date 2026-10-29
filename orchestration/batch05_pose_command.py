# SPDX-License-Identifier: AGPL-3.0-only
"""Five new fixed full/C6 conditions, one cached result; canonical queue only."""
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
from orchestration.batch04_pose_command import ROOT,RUNTIME,INTERPRETER,WEIGHT,WEIGHT_SHA,PREDICT_KWARGS
from orchestration.vlm_command import file_hash
from batch05_pose.geometry import ROI,PIXELS,crop

LOCAL=ROOT/'runtime/BATCH-0005'
MANIFEST=ROOT/'configs/batch0005_pose_manifest.json'
IDENTITY=('run_3d23462a014a','task_000a7c6dec59','ctx_f85d0a3a38de')
STAGES=('comparison',)
CONDITIONS=('030_090_C6','030_084_full','030_084_C6','030_094_full','030_094_C6')
SETTINGS=dict(api='YOLO.predict',ultralytics='8.4.192',predict_kwargs=PREDICT_KWARGS,
    dtype='float32',joint_confidence=.5,minimum_gpu_free_mib=6144,
    roi=ROI,crop_xyxy=list(PIXELS),execution_error_retries_max=1)
OLD_MANIFEST_SHA='dcd6501ef11cd8b7a06aeb2d0bf6c303acb6665ac65dc3a4f6e5d45bba8c4c98'
OLD_SUMMARY='outputs/batch0004/EXP-0022/smoke/6509c805b40e4d7a8137f770cfa04a05/summary.json'
OLD_SUMMARY_SHA='84905e3841a7394f0e3a0e214f7298746f33226fdaa3fafb703c3ded40cf5cde'


def manifest():
    d=json.loads(MANIFEST.read_text())
    old_path=ROOT/'configs/batch0004_pose_manifest.json'
    if file_hash(old_path)!=OLD_MANIFEST_SHA or d['settings']!=SETTINGS:
        raise ValueError('fixed manifest/settings differ')
    old=json.loads(old_path.read_text())
    expected=[next(r for r in old['frames'] if r['frame_id']==f'030_{t:03}') for t in (84,90,94)]
    if d['frames']!=expected or d['conditions']!=list(CONDITIONS):
        raise ValueError('exact three historical frames/five conditions required')
    for r,t in zip(d['frames'],(84,90,94)):
        if Fraction(r['native_pts'])*Fraction(r['time_base'])!=t or r['rgb_shape']!=[1080,1920,3]:
            raise ValueError('exact native PTS/shape differs')
    if d['cached']['summary_path']!=OLD_SUMMARY or d['cached']['summary_sha256']!=OLD_SUMMARY_SHA:
        raise ValueError('exact cached summary provenance required')
    if d['historical_manifest_sha256']!=OLD_MANIFEST_SHA or d['model']!=old['model'] or d['environment']!=old['environment']:
        raise ValueError('historical environment/model provenance differs')
    camera=json.loads((ROOT/'configs/mvp0001_cameras.json').read_text())['cameras']['C6']
    if camera!=d['camera'] or camera['roi']!=ROI:
        raise ValueError('historical C6 config differs')
    return d


def cached_record(d=None):
    d=manifest() if d is None else d
    c=d['cached']
    if file_hash(ROOT/c['summary_path'])!=c['summary_sha256']:
        raise ValueError('cached native summary hash differs')
    s=json.loads((ROOT/c['summary_path']).read_text())
    r=next(r for r in s['results'] if r['frame_id']=='030_090')
    if not s['technical_pass'] or r['person_count']!=0 or r['persons']!=[] or r['artifacts']!=c['artifacts']:
        raise ValueError('exact historical zero-person result required')
    for a in c['artifacts'].values():
        if file_hash(ROOT/a['path'])!=a['sha256']:
            raise ValueError('cached artifact hash differs')
    f=next(f for f in d['frames'] if f['frame_id']=='030_090')
    for key in ('source_id','native_pts','time_base','pts_seconds','rgb_sha256','rgb_bytes_sha256'):
        if r[key]!=f[key]:raise ValueError('cached input provenance differs')
    return r


def input_contract(stage='comparison'):
    if stage not in STAGES:raise ValueError('fixed stage required')
    import numpy as np
    d=manifest();cached_record(d)
    pins={**d['environment']['files'], 'weights/yolo26m-pose.pt':WEIGHT_SHA,
        'configs/mvp0001_cameras.json':d['camera_config_sha256'],
        'configs/batch0004_pose_manifest.json':OLD_MANIFEST_SHA}
    for r in d['frames']:
        pins[r['source_path']]=r['source_sha256'];pins[r['rgb_path']]=r['rgb_sha256']
    for name,expected in pins.items():
        p=ROOT/name
        if not p.resolve().is_relative_to(ROOT.resolve()) or file_hash(p)!=expected:
            raise ValueError('source/input/config/environment/checkpoint hash differs: '+name)
    for name,expected in json.loads((ROOT/d['environment']['file_index']).read_text()).items():
        if not name.startswith('.venv-pose-batch03/') or file_hash(ROOT/name)!=expected:
            raise ValueError('installed environment differs: '+name)
    if WEIGHT.stat().st_size!=49036866:raise ValueError('fixed checkpoint size differs')
    for r in d['frames']:
        rgb=np.load(ROOT/r['rgb_path'],allow_pickle=False)
        if list(rgb.shape)!=r['rgb_shape'] or hashlib.sha256(rgb.tobytes()).hexdigest()!=r['rgb_bytes_sha256']:
            raise ValueError('native source RGB hash differs')
        if hashlib.sha256(crop(rgb).tobytes()).hexdigest()!=d['crop_bytes_sha256'][r['frame_id']]:
            raise ValueError('fixed crop RGB hash differs')
    return dict(manifest_sha256=file_hash(MANIFEST),files=pins,conditions=list(CONDITIONS),
        crop_bytes_sha256=d['crop_bytes_sha256'],cached=d['cached'])


def sources(config=None):
    names=['orchestration/queue.py','orchestration/mock_job.py','orchestration/vlm_command.py',
        'orchestration/batch05_pose_command.py','orchestration/batch04_pose_command.py',
        'orchestration/batch03_pose_command.py','batch03_pose/prepare.py',
        'configs/batch0003_pose_manifest.json','configs/batch0004_pose_manifest.json',
        'configs/batch0005_pose_manifest.json','configs/mvp0001_cameras.json',
        'requirements-pose-batch03-lock.txt','tests_orca/test_batch05_pose.py']
    names += [str(p.relative_to(ROOT)) for folder in ('batch04_pose','batch05_pose') for p in sorted((ROOT/folder).glob('*.py'))]
    return {n:file_hash(ROOT/n) for n in names}


def validate_assignment(run,task,dispatch):
    a=json.loads((LOCAL/'execution-authorization.json').read_text())
    if (run,task,dispatch)!=IDENTITY or tuple(a[k] for k in ('run_id','task_id','dispatch_id'))!=IDENTITY or a.get('confirmed') is not True:
        raise ValueError('current coordinator-confirmed native identity required')
    if a['sources']!=sources() or a.get('allowed_stages')!=['comparison']:
        raise ValueError('reviewed exact source/stage authorization required')
    return a


def job_key(stage):
    if stage not in STAGES:raise ValueError('fixed stage required')
    return 'batch0005-exp0023-c6-comparison'


def output_path(stage,attempt):
    job_key(stage)
    if not re.fullmatch('[0-9a-f]{32}',attempt):raise ValueError('invalid attempt')
    return ROOT/'outputs/batch0005/EXP-0023'/stage/attempt


def validate(config,inputs,runtime):
    if config!=dict(stage='comparison',settings=SETTINGS) or Path(runtime).resolve()!=RUNTIME or not INTERPRETER.is_file():
        raise ValueError('fixed settings/canonical queue/interpreter required')
    if inputs!=input_contract():raise ValueError('fixed input contract differs')
    validate_assignment(*IDENTITY)
    return 'comparison'


def execution_guard(db,job,attempt):
    rows=db.execute("SELECT j.job_key,j.run_id,j.task_id,j.dispatch_id,a.attempt_id,a.attempt_no FROM jobs j LEFT JOIN attempts a USING(job_id) WHERE j.command='batch05-pose'").fetchall()
    if len(rows)!=1 or tuple(rows[0])!=(job_key('comparison'),*IDENTITY,attempt,1) or job['job_key']!=job_key('comparison'):
        raise ValueError('one exact initial comparison attempt required; no automatic retry')


def ensure_unprocessed(condition):
    if condition not in CONDITIONS:raise ValueError('unapproved condition')
    base=ROOT/'outputs/batch0005/EXP-0023'
    if list(base.glob('*/*/'+condition+'-predict-started.json')) or list(base.glob('*/*/'+condition+'-results.pt')):
        raise ValueError('condition already attempted; preserve partial successes')


def retry_guard(db,job):
    raise ValueError('no automatic retry; at most one separately reviewed CPU correction/freeze')


def command(config,inputs,runtime,attempt,lock_fd):
    stage=validate(config,inputs,runtime);output_path(stage,attempt)
    return [str(INTERPRETER),'-I',str(ROOT/'batch05_pose/runner.py'),'--stage',stage,'--attempt',attempt,'--lock-fd',str(lock_fd)]
