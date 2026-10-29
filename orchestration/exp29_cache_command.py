"""EXP-0029: one frozen FCOS cache extension through the canonical GPU queue."""
from fractions import Fraction
import importlib.metadata
import json
from pathlib import Path
import re
import subprocess

from orchestration.queue import digest
from orchestration.vlm_command import file_hash

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = Path('/home/jhc7484/dev/sceneguard-orca-lab/runtime/orca-lab/gpu-queue')
INTERPRETER = ROOT / '.venv/bin/python'
LOCAL = ROOT / 'runtime/EXP-0029'
CACHE = ROOT / 'outputs/cv_phase2d/cache007'
VIDEO = ROOT / 'data/TS_침입/E01_007.mp4'
WEIGHT = ROOT / 'weights/fcos_resnet50_fpn_coco-99b0c9b7.pth'
MERGED = ROOT / 'outputs/exp0029/cache007'
REPLAY = ROOT / 'outputs/exp0029/replay007'
IDENTITY = ('run_3d23462a014a', 'task_7878e1292391', 'ctx_76ca1e4c9b85')
WEIGHT_SHA = '99b0c9b7cfb1527d782db86b91d207f00547c792fb4103fc612b651d0a07b9e7'
VIDEO_SHA = 'df88fcfe8293b5c624a617bb9d36e68fb366acbd0a35835805ee35e31c5b7c04'
OLD_FILES = {'run.json': '63adea541d95ef0854ca7765f116961228674ff8057dc556ec73b2eef2ed5c0c',
             'person_cache.jsonl': 'ecb55d37b8d15806366453263d33df8fb096b5293e18d3c5144e7d3789e4753b',
             'frames.jsonl': '2a1e841c3e26edeee4336006f5edefd701431cebaeab70d35a0ceea07653f016'}
SETTINGS = dict(detector='fcos800', device='cuda', start=68.0, end=105.0,
                cache_person=True, download_weights=False, diagnose_fcos=False,
                batch_size=1, precision='float32', warmup_frames=10, threads=2, seed=0,
                sampling='none', minimum_gpu_free_mib=6144, maximum_new_frames=1110,
                retain_seconds=3.0, execution_error_retries_max=1, automatic_retry=False)


def checked(path, expected):
    path = Path(path)
    if path.is_symlink() or file_hash(path) != expected:
        raise ValueError('Frozen input bytes differ: ' + str(path))


def timing_rows(rows, first, count):
    """Exact integer native PTS; no timestamps synthesized from display FPS."""
    if len(rows) != count:
        raise ValueError('Exact frame count required')
    for index, row in enumerate(rows):
        if (type(row['native_pts']) is not int or row['native_pts'] != first + index * 512
                or row['time_base'] != '1/15360'
                or row['pts'] != float(row['native_pts'] * Fraction(row['time_base']))
                or row['source_size'] != [1920, 1080]):
            raise ValueError('Exact unsampled source native PTS/size required')


def environment():
    site = ROOT / '.venv/lib/python3.10/site-packages'
    versions = {}
    for name, expected in [('torch', '2.5.1+cu124'), ('torchvision', '0.20.1+cu124'),
                           ('av', '16.0.1'), ('numpy', '2.2.6')]:
        dist = next(d for d in importlib.metadata.distributions(path=[str(site)])
                    if d.metadata['Name'].lower() == name)
        if dist.version != expected:
            raise ValueError('Original .venv package version differs: ' + name)
        versions[name] = dist.version
    # Pin installed package bytes, including native CUDA/decoder libraries, without imports.
    files = {str(p.relative_to(ROOT)): file_hash(p)
             for name in versions for p in sorted((site/name).rglob('*'))
             if p.is_file() and p.suffix != '.pyc' and '__pycache__' not in p.parts}
    return dict(versions=versions, files=files)


def input_contract(stage='extend007'):
    job_key(stage)
    for name, sha in OLD_FILES.items():
        checked(CACHE/name, sha)
    checked(VIDEO, VIDEO_SHA)
    checked(WEIGHT, WEIGHT_SHA)
    old = json.loads((CACHE/'run.json').read_text())
    if json.loads((LOCAL/'cache007-config.local.json').read_text()) != old['config']:
        raise ValueError('Original camera configuration required')
    schedule = json.loads((LOCAL/'cache007-native-schedule.local.json').read_text())
    timing_rows(schedule['original'], 737280, 600)
    timing_rows(schedule['extension'], 1044480, 1110)
    current = environment()
    if current != json.loads((LOCAL/'cache007-environment.local.json').read_text()):
        raise ValueError('Frozen original .venv bytes differ')
    return dict(video_sha256=VIDEO_SHA, weight_sha256=WEIGHT_SHA, historical_cache=OLD_FILES,
                configuration_sha256=file_hash(LOCAL/'cache007-config.local.json'),
                native_schedule_sha256=file_hash(LOCAL/'cache007-native-schedule.local.json'),
                environment_sha256=digest(current))


def sources(config=None):
    names = ['orchestration/queue.py', 'orchestration/mock_job.py', 'orchestration/vlm_command.py',
             'orchestration/exp29_cache_command.py', 'tests_orca/test_exp29_cache.py',
             'batch04_pose/runner.py', 'orchestration/batch04_pose_command.py']
    names += [str(p.relative_to(ROOT)) for p in (ROOT/'exp29_cache').glob('*.py')]
    names += ['sceneguard/'+n+'.py' for n in ('run_cv', 'detectors', 'boundary', 'replay_gap_tracking',
               'gap_boundary', 'byte_adapter', 'replay_thresholds')]
    names += [str(p.relative_to(ROOT)) for p in (ROOT/'sceneguard/vendor').rglob('*.py')]
    return {n: file_hash(ROOT/n) for n in sorted(set(names))}


def validate_assignment(run, task, dispatch):
    a = json.loads((LOCAL/'cache007-execution-authorization.json').read_text())
    if (run, task, dispatch) != IDENTITY or tuple(a[k] for k in ('run_id', 'task_id', 'dispatch_id')) != IDENTITY:
        raise ValueError('Current EXP29 extension Run/Task/Dispatch required')
    if any(a.get(k) is not True for k in ('confirmed', 'inference_authorized', 'independent_review_passed')):
        raise ValueError('Coordinator and independent preflight authorization required')
    if a.get('sources') != sources() or a.get('input_contract_sha256') != digest(input_contract()):
        raise ValueError('Exact reviewed source and input freeze required')
    if a.get('maximum_new_frames') != 1110 or a.get('allowed_stages') != ['extend007']:
        raise ValueError('Only 1110 extension samples are authorized')
    if a.get('code_sha') != subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip():
        raise ValueError('Git HEAD differs from reviewed freeze')
    return a


def job_key(stage='extend007'):
    if stage != 'extend007':
        raise ValueError('Only EXP29 cache007 extension stage is registered')
    return 'exp0029-fcos-cache007-extension'


def output_path(stage, attempt):
    job_key(stage)
    if not re.fullmatch('[0-9a-f]{32}', attempt):
        raise ValueError('Invalid attempt')
    return ROOT/'outputs/exp0029/extension007'/attempt


def validate(config, inputs, runtime):
    if (config != dict(stage='extend007', settings=SETTINGS) or Path(runtime).resolve() != RUNTIME
            or not INTERPRETER.is_file()):
        raise ValueError('Fixed EXP29 settings, original .venv and canonical queue required')
    if inputs != input_contract():
        raise ValueError('Frozen extension input differs')
    validate_assignment(*IDENTITY)
    return 'extend007'


def execution_guard(db, job, attempt):
    rows = db.execute("SELECT j.job_key,j.run_id,j.task_id,j.dispatch_id,a.attempt_id,a.attempt_no "
                      "FROM jobs j LEFT JOIN attempts a USING(job_id) WHERE j.command='exp29-cache007'").fetchall()
    if (not 1 <= len(rows) <= 2 or any(tuple(r[:4]) != (job_key(), *IDENTITY) for r in rows)
            or sum(r[4] == attempt and r[5] in (1, 2) for r in rows) != 1
            or job['job_key'] != job_key()):
        raise ValueError('One fixed EXP29 job, maximum two explicitly reviewed attempts required')


def retry_guard(db, job):
    a = validate_assignment(job['run_id'], job['task_id'], job['dispatch_id'])
    first = db.execute('SELECT attempt_id,status FROM attempts WHERE job_id=? ORDER BY attempt_no',
                       (job['job_id'],)).fetchall()
    if (len(first) != 1 or first[0][1] != 'failed'
            or a.get('execution_error_retry_authorized_for') != first[0][0]):
        raise ValueError('Only one coordinator-reviewed execution-error retry; no automatic retry')


def command(config, inputs, runtime, attempt, lock_fd):
    stage = validate(config, inputs, runtime)
    output_path(stage, attempt)
    return [str(INTERPRETER), '-I', str(ROOT/'exp29_cache/runner.py'), '--stage', stage,
            '--attempt', attempt, '--lock-fd', str(lock_fd)]
