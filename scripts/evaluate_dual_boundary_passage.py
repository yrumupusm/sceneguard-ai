"""Frozen saved-measurement evaluation; prepare never invokes candidate rules.

Run with canonical .venv-cv-batch02/bin/python. See DUAL_BOUNDARY_EVALUATION.md.
Only ignored fresh output directories may receive measurements or snapshots.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

BEFORE = Path('outputs/validation/continuation-crossing-v1/default-selected-001')
DRAFT = Path('outputs/region-revisions/inside-boundary-draft-20261104-v1/draft-manifest.json')
C5 = {14, 16, 18, 20, 21, 38}
OUTWARD = (13, 15, 21, 28, 34, 36, 43, 44, 45)
MODES = ('suspicion', 'confirmation')
PROTOCOL = dict(
    id='DUAL-BOUNDARY-SAVED-EVENT-v1',
    baseline=str(BEFORE), baseline_side='after',
    official_videos=45, official_events=52, baseline_confirmation_tp=39,
    baseline_suspicion_tp=51, baseline_early_confirmation_notices=8,
    matching='unchanged accuracy_evaluation: one-to-one maximum cardinality; same gate; actual evidence in half-open official interval',
    first_notice='separate per-card intent; keep every early/unreviewed notice even if later evidence matches',
    timing='first matching evidence and first notice reported separately; neither is verified physical onset delay',
    negative_truth='only frozen verified_non_event_intervals; unreviewed time remains unknown',
    precision='overall precision/F1 remain null when unscored predictions exist; no full accuracy claim',
    unresolved_006='retained, excluded from resolved52; one unresolved reference',
    hold_008='official reference retained; semantic human review hold remains',
    outward_focus=list(OUTWARD),
    outward_cautions={'028': 'late confirmation can remain after official end',
                      '036': 'early official event distinct from later confirmed event',
                      '045': 'simultaneous bidirectional mixed context; not person-specific direction truth'},
    user_010_approximate_onset=63.0,
    user_010_onset_precision='approximate user climbing onset only, not a new exact truth interval',
    origin_association='retain raw decisions and unconfirmed evidence with missing/ambiguous origin or association; never infer missing path',
    candidate_policy='single frozen implementation and geometry; no threshold sweep or outcome-directed tuning',
    source_mode='saved_measurement_rules_replay_not_fresh_inference',
    new_detector_tracker_flow_model_calls=0,
)


def read(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'Duplicate JSON key: {key}')
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def hashes(paths):
    return {str(p.resolve()): sha(p) for p in sorted(set(map(Path, paths)))}


def verify_hashes(expected):
    changed = [name for name, digest in expected.items()
               if not Path(name).is_file() or sha(name) != digest]
    if changed:
        raise ValueError(f'Protected inputs changed: {changed}')


def resolve_input(name, data_root):
    path = Path(name)
    if not path.is_absolute():
        return data_root / path
    # Requests bind canonical absolute paths. Relocate only beneath the declared
    # historical root when --data-root points at a copied canonical data tree.
    historical = Path('/home/jhc7484/dev/sceneguard-ai')
    if path.is_relative_to(historical):
        return data_root / path.relative_to(historical)
    raise ValueError(f'Archived input outside canonical data root: {path}')


def source_paths(number, data_root):
    video = f'E01_{number:03d}'
    batch = 'mvp-c5-v1' if number in C5 else 'mvp-all-v3'
    folder = data_root / f'outputs/validation/{batch}/runs/{video}/attempt-1'
    request = read(folder / 'request.json')
    scene, portal = (resolve_input(request[key], data_root) for key in ('scene', 'portal'))
    paths = [folder / 'request.json', folder / 'source/analysis/analysis.json',
             folder / 'image-paths/frame-evidence.jsonl', data_root / BEFORE / 'videos' / video / 'cards.json',
             scene, portal]
    # All archived geometry/registry consumed or referenced by the request stays
    # immutable. Original media is not opened by a saved-measurement replay.
    for name, expected in request['input_sha256'].items():
        path = resolve_input(name, data_root)
        if path.suffix == '.json':
            if sha(path) != expected:
                raise ValueError(f'Archived geometry binding changed: {path}')
            paths.append(path)
    return folder, request, paths


def git_revision(root, revision='HEAD'):
    return subprocess.check_output(['git', 'rev-parse', '--verify', revision + '^{commit}'],
                                   cwd=root, text=True).strip()


def snapshot_code(code_root, output, revision=None):
    paths = sorted((code_root / 'sceneguard').rglob('*.py'))
    paths += [code_root / 'scripts/mvp_full_evaluation_adapter.py', Path(__file__).resolve()]
    # Runner may live in the evaluator worktree while implementation lives in
    # another checkout. Its own bytes are separately bound, never substituted.
    named = {str(p.relative_to(code_root)): p for p in paths[:-1]}
    named['scripts/evaluate_dual_boundary_passage.py'] = paths[-1]
    before = {name: sha(path) for name, path in named.items()}
    resolved = git_revision(code_root, revision or 'HEAD')
    if revision:
        committed_names = subprocess.check_output(
            ['git', 'ls-tree', '-r', '--name-only', resolved, '--', 'sceneguard'],
            cwd=code_root, text=True).splitlines()
        committed_names = {name for name in committed_names if name.endswith('.py')}
        if committed_names != {name for name in named if name.startswith('sceneguard/')}:
            raise ValueError('Snapshot package file set differs from frozen implementation revision')
        for name, path in named.items():
            if name == 'scripts/evaluate_dual_boundary_passage.py':
                continue
            committed = subprocess.check_output(['git', 'show', f'{resolved}:{name}'], cwd=code_root)
            if hashlib.sha256(committed).hexdigest() != before[name]:
                raise ValueError(f'Implementation differs from frozen revision: {name}')
    for name, path in named.items():
        target = output / 'code_snapshot' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    if before != {name: sha(path) for name, path in named.items()}:
        raise ValueError('Source changed during snapshot')
    return dict(revision=resolved, revision_verified=bool(revision), sha256=before,
                original_paths={name: str(path) for name, path in named.items()})


def load_api(snapshot, pipeline=False):
    snapshot = Path(snapshot).resolve()
    for name, module in list(sys.modules.items()):
        if name == 'sceneguard' or name.startswith('sceneguard.'):
            if not Path(module.__file__).resolve().is_relative_to(snapshot):
                raise ValueError(f'Refusing previously imported non-snapshot module: {name}')
    sys.path.insert(0, str(snapshot))
    from sceneguard.accuracy_evaluation import evaluate, aggregate
    # Use a unique module name to avoid any installed scripts package.
    spec = importlib.util.spec_from_file_location('dual_boundary_snapshot_adapter',
            snapshot / 'scripts/mvp_full_evaluation_adapter.py')
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)
    api = dict(evaluate=evaluate, aggregate=aggregate, extract=adapter.extract_predictions)
    if pipeline:
        from sceneguard.mvp_pipeline import analyze_observations
        from sceneguard.exp0036_application import make_bundle
        api.update(analyze=analyze_observations, bundle=make_bundle)
    for name, module in list(sys.modules.items()):
        if name == 'sceneguard' or name.startswith('sceneguard.'):
            if not Path(module.__file__).resolve().is_relative_to(snapshot):
                raise ValueError(f'Imported module escaped snapshot: {name}')
    return api


def aggregate_report(report, api):
    return {mode: api['aggregate'](report['modes'][mode]['by_video']) for mode in MODES}


def validate_before(data_root, api):
    manifest = read(data_root / BEFORE / 'after-manifest.json')
    saved_report = read(data_root / BEFORE / 'after-report.json')
    videos = manifest['videos']
    if ({v['video_id'] for v in videos} != {f'E01_{n:03d}' for n in range(1, 46)}
            or len(videos) != 45 or sum(len(v['events']) for v in videos) != 52):
        raise ValueError('BEFORE must retain all45 and official52')
    unresolved = next(v for v in videos if v['video_id'] == 'E01_006')
    if unresolved['truth_basis'] != 'unresolved' or unresolved['events'] or unresolved['unresolved_reference_events'] != 1:
        raise ValueError('006 unresolved reference changed')
    if not next(v for v in videos if v['video_id'] == 'E01_008')['events']:
        raise ValueError('008 official truth removed despite semantic hold')
    for video in videos:
        cards = read(data_root / BEFORE / 'videos' / video['video_id'] / 'cards.json')
        if api['extract'](cards) != video['predictions']:
            raise ValueError(f"BEFORE cards differ from exact after-manifest: {video['video_id']}")
    calculated = api['evaluate'](manifest)
    for key in ('inventory', 'protocol', 'modes'):
        if calculated[key] != saved_report[key]:
            raise ValueError(f'BEFORE after-report differs from recomputation: {key}')
    totals = aggregate_report(calculated, api)
    if (totals['confirmation']['counts']['tp'] != 39
            or totals['suspicion']['counts']['tp'] != 51
            or totals['confirmation']['counts']['early_first_notices_for_matched_events'] != 8):
        raise ValueError('BEFORE is not selected 39/52, 51/52, early8 baseline')
    return manifest, calculated, totals


def notice_relations(video, scored, mode):
    matches = {r['prediction_id']: r for r in scored['matches'] if r['outcome'] == 'tp'}
    truths = {r['id']: r for r in video['events']}
    result = []
    for prediction in video['predictions']:
        for notice in prediction['notifications']:
            if notice['kind'] != mode:
                continue
            match = matches.get(prediction['id'])
            truth = truths[match['truth_id']] if match else None
            at = notice['pts']
            result.append(dict(video_id=video['video_id'], prediction_id=prediction['id'], **notice,
                matched_truth_id=truth['id'] if truth else None,
                first_matching_evidence_pts=match['first_matching_evidence_pts'] if match else None,
                matched_reference_start=truth['start'] if truth else None,
                before_matched_reference_start=bool(truth and at < truth['start']),
                seconds_before_matched_reference_start=truth['start'] - at if truth and at < truth['start'] else None,
                containing_official_truth_ids=[t['id'] for t in truths.values()
                    if t['gate_id'] == prediction['gate_id'] and t['start'] <= at < t['end']],
                in_verified_negative=any(m['gate_id'] == prediction['gate_id'] and m['start'] <= at < m['end']
                    for m in video['verified_non_event_intervals']),
                offset_from_approximate_user_010_onset_seconds=at - 63.0 if video['video_id'] == 'E01_010' and mode == 'confirmation' else None))
    return result


def comparison(before, after, reports):
    """Compare identities only within each report; matching can regroup cards."""
    new_by_video = {v['video_id']: v for v in after['videos']}
    scored = {label: {mode: {v['video_id']: v for v in report['modes'][mode]['by_video']}
                      for mode in MODES} for label, report in reports.items()}
    events, notices, misses, per_video = [], {label: {} for label in reports}, [], []
    for video in before['videos']:
        vid = video['video_id']; new = new_by_video[vid]
        # No truth, interval, coverage, negative mask or unresolved edits allowed.
        if {k: v for k, v in video.items() if k not in ('predictions', 'execution_binding')} != {
                k: v for k, v in new.items() if k not in ('predictions', 'execution_binding')}:
            raise ValueError(f'Candidate changed frozen truth or coverage: {vid}')
        row = dict(video_id=vid, truth_basis=video['truth_basis'], official_events=video['events'])
        for mode in MODES:
            pairs = {}
            for label, item in [('before', video), ('after', new)]:
                result = scored[label][mode][vid]
                row[f'{label}_{mode}_counts'] = result['counts']
                pairs[label] = {m['truth_id']: m for m in result['matches'] if m['outcome'] == 'tp'}
                notices[label].setdefault(mode, []).extend(notice_relations(item, result, mode))
            for truth in video['events']:
                matched = {label: pairs[label].get(truth['id']) for label in pairs}
                entry = dict(video_id=vid, mode=mode, truth_id=truth['id'], reference=truth,
                    outcome='retained' if all(matched.values()) else 'gained' if matched['after'] else 'lost' if matched['before'] else 'missed',
                    before=matched['before'], after=matched['after'])
                for label in pairs:
                    match = matched[label]
                    entry[label + '_first_confirmation_or_suspicion_notice_pts'] = next((
                        n['pts'] for n in notices[label][mode]
                        if n['video_id'] == vid and match and n['prediction_id'] == match['prediction_id']), None)
                old_notice = entry['before_first_confirmation_or_suspicion_notice_pts']
                new_notice = entry['after_first_confirmation_or_suspicion_notice_pts']
                entry['first_notice_delta_seconds'] = new_notice - old_notice if old_notice is not None and new_notice is not None else None
                entry['matching_evidence_delta_seconds'] = (
                    matched['after']['first_matching_evidence_pts'] - matched['before']['first_matching_evidence_pts']
                    if all(matched.values()) else None)
                events.append(entry)
                if mode == 'confirmation' and not matched['after']:
                    misses.append(dict(video_id=vid, **truth))
        per_video.append(row)
    focus = [dict(video_id=f'E01_{number:03d}',
                  interpretation=PROTOCOL['outward_cautions'].get(f'{number:03d}', 'prior outward discussion focus; not person-level truth'),
                  events=[e for e in events if e['video_id'] == f'E01_{number:03d}'],
                  confirmation_notices={label: [n for n in notices[label]['confirmation'] if n['video_id'] == f'E01_{number:03d}'] for label in notices})
             for number in OUTWARD if f'E01_{number:03d}' in new_by_video]
    return dict(per_event=events, per_video=per_video, notices=notices,
                early_first_confirmation_notices={label: [n for n in data['confirmation'] if n['before_matched_reference_start']]
                    for label, data in notices.items()},
                user_010_approximate_onset=dict(approximate_pts=63.0, exact_truth=False,
                    provenance='docs/DUAL_BOUNDARY_PASSAGE_PLAN.md; approximate user climbing onset',
                    notices={label: [n for n in data['confirmation'] if n['video_id'] == 'E01_010'] for label, data in notices.items()}),
                outward_focus=focus, remaining_confirmation_misses=misses,
                unresolved_006_retained=True, semantic_008_hold_retained=True)


def build_profiles(numbers, data_root, output, scene_key):
    if not scene_key or not scene_key.isidentifier():
        raise ValueError('Explicit frozen optional scene key required')
    draft = read(data_root / DRAFT)
    cameras = {row['camera']: row for row in draft['cameras']}
    profiles = {}
    for number in numbers:
        _, request, paths = source_paths(number, data_root)
        camera = request['camera']; geometry = cameras[camera]
        if f'{number:03d}' not in geometry['group_videos']:
            raise ValueError('Draft camera mapping does not include source')
        scene = read(paths[4]); line = geometry['draft_normalized']
        if scene_key in scene:
            raise ValueError('Optional scene key already exists in archived scene')
        if len(line) < 2 or any(len(p) != 2 or any(type(x) not in (int, float) or not 0 <= x <= 1 for x in p) for p in line):
            raise ValueError('Normalized reviewed draft polyline required')
        scene[scene_key] = deepcopy(line)
        target = output / 'profiles' / f'{camera}-scene.json'
        if camera not in profiles:
            save(target, scene)
            portal = output / 'profiles' / f'{camera}-portal.json'
            shutil.copyfile(paths[5], portal)
            profiles[camera] = dict(scene=str(target.resolve()), portal=str(portal.resolve()),
                                    scene_key=scene_key, exact_draft_polyline=line,
                                    archived_scene=str(paths[4]), archived_portal=str(paths[5]))
        elif read(target) != scene or sha(profiles[camera]['portal']) != sha(paths[5]):
            raise ValueError('One camera has conflicting source geometry')
    save(output / 'profiles/profile-manifest.json', profiles)
    return profiles


def unconfirmed_evidence(result):
    return dict(
        seed_decisions=[row for row in result.get('seed_decisions', []) if not row.get('automatic_confirmation')],
        evidence=[row for row in result['cards']['evidence'] if row.get('first_confirmation_pts') is None],
        note='Raw rows retained with their actual reasons/binding; absent origin or association is unknown, never inferred or silently filtered')


def worker(job_path):
    started = time.perf_counter(); cpu_started = time.process_time()
    job = read(job_path); snapshot = Path(job['snapshot'])
    api = load_api(snapshot, pipeline=True)
    verify_hashes(job['protected_sources'])
    number = job['number']; data_root = Path(job['data_root'])
    folder, request, paths = source_paths(number, data_root)
    video = f'E01_{number:03d}'
    baseline = read(paths[1])
    with paths[2].open() as stream:
        frames = [json.loads(line) for line in stream]
    profile = job['profile']
    scope = dict(session_id=f'dual-boundary-passage-v1-{video}', camera_id=request['camera'], gate_id=request['camera'] + '_fence')
    bundle = api['bundle'](baseline, scope['camera_id'], scope['gate_id'], scope['session_id'])
    result = api['analyze'](baseline, bundle, frames, read(profile['scene']), read(profile['portal']), scope, scope['session_id'])
    # Do not discard intermediate or unknown rule diagnostics.
    target = Path(job['target']); target.mkdir()
    for key, value in result.items():
        save(target / (key + '.json'), value)
    save(target / 'after-predictions.json', api['extract'](result['cards']))
    save(target / 'unconfirmed-evidence.json', unconfirmed_evidence(result))
    imports = {name: str(Path(module.__file__).resolve()) for name, module in sys.modules.items()
               if name == 'sceneguard' or name.startswith('sceneguard.')}
    if any(not Path(path).is_relative_to(snapshot) for path in imports.values()):
        raise ValueError('Runtime import escaped snapshot')
    calls = result['cards'].get('rule_stage_calls', {})
    if any(calls.values()):
        raise ValueError(f'Unexpected inference stage calls: {calls}')
    verify_hashes(job['protected_sources'])
    summary = dict(video_id=video, measurement_source=str(folder),
        wall_seconds=time.perf_counter() - started, process_cpu_seconds=time.process_time() - cpu_started,
        new_detector_calls=0, new_tracker_calls=0, new_flow_calls=0, imports=imports,
        unconfirmed_evidence=len(unconfirmed_evidence(result)['evidence']))
    save(target / 'summary.json', summary)
    print(json.dumps(summary), flush=True)


def run_job(job_path):
    job = read(job_path)
    environment = dict(os.environ)
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        environment[key] = '1'
    result = subprocess.run([sys.executable, '-I', str(Path(job['snapshot']) / 'scripts/evaluate_dual_boundary_passage.py'),
                             '--_worker', str(job_path)], env=environment, text=True, capture_output=True)
    # Rule output can be large; retain local logs instead of terminal flooding.
    Path(str(job_path) + '.stdout').write_text(result.stdout)
    Path(str(job_path) + '.stderr').write_text(result.stderr)
    if result.returncode:
        raise RuntimeError(f'Worker {job["number"]:03d} exited {result.returncode}; see {job_path}.stderr')
    return read(Path(job['target']) / 'summary.json')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=Path, default=Path('/home/jhc7484/dev/sceneguard-ai'))
    parser.add_argument('--code-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--mode', choices=('prepare', 'replay'), default='prepare')
    parser.add_argument('--videos', type=int, nargs='+', help='subset; omitted means full45')
    parser.add_argument('--workers', type=int, choices=(1, 2, 4), default=4)
    parser.add_argument('--implementation-revision', help='required frozen commit for replay')
    parser.add_argument('--scene-key', help='optional scene key agreed with rule worker; required for replay')
    parser.add_argument('--_worker', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args._worker:
        worker(args._worker); return
    if not args.output:
        parser.error('--output is required and must be fresh')
    if args.mode == 'replay' and (not args.implementation_revision or not args.scene_key):
        parser.error('replay requires exact --implementation-revision and --scene-key from coordinator')
    numbers = args.videos or list(range(1, 46))
    if len(numbers) != len(set(numbers)) or any(not 1 <= n <= 45 for n in numbers):
        parser.error('videos must be unique numbers in 1..45')
    data_root, code_root, output = args.data_root.resolve(), args.code_root.resolve(), args.output.absolute()
    if output.is_symlink() or any(p.is_symlink() for p in output.parents):
        parser.error('output symlinks are forbidden')
    output = output.resolve()
    if not output.is_relative_to(data_root / 'outputs/validation/dual-boundary-passage-v1'):
        parser.error('output must be beneath data-root/outputs/validation/dual-boundary-passage-v1')
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter(); cpu_started = time.process_time()
    # Freeze this before baseline inspection and all candidate execution.
    save(output / 'evaluation-protocol.json', PROTOCOL)
    provenance = dict(mode=args.mode, source_mode=PROTOCOL['source_mode'], selected_videos=numbers,
                      full45_requested=set(numbers) == set(range(1, 46)), errors={},
                      protocol_sha256=sha(output / 'evaluation-protocol.json'), candidate_replay_executed=False)
    protected = {}; code = None; geometry_snapshot_hashes = {}
    generated_input_hashes = {str(output / 'evaluation-protocol.json'): provenance['protocol_sha256']}
    try:
        code = snapshot_code(code_root, output, args.implementation_revision)
        provenance['implementation'] = code
        protected_paths = [data_root / BEFORE / name for name in
                           ('after-manifest.json', 'after-report.json', 'summary.json', 'provenance.json')]
        protected_paths += [data_root / DRAFT]
        sources = {}
        for number in range(1, 46):
            folder, request, paths = source_paths(number, data_root)
            protected_paths.extend(paths)
            sources[number] = dict(folder=str(folder), request=request, paths=paths)
        protected = hashes(protected_paths)
        historical = read(data_root / BEFORE / 'provenance.json')['protected_sources']
        for number, source in sources.items():
            for path in source['paths']:
                name = str(path.relative_to(data_root))
                if path.name == 'cards.json':
                    continue  # Selected cards are bound by exact selected manifest/report.
                if name in historical and protected[str(path.resolve())] != historical[name]:
                    raise ValueError(f'Saved measurement differs from selected baseline binding: {name}')
                if path.name in ('request.json', 'analysis.json', 'frame-evidence.jsonl') and name not in historical:
                    raise ValueError(f'Saved measurement lacks selected baseline provenance: {name}')
        provenance['protected_sources'] = protected
        for path in sorted({p for s in sources.values() for p in s['paths'][4:]}):
            target = output / 'archived_geometry_snapshot' / path.relative_to(data_root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            geometry_snapshot_hashes[str(target)] = protected[str(path.resolve())]
        provenance['archived_geometry_snapshot_sha256'] = geometry_snapshot_hashes
        api = load_api(output / 'code_snapshot')
        before, before_report, totals = validate_before(data_root, api)
        for video in before['videos']:
            number = int(video['video_id'][-3:]); request = sources[number]['request']
            if video['video_sha256'] != request['input_sha256'][request['video']]:
                raise ValueError('Saved source video hash binding differs')
        save(output / 'before-manifest.json', before)
        save(output / 'before-report.json', before_report)
        save(output / 'before-audit.json', dict(aggregate=totals,
            comparison_to_itself= comparison(before, before, {'before': before_report, 'after': before_report}),
            note='Baseline consistency only; after in self-comparison is the identical baseline, not candidate results'))
        provenance.update(before_consistent=True, before_aggregate=totals)
        if args.mode == 'prepare':
            provenance['status'] = 'prepared_only_no_candidate_replay'
        else:
            profiles = build_profiles(numbers, data_root, output, args.scene_key)
            protected.update(hashes(list((output / 'profiles').rglob('*.json'))))
            provenance['protected_sources'] = protected
            # Candidate configuration exists before first process is launched.
            save(output / 'execution-plan.json', dict(implementation=code,
                protocol_sha256=provenance['protocol_sha256'], profiles=profiles,
                protected_sources=protected, videos=numbers, workers=args.workers))
            jobs = []
            for number in numbers:
                job_path = output / 'jobs' / f'E01_{number:03d}.json'
                save(job_path, dict(snapshot=str(output / 'code_snapshot'), data_root=str(data_root),
                    target=str(output / 'videos' / f'E01_{number:03d}'), number=number,
                    profile=profiles[sources[number]['request']['camera']],
                    protected_sources={str(p.resolve()): protected[str(p.resolve())]
                        for p in sources[number]['paths']} | hashes(list((output / 'profiles').rglob('*.json')))))
                jobs.append(job_path)
            generated_input_hashes.update(hashes([output / 'execution-plan.json', *jobs]))
            provenance['generated_execution_input_sha256'] = generated_input_hashes
            (output / 'videos').mkdir()
            provenance['candidate_replay_executed'] = True
            completed = []
            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                futures = {executor.submit(run_job, path): path.stem for path in jobs}
                for future in as_completed(futures):
                    vid = futures[future]
                    try:
                        completed.append(future.result())
                        print(json.dumps(dict(completed=vid, total=len(completed))), flush=True)
                    except Exception:
                        provenance['errors'][vid] = traceback.format_exc()
            save(output / 'per-video-runtime.json', completed)
            provenance['completed_videos'] = len(completed)
            provenance['sum_worker_process_cpu_seconds'] = sum(r['process_cpu_seconds'] for r in completed)
            if provenance['errors']:
                raise RuntimeError('Incomplete replay; candidate coverage not declared complete')
            after = deepcopy(before)
            after['analysis_revision'] = f'dual-boundary-passage-v1-{code["revision"]}'
            after['videos'] = [v for v in after['videos'] if int(v['video_id'][-3:]) in numbers]
            for video in after['videos']:
                video['predictions'] = read(output / 'videos' / video['video_id'] / 'after-predictions.json')
                video['execution_binding'] = dict(measurement_mode='saved_real_measurements',
                    decision_mode='new_cpu_rules_replay', new_inference=False)
            selected_before = deepcopy(before)
            selected_before['videos'] = [v for v in before['videos'] if int(v['video_id'][-3:]) in numbers]
            selected_before_report = api['evaluate'](selected_before)
            after_report = api['evaluate'](after)
            save(output / 'after-manifest.json', after); save(output / 'after-report.json', after_report)
            save(output / 'comparison.json', comparison(selected_before, after,
                 {'before': selected_before_report, 'after': after_report}))
            save(output / 'summary.json', dict(source_mode=PROTOCOL['source_mode'],
                official_full45_aggregate_computed=provenance['full45_requested'],
                selected_videos=numbers, selected_reference_events=sum(len(v['events']) for v in after['videos']),
                aggregate={label: aggregate_report(report, api) for label, report in
                    [('before', selected_before_report), ('after', after_report)]},
                note=('full45 and official52 retained; no full accuracy or fresh inference claim'
                      if provenance['full45_requested'] else
                      'subset is not official52 full45 evaluation; no full accuracy or fresh inference claim')))
            provenance['status'] = 'replay_complete'
    except Exception:
        provenance['status'] = 'failed'
        provenance['errors']['runner'] = traceback.format_exc()
        raise
    finally:
        try:
            verify_hashes(protected)
            verify_hashes(generated_input_hashes)
            provenance['protected_sources_unchanged'] = True
            if code:
                original_hashes = {path: code['sha256'][name] for name, path in code['original_paths'].items()}
                verify_hashes(original_hashes)
                verify_hashes({str(output / 'code_snapshot' / name): digest for name, digest in code['sha256'].items()})
                verify_hashes(geometry_snapshot_hashes)
                provenance['source_and_snapshot_unchanged'] = True
        except Exception:
            provenance['status'] = 'failed'
            provenance['errors']['preservation'] = traceback.format_exc()
            raise
        finally:
            provenance.update(wall_seconds=time.perf_counter() - started,
                              parent_process_cpu_seconds=time.process_time() - cpu_started)
            save(output / 'provenance.json', provenance)
    print(json.dumps(dict(status=provenance['status'], output=str(output),
                          candidate_replay_executed=provenance['candidate_replay_executed'])), flush=True)


if __name__ == '__main__':
    main()
