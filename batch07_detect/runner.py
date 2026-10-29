# SPDX-License-Identifier: AGPL-3.0-only
"""Official Detection baseline/train/best evaluation under one verified queue lease."""
import argparse
import fcntl
import gc
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import sys
import time
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from orchestration.mock_job import atomic_json
from orchestration.queue import digest,process_state,source_hash
from orchestration.vlm_command import file_hash
from orchestration.batch07_detect_command import (ROOT,RUNTIME,LOCAL,EVAL,WEIGHT,WEIGHT_SHA,INTERPRETER,
    SETTINGS,TRAIN_KWARGS,PREDICT_KWARGS,IDENTITY,input_contract,output_path,validate,
    validate_assignment,execution_guard,dataset_files)
from batch04_pose.api import bgr_source
from batch04_pose.runner import resources,DeviceSampler,deny_network
from batch07_detect.api import result_rows
from batch07_detect.prepare import TREE,verify_tree
def verify_lease(config, attempt, fd):
    if len(attempt) != 32 or any(c not in '0123456789abcdef' for c in attempt):
        raise ValueError('invalid Detection attempt')
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
    if row is None or row['attempt_status'] != 'running' or row['status'] != 'running' or row['command'] != 'batch07-detect':
        raise ValueError('live Detection queue attempt required')
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
    if digest(inputs) != row['input_hash'] or digest(config) != row['config_hash'] or source_hash('batch07-detect', config) != row['source_hash']:
        raise ValueError('source/input/config queue hashes differ')
    validate(config, inputs, RUNTIME)
    with sqlite3.connect(f'file:{RUNTIME / "queue.sqlite3"}?mode=ro', uri=True) as db:
        execution_guard(db, row, attempt)
    if Path(sys.executable).absolute() != INTERPRETER:
        raise ValueError('fixed isolated Detection interpreter required')
    return dict(row)




def clean(value):
    if isinstance(value,dict):return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean(v) for v in value]
    if isinstance(value,Path):return str(value)
    if isinstance(value,float):return value if math.isfinite(value) else None
    if isinstance(value,(str,int,bool)) or value is None:return value
    if hasattr(value,'item'):return clean(value.item())
    return str(value)


def configure_offline():
    os.environ.update(YOLO_AUTOINSTALL='false',YOLO_OFFLINE='true',ULTRALYTICS_OFFLINE='true',
        YOLO_CONFIG_DIR=str(LOCAL/'ultralytics-settings'),MPLCONFIGDIR=str(LOCAL/'matplotlib'),
        HF_HUB_OFFLINE='1',WANDB_DISABLED='true',NO_ALBUMENTATIONS_UPDATE='1',
        CUBLAS_WORKSPACE_CONFIG=':4096:8')
    os.environ.pop('ULTRALYTICS_API_KEY',None)
    socket.socket.connect=deny_network;socket.socket.connect_ex=deny_network
    socket.socket.sendto=deny_network;socket.create_connection=deny_network;socket.getaddrinfo=deny_network
    from ultralytics.utils import SETTINGS as USETTINGS,USER_CONFIG_DIR
    disabled={k:False for k in ('sync','clearml','comet','dvc','mlflow','raytune','tensorboard','wandb')}
    USETTINGS.update({**disabled,'api_key':'','datasets_dir':str(LOCAL/'datasets'),
        'weights_dir':str(ROOT/'weights'),'runs_dir':str(LOCAL/'runs')})
    # check_det_dataset always asks for Arial. Supply a documented LOCAL system-font alias,
    # never download a font or modify package files; plots remain disabled.
    from matplotlib import font_manager
    config=Path(USER_CONFIG_DIR);config.mkdir(parents=True,exist_ok=True)
    font=Path(font_manager.findfont('DejaVu Sans',fallback_to_default=False))
    target=config/'Arial.ttf'
    if not target.exists():shutil.copyfile(font,target)
    if file_hash(target)!=file_hash(font):raise ValueError('local font alias differs')
    return dict(integrations=disabled,api_key_present=False,network='all socket connect/DNS/UDP denied',
        local_font_alias=dict(source=str(font),target=str(target),sha256=file_hash(target)),
        analytics='sync false before events import',automatic_model_font_downloads=False)


def callback_names(instance):
    return {k:[f.__module__+'.'+f.__qualname__ for f in v] for k,v in instance.callbacks.items()}


class RejectRecovery(logging.Handler):
    """Fail at pinned official warning before pipeline rebuild/checkpoint recovery."""
    def __init__(self,folder):
        super().__init__(logging.WARNING);self.folder=folder

    def emit(self,record):
        text=record.getMessage()
        forbidden=('Reducing to batch=' in text and 'retrying' in text) or (
            ('NaN' in text or 'Inf' in text) and ('recover' in text or 'detected' in text))
        if forbidden:
            atomic_json(self.folder/'recovery-refused.local.json',dict(message=text,wall_utc=time.time()))
            raise RuntimeError('automatic OOM/nonfinite recovery prohibited; preserve error and fixed configuration')


def make_callbacks(folder,summary,torch):
    epoch_start=[None]
    def pretrain(trainer):
        effective=vars(trainer.args)
        for k,v in TRAIN_KWARGS.items():
            # Installed trainer canonicalizes device int0 to string0.
            if k=='device':
                if str(effective[k])!='0':raise ValueError('effective CUDA0 differs')
            elif effective.get(k)!=v:raise ValueError('effective training option differs: '+k)
        if trainer.data.get('test') or trainer.data['nc']!=1 or trainer.data['names']!={0:'person'}:
            raise ValueError('oneclass train/val without test required')
        if trainer.amp or trainer.batch_size!=2:raise ValueError('FP32 batch2 required')
        summary['effective_train_args']=clean(effective)
        summary['training_model']=dict(task=trainer.model.task if hasattr(trainer.model,'task') else 'detect',
            nc=trainer.model.model[-1].nc,names=trainer.model.names,
            fused=trainer.model.is_fused(),parameter_dtypes=sorted({str(p.dtype) for p in trainer.model.parameters()}))
        summary['frozen_parameters']=[n for n,p in trainer.model.named_parameters() if not p.requires_grad]
        summary['trainable_parameters']=[n for n,p in trainer.model.named_parameters() if p.requires_grad]
        opt=trainer.optimizer
        summary['optimizer']=dict(type=type(opt).__name__,defaults=clean(opt.defaults),
            groups=[{k:clean(v) for k,v in g.items() if k!='params'} for g in opt.param_groups],
            accumulate=trainer.accumulate,nominal_batch=trainer.args.nbs,
            note='official nominal-batch accumulation and decay scaling retained; actual groups recorded')
        summary['callbacks']=callback_names(trainer)
        summary['transforms']=str(trainer.train_loader.dataset.transforms)
        summary['head_transfer']='COCO80 to person1; official cls_remap=True matches person by name when supported; some head tensors differ'
        atomic_json(folder/'effective-training.local.json',clean(summary))
    def epoch_begin(trainer):
        epoch_start[0]=time.perf_counter()
        atomic_json(folder/'progress.local.json',dict(stage='training',epoch=trainer.epoch+1,epochs=20,
            completed_epochs=summary.get('epochs_completed',0),wall_utc=time.time()))
    def batch_begin(trainer):
        if trainer.batch_size!=2 or trainer.args.batch!=2:raise ValueError('batch reduction prohibited')
    def epoch_end(trainer):
        if trainer.loss is not None and not bool(trainer.loss.isfinite().all()):
            raise ValueError('nonfinite training loss; no automatic recovery')
    def val_end(validator):
        if validator.args.quantize is not None:raise ValueError('validator must remain FP32')
        if not math.isfinite(float(validator.metrics.fitness)):
            raise ValueError('nonfinite validation fitness; no automatic recovery')
        summary['validator_precision']='FP32; quantize=None; ampFalse'
        summary['validation_calls']=summary.get('validation_calls',0)+1
    def fit_end(trainer):
        # Official final_eval triggers this hook again; preserve one entry per epoch.
        epoch=trainer.epoch+1
        if epoch>trainer.epochs:
            summary['final_best_validation_metrics']=clean(trainer.metrics)
            return
        if epoch<=summary.get('epochs_completed',0):return
        record=dict(epoch=epoch,fitness=clean(trainer.fitness),best_fitness=clean(trainer.best_fitness),
            metrics=clean(trainer.metrics),lr=clean(trainer.lr),
            wall_seconds=time.perf_counter()-epoch_start[0],batch_size=trainer.batch_size,
            loss=clean(trainer.label_loss_items(trainer.tloss)),amp=trainer.amp,
            allocator_peak_allocated_bytes=torch.cuda.max_memory_allocated())
        summary.setdefault('epoch_metrics',[]).append(record);summary['epochs_completed']=epoch
        with (folder/'epoch-progress.local.jsonl').open('a') as stream:stream.write(json.dumps(record)+'\n')
        atomic_json(folder/'progress.local.json',dict(stage='training',completed_epochs=epoch,epochs=20,last=record,wall_utc=time.time()))
        atomic_json(folder/'summary.json',clean(summary))
    return dict(on_pretrain_routine_end=pretrain,on_train_epoch_start=epoch_begin,on_train_batch_start=batch_begin,
        on_train_epoch_end=epoch_end,on_val_end=val_end,on_fit_epoch_end=fit_end)


def predict(model,frames,phase,folder,summary,np,torch):
    from batch07_detect.visuals import draw
    records=[]
    for item in frames:
        frame_id=item['frame_id'];stem=phase+'-'+frame_id
        started=time.perf_counter()
        rgb=np.load(ROOT/item['rgb_path'],allow_pickle=False)
        source=np.load(ROOT/item['crop_path'],allow_pickle=False)
        atomic_json(folder/(stem+'-predict-started.json'),dict(frame_id=frame_id,phase=phase))
        returned=model.predict(source=bgr_source(source),**PREDICT_KWARGS)
        torch.cuda.synchronize()
        if not isinstance(returned,list) or len(returned)!=1:raise ValueError('one native Detection result required')
        result=returned[0]
        torch.save(result.cpu(),folder/(stem+'-results.pt'))
        parsed=result_rows(result,source.shape,item['crop_xyxy'][:2])
        backend=model.predictor.model
        if backend.fp16 or not backend.end2end:raise ValueError('FP32 official NMSfree Detection backend required')
        record=dict(frame_id=frame_id,phase=phase,**parsed,pts_seconds=item['pts_seconds'],native_pts=item['native_pts'],
            time_base=item['time_base'],camera_id=item['camera_id'],crop_xyxy=item['crop_xyxy'],
            source_sha256=item['source_sha256'],rgb_sha256=item['rgb_sha256'],crop_sha256=item['crop_sha256'],
            results_speed_ms=result.speed,wall_seconds=time.perf_counter()-started,
            dtype='float32',fused=backend.model.is_fused(),end2end=bool(backend.end2end),
            native_result=dict(path=str((folder/(stem+'-results.pt')).relative_to(ROOT)),sha256=file_hash(folder/(stem+'-results.pt'))))
        atomic_json(folder/(stem+'-boxes.local.json'),clean(record))
        records.append(record)
        summary[phase]=records
        draw(rgb,record,folder/(stem+'-overlay.png'))
        atomic_json(folder/'summary.json',clean(summary))
        atomic_json(folder/'progress.local.json',dict(stage=phase,frames_completed=len(records),frames_total=len(frames),wall_utc=time.time()))
    return records


def run(stage,attempt,fd):
    whole=time.perf_counter();config=dict(stage=stage,settings=SETTINGS)
    job=verify_lease(config,attempt,fd)
    folder=output_path(stage,attempt);folder.mkdir(parents=True,exist_ok=False)
    summary=dict(status='preflight',technical_pass=False,config=config,attempt_id=attempt,
        registration={k:job[k] for k in ('job_id','run_id','task_id','dispatch_id','code_sha','source_hash','input_hash','config_hash')},
        epochs_completed=0,training_invocations=0,baseline=[],after=[],retry_count=0,
        label_review='pending',D0_passed=False,accuracy=None,precision=None,recall=None,f1=None,
        false_positive_rate=None,behavior='unmeasured',visual_quality='unreviewed',general_person_data_mixed=False,
        forgetting_risk='small climbing-only dataset; no general-person retention guarantee',test17_used=False,
        baseline_head_classes=80,trained_head_classes=1,checkpoint_selection='official fixed valid20 fitness: mAP50-95')
    monitor=None
    try:
        summary['resource_gate']=resources()
        summary['offline']=configure_offline()
        import numpy as np
        import torch
        from ultralytics import YOLO,__version__
        from ultralytics.utils import LOGGER
        recovery_guard=RejectRecovery(folder);LOGGER.addHandler(recovery_guard)
        if __version__!='8.4.192' or torch.__version__!='2.5.1+cu124':raise ValueError('fixed installed environment required')
        if not torch.cuda.is_available():raise ValueError('CUDA required; no CPU fallback')
        torch.set_default_dtype(torch.float32)
        torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.manual_seed(0)
        torch.cuda.reset_peak_memory_stats();monitor=DeviceSampler();monitor.start()
        frames=json.loads(EVAL.read_text())['frames']
        summary.update(status='baseline',device=torch.cuda.get_device_name(0),torch=torch.__version__,ultralytics=__version__,pretrained_sha256=WEIGHT_SHA)
        t=time.perf_counter();baseline_model=YOLO(str(WEIGHT),task='detect')
        if baseline_model.task!='detect' or len(baseline_model.names)!=80 or baseline_model.names[0]!='person':
            raise ValueError('COCO80 Detection model/person0 required; pose forbidden')
        summary['baseline']=predict(baseline_model,frames,'baseline',folder,summary,np,torch)
        summary['baseline_seconds']=time.perf_counter()-t
        del baseline_model;gc.collect();torch.cuda.empty_cache()
        # Prediction fuses its module. Always reload pretrained checkpoint for train.
        model=YOLO(str(WEIGHT),task='detect')
        if model.task!='detect' or model.model.is_fused() or model.predictor is not None:
            raise ValueError('fresh unfused Detection pretrained instance required for train')
        summary['fresh_unfused_train_instance']=True
        for name,callback in make_callbacks(folder,summary,torch).items():model.add_callback(name,callback)
        if list(folder.glob('train*')):raise ValueError('never resume/overwrite training output')
        summary.update(status='training',training_invocations=1)
        atomic_json(folder/'summary.json',clean(summary));t=time.perf_counter()
        model.train(data=str(TREE/'data.yaml'),project=str(folder),name='training',**TRAIN_KWARGS)
        torch.cuda.synchronize();summary['training_seconds']=time.perf_counter()-t
        if summary['epochs_completed']!=20:raise ValueError('bounded run did not complete 20 epochs')
        checkpoints={}
        for name in ('best','last'):
            p=folder/'training/weights'/(name+'.pt')
            if not p.is_file():raise ValueError('required checkpoint missing')
            checkpoints[name]=dict(path=str(p.relative_to(ROOT)),sha256=file_hash(p),bytes=p.stat().st_size)
        summary['checkpoints']=checkpoints
        summary['checkpoint_storage']='official save/strip_optimizer uses FP16 checkpoint tensors; all training and diagnostic compute FP32'
        csv=folder/'training/results.csv'
        if not csv.is_file():raise ValueError('epoch metrics CSV missing')
        summary['epoch_csv']=dict(path=str(csv.relative_to(ROOT)),sha256=file_hash(csv))
        summary['final_training_callbacks']=callback_names(model.trainer)
        del model;gc.collect();torch.cuda.empty_cache()
        t=time.perf_counter();after_model=YOLO(str(ROOT/checkpoints['best']['path']),task='detect')
        if after_model.task!='detect' or after_model.names!={0:'person'}:raise ValueError('oneclass person Detection checkpoint required')
        summary['after']=predict(after_model,frames,'after',folder,summary,np,torch)
        summary['after_seconds']=time.perf_counter()-t
        from batch07_detect.visuals import compare
        summary['comparisons']=compare(frames,summary['baseline'],summary['after'],folder)
        verify_tree()
        if dataset_files()!=json.loads((LOCAL/'dataset-freeze.local.json').read_text()):raise ValueError('historical draft changed')
        summary.update(status='succeeded',technical_pass=True)
    except BaseException as exc:
        summary.update(status='failed',error_type=type(exc).__name__,error=str(exc),traceback=traceback.format_exc())
        raise
    finally:
        if 'recovery_guard' in locals():LOGGER.removeHandler(recovery_guard)
        if monitor:
            monitor.stop();summary['device_samples']=monitor.samples;summary['device_sample_errors']=monitor.errors
        if 'torch' in locals() and torch.cuda.is_initialized():
            summary['allocator_peak_allocated_bytes']=torch.cuda.max_memory_allocated()
            summary['allocator_peak_reserved_bytes']=torch.cuda.max_memory_reserved()
        summary['run_entry_wall_seconds']=time.perf_counter()-whole
        summary['timing_scope']='baseline/after include load, fuse and warmup; train includes setup, validation and final best validation; allocator peak from pre-baseline through after'
        atomic_json(folder/'summary.json',clean(summary))
        atomic_json(folder/'progress.local.json',dict(stage=summary['status'],completed_epochs=summary['epochs_completed'],wall_utc=time.time()))
    return summary


def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=('train_compare',),required=True)
    p.add_argument('--attempt',required=True);p.add_argument('--lock-fd',type=int,required=True)
    a=p.parse_args();run(a.stage,a.attempt,a.lock_fd)


if __name__=='__main__':main()
