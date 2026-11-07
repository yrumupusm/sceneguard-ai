"""Audit selected actor annotations without promoting them to detector ground truth."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(plan_path):
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    counts = Counter()
    groups, sources = defaultdict(set), defaultdict(set)
    labels, actors = {}, {}
    missing, different, invalid, targets = 0, 0, 0, 0
    for window in plan['windows']:
        split = window['split']
        if split not in ('train', 'validation'):
            raise ValueError('Only existing training and validation candidates may be audited')
        groups[split].add(window['event_group'])
        sources[split].add(window['source_sha256'])
        for target in window['targets']:
            targets += 1
            counts[split, target['action_class']] += 1
            path, expected = target['label_path'], target['label_sha256']
            if path in labels and labels[path] != expected:
                raise ValueError('Conflicting annotation binding')
            labels[path] = expected
            boxes = target.get('anchor_boxes_origin0_origin1', [])
            missing += not bool(boxes)
            valid = (len(boxes) == 2 and all(
                len(box) == 2 and all(len(point) == 2 for point in box)
                and all(isinstance(v, (int, float)) and math.isfinite(v) for point in box for v in point)
                and box[1][0] > box[0][0] and box[1][1] > box[0][1]
                for box in boxes))
            invalid += not valid
            different += bool(valid and boxes[0] != boxes[1])
            key = (target['source_sha256'], target['anchor_frame_index'], target['actor_id'], target['object_id'])
            entry = actors.setdefault(key, dict(split=split, labels=set()))
            if entry['split'] != split:
                raise ValueError('Actor frame appears in both splits')
            entry['labels'].add(target['label'])
    if groups['train'] & groups['validation'] or sources['train'] & sources['validation']:
        raise ValueError('Cross-split capture or source overlap')
    for path, expected in labels.items():
        if sha(path) != expected:
            raise ValueError('Annotation bytes changed: ' + path)
    return dict(
        status='candidate_label_audit_not_detector_training_release',
        plan_sha256=sha(plan_path), auditor_sha256=sha(__file__),
        windows=len(plan['windows']), target_occurrences=targets,
        unique_actor_frame_candidates=len(actors), target_label_files_verified=len(labels),
        target_occurrences_by_split_and_action={s + ':' + a: n for (s, a), n in sorted(counts.items())},
        groups_by_split={s: len(v) for s, v in groups.items()},
        source_hashes_by_split={s: len(v) for s, v in sources.items()},
        cross_split_event_group_overlap=0, cross_split_source_hash_overlap=0,
        target_occurrences_without_box_pairs=missing,
        target_occurrences_with_origin_coordinate_difference=different,
        invalid_box_pair_geometry=invalid,
        candidate_actor_frames_with_conflicting_binary_labels=sum(len(r['labels']) > 1 for r in actors.values()),
        all_visible_people_annotated_verified=False,
        frame_origin_semantics_verified_for_all_sources=False,
        training_release=False, new_detector_training_runs=0,
        limitations=[
            'Counts describe selected actor annotations, not a complete all-person frame dataset.',
            'Origin coordinate differences do not by themselves establish misannotation.',
            'Weak scene labels cannot become verified detector background or action states automatically.',
            'Validation normal subtypes are sitting only; walking/waiting/turnback need augmentation.',
            'No pixels, held-out test annotations, or protected school annotations were read.',
        ])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.plan)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')
    print(json.dumps(result, ensure_ascii=False))
