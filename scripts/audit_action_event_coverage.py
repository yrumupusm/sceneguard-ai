"""Read saved EXP-0064 scores to prepare EXP-0065 review; no model or media IO.

Temporal coincidence is deliberately never called an action TP, detector FN,
intrusion confirmation, or an independent test result.
"""
import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path

LOCK_SHA = "3799ae3eee427b60e698b21f6ee958ac5306eacba07b5d85e4c35dbfa6457b40"
PLAN_SHA = "f8bea6c8b4b36d5d09daf8f3b43a7e8923319ef5bde3b5c4e5cd5f00f0f7cb17"
RESULT_SHA = "b465170efe203655deb76f857549101180e6ce56171ae510c69347595d7e34a8"
MODEL_SHA = "8b4e2eb74bee656f651a172403e4ddfe1e1ce8f9a4438d70c76b5a1b17825b73"
INFERENCE_RECEIPT_SHA = "c615a02b88cd17c41c4b6a6193fc729667cae77f7ec8d02a143766f9c033466b"


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def parse(raw):
    return json.loads(raw, object_pairs_hook=unique_pairs,
                      parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))


def read_snapshot(path, receipts, expected=None, jsonl=False):
    path = Path(path).resolve()
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if expected is not None and digest != expected:
        raise ValueError("Input hash differs: " + str(path))
    receipts[str(path)] = digest
    return [parse(line) for line in raw.splitlines() if line.strip()] if jsonl else parse(raw)


def indexed(rows, field):
    result = {}
    for row in rows:
        key = row[field]
        if not isinstance(key, str) or not key or key in result:
            raise ValueError("Empty or duplicate " + field)
        result[key] = row
    return result


def finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Finite numeric value required")
    return value


def interval(row, last_pts):
    start, end = finite(row['start']), finite(row['end'])
    # A frozen endpoint may include the last frame's duration.
    if not 0 <= start < end or start > last_pts:
        raise ValueError("Invalid reference interval")
    return start, end


def has_sample(points, bounds):
    start, end = bounds
    return any(start <= p < end for p in points)


def validate_scores(plan, scores, entry_sha, model_sha, queue_attempt=None):
    windows = indexed(plan['windows'], 'window_id')
    actual = indexed(scores, 'window_id')
    if set(actual) != set(windows):
        raise ValueError("Missing or unexpected scored window; never replace it with a negative")
    geometry = ('track_id', 'start_target_index', 'end_target_index', 'sample_pts',
                'sample_frame_indices', 'boxes', 'roi_xyxy', 'available_after_pts')
    for key, row in actual.items():
        original = windows[key]
        if any(row.get(k) != original[k] for k in geometry):
            raise ValueError("Score temporal/ROI input differs from frozen plan")
        if (row.get('video_id') != plan['video_id'] or
                row.get('source_sha256') != plan['source_sha256'] or
                row.get('plan_sha256') != entry_sha or
                row.get('model_provenance', {}).get('sha256') != model_sha):
            raise ValueError("Wrong video, plan, source or checkpoint provenance")
        score = finite(row['score'])
        if not 0 <= score <= 1 or row.get('threshold') != .5:
            raise ValueError("Invalid score or changed threshold")
        if row.get('action') != ('climbing_action_candidate' if score >= .5 else None):
            raise ValueError("Saved candidate flag differs from score")
        if row.get('baseline_state_modified') is not False:
            raise ValueError("Expected unchanged advisory baseline")
        if finite(row['batch_flushed_at_source_pts']) < row['available_after_pts']:
            raise ValueError("Score was flushed before its input was available")
        if 'tracking_path' in plan:
            expected_tracking = plan['input_hashes'][plan['tracking_path']]
            if row.get('tracking_sha256') != expected_tracking:
                raise ValueError("Score tracking provenance differs")
        if 'target_index' in plan['samples'][0]:
            provenance = [{k: sample[k] for k in ('target_index', 'target_pts', 'native_pts',
                                                 'time_base', 'pts', 'frame_index')}
                          for sample in plan['samples'][original['start_target_index']:
                                                        original['end_target_index'] + 1]]
            if row.get('sample_provenance') != provenance:
                raise ValueError("Score native sample provenance differs")
        if queue_attempt is not None and row.get('queue_attempt') != queue_attempt:
            raise ValueError("Score belongs to another queue attempt")
    return actual


def candidate_spans(plan, scores):
    """Merge consecutive positive windows of one track for viewing, not event scoring."""
    rows = sorted((s for s in scores if s['score'] >= .5),
                  key=lambda s: (s['track_id'], s['start_target_index']))
    spans = []
    for row in rows:
        if (spans and spans[-1]['track_id'] == row['track_id'] and
                row['start_target_index'] == spans[-1]['last_target_start'] + 3):
            span = spans[-1]
            span['end_pts'] = row['sample_pts'][-1]
            span['last_target_start'] = row['start_target_index']
            span['window_ids'].append(row['window_id'])
            span['max_score'] = max(span['max_score'], row['score'])
        else:
            spans.append(dict(video_id=plan['video_id'], track_id=row['track_id'],
                              start_pts=row['sample_pts'][0], end_pts=row['sample_pts'][-1],
                              last_target_start=row['start_target_index'],
                              window_ids=[row['window_id']], max_score=row['score'],
                              identity_verified=False, review_status='pending'))
    return spans


def audit_video(plan, scores, reference, matched_truth_ids=None):
    if (reference['video_id'] != plan['video_id'] or
            reference['video_sha256'] != plan['source_sha256']):
        raise ValueError("Reference source differs from frozen video")
    indexed(reference['events'], 'id')
    samples = plan['samples']
    points = [finite(s['pts']) for s in samples]
    if not points or any(b <= a for a, b in zip(points, points[1:])):
        raise ValueError("Strictly increasing sample timestamps required")
    partial, empty = [], []
    for row in plan['missing_windows']:
        first = row['start_target_index']
        if type(first) is not int or first < 0 or first + 8 > len(samples):
            raise ValueError("Invalid missing-window sample indices")
        absent = row['missing_target_indices']
        if (not absent or any(type(i) is not int for i in absent) or
                len(set(absent)) != len(absent) or not set(absent) <= set(range(first, first + 8))):
            raise ValueError("Invalid missing observations")
        observed_points = [points[i] for i in range(first, first + 8) if i not in absent]
        if all('observed' in sample for sample in samples[first:first + 8]):
            actual_absent = [i for i in range(first, first + 8)
                             if row['track_id'] not in samples[i]['observed']]
            if actual_absent != sorted(absent):
                raise ValueError("Missing indices differ from actual track observations")
        (empty if len(absent) == 8 else partial).append((row, observed_points))
    if (len(scores) != plan['counts']['eligible_windows'] or
            len(partial) != plan['counts']['partial_observations_windows'] or
            len(empty) != plan['counts']['no_observations_windows']):
        raise ValueError("Frozen observation counts differ from window records")
    events = []
    for event in reference['events']:
        bounds = interval(event, plan['last_pts'])
        overlapping = [s for s in scores if has_sample(s['sample_pts'], bounds)]
        candidates = [s for s in overlapping if s['score'] >= .5]
        missing = [r for r, pts in partial if has_sample(pts, bounds)]
        nominal_partial = [r for r, _ in partial
                           if has_sample(points[r['start_target_index']:r['start_target_index'] + 8], bounds)]
        if candidates:
            status = 'candidate_time_overlap'
        elif overlapping:
            status = 'scored_without_candidate_time_overlap'
        elif missing:
            status = 'partial_observations_only'
        else:
            status = 'no_observed_window_in_reference'
        events.append(dict(video_id=plan['video_id'], reference_id=event['id'],
                           gate_id=event['gate_id'], start=bounds[0], end=bounds[1],
                           truth_basis=reference['truth_basis'], diagnostic=status,
                           scored_windows=len(overlapping), candidate_windows=len(candidates),
                           partial_windows=len(missing),
                           partial_nominal_time_windows=len(nominal_partial),
                           partial_observations_outside_reference_windows=len(nominal_partial) - len(missing),
                           max_score=max((s['score'] for s in overlapping), default=None),
                           scored_window_ids=[s['window_id'] for s in overlapping],
                           candidate_window_ids=[s['window_id'] for s in candidates],
                           partial_window_keys=[dict(track_id=r['track_id'],
                                                    start_target_index=r['start_target_index']) for r in missing],
                           baseline_confirmation_matched=(event['id'] in matched_truth_ids
                                                          if matched_truth_ids is not None else None),
                           relation='temporal_overlap_only_identity_and_gate_unknown',
                           action_true_positive=None, detector_false_negative=None))
    negatives = []
    for i, mask in enumerate(reference.get('verified_non_event_intervals', [])):
        bounds = interval(mask, plan['last_pts'])
        contained = [s for s in scores if all(bounds[0] <= p < bounds[1] for p in s['sample_pts'])]
        partial_overlap = [s for s in scores if has_sample(s['sample_pts'], bounds) and s not in contained]
        negatives.append(dict(video_id=plan['video_id'], interval_index=i,
                              gate_id=mask['gate_id'], start=bounds[0], end=bounds[1],
                              fully_contained_scored_windows=len(contained),
                              fully_contained_candidate_window_ids=[s['window_id'] for s in contained if s['score'] >= .5],
                              edge_overlapping_window_ids=[s['window_id'] for s in partial_overlap],
                              interpretation='review_candidates_not_verified_false_alarms'))
    positive_intervals = [interval(e, plan['last_pts']) for e in reference['events']]
    outside = [s['window_id'] for s in scores if s['score'] >= .5 and
               not any(has_sample(s['sample_pts'], bounds) for bounds in positive_intervals)]
    return dict(video_id=plan['video_id'], events=events, reviewed_negative_intervals=negatives,
                outside_official_reference_candidate_ids=outside,
                outside_reference_is_not_negative=True,
                unresolved_reference_events=reference.get('unresolved_reference_events', 0),
                candidate_review_spans=candidate_spans(plan, scores),
                scored_windows=len(scores), partial_windows=len(partial),
                absent_crossproduct_windows=len(empty))


def locked_json(path, lock, receipts):
    path = Path(path).absolute()
    bindings = lock['verified_paths']
    expected = bindings.get(str(path), bindings.get(str(path.resolve())))
    if expected is None:
        raise ValueError("Reference/report is not in the frozen EXP-0062 lock")
    return read_snapshot(path, receipts, expected)


def baseline_matches(report, references):
    rows = indexed(report['modes']['confirmation']['by_video'], 'video_id')
    if set(rows) != set(references):
        raise ValueError("Incomplete baseline confirmation report")
    matched = {}
    for vid, row in rows.items():
        ref = references[vid]
        truths = set(indexed(ref['events'], 'id'))
        tp = [m['truth_id'] for m in row['matches'] if m['outcome'] == 'tp']
        missed = row['missed_truth_ids']
        if (len(tp) != len(set(tp)) or not set(tp) <= truths or
                len(missed) != len(set(missed)) or set(missed) != truths - set(tp)):
            raise ValueError("Baseline truth IDs do not partition the frozen references")
        counts = row['counts']
        if (counts['tp'] != len(tp) or counts['fn'] != len(missed) or
                counts['known_reference_events'] != len(truths) or
                counts['unresolved_reference_events'] != ref.get('unresolved_reference_events', 0)):
            raise ValueError("Baseline match counts differ from truth IDs")
        matched[vid] = set(tp)
    return matched


def representative_selection(events):
    """One deterministic review suggestion per baseline/category/camera stratum."""
    groups = {}
    for event in events:
        camera = event['gate_id'].split('_', 1)[0]
        key = (event['baseline_confirmation_matched'], event['diagnostic'], camera)
        groups.setdefault(key, []).append(event)
    selected, unselected = [], []
    for key, rows in sorted(groups.items(), key=lambda item: str(item[0])):
        rows = sorted(rows, key=lambda e: (-(e['max_score'] if e['max_score'] is not None else -1),
                                          e['video_id'], e['reference_id']))
        for index, event in enumerate(rows):
            suggestion = dict(video_id=event['video_id'], reference_id=event['reference_id'],
                              gate_id=event['gate_id'], camera=key[2], diagnostic=key[1],
                              baseline_confirmation_matched=key[0], start=event['start'], end=event['end'],
                              max_score=event['max_score'],
                              reason=('representative_of_baseline_category_camera_stratum' if index == 0
                                      else 'same_stratum_already_represented'))
            (selected if index == 0 else unselected).append(suggestion)
    return dict(status='suggestions_only_not_registered_or_semantically_verified',
                selection_policy='one_per_baseline_diagnostic_camera_then_highest_saved_score_stable_id',
                selected=selected, unselected=unselected, all_reference_events=len(events),
                identity_questions=['Does the sampled observed track depict the referenced actor and gate?',
                                    'Does the expanded ROI include a different person performing the action?',
                                    'Do partial observations actually cover the referenced action?'])


def run(args):
    if args.output.exists():
        raise ValueError("Use a new output directory; existing results are preserved")
    receipts = {}
    lock = read_snapshot(args.baseline_lock, receipts, args.baseline_lock_sha256)
    if lock.get('status') != 'verified' or lock.get('baseline_experiment') != 'EXP-0062':
        raise ValueError("Verified EXP-0062 baseline required")
    manifest = read_snapshot(args.plan, receipts, args.plan_sha256)
    result = read_snapshot(args.inference_result, receipts, args.inference_result_sha256)
    refs = locked_json(args.references, lock, receipts)
    evaluation_receipt = getattr(args, 'evaluation_receipt', None)
    if evaluation_receipt:
        envelope = locked_json(evaluation_receipt, lock, receipts)
        for path in (args.references, args.baseline_report):
            if path and envelope['output_hashes'].get(str(path.resolve())) != receipts.get(str(path.resolve()), lock['verified_paths'].get(str(path.resolve()))):
                raise ValueError("Evaluation receipt does not bind the selected reference/report")
    plans = indexed(manifest['videos'], 'video_id')
    references = indexed(refs['videos'], 'video_id')
    reports = indexed(result['videos'], 'video_id')
    if set(plans) != set(references) or set(plans) != set(reports) or len(plans) != args.expected_videos:
        raise ValueError("Preserve the entire matching video inventory")
    if sum(len(v['events']) for v in references.values()) != args.expected_references:
        raise ValueError("Frozen official reference count differs")
    if (manifest['baseline_lock']['sha256'] != args.baseline_lock_sha256 or
            manifest['policy']['threshold'] != .5 or manifest['policy']['frames'] != 8 or
            manifest['policy']['step'] != 3 or result.get('status') != 'advisory_inference_complete' or
            result.get('baseline_state_changes') is not False or result.get('production_integration') is not False):
        raise ValueError("Wrong inference policy, baseline or completion state")
    matched = None
    if args.baseline_report:
        report = locked_json(args.baseline_report, lock, receipts)
        matched = baseline_matches(report, references)
    inference_receipt_path = getattr(args, 'inference_receipt', None)
    inference_receipt = None
    if args.inference_result_sha256 == RESULT_SHA and not inference_receipt_path:
        raise ValueError("Frozen actual run requires its score-hash receipt")
    if inference_receipt_path:
        inference_receipt = read_snapshot(inference_receipt_path, receipts,
                                         getattr(args, 'inference_receipt_sha256', INFERENCE_RECEIPT_SHA))
        attempt = inference_receipt['actual_attempt']
        if (attempt['status'] != 'succeeded' or attempt['exit_code'] != 0 or
                result.get('queue_attempt') != attempt['attempt_id'] or
                inference_receipt['artifacts'].get(str(args.inference_result.resolve())) != args.inference_result_sha256):
            raise ValueError("Inference receipt does not bind the completed result")
    if 'input_contract' in result:
        files = result['input_contract']['files']
        if (files['checkpoint'] != args.checkpoint_sha256 or files['manifest'] != args.plan_sha256 or
                files['baseline_lock'] != args.baseline_lock_sha256):
            raise ValueError("Result input contract differs from frozen inputs")
    audits = []
    for vid, entry in sorted(plans.items()):
        plan = read_snapshot(entry['path'], receipts, entry['sha256'])
        if plan['video_id'] != vid:
            raise ValueError("Wrong per-video plan identity")
        score_path = args.inference_result.parent / vid / 'window-scores.jsonl'
        expected_score_sha = None
        if inference_receipt:
            expected_score_sha = inference_receipt['video_output_hashes'].get(str(score_path.resolve()))
            if expected_score_sha is None:
                raise ValueError("Score file absent from original inference hash receipt")
        scores = read_snapshot(score_path, receipts, expected_score_sha, jsonl=True)
        validate_scores(plan, scores, entry['sha256'], args.checkpoint_sha256, result.get('queue_attempt'))
        if (len(scores) != reports[vid]['scored_windows'] or
                ('candidate_windows' in reports[vid] and
                 sum(s['score'] >= .5 for s in scores) != reports[vid]['candidate_windows'])):
            raise ValueError("Saved report/score count mismatch")
        audits.append(audit_video(plan, scores, references[vid], None if matched is None else matched[vid]))
    total_scores = sum(a['scored_windows'] for a in audits)
    total_candidates = sum(len(s['window_ids']) for a in audits for s in a['candidate_review_spans'])
    if (total_scores != result['totals']['scored_windows'] or
            total_candidates != result['totals']['candidate_windows']):
        raise ValueError("Saved total/score mismatch")
    event_rows = [e for a in audits for e in a['events']]
    counts = Counter(e['diagnostic'] for e in event_rows)
    partition = {name: dict(Counter(e['diagnostic'] for e in event_rows
                                   if e['baseline_confirmation_matched'] is value))
                 for name, value in [('matched', True), ('missed', False)]}
    summary = dict(experiment_id='EXP-0065', status='diagnostics_generated_semantic_review_pending',
                   videos=len(audits), official_reference_events=len(event_rows),
                   unresolved_reference_events=sum(a['unresolved_reference_events'] for a in audits),
                   event_diagnostic_counts=dict(counts), scored_windows=total_scores,
                   candidate_windows=total_candidates, baseline_report_used=bool(args.baseline_report),
                   baseline_partition=partition,
                   baseline_matched_events=sum(e['baseline_confirmation_matched'] is True for e in event_rows),
                   baseline_missed_events=sum(e['baseline_confirmation_matched'] is False for e in event_rows),
                   score_hashes_verified_against_original_receipt=bool(inference_receipt),
                   partial_observation_relation='at_least_one_actually_observed_sample_inside_half_open_reference',
                   precision=None, recall=None, f1=None, intrusion_improvement=None,
                   interpretation='Temporal/gate/person correspondence still needs review; no model execution.',
                   input_sha256=receipts, script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    # The read snapshots are the consumed data. Also detect concurrent file changes
    # before publishing any diagnostic output; no media or weight rehash is needed.
    for path, digest in receipts.items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest:
            raise ValueError("Input changed during audit: " + path)
    args.output.mkdir(parents=True, exist_ok=False)
    for name, data in [('summary.json', summary), ('per-video.json', audits),
                       ('review-selection.json', representative_selection(event_rows))]:
        (args.output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    columns = ['video_id', 'reference_id', 'gate_id', 'start', 'end', 'truth_basis', 'diagnostic',
               'scored_windows', 'candidate_windows', 'partial_windows', 'max_score',
               'baseline_confirmation_matched', 'relation']
    with (args.output / 'event-diagnostics.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(event_rows)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline-lock', 'plan', 'inference-result', 'references', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--baseline-report', type=Path)
    parser.add_argument('--evaluation-receipt', type=Path)
    parser.add_argument('--inference-receipt', type=Path)
    parser.add_argument('--inference-receipt-sha256', default=INFERENCE_RECEIPT_SHA)
    for name, default in [('baseline-lock', LOCK_SHA), ('plan', PLAN_SHA),
                          ('inference-result', RESULT_SHA), ('checkpoint', MODEL_SHA)]:
        parser.add_argument('--' + name + '-sha256', default=default)
    parser.add_argument('--expected-videos', type=int, default=45)
    parser.add_argument('--expected-references', type=int, default=52)
    args = parser.parse_args()
    summary = run(args)
    print(json.dumps({k: summary[k] for k in ('status', 'videos', 'official_reference_events',
                                             'event_diagnostic_counts')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
