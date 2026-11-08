"""Inventory and propose person-data review candidates; never trains or releases labels.

Reuses EXP63/65 event closures and records current on-disk availability, rather
than treating a historical inventory or actor annotations as complete people GT.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / 'outputs/action-recognition/exp0063'
AUG = ROOT / 'outputs/action-recognition/exp0065/augmentation-v1'


def read(p):
    return json.loads(Path(p).read_text())


def rows(p):
    return [json.loads(s) for s in Path(p).read_text().splitlines()]


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def save(p, x):
    with Path(p).open('x') as f:
        json.dump(x, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def save_rows(p, xs):
    with Path(p).open('x') as f:
        for x in xs:
            f.write(json.dumps(x, ensure_ascii=False, allow_nan=False) + '\n')


def inventory(out):
    out.mkdir(parents=True, exist_ok=False)
    inputs = [AUG / 'split-manifest.json', AUG / 'verified-candidates.jsonl',
              OLD / 'combined-split-v3/split-manifest.json',
              OLD / 'baseline/attempt-002/baseline-lock.json',
              OLD / 'data-audit/manifest.jsonl', OLD / 'normal-audit-v1/manifest.jsonl',
              ROOT / 'outputs/model-comparison/exp0067/confirmed-person-v1/manifest.json',
              ROOT / 'runtime/model-comparison/exp0067/review-application-v1/resolved-answers.json']
    bindings = {str(p.relative_to(ROOT)): sha(p) for p in inputs}
    assert bindings[str(inputs[2].relative_to(ROOT))] == 'bfb0f9fcd570794036cc6d2eaad46f988679b612996e21282a34821203ad5499'
    assert bindings[str(inputs[3].relative_to(ROOT))] == '3799ae3eee427b60e698b21f6ee958ac5306eacba07b5d85e4c35dbfa6457b40'
    split = read(inputs[0]); prior = rows(inputs[4]) + rows(inputs[5])
    by_old = {r['source_id']: r for r in prior}
    verified = rows(inputs[1])
    held_groups = {r['group_id'] for r in verified if r['status'] != 'bounded_duplicate_checks_passed_semantic_review_pending'}
    ver_by_id = {r['source_id']: r for r in verified}
    archives = {}; archive_errors = {}
    for r in split['assignments']:
        for kind in ('source_reference', 'label_reference'):
            path = r[kind]['archive_path']
            if path not in archives:
                try:
                    archives[path] = zipfile.ZipFile(path)
                except (OSError, zipfile.BadZipFile) as e:
                    archives[path] = None; archive_errors[path] = str(e)
    output = []
    mapping = {'retained_train': 'train', 'augmentation_train': 'train',
               'retained_validation': 'development', 'augmentation_validation': 'development',
               'new_evaluation_reserved_place': 'new_test', 'new_evaluation_same_place': 'new_test',
               'new_evaluation_exposed_test_place': 'new_test_exposed_place'}
    for i, r in enumerate(split['assignments']):
        x = dict(r)
        old = [by_old[k] for k in r['existing_original_ids'] if k in by_old]
        resolved = {}
        for kind, field in [('source_reference', 'source_path'), ('label_reference', 'label_path')]:
            local = sorted({o[field] for o in old if Path(o[field]).is_file()})
            ref = r[kind]; z = archives[ref['archive_path']]
            if local:
                resolved[kind] = {'path': local[0], 'availability': 'local_file'}
            elif z is not None and ref['member'] in z.NameToInfo:
                zi = z.getinfo(ref['member'])
                if kind == 'source_reference' and (zi.file_size != ref['bytes'] or zi.CRC != ref['crc32']):
                    resolved[kind] = {'availability': 'archive_member_metadata_changed'}
                else:
                    resolved[kind] = {**ref, 'availability': 'archive_member'}
            else:
                resolved[kind] = {**ref, 'availability': 'missing'}
        x['resolved'] = resolved
        x['available_pair'] = all(v['availability'] in ('local_file', 'archive_member') for v in resolved.values())
        x['proposal_split'] = mapping.get(r['proposed_partition'], 'hold')
        x['prior_content_hold'] = r['group_id'] in held_groups
        if x['prior_content_hold']:
            x['proposal_split'] = 'hold'
        x['source_sha256'] = next((o['source_sha256'] for o in old), ver_by_id.get(r['source_id'], {}).get('source_sha256'))
        x['complete_person_labels'] = False
        x['training_eligible'] = False
        x['label_geometry'] = None
        if x['available_pair']:
            ref = resolved['label_reference']
            raw = Path(ref['path']).read_bytes() if 'path' in ref else archives[ref['archive_path']].read(ref['member'])
            actual_hash = hashlib.sha256(raw).hexdigest()
            x['label_hash_matches_inventory'] = actual_hash == r['label_sha256']
            if not x['label_hash_matches_inventory']:
                x['proposal_split'] = 'hold'
            data = json.loads(raw)
            annotations = data.get('annotations', [])
            heights = []; perclass = defaultdict(list); annotated_frames = set()
            for a in annotations:
                try:
                    (x1, y1), (x2, y2) = a['bbox']
                    h = float(y2) - float(y1)
                    if h <= 0 or float(x2) <= float(x1):
                        continue
                    h640 = h * min(640 / r['width'], 640 / r['height'])
                    heights.append(h640)
                    perclass[a.get('class_name')].append((h640, int(a['cur_frame']), a.get('actor_id')))
                    annotated_frames.add(int(a['cur_frame']))
                except (ValueError, TypeError, KeyError):
                    pass
            heights.sort()
            x['label_geometry'] = dict(annotation_rows=len(annotations),
                annotation_frame_count=len(annotated_frames),
                h640_p10=heights[int(.1 * (len(heights)-1))] if heights else None,
                h640_median=heights[len(heights)//2] if heights else None,
                h640_under32=sum(h < 32 for h in heights), h640_under64=sum(h < 64 for h in heights),
                class_smallest={k: {'height640': min(v)[0], 'declared_frame': min(v)[1], 'actor_id': min(v)[2]}
                                for k, v in perclass.items()},
                early_annotation_free_frames=[f for f in range(1, min(25, r['declared_frames'])+1) if f not in annotated_frames],
                empty_frames_are_not_background_truth=True,
                explicit_occlusion_annotation=any('occl' in k.lower() for a in annotations for k in a))
        output.append(x)
        if (i+1) % 1000 == 0:
            print(json.dumps({'inspected_inventory_rows': i+1}), flush=True)
    for z in archives.values():
        if z:
            z.close()
    save_rows(out / 'source-inventory.jsonl', output)
    save(out / 'input-bindings.json', bindings)
    save(out / 'group-closures.json', split['groups'])
    save(out / 'inventory-summary.json', dict(total_historical_sources=len(output),
        current_available_pairs=sum(r['available_pair'] for r in output),
        by_partition=dict(Counter(r['proposal_split'] for r in output if r['available_pair'])),
        unavailable_archives=archive_errors, old_test_originals=296, protected_test_closure_members=327,
        protected_school_videos=45, prior_content_hold_groups=sorted(held_groups),
        old_split_hash_preserved=sha(inputs[2]) == bindings[str(inputs[2].relative_to(ROOT))],
        complete_person_label_note='Reuse EXP67 only for its exact 75 reviewed frames; never whole sources.',
        gpu_inference=0, training=0))


def plan(out):
    data = rows(out / 'source-inventory.jsonl')
    eligible = [r for r in data if r['available_pair'] and r['proposal_split'] != 'hold'
                and not r['errors'] and r.get('label_hash_matches_inventory')]
    selected = {}; used_groups = set()

    def add(r, reason, action=None):
        sid = r['source_id']
        if sid not in selected:
            selected[sid] = dict(r, selection_reasons=[], target_actions=[])
        selected[sid]['selection_reasons'].append(reason)
        if action and action not in selected[sid]['target_actions']:
            selected[sid]['target_actions'].append(action)
        used_groups.add(r['group_id'])

    # Preserve the two already confirmed training snippets; no original changes.
    for token in ['C_4_4_smp_cl_09-06_14-40-00_a_', 'C_33_2_smp_su_09-11_13-36-00_b_']:
        r = next(r for r in eligible if token in r['original_filename'])
        action = 'wall_over' if 'C_4_' in token else 'stand'
        add(r, 'reuse_exact_EXP0067_reviewed_training_window_only', action)

    # One representative per distinct closure for explicit moving / standing.
    for action in ('moving', 'stand'):
        pool = [r for r in eligible if r['proposal_split'] == 'train'
                and any(e['class_name'] == action for e in r['events'])]
        groups = sorted({r['group_id'] for r in pool})
        for group in groups:
            candidates = [r for r in pool if r['group_id'] == group]
            existing = [r for r in candidates if r['source_id'] in selected]
            r = min(existing or candidates, key=lambda r: (r['label_geometry']['h640_p10'], r['source_id']))
            add(r, 'explicit_'+action+'_different_capture_closure', action)

    # Wall poses: different closures, places, and small/larger annotation scales.
    for part in ('train', 'development'):
        pool = [r for r in eligible if r['proposal_split'] == part
                and any(e['class_name'] == 'wall_over' for e in r['events'])]
        for place in sorted({r['location'] for r in pool}):
            pp = [r for r in pool if r['location'] == place and r['group_id'] not in used_groups]
            if not pp:
                continue
            small = min(pp, key=lambda r: (r['label_geometry']['h640_p10'], r['source_id']))
            add(small, 'wall_pose_and_smaller_annotation_scale', 'wall_over')
            pp = [r for r in pp if r['group_id'] not in used_groups]
            if pp and part == 'train':
                large = max(pp, key=lambda r: (r['label_geometry']['h640_p10'], r['source_id']))
                add(large, 'wall_pose_larger_person_different_capture_closure', 'wall_over')

    # Normal activity can be in the prelude of any actor-labelled video. These
    # are review requests, never automatically assigned normal/background labels.
    for part in ('train', 'development'):
        for place in sorted({r['location'] for r in eligible if r['proposal_split'] == part}):
            pp = [r for r in eligible if r['proposal_split'] == part and r['location'] == place
                  and r['group_id'] not in used_groups
                  and r['scenario_family'] != 4]
            if not pp:
                continue
            r = min(pp, key=lambda r: (r['label_geometry']['h640_p10'] or 999, r['source_id']))
            add(r, 'new_background_and_small_person_context_review')

    # Genuine new-place testing only: old known places do not become a fresh
    # school generalisation test by selecting another file.
    reserved = [r for r in eligible if r['proposed_partition'] == 'new_evaluation_reserved_place']
    for place in sorted({r['location'] for r in reserved}):
        pp = [r for r in reserved if r['location'] == place]
        small = min(pp, key=lambda r: (r['label_geometry']['h640_p10'] or 999, r['source_id']))
        add(small, 'reserved_new_place_smallest_annotation_scale')
        pp = [r for r in pp if r['group_id'] not in used_groups]
        if pp:
            large = max(pp, key=lambda r: (r['label_geometry']['h640_p10'] or 0, r['source_id']))
            add(large, 'reserved_new_place_scale_and_capture_contrast')

    cases = []
    for index, r in enumerate(sorted(selected.values(), key=lambda r: (r['proposal_split'], r['location'], r['source_id'])), 1):
        r['candidate_id'] = f'P{index:02d}'
        acts = r['target_actions']
        events = [e for e in r['events'] if e['class_name'] in acts] or r['events']
        event = min(events, key=lambda e: (e['start_frame_declared'], e['event_index']))
        center = (event['start_frame_declared'] + event['end_frame_declared']) / 2 / r['fps']
        if r['label_geometry']['h640_under64']:
            geom = r['label_geometry']['class_smallest']
            available_actions = [a for a in acts if a in geom] or list(geom)
            if available_actions:
                g = min((geom[a] for a in available_actions), key=lambda g: g['height640'])
                center = g['declared_frame'] / r['fps']
        r['review_windows'] = [dict(kind='actor_and_context', start_seconds=round(max(0, center-4), 3),
                                   end_seconds=round(min(r['declared_frames']/r['fps'], center+4), 3)),
                               dict(kind='prelude_unknown_people_and_motion', start_seconds=0., end_seconds=8.)]
        r['person_label_status'] = 'actor_only_full_person_completeness_unverified'
        r['required_review'] = ['actual source PTS and annotation frame origin',
            'all visible people, including bystanders, followers and small distant people',
            'boxes for every chosen native frame; ignore truly unobservable extent',
            'normal walking/waiting versus other activity; do not infer from folder name',
            'prelude has no people only if full interval is actually reviewed',
            'same capture / multicamera / re-encoding check at group level']
        cases.append(r)
    assignments = {r['group_id']: r['proposal_split'] for r in cases}
    assert all(assignments[r['group_id']] == r['proposal_split'] for r in cases)
    # Record all members of each selected closure, even unavailable/unselected views.
    closure = [dict(source_id=r['source_id'], group_id=r['group_id'],
                    proposed_split=assignments[r['group_id']], source_sha256=r['source_sha256'],
                    existing_original_ids=r['existing_original_ids'], available_pair=r['available_pair'],
                    old_partition=r['proposed_partition'])
               for r in data if r['group_id'] in assignments]
    save(out / 'candidate-plan-before-decode.json', dict(status='proposal_not_training_release',
        selection_basis='metadata_labels_geometry_coverage_no_model_predictions',
        independent_event_count_certified=None, group_count=len(assignments),
        cases=cases, closure_members=closure))
    print(json.dumps(dict(candidates=len(cases),groups=len(assignments),
        splits=dict(Counter(r['proposal_split'] for r in cases)))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('stage', choices=['inventory', 'plan'])
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(); globals()[args.stage](args.output)
