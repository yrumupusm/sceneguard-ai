"""Fixed CUDA-only child; verify queue lease and every hash before torch import."""
import argparse
import fcntl
import hashlib
import importlib.metadata
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
from orchestration.batch02_cv_command import (ROOT, RUNTIME, LOCAL, WEIGHT, INTERPRETER,
    SETTINGS, manifest, output_path, validate, validate_assignment, successful_smoke)


def verify_lease(config, attempt, fd):
    if len(attempt) != 32 or any(c not in '0123456789abcdef' for c in attempt):
        raise ValueError('invalid CV attempt')
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
    if row is None or row['attempt_status'] != 'running' or row['status'] != 'running' or row['command'] != 'batch02-cv':
        raise ValueError('live CV queue attempt required')
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
    if digest(inputs) != row['input_hash'] or digest(config) != row['config_hash'] or source_hash('batch02-cv', config) != row['source_hash']:
        raise ValueError('source/input/config queue hashes differ')
    validate(config, inputs, RUNTIME)
    if Path(sys.executable).absolute() != INTERPRETER:
        raise ValueError('fixed isolated CV interpreter required')
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


def person_rows(detections):
    import math
    names = detections.data.get('class_name')
    if names is None or len(names) != len(detections.class_id):
        raise ValueError('explicit official COCO class-name mapping required')
    result = []
    for box, score, category, name in zip(detections.xyxy, detections.confidence, detections.class_id, names):
        if (int(category) == 1) != (str(name) == 'person'):
            raise ValueError('COCO sparse person ID mapping differs')
        values = [float(v) for v in box]
        if not all(math.isfinite(v) for v in [*values, float(score)]):
            raise ValueError('nonfinite model result')
        if int(category) == 1 and float(score) > .5:
            if values[2] <= values[0] or values[3] <= values[1]:
                raise ValueError('degenerate person box')
            result.append(dict(xyxy=values, score=float(score), class_id=1, class_name='person'))
    return result


def run(stage, attempt, fd):
    config = dict(stage=stage, settings=SETTINGS)
    job = verify_lease(config, attempt, fd)
    d = manifest()
    # At most one explicit retry is useful only before any frame predict began.
    # An interrupted/partial stage never silently repeats a diagnostic frame.
    with sqlite3.connect(f'file:{RUNTIME / "queue.sqlite3"}?mode=ro', uri=True) as db:
        prior = db.execute('SELECT attempt_id FROM attempts WHERE job_id=? AND attempt_id<>?',
                           (job['job_id'], attempt)).fetchall()
    if any((output_path(stage, row[0]) / 'inference-started.json').exists() for row in prior):
        raise ValueError('prior stage prediction began; preserve partial results without repeating frames')
    folder = output_path(stage, attempt)
    folder.mkdir(parents=True, exist_ok=False)
    summary = dict(status='preflight', config=config, attempt_id=attempt,
        registration={k: job[k] for k in ('job_id', 'run_id', 'task_id', 'dispatch_id', 'code_sha',
            'source_hash', 'input_hash', 'config_hash')}, results=[], warmup_frames=0,
        precision=None, recall=None, f1=None, adoption='adopt_on_hold', visual_review='unknown',
        latency_comparison='historical FCOS latency is not a controlled benchmark')
    monitor = None
    try:
        summary['resource_gate'] = resources()
        os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1',
            RF_HOME=str(ROOT / 'weights/rf-detr-medium'), MPLCONFIGDIR=str(LOCAL / 'matplotlib'))
        socket.socket.connect = deny_network
        socket.socket.connect_ex = deny_network
        import torch
        import numpy as np
        from PIL import Image
        from rfdetr import RFDETRMedium
        from rfdetr.detr import _move_model_context_to_device
        from rfdetr.assets.coco_classes import COCO_CLASSES, COCO_CLASS_NAMES
        if COCO_CLASSES[1] != 'person' or COCO_CLASS_NAMES[0] != 'person':
            raise ValueError('official sparse COCO person mapping differs')
        if not torch.cuda.is_available():
            raise ValueError('CUDA required; no CPU fallback')
        torch.set_default_dtype(torch.float32)
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        torch.manual_seed(0)
        monitor = DeviceSampler()
        monitor.start()
        torch.cuda.reset_peak_memory_stats()
        start = time.perf_counter()
        model = RFDETRMedium(pretrain_weights=str(WEIGHT), device='cuda:0', compile=False)
        # Official1.11.2 defers device transfer; include it in load timing without a predict.
        _move_model_context_to_device(model.model)
        torch.cuda.synchronize()
        summary.update(model_construction_load_seconds=time.perf_counter()-start,
            load_peak_allocated_bytes=torch.cuda.max_memory_allocated(),
            load_peak_reserved_bytes=torch.cuda.max_memory_reserved(),
            device=torch.cuda.get_device_name(0), cuda=torch.version.cuda, torch=torch.__version__)
        inner = model.model.model
        if {str(p.device) for p in inner.parameters()} != {'cuda:0'} or {p.dtype for p in inner.parameters()} != {torch.float32}:
            raise ValueError('all model parameters must be CUDA0 FP32')
        if model.model_config.resolution != 576 or model.model_config.num_select != 300 or model.model_config.num_queries != 300:
            raise ValueError('official Medium defaults differ')
        if model._is_optimized_for_inference:
            raise ValueError('eager path required')
        # Observe, hash and save the actual model input without running another inference.
        captured = {}
        def capture(module, args):
            tensor = args[0]
            if tensor.dtype != torch.float32 or str(tensor.device) != 'cuda:0' or list(tensor.shape) != [1, 3, 576, 576]:
                raise ValueError('actual preprocessing tensor differs')
            arr = tensor.detach().cpu().numpy().copy()
            captured.update(shape=list(arr.shape), dtype=str(arr.dtype),
                sha256=hashlib.sha256(arr.tobytes()).hexdigest(), array=arr)
        hook = inner.register_forward_pre_hook(capture)
        if stage == 'remaining':
            summary['smoke_attempt'] = successful_smoke()
        selected = json.loads(job['input_json'])['frames']
        for index, item in enumerate(r for r in d['frames'] if r['frame_id'] in selected):
            rgb = np.load(ROOT / item['rgb_path'], allow_pickle=False)
            if list(rgb.shape) != item['rgb_shape'] or hashlib.sha256(rgb.tobytes()).hexdigest() != item['rgb_bytes_sha256']:
                raise ValueError('full original RGB bytes differ')
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.synchronize()
            start = time.perf_counter()
            atomic_json(folder / 'inference-started.json', dict(frame_id=item['frame_id'], attempt=attempt))
            with torch.inference_mode():
                detections = model.predict(Image.fromarray(rgb), threshold=.5)
            torch.cuda.synchronize()
            elapsed = time.perf_counter()-start
            persons = person_rows(detections)
            record = dict(**item, persons=persons, person_count=len(persons), predict_seconds=elapsed,
                timing_label='cold_first_no_warmup' if index == 0 else 'subsequent_single_pass_no_warmup',
                timing_includes='predict plus actual input tensor CPU copy/hash hook; no repeated inference',
                peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                peak_reserved_bytes=torch.cuda.max_memory_reserved(),
                preprocessed={k: captured[k] for k in ('shape', 'dtype', 'sha256')})
            np.save(folder / (item['frame_id'] + '-preprocessed.npy'), captured['array'], allow_pickle=False)
            atomic_json(folder / (item['frame_id'] + '-raw.json'), dict(
                xyxy=detections.xyxy.tolist(), scores=detections.confidence.tolist(),
                class_ids=detections.class_id.tolist(), class_names=[str(n) for n in detections.data['class_name']]))
            atomic_json(folder / (item['frame_id'] + '.json'), record)
            summary['results'].append(record)
            atomic_json(folder / 'summary.json', summary)
            print(item['frame_id'], len(persons), elapsed, flush=True)
        hook.remove()
        summary['status'] = 'succeeded'
    except Exception as exc:
        summary.update(status='failed', error=repr(exc), traceback=traceback.format_exc())
        raise
    finally:
        if monitor:
            monitor.stop()
            atomic_json(folder / 'device-memory-samples.json', dict(samples=monitor.samples, errors=monitor.errors,
                scope='device-wide sampled values; other GPU processes may contribute; sampling can miss peaks'))
        atomic_json(folder / 'summary.json', summary)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=('smoke', 'remaining'), required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--lock-fd', required=True, type=int)
    args = parser.parse_args()
    run(args.stage, args.attempt, args.lock_fd)
