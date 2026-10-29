# SPDX-License-Identifier: AGPL-3.0-only
"""Official public YOLO.predict child, reachable only through the canonical lease."""
import argparse
import fcntl
import hashlib
import inspect
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import traceback
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from orchestration.mock_job import atomic_json
from orchestration.queue import digest, process_state, source_hash
from orchestration.batch04_pose_command import (ROOT, RUNTIME, LOCAL, WEIGHT, INTERPRETER,
    SETTINGS, PREDICT_KWARGS, manifest, output_path, validate, validate_assignment,
    execution_guard, ensure_unprocessed)
from batch04_pose.api import bgr_source, result_rows


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
    if row is None or row['attempt_status'] != 'running' or row['status'] != 'running' or row['command'] != 'batch04-pose':
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
    if digest(inputs) != row['input_hash'] or digest(config) != row['config_hash'] or source_hash('batch04-pose', config) != row['source_hash']:
        raise ValueError('source/input/config queue hashes differ')
    validate(config, inputs, RUNTIME)
    with sqlite3.connect(f'file:{RUNTIME / "queue.sqlite3"}?mode=ro', uri=True) as db:
        execution_guard(db, row, attempt)
    if Path(sys.executable).absolute() != INTERPRETER:
        raise ValueError('fixed isolated pose interpreter required')
    return dict(row)


def resources():
    raw = subprocess.check_output(['nvidia-smi', '-i', '0', '--query-gpu=memory.used,memory.free',
        '--format=csv,noheader,nounits'], text=True, timeout=5).strip()
    used, free = map(float, raw.split(','))
    if free < 6144:
        raise ValueError(f'free VRAM {free} MiB below unchanged 6144 MiB gate; no model loaded')
    return dict(used_mib=used, free_mib=free)


class DeviceSampler:
    """Device-wide samples are separate from PyTorch allocator peaks."""
    def __init__(self):
        self.samples, self.errors, self.done = [], [], threading.Event()
        self.thread = threading.Thread(target=self.loop, daemon=True)

    def loop(self):
        while not self.done.is_set():
            try:
                raw = subprocess.check_output(['nvidia-smi', '-i', '0',
                    '--query-gpu=memory.used,memory.free,utilization.gpu',
                    '--format=csv,noheader,nounits'], text=True, timeout=5).strip()
                self.samples.append(dict(monotonic=time.monotonic(), values=raw))
            except Exception as exc:
                self.errors.append(repr(exc))
            self.done.wait(.1)

    def start(self):
        self.thread.start()

    def stop(self):
        self.done.set()
        self.thread.join(timeout=6)


def deny_network(*args, **kwargs):
    raise RuntimeError('CV execution is offline; implicit weight/backbone download forbidden')


class ObserveOfficial:
    """Python profiler observer; never substitutes any model/predictor algorithm.

    Stage times include profiler/synchronization overhead. Results.speed is stored
    separately. Actual tensor capture is before warmup; its copy/save overhead is
    recorded separately from preprocess elapsed, but included in predict wall.
    """
    def __init__(self, torch, folder, frame_id, model):
        from ultralytics.engine.predictor import BasePredictor
        from ultralytics.nn.autobackend import AutoBackend
        from ultralytics.nn.tasks import BaseModel
        self.torch, self.folder, self.frame_id, self.model = torch, folder, frame_id, model
        self.codes = {inspect.unwrap(getattr(BasePredictor,n)).__code__: n for n in ('setup_model','preprocess','inference')}
        self.codes[inspect.unwrap(AutoBackend.warmup).__code__] = 'warmup'
        self.codes[inspect.unwrap(BaseModel.predict).__code__] = 'network_predict'
        self.starts, self.events, self.attempts = {}, [], []
        self.tensor = None
        self.warming = False

    def profile(self, frame, event, arg):
        name = self.codes.get(frame.f_code)
        if name is None or event not in ('call', 'return'):
            return
        if event == 'call':
            self.torch.cuda.synchronize()
            if name == 'warmup':
                self.warming = True
            self.attempts.append(dict(stage=name,warmup=self.warming))
            self.starts[id(frame)] = (time.perf_counter(), self.warming)
        else:
            self.torch.cuda.synchronize()
            start, warm = self.starts.pop(id(frame))
            self.events.append(dict(stage=name, seconds=time.perf_counter()-start,
                warmup=warm, returned_value=arg is not None))
            if name == 'warmup':
                self.warming = False
            if name == 'preprocess' and arg is not None:
                t = time.perf_counter()
                actual = arg.detach().cpu().numpy().copy()
                if list(actual.shape) != [1,3,640,640] or str(actual.dtype) != 'float32' or str(arg.device) != 'cuda:0':
                    raise ValueError('actual official preprocess must be CUDA0 FP32 1x3x640x640')
                import numpy as np
                path = self.folder / (self.frame_id+'-input.npy')
                np.save(path, actual, allow_pickle=False)
                self.tensor = dict(shape=list(actual.shape), dtype=str(actual.dtype), device=str(arg.device),
                    sha256=hashlib.sha256(actual.tobytes()).hexdigest(), path=str(path.relative_to(ROOT)),
                    capture_save_seconds=time.perf_counter()-t)

    def __enter__(self):
        self.previous = sys.getprofile()
        if self.previous is not None:
            raise ValueError('existing Python profiler cannot be displaced')
        sys.setprofile(self.profile)
        return self

    def __exit__(self, *args):
        sys.setprofile(self.previous)


def comparison_image(bgr, people, folder, frame_id):
    """Native-size original/overlay pair; no coordinate rescaling or media viewing."""
    import cv2
    import numpy as np
    overlay = bgr.copy()
    edges = ((5,6),(5,7),(7,9),(6,8),(8,10),(5,11),(6,12),(11,12),(11,13),(13,15),(12,14),(14,16))
    for p in people:
        color = ((80+71*p['output_index'])%255, 230, 80)
        a,b,c,d = map(round,p['xyxy'])
        cv2.rectangle(overlay,(a,b),(c,d),color,2)
        cv2.putText(overlay,'row '+str(p['output_index']),(a,max(15,b-5)),cv2.FONT_HERSHEY_SIMPLEX,.5,color,1)
        xy = [k['observed_xy'] for k in p['keypoints']]
        for i,j in edges:
            if xy[i] is not None and xy[j] is not None:
                cv2.line(overlay,tuple(map(round,xy[i])),tuple(map(round,xy[j])),color,2)
        for k in xy:
            if k is not None:
                cv2.circle(overlay,tuple(map(round,k)),3,(0,0,255),-1)
    pair = np.concatenate((bgr,overlay),axis=1)
    banner = np.zeros((40,pair.shape[1],3),dtype=np.uint8)
    cv2.putText(banner,frame_id+' ORIGINAL | POSE estimates conf>=0.5; rows are not person IDs; human review pending',
        (10,27),cv2.FONT_HERSHEY_SIMPLEX,.65,(255,255,255),1)
    paths = {}
    for label, image in [('original',bgr),('overlay',overlay),('comparison',np.concatenate((banner,pair),axis=0))]:
        path = folder / (frame_id+'-'+label+'.png')
        if not cv2.imwrite(str(path),image):
            raise ValueError('local PNG write failed')
        paths[label] = dict(path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    return paths


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
        visual_quality='unreviewed',behavior='unmeasured; no rule/tracker',remaining_gate='coordinator human review required',
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
        model = YOLO(str(WEIGHT),task='pose')
        torch.cuda.synchronize()
        summary.update(model_construction_load_seconds=time.perf_counter()-t,
            device=torch.cuda.get_device_name(0),torch=torch.__version__,cuda=torch.version.cuda)
        if model.task != 'pose' or model.names != {0:'person'}:
            raise ValueError('official pose/person model required')
        by_id = {r['frame_id']:r for r in d['frames']}
        for frame_id in json.loads(job['input_json'])['frames']:
            ensure_unprocessed(frame_id)
            item = by_id[frame_id]; start = time.perf_counter()
            rgb = np.load(ROOT/item['rgb_path'],allow_pickle=False)
            if list(rgb.shape) != item['rgb_shape'] or hashlib.sha256(rgb.tobytes()).hexdigest() != item['rgb_bytes_sha256']:
                raise ValueError('native source RGB mismatch')
            bgr = bgr_source(rgb)
            read_seconds = time.perf_counter()-start
            atomic_json(folder/(frame_id+'-predict-started.json'),dict(frame_id=frame_id,attempt_id=attempt))
            summary['public_predict_calls'] += 1
            t = time.perf_counter()
            observer = ObserveOfficial(torch,folder,frame_id,model)
            try:
                with observer:
                    returned = model.predict(source=bgr,**PREDICT_KWARGS)
            finally:
                # Preserve observed partial timings/counts even on an exception.
                atomic_json(folder/(frame_id+'-official-events.local.json'),dict(attempts=observer.attempts,events=observer.events,tensor=observer.tensor))
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
            torch.save(native.cpu(),folder/(frame_id+'-results.pt'))
            summary['successful_results'] += 1
            people = result_rows(native,rgb.shape)
            paths = comparison_image(bgr,people,folder,frame_id)
            for label in ('results.pt','input.npy','official-events.local.json'):
                artifact = folder/(frame_id+'-'+label)
                paths[label] = dict(path=str(artifact.relative_to(ROOT)),sha256=hashlib.sha256(artifact.read_bytes()).hexdigest())
            backend = model.predictor.model
            architecture = dict(format=backend.format,end2end=bool(backend.end2end),fp16=bool(backend.fp16),
                kpt_shape=list(backend.kpt_shape),stride=int(backend.stride),
                fused=bool(backend.model.is_fused()),done_warmup=bool(model.predictor.done_warmup))
            if architecture['format'] != 'pt' or not architecture['end2end'] or architecture['fp16'] or architecture['kpt_shape'] != [17,3]:
                raise ValueError('official backend architecture differs')
            record = dict(frame_id=frame_id,source_id=item['source_id'],native_pts=item['native_pts'],
                time_base=item['time_base'],pts_seconds=item['pts_seconds'],rgb_sha256=item['rgb_sha256'],
                rgb_bytes_sha256=item['rgb_bytes_sha256'],person_count=len(people),persons=people,
                input_tensor=observer.tensor,official_events=observer.events,official_attempts=observer.attempts,architecture=architecture,
                results_speed_ms=native.speed,public_predict_wall_seconds=predict_wall,
                input_read_convert_verify_seconds=read_seconds,artifacts=paths,
                coordinates='native Results already original-sized; no second scaling',visual_quality='unreviewed')
            atomic_json(folder/(frame_id+'-pose.local.json'),record)
            record['frame_wall_seconds'] = time.perf_counter()-start
            summary['results'].append(record)
            atomic_json(folder/'summary.json',summary)
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
    p.add_argument('--stage',choices=('smoke','remaining'),required=True)
    p.add_argument('--attempt',required=True)
    p.add_argument('--lock-fd',type=int,required=True)
    a = p.parse_args()
    run(a.stage,a.attempt,a.lock_fd)


if __name__ == '__main__':
    main()
