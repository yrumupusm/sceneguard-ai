# SPDX-License-Identifier: AGPL-3.0-only
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
from orchestration.batch03_pose_command import (ROOT, RUNTIME, LOCAL, WEIGHT, INTERPRETER,
    SETTINGS, manifest, output_path, validate, validate_assignment, successful_smoke)


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
    if row is None or row['attempt_status'] != 'running' or row['status'] != 'running' or row['command'] != 'batch03-pose':
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
    if digest(inputs) != row['input_hash'] or digest(config) != row['config_hash'] or source_hash('batch03-pose', config) != row['source_hash']:
        raise ValueError('source/input/config queue hashes differ')
    validate(config, inputs, RUNTIME)
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


def pose_rows(boxes, keypoints, width, height):
    """Preserve output row/index; retained confidence means observable estimate, not visual GT."""
    import math
    from orchestration.batch03_pose_command import COCO17
    if len(boxes)!=len(keypoints):raise ValueError('person/keypoint row mismatch')
    persons=[]
    for index,(box,joints) in enumerate(zip(boxes,keypoints)):
        if len(box)!=6 or len(joints)!=17 or any(len(k)!=3 for k in joints):raise ValueError('COCO17 Nx17x3 required')
        if not all(math.isfinite(float(x)) for x in box) or int(box[5])!=0 or box[5]!=0:raise ValueError('finite person class0 required')
        x1,y1,x2,y2,score,_=map(float,box)
        if not (0<=x1<x2<=width and 0<=y1<y2<=height and .25<score<=1):raise ValueError('invalid original person box')
        records=[]
        for joint,(name,values) in enumerate(zip(COCO17,joints)):
            x,y,c=map(float,values)
            if not all(math.isfinite(v) for v in (x,y,c)) or not 0<=c<=1:raise ValueError('nonfinite keypoint/confidence')
            valid=c>=SETTINGS['joint_confidence'] and 0<=x<=width and 0<=y<=height and (x,y)!=(0.,0.)
            records.append(dict(index=joint,name=name,confidence=c,raw_xy=[x,y],
                observed_xy=[x,y] if valid else None,status='retained_estimate' if valid else 'unknown'))
        persons.append(dict(output_index=index,xyxy=[x1,y1,x2,y2],confidence=score,class_id=0,
            keypoints=records,retained_joint_count=sum(r['observed_xy'] is not None for r in records),
            correspondence='unreviewed; output index is not track/person ID'))
    return persons


def architecture(inner):
    head=inner.model[-1]
    return dict(names=inner.names,kpt_shape=list(head.kpt_shape),stride=int(inner.stride.max()),
        end2end=bool(head.end2end),legacy_model_end2end=inner.__dict__.get('end2end'),
        serialized_end2end=head.__dict__.get('_end2end'),one2one_present=getattr(head,'one2one_cv2',None) is not None,
        max_det=head.max_det,export=bool(head.export),fused=False)


def initialize_head(inner):
    # Mirror official v8.4.192 PyTorchBackend override for explicit nms=False before fusion.
    # This selects an existing checkpoint branch; never builds/loads another model or runs a forward.
    inner.end2end=True
    inner.set_head_attr(max_det=300,agnostic_nms=False)
    if not inner.model[-1].end2end:raise ValueError('official one-to-one branch unavailable; no fallback')


def run(stage,attempt,fd):
    from types import SimpleNamespace
    whole=time.perf_counter()
    config=dict(stage=stage,settings=SETTINGS)
    job=verify_lease(config,attempt,fd)
    from orchestration.batch03_pose_command import retry_guard, COCO17
    with sqlite3.connect(f'file:{RUNTIME / "queue.sqlite3"}?mode=ro',uri=True) as db:retry_guard(db,job,for_execution=True)
    correction=None
    if stage=='smoke':
        from orchestration.batch03_pose_command import correction_guard
        correction=correction_guard()
    d=manifest();folder=output_path(stage,attempt);folder.mkdir(parents=True,exist_ok=False)
    summary=dict(status='preflight',config=config,attempt_id=attempt,results=[],technical_pass=False,
        registration={k:job[k] for k in ('job_id','run_id','task_id','dispatch_id','code_sha','source_hash','input_hash','config_hash')},
        correction_binding=correction,warmup_frames=0,forward_count=0,precision=None,recall=None,f1=None,accuracy=None,false_positive_rate=None,
        adoption='adopt_on_hold',visual_review='unknown',rules='not_run; independent human pose/boundary evidence gate required')
    summary['initial_validation_seconds']=time.perf_counter()-whole
    monitor=None
    try:
        summary['resource_gate']=resources()
        os.environ.update(YOLO_AUTOINSTALL='false',YOLO_OFFLINE='true',YOLO_CONFIG_DIR=str(LOCAL/'ultralytics-settings'),
            MPLCONFIGDIR=str(LOCAL/'matplotlib'),HF_HUB_OFFLINE='1',ULTRALYTICS_OFFLINE='true')
        socket.socket.connect=deny_network;socket.socket.connect_ex=deny_network
        import numpy as np
        import torch
        from ultralytics import YOLO
        from ultralytics.data.augment import LetterBox
        from ultralytics.utils.nms import non_max_suppression
        from ultralytics.utils import ops
        if not torch.cuda.is_available():raise ValueError('CUDA required; no fallback')
        torch.set_default_dtype(torch.float32);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
        torch.manual_seed(0);monitor=DeviceSampler();monitor.start();torch.cuda.reset_peak_memory_stats()
        t=time.perf_counter();model=YOLO(str(WEIGHT),task='pose');inner=model.model.float().to('cuda:0').eval();torch.cuda.synchronize()
        summary.update(model_construction_load_seconds=time.perf_counter()-t,device=torch.cuda.get_device_name(0),torch=torch.__version__,cuda=torch.version.cuda,
            load_peak_allocated_bytes=torch.cuda.max_memory_allocated(),load_peak_reserved_bytes=torch.cuda.max_memory_reserved())
        summary['architecture_initial']=architecture(inner)
        initialize_head(inner)
        summary['architecture_selected']=architecture(inner)
        head=inner.model[-1]
        if model.task!='pose' or inner.names!={0:'person'} or list(head.kpt_shape)!=[17,3] or not head.end2end or int(inner.stride.max())!=32:raise ValueError('official pose architecture/end2end differs')
        if {str(p.device) for p in inner.parameters()}!={'cuda:0'} or {p.dtype for p in inner.parameters()}!={torch.float32}:raise ValueError('FP32 CUDA0 model required')
        summary['architecture']=dict(names=inner.names,kpt_shape=list(head.kpt_shape),stride=int(inner.stride.max()),end2end=head.end2end,fused=False)
        transform=LetterBox(new_shape=(640,640),auto=False,scale_fill=False,scaleup=True,center=True,stride=32,padding_value=114)
        if stage=='remaining':summary['smoke_attempt']=successful_smoke()
        selected=json.loads(job['input_json'])['frames'];by_id={r['frame_id']:r for r in d['frames']}
        for frame_id in selected:
            item=by_id[frame_id];start=time.perf_counter();rgb=np.load(ROOT/item['rgb_path'],allow_pickle=False)
            if list(rgb.shape)!=item['rgb_shape'] or hashlib.sha256(rgb.tobytes()).hexdigest()!=item['rgb_bytes_sha256']:raise ValueError('original RGB mismatch')
            read_seconds=time.perf_counter()-start;torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();t=time.perf_counter()
            # Official LetterBox, full frame BGR -> RGB NCHW CUDA FP32 /255. No predictor stream warmup/AutoBackend/fuse/autocheck.
            bgr=np.ascontiguousarray(rgb[:,:,::-1]);padded=transform(image=bgr)
            tensor=torch.from_numpy(padded).unsqueeze(0).to('cuda:0').permute(0,3,1,2).contiguous().flip(1).float().div_(255)
            torch.cuda.synchronize();preprocess_seconds=time.perf_counter()-t
            if list(tensor.shape)!=[1,3,640,640] or tensor.dtype!=torch.float32:raise ValueError('actual input tensor differs')
            actual=tensor.detach().cpu().numpy().copy()
            atomic_json(folder/'inference-started.json',dict(frame_id=frame_id,index=summary['forward_count'],attempt_id=attempt))
            t=time.perf_counter()
            with torch.inference_mode():raw=inner(tensor,augment=False,visualize=False,embed=None)
            torch.cuda.synchronize();inference_seconds=time.perf_counter()-t;summary['forward_count']+=1
            t=time.perf_counter();prediction=raw[0] if isinstance(raw,(list,tuple)) else raw
            if list(prediction.shape)!=[1,300,57] or not torch.isfinite(prediction).all():raise ValueError('expected finite end2end1x300x57')
            raw_array=prediction.detach().cpu().numpy().copy()
            filtered,indices=non_max_suppression(prediction,conf_thres=.25,iou_thres=.7,classes=[0],agnostic=False,max_det=300,nc=1,end2end=True,return_idxs=True)
            pred=filtered[0];input_boxes=pred[:,:6].detach().cpu().numpy().copy();input_joints=pred[:,6:].view(-1,17,3).detach().cpu().numpy().copy()
            boxes=ops.scale_boxes(tensor.shape[2:],pred[:,:4].clone(),rgb.shape)
            joints=ops.scale_coords(tensor.shape[2:],pred[:,6:].reshape(-1,17,3).clone(),rgb.shape)
            full_boxes=torch.cat((boxes,pred[:,4:6]),dim=1).detach().cpu().numpy()
            people=pose_rows(full_boxes.tolist(),joints.detach().cpu().tolist(),rgb.shape[1],rgb.shape[0]);torch.cuda.synchronize();postprocess_seconds=time.perf_counter()-t
            t=time.perf_counter();np.save(folder/(frame_id+'-input.npy'),actual,allow_pickle=False);np.save(folder/(frame_id+'-raw.npy'),raw_array,allow_pickle=False)
            np.savez(folder/(frame_id+'-coordinates.npz'),input_boxes=input_boxes,input_joints=input_joints,original_boxes=full_boxes,original_keypoints=joints.detach().cpu().numpy(),retained_indices=indices[0].detach().cpu().numpy())
            result=dict(frame_id=frame_id,source_id=item['source_id'],native_pts=item['native_pts'],time_base=item['time_base'],pts_seconds=item['pts_seconds'],
                rgb_sha256=item['rgb_sha256'],rgb_bytes_sha256=item['rgb_bytes_sha256'],person_count=len(people),persons=people,coco17=list(COCO17),
                input_tensor=dict(shape=list(actual.shape),dtype=str(actual.dtype),sha256=hashlib.sha256(actual.tobytes()).hexdigest(),path=str((folder/(frame_id+'-input.npy')).relative_to(ROOT))),
                input_read_verify_seconds=read_seconds,preprocess_seconds=preprocess_seconds,inference_seconds=inference_seconds,postprocess_seconds=postprocess_seconds,
                peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved(),
                timing_label='single instrumented forward, no warmup; first stage frame cold; inference wall includes CUDA synchronization; marker IO excluded',
                original_coordinates='official scale_boxes/scale_coords; retained raw confidence, no interpolation',retained_indices=indices[0].detach().cpu().tolist())
            atomic_json(folder/(frame_id+'-pose.local.json'),result)
            result['save_seconds']=time.perf_counter()-t;result['frame_wall_seconds']=time.perf_counter()-start
            summary['results'].append(result);atomic_json(folder/'summary.json',summary)
        summary.update(status='succeeded',technical_pass=True)
    except BaseException as exc:
        summary.update(status='failed',error_type=type(exc).__name__,error=str(exc),traceback=traceback.format_exc());raise
    finally:
        if monitor:
            monitor.stop();summary['device_samples']=monitor.samples;summary['device_sample_errors']=monitor.errors
        summary['run_entry_wall_seconds']=time.perf_counter()-whole
        atomic_json(folder/'summary.json',summary)
    return summary


def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=('smoke','remaining'),required=True);p.add_argument('--attempt',required=True);p.add_argument('--lock-fd',type=int,required=True)
    a=p.parse_args();run(a.stage,a.attempt,a.lock_fd)

if __name__=='__main__':main()
