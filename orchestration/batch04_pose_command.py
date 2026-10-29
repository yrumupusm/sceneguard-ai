# SPDX-License-Identifier: AGPL-3.0-only
"""Fixed public-predict contract; existing canonical queue and historical inputs."""
import json
from pathlib import Path
import re
from orchestration.vlm_command import RUNTIME, file_hash
from orchestration.batch03_pose_command import (
    ROOT, INTERPRETER, WEIGHT, WEIGHT_SHA, COCO17, same,
    manifest as historical_manifest, input_contract as historical_input_contract)

LOCAL = ROOT / 'runtime/BATCH-0004'
MANIFEST = ROOT / 'configs/batch0004_pose_manifest.json'
HISTORICAL_SHA = '6ea2fe8d692611f7808b1109a591fedff9cd8c901f13cc43474246324927883d'
STAGES = ('smoke', 'remaining')
SMOKE = ('030_090', '007_064')
# quantize=None is the pinned release's public FP32 option (half=False is deprecated).
PREDICT_KWARGS = dict(imgsz=640, rect=False, batch=1, conf=.25, device='cuda:0',
    quantize=None, nms=False, max_det=300, iou=.7, agnostic_nms=False,
    classes=[0], augment=False, compile=False, channels_last=False,
    save=False, save_txt=False, save_crop=False, show=False, verbose=False,
    stream=False, visualize=False, embed=None)
SETTINGS = dict(api='YOLO.predict', ultralytics='8.4.192', source='contiguous BGR uint8 ndarray',
    predict_kwargs=PREDICT_KWARGS, dtype='float32', full_frame=True,
    fuse='official setup_model fuse=True', warmup='official first preprocess tensor; separate from sample predictions',
    joint_confidence=.5, minimum_gpu_free_mib=6144, execution_error_retries_max=1)


def manifest():
    old = historical_manifest()
    if file_hash(ROOT / 'configs/batch0003_pose_manifest.json') != HISTORICAL_SHA:
        raise ValueError('historical manifest changed')
    d = json.loads(MANIFEST.read_text())
    if d['historical_manifest_sha256'] != HISTORICAL_SHA or not same(d['settings'], SETTINGS):
        raise ValueError('fixed public predict manifest/settings differ')
    for key in ('frames', 'windows', 'sampling', 'historical_pins', 'environment', 'model', 'coco17'):
        if not same(d[key], old[key]):
            raise ValueError('historical input/environment/model parity differs: ' + key)
    if len(d['frames']) != 267:
        raise ValueError('exact 267 original inputs required')
    return d


def sources(config=None):
    names = ['orchestration/queue.py', 'orchestration/mock_job.py', 'orchestration/vlm_command.py',
        'orchestration/batch04_pose_command.py', 'orchestration/batch03_pose_command.py',
        'batch03_pose/prepare.py', 'configs/batch0003_pose_manifest.json',
        'configs/batch0004_pose_manifest.json', 'requirements-pose-batch03-lock.txt',
        'tests_orca/test_batch04_pose.py']
    names += [str(p.relative_to(ROOT)) for p in sorted((ROOT / 'batch04_pose').glob('*.py'))]
    return {n: file_hash(ROOT / n) for n in names}


def validate_assignment(run, task, dispatch):
    a = json.loads((LOCAL / 'execution-authorization.json').read_text())
    if (run, task, dispatch) != ('run_3d23462a014a', 'task_5df19346a61c', 'ctx_9a8df3d90186'):
        raise ValueError('current native Run/Task/Dispatch required')
    if (run, task, dispatch) != tuple(a[k] for k in ('run_id', 'task_id', 'dispatch_id')) or a.get('confirmed') is not True:
        raise ValueError('coordinator specific authorization required')
    if a['sources'] != sources():
        raise ValueError('source/config differs from reviewed freeze')
    return a


def input_contract(stage):
    if stage not in STAGES:
        raise ValueError('fixed stage required')
    manifest()
    # Reuse only historical CPU provenance validation, never historical inference.
    old = historical_input_contract(stage)
    return dict(old, manifest_sha256=file_hash(MANIFEST),
        historical_manifest_sha256=HISTORICAL_SHA)


def output_path(stage, attempt):
    if stage not in STAGES or not re.fullmatch('[0-9a-f]{32}', attempt):
        raise ValueError('invalid public-predict output identity')
    return ROOT / 'outputs/batch0004/EXP-0022' / stage / attempt


def job_key(stage):
    if stage not in STAGES:
        raise ValueError('fixed stage required')
    return 'batch0004-exp0022-public-predict-' + stage


def execution_guard(db, job, attempt):
    """Reject alternate keys/attempts as well as explicit retries, before model import."""
    stage = json.loads(job['config_json'])['stage']
    rows = db.execute("SELECT j.job_key,j.run_id,j.task_id,j.dispatch_id,a.attempt_id,a.attempt_no "
        "FROM jobs j LEFT JOIN attempts a USING(job_id) WHERE j.command='batch04-pose'").fetchall()
    current = False
    for key, run, task, dispatch, aid, number in rows:
        if key not in [job_key(x) for x in STAGES] or (run,task,dispatch) != ('run_3d23462a014a','task_5df19346a61c','ctx_9a8df3d90186'):
            raise ValueError('alternate public pose queue identity forbidden')
        if number is not None and number != 1:
            raise ValueError('one initial attempt per stage; reviewed correction requires separate freeze')
        if aid == attempt and key == job_key(stage):
            current = True
    if not current or job['job_key'] != job_key(stage):
        raise ValueError('exact current public pose queue attempt required')


def ensure_unprocessed(frame_id):
    base = ROOT / 'outputs/batch0004/EXP-0022'
    if list(base.glob('*/*/'+frame_id+'-predict-started.json')) or list(base.glob('*/*/'+frame_id+'-results.pt')):
        raise ValueError('input already attempted; preserve partial successes without regeneration')


def successful_smoke():
    import sqlite3
    from orchestration.queue import digest
    expected_inputs = input_contract('smoke')
    expected_config = dict(stage='smoke', settings=SETTINGS)
    with sqlite3.connect(f'file:{RUNTIME / "queue.sqlite3"}?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute("SELECT a.attempt_id,j.* FROM attempts a JOIN jobs j USING(job_id) WHERE "
            "j.command='batch04-pose' AND a.status='succeeded' AND j.status='succeeded' "
            "AND json_extract(j.config_json,'$.stage')='smoke'").fetchall()
    matches = []
    for row in rows:
        attempt = row['attempt_id']
        if (row['job_key'] != job_key('smoke') or row['source_hash'] != digest(sources())
                or json.loads(row['input_json']) != expected_inputs or row['input_hash'] != digest(expected_inputs)
                or json.loads(row['config_json']) != expected_config or row['config_hash'] != digest(expected_config)):
            raise ValueError('successful smoke source/input/config lineage differs')
        path = output_path('smoke', attempt) / 'summary.json'
        s = json.loads(path.read_text())
        if any(s['registration'][k] != row[k] for k in ('job_id','run_id','task_id','dispatch_id','code_sha','source_hash','input_hash','config_hash')):
            raise ValueError('successful smoke registration lineage differs')
        if s.get('technical_pass') is not True or [r['frame_id'] for r in s['results']] != list(SMOKE):
            raise ValueError('two exact successful smoke results required')
        for r in s['results']:
            for a in r['artifacts'].values():
                p = ROOT / a['path']
                if p.parent != path.parent or file_hash(p) != a['sha256']:
                    raise ValueError('successful smoke artifact hash differs')
        matches.append((attempt, file_hash(path)))
    if len(matches) != 1:
        raise ValueError('one exact successful smoke required')
    return matches[0]


def validate(config, inputs, runtime):
    if not isinstance(config, dict) or set(config) != {'stage', 'settings'} or config['stage'] not in STAGES or not same(config['settings'], SETTINGS):
        raise ValueError('fixed public-predict stage/settings required')
    if Path(runtime).resolve() != RUNTIME or not INTERPRETER.is_file():
        raise ValueError('canonical queue and existing interpreter required')
    if inputs != input_contract(config['stage']):
        raise ValueError('fixed inputs differ')
    a = validate_assignment('run_3d23462a014a', 'task_5df19346a61c', 'ctx_9a8df3d90186')
    if config['stage'] not in a.get('allowed_stages', []):
        raise ValueError('stage lacks coordinator authorization')
    if config['stage'] == 'remaining':
        attempt, sha = successful_smoke()
        gate = a.get('human_pose_review', {})
        if (gate.get('useful') is not True or gate.get('attempt_id') != attempt or gate.get('summary_sha256') != sha
                or not gate.get('reviewer') or not gate.get('reviewed_at') or not gate.get('evidence_path')
                or not gate.get('evidence_sha256')):
            raise ValueError('actual person/joint usefulness review required before remaining265')
        evidence = ROOT / gate['evidence_path']
        if not evidence.resolve().is_relative_to(LOCAL.resolve()) or file_hash(evidence) != gate['evidence_sha256']:
            raise ValueError('local human review evidence hash differs')
    return config['stage']


def retry_guard(db, job):
    raise ValueError('no automatic retry; CPU correction, independent review and new freeze required')


def command(config, inputs, runtime, attempt, lock_fd):
    stage = validate(config, inputs, runtime)
    output_path(stage, attempt)
    return [str(INTERPRETER), '-I', str(ROOT / 'batch04_pose/runner.py'),
        '--stage', stage, '--attempt', attempt, '--lock-fd', str(lock_fd)]
