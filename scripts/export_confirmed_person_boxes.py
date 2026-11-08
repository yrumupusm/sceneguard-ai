"""Export exact displayed boxes explicitly confirmed in EXP-0067 web answers.

Creates a new person-label artifact; never edits drafts, editor revisions, or
original action annotations, and never releases or starts training.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from webapp.review_request_store import configured_store, validate_binding

PACKAGE_SHA = 'f5c327472fe72da00c19ffe895d24d2267b869c2aee0f641e601db225ef5546a'
PREVIEW_SHA = '2471d865d4245b2764c237ea7880c832747005531b4f61ebdb59b4f2a8444960'
ANSWER = '전체25프레임의 주황색 박스와 보이는 사람을 확인했고 수정할 곳 없음'
CASES = {1: ('train', 99), 3: ('train', 159), 5: ('validation', 40)}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def select(package, preview, responses):
    """Join explicit answers to every shown frame and the exact displayed boxes."""
    frames = {f['frame_id']: f for f in package['frames']}
    if len(frames) != 75 or len(frames) != len(package['frames']):
        raise ValueError('Exactly 75 unique bound frames required')
    if preview['display_threshold'] != .5 or preview['fps'] != 3:
        raise ValueError('Display threshold or clock changed')
    cases = {c['case_number']: c for c in preview['cases']}
    if set(cases) != set(CASES) or len(preview['cases']) != 3:
        raise ValueError('Exactly three reviewed cases required')
    answers = {r['artifact_id']: r for r in responses['requests']}
    if len(answers) != 3 or len(responses['requests']) != 3:
        raise ValueError('Exactly three answer versions required')
    selected, seen = [], set()
    for number, (split, start) in CASES.items():
        case = cases[number]
        answer = answers[f'exp0067-repair-{number:02d}-video']
        if (answer['experiment_id'] != 'EXP-0067' or answer['answer_version'] < 1
                or answer['status'] not in ('acknowledged', 'applied')
                or answer['answer'] != ANSWER or answer.get('note', '').strip()):
            raise ValueError('Explicit unqualified box-completeness answer required')
        if case['frame_count'] != 25 or len(case['frames']) != 25:
            raise ValueError('Exactly 25 shown frames per answer required')
        for index, shown in enumerate(case['frames']):
            frame = frames[shown['frame_id']]
            if (frame['frame_id'] in seen or frame['case_number'] != number
                    or frame['split'] != split or frame['frame_index'] != start + index
                    or abs(frame['source_pts'] - (start + index) / 3) > 1e-8
                    or frame['source_pts'] != shown['source_pts']
                    or frame['image_sha256'] != shown['image_sha256']):
                raise ValueError('Reviewed frame/time/split binding differs')
            expected = [dict(id=c['id'], xyxy=c['xyxy'], score=c['score'])
                        for c in frame['candidates'] if c['kind'] == 'model' and c['score'] >= .5]
            if expected != shown['displayed_proposals'] or not expected:
                raise ValueError('Only exact displayed nonempty model boxes may be imported')
            if len({b['id'] for b in expected}) != len(expected):
                raise ValueError('Duplicate displayed proposal ID')
            width, height = frame['source_size']
            for b in expected:
                xy = b['xyxy']
                if (len(xy) != 4 or not all(type(x) in (int, float) and math.isfinite(x) for x in xy)
                        or not (0 <= xy[0] < xy[2] <= width and 0 <= xy[1] < xy[3] <= height)):
                    raise ValueError('Invalid confirmed box coordinates')
            selected.append((frame, expected, answer))
            seen.add(frame['frame_id'])
    if seen != set(frames):
        raise ValueError('Unreviewed frame in package')
    for key in ('source_sha256', 'event_group'):
        train = {f[key] for f, _, _ in selected if f['split'] == 'train'}
        val = {f[key] for f, _, _ in selected if f['split'] == 'validation'}
        if train & val:
            raise ValueError('Source/event leakage across splits')
    return selected


def current_answers(config, responses):
    current = {r['id']: r for r in configured_store(config).list('EXP-0067')}
    for r in responses['requests']:
        actual = current[r['id']]
        for key in ('answer_version', 'answer', 'note', 'artifact_id', 'source_binding_sha256'):
            if actual[key] != r[key]:
                raise ValueError('Newer or different web answer: ' + key)
        if actual['status'] not in ('acknowledged', 'applied'):
            raise ValueError('Answer not acknowledged')
        validate_binding(config, actual)


def export(config_path, responses_path, package_path, preview_path, output):
    config, responses, package, preview = map(read, (config_path, responses_path, package_path, preview_path))
    if sha(package_path) != PACKAGE_SHA or sha(preview_path) != PREVIEW_SHA or preview['package_sha256'] != PACKAGE_SHA:
        raise ValueError('Immutable executed package/preview changed')
    current_answers(config, responses)
    selected = select(package, preview, responses)
    # The immutable preparation already verified the protected source/group split;
    # retain it and independently reject protected school hashes here as well.
    from scripts.prepare_person_label_repair import FIXED
    baseline_path, baseline_sha = FIXED['baseline']
    if sha(baseline_path) != baseline_sha:
        raise ValueError('Protected baseline changed')
    protected = {r['sha256'] for r in read(baseline_path)['regression_only_videos']}
    if any(f['source_sha256'] in protected for f, _, _ in selected):
        raise ValueError('Protected school source')
    for case in preview['cases']:
        artifact = config['artifacts'][f"exp0067-repair-{case['case_number']:02d}-video"]
        if Path(artifact['path']).resolve() != Path(case['video']).resolve() or sha(case['video']) != case['video_sha256']:
            raise ValueError('Shown video binding changed')
    for f, _, _ in selected:
        if sha(f['image_path']) != f['image_sha256']:
            raise ValueError('Source image changed')
    current_answers(config, responses)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    records = []
    coco = {split: dict(images=[], annotations=[], categories=[dict(id=0, name='person')])
            for split in ('train', 'validation')}
    for image_id, (frame, boxes, answer) in enumerate(selected, 1):
        split, name = frame['split'], frame['frame_id']
        image = output/'images'/split/(name + '.png')
        label = output/'labels'/split/(name + '.txt')
        image.parent.mkdir(parents=True, exist_ok=True)
        label.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(frame['image_path'], image)
        if sha(image) != frame['image_sha256']:
            raise ValueError('Copied image differs')
        width, height = frame['source_size']
        lines = []
        for box in boxes:
            x1, y1, x2, y2 = box['xyxy']
            lines.append(f'0 {(x1+x2)/2/width:.10f} {(y1+y2)/2/height:.10f} {(x2-x1)/width:.10f} {(y2-y1)/height:.10f}')
            coco[split]['annotations'].append(dict(id=len(coco[split]['annotations'])+1,
                image_id=image_id, category_id=0, bbox=[x1, y1, x2-x1, y2-y1],
                area=(x2-x1)*(y2-y1), iscrowd=0, proposal_id=box['id']))
        label.write_text('\n'.join(lines)+'\n', encoding='utf-8')
        coco[split]['images'].append(dict(id=image_id, file_name=str(image.relative_to(output)), width=width, height=height))
        records.append(dict(**{k:frame[k] for k in ('frame_id','case_number','split','event_group',
            'source_sha256','source_size','frame_index','native_pts_tick','source_pts','source_rgb_sha256')},
            image=str(image.relative_to(output)), image_sha256=sha(image), label=str(label.relative_to(output)),
            label_sha256=sha(label), confirmed_person_boxes=boxes, person_completeness_verified=True,
            annotation_method='explicit_web_review_of_all_displayed_boxes_and_people',
            request_id=answer['id'], answer_version=answer['answer_version'],
            source_binding_sha256=answer['source_binding_sha256'],
            action_ground_truth_verified=False, identity_ground_truth_verified=False))
    # Recheck concurrent answer changes before marking an export complete.
    current_answers(config, responses)
    for split, data in coco.items():
        (output/f'{split}.coco.json').write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
    (output/'dataset.yaml').write_text(f'path: {json.dumps(str(output))}\ntrain: images/train\nval: images/validation\nnames:\n  0: person\n')
    manifest = dict(schema_version=1, experiment_id='EXP-0067', purpose='human_confirmed_person_boxes',
        training_release=False, person_boxes_human_verified=True, action_ground_truth_verified=False,
        protected_school_or_test_used=False, frames=records,
        frame_counts=dict(Counter(r['split'] for r in records)),
        box_counts={s:sum(len(r['confirmed_person_boxes']) for r in records if r['split']==s) for s in coco},
        group_counts={s:len({r['event_group'] for r in records if r['split']==s}) for s in coco},
        package_sha256=PACKAGE_SHA, preview_sha256=PREVIEW_SHA, responses_sha256=sha(responses_path),
        exporter_sha256=sha(__file__), execution_binding=package['execution_binding'],
        derived_files={p.name:sha(p) for p in (output/'train.coco.json', output/'validation.coco.json', output/'dataset.yaml')},
        limitations=['Only displayed75 frames; not the full source videos',
                     'Only three clips; validation is not independent generalization evidence',
                     'YOLO26x proposals explicitly reviewed by a human; proposal-origin selection bias remains',
                     'No inferred actions, identities, hidden proposals, or union with original labels'])
    (output/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k:manifest[k] for k in ('frame_counts','box_counts','group_counts','training_release')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('config', 'responses', 'package', 'preview', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    export(args.config, args.responses, args.package, args.preview, args.output)
