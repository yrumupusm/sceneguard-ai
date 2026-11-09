"""Freeze the existing 197 reviewed frames; export incomplete repairs separately.

Read-only inputs, exclusive-create outputs, no inference or training. Absolute
image/label references preserve the exact previously reviewed bytes and boxes.
"""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
READY = ROOT / 'outputs/model-comparison/exp0070/data-readiness-v1'
OLD = ROOT / 'outputs/model-comparison/exp0067/confirmed-person-v1/manifest.json'
NEW = ROOT / 'outputs/model-comparison/exp0071/confirmed-person-v1/manifest.json'
REPAIR = ROOT / 'outputs/model-comparison/exp0073/box-repairs-v1'
APPROVAL = ROOT / 'runtime/model-comparison/exp0073/coordinate-approval-v1/approved-replacement-boxes.json'
CONFIG = Path('/home/jhc7484/dev/sceneguard-orca-lab/runtime/orca-lab/local_config.json')
WEB_PYTHON = CONFIG.parents[2] / '.venv-orca-lab/bin/python'
FIXED = {
    OLD: '1bda84cc3421bcfc1b528bfb4e4092c02e9ec22d4a09c41907ff46211381ad18',
    NEW: '837bbb18e2a6cd2d565387f60128768e02b014b897205b3245548dec54bbb90b',
}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def bindings(paths):
    return {str(Path(p).resolve()): sha(p) for p in paths}


def preserved(before):
    for path, expected in before.items():
        if sha(path) != expected:
            raise ValueError('Input changed: ' + path)


def box_valid(box, size):
    if (len(box) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) for v in box)
            or not (0 <= box[0] < box[2] <= size[0] and 0 <= box[1] < box[3] <= size[1])):
        raise ValueError('Invalid box')


def validate_frame(frame):
    for key in ('image', 'label'):
        if sha(frame[key]) != frame[key + '_sha256']:
            raise ValueError('Changed ' + key + ': ' + frame['frame_id'])
    with Path(frame['image']).open('rb') as image:
        header = image.read(24)
    if header[:8] != b'\x89PNG\r\n\x1a\n' or list(struct.unpack('>II', header[16:24])) != frame['source_size']:
        raise ValueError('Image dimensions differ')
    lines = Path(frame['label']).read_text().splitlines()
    boxes = frame['confirmed_person_boxes']
    if len(lines) != len(boxes):
        raise ValueError('Label count differs')
    width, height = frame['source_size']
    for line, box in zip(lines, boxes):
        box_valid(box['xyxy'], frame['source_size'])
        values = list(map(float, line.split()))
        if len(values) != 5 or values[0] != 0 or not all(math.isfinite(x) for x in values):
            raise ValueError('Invalid person YOLO label')
        _, cx, cy, w, h = values
        restored = [(cx-w/2)*width, (cy-h/2)*height, (cx+w/2)*width, (cy+h/2)*height]
        if max(abs(x-y) for x, y in zip(restored, box['xyxy'])) > 1e-5:
            raise ValueError('Label geometry differs')


def validate_splits(frames):
    for key in ('source_sha256', 'event_group', 'capture_reservation'):
        seen = {}
        for frame in frames:
            value = frame[key]
            if not value:
                raise ValueError('Missing split identity: ' + key)
            if value in seen and seen[value] != frame['split']:
                raise ValueError('Cross-split overlap: ' + key)
            seen[value] = frame['split']
    for key in ('frame_id',):
        if len({f[key] for f in frames}) != len(frames):
            raise ValueError('Duplicate frame ID')
    if len({(f['source_sha256'], f['frame_index']) for f in frames}) != len(frames):
        raise ValueError('Duplicate source frame')
    ids = [b['id'] for f in frames for b in f['confirmed_person_boxes']]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate box ID')


def current_web():
    """Read pending and saved answers, including applied versions; never mutate DB."""
    code = '''import json,sys
from webapp.review_request_store import configured_store, validate_binding
config=json.load(open(sys.argv[1])); store=configured_store(config)
rows=[]
for experiment in ('EXP-0067','EXP-0071','EXP-0072','EXP-0073','EXP-0074'):
    rows.extend(store.list(experiment))
for r in rows:
    if r.get('answer_version',0):validate_binding(config,r)
print(json.dumps(dict(requests=rows,pending=[r for r in rows if r['status'] in ('answered','acknowledged')]),ensure_ascii=False))
'''
    result = subprocess.run([str(WEB_PYTHON), '-c', code, str(CONFIG)], cwd=ROOT,
                            text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


def verify_web(web, frames):
    live = {r['id']: r for r in web['requests']}
    for f in frames:
        request = live[f.get('request_id', f.get('web_request_id'))]
        version = f.get('answer_version', f.get('web_answer_version'))
        if (request['answer_version'] != version
                or request['source_binding_sha256'] != f['source_binding_sha256']
                or request['status'] != 'applied'):
            raise ValueError('Reviewed answer changed: ' + f['frame_id'])


def context():
    plan = read(READY / 'split-proposal.json')
    inventory = [json.loads(line) for line in (READY / 'source-inventory.jsonl').read_text().splitlines()]
    closures = {c['group_id']: c for c in read(READY / 'group-closures.json')}
    groups = {g: c for c in plan['captures'] for g in c['original_group_ids']}
    return plan, inventory, closures, groups


def protected_hashes():
    baseline = ROOT / 'outputs/action-recognition/exp0063/baseline/attempt-002/baseline-lock.json'
    fingerprints = ROOT / 'outputs/action-recognition/exp0065/augmentation-v1/protected-content-fingerprints.jsonl'
    hashes = {r['sha256'] for r in read(baseline)['regression_only_videos']}
    hashes.update(json.loads(line)['recorded_source_sha256'] for line in fingerprints.read_text().splitlines())
    return hashes, [baseline, fingerprints]


def freeze(output):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(output)
    for path, expected in FIXED.items():
        if sha(path) != expected:
            raise ValueError('Confirmed manifest changed: ' + str(path))
    plan, inventory, closures, groups = context()
    protected, protected_paths = protected_hashes()
    inputs = bindings([OLD, NEW, READY/'split-proposal.json', READY/'group-closures.json',
                       READY/'source-inventory.jsonl', READY/'review-reuse.json', *protected_paths])
    rows = []
    for path in (OLD, NEW):
        for original in read(path)['frames']:
            frame = deepcopy(original)
            matches = [r for r in inventory if r['source_sha256'] == frame['source_sha256']
                       or (frame.get('source_id') and r['source_id'] == frame['source_id'])]
            if len(matches) != 1:
                raise ValueError('Ambiguous or missing source mapping')
            source = matches[0]
            if source['source_sha256'] is None:
                checked = [c for c in plan['cases'] if c['source_id'] == source['source_id']
                           and c['source_sha256'] == frame['source_sha256']]
                if len(checked) != 1:
                    raise ValueError('Source hash missing from checked EXP0070 plan')
            elif source['source_sha256'] != frame['source_sha256']:
                raise ValueError('Source hash differs')
            if (source['excluded'] or source['proposed_partition'] == 'protected_exp0064_test'
                    or frame['source_sha256'] in protected):
                raise ValueError('Protected/excluded source')
            group_id = source['group_id']
            closure = closures[group_id]
            if 'new:' + source['source_id'] not in closure['member_ids']:
                raise ValueError('Source missing from group closure')
            frame['source_id'] = source['source_id']
            frame['original_split'] = frame['split']
            frame['split'] = 'train' if frame['split'] in ('train', 'train_candidate') else 'development'
            frame['original_event_group'] = frame.get('event_group')
            frame['event_group'] = group_id
            reservation = groups.get(group_id)
            if reservation:
                if reservation['reserved_split'] != frame['split']:
                    raise ValueError('Reservation split changed')
                if frame.get('capture_reservation', reservation['reservation_id']) != reservation['reservation_id']:
                    raise ValueError('Reservation mapping differs')
                frame['capture_reservation'] = reservation['reservation_id']
                frame['capture_reservation_basis'] = 'EXP0070 split-proposal original_group_ids membership'
            else:
                # Case5 is NOT reservation19. Preserve the existing validation
                # closure, with an explicit local ID and unresolved physical relation.
                if path != OLD or frame['case_number'] != 5 or closure['partition'] != 'retained_validation':
                    raise ValueError('Unmapped capture reservation')
                frame['capture_reservation'] = 'legacy-closure-' + group_id
                frame['capture_reservation_basis'] = 'EXP0070 group-closures retained_validation; no numbered reservation'
                frame['capture_relation_unresolved'] = True
                frame['cohort_limitation'] = 'Legacy diagnostic development; EXP65 similarity/capture hold remains unresolved'
            for key in ('image', 'label'):
                frame[key] = str((path.parent / frame[key]).resolve())
            frame['confirmed_person_boxes'] = deepcopy(frame.pop('person_boxes', frame.get('confirmed_person_boxes', [])))
            frame['person_completeness_verified'] = True
            frame['completeness_basis'] = 'existing accepted EXP0067/EXP0071 reviewed export; exact frames only'
            frame['origin_manifest'] = str(path)
            frame['origin_manifest_sha256'] = inputs[str(path)]
            frame['physical_capture_independence_certified'] = False
            frame['training_release'] = False
            validate_frame(frame)
            rows.append(frame)
    validate_splits(rows)
    counts = dict(Counter(f['split'] for f in rows))
    boxes = {s: sum(len(f['confirmed_person_boxes']) for f in rows if f['split'] == s) for s in counts}
    empty = {s: sum(not f['confirmed_person_boxes'] for f in rows if f['split'] == s) for s in counts}
    if (counts, boxes, empty) != ({'train': 122, 'development': 75}, {'train': 333, 'development': 56}, {'train': 0, 'development': 25}):
        raise ValueError('Unexpected verified cohort counts')
    web = current_web()
    verify_web(web, rows)
    preserved(inputs)
    output.mkdir(parents=True, exist_ok=False)
    with (output/'exporter-source.py').open('xb') as stream:
        stream.write(Path(__file__).read_bytes())
    save(output/'web-answers-read-only.json', web)
    manifest = dict(schema_version=1, experiment_id='EXP-0074', purpose='frozen_verified197_person_baseline',
        person_boxes_human_verified=True, protected_school_or_test_used=False,
        person_completeness_verified=True, action_ground_truth_verified=False,
        training_release=False, standard_person_metrics_eligible=True,
        physical_capture_independence_certified=False, independent_test=False,
        frame_counts=counts, box_counts=boxes, explicit_empty_frame_counts=empty,
        frames=rows, input_sha256=inputs, exporter_sha256=sha(__file__),
        web_answers_snapshot_sha256=sha(output/'web-answers-read-only.json'),
        split_validation=dict(source_overlap=0, event_overlap=0, capture_reservation_overlap=0,
            basis='Exact hashes and EXP0070 metadata closures/reservations; not physical independence certification'),
        limitations=['Only exact existing reviewed197 frames; no newly corrected frames included',
            'Legacy case5 physical/capture similarity unresolved; diagnostic development only',
            'P05 moving/person and explicit empty windows retained despite whole-video other-action context',
            'No training authorization or model inference is performed by this export'])
    save(output/'manifest.json', manifest)
    save(output/'validation.json', dict(frames=197, images_hashed=197, labels_hashed=197,
         yolo_geometry_verified=True, split_validation=manifest['split_validation'],
         manifest_sha256=sha(output/'manifest.json'), original_inputs_preserved=True))
    return dict(manifest=str(output/'manifest.json'), manifest_sha256=sha(output/'manifest.json'),
                frame_counts=counts, box_counts=boxes)


def integrate_repairs(drafts, approval):
    """Apply ONLY the approved replacement, leaving retained proposals unconfirmed."""
    expected = {('R01', 60), ('R02', 71), ('R02', 72), ('R02', 73), ('R02', 75)}
    approved = {f['frame_id']: f for f in approval['frames']}
    if len(approved) != 5 or len(approval['frames']) != 5:
        raise ValueError('Exactly five explicit replacement approvals required')
    rows, applied, removed = [], set(), []
    for draft in drafts:
        rid = draft['review_id']
        for old in draft['frames']:
            frame = deepcopy(old)
            index = frame['decoded_index']
            fid = f'exp0073-{rid.lower()}-frame-{index:06d}'
            frame.update(frame_id=fid, review_id=rid, source_id=draft['source_id'],
                         source_sha256=draft['source_sha256'], split=draft['reserved_split'],
                         capture_reservation=draft['capture_reservation'], source_size=[1920, 1080],
                         person_completeness_verified=False, standard_train_eligible=False,
                         full_frame_metrics_eligible=False, training_release=False)
            for box in frame['boxes']:
                box['coordinate_confirmed'] = False
                box['origin'] = 'model_proposal_retained_unconfirmed'
            for change in old['changes']:
                if change['kind'] == 'remove_user_identified_background_proposals':
                    removed.extend(dict(frame_id=fid, **b) for b in change['removed'])
            if fid in approved:
                a = approved[fid]
                if ((rid, index) not in expected or a['source_sha256'] != draft['source_sha256']
                        or a['source_pts'] != frame['source_pts']
                        or a['source_rgb_sha256'] != frame['source_rgb_sha256']
                        or not a['coordinate_confirmed'] or a['whole_frame_completeness_confirmed']
                        or len(a['approved_boxes']) != 1):
                    raise ValueError('Approval frame binding/scope differs')
                old_repair_id = f'{rid}-{index}-repair'
                positions = [i for i, b in enumerate(frame['boxes']) if b['id'] == old_repair_id]
                if len(positions) != 1:
                    raise ValueError('Replacement target is not unique')
                new_box = deepcopy(a['approved_boxes'][0])
                box_valid(new_box['xyxy'], frame['source_size'])
                new_box.update(coordinate_confirmed=True, origin='explicit_user_approved_replacement',
                               replaces_repair_id=old_repair_id, approval_manifest=str(APPROVAL))
                frame['boxes'][positions[0]] = new_box
                applied.add((rid, index))
            frame['confirmed_person_boxes'] = [deepcopy(b) for b in frame['boxes'] if b['coordinate_confirmed']]
            frame['coordinate_confirmation_required'] = False
            frame['historical_changes'] = frame.pop('changes')
            frame['disposition'] = 'excluded_whole_frame_uncertain' if frame['whole_frame_hold'] else 'held_incomplete'
            frame['label_role'] = 'incomplete_proposals_and_approved_replacements_not_full_frame_GT'
            for box in frame['boxes']:
                box_valid(box['xyxy'], frame['source_size'])
            rows.append(frame)
    excluded = [f for f in rows if f['whole_frame_hold']]
    if (applied != expected or len(rows) != 72 or len(removed) != 17
            or len(excluded) != 1 or excluded[0]['review_id'] != 'R02'
            or excluded[0]['decoded_index'] != 70):
        raise ValueError('Repair/removal/exclusion scope changed')
    return rows, removed


def overlap_candidates(frames):
    """Geometry-only review triage. This never deletes, merges, or confirms boxes."""
    found = []
    for f in frames:
        if f['whole_frame_hold']:
            continue
        pairs = []
        for i, a in enumerate(f['boxes']):
            for b in f['boxes'][i+1:]:
                x, y = a['xyxy'], b['xyxy']
                inter = max(0, min(x[2], y[2])-max(x[0], y[0])) * max(0, min(x[3], y[3])-max(x[1], y[1]))
                area_x = (x[2]-x[0])*(x[3]-x[1])
                area_y = (y[2]-y[0])*(y[3]-y[1])
                iou = inter / (area_x+area_y-inter)
                containment = inter / min(area_x, area_y)
                if iou >= .5 or containment >= .9:
                    pairs.append(dict(box_ids=[a['id'], b['id']], iou=iou, containment=containment))
        if pairs:
            found.append(dict(frame_id=f['frame_id'], review_id=f['review_id'],
                              frame_index=f['decoded_index'], source_pts=f['source_pts'], pairs=pairs))
    return found


def corrections(output):
    import av
    from PIL import Image
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(output)
    if sha(APPROVAL) != '1c0f45ed1fb1e11e485d6202f585abdfc52d88c2b63de97f185ce9146b640e63':
        raise ValueError('Explicit five approval artifact changed')
    draft_paths = [REPAIR/f'{rid}-repaired-draft.json' for rid in ('R01', 'R02', 'R03')]
    drafts = [read(p) for p in draft_paths]
    approval = read(APPROVAL)
    night_path = ROOT/'runtime/model-comparison/exp0073/day-bottom-v2/night-four-box-approval.json'
    inputs = bindings([*draft_paths, APPROVAL, REPAIR/'editor-package.json', night_path,
                       READY/'split-proposal.json', READY/'group-closures.json', OLD, NEW])
    rows, removed = integrate_repairs(drafts, approval)
    web = current_web()
    live = {r['id']: r for r in web['requests']}
    day, night = live[approval['day_request_id']], live[read(night_path)['request_id']]
    if (day['answer_version'] != approval['day_answer_version'] or day['status'] != 'applied'
            or approval['day_revision_sha256'] not in day['note']
            or approval['day_preview_sha256'] not in day['note']
            or night['answer_version'] != approval['night_answer_version'] or night['status'] != 'applied'
            or night['source_binding_sha256'] != read(night_path)['source_binding_sha256']):
        raise ValueError('Current exact coordinate approval differs')
    plan, inventory, closures, groups = context()
    source_by_id = {c['source_id']: c for c in plan['cases']}
    protected, _ = protected_hashes()
    existing_images = {f['frame_id']: f for f in read(REPAIR/'editor-package.json')['frames']}
    output.mkdir(parents=True, exist_ok=False)
    (output/'images').mkdir()
    (output/'incomplete-yolo').mkdir()
    source_hashes = {}
    for draft in drafts:
        case = source_by_id[draft['source_id']]
        if (case['source_sha256'] != draft['source_sha256'] or draft['source_sha256'] in protected
                or case['capture_reservation'] != draft['capture_reservation']
                or case['reserved_split'] != draft['reserved_split']):
            raise ValueError('Correction source protection/reservation mismatch')
        ref = case['source_reference']
        if 'path' in ref:
            raw = Path(ref['path']).read_bytes()
        else:
            with zipfile.ZipFile(ref['archive_path']) as archive:
                raw = archive.read(ref['member'])
        raw_sha = hashlib.sha256(raw).hexdigest()
        if raw_sha != draft['source_sha256']:
            raise ValueError('Original source bytes changed')
        source_hashes[draft['source_id']] = dict(sha256=raw_sha, bytes=len(raw), reference=ref)
        wanted = {f['decoded_index']: f for f in rows if f['review_id'] == draft['review_id']}
        found = set()
        with av.open(io.BytesIO(raw)) as source:
            stream = source.streams.video[0]
            stream.codec_context.thread_count = 1
            source.seek(int(min(wanted)/3/float(stream.time_base)), stream=stream, backward=True)
            for decoded in source.decode(stream):
                pts = float(decoded.pts * decoded.time_base)
                index = round(pts * 3)
                if index > max(wanted):
                    break
                if index not in wanted:
                    continue
                f = wanted[index]
                rgb = decoded.to_ndarray(format='rgb24')
                if (abs(pts-f['source_pts']) > 1e-8
                        or hashlib.sha256(rgb.tobytes()).hexdigest() != f['source_rgb_sha256']):
                    raise ValueError('Original PTS/RGB frame changed')
                f['frame_index'] = index
                f['native_pts_tick'] = decoded.pts
                f['event_group'] = case['original_group_id']
                image = output/'images'/(f['frame_id']+'.png')
                if f['frame_id'] in existing_images:
                    old = existing_images[f['frame_id']]
                    if sha(old['image_path']) != old['image_sha256']:
                        raise ValueError('Previous approval image changed')
                    data = Path(old['image_path']).read_bytes()
                else:
                    buffer = io.BytesIO()
                    Image.fromarray(rgb).save(buffer, format='PNG')
                    data = buffer.getvalue()
                with image.open('xb') as target:
                    target.write(data)
                f['image'], f['image_sha256'] = str(image), sha(image)
                f['label'] = f['label_sha256'] = None
                if not f['whole_frame_hold']:
                    label = output/'incomplete-yolo'/(f['frame_id']+'.txt')
                    lines = []
                    for b in f['boxes']:
                        x1, y1, x2, y2 = b['xyxy']
                        lines.append(f'0 {(x1+x2)/3840:.10f} {(y1+y2)/2160:.10f} {(x2-x1)/1920:.10f} {(y2-y1)/1080:.10f}')
                    with label.open('x') as target:
                        target.write('\n'.join(lines)+ ('\n' if lines else ''))
                    f['label'], f['label_sha256'] = str(label), sha(label)
                    # Verify all draft coordinates too; this check is geometric,
                    # never a claim that unconfirmed proposals are person GT.
                    validate_frame(dict(f, confirmed_person_boxes=f['boxes']))
                found.add(index)
        if found != set(wanted):
            raise ValueError('Missing decoded source frame')
    candidates = overlap_candidates(rows)
    p01_subset = [f for f in rows if f['review_id'] == 'R03' and f['frame_index'] in (168, 175, 185)]
    triage = dict(method='Geometry only: IoU >=0.5 or smaller-box containment >=0.9; no new GT',
                  frames=candidates, frame_counts=dict(Counter(f['review_id'] for f in candidates)),
                  coordinator_selected_P01_subset=[dict(frame_id=f['frame_id'], frame_index=f['frame_index'],
                      source_pts=f['source_pts'], image=f['image'], person_completeness_verified=False) for f in p01_subset],
                  P01_unresolved_scope='Remaining boxes including tiny distant x535-587 y130-178 and overlapping actor boxes; full-frame completeness. Removed x720-760 y35-90 background stays removed. Wall-over action never rejects person labels.',
                  review_subset_is_not_full24_completion=True)
    save(output/'structural-duplication-candidates.json', triage)
    save(output/'background-removals.json', dict(removed=removed, count=17, scope='Exact previously identified proposals only'))
    save(output/'web-answers-read-only.json', web)
    with (output/'exporter-source.py').open('xb') as target:
        target.write(Path(__file__).read_bytes())
    preserved(inputs)
    current = current_web()
    for rid in (day['id'], night['id']):
        latest = {r['id']: r for r in current['requests']}[rid]
        if latest != live[rid]:
            raise ValueError('Approval changed during correction export')
    manifest = dict(schema_version=1, experiment_id='EXP-0074', purpose='incomplete_person_label_corrections',
        training_release=False, standard_train_eligible=False, full_frame_metrics_eligible=False,
        person_completeness_verified=False, protected_school_or_test_used=False,
        frames=rows, corrected_held_frames=71, excluded_whole_frames=1,
        corrected_draft_boxes_including_excluded=sum(len(f['boxes']) for f in rows),
        held_incomplete_yolo_boxes=sum(len(f['boxes']) for f in rows if not f['whole_frame_hold']),
        approved_replacement_boxes=5, background_proposals_removed=17,
        unconfirmed_retained_boxes=sum(not b['coordinate_confirmed'] for f in rows for b in f['boxes']),
        source_hashes=source_hashes, input_sha256=inputs, exporter_sha256=sha(__file__),
        complete_new_ground_truth_frames=0,
        direct_chat_scope='User observations were supplied directly; this does not explicitly approve all other boxes',
        derived_files={p.name: sha(p) for p in output.iterdir() if p.is_file()},
        limitations=['YOLO files include retained unconfirmed proposals and are incomplete; do not train or compute standard full-frame metrics',
                     'Night index70/PTS23.333 entire frame excluded; no YOLO label emitted',
                     'Five replacement coordinates are approved; no repeated coordinate confirmation needed',
                     'P01 eligibility depends only on remaining boxes and completeness, never whole-video action'])
    save(output/'manifest.json', manifest)
    save(output/'validation.json', dict(manifest_sha256=sha(output/'manifest.json'), images_hashed=72,
        labels_hashed=71, source_videos_hashed=3, native_pts_and_rgb_verified=72,
        old_approval_images_exact_bytes=5, new_complete_GT_frames=0, original_inputs_preserved=True))
    return dict(manifest=str(output/'manifest.json'), manifest_sha256=sha(output/'manifest.json'),
                corrected_held_frames=71, excluded_whole_frames=1, new_complete_GT_frames=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['freeze', 'corrections'])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps((freeze if args.command == 'freeze' else corrections)(args.output), ensure_ascii=False))


if __name__ == '__main__':
    main()
