# SPDX-License-Identifier: AGPL-3.0-only
"""EXP-0026 exact source/input/authorization contract, canonical queue only."""
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import subprocess
from orchestration.batch04_pose_command import ROOT, RUNTIME, INTERPRETER, PREDICT_KWARGS as _PREDICT
from orchestration.queue import digest
from orchestration.vlm_command import file_hash

LOCAL = ROOT / 'runtime/BATCH-0007/training'
MANIFEST = ROOT / 'configs/batch0007_detect_manifest.json'
EVAL = LOCAL / 'evaluation-manifest.local.json'
DATA = ROOT / 'data/climbing_fence/person_bbox_draft_v1'
WEIGHT = ROOT / 'weights/yolo26m.pt'
WEIGHT_SHA = '401cea9ab23ad19246ff7744859816bc599f350e93c9dd30367b6f0a0745d0b7'
WEIGHT_URL = 'https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26m.pt'
IDENTITY = ('run_3d23462a014a', 'task_96b539b1624d', 'ctx_76b9a0360296')
STAGES = ('train_compare',)
AUGMENT_ZERO = ('hsv_h','hsv_s','hsv_v','degrees','translate','scale','shear','perspective',
    'flipud','fliplr','mosaic','mixup','cutmix','copy_paste','bgr')
TRAIN_KWARGS = dict(epochs=20,imgsz=640,batch=2,device=0,workers=0,seed=0,deterministic=True,
    amp=False,freeze=10,optimizer='AdamW',lr0=.0001,lrf=.1,weight_decay=.0005,warmup_epochs=1,
    warmup_bias_lr=0.0,nbs=64,patience=0,resume=False,pretrained=True,cls_remap=True,save=True,save_period=-1,cache=False,
    rect=False,cos_lr=False,close_mosaic=0,single_cls=False,fraction=1.0,profile=False,
    multi_scale=0.0,compile=False,channels_last=False,val=True,split='val',plots=False,
    save_json=False,nms=False,quantize=None,augment=False,augmentations=[],erasing=0.,auto_augment=None,
    time=None,exist_ok=False,verbose=True,**{k:0.0 for k in AUGMENT_ZERO})
PREDICT_KWARGS = deepcopy(_PREDICT)
SETTINGS = dict(api=['YOLO.predict','YOLO.train','YOLO.predict'],ultralytics='8.4.192',
    train_kwargs=TRAIN_KWARGS,predict_kwargs=PREDICT_KWARGS,minimum_gpu_free_mib=6144,
    maximum_queue_seconds=3600,execution_error_retries_max=1,automatic_retry=False,
    checkpoint_selection='official best.pt by fixed valid20 fitness (mAP50-95); never diagnostic frames',
    baseline_head_classes=80,trained_head_classes=1,general_person_data_mixed=False,
    D0_passed=False,label_review='pending',authorization='one exploratory run despite deferred visual review')


def checked(path, expected):
    p=Path(path)
    if not p.is_absolute():p=ROOT/p
    if not p.resolve().is_relative_to(ROOT.resolve()) or p.is_symlink() or file_hash(p)!=expected:
        raise ValueError('source/input/environment hash differs: '+str(path))
    return p


def dataset_files():
    """Pin ALL historical data bytes, including unused test and review metadata."""
    return {str(p.relative_to(ROOT)):file_hash(p) for p in sorted(DATA.rglob('*')) if p.is_file()}


def validate_eval(d):
    import numpy as np
    frames=d['frames']
    expected={'030_084':84,'030_090':90,'030_094':94,'030_050':50,'030_055':55,
        '007_047p5':47.5,'007_052p5':52.5}
    if len(frames)!=7 or {f['frame_id'] for f in frames}!=set(expected):
        raise ValueError('exact seven preregistered diagnostic/control frames required')
    for f in frames:
        if Fraction(f['native_pts'])*Fraction(f['time_base'])!=Fraction(str(expected[f['frame_id']])):
            raise ValueError('exact native PTS required')
        for p,h in [('source_path','source_sha256'),('rgb_path','rgb_sha256'),('crop_path','crop_sha256')]:
            checked(f[p],f[h])
        rgb=np.load(ROOT/f['rgb_path'],allow_pickle=False);c=np.load(ROOT/f['crop_path'],allow_pickle=False)
        if rgb.dtype!=np.uint8 or c.dtype!=np.uint8 or list(rgb.shape)!=f['rgb_shape'] or list(c.shape)!=f['crop_shape']:
            raise ValueError('RGB dtype/shape differs')
        x1,y1,x2,y2=f['crop_xyxy']
        if f['frame_id'].startswith('030_') and (f['camera_id']!='C6' or [x1,y1,x2,y2]!=[537,216,1440,864]):
            raise ValueError('static C6 crop differs')
        cameras=json.loads((ROOT/'configs/mvp0001_cameras.json').read_text())['cameras']
        from batch05_pose.geometry import bounds
        if f['roi']!=cameras[f['camera_id']]['roi'] or list(bounds(rgb.shape,f['roi']))!=[x1,y1,x2,y2]:
            raise ValueError('fixed camera ROI differs')
        for a,h in [(rgb,'rgb_bytes_sha256'),(c,'crop_bytes_sha256')]:
            if hashlib.sha256(a.tobytes()).hexdigest()!=f[h]:raise ValueError('RGB byte hash differs')
        if not np.array_equal(c,rgb[y1:y2,x1:x2]):raise ValueError('native crop differs')
    return d


def input_contract(stage='train_compare'):
    job_key(stage)
    public=json.loads(MANIFEST.read_text())
    if public['settings']!=SETTINGS or public['checkpoint_sha256']!=WEIGHT_SHA:raise ValueError('fixed manifest differs')
    checked(WEIGHT,WEIGHT_SHA)
    if WEIGHT.stat().st_size!=44255705:raise ValueError('Detection checkpoint size differs')
    d=validate_eval(json.loads(EVAL.read_text()))
    old=json.loads((ROOT/'runtime/BATCH-0006/input-manifest.local.json').read_text())
    env=old['environment']
    for n,h in env['files'].items():checked(n,h)
    for n,h in json.loads((ROOT/env['file_index']).read_text()).items():
        if not n.startswith('.venv-pose-batch03/'):raise ValueError('fixed environment prefix required')
        checked(n,h)
    snapshot=json.loads((LOCAL/'dataset-freeze.local.json').read_text())
    if dataset_files()!=snapshot:raise ValueError('historical prepared dataset bytes differ')
    summary=json.loads((DATA/'summary.json').read_text())
    if summary.get('usable_for_training') is not False or summary.get('D0_passed') is not False or summary.get('status')!='review_pending':
        raise ValueError('historical review metadata must stay pending')
    from batch07_detect.prepare import verify_tree
    verify_tree()
    return dict(manifest_sha256=file_hash(MANIFEST),evaluation_manifest_sha256=file_hash(EVAL),
        checkpoint_sha256=WEIGHT_SHA,dataset_snapshot_sha256=file_hash(LOCAL/'dataset-freeze.local.json'),
        isolated_data_manifest_sha256=file_hash(LOCAL/'train-data-manifest.local.json'),
        environment_index_sha256=file_hash(ROOT/env['file_index']),environment_files=env['files'],
        camera_config_sha256=file_hash(ROOT/'configs/mvp0001_cameras.json'))


def sources(config=None):
    names=['orchestration/queue.py','orchestration/mock_job.py','orchestration/vlm_command.py',
        'orchestration/batch07_detect_command.py','orchestration/batch04_pose_command.py',
        'orchestration/batch03_pose_command.py','batch04_pose/api.py','batch04_pose/runner.py',
        'batch05_pose/geometry.py','configs/batch0007_detect_manifest.json','configs/mvp0001_cameras.json',
        'requirements-pose-batch03-lock.txt','tests_orca/test_batch07_detect.py']
    names += [str(p.relative_to(ROOT)) for folder in ('batch03_pose','batch04_pose','batch05_pose','batch07_detect') for p in sorted((ROOT/folder).glob('*.py'))]
    names=sorted(set(names))
    return {n:file_hash(ROOT/n) for n in names}


def validate_assignment(run,task,dispatch):
    a=json.loads((LOCAL/'execution-authorization.json').read_text())
    if (run,task,dispatch)!=IDENTITY or tuple(a[k] for k in ('run_id','task_id','dispatch_id'))!=IDENTITY or a.get('confirmed') is not True:
        raise ValueError('current coordinator-confirmed native identity required')
    if a.get('training_authorized') is not True or a.get('D0_passed') is not False:
        raise ValueError('explicit exploratory training override without D0 pass required')
    if a['sources']!=sources() or a.get('allowed_stages')!=list(STAGES) or a.get('input_contract_sha256')!=digest(input_contract()):
        raise ValueError('reviewed exact source/input/stage authorization required')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if a['code_sha']!=head:raise ValueError('current Git freeze differs')
    return a


def job_key(stage='train_compare'):
    if stage not in STAGES:raise ValueError('fixed stage required')
    return 'batch0007-exp0026-detect-train-compare'


def output_path(stage,attempt):
    job_key(stage)
    if not re.fullmatch('[0-9a-f]{32}',attempt):raise ValueError('invalid attempt')
    return ROOT/'outputs/batch0007/EXP-0026'/stage/attempt


def validate(config,inputs,runtime):
    if config!=dict(stage='train_compare',settings=SETTINGS) or Path(runtime).resolve()!=RUNTIME or not INTERPRETER.is_file():
        raise ValueError('fixed settings/canonical queue/interpreter required')
    if inputs!=input_contract():raise ValueError('fixed input contract differs')
    validate_assignment(*IDENTITY)
    return 'train_compare'


def execution_guard(db,job,attempt):
    rows=db.execute("SELECT j.job_key,j.run_id,j.task_id,j.dispatch_id,a.attempt_id,a.attempt_no FROM jobs j LEFT JOIN attempts a USING(job_id) WHERE j.command='batch07-detect'").fetchall()
    if len(rows)!=1 or tuple(rows[0])!=(job_key(),*IDENTITY,attempt,1) or job['job_key']!=job_key():
        raise ValueError('one exact initial attempt required; retry needs separately reviewed correction')


def retry_guard(db,job):
    raise ValueError('no automatic retry; at most one separately reviewed CPU correction/freeze')


def command(config,inputs,runtime,attempt,lock_fd):
    stage=validate(config,inputs,runtime);output_path(stage,attempt)
    return [str(INTERPRETER),'-I',str(ROOT/'batch07_detect/runner.py'),'--stage',stage,'--attempt',attempt,'--lock-fd',str(lock_fd)]
