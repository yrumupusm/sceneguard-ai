"""Separate, frozen expanded-camera whole-original batch; preparation never infers.

The legacy mvp_full_run.py remains a frozen historical guard.  This runner names
its analysis by a digest of the actual working bytes, rather than claiming that
camera/FPS compatibility changes are the historical analysis revision.  All
execution requires a coordinator authorization bound to the immutable plan.
"""
from __future__ import annotations

import argparse
from collections import Counter
from fractions import Fraction
import fcntl
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
from orchestration.video_cards_command import RUNTIME, SETTINGS, WEIGHT, sources, validate_assignment
from orchestration.queue import Queue
from scripts.mvp_full_run import (assert_clock, bindings, costs, coverage_receipt,
                                  gpu, head, source_clock, utc, write)

LOCAL = ROOT / 'runtime/MVP-0005/execution'
RUNS = ROOT / 'outputs/validation/mvp-all-v3/runs'
FIELDS = {'video_id', 'video_path', 'camera_id', 'support_provenance'}
REGRESSIONS = ('E01_007', 'E01_030')
HISTORICAL = ROOT / 'outputs/validation/mvp-all-v2/runs'
SOURCE_LIST = ROOT / 'outputs/validation/mvp-all-v1/inventory/source-list.json'
NATIVE_CLOCKS = ROOT / 'outputs/validation/mvp-all-v1/inventory/native-pts'
CACHES = {
    'E01_007': ROOT / 'outputs/exp0037/detector/f056fc1401184eb289f7ac8d3dfd846f/cache',
    'E01_030': ROOT / 'outputs/exp0037/detector/14086945309a4db4b0c0bd3957ad333d/cache',
}
CONTEXT_KEYS = ('run_id', 'task_id', 'dispatch_id', 'owner')
STAGES = ('source/tracking', 'source/analysis', 'source/evidence',
          'image-paths', 'decision', 'evidence')


def local_path(path, root):
    """Reject aliases, traversal and symlinks before writing or binding files."""
    path, root = Path(path).absolute(), Path(root).absolute()
    if (not path.is_relative_to(root) or path.resolve() != path
            or any(p.is_symlink() for p in (path, *path.parents))):
        raise ValueError('Use a local non-symlink path under ' + str(root))
    return path


def code_files():
    paths = set((ROOT / 'sceneguard').rglob('*.py'))
    paths.update(ROOT / name for name in sources())
    paths.update((Path(__file__).resolve(), ROOT / 'scripts/mvp_full_run.py'))
    return bindings(paths)


def analysis_code_digest(code):
    relative = {str(Path(path).relative_to(ROOT)): value for path, value in code.items()}
    return 'MVP-0005-sha256:' + vc.fingerprint(relative)


def load_sources(path):
    data = vc.read(path)
    if set(data) != {'videos'} or len(data['videos']) != 45:
        raise ValueError('Exact no-truth all-45 source list required')
    seen = set()
    for row in data['videos']:
        if (set(row) != FIELDS or not re.fullmatch(r'[A-Za-z0-9_-]+', row['video_id'])
                or row['video_id'] in seen or not row['support_provenance']):
            raise ValueError('Exact no-truth fields, unique safe IDs and provenance required')
        seen.add(row['video_id'])
        local_path(row['video_path'], ROOT / 'data')
    original = vc.read(SOURCE_LIST)['videos']
    expected = {(r['video_id'], str(Path(r['video_path']).absolute())) for r in original}
    actual = {(r['video_id'], str(Path(r['video_path']).absolute())) for r in data['videos']}
    if len(expected) != 45 or actual != expected:
        raise ValueError('Source inventory changed; keep all original 45 once')
    return data['videos']


def audited_clock(video, source_sha, video_id):
    """Reuse the complete decoded inventory clock only with its original hash binding."""
    path = NATIVE_CLOCKS / (video_id + '.json')
    if not path.exists():
        return source_clock(video), None
    audit = vc.read(path)
    if (audit['source_sha256'] != source_sha
            or audit['media']['decode_status'] != 'complete'):
        raise ValueError('Existing decoded clock is not bound to this complete original')
    clock = audit['clocks']
    rows = [dict(frame_index=i, native_pts=pts, time_base=clock['time_base'],
                 pts=float(pts * Fraction(clock['time_base'])))
            for i, pts in enumerate(clock['native_pts'])]
    if len(rows) != audit['media']['decoded_frame_count']:
        raise ValueError('Decoded inventory clock count differs')
    validate_source_clock(rows)
    return rows, path


def validate_source_clock(clock):
    if len(clock) < 2 or clock[0]['pts'] != 0:
        raise ValueError('Whole nonempty source clock must begin at native origin zero')
    for index, row in enumerate(clock):
        if (type(row['native_pts']) is not int or row['frame_index'] != index
                or row['pts'] != float(row['native_pts'] * Fraction(row['time_base']))
                or (index and row['pts'] <= clock[index - 1]['pts'])):
            raise ValueError('Decoded clock must preserve exact increasing native PTS')


def source_metadata(video, clock, audit_path):
    """Keep denominator metadata even when a camera/profile is unsupported."""
    if audit_path:
        media = vc.read(audit_path)['media']
        size, rate, duration = media['source_size'], media['average_rate'], media['duration_seconds']
    else:
        import av
        with av.open(str(video)) as container:
            stream = container.streams.video[0]
            size, rate = [stream.width, stream.height], str(stream.average_rate)
            duration = float(stream.duration * stream.time_base) if stream.duration is not None else None
    return dict(source_size=size, average_rate=rate, time_base=clock[0]['time_base'],
                source_end_exclusive=float(Fraction(clock[-1]['native_pts']) * Fraction(clock[-1]['time_base']) + 1 / Fraction(rate)),
                duration_seconds=duration,
                container_duration_seconds=duration)


def queue_snapshot(path):
    value = dict(utc=utc(), runtime=str(RUNTIME), **Queue(RUNTIME).status())
    write(path, value, exclusive=True)
    return value


def profile_inputs(camera_id, camera, scene, portal, registry_path, source_size):
    """Use the pipeline's exact external/embedded region and seed resolution."""
    from sceneguard.exp0034_application import validate_scene_binding
    from sceneguard.portal_births import PortalGate
    selected = vc.read(scene)
    PortalGate(selected, vc.read(portal), camera_id)
    _, selected_regions = vc.scene_regions(selected, scene, embedded=True)
    seed = vc.source_scene(camera_id, scene, registry_path)
    regions, seed_regions = vc.scene_regions(vc.read(seed), seed, embedded=True)
    validate_scene_binding(vc.read(seed), [dict(source_size=source_size)], regions, camera)
    return [scene, portal, seed, selected_regions, seed_regions]


def prepare(source_path, registry_path, plan_path):
    """Freeze all inputs and all source clocks without calling a detector or pipeline."""
    plan_path = local_path(plan_path, LOCAL)
    if plan_path.exists() or (LOCAL / 'execution-ledger.local.json').exists():
        raise ValueError('Existing plan/ledger is immutable; do not overwrite or re-prepare')
    source_path, registry_path = Path(source_path).absolute(), Path(registry_path).absolute()
    source_rows = load_sources(source_path)
    registry = vc.read(registry_path)
    expected_sources = {str(Path(r['video_path']).absolute()) for r in source_rows}
    if registry.get('schema_version') != 1 or set(registry.get('sources', {})) != expected_sources:
        raise ValueError('Registry must bind exactly the 45 source paths')
    files = [source_path, registry_path, SOURCE_LIST, WEIGHT]
    # Bind the registry's full static provenance, including CPU seed scenes and regions.
    for path in sorted(registry_path.parent.rglob('*.json')):
        files.append(path)
    for path in vc.SCENES.values():
        files.append(path)
    cache_candidates = {}
    for path in sorted((ROOT / 'outputs').rglob('run.json')):
        if path.is_symlink() or any(p.is_symlink() for p in path.parents):
            continue
        try:
            metadata = vc.read(path)
            if metadata.get('model') == 'fcos_resnet50_fpn.COCO_V1':
                cache_candidates.setdefault(metadata.get('source_sha256'), []).append(path.parent)
        except (OSError, ValueError):
            continue
    rows, source_hashes = [], {}
    for item in source_rows:
        video = local_path(item['video_path'], ROOT / 'data')
        source_sha = vc.sha256(video)
        files.append(video)
        clock, audit_path = audited_clock(video, source_sha, item['video_id'])
        validate_source_clock(clock)
        clock_path = LOCAL / 'source-clocks' / (item['video_id'] + '.json')
        write(clock_path, clock, exclusive=True)
        files.append(clock_path)
        if audit_path:
            files.append(audit_path)
        row = dict(item, video_path=str(video), source_sha256=source_sha,
                   source_clock_path=str(clock_path), decoded_frames=len(clock),
                   source_first_pts=clock[0]['pts'], source_last_pts=clock[-1]['pts'],
                   execution_status='not_run', processed_seconds=0.0, reason=None,
                   output_path=None, attempts=[], cache=None, detector_required=True)
        row['cache_candidates'] = []
        row.update(source_metadata(video, clock, audit_path))
        try:
            if source_sha in source_hashes:
                raise ValueError('duplicate_source_bytes_of_' + source_hashes[source_sha])
            camera, scene, portal, _ = vc.camera_profile(item['camera_id'], video, registry_path)
            info = vc.probe(video)
            # Preserve the container duration separately: 006 ends with a frame at it.
            exact_end = clock[-1]['pts'] + float(1 / Fraction(info['fps']))
            exclusive_end = info.get('source_end_exclusive', info['duration'])
            if abs(exclusive_end - exact_end) > 1e-6:
                raise ValueError('Probe exclusive EOF end differs from full native clock')
            if info['size'] != vc.read(scene)['source_size']:
                raise ValueError('Source dimensions differ from the static scene')
            row.update(scene=str(scene), portal=str(portal), source_size=info['size'],
                       average_rate=info['fps'], time_base=info['time_base'],
                       duration_seconds=info['duration'], source_end_exclusive=exclusive_end,
                       container_duration_seconds=info['duration'])
            files.extend(profile_inputs(item['camera_id'], camera, scene, portal, registry_path, info['size']))
            if item['video_id'] in REGRESSIONS:
                cache = CACHES[item['video_id']]
                _, frames, _, _ = vc.validate_cached(video, camera, cache, 0.0, exclusive_end, info)
                assert_clock(clock, frames)
                row.update(cache=str(cache), detector_required=False,
                           regression_reference=str(HISTORICAL / item['video_id']))
                files.extend((cache / 'run.json', cache / 'person_cache.jsonl'))
                files.extend(p for p in (HISTORICAL / item['video_id']).rglob('*') if p.is_file())
            else:
                for cache in cache_candidates.get(source_sha, []):
                    candidate = dict(path=str(cache), metadata_sha256=vc.sha256(cache / 'run.json'))
                    try:
                        _, frames, _, _ = vc.validate_cached(video, camera, cache, 0.0, exclusive_end, info)
                        assert_clock(clock, frames)
                        candidate['exact_whole_source_match'] = True
                        if row['cache'] is None:
                            row.update(cache=str(cache), detector_required=False)
                            files.extend((cache / 'run.json', cache / 'person_cache.jsonl'))
                    except (ValueError, KeyError, TypeError, OSError) as exc:
                        candidate.update(exact_whole_source_match=False, reason=str(exc))
                    row['cache_candidates'].append(candidate)
        except (ValueError, KeyError, TypeError, OSError) as exc:
            row.update(execution_status='unsupported', reason=str(exc))
        source_hashes[source_sha] = item['video_id']
        rows.append(row)
        write(LOCAL / 'preparation-progress.local.json', dict(utc=utc(),
              prepared_sources=len(rows), total_sources=len(source_rows),
              video_id=item['video_id'], execution_status=row['execution_status']))
    code = code_files()
    snapshot = queue_snapshot(LOCAL / 'queue-before.local.json')
    revision = head()
    plan = dict(schema_version=1, protocol_id='MVP-ALL-EVENT-EVIDENCE-v1',
                frozen_utc=utc(), analysis_revision=revision, analysis_code_digest=analysis_code_digest(code),
                execution_revision=revision, historical_analysis_revision='f05d430458150c9b63e04aa9caf93cb85ee18cae',
                code_sha256=code, input_sha256=bindings(files), registry_path=str(registry_path),
                source_list_sha256=vc.sha256(source_path), queue_runtime=str(RUNTIME),
                detector_settings=SETTINGS, ground_truth_loaded=False, retries_allowed=1,
                automatic_detector_retries=0, videos=rows,
                queue_pending_at_preparation=[j['job_id'] for j in snapshot['jobs']
                    if j['status'] in ('queued', 'running', 'unknown')],
                estimated_wall_seconds=sum(r.get('duration_seconds', 0) for r in rows) * 4,
                estimate_basis='prior approximately 4x source duration, not a measured promise')
    write(plan_path, plan, exclusive=True)
    write(LOCAL / 'execution-ledger.local.json', dict(plan_path=str(plan_path),
          plan_sha256=vc.sha256(plan_path), analysis_revision=plan['analysis_revision'],
          updated_utc=utc(), videos=rows), exclusive=True)
    return plan


def verify_plan(plan):
    if (head() != plan['execution_revision'] or code_files() != plan['code_sha256']
            or plan['analysis_revision'] != plan['execution_revision']
            or analysis_code_digest(plan['code_sha256']) != plan['analysis_code_digest']):
        raise ValueError('Frozen expanded analysis revision/code changed')
    if bindings(plan['input_sha256']) != plan['input_sha256']:
        raise ValueError('Frozen source/profile/clock/cache/reference/weight bytes changed')
    if plan['detector_settings'] != SETTINGS or plan['queue_runtime'] != str(RUNTIME):
        raise ValueError('Canonical FCOS settings or queue changed')


def verify_authorization(path, plan_path, plan, context, *, fresh=False):
    approval = vc.read(path)
    if (approval.get('plan_sha256') != vc.sha256(plan_path)
            or approval.get('analysis_revision') != plan['analysis_revision']
            or approval.get('context') != context
            or approval.get('profiles_code_frozen') is not True
            or approval.get('independent_review_accepted') is not True
            or approval.get('execution_permitted') is not True
            or (fresh and approval.get('gpu_permitted') is not True)):
        raise ValueError('Coordinator freeze/review/execution authorization is absent or mismatched')
    review = approval.get('independent_review', {})
    if not review.get('path') or vc.sha256(review['path']) != review.get('sha256'):
        raise ValueError('Independent review artifact hash differs')
    return approval


def verify_ledger(ledger, plan_path, plan):
    if (ledger.get('plan_sha256') != vc.sha256(plan_path)
            or ledger.get('analysis_revision') != plan['analysis_revision']
            or len(ledger['videos']) != len(plan['videos'])):
        raise ValueError('Ledger belongs to a different frozen all-source plan')
    for actual, expected in zip(ledger['videos'], plan['videos']):
        if any(actual.get(k) != v for k, v in expected.items()
               if k not in {'execution_status', 'reason', 'processed_seconds', 'output_path', 'attempts'}):
            raise ValueError('Immutable ledger source/profile/cache binding differs')


def artifact_bindings(output):
    output = local_path(output, RUNS)
    paths = list(output.rglob('*'))
    if any(p.is_symlink() for p in paths):
        raise ValueError('Completed output artifacts must not be symlinks')
    return bindings(p for p in paths if p.is_file() and not p.name.endswith('.lock'))


def validate_stages(output):
    for relative in STAGES:
        folder = Path(output) / relative
        receipt = vc.read(folder / 'stage.json')
        actual = {str(p.relative_to(folder)): vc.sha256(p) for p in folder.rglob('*')
                  if p.is_file() and p.name != 'stage.json'}
        if receipt.get('status') != 'complete' or receipt.get('artifacts') != actual:
            raise ValueError('Completed stage artifact binding differs: ' + relative)


def validate_complete(row, plan):
    output = Path(row['output_path'])
    status = vc.read(output / 'status.json')
    request = vc.read(output / 'request.json')
    if (status.get('state') != 'analysis_complete' or status.get('frames') != row['decoded_frames']
            or status.get('detector_frames_this_execution') != (row['decoded_frames'] if row['detector_required'] else 0)
            or status.get('tracker_frames_this_execution') != row['decoded_frames']
            or status.get('cpu_image_path_frames_this_execution') != row['decoded_frames']
            or request.get('video') != row['video_path'] or request.get('camera') != row['camera_id']
            or request.get('scene') != row['scene'] or request.get('portal') != row['portal']
            or request.get('camera_registry') != plan['registry_path']
            or request.get('whole') is not True or request.get('window') != [None, None]
            or request.get('cache') != row['cache']
            or request.get('code_sha256') != {str(Path(k).relative_to(ROOT)): v
                for k, v in plan['code_sha256'].items() if Path(k).is_relative_to(ROOT / 'sceneguard')}):
        raise ValueError('Completed pipeline request/status differs from frozen whole-source binding')
    input_paths = {row['video_path'], row['scene'], row['portal'], plan['registry_path'],
                   str(vc.SCENES.get(row['camera_id'], Path(row['scene'])))}
    expected_inputs = {path: plan['input_sha256'][path] for path in input_paths}
    if (request.get('input_sha256') != expected_inputs
            or bindings(expected_inputs) != expected_inputs):
        raise ValueError('Completed request input hashes differ')
    validate_stages(output)
    manifest_path = output / 'viewer-manifest.json'
    manifest = vc.read(manifest_path)
    if (manifest['source_sha256'] != row['source_sha256']
            or manifest['requested_window'] != [0.0, row['source_end_exclusive']]
            or vc.sha256(manifest['cards_path']) != manifest['cards_sha256']
            or vc.sha256(manifest['source_frames_path']) != manifest['source_frames_sha256']):
        raise ValueError('Completed viewer manifest differs from actual analysis artifacts')
    for media in manifest['media']:
        if vc.sha256(media['path']) != media['sha256']:
            raise ValueError('Completed evidence media hash differs')
    return coverage_receipt(row), status, manifest


def validate_job(row, context):
    """Prove a fresh detector used exactly one successful canonical attempt."""
    receipt_path = Path(row['output_path']) / 'source/queue-job.json'
    if not row['detector_required']:
        if receipt_path.exists():
            raise ValueError('Saved-cache CPU attempt unexpectedly submitted a detector job')
        return
    queued = vc.read(receipt_path)
    snapshot = Queue(RUNTIME).status()
    jobs = [j for j in snapshot['jobs'] if j['job_id'] == queued['job_id']]
    attempts = [a for a in snapshot['attempts'] if a['job_id'] == queued['job_id']]
    if len(jobs) != 1 or jobs[0]['status'] != 'succeeded' or len(attempts) != 1 or attempts[0]['status'] != 'succeeded':
        raise ValueError('Fresh canonical detector did not have exactly one successful attempt')
    config = json.loads(jobs[0]['config_json'])
    request = Path(row['output_path']) / 'source/request.json'
    if (config.get('request_path') != str(request) or config.get('context') != context
            or config.get('request_sha256') != vc.sha256(request) or config.get('settings') != SETTINGS):
        raise ValueError('Canonical detector job binding differs from this frozen request')


def validate_resume(row, plan):
    """Only a completed, receipted exact request may be skipped on resume."""
    receipt_path = Path(row['completion_receipt_path'])
    if vc.sha256(receipt_path) != row['completion_receipt_sha256']:
        raise ValueError('Completed binding receipt changed')
    receipt = vc.read(receipt_path)
    if (receipt['analysis_revision'] != plan['analysis_revision']
            or receipt['source_sha256'] != row['source_sha256']
            or receipt['output_sha256'] != artifact_bindings(row['output_path'])):
        raise ValueError('Completed output bytes/bindings changed; refusing resume')
    validate_complete(row, plan)


def regression_projection(value):
    """Keep behavior and topology; relabel only generated per-run identifiers.

    Session/request changes necessarily re-key evidence and cards.  IDs are
    replaced bijectively in first-occurrence order, preserving reuse, identity
    links, list order, timestamps, geometry, policies and every non-ID field.
    A provenance digest of the candidate bundle is omitted explicitly because
    that bundle includes the new run's IDs; candidates themselves are compared.
    """
    identifiers = {}
    def collect(node):
        if isinstance(node, dict):
            for key, child in node.items():
                if (key in {'event_id', 'incident_id', 'session_id', 'analysis_run_id',
                            'resolution_id', 'source_incident_id', 'current_incident_id',
                            'owner_incident_id', 'routing_source_resolution_id'} and isinstance(child, str)):
                    identifiers.setdefault(child, '@generated-' + str(len(identifiers)))
                collect(child)
        elif isinstance(node, list):
            for child in node:
                collect(child)
    collect(value)
    pattern = re.compile('|'.join(re.escape(k) for k in sorted(identifiers, key=len, reverse=True))) if identifiers else None
    def replace(node):
        if isinstance(node, dict):
            return {replace(k): (sorted(replace(v)) if k.endswith('event_ids') or k == 'source_incident_ids'
                                else replace(v)) for k, v in node.items() if k != 'source_candidate_sha256'}
        if isinstance(node, list):
            return [replace(v) for v in node]
        if isinstance(node, str) and pattern:
            return pattern.sub(lambda m: identifiers[m.group()], node)
        return node
    return replace(value)


def regression_receipt(row):
    output, reference = Path(row['output_path']), Path(row['regression_reference'])
    compared = {}
    for relative in ('source/tracking/frames.jsonl', 'image-paths/frame-evidence.jsonl'):
        same = vc.sha256(output / relative) == vc.sha256(reference / relative)
        compared[relative] = dict(byte_exact=same, current_sha256=vc.sha256(output / relative),
                                  reference_sha256=vc.sha256(reference / relative))
        if not same:
            raise ValueError('CPU regression frame behavior differs: ' + relative)
    for path in sorted((reference / 'decision').glob('*.json')):
        if path.name == 'stage.json':
            continue
        actual = vc.read(output / 'decision' / path.name)
        expected = vc.read(path)
        if regression_projection(actual) != regression_projection(expected):
            raise ValueError('CPU regression decision behavior differs: ' + path.name)
        compared['decision/' + path.name] = dict(equal_after_generated_id_relabeling=True,
            current_sha256=vc.sha256(output / 'decision' / path.name), reference_sha256=vc.sha256(path))
    return dict(utc=utc(), video_id=row['video_id'], state='passed', compared=compared,
                detector_reused=True, new_gpu_frames=0,
                scope='exact tracking/CPU frames and decision behavior, generated run IDs relabeled')


class Progress:
    """Incrementally count durable JSONL records; never infer completed coverage."""
    def __init__(self):
        self.files = {}

    def snapshot(self, output):
        output = Path(output)
        records = {}
        candidates = list(output.glob('source/*/frames.jsonl'))
        candidates += list(output.glob('*/frame-evidence.jsonl'))
        for path in candidates:
            key = str(path)
            state = self.files.setdefault(key, dict(offset=0, complete_records=0))
            with path.open('rb') as stream:
                stream.seek(state['offset'])
                while chunk := stream.read(1024 * 1024):
                    state['complete_records'] += chunk.count(b'\n')
                    state['offset'] += len(chunk)
            records[key] = dict(state)
        statuses = {}
        for path in (output / 'status.json', output / 'source/status.json'):
            if path.exists():
                statuses[str(path)] = vc.read(path)
        return dict(utc=utc(), observed_jsonl=records, pipeline_status=statuses,
                    observed_records_are_progress_only=True)


def run_process(command, folder, output, persist):
    tracker = Progress()
    with (folder / 'stdout.log').open('x') as stdout, (folder / 'stderr.log').open('x') as stderr:
        process = subprocess.Popen(command, cwd=ROOT, stdout=stdout, stderr=stderr)
        persist(dict(pid=process.pid, **tracker.snapshot(output)))
        while True:
            try:
                result = process.wait(timeout=30)
                persist(dict(pid=process.pid, **tracker.snapshot(output)))
                return result
            except subprocess.TimeoutExpired:
                persist(dict(pid=process.pid, **tracker.snapshot(output)))


def pending_jobs():
    return [j for j in Queue(RUNTIME).status()['jobs']
            if j['status'] in ('queued', 'running', 'unknown')]


def execute(plan_path, authorization_path, context, *, regression_only=False):
    plan = vc.read(plan_path)
    verify_plan(plan)
    approval = verify_authorization(authorization_path, plan_path, plan, context)
    validate_assignment(context)
    ledger_path = LOCAL / 'execution-ledger.local.json'
    ledger = vc.read(ledger_path)
    verify_ledger(ledger, plan_path, plan)
    def persist():
        ledger['updated_utc'] = utc()
        write(ledger_path, ledger)
    for row in ledger['videos']:
        if row['execution_status'] == 'complete':
            validate_resume(row, plan)
        elif any(a.get('state') == 'running' for a in row['attempts']):
            raise ValueError('Unsettled prior attempt: inspect its PID/queue; no partial resume or duplicate execution')
    ordered = sorted(ledger['videos'], key=lambda r: (r['video_id'] not in REGRESSIONS,
                     REGRESSIONS.index(r['video_id']) if r['video_id'] in REGRESSIONS else 0))
    for row in ordered:
        if row['execution_status'] != 'not_run' or (regression_only and row['video_id'] not in REGRESSIONS):
            continue
        if row['detector_required']:
            regressions = {r['video_id']: r for r in ledger['videos'] if r['video_id'] in REGRESSIONS}
            if any(regressions.get(k, {}).get('regression_status') != 'passed' for k in REGRESSIONS):
                ledger['blocked_reason'] = 'both_cpu_regressions_must_pass_before_fresh_detector'
                persist()
                return ledger
            approval = verify_authorization(authorization_path, plan_path, plan, context, fresh=True)
        verify_plan(plan)
        # One additional CPU-only attempt is allowed. The canonical adapter's
        # stricter prohibition on automatic detector retries is preserved.
        maximum_attempts = 1 if row['detector_required'] else 2
        while len(row['attempts']) < maximum_attempts:
            if row['detector_required']:
                resource = gpu()
                row['resource_before'] = resource
                pending = pending_jobs()
                if not resource['available'] or pending:
                    row['reason'] = ('blocked_gpu_free_below_6144_mib' if not resource['available']
                                     else 'blocked_canonical_queue_pending_work')
                    ledger['blocked_reason'] = row['reason']
                    ledger['blocked_queue_job_ids'] = [j['job_id'] for j in pending]
                    persist()
                    return ledger  # Never poll resources, retry, or spin.
            attempt_no = len(row['attempts']) + 1
            folder = local_path(LOCAL / row['video_id'] / ('attempt-' + str(attempt_no)), LOCAL)
            output = local_path(RUNS / row['video_id'] / ('attempt-' + str(attempt_no)), RUNS)
            if output.exists():
                raise ValueError('New attempt output already exists; retain it and diagnose')
            folder.mkdir(parents=True, exist_ok=False)
            row['output_path'] = str(output)
            command = [sys.executable, '-m', 'sceneguard.mvp_pipeline', '--video', row['video_path'],
                       '--camera', row['camera_id'], '--scene', row['scene'], '--portal', row['portal'],
                       '--camera-registry', plan['registry_path'], '--output', str(output), '--whole']
            if row['cache']:
                command += ['--cache', row['cache']]
            else:
                for key in CONTEXT_KEYS:
                    command += ['--' + key.replace('_', '-'), context[key]]
            before = queue_snapshot(folder / 'queue-before.local.json')
            attempt = dict(number=attempt_no, state='running', command=command,
                           output_path=str(output), started_utc=utc(), progress_path=str(folder / 'progress.local.json'),
                           authorization_sha256=vc.sha256(authorization_path))
            row['attempts'].append(attempt)
            row['reason'] = 'execution_in_progress'
            persist()
            begin = time.perf_counter()
            def progress(value):
                value['elapsed_seconds'] = time.perf_counter() - begin
                write(folder / 'progress.local.json', value)
                attempt.update(last_progress_utc=value['utc'], elapsed_seconds=value['elapsed_seconds'],
                               pid=value['pid'])
                persist()
            try:
                result = run_process(command, folder, output, progress)
                row.update(exit_code=result, elapsed_seconds=time.perf_counter() - begin)
                if result != 0:
                    raise ValueError('Pipeline exit code ' + str(result))
                receipt, status, manifest = validate_complete(row, plan)
                validate_job(row, context)
                row['pipeline_status'] = status
                write(folder / 'whole-source-integrity.local.json', receipt, exclusive=True)
                if row['video_id'] in REGRESSIONS:
                    regression = regression_receipt(row)
                    write(folder / 'cpu-regression.local.json', regression, exclusive=True)
                    row.update(regression_status='passed', regression_receipt_path=str(folder / 'cpu-regression.local.json'))
                verify_plan(plan)
                completion = dict(utc=utc(), source_sha256=row['source_sha256'],
                                  analysis_revision=plan['analysis_revision'],
                                  output_sha256=artifact_bindings(output))
                completion_path = folder / 'completed-binding.local.json'
                write(completion_path, completion, exclusive=True)
                row.update(execution_status='complete', processed_seconds=row['duration_seconds'], reason=None,
                           integrity_receipt_path=str(folder / 'whole-source-integrity.local.json'),
                           completion_receipt_path=str(completion_path), completion_receipt_sha256=vc.sha256(completion_path),
                           viewer_manifest_path=str(output / 'viewer-manifest.json'),
                           viewer_manifest_sha256=vc.sha256(output / 'viewer-manifest.json'),
                           cards_path=manifest['cards_path'], frames=status['frames'],
                           source_window=manifest['source_window'], costs=costs(row))
                attempt['state'] = 'complete'
            except Exception as exc:
                attempt.update(state='failed', error_type=type(exc).__name__, error=str(exc))
                row.update(execution_status='failed', processed_seconds=0.0, reason=str(exc))
            attempt.update(finished_utc=utc(), elapsed_seconds=time.perf_counter() - begin)
            after = queue_snapshot(folder / 'queue-after.local.json')
            before_ids = {j['job_id'] for j in before['jobs']}
            jobs = [j for j in after['jobs'] if j['job_id'] not in before_ids]
            ids = {j['job_id'] for j in jobs}
            attempt['queue_provenance'] = dict(jobs=jobs, attempts=[a for a in after['attempts'] if a['job_id'] in ids])
            persist()
            verify_plan(plan)  # Changes stop the batch, never become a per-file retry.
            if attempt['state'] == 'complete':
                break
            if row['video_id'] in REGRESSIONS and 'regression' in attempt.get('error', '').lower():
                break  # A behavioral mismatch must be reviewed, not retried away.
        # Failed files remain failed; continue other files unless regression gate blocks GPU.
    ledger.pop('blocked_reason', None)
    persist()
    return ledger


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'execute'))
    parser.add_argument('--sources', type=Path, default=ROOT / 'runtime/MVP-0005/profiles/source-list.json')
    parser.add_argument('--registry', type=Path, default=ROOT / 'runtime/MVP-0005/profiles/registry.json')
    parser.add_argument('--plan', type=Path, default=LOCAL / 'execution-plan.local.json')
    parser.add_argument('--authorization', type=Path)
    parser.add_argument('--regression-only', action='store_true')
    for key in CONTEXT_KEYS:
        parser.add_argument('--' + key.replace('_', '-'))
    args = parser.parse_args()
    LOCAL.mkdir(parents=True, exist_ok=True)
    local_path(args.plan, LOCAL)
    with (LOCAL / 'runner.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == 'prepare':
            result = prepare(args.sources, args.registry, args.plan)
        else:
            context = {key: getattr(args, key) for key in CONTEXT_KEYS}
            if not args.authorization or not all(context.values()):
                parser.error('execute requires coordinator authorization and all four live queue identity fields')
            result = execute(args.plan, args.authorization, context, regression_only=args.regression_only)
        print(json.dumps(dict(videos=len(result['videos']),
              statuses=dict(Counter(r['execution_status'] for r in result['videos'])),
              plan=str(args.plan), ledger=str(LOCAL / 'execution-ledger.local.json')), indent=2))
        if args.action == 'execute' and any(r['execution_status'] in ('not_run', 'failed', 'partial')
                for r in result['videos'] if not args.regression_only or r['video_id'] in REGRESSIONS):
            raise SystemExit(2)


if __name__ == '__main__':
    main()
