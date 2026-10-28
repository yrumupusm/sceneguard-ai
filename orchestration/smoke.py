"""Explicit CPU-only acceptance smoke using one canonical queue across worktrees."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
from orchestration.queue import Queue, process_state
from orchestration.lab import run as service


def restart_smoke(config_path, tag, task_id):
    config = json.loads(config_path.read_text())
    runtime = Path(config['runtime_dir'])
    output = runtime / f'{tag}-service-smoke.json'
    if output.exists():
        raise FileExistsError('Preserve existing test result; use a new tag')
    queue = Queue(runtime / 'gpu-queue')
    result = {'passed': False, 'synthetic': True, 'state': 'inconclusive'}
    process = None

    def live_services():
        observed = service(config_path, 'status')
        if not all(observed.get('services', {}).get(name, {}).get('identity_matches') is True
                   for name in ('web', 'projection')):
            raise RuntimeError('Both owned services must be live for this check')
        return observed

    def inflight(job_id):
        attempt = next((a for a in queue.status()['attempts'] if a['job_id'] == job_id), None)
        if not attempt or attempt['status'] != 'running' or not attempt.get('child_pid'):
            raise RuntimeError('Exact mock attempt is not running; overlap not exercised')
        if process_state(attempt['child_pid'], attempt.get('child_identity')) != 'live':
            raise RuntimeError('Exact mock child liveness is not proven')
        return attempt

    try:
        state = queue.status()
        if any(j['status'] in ('queued', 'running', 'unknown') for j in state['jobs']):
            raise RuntimeError('Queue must be idle before this acceptance check')
        if any(j['job_key'] == f'{tag}-web-independence' for j in state['jobs']):
            raise RuntimeError('Tag was used by an earlier attempt; inspect it and choose a new tag')
        result['services_before'] = live_services()
        job = queue.enqueue(job_key=f'{tag}-web-independence', run_id=config['orca_run_id'],
                            task_id=task_id, dispatch_id='TEST-coordinator-local-validation',
                            owner='coordinator_CPU_smoke', config={'seconds': 2.0, 'exit_code': 0}, timeout=6)
        process = subprocess.Popen([sys.executable, '-m', 'orchestration.queue', '--runtime', str(queue.runtime), 'run-once'],
                                   cwd=config['repo_root'], stdout=subprocess.PIPE, text=True)
        for _ in range(100):
            attempt = next((a for a in queue.status()['attempts'] if a['job_id'] == job['job_id'] and a['child_pid']), None)
            if attempt:
                break
            time.sleep(.03)
        else:
            raise RuntimeError('Mock did not start; inspect queue without automatic retry')
        result['services_at_stop'] = live_services()
        before = inflight(job['job_id'])
        result['attempt_at_stop'] = before
        result['web_stop_at'] = time.time()
        result['stop'] = service(config_path, 'stop')
        result['web_stopped_at'] = time.time()
        after = inflight(job['job_id'])
        if after['attempt_id'] != before['attempt_id']:
            raise RuntimeError('Attempt changed across stop')
        result['attempt_after_stop'] = after
        process.communicate(timeout=10)
        attempt = next(a for a in queue.status()['attempts'] if a['attempt_id'] == before['attempt_id'])
        result['queue_status_after_web_stop'] = attempt['status']
        result['job_finished_at'] = attempt['finished_at']
        child = json.loads((queue.runtime / 'attempts' / attempt['attempt_id'] / 'mock-result.json').read_text())
        result['child_finished_at'] = child['finished_at']
        if not (attempt['status'] == 'succeeded' and child['pid'] == before['child_pid']
                and child['started_at'] <= result['web_stop_at'] < result['web_stopped_at']
                < child['finished_at'] <= attempt['finished_at']):
            raise RuntimeError('Completion did not prove overlap with the entire web stop')
        restarted = service(config_path, 'start')
        result['restart'] = restarted
        if restarted.get('state') != 'started' or restarted.get('projection_state') != 'connected':
            raise RuntimeError('Restart degraded; connected-service acceptance not established')
        before_count = len(queue.status()['attempts'])
        for _ in range(3):
            with urllib.request.urlopen(restarted['url'] + '/api/catalog', timeout=3) as response:
                if response.status != 200:
                    raise RuntimeError('Catalog unavailable after restart')
        if len(queue.status()['attempts']) != before_count:
            raise RuntimeError('Read-only requests coincided with additional attempts')
        result.update(passed=True, state='passed', reads_added_attempts=0)
        return result
    except Exception as error:
        result['error'] = str(error)
        result['recovery'] = 'Inspect queue and service status; no automatic replay. If stopped, start services explicitly.'
        raise
    finally:
        # The registered workload is bounded. Reap only our caller, without
        # killing or replaying a possibly independent supervisor/child.
        if process is not None and process.poll() is None:
            try:
                process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                result['caller_cleanup'] = 'still live; inspect exact process, no blind kill'
        output.write_text(json.dumps(result, indent=2), encoding='utf-8')


def smoke(config_path, other_worktree, tag, task_id):
    config = json.loads(config_path.read_text())
    runtime = Path(config['runtime_dir'])
    output = runtime / f'{tag}-queue-smoke.json'
    if output.exists():
        raise FileExistsError('Preserve prior smoke result; choose a new explicit tag')
    queue = Queue.initialize(runtime / 'gpu-queue')
    if any(j['status'] in ('queued', 'running', 'unknown') for j in queue.status()['jobs']):
        raise RuntimeError('Queue must be idle before controlled smoke')
    contract = dict(run_id=config['orca_run_id'], task_id=task_id,
                    dispatch_id='TEST-coordinator-local-validation', owner='coordinator_CPU_smoke')
    jobs = [queue.enqueue(job_key=f'{tag}-{name}', config={'seconds': seconds, 'exit_code': code},
                          timeout=5, **contract)
            for name, seconds, code in [('a', .3, 0), ('b', .25, 0), ('failure', .1, 7), ('after', .1, 0)]]
    argv = [sys.executable, '-m', 'orchestration.queue', '--runtime', str(queue.runtime), 'run-once']
    processes = [subprocess.Popen(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                 for cwd in [Path(config['repo_root']), other_worktree]]
    receipts = []
    for process in processes:
        stdout, stderr = process.communicate(timeout=20)
        if process.returncode:
            raise RuntimeError(stderr)
        receipts.append(json.loads(stdout))
    # Intentional workload failure is followed by another job under the same lock.
    for _ in range(2):
        receipts.append(json.loads(subprocess.check_output(argv, cwd=config['repo_root'], text=True)))
    state = queue.status()
    selected = [x for x in state['attempts'] if x['job_id'] in {j['job_id'] for j in jobs}]
    intervals = []
    for attempt in selected:
        result = json.loads((queue.runtime / 'attempts' / attempt['attempt_id'] / 'mock-result.json').read_text())
        intervals.append({'start': result['started_at'], 'end': result['finished_at'],
                          'status': attempt['status'], 'exit_code': attempt['exit_code']})
    intervals.sort(key=lambda x: x['start'])
    assert len(intervals) == 4
    assert all(a['end'] <= b['start'] for a, b in zip(intervals, intervals[1:]))
    assert [x['status'] for x in intervals] == ['succeeded', 'succeeded', 'failed', 'succeeded']
    before = len(state['attempts'])
    subprocess.check_output(argv, cwd=other_worktree, text=True)
    assert len(queue.status()['attempts']) == before
    assert queue.enqueue(job_key=f'{tag}-a', config={'seconds': .3, 'exit_code': 0}, timeout=5, **contract)['job_id'] == jobs[0]['job_id']
    result = {'synthetic': True, 'gpu_or_model_execution': False, 'passed': True,
              'same_queue_from_two_worktrees': True, 'overlap_count': 0,
              'failure_then_success': True, 'restart_duplicate_attempts': 0,
              'intervals': intervals, 'supervisor_receipts': receipts, 'recovery': queue.recover()}
    output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--other-worktree', type=Path, required=True)
    p.add_argument('--tag', required=True)
    p.add_argument('--task-id', required=True)
    p.add_argument('--action', choices=['queue', 'web-restart'], default='queue')
    a = p.parse_args()
    if not a.tag.replace('-', '').replace('_', '').isalnum():
        p.error('tag must contain letters, digits, hyphen or underscore only')
    result = smoke(a.config, a.other_worktree, a.tag, a.task_id) if a.action == 'queue' else restart_smoke(a.config, a.tag, a.task_id)
    print(json.dumps(result, indent=2))
