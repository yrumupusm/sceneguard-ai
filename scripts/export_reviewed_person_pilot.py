"""Export only the displayed frames covered by explicit person-completeness reviews.

This produces a preparation artifact, not a released training dataset. It does not
certify action labels, precise box coordinates, frame origin, or unseen frames.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def select_cases(review, responses, decisions, plan):
    answers = {r['id']: r for r in responses['requests']}
    windows = {w['window_id']: w for w in plan['windows']}
    cases = {c['number']: c for c in review['cases']}
    selected = []
    seen = set()
    for decision in decisions['cases']:
        case = cases[decision['case_number']]
        answer = answers[decision['request_id']]
        window = windows[case['window_id']]
        if case['number'] in seen:
            raise ValueError('Duplicate review case')
        seen.add(case['number'])
        if (answer['answer_version'] != decision['answer_version'] or
                answer['source_binding_sha256'] != decision['source_binding_sha256'] or
                answer['artifact_id'] != f"exp0066-label-{case['number']:02d}-video" or
                answer['status'] not in ('acknowledged', 'applied')):
            raise ValueError('Review answer binding/version mismatch')
        if (case['window_id'] != decision['window_id'] or
                case['split'] != decision['original_split'] or
                case['split'] != window['split'] or
                case['split'] not in ('train', 'validation') or
                case['source_sha256'] != window['source_sha256'] or
                case['event_group'] != window['event_group'] or
                decision['frame_indices'] != [f['frame_index'] for f in case['frames']]):
            raise ValueError('Review scope or original split changed')
        if decision['disposition'] == 'hold_incomplete_or_uncertain_person_scope':
            continue
        if decision['disposition'] != 'export_reviewed_person_scope':
            raise ValueError('Unknown disposition')
        if answer['answer'] != '보이는 사람은 모두 박스가 있음':
            raise ValueError('No explicit person-completeness answer')
        if case['displayed_frame_origin'] != 1 or not case['frames']:
            raise ValueError('Unexpected display origin or empty review')
        for frame in case['frames']:
            if not frame['boxes']['1']:
                raise ValueError('No empty-background labels may be inferred')
        selected.append((case, window, decision))
    if seen != set(cases):
        raise ValueError('Missing review dispositions')
    for key in ('event_group', 'source_sha256'):
        train = {c[key] for c, _, _ in selected if c['split'] == 'train'}
        validation = {c[key] for c, _, _ in selected if c['split'] == 'validation'}
        if train & validation:
            raise ValueError('Cross-split leakage')
    return selected


def export(review_path, responses_path, decisions_path, plan_path, output):
    import av
    from PIL import Image
    review, responses, decisions, plan = map(read, (review_path, responses_path, decisions_path, plan_path))
    if (sha(review_path) != decisions['review_sha256'] or
            sha(responses_path) != decisions['response_snapshot_sha256'] or
            sha(plan_path) != review['plan_sha256']):
        raise ValueError('Input snapshot changed')
    selected = select_cases(review, responses, decisions, plan)
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for case, window, decision in selected:
        if sha(window['source_path']) != case['source_sha256']:
            raise ValueError('Source video changed')
        for path, digest in case['label_bindings'].items():
            if sha(path) != digest:
                raise ValueError('Source annotation changed')
        wanted = {f['native_pts_tick']: f for f in case['frames']}
        found = set()
        with av.open(window['source_path']) as source:
            stream = source.streams.video[0]
            stream.codec_context.thread_count = 1
            for frame in source.decode(stream):
                if frame.pts > max(wanted):
                    break
                if frame.pts not in wanted:
                    continue
                ref = wanted[frame.pts]
                rgb = frame.to_ndarray(format='rgb24')
                if (hashlib.sha256(rgb.tobytes()).hexdigest() != ref['source_rgb_sha256'] or
                        abs(float(frame.pts * stream.time_base) - ref['source_pts']) > 1e-8 or
                        list(rgb.shape[1::-1]) != case['source_size']):
                    raise ValueError('Decoded source pixels/clock/geometry changed')
                width, height = case['source_size']
                lines = []
                for box in ref['boxes']['1']:
                    x1, y1, x2, y2 = box['xyxy']
                    if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
                        raise ValueError('Invalid existing annotation geometry')
                    lines.append(f'0 {(x1+x2)/2/width:.10f} {(y1+y2)/2/height:.10f} {(x2-x1)/width:.10f} {(y2-y1)/height:.10f}')
                stem = f"case-{case['number']:02d}-frame-{ref['frame_index']:06d}"
                folder = output / case['split']
                folder.mkdir(exist_ok=True)
                image_path, label_path = folder / (stem + '.png'), folder / (stem + '.txt')
                Image.fromarray(rgb).save(image_path)
                label_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
                rows.append(dict(case_number=case['number'], split=case['split'],
                    event_group=case['event_group'], source_sha256=case['source_sha256'],
                    frame_index=ref['frame_index'], source_pts=ref['source_pts'],
                    native_pts_tick=frame.pts, source_rgb_sha256=ref['source_rgb_sha256'],
                    original_annotations=ref['boxes']['1'], request_id=decision['request_id'],
                    answer_version=decision['answer_version'], image=str(image_path.relative_to(output)),
                    image_sha256=sha(image_path), label=str(label_path.relative_to(output)), label_sha256=sha(label_path)))
                found.add(frame.pts)
        if found != set(wanted):
            raise ValueError('Missing reviewed frames')
    result = dict(schema_version=1, purpose='reviewed_person_preparation_only', training_release=False,
        action_ground_truth_verified=False, precise_boxes_certified=False, frame_origin_certified=False,
        class_names=['person'], model_inference_count=0, displayed_frame_origin=1,
        input_sha256={str(p): sha(p) for p in (review_path, responses_path, decisions_path, plan_path)},
        exporter_sha256=sha(__file__), frames=rows, frame_counts=dict(Counter(r['split'] for r in rows)),
        held_case_numbers=[d['case_number'] for d in decisions['cases'] if d['disposition'].startswith('hold_')])
    (output / 'manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(frame_counts=result['frame_counts'], training_release=False, manifest_sha256=sha(output/'manifest.json'))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('review', 'responses', 'decisions', 'plan', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    export(args.review, args.responses, args.decisions, args.plan, args.output)
