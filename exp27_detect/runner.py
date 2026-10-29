# SPDX-License-Identifier: AGPL-3.0-only
"""Exactly two Detection checkpoints x seven cached inputs, under canonical lease."""
import argparse
import fcntl
import gc
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
from orchestration.vlm_command import file_hash
from orchestration.exp27_detect_command import (ROOT,RUNTIME,LOCAL,EVAL,INTERPRETER,MODELS,
    SETTINGS,PREDICT_KWARGS,IDENTITY,FRAMES,evaluation,historical_outputs,output_path,
    validate,validate_assignment,execution_guard)
from batch04_pose.api import bgr_source
from batch04_pose.runner import resources,DeviceSampler,deny_network,ObserveOfficial
from exp27_detect.api import result_rows,compare_cached,official_audit

def verify_lease(config, attempt, fd):
    if len(attempt) != 32 or any(c not in '0123456789abcdef' for c in attempt):
        raise ValueError('invalid EXP27 attempt')
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
    if row is None or row['attempt_status'] != 'running' or row['status'] != 'running' or row['command'] != 'exp27-detect':
        raise ValueError('live EXP27 queue attempt required')
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
    if digest(inputs) != row['input_hash'] or digest(config) != row['config_hash'] or source_hash('exp27-detect', config) != row['source_hash']:
        raise ValueError('source/input/config queue hashes differ')
    validate(config, inputs, RUNTIME)
    with sqlite3.connect(f'file:{RUNTIME / "queue.sqlite3"}?mode=ro', uri=True) as db:
        execution_guard(db, row, attempt)
    if Path(sys.executable).absolute() != INTERPRETER:
        raise ValueError('fixed isolated EXP27 interpreter required')
    return dict(row)




def configure_offline():
    """Same audited transport/settings protections, scoped to new EXP27 folders."""
    os.environ.update(YOLO_AUTOINSTALL='false',YOLO_OFFLINE='true',ULTRALYTICS_OFFLINE='true',
        YOLO_CONFIG_DIR=str(LOCAL/'ultralytics-settings'),MPLCONFIGDIR=str(LOCAL/'matplotlib'),
        HF_HUB_OFFLINE='1',WANDB_DISABLED='true',NO_ALBUMENTATIONS_UPDATE='1',
        CUBLAS_WORKSPACE_CONFIG=':4096:8')
    os.environ.pop('ULTRALYTICS_API_KEY',None)
    socket.socket.connect=deny_network;socket.socket.connect_ex=deny_network
    socket.socket.sendto=deny_network;socket.create_connection=deny_network;socket.getaddrinfo=deny_network
    from ultralytics.utils import SETTINGS as USETTINGS
    disabled={k:False for k in ('sync','clearml','comet','dvc','mlflow','raytune','tensorboard','wandb')}
    USETTINGS.update({**disabled,'api_key':'','datasets_dir':str(LOCAL/'datasets'),
        'weights_dir':str(ROOT/'weights'),'runs_dir':str(LOCAL/'runs')})
    return dict(integrations=disabled,api_key_present=False,network='all socket connect/DNS/UDP denied',
        analytics='sync false before events import',automatic_model_font_downloads=False)


def start_marker(folder,stem,attempt):
    """Durable exclusive markers survive failure; no sample ever runs twice."""
    base=ROOT/'outputs/exp0027/EXP-0027'
    if list(base.glob('**/'+stem+'-predict-started.json')):
        raise ValueError('sample already started in this or another EXP27 attempt')
    path=folder/(stem+'-predict-started.json')
    with path.open('x') as stream:
        json.dump(dict(stem=stem,attempt_id=attempt,wall_utc=time.time()),stream)
        stream.flush();os.fsync(stream.fileno())
    fd=os.open(folder,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def observer_counts(observer):
    return dict(warmup_model_forward_attempts=sum(a['stage']=='network_predict' and a['warmup'] for a in observer.attempts),
        sample_model_forward_attempts=sum(a['stage']=='network_predict' and not a['warmup'] for a in observer.attempts),
        warmup_model_forward_count=sum(a['stage']=='network_predict' and a['warmup'] and a['returned_value'] for a in observer.events),
        sample_model_forward_count=sum(a['stage']=='network_predict' and not a['warmup'] and a['returned_value'] for a in observer.events))


def predict(model,frames,phase,folder,summary,np,torch,old,attempt):
    records=[]
    for item,cached in zip(frames,old[MODELS[phase]['cached_phase']]):
        fid=item['frame_id'];stem=phase+'-'+fid
        source=np.load(ROOT/item['crop_path'],allow_pickle=False)
        start_marker(folder,stem,attempt)
        summary['public_predict_calls']+=1
        atomic_json(folder/'summary.json',summary)
        observer=ObserveOfficial(torch,folder,stem,model);t=time.perf_counter()
        try:
            with observer:
                returned=model.predict(source=bgr_source(source),**PREDICT_KWARGS)
            torch.cuda.synchronize()
        finally:
            counts=observer_counts(observer)
            for k,v in counts.items():summary[k]+=v
            atomic_json(folder/(stem+'-official-events.local.json'),dict(attempts=observer.attempts,events=observer.events,tensor=observer.tensor,counts=counts))
            atomic_json(folder/'summary.json',summary)
        if not isinstance(returned,list) or len(returned)!=1:raise ValueError('one native Detection result required')
        result=returned[0];native=folder/(stem+'-results.pt')
        if native.exists():raise ValueError('never overwrite native Results')
        torch.save(result.cpu(),native)
        parsed=result_rows(result,source.shape,item['crop_xyxy'][:2])
        backend=model.predictor.model;head=backend.model.model[-1]
        if backend.fp16 or not backend.end2end or head.nc!=MODELS[phase]['nc'] or head.max_det!=300 or head.agnostic_nms:
            raise ValueError('fixed FP32 end2end head/nc/max_det/agnostic configuration required')
        for k,v in PREDICT_KWARGS.items():
            if k=='stream':continue
            actual=getattr(model.predictor.args,k)
            if (str(actual)!=str(v) if k=='device' else actual!=v):raise ValueError('effective predict setting differs: '+k)
        # Only load frozen historical native Results on CPU; never call its model.
        ref=cached['native_result']
        if file_hash(ROOT/ref['path'])!=ref['sha256']:raise ValueError('historical native Results hash differs')
        historical=torch.load(ROOT/ref['path'],map_location='cpu',weights_only=False)
        old_parsed=result_rows(historical,source.shape,item['crop_xyxy'][:2],minimum=.25)
        if old_parsed['local_persons']!=cached['local_persons'] or old_parsed['persons']!=cached['persons']:
            raise ValueError('historical summary/raw Results disagree')
        record=dict(frame_id=fid,phase=phase,**parsed,pts_seconds=item['pts_seconds'],native_pts=item['native_pts'],
            time_base=item['time_base'],camera_id=item['camera_id'],crop_xyxy=item['crop_xyxy'],
            source_sha256=item['source_sha256'],rgb_sha256=item['rgb_sha256'],crop_sha256=item['crop_sha256'],
            model_sha256=MODELS[phase]['sha256'],head_nc=head.nc,head_max_det=head.max_det,
            dtype='float32',end2end=True,fused=backend.model.is_fused(),
            effective_predict_kwargs={k:getattr(model.predictor.args,k) for k in PREDICT_KWARGS if k!='stream'},
            native_result=dict(path=str(native.relative_to(ROOT)),sha256=file_hash(native)),
            historical_native_result=ref,cached_comparison=compare_cached(parsed['local_persons'],old_parsed['local_persons']),
            official_observation=dict(counts=counts,tensor=observer.tensor),
            results_speed_ms=result.speed,wall_seconds=time.perf_counter()-t)
        atomic_json(folder/(stem+'-boxes.local.json'),record);records.append(record)
        summary[phase]=records;summary['successful_results']+=1
        atomic_json(folder/'summary.json',summary)
        atomic_json(folder/'progress.local.json',dict(stage=phase,frames_completed=len(records),frames_total=7,public_predict_calls=summary['public_predict_calls'],wall_utc=time.time()))
    return records


def run(stage,attempt,fd):
    whole=time.perf_counter();config=dict(stage=stage,settings=SETTINGS)
    job=verify_lease(config,attempt,fd)
    folder=output_path(stage,attempt);folder.mkdir(parents=True,exist_ok=False)
    summary=dict(status='preflight',technical_pass=False,config=config,attempt_id=attempt,
        registration={k:job[k] for k in ('job_id','run_id','task_id','dispatch_id','code_sha','source_hash','input_hash','config_hash')},
        public_predict_calls=0,successful_results=0,model_loads=0,retry_count=0,
        warmup_model_forward_attempts=0,sample_model_forward_attempts=0,warmup_model_forward_count=0,sample_model_forward_count=0,
        pretrained=[],fine_tuned=[],models=MODELS,accuracy=None,recall=None,precision=None,f1=None,
        behavior='unmeasured',visual_quality='unreviewed',default_applied=False,label_review='pending',D0_passed=False)
    monitor=None
    try:
        # All lease/source/input/model/auth gates above, plus VRAM gate before imports.
        summary['resource_gate']=resources()
        summary['offline']=configure_offline()
        import numpy as np
        import torch
        from ultralytics import YOLO,__version__
        if __version__!='8.4.192' or torch.__version__!='2.5.1+cu124':raise ValueError('fixed installed environment required')
        if not torch.cuda.is_available():raise ValueError('CUDA required; no CPU fallback')
        summary['installed_audit']=official_audit()
        torch.set_default_dtype(torch.float32)
        torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.manual_seed(0)
        torch.cuda.reset_peak_memory_stats();monitor=DeviceSampler();monitor.start()
        frames=evaluation()['frames'];old=historical_outputs()
        summary.update(status='running',device=torch.cuda.get_device_name(0),torch=torch.__version__,ultralytics=__version__)
        for phase,spec in MODELS.items():
            summary['resource_gate_'+phase]=resources()
            t=time.perf_counter();model=YOLO(str(ROOT/spec['path']),task='detect');summary['model_loads']+=1
            if model.task!='detect' or len(model.names)!=spec['nc'] or model.names[0]!='person':
                raise ValueError('exact Detection model/head/person0 required')
            summary[phase+'_model_load_seconds']=time.perf_counter()-t
            t=time.perf_counter();summary[phase]=predict(model,frames,phase,folder,summary,np,torch,old,attempt)
            summary[phase+'_seconds']=time.perf_counter()-t
            del model;gc.collect();torch.cuda.empty_cache()
        from exp27_detect.visuals import triptych
        summary['comparisons']={}
        for i,item in enumerate(frames):
            rgb=np.load(ROOT/item['rgb_path'],allow_pickle=False)
            summary['comparisons'][item['frame_id']]=triptych(rgb,summary['pretrained'][i],summary['fine_tuned'][i],folder,item['frame_id'])
        if summary['public_predict_calls']!=14 or summary['sample_model_forward_count']!=14 or summary['sample_model_forward_attempts']!=14:
            raise ValueError('exact fourteen sample calls/forwards required')
        if summary['warmup_model_forward_count']!=2 or summary['warmup_model_forward_attempts']!=2:
            raise ValueError('exact two separately counted official warmup forwards required')
        validate(config,json.loads(job['input_json']),RUNTIME)  # Revalidate preserved inputs/cache/environment.
        summary.update(status='succeeded',technical_pass=True)
    except Exception as exc:
        summary.update(status='failed',error=repr(exc),traceback=traceback.format_exc())
        raise
    finally:
        if monitor:
            monitor.stop();summary['device_samples']=monitor.samples;summary['device_sample_errors']=monitor.errors
            summary['allocator_peak_allocated_bytes']=torch.cuda.max_memory_allocated()
            summary['allocator_peak_reserved_bytes']=torch.cuda.max_memory_reserved()
        summary['run_entry_wall_seconds']=time.perf_counter()-whole
        summary['timing_scope']='predict wall includes profiler, sync, Results CPU copy and cached comparisons; load/setup/warmup and Results.speed differ; device samples separate from allocator peaks'
        atomic_json(folder/'summary.json',summary)
        print(json.dumps(dict(status=summary['status'],public_predict_calls=summary['public_predict_calls'],output=str(folder))))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--stage',choices=('diagnose',),required=True)
    p.add_argument('--attempt',required=True);p.add_argument('--lock-fd',type=int,required=True)
    a=p.parse_args();run(a.stage,a.attempt,a.lock_fd)


if __name__=='__main__':main()
