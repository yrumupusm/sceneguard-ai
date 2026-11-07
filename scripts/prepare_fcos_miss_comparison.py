"""CPU-only full-video FCOS cache inventory and proposal-independent EXP-0066 plans.

Reads saved post-internal-filter person returns, never a detector or image tensor.
Empty outputs and tracking gaps are not automatically actor-specific detector FNs.
"""
import argparse
from bisect import bisect_left
from collections import Counter
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK_SHA = '3799ae3eee427b60e698b21f6ee958ac5306eacba07b5d85e4c35dbfa6457b40'
MODEL_SHA = '99b0c9b7cfb1527d782db86b91d207f00547c792fb4103fc612b651d0a07b9e7'
STAGE = 'model_return_after_internal_filters_nms_global_cap_before_project_score'


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def pairs(values):
    result = {}
    for key, value in values:
        if key in result:
            raise ValueError('Duplicate JSON key: ' + key)
        result[key] = value
    return result


def parse(raw):
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def read(path, receipts, expected=None):
    path = Path(path).resolve()
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if expected is not None and digest != expected:
        raise ValueError('Changed frozen input: ' + str(path))
    receipts[str(path)] = digest
    return parse(raw)


def unique(rows, key):
    result = {}
    for row in rows:
        value = row[key]
        if not isinstance(value, str) or not value or value in result:
            raise ValueError('Invalid/duplicate identity: ' + key)
        result[value] = row
    return result


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Finite number required')
    return value


def nearest(points, requested):
    """Exact rational distance, with earlier presentation timestamp winning ties."""
    index = bisect_left(points, requested)
    if index == len(points):
        return len(points) - 1
    if index == 0:
        return 0
    return index - 1 if requested - points[index - 1] <= points[index] - requested else index


def window(video_id, points, native_pts, time_base, anchor, role, name):
    requested = [anchor + Fraction((i - 8) * 4, 30) for i in range(16)]
    indices = [nearest(points, value) for value in requested]
    boundary = [value < points[0] or value > points[-1] for value in requested]
    seen = set()
    duplicate = []
    for index in indices:
        duplicate.append(index in seen)
        seen.add(index)
    return dict(window_id=f'{video_id}-{name}', video_id=video_id, anchor_pts=float(anchor),
                anchor_frame_index=nearest(points, anchor), role=role,
                sample_requested_pts=[float(value) for value in requested],
                sample_frame_indices=indices, sample_native_pts=[native_pts[i] for i in indices],
                sample_pts=[float(points[i]) for i in indices], time_base=time_base,
                boundary_repeat_mask=boundary, duplicate_sample_mask=duplicate,
                unique_native_frames=len(set(indices)), available_after_pts=float(max(points[i] for i in indices)),
                geometry='whole_original_frame', fcos_proposals_used=False)


def intersects(box, roi):
    return max(box[0], roi[0]) < min(box[2], roi[2]) and max(box[1], roi[1]) < min(box[3], roi[3])


def scan_cache(path, metadata, clock, sink, receipts, expected):
    """Hash and validate every native FCOS row; output counts retain all frame slots."""
    native = clock['native_pts']
    time_base = Fraction(clock['time_base'])
    size = metadata['source_size']
    roi = [value * size[i % 2] for i, value in enumerate(metadata['config']['roi'])]
    counts = Counter(frames=0, raw_person_rows=0, project_person_rows=0,
                     raw_nonempty_frames=0, project_nonempty_frames=0,
                     roi_raw_person_rows=0, roi_project_person_rows=0)
    digest = hashlib.sha256()
    result = []
    with Path(path).open('rb') as stream:
        for index, raw in enumerate(stream):
            digest.update(raw)
            row = parse(raw)
            if (index >= len(native) or type(row['native_pts']) is not int or
                    row['native_pts'] != native[index] or Fraction(row['time_base']) != time_base or
                    abs(number(row['pts']) - float(native[index] * time_base)) > 1e-8 or
                    row['source_size'] != size):
                raise ValueError('Cache differs from full original native clock')
            boxes, scores = row['boxes'], row['scores']
            if len(boxes) != len(scores):
                raise ValueError('Unequal box/score counts')
            for box, score in zip(boxes, scores):
                if (len(box) != 4 or any(not math.isfinite(number(v)) for v in box) or
                        not (0 <= box[0] < box[2] <= size[0] and 0 <= box[1] < box[3] <= size[1]) or
                        not 0 <= number(score) <= 1):
                    raise ValueError('Invalid saved person box or score')
            project = sum(score >= .5 for score in scores)
            roi_raw = sum(intersects(box, roi) for box in boxes)
            roi_project = sum(score >= .5 and intersects(box, roi) for box, score in zip(boxes, scores))
            item = dict(video_id=metadata['video_id'], frame_index=index, native_pts=native[index],
                        time_base=clock['time_base'], pts=row['pts'], raw_person_rows=len(boxes),
                        project_person_rows=project, roi_raw_person_rows=roi_raw,
                        roi_project_person_rows=roi_project, max_saved_person_score=max(scores, default=None))
            sink.write(json.dumps(item, allow_nan=False) + '\n')
            result.append(item)
            counts.update(frames=1, raw_person_rows=len(boxes), project_person_rows=project,
                          raw_nonempty_frames=bool(boxes), project_nonempty_frames=bool(project),
                          roi_raw_person_rows=roi_raw, roi_project_person_rows=roi_project)
    receipts[str(Path(path).resolve())] = digest.hexdigest()
    if digest.hexdigest() != expected:
        raise ValueError('Changed raw person cache hash')
    if (len(result) != len(native) or len(result) != metadata['frames'] or
            counts['project_person_rows'] != metadata['person_boxes'] or
            counts['project_nonempty_frames'] != metadata['frames_with_person']):
        raise ValueError('Native cache coverage/project totals differ from run receipt')
    return result, dict(counts)


def review_bindings(snapshot):
    reviews = unique(snapshot['requests'], 'id')
    if len(reviews) != 9:
        raise ValueError('Preserve all nine existing EXP-0065 reviews')
    result = []
    for row in reviews.values():
        if (row['experiment_id'] != 'EXP-0065' or row['answer_version'] != 1 or
                row['status'] != 'applied' or row['version'] != 4 or not row['answer'] or
                len(row['source_binding_sha256']) != 64):
            raise ValueError('Wrong or incomplete saved review answer version')
        result.append({key: row.get(key) for key in ('id', 'version', 'answer_version', 'artifact_id',
                       'source_binding_sha256', 'source_label', 'question', 'answer', 'note', 'processing_note')})
    return result


def case_specs(spec):
    cases = [dict(row, cohort_role=('qualitative_non_climbing_control' if row.get('case_role')
                                   else 'historically_documented_detection_failure'))
             for row in spec['primary_cohort']['known_cases']]
    for vid, focus, issue, role in [
        ('015', [60, 61, 62, 63], 'User reports boxes intermittent from about61s; source layer/actor association unresolved', 'reviewed_box_gap_cause_unresolved'),
        ('039', [57, 58, 59, 60], 'Two overlapping people; user reports58–59s box gap, no per-actor box GT', 'reviewed_box_gap_cause_unresolved'),
        ('043', [67, 68, 69, 70], 'User reports main climb and box loss from about68s, beyond selected action input', 'reviewed_box_gap_cause_unresolved'),
        ('026', [64, 65, 66, 67, 68, 69, 70], 'User reviewed stable climbing boxes64–70s; subsequent door occlusion distinct', 'reviewed_climbing_continuity_control'),
        ('028', [66, 67, 68], 'Reviewed climbing and ID3→4 same person; tracker ID break is not detector FN', 'reviewed_identity_transition_control'),
        ('034', [33, 34, 35], 'Reviewed standing without climbing in33–35.333s; action-negative control only', 'reviewed_standing_action_control'),
        ('021', [72, 73, 74], 'Two people use side path, not generic gate climbing; C5 expanded geometry retained', 'reviewed_sidepath_semantic_control')]:
        cases.append(dict(id=f'{vid}_review_followup', video_id='E01_' + vid,
                          focus_seconds=focus, issue=issue, cohort_role=role,
                          source='docs/experiments/EXP-0065-followup.md'))
    return cases


def run(args):
    if args.output.exists():
        raise ValueError('Existing outputs are immutable; use a new revision')
    receipts = {}
    lock = read(args.baseline_lock, receipts, LOCK_SHA)
    if lock.get('status') != 'verified' or lock.get('baseline_experiment') != 'EXP-0062':
        raise ValueError('Verified EXP-0062 AFTER baseline required')
    locked = lock['verified_paths']
    refs = read(args.references, receipts, locked[str(args.references.resolve())])
    inventory = read(args.inventory, receipts, refs['inventory_sha256'])
    sources = unique(lock['regression_only_videos'], 'video_id')
    items = unique(inventory['videos'], 'video_id')
    provenance = unique(lock['detector_provenance'], 'video_id')
    if set(sources) != set(items) or set(items) != set(provenance) or len(items) != 45:
        raise ValueError('Full45 original inventory must be retained')
    spec = read(args.spec, receipts)
    reviews = review_bindings(read(args.reviews, receipts))
    cases = case_specs(spec)
    # The only new directory; a failed preparation retains its status and partial evidence.
    args.output.mkdir(parents=True, exist_ok=False)
    write = lambda name, value: (args.output / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    write('status.json', dict(status='preparing_cpu_only', model_execution=False))
    (args.output / 'plans').mkdir()
    video_rows, supplemental, camera_domains = [], [], {}
    import av  # Existing CPU metadata reader only; no decode, tensors, model, or CUDA.
    with (args.output / 'native-frame-inventory.jsonl').open('x') as sink:
        for vid, original in sorted(sources.items()):
            inv = items[vid]
            if original['sha256'] != inv['sha256'] or locked[str(Path(original['path']).resolve())] != inv['sha256']:
                raise ValueError('Original source hashes disagree')
            if Path(original['path']).stat().st_size != inv['bytes']:
                raise ValueError('Original byte length changed')
            metadata_path = Path(provenance[vid]['metadata_path'])
            meta = read(metadata_path, receipts, locked[str(metadata_path.resolve())])
            if (meta['video_id'] != vid or meta['source_sha256'] != inv['sha256'] or
                    meta['model_sha256'] != MODEL_SHA or meta['sampling'] != 'none' or
                    meta['status'] != 'complete' or meta['decoded_to_eof'] is not True or
                    meta['person_cache']['stage'] != STAGE or meta['config']['score_threshold'] != .5):
                raise ValueError('Incomplete or incompatible native FCOS provenance')
            native_path = ROOT / inv['native_pts_path']
            native = read(native_path, receipts, inv['native_pts_sha256'])
            if native['source_sha256'] != inv['sha256']:
                raise ValueError('Clock source differs')
            clock = native['clocks']
            ticks = clock['native_pts']
            if (len(ticks) != inv['media']['decoded_frame_count'] or
                    any(type(t) is not int for t in ticks) or any(b <= a for a, b in zip(ticks, ticks[1:]))):
                raise ValueError('Invalid/incomplete native frame sequence')
            points = [t * Fraction(clock['time_base']) for t in ticks]
            with av.open(original['path']) as media:
                stream = media.streams.video[0]
                header = dict(width=stream.width, height=stream.height, time_base=str(stream.time_base),
                              frames=stream.frames, average_rate=str(stream.average_rate))
            if ([header['width'], header['height']] != meta['source_size'] or
                    Fraction(header['time_base']) != Fraction(clock['time_base']) or
                    header['frames'] != len(ticks)):
                raise ValueError('Current source header differs from frozen original metadata')
            cache_path = metadata_path.parent / 'person_cache.jsonl'
            expected_cache = meta['person_cache']['sha256']
            if locked.get(str(cache_path.resolve())) != expected_cache:
                raise ValueError('Person cache not bound in original lock')
            lineage = meta.get('geometry_reuse_provenance')
            if lineage:
                origin = Path(lineage['original_directory'])
                old = read(origin / 'run.json', receipts, lineage['original_metadata_sha256'])
                if (old['person_cache']['sha256'] != expected_cache or
                        lineage['original_person_cache_sha256'] != expected_cache or
                        sha(origin / 'person_cache.jsonl') != expected_cache):
                    raise ValueError('Geometry-only cache view changed detector data')
                receipts[str((origin / 'person_cache.jsonl').resolve())] = expected_cache
            rows, counts = scan_cache(cache_path, meta, clock, sink, receipts, expected_cache)
            end = Fraction(str(inv['media'].get('full_native_end_seconds', inv['media']['duration_seconds'])))
            if points[0] != 0 or points[-1] >= end:
                raise ValueError('Full source bounds omit native frames')
            windows = [window(vid, points, ticks, clock['time_base'], Fraction(i), 'fullvideo_regular', f'regular-{i:06d}')
                       for i in range(math.ceil(end))]
            extra = []
            for case in (c for c in cases if c['video_id'] == vid):
                focus = []
                for index, requested in enumerate(case['focus_seconds']):
                    frame = nearest(points, Fraction(str(requested)))
                    focus.append(dict(requested_display_pts=requested, **rows[frame],
                                      actor_identity_verified=False, detector_false_negative=None))
                    w = window(vid, points, ticks, clock['time_base'], points[frame],
                               'supplemental_diagnostic_not_regular_denominator', f"{case['id']}-{index:02d}")
                    w['case_id'] = case['id']
                    extra.append(w)
                case['latest_native_focus'] = focus
                case['precise_target_bbox_ground_truth'] = None
                case['whole_event_detector_fn'] = None
            plan = dict(video_id=vid, source_path=original['path'], source_sha256=inv['sha256'],
                        source_size=meta['source_size'], time_base=clock['time_base'],
                        native_pts_binding=dict(path=str(native_path), sha256=inv['native_pts_sha256'],
                                                time_base=clock['time_base'], decoded_frame_count=len(ticks)),
                        windows=windows, supplemental_windows=extra)
            plan_path = args.output / 'plans' / (vid + '.json')
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
            camera = meta['config']['camera_group']
            roi = meta['config']['roi']
            camera_domains.setdefault(camera, [])
            if roi not in camera_domains[camera]:
                camera_domains[camera].append(roi)
            video_rows.append(dict(video_id=vid, source_path=original['path'], source_sha256=inv['sha256'],
                                   source_sha256_policy='reuse_frozen_original_hash_no_full_media_rehash',
                                   current_source_header=header, source_size=meta['source_size'],
                                   full_native_start_seconds=0, full_native_end_seconds=float(end),
                                   legacy_duration_seconds=inv['media']['duration_seconds'],
                                   native_pts_binding=plan['native_pts_binding'], camera_id=camera,
                                   fixed_roi_secondary=dict(normalized_xyxy=roi,
                                       source_metadata_path=str(metadata_path), source_metadata_sha256=receipts[str(metadata_path.resolve())],
                                       config_sha256=meta['config_sha256'], fcos_proposals_used=False),
                                   primary_spatial_domain='whole_original_frame',
                                   plan=dict(path=str(plan_path.resolve()), sha256=sha(plan_path)),
                                   regular_windows=len(windows), supplemental_windows=len(extra),
                                   cache=dict(path=str(cache_path.resolve()), sha256=expected_cache,
                                              metadata_path=str(metadata_path.resolve()),
                                              metadata_sha256=receipts[str(metadata_path.resolve())],
                                              geometry_reuse_provenance=lineage, stats=counts)))
            supplemental.extend(extra)
    historical = {}
    for suffix in ('006', '007', '030', '031'):
        path = ROOT / f'outputs/cv_phase2b/fcos{suffix}/frames.jsonl'
        metadata_path = path.parent / 'run.json'
        if not path.exists() or not metadata_path.exists():
            historical['E01_' + suffix] = dict(status='missing_historical_saved_output')
            continue
        m = read(metadata_path, receipts)
        if m['source_sha256'] != sources['E01_' + suffix]['sha256']:
            raise ValueError('Historical comparison source differs')
        raw = path.read_bytes()
        receipts[str(path)] = hashlib.sha256(raw).hexdigest()
        rows = [parse(line) for line in raw.splitlines()]
        by_time = {Fraction(r['native_pts']) * Fraction(r['time_base']): r for r in rows}
        for case in (c for c in cases if c['video_id'] == 'E01_' + suffix and 'historical_comparison_window' in c):
            case['historical_focus'] = []
            for focus in case['latest_native_focus']:
                key = Fraction(focus['native_pts']) * Fraction(focus['time_base'])
                old = by_time.get(key)
                case['historical_focus'].append(dict(native_pts=focus['native_pts'], time_base=focus['time_base'],
                    project_detection_rows=(len(old['detections']) if old is not None else None),
                    observed_detection_rows=(sum(d.get('observed') is True for d in old['detections']) if old else None),
                    status='exact_native_pts_found' if old else 'historical_point_not_available',
                    source_path=str(path), person_recovery_success=None))
        historical['E01_' + suffix] = dict(path=str(path), sha256=receipts[str(path)],
                                           metadata_path=str(metadata_path), metadata_sha256=receipts[str(metadata_path)],
                                           raw_internal_returns_available=False,
                                           schema='project_filtered_detections_not_internal_FCOS_candidates')
    smoke_targets = [('E01_006', 124.991533), ('E01_007', 66), ('E01_030', 90),
                     ('E01_030', 94), ('E01_031', 40), ('E01_034', 34), ('E01_028', 67)]
    smoke = []
    for vid, target in smoke_targets:
        candidates = [w for w in supplemental if w['video_id'] == vid]
        chosen = min(candidates, key=lambda w: abs(w['anchor_pts'] - target))
        if abs(chosen['anchor_pts'] - target) > 1e-5:
            raise ValueError('Missing required fixed smoke focus')
        smoke.append(chosen)
    frame_total = sum(v['cache']['stats']['frames'] for v in video_rows)
    if frame_total != 184300:
        raise ValueError('Preserve184300 original native frames')
    # Recheck every consumed frozen text/cache input before publication; no source/weight reads.
    for path, digest in receipts.items():
        if sha(path) != digest:
            raise ValueError('Input changed during inventory: ' + path)
    policy = dict(full_video_domain=True, proposal_gating=False, primary_spatial_domain='whole_original_frame',
                  anchor_step_seconds=1, frames=16, physical_sample_step_seconds='4/30', center_index=8,
                  offsets='(i-8)*4/30 seconds', native_mapping='nearest_presentation_timestamp_ties_earlier',
                  boundary='clamp_to_first_or_last_native_frame_record_repeats_not_new_observations',
                  temporal_input_end='max_actual_sample_pts', model_alternatives='separate_declared_conditions',
                  fcos_cache_stage=STAGE, fcos_internal_score_threshold=.2, project_score_threshold=.5)
    manifest = dict(schema_version=1, experiment_id='EXP-0066', status='fullvideo_cpu_inventory_and_input_plan_complete',
                    videos=video_rows, policy=policy, frame_count=frame_total,
                    regular_windows=sum(v['regular_windows'] for v in video_rows),
                    supplemental_windows=len(supplemental), model_execution=False,
                    miss_ground_truth_complete=False, action_ground_truth_complete=False,
                    original_sources_hashed_this_execution=False, consumed_sha256=receipts,
                    script_sha256=sha(__file__), detector_recall=None, action_f1=None)
    write('manifest.json', manifest)
    write('smoke-windows.json', dict(windows=smoke, supplemental_only=True, inference_executed=False))
    write('failure-evidence.json', dict(cases=cases, historical_sources=historical,
          reviews=reviews, complete_detector_fn_ground_truth=False,
          interpretation='Documented point failures and user box-gap observations are distinct from exhaustive actor FN truth; no gap automatically promoted.'))
    write('camera-domains.json', dict(primary='whole_original_frame', normalized_camera_rois=camera_domains,
                                     new_roi_drawn=False, proposals_used=False))
    totals = Counter()
    for video in video_rows:
        totals.update(video['cache']['stats'])
    write('summary.json', dict(status=manifest['status'], videos=len(video_rows), totals=dict(totals),
           regular_windows=manifest['regular_windows'], supplemental_windows=len(supplemental),
           historical_failure_video_ids=['E01_006', 'E01_007', 'E01_030', 'E01_031'],
           reviewed_gap_cause_unresolved_video_ids=['E01_015', 'E01_039', 'E01_043'],
           positive_known_failure_scope='historical_specific_frames_not_whole_events_or_exhaustive_actor_GT',
           full45_raw_cache_inventory_complete=True, complete_detector_fn_ground_truth=False,
           reviewed_answers=9, precision=None, recall=None, f1=None, model_execution=False))
    write('status.json', dict(status='complete_cpu_preparation_only', model_execution=False,
                             manifest_sha256=sha(args.output / 'manifest.json')))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-lock', type=Path, default=ROOT / 'outputs/action-recognition/exp0063/baseline/attempt-002/baseline-lock.json')
    parser.add_argument('--references', type=Path, default=ROOT / 'outputs/validation/false-confirmation-guard-all45-v1/run-001/after-manifest.json')
    parser.add_argument('--inventory', type=Path, default=ROOT / 'outputs/validation/mvp-all-v3/evaluation-inputs/inventory.json')
    parser.add_argument('--spec', type=Path, default=ROOT / 'runtime/model-comparison/exp0066/handoff/comparison_spec.json')
    parser.add_argument('--reviews', type=Path, default=ROOT / 'runtime/model-comparison/exp0066/cohort/current-review-snapshot.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args)
    print(json.dumps(dict(status=result['status'], videos=len(result['videos']), frames=result['frame_count'],
                          regular_windows=result['regular_windows'])))


if __name__ == '__main__':
    main()
