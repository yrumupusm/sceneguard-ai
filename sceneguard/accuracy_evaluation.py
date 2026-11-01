"""Frozen, event-level accuracy audit; no inference or edits to source results.

Input is a LOCAL normalized manifest (schema described in CODEX_MVP_EVALUATE_ALL).
Only real evidence-update timestamps can match an annotated event. An open card
is not evidence throughout its lifetime. Suspicion and confirmation are scored
independently, with one-to-one maximum-cardinality matching. First notification
errors are counted separately, even when a later observation makes a card a TP.
Unreviewed time is NOT negative ground truth. Runtime failures remain in coverage.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
from typing import Any

STATUSES = {'complete', 'partial', 'unsupported', 'failed', 'not_run'}
BASES = {'official_reference', 'reviewed', 'unresolved'}
MODES = ('suspicion', 'confirmation')


def number(value: Any, name: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f'{name}: finite number required')
    return float(value)


def text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name}: nonempty string required')
    return value


def interval(row: dict, duration: float) -> tuple[float, float]:
    a, b = number(row['start'], 'start'), number(row['end'], 'end')
    text(row['gate_id'], 'gate_id')
    if not 0 <= a < b <= duration:
        raise ValueError('Intervals must be nonempty half-open original-PTS ranges')
    return a, b


def union_seconds(rows: list[dict]) -> float:
    """Exposure is summed by gate; overlapping negative masks are not repeated."""
    grouped = defaultdict(list)
    for row in rows:
        grouped[row['gate_id']].append((row['start'], row['end']))
    total = 0.0
    for ranges in grouped.values():
        end = -math.inf
        for a, b in sorted(ranges):
            total += max(0., b-max(a, end))
            end = max(end, b)
    return total


def is_negative(at: float, gate: str, masks: list[dict]) -> bool:
    return any(r['gate_id'] == gate and r['start'] <= at < r['end'] for r in masks)


def validate_video(video: dict) -> None:
    text(video['video_id'], 'video_id')
    text(video['split'], 'split')
    duration = number(video['duration_seconds'], 'duration_seconds')
    processed = number(video['processed_seconds'], 'processed_seconds')
    if duration <= 0 or not 0 <= processed <= duration + 1e-6:
        raise ValueError('Invalid media coverage')
    if video['execution_status'] not in STATUSES or video['truth_basis'] not in BASES:
        raise ValueError('Unknown execution status or truth basis')
    if video['execution_status'] == 'complete' and abs(processed-duration) > 1e-6:
        raise ValueError('Complete means whole source processed, not an event crop')
    if video['execution_status'] != 'complete':
        text(video.get('reason'), 'non-completion reason')
    if video['truth_basis'] == 'unresolved' and video['events']:
        raise ValueError('Unresolved event timing cannot supply scored truth events')
    unresolved = video.get('unresolved_reference_events', 0)
    if type(unresolved) is not int or unresolved < 0:
        raise ValueError('Nonnegative unresolved reference count required')
    seen = set()
    for event in video['events']:
        eid = text(event['id'], 'truth event id')
        if eid in seen: raise ValueError('Duplicate truth event id')
        seen.add(eid); interval(event, duration)
        text(event['provenance'], 'truth provenance')
        if type(event.get('onset_precise', False)) is not bool:
            raise ValueError('Explicit onset precision boolean required')
    # Same-gate simultaneous/overlapping annotations must be normalized as
    # entrance incidents BEFORE looking at predictions, not counted as people.
    for i, event in enumerate(video['events']):
        for other in video['events'][i+1:]:
            if (event['gate_id'] == other['gate_id'] and
                    max(event['start'], other['start']) < min(event['end'], other['end'])):
                raise ValueError('Normalize overlapping same-gate truth incidents first')
    for mask in video['verified_non_event_intervals']:
        interval(mask, duration); text(mask['provenance'], 'negative provenance')
        for event in video['events']:
            if (mask['gate_id'] == event['gate_id'] and
                    max(mask['start'], event['start']) < min(mask['end'], event['end'])):
                raise ValueError('Positive and verified-negative truth conflict')
    seen = set()
    for pred in video['predictions']:
        pid = text(pred['id'], 'prediction id')
        if pid in seen: raise ValueError('Duplicate prediction id / replay delivery')
        seen.add(pid); text(pred['gate_id'], 'prediction gate')
        for field in ('suspicion_evidence_pts', 'confirmation_evidence_pts'):
            times = pred[field]
            if not isinstance(times, list): raise ValueError('Evidence timestamp list required')
            if any(not 0 <= number(t, field) < duration for t in times):
                raise ValueError('Evidence outside the original source timeline')
            if times != sorted(set(times)):
                raise ValueError('Evidence timestamps must be sorted and unique')
        notices = pred['notifications']; kinds = set()
        for notice in notices:
            kind = notice['kind']; at = number(notice['pts'], 'notification pts')
            if kind not in MODES or kind in kinds or not 0 <= at < duration:
                raise ValueError('At most one first notice per kind per incident')
            kinds.add(kind)
            times = pred[kind+'_evidence_pts']
            if not times or min(times) > at+1e-6:
                raise ValueError('Notification cannot precede its own evidence')


def maximum_matching(edges: dict[str, list[str]]) -> dict[str, str]:
    """Deterministic augmenting-path match; not greedy many-to-one credit."""
    matched: dict[str, str] = {}
    def visit(pid: str, seen: set[str]) -> bool:
        for gid in edges[pid]:
            if gid in seen: continue
            seen.add(gid)
            if gid not in matched or visit(matched[gid], seen):
                matched[gid] = pid
                return True
        return False
    for pid in sorted(edges): visit(pid, set())
    return {pid: gid for gid, pid in matched.items()}


def ratio(a: float, b: float) -> float | None:
    return a/b if b else None


def metrics(counts: dict) -> dict:
    tp, fp, fn, unknown = (counts[k] for k in ('tp', 'fp', 'fn', 'unscored_predictions'))
    # Unknown predictions must never be silently dropped from headline precision.
    precision = ratio(tp, tp+fp) if unknown == 0 else None
    recall = ratio(tp, tp+fn)
    return dict(precision=precision, recall_on_resolved_references=recall,
        f1=ratio(2*tp, 2*tp+fp+fn) if unknown == 0 else None,
        precision_on_scored_subset=ratio(tp, tp+fp),
        precision_lower_bound=ratio(tp, tp+fp+unknown),
        precision_upper_bound=ratio(tp+unknown, tp+fp+unknown),
        false_notices_per_verified_negative_gate_hour=(
            ratio(counts['false_notices_in_verified_negative'],
                  counts['verified_negative_gate_seconds']/3600)),
        reference_coverage_across_inventory=ratio(tp, counts['inventory_resolved_events']),
        reference_coverage_note='Execution failures/unrun references remain in this denominator; not detector-only recall.')


def score_video(video: dict, mode: str) -> dict:
    if mode not in MODES: raise ValueError('Unknown scoring mode')
    validate_video(video)
    truths = {e['id']: e for e in video['events']}
    completed = video['execution_status'] == 'complete'
    scored = completed and video['truth_basis'] != 'unresolved'
    preds = {p['id']: p for p in video['predictions'] if p[mode+'_evidence_pts']} if completed else {}
    masks = video['verified_non_event_intervals'] if completed else []
    edges: dict[str, list[str]] = {}
    for pid, pred in preds.items():
        edges[pid] = [g['id'] for g in sorted(truths.values(), key=lambda e:(e['start'], e['id']))
            if pred['gate_id'] == g['gate_id'] and
            any(g['start'] <= t < g['end'] for t in pred[mode+'_evidence_pts'])] if scored else []
    matched = maximum_matching(edges)
    details = []; counts = dict(tp=0, fp=0, fn=0, duplicate_fp=0,
        unscored_predictions=0, known_reference_events=len(truths) if scored else 0,
        inventory_resolved_events=len(truths), unresolved_reference_events=video.get('unresolved_reference_events', 0),
        false_notices_in_verified_negative=0, unreviewed_notices=0,
        first_notices=0, early_first_notices_for_matched_events=0,
        verified_negative_gate_seconds=union_seconds(masks))
    for pid, pred in preds.items():
        times = pred[mode+'_evidence_pts']; gate = pred['gate_id']
        if pid in matched:
            gt = truths[matched[pid]]
            hit = min(t for t in times if gt['start'] <= t < gt['end'])
            details.append(dict(prediction_id=pid, outcome='tp', truth_id=gt['id'],
                first_matching_evidence_pts=hit,
                offset_from_reference_start_seconds=hit-gt['start'],
                source_detection_delay_seconds=hit-gt['start'] if gt.get('onset_precise') else None))
            counts['tp'] += 1
        elif edges[pid]:
            counts['fp'] += 1; counts['duplicate_fp'] += 1
            details.append(dict(prediction_id=pid, outcome='duplicate_fp', competing_truth_ids=edges[pid]))
        elif masks and all(is_negative(t, gate, masks) for t in times):
            counts['fp'] += 1
            details.append(dict(prediction_id=pid, outcome='fp_in_verified_negative'))
        else:
            counts['unscored_predictions'] += 1
            details.append(dict(prediction_id=pid, outcome='unreviewed_or_unresolved'))
        for notice in pred['notifications']:
            if notice['kind'] != mode: continue
            at = notice['pts']; counts['first_notices'] += 1
            if is_negative(at, gate, masks):
                counts['false_notices_in_verified_negative'] += 1
            elif not any(g['gate_id'] == gate and g['start'] <= at < g['end'] for g in truths.values()):
                counts['unreviewed_notices'] += 1
            if pid in matched and at < truths[matched[pid]]['start']:
                counts['early_first_notices_for_matched_events'] += 1
    missed = sorted(set(truths)-set(matched.values())) if scored else []
    counts['fn'] = len(missed)
    return dict(video_id=video['video_id'], split=video['split'], truth_basis=video['truth_basis'],
        execution_status=video['execution_status'], eligible_for_reference_scoring=scored,
        counts=counts, metrics=metrics(counts), matches=details, missed_truth_ids=missed,
        unresolved_reference_ids_due_to_execution=sorted(truths) if not completed else [])


def aggregate(rows: list[dict]) -> dict:
    keys = score_video(dict(video_id='_',split='_',duration_seconds=1,processed_seconds=1,
        execution_status='complete',truth_basis='reviewed',events=[],
        predictions=[],verified_non_event_intervals=[]), 'suspicion')['counts']
    counts = {k: sum(r['counts'][k] for r in rows) for k in keys}
    return dict(videos=len(rows), counts=counts, metrics=metrics(counts))


def evaluate(manifest: dict) -> dict:
    if manifest.get('schema_version') != 1 or not manifest.get('videos'):
        raise ValueError('Schema version 1 and full nonempty inventory required')
    text(manifest['analysis_revision'], 'analysis_revision')
    text(manifest['protocol_id'], 'protocol_id')
    videos = manifest['videos']; ids = [v['video_id'] for v in videos]
    if len(ids) != len(set(ids)): raise ValueError('Duplicate source video')
    for video in videos: validate_video(video)
    report = dict(schema_version=1, protocol_id=manifest['protocol_id'],
        analysis_revision=manifest['analysis_revision'],
        inventory=dict(videos=len(videos), source_seconds=sum(v['duration_seconds'] for v in videos),
            processed_seconds=sum(v['processed_seconds'] for v in videos),
            by_status={s:sum(v['execution_status']==s for v in videos) for s in sorted(STATUSES)},
            non_completed=[dict(video_id=v['video_id'],status=v['execution_status'],reason=v.get('reason'))
                           for v in videos if v['execution_status']!='complete']),
        protocol=dict(unit='entrance_incident_not_person_or_frame',interval='half_open_source_pts',
            matching='one_to_one_maximum_cardinality', early_tolerance_seconds=0,
            late_tolerance_seconds=0, occupancy_is_not_evidence=True,
            unlabelled_time_is_negative=False, full_accuracy=None,
            note='Evidence-hit metrics are not first-alarm correctness; inspect false/early notice counts separately.'), modes={})
    for mode in MODES:
        rows = [score_video(v, mode) for v in videos]; groups = defaultdict(list)
        for row in rows: groups[(row['split'],row['truth_basis'])].append(row)
        # Do not blend official-reference and human-reviewed truth as one headline.
        report['modes'][mode] = dict(by_video=rows, by_split_and_truth=[
            dict(split=key[0],truth_basis=key[1],**aggregate(group))
            for key,group in sorted(groups.items())])
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists(): raise SystemExit('Refusing to replace an existing evaluation')
    raw = args.manifest.read_bytes()
    report = evaluate(json.loads(raw))
    report['input_sha256'] = hashlib.sha256(raw).hexdigest()
    report['evaluator_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(report,stream,ensure_ascii=False,indent=2,allow_nan=False)
        stream.write('\n')
    print(json.dumps(report['inventory'],ensure_ascii=False,indent=2))


if __name__ == '__main__': main()
