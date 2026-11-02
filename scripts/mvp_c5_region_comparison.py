"""Frozen six-original C5 comparison using exact historical FCOS person bytes.

inspect/prepare never run tracking, flow, detection or scoring. execute requires a
coordinator's hash-bound CPU authorization. Historical files are always read-only.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sceneguard import video_cards as vc
from scripts.mvp_full_run import assert_clock, bindings, coverage_receipt, utc, write
from scripts.mvp_expanded_run import local_path, profile_inputs

IDS = tuple('E01_' + n for n in ('014', '016', '018', '020', '021', '038'))
LOCAL = ROOT / 'runtime/MVP-0006/execution'
RUNS = ROOT / 'outputs/validation/mvp-c5-v1/runs'
OLD = ROOT / 'outputs/validation/mvp-all-v3'
OLD_REGISTRY = ROOT / 'runtime/MVP-0005/profiles/registry.json'
OLD_PLAN = ROOT / 'runtime/MVP-0005/execution/execution-plan.local.json'
VARIANTS = ('official-zero-based', 'official-one-based', 'reviewed')
GEOMETRY = {'line', 'roi', 'selection'}
PYTHON = ROOT / '.venv-cv-batch02/bin/python'


def code_binding():
    paths = list((ROOT / 'sceneguard').rglob('*.py'))
    paths += [Path(__file__).resolve(), ROOT / 'scripts/mvp_full_run.py',
              ROOT / 'scripts/mvp_expanded_run.py',
              ROOT / 'scripts/mvp_full_evaluation_adapter.py']
    paths += list((ROOT / 'orchestration').rglob('*.py'))
    return bindings(paths)


def environment_binding():
    raw = subprocess.check_output([str(PYTHON), '-c',
        'import importlib.metadata as m,json,sys; '
        'print(json.dumps(dict(python=sys.version, packages=sorted('
        '(d.metadata["Name"],d.version) for d in m.distributions()))))'],
        cwd=ROOT, text=True)
    return json.loads(raw)


def geometry_only(before, after):
    """Identity, policy and detector thresholds cannot change with geometry."""
    if ({k: v for k, v in before.items() if k not in GEOMETRY} !=
            {k: v for k, v in after.items() if k not in GEOMETRY}):
        raise ValueError('Only line/roi/selection may differ; policy/identity is frozen')
    if set(before) != set(after):
        raise ValueError('Boundary config fields may not be added or removed')


def derived_metadata(meta, config, original, config_path):
    geometry_only(meta['config'], config)
    result = deepcopy(meta)
    result.update(config=deepcopy(config), config_sha256=vc.sha256(config_path))
    result['geometry_reuse_provenance'] = dict(
        kind='MVP-0006_geometry_only_cache_view_v1',
        original_directory=str(original),
        original_metadata_sha256=vc.sha256(original / 'run.json'),
        original_person_cache_sha256=vc.sha256(original / 'person_cache.jsonl'),
        original_boundary_config=deepcopy(meta['config']),
        changed_geometry_fields=sorted(k for k in GEOMETRY if meta['config'][k] != config[k]),
        detector_frames_this_execution=0,
        historical_metrics_scope='All inherited detector costs/settings describe original inference',
        reason='Full-frame model person returns precede project score/ROI/boundary rules')
    return result


def historical_inputs():
    """Resolve caches through the six completed original pipeline outputs only."""
    plan = vc.read(OLD_PLAN)
    source_rows = {r['video_id']: r for r in plan['videos']}
    files, rows = [OLD_PLAN, OLD_REGISTRY], []
    registry = vc.read(OLD_REGISTRY)
    for video_id in IDS:
        row = source_rows[video_id]
        folder = OLD / 'runs' / video_id / 'attempt-1'
        request = vc.read(folder / 'request.json')
        state = vc.read(folder / 'status.json')
        baseline = vc.read(folder / 'source/analysis/analysis.json')
        cache = local_path(baseline['source_paths']['cache'], ROOT / 'outputs')
        video = local_path(row['video_path'], ROOT / 'data')
        if (request['camera'] != 'C5' or request['video'] != str(video)
                or request.get('whole') is not True or state['state'] != 'analysis_complete'
                or vc.sha256(video) != row['source_sha256']):
            raise ValueError('Historical completed whole original/source binding differs')
        camera, scene, portal, _ = vc.camera_profile('C5', video, OLD_REGISTRY)
        info = dict(size=row['source_size'], time_base=row['time_base'])
        meta, frames, _, hashes = vc.validate_cached(video, camera, cache, 0., row['source_end_exclusive'], info)
        if meta['video_id'] != video_id:
            raise ValueError('Historical cache video identity differs')
        assert_clock(vc.read(row['source_clock_path']), frames)
        files.extend([video, Path(row['source_clock_path']), scene, portal,
                      cache / 'run.json', cache / 'person_cache.jsonl'])
        files.extend(p for p in folder.rglob('*') if p.is_file())
        rows.append(dict(video_id=video_id, video_path=str(video), camera_id='C5',
            source_sha256=row['source_sha256'], source_clock_path=row['source_clock_path'],
            decoded_frames=len(frames), duration_seconds=row['duration_seconds'],
            source_size=row['source_size'], time_base=row['time_base'],
            source_end_exclusive=row['source_end_exclusive'], original_output=str(folder),
            original_cache=str(cache), original_cache_sha256=hashes))
    files.append(OLD / 'evaluation-inputs/inventory.json')
    for variant in VARIANTS:
        files.extend([OLD / 'evaluation-inputs' / (variant + '.json'),
                      OLD / ('evaluation-' + variant + '-manifest.json'),
                      OLD / ('evaluation-' + variant + '-report.json')])
    return rows, bindings(files), registry


def readiness(report):
    rows, hashes, _ = historical_inputs()
    result = dict(schema_version=1, scope='MVP-0006', prepared_utc=utc(),
        status='ready_for_frozen_profiles_and_coordinator_go', execution_permitted=False,
        videos=rows, preserved_sha256=hashes, code_sha256=code_binding(),
        totals=dict(originals=6, frames=sum(r['decoded_frames'] for r in rows),
                    source_seconds=sum(r['duration_seconds'] for r in rows),
                    planned_detector_frames=0, planned_cpu_tracking_frames=sum(r['decoded_frames'] for r in rows),
                    planned_cpu_image_path_frames=sum(r['decoded_frames'] for r in rows)),
        cache_reuse=dict(valid=True, exact_original_person_bytes=True,
            original_metadata_unchanged=True, derived_metadata_required=True,
            evidence=['sceneguard/run_cv.py: full rgb frame -> model -> person cache before project score filter',
                      'sceneguard/video_cards.py: validate_cached compares entire boundary config',
                      'sceneguard/exp0034_application.py: scene line and ROI must equal camera config'],
            note='New documented cache view copies raw person bytes and replaces geometry binding only'),
        config_bindings_requiring_change=[
            'C5 scene zones.outside/inside, approach_polygon, line, static-image provenance',
            'C5 portal polygon and scene_digest',
            'C5 registry roi and legacy_boundary_config line/roi/selection, scene_path/hash, portal_path/hash',
            'New cache-view metadata config/config_sha256 with original metadata and cache hashes',
            'New pipeline request, source/image-path/decision/evidence stage bindings and output paths',
            'New immutable plan/code/profile hashes and coordinator authorization'],
        preserved=['all original caches and MVP-0005 outputs', 'FCOS/ByteTrack/rule settings',
                   'all frozen official and reviewed truth, gates, splits and unknown intervals'],
        scoring='Same frozen truth; suspicion/confirmation evidence hits and first notices separately; no new labels',
        pending=['frozen new registry path', 'independent review', 'hash-bound CPU execution authorization'],
        commands=dict(prepare=f'{PYTHON} scripts/mvp_c5_region_comparison.py prepare --registry FROZEN_REGISTRY',
                      execute=f'{PYTHON} scripts/mvp_c5_region_comparison.py execute --authorization CPU_AUTHORIZATION'))
    write(local_path(report, ROOT / 'runtime/MVP-0006'), result, exclusive=True)
    return result


def validate_registry(registry_path, rows, original):
    registry = vc.read(registry_path)
    if registry.get('schema_version') != 1 or registry['sources'] != original['sources']:
        raise ValueError('Exact original 45 source/camera/hash assignments required')
    if set(registry['cameras']) != set(original['cameras']):
        raise ValueError('Exact original eight cameras required')
    for name in original['cameras']:
        if name != 'C5' and registry['cameras'][name] != original['cameras'][name]:
            raise ValueError('Only C5 profile may change')
    camera, scene, portal, _ = vc.camera_profile('C5', rows[0]['video_path'], registry_path)
    geometry_only(original['cameras']['C5']['legacy_boundary_config'], camera['legacy_boundary_config'])
    files = profile_inputs('C5', camera, scene, portal, registry_path, rows[0]['source_size'])
    return camera, scene, portal, files


def prepare(registry_path):
    plan_path = LOCAL / 'plan.json'
    if plan_path.exists() or (LOCAL / 'ledger.json').exists():
        raise ValueError('Existing frozen plan/ledger cannot be replaced')
    registry_path = local_path(registry_path, ROOT / 'runtime/MVP-0006')
    rows, preserved, original = historical_inputs()
    camera, scene, portal, files = validate_registry(registry_path, rows, original)
    config = camera['legacy_boundary_config']
    config_path = LOCAL / 'boundary-config.json'
    write(config_path, config, exclusive=True)
    files += [registry_path, config_path, PYTHON.parent.parent / 'pyvenv.cfg', PYTHON.resolve()]
    files += list(registry_path.parent.glob('*.json'))
    for row in rows:
        cache = LOCAL / 'cache-views' / row['video_id']
        if cache.exists():
            raise ValueError('Fresh cache view required; never overwrite partial preparation')
        cache.mkdir(parents=True)
        original_cache = Path(row['original_cache'])
        shutil.copyfile(original_cache / 'person_cache.jsonl', cache / 'person_cache.jsonl')
        meta = derived_metadata(vc.read(original_cache / 'run.json'), config, original_cache, config_path)
        write(cache / 'run.json', meta, exclusive=True)
        _, frames, _, hashes = vc.validate_cached(Path(row['video_path']), camera, cache,
            0., row['source_end_exclusive'], dict(size=row['source_size'], time_base=row['time_base']))
        assert_clock(vc.read(row['source_clock_path']), frames)
        if hashes['cache'] != row['original_cache_sha256']['cache']:
            raise ValueError('Derived view changed raw detector bytes')
        row.update(cache=str(cache), scene=str(scene), portal=str(portal),
                   output_path=str(RUNS / row['video_id'] / 'attempt-1'))
        if Path(row['output_path']).exists():
            raise ValueError('Fresh MVP-0006 output required')
        files += [cache / 'run.json', cache / 'person_cache.jsonl']
    if bindings(preserved) != preserved:
        raise ValueError('Historical files changed while preparing')
    code = code_binding()
    plan = dict(schema_version=1, scope='MVP-0006', frozen_utc=utc(),
        registry_path=str(registry_path), videos=rows, preserved_sha256=preserved,
        input_sha256=bindings(files), code_sha256=code,
        analysis_code_digest='MVP-0006-sha256:' + vc.fingerprint(code),
        pipeline_code_sha256={str(p.relative_to(ROOT)): vc.sha256(p)
                             for p in sorted((ROOT / 'sceneguard').rglob('*.py'))},
        python=str(PYTHON), cpu_only=True, detector_frames_planned=0,
        environment=environment_binding(),
        new_labels=False, comparison_against='preserved_MVP-0005_outputs')
    write(plan_path, plan, exclusive=True)
    return plan


def verify_plan(plan):
    if plan['code_sha256'] != code_binding():
        raise ValueError('Frozen code changed')
    for key in ('preserved_sha256', 'input_sha256'):
        if bindings(plan[key]) != plan[key]:
            raise ValueError('Frozen source/profile/cache/truth/old-output bytes changed')
    if plan['environment'] != environment_binding():
        raise ValueError('Frozen CPU Python/package environment changed')


def verify_authorization(path, plan_path, plan):
    approval = vc.read(path)
    required = dict(plan_sha256=vc.sha256(plan_path), execution_permitted=True,
                    cpu_only=True, profiles_code_frozen=True,
                    independent_review_accepted=True, analysis_code_digest=plan['analysis_code_digest'])
    if any(approval.get(k) != v for k, v in required.items()):
        raise ValueError('Coordinator frozen-profile/code CPU authorization is absent or mismatched')
    review = approval.get('independent_review', {})
    if not review.get('path') or vc.sha256(review['path']) != review.get('sha256'):
        raise ValueError('Independent review artifact hash differs')


def command(plan, row):
    return [plan['python'], '-m', 'sceneguard.mvp_pipeline', '--video', row['video_path'],
            '--camera', 'C5', '--scene', row['scene'], '--portal', row['portal'],
            '--camera-registry', plan['registry_path'], '--cache', row['cache'],
            '--whole', '--output', row['output_path']]


def compare(plan, ledger):
    """Copy immutable gold fields from the earlier manifest, validate new outputs."""
    from scripts.mvp_full_evaluation_adapter import adapt_execution
    from sceneguard.accuracy_evaluation import evaluate, aggregate
    inventory = vc.read(OLD / 'evaluation-inputs/inventory.json')
    inventory = {r['video_id']: r for r in inventory['videos']}
    executions = {r['video_id']: r for r in ledger['videos']}
    comparison = dict(scope='MVP-0006', no_new_labels=True,
                      interpretation='Region sensitivity on reused cameras, not independent generalization', variants={})
    for variant in VARIANTS:
        path = OLD / ('evaluation-' + variant + '-manifest.json')
        old = vc.read(path)
        baseline = deepcopy(old)
        baseline['videos'] = [v for v in baseline['videos'] if v['video_id'] in IDS]
        current = deepcopy(baseline)
        current['analysis_revision'] = plan['analysis_code_digest']
        current['comparison_truth_source_manifest_sha256'] = vc.sha256(path)
        for row in current['videos']:
            row.update(adapt_execution(inventory[row['video_id']], executions[row['video_id']],
                                       plan['pipeline_code_sha256']))
        before, after = evaluate(baseline), evaluate(current)
        for name, value in [('before-manifest', baseline), ('after-manifest', current),
                            ('before-report', before), ('after-report', after)]:
            write(LOCAL / 'evaluation' / (variant + '-' + name + '.json'), value, exclusive=True)
        comparison['variants'][variant] = {mode: dict(
            before=aggregate(before['modes'][mode]['by_video']),
            after=aggregate(after['modes'][mode]['by_video']),
            per_video_before=before['modes'][mode]['by_video'],
            per_video_after=after['modes'][mode]['by_video']) for mode in ('suspicion', 'confirmation')}
    write(LOCAL / 'comparison.json', comparison, exclusive=True)
    return comparison


def execute(authorization):
    plan_path = LOCAL / 'plan.json'
    plan = vc.read(plan_path)
    verify_plan(plan)
    verify_authorization(authorization, plan_path, plan)
    with (LOCAL / '.execution.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        ledger_path = LOCAL / 'ledger.json'
        if ledger_path.exists():
            ledger = vc.read(ledger_path)
            if ledger['plan_sha256'] != vc.sha256(plan_path):
                raise ValueError('Ledger plan differs')
        else:
            ledger = dict(plan_sha256=vc.sha256(plan_path), videos=[])
        for row in plan['videos']:
            if any(r['video_id'] == row['video_id'] for r in ledger['videos']):
                if next(r for r in ledger['videos'] if r['video_id'] == row['video_id'])['execution_status'] == 'complete':
                    continue
                raise ValueError('Previous failure needs coordinator diagnosis; automatic retry disabled')
            verify_plan(plan)
            verify_authorization(authorization, plan_path, plan)
            started = time.perf_counter()
            entry = dict(video_id=row['video_id'], execution_status='failed', output_path=row['output_path'])
            try:
                with (LOCAL / (row['video_id'] + '.log')).open('x') as log:
                    subprocess.run(command(plan, row), cwd=ROOT, check=True, stdout=log,
                        stderr=subprocess.STDOUT, env=dict(os.environ, CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='2'))
                state = vc.read(Path(row['output_path']) / 'status.json')
                count = row['decoded_frames']
                if (state['state'] != 'analysis_complete' or state.get('source_mode') != 'saved_cache'
                        or state.get('detector_frames_this_execution') != 0
                        or state.get('tracker_frames_this_execution') != count
                        or state.get('cpu_image_path_frames_this_execution') != count):
                    raise ValueError('Expected saved detector cache and fresh whole-source CPU tracking/features')
                receipt = coverage_receipt(row)
                write(LOCAL / (row['video_id'] + '-native-coverage.json'), receipt, exclusive=True)
                verify_plan(plan)
                entry.update(execution_status='complete', processed_seconds=row['duration_seconds'],
                             pipeline_status=state, detector_cache_frames_reused=count,
                             cpu_tracking_frames=count, cpu_image_path_frames=count)
            except Exception as exc:
                entry.update(reason=str(exc))
                raise
            finally:
                entry['wrapper_wall_seconds'] = time.perf_counter() - started
                ledger['videos'].append(entry)
                write(ledger_path, ledger)
        verify_plan(plan)
        result = compare(plan, ledger)
        verify_plan(plan)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('inspect')
    p.add_argument('--report', type=Path, default=ROOT / 'runtime/MVP-0006/preparation.json')
    p = sub.add_parser('prepare')
    p.add_argument('--registry', type=Path, required=True)
    p = sub.add_parser('execute')
    p.add_argument('--authorization', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'inspect':
        result = readiness(args.report)
    elif args.action == 'prepare':
        result = prepare(args.registry)
    else:
        result = execute(args.authorization)
    print(json.dumps(dict(action=args.action, scope='MVP-0006',
                          videos=len(result.get('videos', IDS))), indent=2))


if __name__ == '__main__':
    main()
