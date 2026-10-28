"""One fixed RF-DETR native-frame command in the existing canonical queue."""
import json
from pathlib import Path
import re

from orchestration.vlm_command import RUNTIME, file_hash

ROOT = Path('/home/jhc7484/dev/sceneguard-ai')
INTERPRETER = ROOT / '.venv-cv-batch02/bin/python'
MANIFEST = ROOT / 'configs/batch0002_cv_manifest.json'
LOCAL = ROOT / 'runtime/BATCH-0002/cv'
WEIGHT = ROOT / 'weights/rf-detr-medium/rf-detr-medium.pth'
SETTINGS = dict(model='RFDETRMedium', rfdetr='1.11.2', device='cuda:0', dtype='float32',
    batch_size=1, resolution=[576, 576], threshold=0.5, threshold_operator='>',
    num_queries=300, num_select=300, nms=None, compile=False, warmup_frames=0,
    minimum_gpu_free_mib=6144, execution_error_retries_max=1)
STAGES = ('smoke', 'remaining')
SMOKE = ('030_084', '030_090')
EXPECTED_FRAMES = ('030_084', '030_090', '030_094', '007_052', '007_064', '007_066',
                   '031_032', '031_040', '006_119', '006_125', '006_131')


def same(a, b):
    return json.dumps(a, sort_keys=True, allow_nan=False) == json.dumps(b, sort_keys=True, allow_nan=False)


def manifest():
    d = json.loads(MANIFEST.read_text())
    if not same(d['settings'], SETTINGS) or tuple(r['frame_id'] for r in d['frames']) != EXPECTED_FRAMES:
        raise ValueError('frozen eleven-frame manifest or settings differ')
    if d['model']['bytes'] != 404992918 or d['model']['md5'] != '7223f764a87b863f02eb8d52bf0ce2ee':
        raise ValueError('sole official checkpoint differs')
    return d


def sources(config=None):
    names = ['orchestration/queue.py', 'orchestration/mock_job.py', 'orchestration/vlm_command.py',
             'orchestration/batch02_cv_command.py', 'configs/batch0002_cv_manifest.json',
             'requirements-cv-batch02-lock.txt', 'tests_orca/test_batch02_cv.py']
    names += [str(p.relative_to(ROOT)) for p in sorted((ROOT / 'batch02_cv').glob('*.py'))]
    return {n: file_hash(ROOT / n) for n in names}


def validate_assignment(run, task, dispatch):
    assignment = json.loads((LOCAL / 'execution-authorization.json').read_text())
    if (run, task, dispatch) != tuple(assignment[k] for k in ('run_id', 'task_id', 'dispatch_id')):
        raise ValueError('coordinator-confirmed CV execution assignment required')
    if assignment.get('confirmed') is not True:
        raise ValueError('coordinator code freeze confirmation required')
    if assignment['sources'] != sources():
        raise ValueError('code/config differ from coordinator-confirmed freeze')
    return assignment


def input_contract(stage):
    if stage not in STAGES:
        raise ValueError('fixed smoke/remaining stage required')
    d = manifest()
    pins = {**d['historical_pins'], **d['environment']['files']}
    pins.update({r['source_path']: r['source_sha256'] for r in d['frames']})
    pins.update({r['rgb_path']: r['rgb_sha256'] for r in d['frames']})
    pins['weights/rf-detr-medium/rf-detr-medium.pth'] = d['model']['sha256']
    for name, expected in pins.items():
        path = ROOT / name
        if not path.is_relative_to(ROOT) or file_hash(path) != expected:
            raise ValueError('frozen local input/model/environment hash differs: ' + name)
    if d['environment'].get('file_index'):
        index = json.loads((ROOT / d['environment']['file_index']).read_text())
        for name, expected in index.items():
            if not name.startswith('.venv-cv-batch02/') or file_hash(ROOT / name) != expected:
                raise ValueError('isolated installed environment changed: ' + name)
    if WEIGHT.stat().st_size != d['model']['bytes']:
        raise ValueError('checkpoint size differs')
    return dict(manifest_sha256=file_hash(MANIFEST), files=pins,
                frames=[r['frame_id'] for r in d['frames'] if (r['frame_id'] in SMOKE) == (stage == 'smoke')])


def successful_smoke():
    import sqlite3
    with sqlite3.connect(f'file:{RUNTIME / "queue.sqlite3"}?mode=ro', uri=True) as db:
        rows = db.execute("SELECT a.attempt_id,j.source_hash,j.input_json FROM attempts a JOIN jobs j USING(job_id) "
            "WHERE j.command='batch02-cv' AND a.status='succeeded' AND j.status='succeeded' "
            "AND json_extract(j.config_json,'$.stage')='smoke'").fetchall()
    from orchestration.queue import digest
    matching = []
    for attempt, source, inputs in rows:
        path = output_path('smoke', attempt) / 'summary.json'
        if source != digest(sources()) or json.loads(inputs) != input_contract('smoke') or not path.is_file():
            continue
        summary = json.loads(path.read_text())
        if summary['status'] == 'succeeded' and [r['frame_id'] for r in summary['results']] == list(SMOKE):
            matching.append(attempt)
    if len(matching) != 1:
        raise ValueError('one successful exact frozen smoke required before remaining nine')
    return matching[0]


def validate(config, inputs, runtime):
    if not isinstance(config, dict) or set(config) != {'stage', 'settings'}:
        raise ValueError('fixed stage/settings config required')
    if config['stage'] not in STAGES or not same(config['settings'], SETTINGS):
        raise ValueError('unregistered CV stage or settings')
    if Path(runtime).resolve() != RUNTIME or not INTERPRETER.is_file():
        raise ValueError('canonical queue and isolated CV interpreter required')
    if inputs != input_contract(config['stage']):
        raise ValueError('registered CV inputs differ')
    if config['stage'] == 'remaining':
        successful_smoke()
    return config['stage']


def command(config, inputs, runtime, attempt, lock_fd):
    stage = validate(config, inputs, runtime)
    if not re.fullmatch('[0-9a-f]{32}', attempt):
        raise ValueError('invalid queue attempt')
    return [str(INTERPRETER), '-I', str(ROOT / 'batch02_cv/runner.py'), '--stage', stage,
            '--attempt', attempt, '--lock-fd', str(lock_fd)]


def output_path(stage, attempt):
    if stage not in STAGES or not re.fullmatch('[0-9a-f]{32}', attempt):
        raise ValueError('invalid CV output identity')
    return ROOT / 'outputs/batch0002/cv/EXP-0019' / stage / attempt
