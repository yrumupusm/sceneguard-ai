"""EXP-0043: explain SAVED EXP-0042 evidence; no new flow or candidates.

Score arithmetic is replayed, not tuned. Box overlap is provenance, not person
identity. A reference frame/point absent from the recording is an input error,
not evidence of a missing person. Only stdlib is needed for this audit.
"""
from __future__ import annotations

import argparse
from collections import deque
from copy import deepcopy
import csv
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import statistics
from typing import Iterable


def number(value, name, low=None, high=None):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f'{name}: finite number required')
    if low is not None and value < low or high is not None and value > high:
        raise ValueError(f'{name}: out of range')
    return float(value)


def clip(value):
    return max(0., min(1., value))


def explain_score(signal, threshold):
    """Independent arithmetic for gate_transition.cue_metrics + camera penalty.

    Ceilings are mathematical bounds with some terms hypothetically set to one;
    they are NOT proposed scores or claims that any visual evidence is correct.
    """
    number(threshold, 'threshold', 0., 1.)
    names = ('proximity', 'crossing_fraction', 'crossing', 'upward_image_motion',
             'local_deformation', 'normal_progress', 'motion_change', 'coherence')
    x = {k: number(signal[k], k, 0., 1.) for k in names}
    n = signal['point_count']
    if type(n) is not int or n < 3 or type(signal['camera_support']) is not bool:
        raise ValueError('At least three points and explicit camera_support required')
    if abs(x['crossing']-clip(x['crossing_fraction']/.35)) > 1e-6:
        raise ValueError('Crossing fraction and normalized component disagree')
    cross_terms = dict(crossing=.65*x['crossing'], progress=.20*x['normal_progress'],
                       coherence=.15*x['coherence'])
    local_terms = dict(deformation=.55*x['local_deformation'], change=.25*x['motion_change'],
                       progress=.20*x['normal_progress'])
    cross = x['proximity']*sum(cross_terms.values()) if x['crossing_fraction'] > 0 else 0.
    local = x['proximity']*x['upward_image_motion']*sum(local_terms.values())
    quality = .8+.2*min(1., n/8)
    penalty = 0. if signal['camera_support'] else .10
    result = max(0., clip(max(cross, local)*quality)-penalty)
    saved = number(signal['score'], 'score', 0., 1.)
    route = 'boundary_motion' if cross >= local else 'local_gate_change'
    if abs(result-saved) > 1e-6 or route != signal['route']:
        raise ValueError('Stored score/route does not reproduce frozen EXP-0042 arithmetic')
    proximity_cap = max(0., x['proximity']*quality-penalty)
    local_cap = max(0., x['proximity']*x['upward_image_motion']*quality-penalty)
    return dict(saved_score=saved, reproduced_score=result, difference=result-saved,
        route=route, cross_branch=cross, local_branch=local, cross_terms=cross_terms,
        local_terms=local_terms, quality=quality, camera_penalty=penalty,
        threshold=threshold, margin=result-threshold, reaches_threshold=result>=threshold,
        proximity_ceiling=proximity_cap, local_ceiling=local_cap,
        proximity_ceiling_below_threshold=proximity_cap<threshold,
        local_ceiling_below_threshold=local_cap<threshold,
        semantic_correctness=None, altered_candidate=False)


def point_map(path):
    ids, points = path['point_ids'], path['points_original_pixels']
    if len(ids) != len(points) or len(ids) != len(set(ids)):
        raise ValueError('Point IDs/positions must correspond uniquely')
    if any(type(k) is not int or k < 0 for k in ids):
        raise ValueError('Nonnegative permanent point IDs required')
    result = {}
    for k, p in zip(ids, points):
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            raise ValueError('Pixel coordinate pair required')
        result[k] = [number(p[0], 'pixel x'), number(p[1], 'pixel y')]
    return result


def overlap_audit(points, boxes, size, floor):
    """Counts point/actual-box overlap, NEVER semantic tracking accuracy."""
    width, height = size
    membership = {k: [] for k in points}
    coverage = []
    seen = set()
    for box in boxes:
        if box.get('observed') is False or box.get('bbox') is None:
            continue
        score = number(box['score'], 'detector score', 0., 1.)
        if score < floor:
            continue
        idx = box['cache_index']
        if idx in seen:
            raise ValueError('Duplicate actual cache_index')
        seen.add(idx)
        b = box['bbox']
        if len(b) != 4:
            raise ValueError('Normalized xyxy box required')
        x1, y1, x2, y2 = [number(v, 'bbox', 0., 1.) for v in b]
        if not x1 < x2 or not y1 < y2:
            raise ValueError('Nonempty bbox required')
        inside = [k for k, p in points.items()
                  if x1*width <= p[0] <= x2*width and y1*height <= p[1] <= y2*height]
        for k in inside:
            membership[k].append(idx)
        if inside:
            coverage.append(dict(cache_index=idx, track_ids=box.get('track_ids', []),
                                 point_count=len(inside), score=score))
    return dict(points=len(points), within_any_box=sum(bool(v) for v in membership.values()),
        within_multiple_boxes=sum(len(v)>1 for v in membership.values()),
        outside_all_boxes=sum(not v for v in membership.values()),
        boxes=sorted(coverage, key=lambda v: (-v['point_count'], v['cache_index'])),
        scope='point_box_overlap_not_person_identity', semantic_tracking_quality=None)


class SavedEvidenceAudit:
    """Replay score/latch and retain only short histories, without CV imports."""
    def __init__(self, policy, size):
        self.policy = dict(policy)
        for key in ('score_threshold', 'support_window', 'support_seconds', 'max_frame_gap',
                    'cooldown_seconds', 'seed_score', 'window_seconds'):
            number(policy[key], key, 0.)
            if policy[key] <= 0:
                raise ValueError('Positive policy required')
        for key in ('min_support_frames', 'max_windows'):
            if type(policy[key]) is not int or policy[key] < 1:
                raise ValueError('Integer policy required')
        if len(size) != 2 or any(type(v) is not int or v <= 0 for v in size):
            raise ValueError('Positive native size required')
        self.size = list(size)
        self.histories = {}
        self.seen = set()
        self.previous_pts = None
        self.previous_index = None
        self.positive = deque()
        self.last_emit = -math.inf
        self.frames = 0
        self.event_pts = []
        self.signal_count = 0

    def push(self, row):
        at = number(row['pts'], 'PTS', 0.)
        index = row['frame_index']
        if type(index) is not int or index < 0:
            raise ValueError('Nonnegative frame index required')
        if self.previous_index is not None and index != self.previous_index+1:
            raise ValueError('Incomplete saved frame sequence')
        if self.previous_pts is not None and at <= self.previous_pts:
            raise ValueError('PTS must increase')
        if type(row['native_pts']) is not int or abs(
                float(Fraction(row['native_pts'])*Fraction(row['time_base']))-at) > 1e-8:
            raise ValueError('Native PTS mismatch')
        if type(row['camera_support']) is not bool:
            raise ValueError('Explicit frame camera support required')
        gap = self.previous_pts is not None and at-self.previous_pts > self.policy['max_frame_gap']
        if gap:
            self.positive.clear()
        paths = {}
        maps = {}
        for path in row['point_paths']:
            wid = path['window_id']
            if not isinstance(wid, str) or not wid or wid in paths:
                raise ValueError('Unique nonempty window IDs required')
            current = point_map(path)
            if wid in self.seen:
                if wid not in self.histories:
                    raise ValueError('Retired window reappeared')
                last = self.histories[wid][-1]
                if not set(current).issubset(last['points']):
                    raise ValueError('Dropped point reappeared')
                if path['seed_pts'] != last['seed_pts']:
                    raise ValueError('Window origin changed')
            else:
                if abs(number(path['seed_pts'], 'seed PTS', 0.)-at) > 1e-8:
                    raise ValueError('Missing birth of saved window')
                self.histories[wid] = deque()
                self.seen.add(wid)
            paths[wid], maps[wid] = path, current
        if row['windows'] != len(paths):
            raise ValueError('Saved window count mismatch')
        signals = []
        signal_ids = set()
        for signal in row['signals']:
            wid = signal['window_id']
            if wid not in paths or wid in signal_ids:
                raise ValueError('Signal must correspond to one live window')
            signal_ids.add(wid)
            if not signal['seed_pts'] <= signal['reference_pts'] < at:
                raise ValueError('Future/invalid reference')
            if signal['seed_pts'] != paths[wid]['seed_pts'] or signal['evidence_until_pts'] != at:
                raise ValueError('Signal provenance mismatch')
            if signal['camera_support'] != row['camera_support']:
                raise ValueError('Camera support mismatch')
            current = point_map(signal)
            if current != maps[wid] or len(current) != signal['point_count']:
                raise ValueError('Signal and path positions disagree')
            reference = next((r for r in self.histories[wid]
                              if abs(r['pts']-signal['reference_pts']) <= 1e-8), None)
            if reference is None or not set(current).issubset(reference['points']):
                raise ValueError('Saved corresponding reference points missing')
            movements = [(p[0]-reference['points'][k][0], p[1]-reference['points'][k][1])
                         for k, p in current.items()]
            explanation = explain_score(signal, self.policy['score_threshold'])
            signals.append(dict(window_id=wid, seed_pts=signal['seed_pts'],
                reference_pts=signal['reference_pts'], seed_cache_index=signal['seed_cache_index'],
                seed_track_ids=signal.get('seed_track_ids', []),
                point_ids=list(current), point_count=len(current),
                raw_median_displacement_pixels=[statistics.median(v[k] for v in movements) for k in (0, 1)],
                raw_displacement_is_camera_uncorrected=True,
                box_overlap=overlap_audit(current, row['actual_boxes'], self.size, self.policy['seed_score']),
                components={k: signal[k] for k in ('proximity', 'crossing_fraction', 'upward_image_motion',
                    'local_deformation', 'normal_progress', 'motion_change', 'coherence')},
                score_explanation=explanation))
        best = max(signals, key=lambda s: s['score_explanation']['saved_score'], default=None)
        score = best['score_explanation']['saved_score'] if best else 0.
        if abs(number(row['score'], 'frame score', 0., 1.)-score) > 1e-6:
            raise ValueError('Frame score differs from its signals')
        self.positive.append((at, score))
        while self.positive and at-self.positive[0][0] > self.policy['support_window']+1e-9:
            self.positive.popleft()
        positives = [t for t, s in self.positive if s >= self.policy['score_threshold']]
        enough = (score >= self.policy['score_threshold'] and
                  len(positives) >= self.policy['min_support_frames'] and
                  positives[-1]-positives[0] >= self.policy['support_seconds']-1e-9)
        emit = enough and at-self.last_emit >= self.policy['cooldown_seconds']-1e-9
        if emit:
            self.last_emit = at
        if bool(row.get('event')) != bool(emit):
            raise ValueError('Stored event disagrees with unchanged evidence latch')
        if row.get('event'):
            e = row['event']
            if e['decision_time_pts'] != at or e['evidence_until_pts'] != at:
                raise ValueError('Event clock mismatch')
            if e['evidence']['window_id'] != best['window_id']:
                raise ValueError('Event does not use winning window')
            self.event_pts.append(at)
        stage = ('no_signal' if not signals else 'below_score_threshold' if score < self.policy['score_threshold']
                 else 'temporal_support_not_ready' if not enough else 'cooldown' if not emit else 'candidate')
        result = dict(frame_index=index, pts=at, native_pts=row['native_pts'], time_base=row['time_base'],
            score=score, stage=stage, best_window_id=None if best is None else best['window_id'],
            active_windows=len(paths), window_capacity_reached=len(paths)>=self.policy['max_windows'],
            capacity_proves_target_starvation=False, signals=signals, event_present=bool(emit),
            semantic_tracking_quality=None, intrusion_truth=None)
        self.histories = {wid: self.histories[wid] for wid in paths}
        for wid in paths:
            history = self.histories[wid]
            history.append(dict(pts=at, points=maps[wid], seed_pts=paths[wid]['seed_pts']))
            while len(history)>1 and at-history[0]['pts'] > self.policy['window_seconds']+1e-9:
                history.popleft()
        self.frames += 1
        self.signal_count += len(signals)
        self.previous_pts, self.previous_index = at, index
        return result


def parse_range(value):
    try:
        name, times = value.split('=', 1)
        start, end = map(float, times.split(':'))
        number(start, 'range start', 0.); number(end, 'range end', 0.)
        if not name or end <= start:
            raise ValueError()
    except (ValueError, TypeError) as exc:
        raise ValueError('Review range must be NAME=START:END, e.g. missed=64:74') from exc
    return dict(name=name, start=start, end=end)


def summarize_range(rows, spec):
    selected = [r for r in rows if spec['start'] <= r['pts'] <= spec['end']]
    stages = {k: sum(r['stage']==k for r in selected) for k in
              ('no_signal', 'below_score_threshold', 'temporal_support_not_ready', 'cooldown', 'candidate')}
    best = max(selected, key=lambda r:r['score'], default=None)
    return dict(**spec, coverage='present' if selected else 'not_available', frames=len(selected),
        stages=stages, highest_score=None if best is None else best['score'],
        highest_score_pts=None if best is None else best['pts'],
        highest_score_window=None if best is None else best['best_window_id'],
        candidate_pts=[r['pts'] for r in selected if r['event_present']],
        capacity_frames=sum(r['window_capacity_reached'] for r in selected),
        intrusion_truth=None, semantic_tracking_quality=None)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def execute(directory: Path, output: Path, ranges: Iterable[dict]):
    directory, output = Path(directory), Path(output)
    files = {name: directory/name for name in ('request.json', 'summary.json', 'frame-evidence.jsonl',
                                               'transition-events.json')}
    before = {name: sha(path) for name, path in files.items()}
    request = json.loads(files['request.json'].read_text(encoding='utf-8'))
    summary = json.loads(files['summary.json'].read_text(encoding='utf-8'))
    if request['experiment'] != 'EXP-0042' or summary['experiment'] != 'EXP-0042':
        raise ValueError('Completed saved EXP-0042 output required')
    if request['policy'] != summary['policy']:
        raise ValueError('Policy mismatch')
    if not output.resolve().is_relative_to(Path('outputs').resolve()) or output.exists() or output.is_symlink():
        raise ValueError('Use a NEW local directory under outputs/')
    if any(p.is_symlink() for p in output.parents):
        raise ValueError('Symlink output parent forbidden')
    # Native size is read from the bound scene, never assumed to be 1920x1080.
    scenes = []
    for name, expected in request['input_sha256'].items():
        p = Path(name)
        if 'scene' in name and p.suffix == '.json' and p.is_file():
            value = json.loads(p.read_text(encoding='utf-8'))
            if all(k in value for k in ('source_size', 'line', 'approach_polygon')):
                if sha(p) != expected:
                    raise ValueError('Bound scene changed')
                scenes.append((p, value, expected))
    if len(scenes) != 1:
        raise ValueError('Exactly one bound scene required')
    scene_path, scene, scene_sha = scenes[0]
    engine = SavedEvidenceAudit(request['policy'], scene['source_size'])
    output.mkdir(parents=True, exist_ok=False)
    compact = []
    ranges = list(ranges)
    try:
        with files['frame-evidence.jsonl'].open(encoding='utf-8') as source, \
                (output/'frame-diagnostics.jsonl').open('x', encoding='utf-8') as sink, \
                (output/'signals.csv').open('x', newline='', encoding='utf-8') as csv_stream:
            fields = ['pts', 'frame_index', 'window_id', 'seed_pts', 'reference_pts', 'score', 'route',
                      'cross_branch', 'local_branch', 'proximity', 'upward_image_motion',
                      'local_deformation', 'normal_progress', 'motion_change', 'crossing_fraction',
                      'proximity_ceiling', 'local_ceiling', 'camera_penalty', 'point_count',
                      'within_any_box', 'within_multiple_boxes', 'outside_all_boxes']
            writer = csv.DictWriter(csv_stream, fieldnames=fields); writer.writeheader()
            for line in source:
                if not line.strip(): continue
                row = engine.push(json.loads(line))
                sink.write(json.dumps(row, ensure_ascii=False, allow_nan=False)+'\n')
                compact.append({k:v for k,v in row.items() if k != 'signals'})
                for signal in row['signals']:
                    ex = signal['score_explanation']; overlap = signal['box_overlap']
                    csv_row = {k: signal[k] for k in ('window_id', 'seed_pts', 'reference_pts', 'point_count')}
                    csv_row.update({k: signal['components'][k] for k in ('proximity','upward_image_motion',
                        'local_deformation','normal_progress','motion_change','crossing_fraction')})
                    csv_row.update({k: ex[k] for k in ('route','cross_branch','local_branch',
                        'proximity_ceiling','local_ceiling','camera_penalty')})
                    csv_row.update({k: overlap[k] for k in ('within_any_box','within_multiple_boxes','outside_all_boxes')})
                    writer.writerow(dict(csv_row, pts=row['pts'], frame_index=row['frame_index'], score=ex['saved_score']))
        expected = json.loads(files['transition-events.json'].read_text(encoding='utf-8'))
        if engine.frames != summary['frames'] or engine.event_pts != [e['decision_time_pts'] for e in expected]:
            raise ValueError('Saved full-run frame/event counts mismatch')
        if before != {k: sha(v) for k,v in files.items()} or sha(scene_path) != scene_sha:
            raise ValueError('Read-only inputs changed')
        report = dict(experiment='EXP-0043', video_id=summary['video_id'], frames=engine.frames,
            checked_signals=engine.signal_count, arithmetic_reproduced=True, event_pts=engine.event_pts,
            ranges=[summarize_range(compact, s) for s in ranges],
            input_sha256=before, scene_sha256=scene_sha, code_sha256=sha(__file__),
            new_flow_calls=0, model_calls=0, alarm_changes=0, accuracy=None,
            tracking_vs_decision_root_cause='requires_original_and_saved_path_review',
            scope='diagnostic_replay_not_performance_improvement')
        write_json(output/'summary.json', report)
        write_json(output/'inspection-plan.json', dict(ranges=ranges, video_id=summary['video_id'],
            evidence=str(files['frame-evidence.jsonl']), diagnostics=str(output/'frame-diagnostics.jsonl'),
            instruction='Show original pixels, ALL saved windows, and one selected window; do not show only the winning score.',
            semantic_labels_not_generated=True))
        return report
    except Exception as exc:
        write_json(output/'failure.json', dict(error=repr(exc), checked_frames=engine.frames,
                                             arithmetic_success=False))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--range', action='append', default=[], dest='ranges', help='Review only: NAME=START:END')
    args = parser.parse_args()
    print(json.dumps(execute(args.directory, args.output, map(parse_range,args.ranges)),
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
