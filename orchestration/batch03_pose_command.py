# SPDX-License-Identifier: AGPL-3.0-only
"""Single fixed offline YOLO26m-Pose contract for the canonical GPU queue."""
import json
from pathlib import Path
import re
from orchestration.vlm_command import RUNTIME, file_hash
ROOT=Path('/home/jhc7484/dev/sceneguard-ai')
INTERPRETER=ROOT/'.venv-pose-batch03/bin/python'
LOCAL=ROOT/'runtime/BATCH-0003'
MANIFEST=ROOT/'configs/batch0003_pose_manifest.json'
WEIGHT=ROOT/'weights/yolo26m-pose.pt'
SETTINGS=dict(model='yolo26m-pose.pt',ultralytics='8.4.192',device='cuda:0',dtype='float32',batch_size=1,
    imgsz=640,rect=False,padding='centered square LetterBox114 scaleupTrue stride32',end2end=True,
    conf=.25,threshold_operator='>',max_det=300,nms=False,iou=.7,agnostic_nms=False,
    augment=False,half=False,compile=False,fuse=False,warmup_frames=0,joint_confidence=.5,
    minimum_gpu_free_mib=6144,execution_error_retries_max=1)
STAGES=('smoke','remaining');SMOKE=('030_090','007_064')
WEIGHT_SHA='2fbf16367022256a226035695c5c389384c6706e8bb8ab8fcd0e7976f05443c4'
COCO17=('nose','left_eye','right_eye','left_ear','right_ear','left_shoulder','right_shoulder','left_elbow',
    'right_elbow','left_wrist','right_wrist','left_hip','right_hip','left_knee','right_knee','left_ankle','right_ankle')


def same(a,b):return json.dumps(a,sort_keys=True,allow_nan=False)==json.dumps(b,sort_keys=True,allow_nan=False)


def manifest():
    from batch03_pose.prepare import WINDOWS,DIAGNOSTICS
    d=json.loads(MANIFEST.read_text())
    if not same(d['settings'],SETTINGS) or not 11<=len(d['frames'])<=300:raise ValueError('fixed pose settings/count differ')
    if set(r['frame_id'] for r in d['frames'] if r['diagnostic'])!=set(DIAGNOSTICS):raise ValueError('eleven diagnostics differ')
    if [(w['alias'],w['source_id'],w['start'],w['end']) for w in d['windows']]!=WINDOWS:raise ValueError('fixed five intervals differ')
    if d['model']['sha256']!=WEIGHT_SHA or d['model']['bytes']!=49036866:raise ValueError('sole checkpoint differs')
    validate_frame_contract(d,json.loads((ROOT/'configs/batch0002_cv_manifest.json').read_text()))
    binding_path=ROOT/'runtime/BATCH-0003/frame-binding.json'
    if file_hash(binding_path)!=d['environment']['files']['runtime/BATCH-0003/frame-binding.json']:raise ValueError('initial frame binding hash differs')
    binding=json.loads(binding_path.read_text())
    if d['frames']!=binding['frames'] or d['windows']!=binding['windows']:raise ValueError('initial frozen frames/windows differ')
    return d


def validate_frame_contract(d,historical):
    from fractions import Fraction
    from batch03_pose.prepare import DIAGNOSTICS
    frames=d['frames'];ids=[r['frame_id'] for r in frames]
    if len(set(ids))!=len(ids):raise ValueError('duplicate frame_id')
    identities=[(r['source_id'],r['native_pts'],r['time_base']) for r in frames]
    if len(set(identities))!=len(identities):raise ValueError('duplicate native input')
    by_id={r['frame_id']:r for r in frames};membership={k:[] for k in by_id}
    for w in d['windows']:
        if len(set(w['frames']))!=len(w['frames']):raise ValueError('duplicate window membership')
        if any(k not in by_id or by_id[k]['source_id']!=w['source_id'] for k in w['frames']):raise ValueError('window/source mismatch')
        times=[Fraction(by_id[k]['native_pts'])*Fraction(by_id[k]['time_base']) for k in w['frames']]
        if not times or any(not Fraction(str(w['start']))<=t<Fraction(str(w['end'])) for t in times) or any(b-a<Fraction(1,10) for a,b in zip(times,times[1:])):raise ValueError('native window sampling exceeds bound')
        for k in w['frames']:membership[k].append(w['alias'])
    previous={r['frame_id']:r for r in historical['frames']}
    if {r['frame_id'] for r in frames if r['diagnostic']}!=set(DIAGNOSTICS):raise ValueError('exact diagnostics missing')
    for r in frames:
        if r['windows']!=membership[r['frame_id']] or (not r['diagnostic'] and not r['windows']):raise ValueError('incomplete/outside window membership')
        if r['diagnostic']:
            old=previous[r['frame_id']]
            for key in ('source_id','native_pts','time_base','source_path','source_sha256','rgb_bytes_sha256','source_size'):
                if r[key]!=old[key]:raise ValueError('EXP19 exact diagnostic parity differs: '+key)
        if r['pts_seconds']!=float(Fraction(r['native_pts'])*Fraction(r['time_base'])):raise ValueError('native seconds differ')


def sources(config=None):
    names=['orchestration/queue.py','orchestration/mock_job.py','orchestration/vlm_command.py','orchestration/batch03_pose_command.py',
           'configs/batch0003_pose_manifest.json','requirements-pose-batch03-lock.txt','tests_orca/test_batch03_pose.py']
    names += [str(p.relative_to(ROOT)) for p in sorted((ROOT/'batch03_pose').glob('*.py'))]
    return {n:file_hash(ROOT/n) for n in names}


def validate_assignment(run,task,dispatch):
    a=json.loads((LOCAL/'execution-authorization.json').read_text())
    if (run,task,dispatch)!=tuple(a[k] for k in ('run_id','task_id','dispatch_id')) or a.get('confirmed') is not True:raise ValueError('coordinator-confirmed pose assignment required')
    if a['sources']!=sources():raise ValueError('pose code/config differs from confirmed freeze')
    return a


def input_contract(stage):
    if stage not in STAGES:raise ValueError('fixed stage required')
    d=manifest();pins={**d['historical_pins'],**d['environment']['files']}
    pins.update({r['source_path']:r['source_sha256'] for r in d['frames']})
    pins.update({r['rgb_path']:r['rgb_sha256'] for r in d['frames']});pins['weights/yolo26m-pose.pt']=WEIGHT_SHA
    for name,expected in pins.items():
        p=ROOT/name
        if not p.resolve().is_relative_to(ROOT.resolve()) or file_hash(p)!=expected:raise ValueError('frozen input/model/environment hash differs: '+name)
    for name,expected in json.loads((ROOT/d['environment']['file_index']).read_text()).items():
        if not name.startswith('.venv-pose-batch03/') or file_hash(ROOT/name)!=expected:raise ValueError('installed pose environment changed: '+name)
    if WEIGHT.stat().st_size!=49036866:raise ValueError('checkpoint size differs')
    frames=list(SMOKE) if stage=='smoke' else [r['frame_id'] for r in d['frames'] if r['frame_id'] not in SMOKE]
    return dict(manifest_sha256=file_hash(MANIFEST),files=pins,frames=frames)


def output_path(stage,attempt):
    if stage not in STAGES or not re.fullmatch('[0-9a-f]{32}',attempt):raise ValueError('invalid pose output identity')
    return ROOT/'outputs/batch0003/EXP-0021'/stage/attempt


def successful_smoke():
    import sqlite3
    from orchestration.queue import digest
    with sqlite3.connect(f'file:{RUNTIME / "queue.sqlite3"}?mode=ro',uri=True) as db:
        rows=db.execute("SELECT a.attempt_id,j.source_hash,j.input_json FROM attempts a JOIN jobs j USING(job_id) WHERE j.command='batch03-pose' AND a.status='succeeded' AND j.status='succeeded' AND json_extract(j.config_json,'$.stage')='smoke'").fetchall()
    matching=[]
    for attempt,source,inputs in rows:
        p=output_path('smoke',attempt)/'summary.json'
        if source!=digest(sources()) or json.loads(inputs)!=input_contract('smoke') or not p.is_file():continue
        s=json.loads(p.read_text())
        if s['status']=='succeeded' and s.get('technical_pass') is True and [r['frame_id'] for r in s['results']]==list(SMOKE):matching.append(attempt)
    if len(matching)!=1:raise ValueError('one exact successful technical smoke required')
    return matching[0]


def validate(config,inputs,runtime):
    if not isinstance(config,dict) or set(config)!={'stage','settings'} or config['stage'] not in STAGES or not same(config['settings'],SETTINGS):raise ValueError('fixed pose stage/settings required')
    if Path(runtime).resolve()!=RUNTIME or not INTERPRETER.is_file():raise ValueError('canonical queue and isolated pose interpreter required')
    if inputs!=input_contract(config['stage']):raise ValueError('pose inputs differ')
    if config['stage']=='remaining':successful_smoke()
    return config['stage']


def retry_guard(db,job):
    # A crash after a forward-start marker cannot regenerate even one success.
    config=json.loads(job['config_json'])
    for row in db.execute('SELECT attempt_id FROM attempts WHERE job_id=?',(job['job_id'],)):
        if (output_path(config['stage'],row[0])/'inference-started.json').exists():raise ValueError('pose forward began; preserve partial results without regeneration')


def command(config,inputs,runtime,attempt,lock_fd):
    stage=validate(config,inputs,runtime)
    if not re.fullmatch('[0-9a-f]{32}',attempt):raise ValueError('invalid pose attempt')
    return [str(INTERPRETER),'-I',str(ROOT/'batch03_pose/runner.py'),'--stage',stage,'--attempt',attempt,'--lock-fd',str(lock_fd)]
