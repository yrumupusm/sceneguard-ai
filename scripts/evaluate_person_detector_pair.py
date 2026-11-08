"""Compare person boxes on identical human-confirmed validation frames only."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

MANIFEST_SHA = '1bda84cc3421bcfc1b528bfb4e4092c02e9ec22d4a09c41907ff46211381ad18'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def iou(a, b):
    intersection = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    union = (a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-intersection
    return intersection/union if union else 0.0


def match(gt, boxes, scores, threshold=.5, iou_threshold=.5):
    """Deterministic maximum-cardinality matching; no temporal or identity inference.

    Candidate edges prefer higher IoU then lower GT index. Prediction traversal
    prefers confidence then source order. Reassignments maximize matched people;
    this is a fixed-threshold count, not confidence-ranked AP or an IoU optimum.
    """
    selected = sorted((i for i, score in enumerate(scores) if score >= threshold), key=lambda i: (-scores[i], i))
    edges = {p: sorted((g for g in range(len(gt)) if iou(gt[g], boxes[p]) >= iou_threshold),
                       key=lambda g: (-iou(gt[g], boxes[p]), g)) for p in selected}
    assigned = {}

    def augment(p, visited):
        for g in edges[p]:
            if g in visited:
                continue
            visited.add(g)
            if g not in assigned or augment(assigned[g], visited):
                assigned[g] = p
                return True
        return False

    for p in selected:
        augment(p, set())
    matched = [dict(gt_index=g, prediction_index=p, iou=iou(gt[g], boxes[p])) for g, p in sorted(assigned.items())]
    return dict(tp=len(matched), fp=len(selected)-len(matched), fn=len(gt)-len(matched),
                matches=matched, unmatched_prediction_indices=[p for p in selected if p not in assigned.values()],
                unmatched_gt_indices=[g for g in range(len(gt)) if g not in assigned])


def validate_predictions(rows, frames):
    predictions = {r['frame_id']: r for r in rows}
    if len(predictions) != len(rows) or set(predictions) != {f['frame_id'] for f in frames}:
        raise ValueError('Exact validation frames required; no duplicate, omitted, or train frames')
    for frame in frames:
        r = predictions[frame['frame_id']]
        if r['image_sha256'] != frame['image_sha256'] or r['source_pts'] != frame['source_pts']:
            raise ValueError('Prediction frame pixels/time differ')
        if len(r['boxes']) != len(r['person_scores']):
            raise ValueError('Boxes/scores differ')
        width, height = frame['source_size']
        for b, score in zip(r['boxes'], r['person_scores']):
            if (len(b) != 4 or not all(type(x) in (int, float) and math.isfinite(x) for x in b+[score])
                    or not 0 <= score <= 1 or not (0 <= b[0] < b[2] <= width and 0 <= b[1] < b[3] <= height)):
                raise ValueError('Invalid original-pixel prediction')
    return predictions


def evaluate(manifest, before_rows, after_rows):
    frames = [f for f in manifest['frames'] if f['split'] == 'validation']
    if (len(frames) != 25 or len({f['event_group'] for f in frames}) != 1
            or not all(f['person_completeness_verified'] for f in frames)
            or sum(len(f['confirmed_person_boxes']) for f in frames) != 31):
        raise ValueError('Fixed reviewed25 validation frames/31 boxes/one event required')
    before, after = (validate_predictions(r, frames) for r in (before_rows, after_rows))
    records, paired = [], Counter()
    for f in frames:
        fid = f['frame_id']
        gt = [b['xyxy'] for b in f['confirmed_person_boxes']]
        a, b = (match(gt, p[fid]['boxes'], p[fid]['person_scores']) for p in (before, after))
        aa, bb = ({r['gt_index'] for r in x['matches']} for x in (a, b))
        states = []
        for g, truth in enumerate(f['confirmed_person_boxes']):
            state = ('both_detected' if g in bb else 'new_miss') if g in aa else ('recovered' if g in bb else 'both_missed')
            paired[state] += 1
            states.append(dict(gt_id=truth['id'], gt_index=g, state=state))
        records.append(dict(frame_id=fid, source_pts=f['source_pts'], before=a, after=b, paired_people=states))
    metrics = {}
    for condition in ('before', 'after'):
        sums = {k:sum(r[condition][k] for r in records) for k in ('tp', 'fp', 'fn')}
        tp, fp, fn = (sums[k] for k in ('tp', 'fp', 'fn'))
        overlaps = [m['iou'] for r in records for m in r[condition]['matches']]
        metrics[condition] = dict(**sums, precision=tp/(tp+fp) if tp+fp else None,
            recall=tp/(tp+fn) if tp+fn else None, f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
            mean_matched_iou=sum(overlaps)/len(overlaps) if overlaps else None)
    return dict(schema_version=1, scope='EXP0067 reviewed validation25/one event; not school45',
        person_threshold=.5, iou_threshold=.5, matching='deterministic_maximum_cardinality_per_frame',
        frames_evaluated=25, gt_box_rows=31, event_groups=1, metrics=metrics,
        paired_gt_counts={k:paired[k] for k in ('both_detected','recovered','new_miss','both_missed')},
        frames=records, action_metrics=None, school_improvement=None, independent_generalization=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'before', 'after', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    if sha(args.manifest) != MANIFEST_SHA:
        raise ValueError('Fixed human-confirmed source manifest required')
    result = evaluate(json.loads(args.manifest.read_text()),
                      [json.loads(line) for line in args.before.read_text().splitlines()],
                      [json.loads(line) for line in args.after.read_text().splitlines()])
    result['input_sha256'] = {k:sha(getattr(args, k)) for k in ('manifest','before','after')}
    result['evaluator_sha256'] = sha(__file__)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(metrics=result['metrics'], paired_gt_counts=result['paired_gt_counts'])))
