"""Queue child only: verify canonical inherited lease before existing run_cv."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import socket
import sqlite3
import sys
import time
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from orchestration.video_cards_command import (ROOT,RUNTIME,INTERPRETER,WEIGHT,SETTINGS,
                                              validate,output_path)
from orchestration.queue import digest,process_state,source_hash
from sceneguard.replay_gap_tracking import sha256


def verify_lease(attempt, fd):
    output_path('fcos-cache',attempt)
    inherited,canonical = os.fstat(fd),(RUNTIME/'gpu.lock').stat()
    if (inherited.st_dev,inherited.st_ino)!=(canonical.st_dev,canonical.st_ino):
        raise ValueError('Canonical inherited reservation descriptor required')
    fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    with (RUNTIME/'gpu.lock').open('r') as separate:
        try: fcntl.flock(separate,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: pass
        else: raise ValueError('Canonical reservation is not held')
    row = None
    for _ in range(100):
        with sqlite3.connect(f'file:{RUNTIME/"queue.sqlite3"}?mode=ro',uri=True) as db:
            db.row_factory=sqlite3.Row
            row=db.execute('SELECT j.*,a.status AS attempt_status,a.supervisor_pid,a.supervisor_identity,'
                'a.child_pid,a.child_identity,a.attempt_no FROM jobs j JOIN attempts a USING(job_id) '
                'WHERE a.attempt_id=?',(attempt,)).fetchone()
        if row is None or row['child_pid'] is not None: break
        time.sleep(.01)
    if (row is None or row['command']!='video-cards' or row['status']!='running'
            or row['attempt_status']!='running' or row['attempt_no']!=1
            or row['supervisor_pid']!=os.getppid() or row['child_pid']!=os.getpid()
            or process_state(row['supervisor_pid'],row['supervisor_identity'])!='live'
            or process_state(row['child_pid'],row['child_identity'])!='live'
            or Path(sys.executable).absolute()!=INTERPRETER):
        raise ValueError('Exact live canonical parent/child/attempt/interpreter required')
    config,inputs=json.loads(row['config_json']),json.loads(row['input_json'])
    if (digest(config)!=row['config_hash'] or digest(inputs)!=row['input_hash']
            or source_hash('video-cards',config)!=row['source_hash']
            or subprocess_head()!=row['code_sha']
            or any(config['context'][k]!=row[k] for k in ('run_id','task_id','dispatch_id','owner'))):
        raise ValueError('Queue source/input/settings/commit/assignment differs')
    return dict(row),config,inputs,validate(config,inputs,RUNTIME)


def subprocess_head():
    import subprocess
    return subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()


def run(attempt, fd):
    from orchestration.mock_job import atomic_json
    job,config,inputs,request=verify_lease(attempt,fd)
    folder=output_path('fcos-cache',attempt)
    folder.mkdir(parents=True,exist_ok=False)
    summary=dict(status='preflight',registration={k:job[k] for k in
        ('job_id','run_id','task_id','dispatch_id','code_sha','source_hash','input_hash','config_hash')},
        behavior_accuracy=None,training=0,new_weights=0,automatic_retry=False)
    begin=time.perf_counter()
    try:
        from batch04_pose.runner import resources,deny_network
        summary['resource_gate']=resources()
        os.environ.update(HF_HUB_OFFLINE='1',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
        socket.socket.connect=deny_network; socket.socket.connect_ex=deny_network
        socket.socket.sendto=deny_network; socket.create_connection=deny_network
        socket.getaddrinfo=deny_network
        from sceneguard.video_cards import read,CAMERAS
        camera=read(CAMERAS)['cameras'][request['camera_id']]
        config_path=folder/'boundary-config.json'
        atomic_json(config_path,camera['legacy_boundary_config'])
        args=SimpleNamespace(video=Path(request['video']),config=config_path,output=folder/'cache',
            weights=WEIGHT,detector='fcos800',device='cuda',download_weights=False,
            cache_person=True,diagnose_fcos=False,start=request['requested_window'][0],
            end=request['requested_window'][1])
        atomic_json(folder/'summary.json',summary)
        from sceneguard.run_cv import run as original_run
        original_run(args)
        validate(config,inputs,RUNTIME)
        summary.update(status='succeeded',cache_path=str(folder/'cache'),
                       cache_metadata_sha256=sha256(folder/'cache/run.json'))
    except BaseException as exc:
        summary.update(status='failed',error_type=type(exc).__name__,error=str(exc))
        raise
    finally:
        summary['elapsed_seconds']=time.perf_counter()-begin
        atomic_json(folder/'summary.json',summary)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--attempt',required=True);p.add_argument('--lock-fd',type=int,required=True)
    a=p.parse_args();run(a.attempt,a.lock_fd)
