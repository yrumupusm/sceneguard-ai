# SPDX-License-Identifier: AGPL-3.0-only
"""Three 960 public predictions; historical utilities are imported read-only."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import sys
import time
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from orchestration.mock_job import atomic_json
from orchestration.queue import digest,process_state,source_hash
from orchestration.batch06_pose_command import (ROOT,RUNTIME,LOCAL,WEIGHT,INTERPRETER,
    SETTINGS,PREDICT_KWARGS,CONDITIONS,manifest,cached_records,output_path,validate,
    validate_assignment,execution_guard,ensure_unprocessed)
from batch04_pose.api import bgr_source
from batch04_pose.runner import resources,DeviceSampler,deny_network
from batch05_pose.geometry import crop,rows
from batch06_pose.visuals import comparison_images
from batch06_pose.observer import ObserveOfficial


def verify_lease(config, attempt, fd):
    if len(attempt) != 32 or any(c not in '0123456789abcdef' for c in attempt):
        raise ValueError('invalid pose attempt')
    inherited, canonical = os.fstat(fd), (RUNTIME / 'gpu.lock').stat()
    if (inherited.st_dev, inherited.st_ino) != (canonical.st_dev, canonical.st_ino):
        raise ValueError('canonical inherited queue descriptor required')
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        raise ValueError('descriptor does not own inherited reservation') from exc
    with (RUNTIME / 'gpu.lock').open('r') as other:
        try:
            fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            pass
        else:
            raise ValueError('canonical queue reservation is not held')
    # Parent records the child immediately after Popen; no model import during that handshake.
    row = None
    for _ in range(100):
        with sqlite3.connect(f'file:{RUNTIME / "queue.sqlite3"}?mode=ro', uri=True) as db:
            db.row_factory = sqlite3.Row
            row = db.execute('SELECT a.status AS attempt_status,a.supervisor_pid,a.supervisor_identity,'
                'a.child_pid,a.child_identity,j.* FROM attempts a JOIN jobs j USING(job_id) '
                'WHERE a.attempt_id=?', (attempt,)).fetchone()
        if row is None or row['child_pid'] is not None:
            break
        time.sleep(.01)
    if row is None or row['attempt_status'] != 'running' or row['status'] != 'running' or row['command'] != 'batch06-pose':
        raise ValueError('live pose queue attempt required')
    if row['supervisor_pid'] != os.getppid() or process_state(row['supervisor_pid'], row['supervisor_identity']) != 'live':
        raise ValueError('exact live queue supervisor must be parent')
    if row['child_pid'] != os.getpid() or process_state(row['child_pid'], row['child_identity']) != 'live':
        raise ValueError('recorded exact child identity required')
    if json.loads(row['config_json']) != config:
        raise ValueError('live queue config differs')
    authorization = validate_assignment(row['run_id'], row['task_id'], row['dispatch_id'])
    if authorization['code_sha'] != row['code_sha']:
        raise ValueError('queue commit differs from coordinator-confirmed code freeze')
    inputs = json.loads(row['input_json'])
    if digest(inputs) != row['input_hash'] or digest(config) != row['config_hash'] or source_hash('batch06-pose', config) != row['source_hash']:
        raise ValueError('source/input/config queue hashes differ')
    validate(config, inputs, RUNTIME)
    with sqlite3.connect(f'file:{RUNTIME / "queue.sqlite3"}?mode=ro', uri=True) as db:
        execution_guard(db, row, attempt)
    if Path(sys.executable).absolute() != INTERPRETER:
        raise ValueError('fixed isolated pose interpreter required')
    return dict(row)



def run(stage, attempt, fd):
    whole = time.perf_counter()
    config = dict(stage=stage,settings=SETTINGS)
    job = verify_lease(config,attempt,fd)
    d = manifest()
    folder = output_path(stage,attempt)
    folder.mkdir(parents=True,exist_ok=False)
    summary = dict(status='preflight',technical_pass=False,config=config,attempt_id=attempt,results=[],
        registration={k:job[k] for k in ('job_id','run_id','task_id','dispatch_id','code_sha','source_hash','input_hash','config_hash')},
        public_predict_calls=0,successful_results=0,warmup_model_forward_count=0,sample_model_forward_count=0,
        warmup_model_forward_attempts=0,sample_model_forward_attempts=0,
        accuracy=None,precision=None,recall=None,f1=None,false_positive_rate=None,
        visual_quality='unreviewed',behavior='unmeasured; no rule/tracker',new_conditions=3,cached_conditions=3,model_constructions=0,
        initial_validation_seconds=time.perf_counter()-whole)
    monitor = None
    try:
        summary['resource_gate'] = resources()
        os.environ.update(YOLO_AUTOINSTALL='false',YOLO_OFFLINE='true',YOLO_CONFIG_DIR=str(LOCAL/'ultralytics-settings'),
            MPLCONFIGDIR=str(LOCAL/'matplotlib'),HF_HUB_OFFLINE='1',ULTRALYTICS_OFFLINE='true')
        # Block network at socket transport, including DNS/UDP; no algorithm monkeypatch.
        socket.socket.connect = deny_network
        socket.socket.connect_ex = deny_network
        socket.socket.sendto = deny_network
        socket.create_connection = deny_network
        socket.getaddrinfo = deny_network
        import numpy as np
        import torch
        from ultralytics import YOLO
        if not torch.cuda.is_available():
            raise ValueError('CUDA required; no CPU fallback')
        torch.set_default_dtype(torch.float32)
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        torch.manual_seed(0)
        monitor = DeviceSampler(); monitor.start()
        torch.cuda.reset_peak_memory_stats()
        t = time.perf_counter()
        summary['model_constructions'] += 1
        model = YOLO(str(WEIGHT),task='pose')
        torch.cuda.synchronize()
        summary.update(model_construction_load_seconds=time.perf_counter()-t,
            device=torch.cuda.get_device_name(0),torch=torch.__version__,cuda=torch.version.cuda)
        if model.task != 'pose' or model.names != {0:'person'}:
            raise ValueError('official pose/person model required')
        by_id = {r['frame_id']:r for r in d['frames']}
        for condition in CONDITIONS:
            frame_id, view, resolution = condition.rsplit('_',2)
            if view != 'C6' or resolution != '960':
                raise ValueError('only C6 960 conditions allowed')
            ensure_unprocessed(condition)
            item = by_id[frame_id]; start = time.perf_counter()
            rgb = np.load(ROOT/item['rgb_path'],allow_pickle=False)
            if list(rgb.shape) != item['rgb_shape'] or hashlib.sha256(rgb.tobytes()).hexdigest() != item['rgb_bytes_sha256']:
                raise ValueError('native source RGB mismatch')
            source = crop(rgb) if view=='C6' else rgb
            bgr = bgr_source(source)
            read_seconds = time.perf_counter()-start
            atomic_json(folder/(condition+'-predict-started.json'),dict(frame_id=frame_id,attempt_id=attempt))
            summary['public_predict_calls'] += 1
            t = time.perf_counter()
            observer = ObserveOfficial(torch,folder,condition,model)
            try:
                with observer:
                    returned = model.predict(source=bgr,**PREDICT_KWARGS)
            finally:
                # Preserve observed partial timings/counts even on an exception.
                atomic_json(folder/(condition+'-official-events.local.json'),dict(attempts=observer.attempts,events=observer.events,tensor=observer.tensor))
                summary['warmup_model_forward_count'] += sum(e['stage']=='network_predict' and e['warmup'] and e['returned_value'] for e in observer.events)
                summary['sample_model_forward_count'] += sum(e['stage']=='network_predict' and not e['warmup'] and e['returned_value'] for e in observer.events)
                summary['warmup_model_forward_attempts'] += sum(e['stage']=='network_predict' and e['warmup'] for e in observer.attempts)
                summary['sample_model_forward_attempts'] += sum(e['stage']=='network_predict' and not e['warmup'] for e in observer.attempts)
            torch.cuda.synchronize()
            predict_wall = time.perf_counter()-t
            if not isinstance(returned,list) or len(returned) != 1:
                raise ValueError('one native Results required per public predict')
            native = returned[0]
            # Preserve actual native Results first; interpretation must not discard it.
            torch.save(native.cpu(),folder/(condition+'-results.pt'))
            summary['successful_results'] += 1
            parsed = rows(native,source.shape,view)
            people = parsed['persons']
            paths = {}
            for label in ('results.pt','input.npy','official-events.local.json'):
                artifact = folder/(condition+'-'+label)
                paths[label] = dict(path=str(artifact.relative_to(ROOT)),sha256=hashlib.sha256(artifact.read_bytes()).hexdigest())
            backend = model.predictor.model
            architecture = dict(format=backend.format,end2end=bool(backend.end2end),fp16=bool(backend.fp16),
                kpt_shape=list(backend.kpt_shape),stride=int(backend.stride),
                fused=bool(backend.model.is_fused()),done_warmup=bool(model.predictor.done_warmup))
            if architecture['format'] != 'pt' or not architecture['end2end'] or architecture['fp16'] or architecture['kpt_shape'] != [17,3]:
                raise ValueError('official backend architecture differs')
            record = dict(condition_id=condition,view=view,frame_id=frame_id,source_id=item['source_id'],native_pts=item['native_pts'],
                time_base=item['time_base'],pts_seconds=item['pts_seconds'],rgb_sha256=item['rgb_sha256'],
                rgb_bytes_sha256=item['rgb_bytes_sha256'],person_count=len(people),**parsed,
                input_tensor=observer.tensor,official_events=observer.events,official_attempts=observer.attempts,architecture=architecture,
                results_speed_ms=native.speed,public_predict_wall_seconds=predict_wall,
                input_read_convert_verify_seconds=read_seconds,artifacts=paths,
                coordinates='full unchanged; ROI local interpreted before exactly one offset(+537,+216)',visual_quality='unreviewed')
            atomic_json(folder/(condition+'-pose.local.json'),record)
            record['frame_wall_seconds'] = time.perf_counter()-start
            summary['results'].append(record)
            atomic_json(folder/'summary.json',summary)
        summary['comparisons'] = comparison_images(d,summary['results'],folder)
        summary.update(status='succeeded',technical_pass=True)
    except BaseException as exc:
        summary.update(status='failed',error_type=type(exc).__name__,error=str(exc),traceback=traceback.format_exc())
        raise
    finally:
        if monitor:
            monitor.stop()
            summary['device_samples'] = monitor.samples
            summary['device_sample_errors'] = monitor.errors
        if 'torch' in locals() and torch.cuda.is_initialized():
            summary['allocator_peak_allocated_bytes'] = torch.cuda.max_memory_allocated()
            summary['allocator_peak_reserved_bytes'] = torch.cuda.max_memory_reserved()
        summary['run_entry_wall_seconds'] = time.perf_counter()-whole
        summary['timing_scope'] = 'run entry includes lease/input validation; excludes interpreter startup/final summary save; predict wall includes setup/fuse/first warmup/profiler/tensor capture; Results.speed excludes warmup; allocator peak is post-import reset through final frame'
        atomic_json(folder/'summary.json',summary)
    return summary


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--stage',choices=('comparison',),required=True)
    p.add_argument('--attempt',required=True)
    p.add_argument('--lock-fd',type=int,required=True)
    a = p.parse_args()
    run(a.stage,a.attempt,a.lock_fd)


if __name__ == '__main__':
    main()
