"""Offline MVP queue child: no GPU model construction without a live lease."""
import argparse
import fcntl
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import traceback

# Queue invokes this fixed script under -I; add only this trusted checkout.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from orchestration.mock_job import atomic_json
from orchestration.queue import digest, process_state, source_hash
from orchestration.mvp_command import (ASSETS, ROOT, RUNTIME, MODEL_DIR, SETTINGS,
                                       PHASES, load_configs, load_regression_manifest,
                                       output_path, validate, validate_run, settings_for_phase)


def verify_lease(config, attempt, lock_fd):
    """Prove canonical lock ownership and exact live parent before torch import."""
    if not isinstance(attempt, str) or len(attempt) != 32 or any(c not in '0123456789abcdef' for c in attempt):
        raise ValueError('invalid MVP queue attempt')
    inherited, canonical = os.fstat(lock_fd), (RUNTIME / 'gpu.lock').stat()
    if (inherited.st_dev, inherited.st_ino) != (canonical.st_dev, canonical.st_ino):
        raise ValueError('canonical inherited queue lock required')
    # An unrelated open descriptor to the same locked inode is not a lease.
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        raise ValueError('descriptor does not own inherited reservation') from exc
    with (RUNTIME / 'gpu.lock').open('r') as other:
        try:
            fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            pass
        else:
            raise ValueError('canonical reservation is not held')
    with sqlite3.connect(f'file:{RUNTIME / "queue.sqlite3"}?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        query = ('SELECT a.status AS attempt_status,a.supervisor_pid,a.supervisor_identity,'
                         'a.child_pid,a.child_identity,j.* FROM attempts a JOIN jobs j USING(job_id) '
                         'WHERE a.attempt_id=?')
        row = db.execute(query, (attempt,)).fetchone()
        if config['phase'] == 'appearance-8b':
            # Popen returns before the supervisor can persist its exact child PID.
            for _ in range(100):
                if row is None or row['child_pid'] is not None:
                    break
                time.sleep(.01)
                row = db.execute(query, (attempt,)).fetchone()
    if row is None or row['attempt_status'] != 'running' or row['status'] != 'running' or row['command'] != 'mvp-0001':
        raise ValueError('live MVP queue attempt required')
    if row['supervisor_pid'] != os.getppid() or process_state(row['supervisor_pid'], row['supervisor_identity']) != 'live':
        raise ValueError('live exact queue supervisor must be the parent')
    if row['child_pid'] is not None and (row['child_pid'] != os.getpid() or process_state(
            row['child_pid'], row['child_identity']) != 'live'):
        raise ValueError('attempt child identity differs')
    if json.loads(row['config_json']) != config:
        raise ValueError('MVP phase/view/settings differ from live queue attempt')
    if config['phase'] == 'appearance-compare':
        from mvp.exp0034_appearance import IDENTITY
        if tuple(row[k] for k in ('run_id','task_id','dispatch_id')) != IDENTITY:
            raise ValueError('EXP-0034 requires its exact current Run/Task/Dispatch')
        # Check actual Orca authority, rather than trusting a copied local row.
        snapshot=json.loads(subprocess.check_output(['orca-ide','orchestration','worker-list',
            '--run',IDENTITY[0],'--json'],text=True,timeout=25))
        matches=[w for w in snapshot.get('result',{}).get('workers',[])
                 if w.get('taskId')==IDENTITY[1] and w.get('dispatchId')==IDENTITY[2]
                 and w.get('dispatchStatus')=='dispatched'
                 and w.get('projection',{}).get('liveness',{}).get('verdict')=='live']
        if not snapshot.get('ok') or len(matches)!=1:
            raise ValueError('EXP-0034 current native dispatch must be live')
        with sqlite3.connect(f'file:{RUNTIME / "queue.sqlite3"}?mode=ro', uri=True) as db:
            previous=db.execute("SELECT j.job_id,a.attempt_id,j.config_json FROM jobs j "
                "LEFT JOIN attempts a USING(job_id) WHERE j.command='mvp-0001'").fetchall()
        appearance=[r for r in previous if json.loads(r[2]).get('phase')=='appearance-compare']
        if len(appearance)!=1 or appearance[0][0]!=row['job_id'] or appearance[0][1]!=attempt:
            raise ValueError('Only one EXP-0034 job/attempt; automatic retry forbidden')
    if config['phase'] == 'appearance-8b':
        from mvp.exp0038 import verify_live_dispatch
        if row['child_pid'] != os.getpid():
            raise ValueError('EXP-0038 exact child receipt required')
        with sqlite3.connect(f'file:{RUNTIME / "queue.sqlite3"}?mode=ro', uri=True) as db:
            previous = db.execute("SELECT j.job_id,a.attempt_id,j.config_json FROM jobs j "
                "LEFT JOIN attempts a USING(job_id) WHERE j.command='mvp-0001'").fetchall()
        verify_live_dispatch(dict(row), attempt, previous)
    else:
        validate_run(config['phase'], row['run_id'])
    return dict(row)


def verify_environment_lease():
    try:
        config = json.loads(os.environ['SCENEGUARD_MVP_CONFIG'])
        attempt, lock_fd = os.environ['SCENEGUARD_MVP_ATTEMPT'], int(os.environ['SCENEGUARD_MVP_LOCK_FD'])
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError('inherited MVP queue environment required before model load') from exc
    return verify_lease(config, attempt, lock_fd)


def check_resources(settings):
    raw = subprocess.check_output(['nvidia-smi', '-i', '0', '--query-gpu=memory.used,memory.free',
                                   '--format=csv,noheader,nounits'], text=True, timeout=5).strip()
    used, free = map(float, raw.split(','))
    if free < settings['minimum_gpu_free_mib']:
        raise ValueError(f'GPU resource gate: free {free} MiB below frozen minimum; no model loaded')
    return {'used_mib': used, 'free_mib': free}


def development_source(cached, rgb):
    pts = [r['pts'] for r in cached['frames']]
    return dict(fps=cached['fps'], pts_seconds=pts,
                native_pts=[r['native_pts'] for r in cached['frames']],
                time_base=cached['frames'][0]['time_base'], relative_indices=list(cached['relative_indices']),
                source_size=[rgb.shape[2], rgb.shape[1]], window_start=pts[0], window_end=pts[0]+5.0,
                last_decoded_pts=pts[-1])


def run_development(analyzer, folder, sources, cameras, inputs):
    import numpy as np
    from mvp.compare import reuse_development
    from vlm_batch.run import save_frames
    results = []
    analyzer.artifact_root = folder
    for item in sources['development_clips']:
        analyzer.last_generated_token_ids = []
        analyzer.last_processor_frames = None
        analyzer.last_expanded_prompt = None
        clip = item['clip_id']
        target = folder / clip
        target.mkdir()
        rgb = np.load(ASSETS / item['cache_dir'] / 'rgb.npy', allow_pickle=False)
        cached = json.loads((ASSETS / item['cache_dir'] / 'input.json').read_text())
        source = development_source(cached, rgb)
        roi = cameras['cameras'][item['camera_id']]['roi']
        atomic_json(target / 'input.json', {**source, 'roi': roi, 'camera_id': item['camera_id'],
                                          'source_sha256': cached['source_sha256']})
        try:
            record = (reuse_development(analyzer, rgb, source, clip, roi, inputs['model_files'])
                      if clip == 'clip05' else analyzer.analyze(rgb, source, clip, roi))
            record.update(status='reused' if record.get('reused') else 'generated', clip_id=clip)
            save_frames(target, analyzer.last_processor_frames, cached, clip)
            (target / 'expanded_prompt.txt').write_text(analyzer.last_expanded_prompt, encoding='utf-8')
            np.save(target / 'generated_token_ids.npy', np.array(analyzer.last_generated_token_ids, dtype='int64'))
            (target / 'raw_response.txt').write_text(record['raw_response'], encoding='utf-8')
            atomic_json(target / 'result.json', record)
            results.append({'clip_id': clip, 'status': record['status'], 'timing': record['timing']})
            print(clip, record['status'], flush=True)
        except Exception as exc:
            if getattr(analyzer, 'last_generated_token_ids', None):
                np.save(target / 'generated_token_ids.npy', np.array(analyzer.last_generated_token_ids, dtype='int64'))
            atomic_json(target / 'failure.json', {'status': 'failed', 'error': repr(exc),
                                                  'traceback': traceback.format_exc()})
            raise
    return results


def find_full_baseline(inputs, run_id):
    from mvp.compare import successful_baseline
    with sqlite3.connect(f'file:{RUNTIME / "queue.sqlite3"}?mode=ro', uri=True) as db:
        rows = db.execute("SELECT a.attempt_id,j.input_json,j.source_hash FROM attempts a JOIN jobs j USING(job_id) "
                          "WHERE a.status='succeeded' AND j.command='mvp-0001' AND j.run_id=? "
                          "ORDER BY a.finished_at DESC", (run_id,)).fetchall()
    for attempt, input_json, stored_source in rows:
        if json.loads(input_json) != inputs or stored_source != source_hash('mvp-0001'):
            continue
        try:
            successful_baseline(attempt, 'full', 'full_frame')
        except ValueError:
            continue
        folder = output_path('full', attempt)
        summary = json.loads((folder / 'summary.json').read_text())
        if summary.get('status') == 'succeeded':
            return attempt, folder
    raise ValueError('no successful exact full-frame baseline for C4 fallback reuse')


def run_full(analyzer, folder, sources, cameras, pipeline_settings, config, inputs, context):
    from mvp.pipeline import run_video
    from mvp.compare import ExactReuseAnalyzer, FingerprintedAnalyzer, read_baseline_results
    baseline = find_full_baseline(inputs, context['run_id']) if config['view'] == 'fixed_roi' else None
    baseline_records = {}
    if baseline:
        attempt, previous = baseline
        for item in sources['continuous_sources']:
            if cameras['cameras'][item['camera_id']]['roi'] != [0, 0, 1, 1]:
                continue
            source_dir = previous / item['source_id']
            if json.loads((source_dir / 'summary.json').read_text()).get('status') != 'succeeded':
                raise ValueError('source baseline did not complete successfully')
            baseline_records[item['source_id']] = read_baseline_results(source_dir)
        atomic_json(folder / 'reuse_manifest.json', {'baseline_attempt': attempt,
            'baseline_summary_sha256': hashlib.sha256((previous / 'summary.json').read_bytes()).hexdigest(),
            'sources': {source_id: {window: record['_reuse_binding'] for window, record in records.items()}
                        for source_id, records in baseline_records.items()}})
    results = []
    for item in sources['continuous_sources']:
        analyzer.artifact_root = folder / item['source_id'] / 'windows'
        camera = dict(cameras['cameras'][item['camera_id']])
        camera['source_id'] = item['source_id']
        if config['view'] == 'full_frame':
            camera['roi'] = [0, 0, 1, 1]
        settings_digest = digest({'settings': pipeline_settings, 'source_sha256': item['sha256']})
        wrapped = FingerprintedAnalyzer(analyzer, digest(inputs['model_files']), settings_digest)
        if baseline and camera['roi'] == [0, 0, 1, 1]:
            attempt, previous = baseline
            records = baseline_records[item['source_id']]
            wrapped = ExactReuseAnalyzer(wrapped, records, attempt, digest(inputs['model_files']), settings_digest)
        summary = run_video(ASSETS / item['relative_video_path'], camera, wrapped,
                            folder / item['source_id'], {**context, 'source_id': item['source_id']}, pipeline_settings)
        results.append({'source_id': item['source_id'], **summary})
        if summary.get('status') != 'succeeded':
            raise ValueError(f"full pipeline failed at {item['source_id']}; partial output retained")
    return results


def run_prompt_regression(analyzer, folder, sources, cameras, context):
    """Filter unchanged native-PTS windows; no review labels enter this path."""
    import numpy as np
    from mvp.windows import iter_windows
    from mvp.pipeline import _clear_diagnostics, _failure_diagnostics
    manifest = load_regression_manifest()
    results = []
    for item in sources['continuous_sources']:
        selected = {r['window_id']: r for r in manifest['windows']
                    if r['source_id'] == item['source_id']}
        if not selected:
            continue
        source_dir = folder / item['source_id']
        source_dir.mkdir()
        analyzer.artifact_root = source_dir / 'windows'
        stats, completed = {}, []
        try:
            for window in iter_windows(ASSETS / item['relative_video_path'], stats=stats):
                frozen = selected.get(window.window_id)
                if frozen is None:
                    continue
                source, rgb = window.source(), window.rgb
                if (window.start != frozen['start'] or window.end != frozen['end'] or
                        len(window.samples) != 10 or source['pts_seconds'] !=
                        [frozen['start'] + i / 2 for i in range(10)]):
                    raise ValueError('frozen window PTS/frame-count contract differs')
                source['rgb_sha256'] = hashlib.sha256(rgb.tobytes()).hexdigest()
                target = analyzer.artifact_root / window.window_id
                target.mkdir(parents=True)
                roi = ([0, 0, 1, 1] if context['view'] == 'full_frame' else
                       cameras['cameras'][item['camera_id']]['roi'])
                atomic_json(target / 'input.json', {**source, 'roi': roi,
                    'source_sha256': manifest['sources'][item['source_id']]})
                _clear_diagnostics(analyzer)
                try:
                    record = analyzer.analyze(rgb, source, window.window_id, roi)
                except Exception:
                    atomic_json(target / 'failure.json', {'status': 'failed',
                        'traceback': traceback.format_exc(), **_failure_diagnostics(analyzer)})
                    raise
                atomic_json(target / 'result.json', record)
                (target / 'raw_response.txt').write_text(record['raw_response'], encoding='utf-8')
                (target / 'expanded_prompt.txt').write_text(analyzer.last_expanded_prompt, encoding='utf-8')
                np.save(target / 'generated_token_ids.npy', np.array(analyzer.last_generated_token_ids, dtype='int64'))
                np.save(target / 'processor_rgb.npy', analyzer.last_processor_frames, allow_pickle=False)
                completed.append(window.window_id)
            if set(completed) != set(selected) or not stats.get('eof_reached'):
                raise ValueError('not all frozen windows decoded from original source through EOF')
        finally:
            atomic_json(source_dir / 'summary.json', dict(decode=stats,
                completed_windows=completed, run_context=context))
        results.append(dict(source_id=item['source_id'], windows=completed, decode=stats))
    return results


def run(phase, view, attempt, lock_fd):
    config = {'phase': phase, 'view': view, 'settings': settings_for_phase(phase)}
    validation_started = time.perf_counter()
    job = verify_lease(config, attempt, lock_fd)
    inputs = json.loads(job['input_json'])
    if digest(inputs) != job['input_hash'] or digest(config) != job['config_hash'] or source_hash('mvp-0001', config) != job['source_hash']:
        raise ValueError('registered source/input/config contract changed')
    validate(config, inputs, RUNTIME)
    sources, cameras, pipeline_settings = load_configs()
    folder = output_path(phase, attempt)
    folder.mkdir(parents=True, exist_ok=False)
    summary = dict(status='preflight', config=config, attempt_id=attempt, job_id=job['job_id'],
                   code_sha=job['code_sha'], source_hash=job['source_hash'], input_hash=job['input_hash'],
                   config_hash=job['config_hash'], pipeline_settings=pipeline_settings,
                   python_version=sys.version, results=[], generation_retries=0)
    if phase == 'appearance-8b':
        # Legacy video-window settings are neither used nor effective for this phase.
        summary.pop('pipeline_settings')
        summary['effective_settings'] = config['settings']
    from mvp.independent import PHASES as INDEPENDENT_PHASES, run_comparison
    if phase in ('prompt-regression', 'candidate-vlm', 'appearance-compare', 'appearance-8b', *INDEPENDENT_PHASES):
        from orchestration.mvp_command import sources as code_sources
        summary['bindings'] = {'inputs': inputs, 'code_files': code_sources(config)}
    monitor = None
    try:
        summary['queue_contract_validation_seconds'] = time.perf_counter() - validation_started
        os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1',
            SCENEGUARD_MVP_CONFIG=json.dumps(config), SCENEGUARD_MVP_ATTEMPT=attempt,
            SCENEGUARD_MVP_LOCK_FD=str(lock_fd))
        if phase == 'appearance-8b':
            from mvp.exp0038 import run_six_pairs, MODEL_DIR as model_8b, CHECKPOINT, BASELINE_OUTPUT
            from vlm_batch.run import MemoryMonitor
            # The 8B entrypoint owns the resource gate and its sole NF4 model load.
            # In particular, never construct the historical 2B QwenAnalyzer here.
            monitor = MemoryMonitor()
            monitor.start()
            context = {k: job[k] for k in ('run_id', 'task_id', 'dispatch_id', 'code_sha',
                                           'source_hash', 'input_hash', 'config_hash')}
            context.update(attempt_id=attempt, phase=phase, view=view)
            summary['results'] = run_six_pairs(model_8b, json.loads(CHECKPOINT.read_text()),
                                               folder, context, BASELINE_OUTPUT)
            summary['status'] = 'succeeded'
            return
        if phase == 'appearance-compare':
            from mvp.exp0034_appearance import verify_native_crops
            summary['native_crop_verification'] = verify_native_crops()
        summary['resource_gate'] = check_resources(pipeline_settings)
        os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1',
            SCENEGUARD_MVP_CONFIG=json.dumps(config), SCENEGUARD_MVP_ATTEMPT=attempt,
            SCENEGUARD_MVP_LOCK_FD=str(lock_fd))
        import torch
        from mvp.method import QwenAnalyzer
        from vlm_batch.run import MemoryMonitor
        if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
            raise ValueError('CUDA0 BF16 required')
        monitor = MemoryMonitor()
        monitor.start()
        torch.cuda.reset_peak_memory_stats()
        t = time.perf_counter()
        analyzer = QwenAnalyzer(MODEL_DIR, SETTINGS)
        torch.cuda.synchronize()
        summary.update(status='running', load_seconds=time.perf_counter()-t,
            device=torch.cuda.get_device_name(0), torch_version=torch.__version__, cuda_version=torch.version.cuda,
            load_peak_allocated_bytes=torch.cuda.max_memory_allocated(),
            load_peak_reserved_bytes=torch.cuda.max_memory_reserved(),
            packages={d.metadata['Name']: d.version for d in importlib.metadata.distributions()},
            model_parameter_devices=sorted({str(p.device) for p in analyzer.model.parameters()}))
        if summary['model_parameter_devices'] != ['cuda:0']:
            raise ValueError('all model parameters must be on CUDA0')
        atomic_json(folder / 'loading.json', summary)
        context = {key: job[key] for key in ('run_id', 'task_id', 'dispatch_id', 'code_sha', 'source_hash', 'input_hash', 'config_hash')}
        context.update(attempt_id=attempt, view=view, phase=phase)
        from mvp.candidate_vlm import run_candidate_review
        from mvp.exp0034_appearance import run_appearance
        summary['results'] = (run_appearance(analyzer, folder, context) if phase == 'appearance-compare' else
            run_candidate_review(analyzer, folder, context, cameras, inputs)
                              if phase == 'candidate-vlm' else
            run_development(analyzer, folder, sources, cameras, inputs) if phase == 'dev' else
            run_comparison(analyzer, folder, context) if phase in INDEPENDENT_PHASES else
            run_prompt_regression(analyzer, folder, sources, cameras, context) if phase == 'prompt-regression' else
            run_full(analyzer, folder, sources, cameras, pipeline_settings, config, inputs, context))
        summary['status'] = 'succeeded'
    except Exception as exc:
        summary.update(status='failed', error=repr(exc), traceback=traceback.format_exc())
        raise
    finally:
        if monitor:
            monitor.stop()
            atomic_json(folder / 'gpu_memory_samples.json', {'samples': monitor.samples, 'errors': monitor.errors})
        atomic_json(folder / 'summary.json', summary)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=PHASES, required=True)
    parser.add_argument('--view', choices=('fixed_roi', 'full_frame'), required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--lock-fd', required=True, type=int)
    args = parser.parse_args()
    run(args.phase, args.view, args.attempt, args.lock_fd)
