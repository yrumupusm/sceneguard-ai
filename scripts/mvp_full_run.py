"""Freeze and execute whole originals with the unchanged MVP pipeline, locally.

Input is a no-truth JSON object with ``videos`` containing video_id, video_path,
camera_id (null when unestablished), and support_provenance.  Do not supply labels,
captions, event windows, or scoring manifests.  Preparation never invokes a model.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sceneguard import video_cards as vc
from orchestration.video_cards_command import RUNTIME, SETTINGS, WEIGHT, sources
from orchestration.queue import Queue

REVISION = 'f05d430458150c9b63e04aa9caf93cb85ee18cae'
BASELINE = '548ff7098045f9efc5bd2edfd5ce61431a5e210e'
LOCAL = ROOT / 'runtime/MVP-ALL'
RUNS = ROOT / 'outputs/validation/mvp-all-v1/runs'
FIELDS = {'video_id', 'video_path', 'camera_id', 'support_provenance'}


def utc():
    return datetime.now(timezone.utc).isoformat()


def write(path, value, *, exclusive=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive:
        vc.save(path, value)
    else:
        temporary = path.with_name(path.name + '.tmp-' + str(os.getpid()))
        vc.save(temporary, value)
        temporary.replace(path)


def head():
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()


def gpu():
    raw = subprocess.check_output(['nvidia-smi', '-i', '0',
        '--query-gpu=memory.used,memory.free,utilization.gpu',
        '--format=csv,noheader,nounits'], text=True, timeout=10).strip()
    used, free, utilization = map(float, raw.split(','))
    return dict(utc=utc(), used_mib=used, free_mib=free, utilization_percent=utilization,
                minimum_free_mib=6144, available=free >= 6144)


def code_files():
    paths = sorted((ROOT / 'sceneguard').rglob('*.py'))
    paths += [ROOT / p for p in sources() if not p.startswith('sceneguard/')]
    paths += [Path(__file__).resolve()]
    return {str(p): vc.sha256(p) for p in sorted(set(paths))}


def bindings(paths):
    return {str(p): vc.sha256(p) for p in sorted(set(map(Path, paths)))}


def frozen_analysis_bytes():
    actual = code_files()
    actual.pop(str(Path(__file__).resolve()))
    expected = {}
    for absolute in actual:
        relative = Path(absolute).relative_to(ROOT)
        blob = subprocess.check_output(['git', 'show', REVISION + ':' + str(relative)], cwd=ROOT)
        expected[absolute] = hashlib.sha256(blob).hexdigest()
    reference_modules = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only',
        REVISION, '--', 'sceneguard'], cwd=ROOT, text=True).splitlines()
    reference_modules = {str(ROOT / p) for p in reference_modules if p.endswith('.py')}
    actual_modules = {str(p) for p in (ROOT / 'sceneguard').rglob('*.py')}
    if actual_modules != reference_modules or actual != expected:
        raise ValueError('Analysis/queue dependencies differ from frozen f05d430 git blobs')
    return actual


def queue_snapshot(path):
    status = Queue(RUNTIME).status()
    write(path, dict(utc=utc(), runtime=str(RUNTIME), **status), exclusive=True)
    return status


def source_clock(video):
    """Decode every source frame: container counts/FPS alone do not prove coverage."""
    import av
    rows = []
    with av.open(str(video)) as container:
        stream = container.streams.video[0]
        stream.thread_count = 2
        for index, frame in enumerate(container.decode(stream)):
            if frame.pts is None:
                raise ValueError('Source frame has no native PTS')
            rows.append(dict(frame_index=index, native_pts=frame.pts,
                time_base=str(frame.time_base), pts=float(frame.pts * frame.time_base)))
    if not rows:
        raise ValueError('Empty original source')
    return rows


def assert_clock(expected, actual, *, indexed=False):
    if len(expected) != len(actual):
        raise ValueError('Whole decoded source frame count differs')
    for original, measured in zip(expected, actual):
        keys = ('native_pts', 'time_base', 'pts', 'frame_index') if indexed else (
            'native_pts', 'time_base', 'pts')
        if any(original[k] != measured[k] for k in keys):
            raise ValueError('Entire native source PTS sequence differs')


def coverage_receipt(row):
    output = Path(row['output_path'])
    expected = vc.read(row['source_clock_path'])
    baseline = vc.read(output / 'source/analysis/analysis.json')
    cache = Path(baseline['source_paths']['cache'])
    measured = {
        'detector_cache': (cache / 'person_cache.jsonl', False),
        'tracking': (output / 'source/tracking/frames.jsonl', False),
        'image_paths': (output / 'image-paths/frame-evidence.jsonl', True),
        'frontend_evidence': (output / 'source/evidence/source-frames.json', True),
        'final_evidence': (output / 'evidence/source-frames.json', True)}
    results = {}
    for name, (path, indexed) in measured.items():
        records = vc.read(path) if path.suffix == '.json' else [json.loads(line)
            for line in path.read_text().splitlines() if line.strip()]
        assert_clock(expected, records, indexed=indexed)
        results[name] = dict(path=str(path), sha256=vc.sha256(path), frames=len(records),
                             exact_entire_native_pts_match=True)
    return dict(utc=utc(), source_sha256=row['source_sha256'],
        source_clock_sha256=vc.sha256(row['source_clock_path']), frames=len(expected),
        first=expected[0], last=expected[-1], compared=results,
        state='complete_whole_original_native_partition')


def costs(row):
    output = Path(row['output_path'])
    stages = {}
    for relative in ('source/tracking', 'source/analysis', 'source/evidence',
                     'image-paths', 'decision', 'evidence'):
        receipt = output / relative / 'stage.json'
        if receipt.exists():
            stages[relative] = vc.read(receipt).get('elapsed_seconds')
    result = dict(wrapper_wall_seconds=row['elapsed_seconds'],
        wrapper_wall_per_video_second=row['elapsed_seconds'] / row['duration_seconds'],
        pipeline_status_costs={k: row['pipeline_status'].get(k) for k in
            ('elapsed_seconds', 'cpu_seconds', 'frames', 'detector_frames_this_execution',
             'tracker_frames_this_execution', 'cpu_image_path_frames_this_execution', 'reused')},
        stage_wall_seconds=stages, stage_times_overlap_pipeline_wall=True,
        cpu_seconds_scope='pipeline process only; excludes canonical detector child')
    baseline_path = output / 'source/analysis/analysis.json'
    if baseline_path.exists():
        cache = Path(vc.read(baseline_path)['source_paths']['cache'])
        meta = vc.read(cache / 'run.json')
        result['detector_cache_metadata'] = dict(path=str(cache / 'run.json'),
            sha256=vc.sha256(cache / 'run.json'), **{k: meta.get(k) for k in
                ('frames', 'first_pts', 'last_pts', 'processing_wall_seconds', 'warmup_seconds',
                 'throughput_fps', 'peak_allocated_bytes', 'peak_reserved_bytes',
                 'stage_ms', 'processing_wall_scope')})
    return result


def prepare(source_path, plan_path):
    import av
    frozen_analysis = frozen_analysis_bytes()
    execution_revision = head()
    source = vc.read(source_path)
    if set(source) != {'videos'} or not source['videos']:
        raise ValueError('Use the no-truth execution source contract')
    profile_path = ROOT / 'runtime/MVP-0002/camera-profiles.local.json'
    profiles = vc.read(profile_path)['profiles']
    cameras = vc.read(vc.CAMERAS)['cameras']
    files = [source_path, profile_path, vc.CAMERAS, WEIGHT]
    for camera in ('C3', 'C6'):
        profile = profiles[camera]
        for relative, expected in profile['input_sha256'].items():
            if vc.sha256(ROOT / relative) != expected:
                raise ValueError('Adopted profile bytes differ: ' + relative)
        files += [ROOT / profile[k] for k in ('scene', 'portal', 'cpu_seed_scene')]
        scene = vc.read(vc.SCENES[camera])
        region = Path(scene['annotation_provenance']['current_regions_path'])
        files += [region if region.is_absolute() else ROOT / region]
    candidates = []
    for path in sorted((ROOT / 'outputs').rglob('run.json')):
        if path.is_symlink() or any(p.is_symlink() for p in path.parents):
            continue
        try:
            meta = vc.read(path)
            if meta.get('model') == 'fcos_resnet50_fpn.COCO_V1':
                candidates.append((path.parent, meta))
        except (ValueError, OSError):
            continue
    rows, seen, hashes = [], set(), {}
    for item in source['videos']:
        if set(item) != FIELDS or not re.fullmatch(r'[A-Za-z0-9_-]+', item['video_id']):
            raise ValueError('Exact no-truth fields and safe video IDs required')
        if item['video_id'] in seen:
            raise ValueError('Duplicate video ID')
        seen.add(item['video_id'])
        video = Path(item['video_path'])
        if not video.is_absolute():
            video = ROOT / video
        if not video.resolve().is_relative_to(ROOT / 'data'):
            raise ValueError('Use local original data paths')
        source_sha = vc.sha256(video)
        files.append(video)
        with av.open(str(video)) as container:
            stream = container.streams.video[0]
            info = dict(duration_seconds=float(stream.duration * stream.time_base)
                if stream.duration is not None else None, source_size=[stream.width, stream.height],
                average_rate=str(stream.average_rate), time_base=str(stream.time_base),
                metadata_frames=stream.frames)
        row = dict(item, video_path=str(video), source_sha256=source_sha, **info,
                   output_path=str(RUNS / item['video_id']), cache=None, cache_candidates=[],
                   execution_status='not_run', processed_seconds=0.0, reason=None)
        if source_sha in hashes:
            row.update(execution_status='unsupported', reason='duplicate_source_bytes',
                       duplicate_of=hashes[source_sha])
        hashes[source_sha] = item['video_id']
        camera = item['camera_id']
        if row['execution_status'] == 'not_run':
            if camera not in vc.SCENES or not item['support_provenance']:
                row.update(execution_status='unsupported', reason='no_admitted_camera_scene_portal_binding')
            else:
                try:
                    supported_info = vc.probe(video)
                    if supported_info['size'] != vc.read(vc.SCENES[camera])['source_size']:
                        raise ValueError('Source size differs from calibrated scene')
                except ValueError as exc:
                    row.update(execution_status='unsupported', reason=str(exc))
                else:
                    row.update(scene=str(ROOT / profiles[camera]['scene']),
                               portal=str(ROOT / profiles[camera]['portal']))
                    clock = source_clock(video)
                    clock_path = LOCAL / 'source-clocks' / (item['video_id'] + '.json')
                    write(clock_path, clock, exclusive=True)
                    files.append(clock_path)
                    row.update(source_clock_path=str(clock_path), decoded_frames=len(clock),
                               source_first_pts=clock[0]['pts'], source_last_pts=clock[-1]['pts'])
                    for directory, meta in candidates:
                        if meta.get('source_sha256') != source_sha:
                            continue
                        candidate = dict(path=str(directory), first_pts=meta.get('first_pts'),
                            last_pts=meta.get('last_pts'), frames=meta.get('frames'))
                        try:
                            _, frames, _, _ = vc.validate_cached(video, cameras[camera], directory,
                                0.0, info['duration_seconds'], supported_info)
                            assert_clock(clock, frames)
                            candidate.update(whole_match=True)
                            if row['cache'] is None:
                                row['cache'] = str(directory)
                                files += [directory / 'run.json', directory / 'person_cache.jsonl']
                        except (ValueError, KeyError, TypeError, OSError) as exc:
                            candidate.update(whole_match=False, reason=str(exc))
                        row['cache_candidates'].append(candidate)
                    row['detector_required'] = row['cache'] is None
        rows.append(row)
    status = queue_snapshot(LOCAL / 'queue-before.local.json')
    plan = dict(schema_version=1, protocol_id='MVP-ALL-EVENT-EVIDENCE-v1', frozen_utc=utc(),
        analysis_revision=REVISION, execution_revision=execution_revision,
        baseline_revision=BASELINE, frozen_analysis_sha256=frozen_analysis,
        source_list_sha256=vc.sha256(source_path),
        input_sha256=bindings(files), code_sha256=code_files(), profiles_path=str(profile_path),
        queue_runtime=str(RUNTIME), detector_settings=SETTINGS, ground_truth_loaded=False,
        retries_allowed=0, videos=rows, resource_at_preparation=gpu(),
        queue_pending_at_preparation=[j['job_id'] for j in status['jobs']
            if j['status'] in ('queued', 'running', 'unknown')])
    write(plan_path, plan, exclusive=True)
    write(LOCAL / 'execution-ledger.local.json', dict(plan_path=str(plan_path),
        plan_sha256=vc.sha256(plan_path), updated_utc=utc(), videos=rows))
    return plan


def verify_plan(plan):
    if head() != plan['execution_revision'] or code_files() != plan['code_sha256']:
        raise ValueError('Frozen source revision/code changed')
    if bindings(plan['input_sha256']) != plan['input_sha256']:
        raise ValueError('Frozen source/config/cache/weight bytes changed')


def execute(plan_path, context):
    plan = vc.read(plan_path)
    verify_plan(plan)
    ledger_path = LOCAL / 'execution-ledger.local.json'
    ledger = vc.read(ledger_path)
    if ledger['plan_sha256'] != vc.sha256(plan_path):
        raise ValueError('Ledger belongs to a different frozen plan')
    for row in ledger['videos']:
        if row['execution_status'] != 'not_run':
            continue
        verify_plan(plan)
        resource = gpu()
        row['resource_before'] = resource
        if row['detector_required'] and not resource['available']:
            row['reason'] = 'blocked_gpu_free_below_6144_mib'
            ledger.update(updated_utc=utc(), blocked_resource=resource)
            write(ledger_path, ledger)
            return ledger
        pending = [j['job_id'] for j in Queue(RUNTIME).status()['jobs']
                   if j['status'] in ('queued', 'running', 'unknown')]
        if row['detector_required'] and pending:
            row['reason'] = 'blocked_canonical_queue_pending_work'
            ledger.update(updated_utc=utc(), blocked_queue_jobs=pending)
            write(ledger_path, ledger)
            return ledger
        command = [sys.executable, '-m', 'sceneguard.mvp_pipeline', '--video', row['video_path'],
            '--camera', row['camera_id'], '--scene', row['scene'], '--portal', row['portal'],
            '--output', row['output_path'], '--whole']
        if row['cache']:
            command += ['--cache', row['cache']]
        else:
            for key, value in context.items():
                command += ['--' + key.replace('_', '-'), value]
        folder = LOCAL / row['video_id']
        folder.mkdir(exist_ok=False)
        queue_snapshot(folder / 'queue-before.local.json')
        row.update(command=command, started_utc=utc(), reason='execution_in_progress')
        write(ledger_path, ledger)
        begin = time.perf_counter()
        with (folder / 'stdout.log').open('x') as stdout, (folder / 'stderr.log').open('x') as stderr:
            result = subprocess.run(command, cwd=ROOT, stdout=stdout, stderr=stderr)
        row.update(exit_code=result.returncode, elapsed_seconds=time.perf_counter() - begin,
                   finished_utc=utc(), retries=0)
        status_path = Path(row['output_path']) / 'status.json'
        status = vc.read(status_path) if status_path.exists() else {}
        row['pipeline_status'] = status
        complete = result.returncode == 0 and status.get('state') == 'analysis_complete'
        row.update(execution_status='complete' if complete else 'failed',
                   processed_seconds=row['duration_seconds'] if complete else 0.0,
                   reason=None if complete else status.get('error', 'pipeline_did_not_complete'))
        if complete:
            try:
                receipt = coverage_receipt(row)
                receipt_path = folder / 'whole-source-integrity.local.json'
                write(receipt_path, receipt, exclusive=True)
                row['integrity_receipt_path'] = str(receipt_path)
                manifest = vc.read(Path(row['output_path']) / 'viewer-manifest.json')
                row['viewer_manifest_path'] = str(Path(row['output_path']) / 'viewer-manifest.json')
                row['viewer_manifest_sha256'] = vc.sha256(row['viewer_manifest_path'])
                row['cards_path'] = manifest['cards_path']
                row['frames'] = status['frames']
                row['source_window'] = manifest['source_window']
            except (ValueError, KeyError, OSError) as exc:
                row.update(execution_status='failed', processed_seconds=0.0,
                           reason='whole_source_integrity_failed: ' + str(exc))
        after = queue_snapshot(folder / 'queue-after.local.json')
        jobs = [j for j in after['jobs'] if j['dispatch_id'] == context['dispatch_id']
                and json.loads(j['config_json']).get('request_path') ==
                    str(Path(row['output_path']) / 'source/request.json')]
        job_ids = {j['job_id'] for j in jobs}
        row['queue_provenance'] = dict(jobs=jobs,
            attempts=[a for a in after['attempts'] if a['job_id'] in job_ids])
        row['costs'] = costs(row)
        verify_plan(plan)
        ledger['updated_utc'] = utc()
        write(ledger_path, ledger)
    return ledger


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'execute'))
    parser.add_argument('--sources', type=Path)
    parser.add_argument('--plan', type=Path, default=LOCAL / 'execution-plan.local.json')
    for key in ('run-id', 'task-id', 'dispatch-id', 'owner'):
        parser.add_argument('--' + key)
    args = parser.parse_args()
    LOCAL.mkdir(parents=True, exist_ok=True)
    with (LOCAL / 'runner.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == 'prepare':
            if args.sources is None:
                parser.error('prepare requires --sources')
            result = prepare(args.sources.absolute(), args.plan.absolute())
        else:
            context = {key: getattr(args, key) for key in ('run_id', 'task_id', 'dispatch_id', 'owner')}
            if not all(context.values()):
                parser.error('execute requires all four live canonical queue identity fields')
            result = execute(args.plan.absolute(), context)
        print(json.dumps(dict(videos=len(result['videos']),
            statuses=dict(Counter(r['execution_status'] for r in result['videos'])),
            plan=str(args.plan), ledger=str(LOCAL / 'execution-ledger.local.json')), indent=2))
        if args.action == 'execute' and any(r['execution_status'] in ('not_run', 'failed', 'partial')
                                            for r in result['videos']):
            raise SystemExit(2)


if __name__ == '__main__':
    main()
