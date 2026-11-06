"""Plan official actor-action clips without opening videos or importing ML libraries.

All labels remain official reference annotations with sampled alignment evidence.
A separate immutable coordinator release must bind this manifest before preparation.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

LABEL_POLICY = 'official_actor_action_intervals_sampled_alignment_review'
REVIEW_STATUS = 'sampled_alignment_review_complete'
ROI_POLICY = 'static_both_origins_actor_union_3x_width_2x_height_clipped_fullframe'
NEGATIVE_POLICIES = {
    'moving_stand_v1': ('moving', 'stand'),
    'explicit_normal_actions_v2': ('moving', 'stand', 'sit_down_bench', 'sit_down_floor'),
}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def digest_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True,
                                    allow_nan=False) + '\n')


def indexed(rows, key):
    result = {}
    for row in rows:
        if row[key] in result:
            raise ValueError('Duplicate ' + key + ': ' + row[key])
        result[row[key]] = row
    return result


def center_indices(start, end, count=8):
    """Intersection of inclusive origin-0 [s,e] and origin-1 [s-1,e-1]."""
    if type(start) is not int or type(end) is not int or end - start < count:
        raise ValueError('short_both_origin_interior')
    first = start + (end - start - count) // 2  # earlier of two centers on a tie
    return list(range(first, first + count))


def contextual_roi(boxes, width, height):
    checked = []
    for ann in boxes:
        try:
            x1, y1, x2, y2 = map(float, (*ann['bbox'][0], *ann['bbox'][1]))
            if (not all(math.isfinite(x) for x in (x1, y1, x2, y2))
                    or not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height)):
                raise ValueError()
        except (KeyError, TypeError, ValueError, IndexError):
            raise ValueError('invalid_box') from None
        checked.append((x1, y1, x2, y2))
    if not checked:
        raise ValueError('missing_box_frames')
    x1, y1 = min(b[0] for b in checked), min(b[1] for b in checked)
    x2, y2 = max(b[2] for b in checked), max(b[3] for b in checked)
    w, h = x2 - x1, y2 - y1
    union = [x1, y1, x2, y2]
    return [max(0, math.floor(x1-w)), max(0, math.floor(y1-h/2)),
            min(width, math.ceil(x2+w)), min(height, math.ceil(y2+h/2))], union


def plan_event(source, assignment, event, annotations, packets, negative_policy='moving_stand_v1'):
    """Reject a center window if any required frame/actor/action is ambiguous."""
    name = event['class_name']
    allowed = {'wall_over': 1, **{name: 0 for name in NEGATIVE_POLICIES[negative_policy]}}
    if name not in allowed:
        raise ValueError('unsupported_or_ambiguous_action')
    indices = center_indices(event['start_frame_declared'], event['end_frame_declared'])
    # At decoded index d, origin-0 uses annotation d and origin-1 uses d+1.
    required = set(indices) | {i+1 for i in indices}
    actor, obj = event['actor_id'], event['object_id']
    matching = defaultdict(list)
    for i, ann in enumerate(annotations):
        if ann['actor_id'] == actor and ann['object_id'] == obj and ann['cur_frame'] in required:
            matching[ann['cur_frame']].append((i, ann))
    if any(not matching[i] for i in required):
        raise ValueError('missing_box_frames')
    if any(len(matching[i]) != 1 for i in required):
        raise ValueError('duplicate_or_contradictory_boxes')
    selected = [matching[i][0] for i in sorted(required)]
    if any(a['class_name'] != name for _, a in selected):
        raise ValueError('multi_action_ambiguity')
    if any(a['actor_id'] == actor and a['cur_frame'] in required and a['class_name'] != name
           for a in annotations):
        raise ValueError('multi_action_ambiguity')
    for other in source['label']['events']:
        if other['event_index'] == event['event_index']:
            continue
        if (other['actor_id'] == actor
                and other['start_frame_declared'] <= max(required)
                and other['end_frame_declared'] >= min(required)):
            # Even duplicate same-action event intervals have uncertain event identity.
            raise ValueError('overlapping_actor_events')
    if allowed[name] == 0:
        # Conservative source-wide spatial context: a wall annotation anywhere in
        # the concurrent source frame rejects a negative, even outside target ROI.
        if any(a['class_name'] == 'wall_over' and a['cur_frame'] in required for a in annotations):
            raise ValueError('concurrent_wall_over_annotation')
        for other in source['label']['events']:
            if ('wall_over' in other.get('annotation_classes', [])
                    and other['start_frame_declared'] <= max(required)
                    and other['end_frame_declared'] >= min(required)):
                raise ValueError('concurrent_wall_over_event')
    video = source['video']
    native = packets.get('pts', [])
    if (not native or any(p is None or type(p) is not int for p in native)
            or len(native) != len(set(native))):
        raise ValueError('invalid_packet_pts')
    native = sorted(native)
    if indices[0] < 0 or indices[-1] >= len(native):
        raise ValueError('missing_native_frames')
    tb = Fraction(packets.get('time_base', video['time_base']))
    times = [Fraction(native[i]) * tb for i in indices]
    if any(b-a != Fraction(1, 3) for a, b in zip(times, times[1:])):
        raise ValueError('missing_native_frames')
    roi, union = contextual_roi([a for _, a in selected], video['width'], video['height'])
    evidence = {'annotation_path': source['label_path'], 'annotation_sha256': source['label_sha256'],
                'event_index': event['event_index'], 'class_name': name,
                'selected_annotation_indices': [i for i, _ in selected],
                'selected_annotations_sha256': digest_json([a for _, a in selected]),
                'provenance': 'official_actor_action_annotation_not_full_human_review'}
    row = {k: source[k] for k in ('source_id', 'source_path', 'source_sha256', 'label_path', 'label_sha256')}
    row.update(clip_id='clip-' + digest_json([source['source_id'], actor, obj, event['event_index']])[:24],
               event_group=assignment['group_id'], split=assignment['split'], label=allowed[name],
               action_class=name, actor_id=actor, object_id=obj, event_index=event['event_index'],
               location=assignment['location'], evaluation_cohort=assignment['evaluation_cohort'],
               scenario_family=source.get('scenario_family', 4), scenario_number=source['scenario'],
               sample_frame_indices=indices, sample_pts=[float(t) for t in times],
               sample_pts_ticks=[native[i] for i in indices], time_base=str(tb),
               source_width=video['width'], source_height=video['height'], roi_xyxy=roi,
               actor_union_xyxy=union, roi_policy=ROI_POLICY, roi_coordinate_space='fullframe_xyxy',
               roi_human_inspected=False, verified_action_interval=[
                   float(Fraction(native[event['start_frame_declared']])*tb),
                   float(Fraction(native[event['end_frame_declared']-1])*tb)],
               interval_basis='label_derived_both_origin_interior_not_precise_human_boundaries',
               negative_basis='explicit_action_annotation' if allowed[name] == 0 else None,
               label_evidence=evidence, temporal_alignment='annotation_interior_both_origins',
               box_alignment='official_annotations_sampled_alignment_review',
               semantic_ground_truth_coverage='official_reference_only_not_all_human_reviewed',
               decode_verification='pending_exact_native_pts_during_preprocessing')
    return row


def counts(rows, fields):
    return dict(sorted(Counter('|'.join(str(r[k]) for k in fields) for r in rows).items()))


def validate_review_evidence(path):
    evidence = json.loads(Path(path).read_text())
    if (evidence.get('experiment_id') != 'EXP-0063'
            or evidence.get('label_policy') != LABEL_POLICY
            or evidence.get('review_status') != REVIEW_STATUS
            or evidence.get('full_human_semantic_validation') is not False):
        raise ValueError('Expected sampled alignment evidence without full semantic certification')
    for key in ('review_snapshot', 'interpretation_policy'):
        item = evidence[key]
        if sha(item['path']) != item['sha256']:
            raise ValueError('Review evidence hash mismatch: ' + key)
    requests = json.loads(Path(evidence['review_snapshot']['path']).read_text())['requests']
    actual = {(r['id'], r['version'], r['answer_version']) for r in requests
              if r.get('status') == 'applied' and r.get('answer')}
    expected = {(r['request_id'], r['version'], r['answer_version']) for r in evidence['reviews']}
    if len(actual) != 8 or len(requests) != 8 or actual != expected:
        raise ValueError('Expected exact eight applied review versions')
    return evidence


def build_plan(sources, split, baseline, packet_rows, label_loader, negative_policy='moving_stand_v1'):
    assignments = indexed(split['assignments'], 'source_id')
    if set(assignments) != {s['source_id'] for s in sources}:
        raise ValueError('Frozen split/source inventory mismatch')
    indexed(sources, 'source_id')
    if baseline.get('status') != 'verified' or baseline.get('baseline_experiment') != 'EXP-0062':
        raise ValueError('Verified EXP-0062 baseline required')
    forbidden_hashes = {r['sha256'] for r in baseline['regression_only_videos']}
    forbidden_paths = {str(Path(r['path']).resolve()) for r in baseline['regression_only_videos']}
    heldout = set(split['held_out_test_locations'])
    clips, exclusions, source_audit = [], [], []
    group_splits, hash_splits, path_splits = {}, {}, {}
    for source in sorted(sources, key=lambda r: r['source_id']):
        sid = source['source_id']; a = assignments[sid]
        if a['source_sha256'] != source['source_sha256'] or a['label_sha256'] != source['label_sha256']:
            raise ValueError('Frozen source/label hash differs: ' + sid)
        reason = None
        if source['excluded'] or a['excluded'] or a['split'] == 'excluded':
            reason = 'user_excluded_source'
        elif source['errors'] or a['split'] not in {'train', 'validation', 'test'}:
            reason = 'quarantined_source'
        elif source.get('scenario_family', 4) == 4 and source['scenario'] in {*range(19, 36), 69, 70}:
            raise ValueError('Excluded scenario admitted by frozen split')
        elif source['source_sha256'] in forbidden_hashes or str(Path(source['source_path']).resolve()) in forbidden_paths:
            raise ValueError('Forbidden regression source')
        events = (source.get('label') or {}).get('events', [])
        if reason:
            source_audit.append({'source_id': sid, 'split': a['split'], 'reason': reason, 'events': len(events)})
            exclusions.extend({'source_id': sid, 'event_index': e['event_index'], 'actor_id': e['actor_id'],
                               'object_id': e['object_id'], 'action_class': e['class_name'],
                               'split': a['split'], 'reason': reason} for e in events)
            continue
        if a['location'] != source['label']['info']['location']:
            raise ValueError('Frozen location differs')
        if a['location'] in heldout and a['split'] != 'test':
            raise ValueError('Held-out place leakage')
        for seen, key in ((group_splits, a['group_id']), (hash_splits, source['source_sha256']),
                          (path_splits, str(Path(source['source_path']).resolve()))):
            if key in seen and seen[key] != a['split']:
                raise ValueError('Frozen group/source leakage')
            seen[key] = a['split']
        # label_loader reads original JSON and verifies its audited byte SHA.
        raw = label_loader(source)
        if len(raw['events']) != len(events):
            raise ValueError('Original event inventory differs')
        if source['video']['average_rate'] != '3' or source['label']['info']['fps'] != 3:
            raise ValueError('Expected audited native 3FPS')
        source_audit.append({'source_id': sid, 'split': a['split'], 'reason': 'candidate_events_checked', 'events': len(events)})
        for e in events:
            try:
                if not (0 <= e['start_frame_declared'] <= e['end_frame_declared']-1 < len(packet_rows[sid]['pts'])):
                    raise ValueError('missing_native_frames')
                row = plan_event(source, a, e, raw['annotations'], packet_rows[sid], negative_policy)
            except ValueError as exc:
                exclusions.append({'source_id': sid, 'event_index': e['event_index'], 'actor_id': e['actor_id'],
                                   'object_id': e['object_id'], 'action_class': e['class_name'],
                                   'split': a['split'], 'reason': str(exc)})
            else:
                clips.append(row)
    event_total = sum(len((s.get('label') or {}).get('events', [])) for s in sources)
    assert len(clips) + len(exclusions) == event_total
    assert len({(r['source_id'], r['event_index']) for r in clips + exclusions}) == event_total
    return clips, exclusions, source_audit


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--wall-audit', type=Path, required=True)
    p.add_argument('--normal-audit', type=Path, required=True)
    p.add_argument('--split-manifest', type=Path, required=True)
    p.add_argument('--baseline-lock', type=Path, required=True)
    p.add_argument('--review-evidence', '--review-release', dest='review_evidence', type=Path, required=True,
                   help='Coordinator policy evidence; final trainer release is external and later')
    p.add_argument('--config', type=Path, default=Path('configs/exp0063_action_training.json'))
    p.add_argument('--negative-policy', choices=sorted(NEGATIVE_POLICIES), default='moving_stand_v1')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise ValueError('Output must be a new immutable revision')
    script_bytes = Path(__file__).read_bytes()
    policy_evidence = validate_review_evidence(args.review_evidence)
    if args.negative_policy == 'explicit_normal_actions_v2':
        if set(policy_evidence.get('negative_classes', [])) != set(NEGATIVE_POLICIES[args.negative_policy]):
            raise ValueError('Negative policy differs from coordinator evidence')
    config = json.loads(args.config.read_text())
    if config['frames'] != 8:
        raise ValueError('This frozen clip policy requires eight native frames')
    split = json.loads(args.split_manifest.read_text())
    sources, packets = [], []
    input_paths = {'split_manifest': args.split_manifest, 'baseline_lock': args.baseline_lock,
                   'review_snapshot': Path(policy_evidence['review_snapshot']['path']),
                   'review_policy': Path(policy_evidence['interpretation_policy']['path']),
                   'policy_evidence': args.review_evidence, 'config': args.config,
                   'builder_script': Path(__file__)}
    if 'prior_interpretation_policy' in policy_evidence:
        prior = policy_evidence['prior_interpretation_policy']
        if sha(prior['path']) != prior['sha256']:
            raise ValueError('Prior interpretation policy hash mismatch')
        input_paths['prior_review_policy'] = Path(prior['path'])
    for name, directory in [('wall', args.wall_audit), ('normal', args.normal_audit)]:
        manifest, pts = directory/'manifest.jsonl', directory/'packet-pts.jsonl'
        if split[name + '_manifest_sha256'] != sha(manifest):
            raise ValueError('Audit manifest differs from frozen split')
        sources.extend(read_jsonl(manifest)); packets.extend(read_jsonl(pts))
        input_paths[name + '_manifest'] = manifest; input_paths[name + '_packet_pts'] = pts
    bindings = {key: {'path': str(path.resolve()), 'sha256': sha(path)} for key, path in input_paths.items()}
    def label_loader(source):
        if sha(source['label_path']) != source['label_sha256']:
            raise ValueError('Official label bytes changed: ' + source['source_id'])
        return json.loads(Path(source['label_path']).read_text(encoding='utf-8-sig'))
    clips, exclusions, source_audit = build_plan(sources, split, json.loads(args.baseline_lock.read_text()),
                                                 indexed(packets, 'source_id'), label_loader, args.negative_policy)
    for item in bindings.values():
        if sha(item['path']) != item['sha256']:
            raise ValueError('Bound input changed during planning: ' + item['path'])
    if Path(__file__).read_bytes() != script_bytes:
        raise ValueError('Builder source changed during planning')
    evidence = {key: bindings[key] for key in ('review_snapshot', 'review_policy', 'policy_evidence')}
    evidence['reviews'] = policy_evidence['reviews']
    evidence.update(scope='eight_sample_alignment_reviews_not_full_corpus_semantic_or_roi_certification',
                    release_binding='external_immutable_release_binds_manifest_after_generation')
    manifest = {'schema_version': 'exp0063-clip-candidates-v1', 'label_policy': LABEL_POLICY,
                'negative_policy': args.negative_policy,
                'negative_action_classes': list(NEGATIVE_POLICIES[args.negative_policy]),
                'review_status': REVIEW_STATUS, 'review_evidence': evidence,
                'source_split_sha256': sha(args.split_manifest), 'baseline_lock_sha256': sha(args.baseline_lock),
                'config_sha256': sha(args.config), 'builder_sha256': sha(__file__),
                'held_out_test_locations': split['held_out_test_locations'], 'frames': 8,
                'roi_policy': ROI_POLICY, 'clips': clips,
                'metrics_scope': 'official_reference_labels_until_sufficient_semantic_ground_truth_coverage',
                'source_hash_verification': 'audit_manifest_bound_to_frozen_split_rehash_before_preprocessing',
                'validation_subtype_limitation': policy_evidence.get('validation_subtype_limitation'),
                'preprocessing': 'not_run', 'training': 'not_run'}
    summary = {'source_count': len(sources), 'audited_event_count': len(clips)+len(exclusions),
               'candidate_clips': len(clips), 'excluded_events': len(exclusions),
               'candidate_sources': len({r['source_id'] for r in clips}),
               'candidate_groups': len({r['event_group'] for r in clips}),
               'class_split': counts(clips, ['split', 'action_class']),
               'binary_split': counts(clips, ['split', 'label']),
               'place_class_split': counts(clips, ['location', 'split', 'action_class']),
               'cohort_class_split': counts(clips, ['evaluation_cohort', 'split', 'action_class']),
               'group_class_split': counts(clips, ['event_group', 'split', 'action_class']),
               'source_split_counts': counts(source_audit, ['split']),
               'source_disposition_counts': counts(source_audit, ['reason']),
               'exclusion_reason_counts': counts(exclusions, ['reason']),
               'exclusion_class_split_reason': counts(exclusions, ['split', 'action_class', 'reason']),
               'frames_decoded': 0, 'gpu_work': 0, 'training': 0,
               'actual_frame_availability': 'pending_preprocessing_decode_not_inferred_from_packet_count',
               'metrics_scope': manifest['metrics_scope']}
    summary['negative_policy'] = args.negative_policy
    summary['validation_subtype_limitation'] = manifest['validation_subtype_limitation']
    summary['blocking_conditions'] = [
        f'{part}_missing_class_{label}' for part in ('train', 'validation') for label in (0, 1)
        if not any(r['split'] == part and r['label'] == label for r in clips)]
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output/'executed-script.py').write_bytes(script_bytes)
    save(args.output/'candidate-manifest.json', manifest)
    summary['manifest_sha256'] = sha(args.output/'candidate-manifest.json')
    save(args.output/'summary.json', summary); save(args.output/'input-bindings.json', bindings)
    for name, rows in [('exclusions.jsonl', exclusions), ('source-audit.jsonl', source_audit)]:
        (args.output/name).write_text(''.join(json.dumps(r, ensure_ascii=False, sort_keys=True)+'\n' for r in rows))
    print(json.dumps({k: summary[k] for k in ('candidate_clips','excluded_events','class_split','exclusion_reason_counts','manifest_sha256')}, sort_keys=True))


if __name__ == '__main__':
    main()
