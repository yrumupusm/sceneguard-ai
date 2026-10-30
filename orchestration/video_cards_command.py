"""Allowlisted existing-FCOS generation for the local video-to-cards command."""
import json
import os
from pathlib import Path
import re
import subprocess

from orchestration.queue import digest
from sceneguard.replay_gap_tracking import sha256, FCOS_SHA

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = Path('/home/jhc7484/dev/sceneguard-orca-lab/runtime/orca-lab/gpu-queue')
INTERPRETER = ROOT/'.venv/bin/python'
WEIGHT = ROOT/'weights/fcos_resnet50_fpn_coco-99b0c9b7.pth'
SETTINGS = dict(detector='fcos800', device='cuda', cache_person=True, download_weights=False,
                diagnose_fcos=False, precision='float32', batch_size=1, seed=0,
                sampling='none', warmup_frames=10, minimum_gpu_free_mib=6144)


def sources(config=None):
    from sceneguard.video_cards import code_binding
    paths = ['orchestration/queue.py','orchestration/mock_job.py',
             'orchestration/video_cards_command.py','sceneguard/video_cards_gpu.py',
             'batch04_pose/runner.py']
    return code_binding() | {p:sha256(ROOT/p) for p in paths}


def validate_assignment(context):
    if context.get('run_id') != 'run_3d23462a014a':
        raise ValueError('Existing canonical Orca Run required')
    cli = os.environ.get('ORCA_CLI_COMMAND','orca-ide')
    data = json.loads(subprocess.check_output([cli,'orchestration','worker-show',
                       '--dispatch',context['dispatch_id'],'--json'],text=True,timeout=25))
    if not data.get('ok'):
        raise ValueError('Orca current assignment unavailable')
    dispatch = data['result']['dispatch']
    if (dispatch['runId'] != context['run_id'] or dispatch['taskId'] != context['task_id']
            or dispatch['assigneeHandle'] != context['owner']
            or dispatch['status'] != 'dispatched' or dispatch.get('capabilityRevokedAt') is not None):
        raise ValueError('Current live Run/Task/Dispatch/owner binding required')
    return dispatch


def validate(config, inputs, runtime):
    from sceneguard.video_cards import read, code_binding, probe, SCENES, CAMERAS
    if set(config) != {'stage','request_path','request_sha256','settings','context'}:
        raise ValueError('Exact video-card queue contract required')
    path = Path(config['request_path'])
    if (Path(runtime).resolve() != RUNTIME or config['stage'] != 'fcos-cache'
            or config['settings'] != SETTINGS or path.is_symlink()
            or not path.resolve().is_relative_to(ROOT/'outputs')
            or sha256(path) != config['request_sha256'] or sha256(WEIGHT) != FCOS_SHA):
        raise ValueError('Canonical runtime/local weight/immutable request/settings required')
    request = read(path)
    if request['queue_context'] != config['context'] or request['camera_id'] not in SCENES:
        raise ValueError('Request queue identity/camera differs')
    if request['code_sha256'] != code_binding() or request['cache'] is not None:
        raise ValueError('Current code and genuinely new detector request required')
    camera = read(CAMERAS)['cameras'][request['camera_id']]
    video = Path(request['video'])
    info = probe(video)
    a,b = request['requested_window']
    if not 0 <= a < b <= info['duration']+1e-6:
        raise ValueError('Source window differs')
    scene = read(SCENES[request['camera_id']])
    region = Path(scene['annotation_provenance']['current_regions_path'])
    if not region.is_absolute(): region = ROOT/region
    actual = dict(video=sha256(video),cameras=sha256(CAMERAS),
                  scene=sha256(SCENES[request['camera_id']]),regions=sha256(region))
    expected = dict(request_sha256=config['request_sha256'],source_sha256=actual['video'],
                    model_sha256=FCOS_SHA,settings_sha256=digest(SETTINGS))
    if request['input_sha256'] != actual or inputs != expected:
        raise ValueError('Source/settings input bytes differ')
    from sceneguard.exp0034_application import validate_scene_binding
    validate_scene_binding(scene,[dict(source_size=info['size'])],read(region),camera)
    validate_assignment(config['context'])
    return request


def output_path(stage, attempt):
    if stage != 'fcos-cache' or not re.fullmatch('[0-9a-f]{32}',attempt):
        raise ValueError('Exact cache stage/attempt required')
    return ROOT/'outputs/exp0037/detector'/attempt


def command(config, inputs, runtime, attempt, lock_fd):
    validate(config,inputs,runtime)
    return [str(INTERPRETER),'-I',str(ROOT/'sceneguard/video_cards_gpu.py'),
            '--attempt',attempt,'--lock-fd',str(lock_fd)]


def retry_guard(db, job):
    raise ValueError('Automatic/fresh detector retry is disabled; coordinator diagnosis required')


def generate_cache(request_path, output, context):
    from orchestration.queue import Queue
    from sceneguard.video_cards import read, save
    request = read(request_path)
    config = dict(stage='fcos-cache',request_path=str(request_path),request_sha256=sha256(request_path),
                  settings=SETTINGS,context=context)
    inputs = dict(request_sha256=config['request_sha256'],source_sha256=request['input_sha256']['video'],
                  model_sha256=FCOS_SHA,settings_sha256=digest(SETTINGS))
    validate(config,inputs,RUNTIME)
    queue = Queue(RUNTIME)
    key = 'video-cards-'+config['request_sha256']
    if any(j['job_key'] != key and j['status'] in ('queued','running','unknown')
           for j in queue.status()['jobs']):
        raise RuntimeError('Canonical queue has other pending work; no unrelated job will be started')
    queued = queue.enqueue(job_key=key,command='video-cards',
                          input_value=inputs,config=config,timeout=3600,**context)
    receipt_path = Path(output)/'queue-job.json'
    if not receipt_path.exists(): save(receipt_path,queued)
    jobs = queue.status()['jobs']
    current = next(j for j in jobs if j['job_id']==queued['job_id'])
    executed = current['status'] == 'queued'
    if current['status'] == 'queued':
        # Canonical detached supervisor owns the inherited reservation and child.
        queue.run_once(job_id=queued['job_id'])
    with queue.connection() as db:
        job = db.execute('SELECT status FROM jobs WHERE job_id=?',(queued['job_id'],)).fetchone()
        attempts = db.execute('SELECT attempt_id,status FROM attempts WHERE job_id=? ORDER BY attempt_no',
                              (queued['job_id'],)).fetchall()
    if job[0] != 'succeeded' or len(attempts)!=1 or attempts[0][1]!='succeeded':
        raise RuntimeError('Canonical detector job did not succeed; inspect queue-job.json; no automatic retry')
    cache = output_path('fcos-cache',attempts[0][0])/'cache'
    return cache,read(cache/'run.json')['frames'] if executed else 0
