# SPDX-License-Identifier: AGPL-3.0-only
"""Frozen FCOS extension; refuses all execution without canonical inherited lease."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import socket
import sqlite3
import sys
import time
import traceback
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from orchestration.mock_job import atomic_json
from orchestration.queue import digest,process_state,source_hash
from orchestration.exp29_cache_command import (ROOT,RUNTIME,LOCAL,CACHE,VIDEO,WEIGHT,MERGED,REPLAY,
    INTERPRETER,SETTINGS,output_path,validate,validate_assignment,execution_guard)
from batch04_pose.runner import resources,DeviceSampler,deny_network


def verify_lease(config, attempt, fd):
    if len(attempt) != 32 or any(c not in '0123456789abcdef' for c in attempt):
        raise ValueError('invalid EXP29 attempt')
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
    if row is None or row['attempt_status'] != 'running' or row['status'] != 'running' or row['command'] != 'exp29-cache007':
        raise ValueError('live EXP29 queue attempt required')
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
    if digest(inputs) != row['input_hash'] or digest(config) != row['config_hash'] or source_hash('exp29-cache007', config) != row['source_hash']:
        raise ValueError('source/input/config queue hashes differ')
    validate(config, inputs, RUNTIME)
    with sqlite3.connect(f'file:{RUNTIME / "queue.sqlite3"}?mode=ro', uri=True) as db:
        execution_guard(db, row, attempt)
    if Path(sys.executable).absolute() != INTERPRETER:
        raise ValueError('fixed original EXP29 interpreter required')
    return dict(row)


def run(stage, attempt, fd):
    begin = time.perf_counter()
    config = dict(stage=stage, settings=SETTINGS)
    job = verify_lease(config, attempt, fd)
    folder = output_path(stage, attempt)
    folder.mkdir(parents=True, exist_ok=False)
    summary = dict(status='preflight', technical_pass=False, attempt_id=attempt,
                   registration={k: job[k] for k in ('job_id','run_id','task_id','dispatch_id',
                                  'code_sha','source_hash','input_hash','config_hash')},
                   new_weights=0, training=0, ground_truth_loaded=False,
                   behavior_accuracy=None, default_applied=False)
    monitor = None
    try:
        if MERGED.exists() or REPLAY.exists():
            raise FileExistsError('Extension outputs already exist; no automatic rerun')
        # All authority, installed bytes and inherited lock checks precede model imports.
        summary['resource_gate'] = resources()
        os.environ.update(HF_HUB_OFFLINE='1', OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2')
        socket.socket.connect = deny_network
        socket.socket.connect_ex = deny_network
        socket.socket.sendto = deny_network
        socket.create_connection = deny_network
        socket.getaddrinfo = deny_network
        import torch
        if not torch.cuda.is_available():
            raise ValueError('CUDA required; no CPU fallback')
        monitor = DeviceSampler()
        monitor.start()
        from sceneguard.run_cv import run as original_run
        extension = folder/'cache'
        args = SimpleNamespace(video=VIDEO, config=LOCAL/'cache007-config.local.json',
            output=extension, detector='fcos800', weights=WEIGHT, device='cuda',
            start=68.0, end=105.0, download_weights=False, cache_person=True, diagnose_fcos=False)
        summary.update(status='running', exact_original_inference_function='sceneguard.run_cv.run')
        atomic_json(folder/'summary.json', summary)
        # Unchanged historical implementation includes the original 10 separate zero warmups.
        original_run(args)
        from exp29_cache.merge import merge_and_replay
        schedule = json.loads((LOCAL/'cache007-native-schedule.local.json').read_text())
        summary['merge'] = merge_and_replay(CACHE, extension, MERGED, REPLAY, schedule)
        # Compare the replayed old prefix to preserved EXP28 before handing it off.
        for condition in ('strict','gap'):
            previous = ROOT/'outputs/exp0028/practical-v1/track007'/condition/'frames.jsonl'
            old = [json.loads(line) for line in previous.read_text().splitlines()]
            current = [json.loads(line) for line in (REPLAY/condition/'frames.jsonl').read_text().splitlines()]
            if len(old) != 600 or current[:600] != old:
                raise ValueError('Continuous replay does not reproduce the preserved 600-frame prefix')
        summary['old_replay_prefix_exact'] = True
        validate(config, json.loads(job['input_json']), RUNTIME)
        summary.update(status='succeeded', technical_pass=True)
    except BaseException as exc:
        summary.update(status='failed', error_type=type(exc).__name__, error=str(exc),
                       traceback=traceback.format_exc())
        raise
    finally:
        if monitor:
            monitor.stop()
            summary['device_samples'] = monitor.samples
            summary['device_sample_errors'] = monitor.errors
        summary['run_entry_wall_seconds'] = time.perf_counter()-begin
        summary['timing_scope'] = 'Wrapper includes inference and CPU merge/replay; original inference timing stays in extension cache/run.json'
        atomic_json(folder/'summary.json', summary)
        atomic_json(LOCAL/('cache007-receipt-'+attempt+'.json'), summary)
    print(json.dumps(dict(status=summary['status'], attempt_id=attempt, merged_frames=1710)))
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage', choices=['extend007'], required=True)
    p.add_argument('--attempt', required=True)
    p.add_argument('--lock-fd', type=int, required=True)
    a = p.parse_args()
    run(a.stage, a.attempt, a.lock_fd)


if __name__ == '__main__':
    main()
