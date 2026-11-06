"""EXP-0065 read-only local label inventory and protected augmentation proposal.

No model/torch/GPU, training labels, downloads or existing split changes. ZIP
references are archive+member pairs, never silently extracted by basename.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PARK = Path('/mnt/e/AI_HUB/173.공원 주요시설 및 불법행위 감시 CCTV 영상 데이터/01.데이터')
OLD = ROOT / 'outputs/action-recognition/exp0063'
OUTPUT = ROOT / 'outputs/action-recognition/exp0065/augmentation-v1'
NORMAL = {'moving', 'stand', 'sit_down_bench', 'sit_down_floor'}
TARGET = NORMAL | {'wall_over'}


def checked_output(path, owned_root=OUTPUT.parent):
    supplied = Path(path).absolute()
    if (supplied.is_symlink() or '..' in supplied.parts
            or supplied.parent.resolve() != Path(owned_root).resolve()
            or not re.fullmatch(r'augmentation-[A-Za-z0-9][A-Za-z0-9._-]*', supplied.name)):
        raise ValueError('Use a nonsymlink augmentation revision directly under the EXP0065 owned root')
    return supplied


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(4 * 1024 * 1024), b''): h.update(b)
    return h.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False); f.write('\n')


def jsonl(path, rows):
    with Path(path).open('x') as f:
        for r in rows: f.write(json.dumps(r, ensure_ascii=False, allow_nan=False) + '\n')


def csv_rows(path, rows, fields):
    import csv
    with Path(path).open('x', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore'); w.writeheader()
        for r in rows: w.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in r.items()})


def family_scenario(name):
    m = re.match(r'^C_(\d+)_(\d+)_', Path(name).name)
    return (int(m[1]), int(m[2])) if m else (None, None)


def excluded(family, scenario):
    return family == 4 and scenario is not None and (19 <= scenario <= 35 or 69 <= scenario <= 70)


def intervals(data):
    """Explicit actor/event classes only; missing annotations stay unknown."""
    from audit_action_dataset import audit_label
    result = audit_label(data, data.get('info', {}).get('filename', ''))
    rows = []
    for event in result['events']:
        r = {k: event[k] for k in ('event_index', 'actor_id', 'object_id', 'class_name',
             'annotation_classes', 'start_frame_declared', 'end_frame_declared',
             'start_time_declared', 'end_time_declared', 'matching_box_count')}
        r['missing_box_frame_count'] = len(event['missing_box_frames'])
        r['both_origin_interior_eight_frames_possible'] = (
            r['end_frame_declared'] - r['start_frame_declared'] >= 8)
        r['basis'] = 'official_explicit_actor_event_not_human_semantic_truth'
        r['training_eligible'] = False
        rows.append(r)
    return rows, sorted({e['code'] for e in result['errors']}), sorted({e['code'] for e in result['warnings']})


def archive_index(path, suffix):
    with zipfile.ZipFile(path) as z:
        members = [dict(member=x.filename, bytes=x.file_size, crc32=x.CRC,
                        compressed_bytes=x.compress_size) for x in z.infolist()
                   if not x.is_dir() and x.filename.lower().endswith(suffix)]
    by_name = defaultdict(list)
    for m in members: by_name[Path(m['member']).name].append(m)
    return members, by_name


def inventory(base, output):
    output.mkdir(parents=True, exist_ok=False)
    rows, archives = [], []
    for labels in sorted(base.glob('*/라벨링데이터/*.zip')):
        action = '행위' in labels.name
        source_name = labels.name.replace('TL_', 'TS_', 1).replace('VL_', 'VS_', 1)
        source = labels.parent.parent / '원천데이터' / source_name
        # Validation combines illegal and normal under one matching archive.
        label_members, _ = archive_index(labels, '.json')
        sm, source_by_name = archive_index(source, '.mp4') if source.is_file() and action else ([], {})
        astat = labels.stat(); sstat = source.stat() if source.exists() else None
        archives.append(dict(label_archive=str(labels), label_archive_sha256=sha(labels),
            source_archive=str(source), source_archive_bytes=sstat.st_size if sstat else None,
            source_archive_mtime_ns=sstat.st_mtime_ns if sstat else None,
            source_archive_full_sha256=None, source_member_directory_sha256=digest(sm),
            label_members=len(label_members), source_video_members=len(sm),
            scope='temporal_action' if action else 'object_stills_no_temporal_action_labels'))
        if not action: continue
        with zipfile.ZipFile(labels) as z:
            for index, member in enumerate(label_members):
                raw = z.read(member['member']); data = json.loads(raw); info = data.get('info', {})
                filename = info.get('filename', Path(member['member']).with_suffix('.mp4').name)
                pairs = source_by_name.get(filename, [])
                family, scenario = family_scenario(filename)
                events, errors, warnings = intervals(data)
                if len(pairs) != 1: errors.append('source_pair_missing_or_ambiguous')
                camera = re.search(r'_(DF\d+)\.', filename)
                rid = labels.parent.parent.name + ':' + filename
                rows.append(dict(source_id=rid, original_filename=filename,
                    supplied_partition=labels.parent.parent.name,
                    source_reference=dict(archive_path=str(source), **pairs[0]) if len(pairs) == 1 else None,
                    source_sha256=None, label_reference=dict(archive_path=str(labels), member=member['member']),
                    label_sha256=hashlib.sha256(raw).hexdigest(), label_bytes=len(raw),
                    location=info.get('location'), date_captured=info.get('date_captured'),
                    declared_frames=info.get('frame'), fps=info.get('fps'),
                    width=info.get('width'), height=info.get('height'),
                    scenario_family=family, scenario_number=scenario,
                    camera_code_from_filename=camera[1] if camera else None,
                    camera_metadata_verified=False, excluded=excluded(family, scenario),
                    events=events, errors=sorted(set(errors)), warnings=warnings,
                    semantic_ground_truth_verified=False, training_eligible=False))
                if (index + 1) % 300 == 0: print(json.dumps(dict(archive=labels.name, labels_read=index + 1)), flush=True)
        if labels.stat().st_size != astat.st_size or labels.stat().st_mtime_ns != astat.st_mtime_ns:
            raise ValueError('Label archive changed during inventory')
        if sstat and (source.stat().st_size, source.stat().st_mtime_ns) != (sstat.st_size, sstat.st_mtime_ns):
            raise ValueError('Source archive changed during inventory')
    if len({r['source_id'] for r in rows}) != len(rows): raise ValueError('Duplicate inventory identity')
    jsonl(output / 'inventory.jsonl', rows); save(output / 'archives.json', archives)
    csv_rows(output / 'inventory.csv', rows, ['source_id', 'location', 'date_captured', 'scenario_family',
        'scenario_number', 'camera_code_from_filename', 'excluded', 'label_sha256', 'source_reference', 'errors', 'events'])
    save(output / 'inventory-summary.json', dict(sources=len(rows), action_events=dict(Counter(
        e['class_name'] for r in rows for e in r['events'])), locations=dict(Counter(r['location'] for r in rows)),
        archives=archives, script_sha256=sha(__file__), media_hashed=0, model_loads=0, training=0))


def grouped(rows, old_rows, assignments, protected45):
    """Conservative closure: exact SHA, same scenario/place, overlapping cameras.

    Existing test ORIGINALS, not just clips actually scored, seed protection.
    Unknown camera/time metadata can never establish an independent split.
    """
    nodes = [dict(r, node_id='new:' + r['source_id'], old_split=None) for r in rows]
    old_by_name = defaultdict(list)
    for r in old_rows:
        assignment = assignments[r['source_id']]; info = (r.get('label') or {}).get('info', {})
        family = r.get('scenario_family', 4); scenario = r.get('scenario')
        node = dict(node_id='old:' + r['source_id'], source_id=r['source_id'],
            original_filename=Path(r['source_path']).name, source_sha256=r['source_sha256'],
            location=info.get('location'), date_captured=info.get('date_captured'),
            declared_frames=info.get('frame'), fps=info.get('fps'),
            scenario_family=family, scenario_number=scenario, old_split=assignment['split'],
            original_group=assignment['group_id'], excluded=r['excluded'])
        nodes.append(node); old_by_name[node['original_filename']].append(node)
    heldout_places = {n['location'] for n in nodes if n.get('old_split') == 'test'} - {
        n['location'] for n in nodes if n.get('old_split') in {'train', 'validation'}}
    old_places = {n['location'] for n in nodes if n.get('old_split') is not None}
    novel_classes = defaultdict(set)
    for n in nodes:
        if n['node_id'].startswith('new:') and n.get('location') not in old_places and not n.get('excluded') and not n.get('errors'):
            novel_classes[n['location']].update(e['class_name'] for e in n.get('events', []))
    complete_eval_places = sorted(p for p, classes in novel_classes.items()
                                 if 'wall_over' in classes and classes & {'moving', 'stand'})
    # Reserve whole places for new evaluation, never split an evaluation place
    # into augmentation train/validation. Incomplete places stay reserved rather
    # than turning unrelated illegal-action labels into negative examples.
    reserved_places = set(complete_eval_places[:1]) | {
        p for p, classes in novel_classes.items() if not classes & {'moving', 'stand'}}
    parent = {n['node_id']: n['node_id'] for n in nodes}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    def join(x, y):
        a, b = find(x), find(y)
        if a != b: parent[max(a, b)] = min(a, b)
    by_key, captures = {}, defaultdict(list)
    for n in nodes:
        for typ, key in [('sha', n.get('source_sha256')), ('old_group', n.get('original_group')),
                         ('scenario', (n['location'], n['scenario_family'], n['scenario_number'])
                          if n.get('location') and n.get('scenario_family') is not None and n.get('scenario_number') is not None else None)]:
            if key:
                if (typ, key) in by_key: join(n['node_id'], by_key[(typ, key)])
                by_key[(typ, key)] = n['node_id']
        if n['node_id'].startswith('new:'):
            # Matching filename+place+capture identifies an already audited original;
            # content equality remains a reused old binding, not a fresh ZIP assertion.
            matches = [old for old in old_by_name[n['original_filename']]
                       if old['location'] == n['location'] and old['date_captured'] == n['date_captured']]
            if matches:
                n['existing_original_ids'] = sorted(o['source_id'] for o in matches)
                for old in matches: join(n['node_id'], old['node_id'])
        try:
            start = datetime.strptime(n['date_captured'], '%Y/%m/%d %H:%M:%S')
            duration = float(n['declared_frames']) / float(n['fps'])
            if not n['location'] or duration <= 0: raise ValueError('Invalid capture')
            captures[n['location']].append((start, start + timedelta(seconds=duration), n['node_id']))
        except (KeyError, TypeError, ValueError, ZeroDivisionError): n['capture_unresolved'] = True
    for times in captures.values():
        active = []
        for start, end, key in sorted(times):
            active = [(e, k) for e, k in active if e >= start]
            for _, other in active: join(key, other)
            active.append((end, key))
    components = defaultdict(list)
    for n in nodes: components[find(n['node_id'])].append(n)
    groups, out = [], []
    for members in components.values():
        keys = sorted(n['node_id'] for n in members); gid = 'aug-' + digest(keys)[:20]
        old_splits = {n['old_split'] for n in members if n['old_split'] is not None}
        places = sorted({n['location'] for n in members if n.get('location')})
        reasons = []
        if 'test' in old_splits: partition = 'protected_exp0064_test'; reasons.append('closure_contains_old_test_original_or_event_multicamera_group')
        elif any(n.get('source_sha256') in protected45 for n in members): partition = 'protected45'; reasons.append('protected45_hash')
        elif len(old_splits & {'train', 'validation'}) > 1: partition = 'quarantine'; reasons.append('closure_conflicts_existing_train_validation')
        elif any(n.get('capture_unresolved') for n in members) or len(places) != 1: partition = 'quarantine'; reasons.append('unresolved_capture_or_place')
        elif old_splits & {'train', 'validation'}: partition = 'retained_' + next(iter(old_splits & {'train', 'validation'}))
        elif old_splits & {'excluded', 'quarantine'}: partition = 'quarantine'; reasons.append('closure_contains_old_exclusion_or_error')
        elif places[0] in heldout_places:
            partition = 'new_evaluation_exposed_test_place'
            reasons.append('existing_heldout_place_remains_evaluation_only_but_prior_test_was_inspected')
        elif places[0] in reserved_places:
            partition = 'new_evaluation_reserved_place'
            if places[0] not in complete_eval_places:
                reasons.append('reserved_unseen_place_lacks_explicit_normal_and_wall_over_coverage')
        else:
            # Fixed metadata-only split before reading fingerprints or model outcomes.
            bucket = int(hashlib.sha256(('exp0065-seed6501:' + gid).encode()).hexdigest()[:8], 16) % 10
            partition = 'new_evaluation_same_place' if bucket < 2 else 'augmentation_validation' if bucket < 4 else 'augmentation_train'
        group = dict(group_id=gid, locations=places, partition=partition, reasons=reasons,
                     old_splits=sorted(old_splits), member_ids=keys)
        groups.append(group)
        for n in members:
            if not n['node_id'].startswith('new:'): continue
            original = next(r for r in rows if r['source_id'] == n['source_id'])
            out.append(dict(original, group_id=gid, proposed_partition='excluded_user_scenario' if original['excluded'] else 'quarantine' if original['errors'] else partition,
                            partition_reasons=reasons, existing_original_ids=n.get('existing_original_ids', [])))
    return sorted(out, key=lambda r: r['source_id']), sorted(groups, key=lambda g: g['group_id'])


def plan(output, maximum=96):
    rows = [json.loads(l) for l in (output / 'inventory.jsonl').open()]
    old_paths = [OLD / 'data-audit/manifest.jsonl', OLD / 'normal-audit-v1/manifest.jsonl']
    old = [json.loads(l) for p in old_paths for l in p.open()]
    split_path = OLD / 'combined-split-v3/split-manifest.json'; split = read(split_path)
    if sha(split_path) != 'bfb0f9fcd570794036cc6d2eaad46f988679b612996e21282a34821203ad5499': raise ValueError('Frozen split changed')
    assignments = {r['source_id']: r for r in split['assignments']}
    lock_path = OLD / 'baseline/attempt-002/baseline-lock.json'
    if sha(lock_path) != '3799ae3eee427b60e698b21f6ee958ac5306eacba07b5d85e4c35dbfa6457b40': raise ValueError('Baseline lock changed')
    lock = read(lock_path); protected = {r['sha256'] for r in lock['regression_only_videos']}
    rows, groups = grouped(rows, old, assignments, protected)
    # Existing originals retain partitions; propose new files only. Round robin
    # partition/place/action/group before CPU decoding, never by action score.
    pools = defaultdict(list)
    for r in rows:
        if r['existing_original_ids'] or r['proposed_partition'] in {'quarantine', 'protected_exp0064_test', 'protected45', 'excluded_user_scenario'}: continue
        actions = sorted({e['class_name'] for e in r['events'] if e['class_name'] in TARGET and e['both_origin_interior_eight_frames_possible']})
        for action in actions: pools[(r['proposed_partition'], r['location'], action, r['group_id'])].append(r)
    for pool in pools.values(): pool.sort(key=lambda r: digest(['exp0065-source6501', r['source_id']]))
    selected, seen = [], set()
    while len(selected) < maximum and pools:
        for key in sorted(list(pools)):
            pool = pools[key]
            while pool and pool[0]['source_id'] in seen: pool.pop(0)
            if pool and len(selected) < maximum:
                r = pool.pop(0); selected.append(r); seen.add(r['source_id'])
            if not pool: del pools[key]
    old_locations = sorted({r['location'] for r in split['assignments'] if r['split'] in {'train', 'validation'}})
    all_old_locations = sorted({r['location'] for r in split['assignments'] if r.get('location')})
    summary = dict(schema_version=1, status='metadata_proposal_frozen_before_decode_no_training',
        total_sources=len(rows), partitions=dict(Counter(r['proposed_partition'] for r in rows)),
        old_split_counts=dict(Counter(r['split'] for r in split['assignments'])),
        old_test_originals=sum(r['split'] == 'test' for r in split['assignments']),
        old_test_groups=len({r['group_id'] for r in split['assignments'] if r['split'] == 'test'}),
        protected45=len(protected), group_count=len(groups),
        existing_train_validation_locations=old_locations,
        all_previously_inspected_corpus_locations=all_old_locations,
        genuinely_unseen_place_locations=sorted({r['location'] for r in rows if r['location'] not in all_old_locations and r['proposed_partition'] not in {'protected_exp0064_test', 'excluded_user_scenario', 'quarantine'}}),
        independent_new_place_generalization_evaluation_ready=False,
        selected_new_sources=len(selected), selected_source_limit=maximum,
        counts_by_partition_place_action=dict(Counter('|'.join([r['proposed_partition'], str(r['location']), e['class_name']]) for r in rows for e in r['events'])),
        trained=False, candidate_training_eligible=False, validation_existing_assignments_changed=0,
        group_policy=['existing_full_original_groups', 'same_location_family_scenario_across_dates', 'inclusive_capture_overlap_all_camera_families', 'old_test_closure_excluded_from_any_new_train_validation'],
        evaluation_place_policy='Whole unseen place reserved before fingerprints: first complete normal+wall place if any; places without explicitmoving/stand also reserved but insufficient labels. Existing heldout place stays evaluation-only, prior test exposure disclosed.',
        hard_negative_semantics=dict(approach_return_verified=0, touch_without_cross_verified=0, moving_is_not_verified_approach_return=True),
        source_hash_policy='Existing audit hashes reused without raw-media rehash; new selected member SHA and bounded content fingerprints pending; ZIP CRC is not cryptographic source proof.',
        inputs={str(p): sha(p) for p in old_paths + [split_path, lock_path, output / 'inventory.jsonl', output / 'archives.json']}, script_sha256=sha(__file__))
    save(output / 'split-manifest.json', dict(summary=summary, groups=groups, assignments=rows))
    save(output / 'candidate-manifest.json', dict(schema_version=1, status='review_candidates_only_not_training_release',
         selection='fixed_round_robin_partition_location_explicit_action_group_before_decode', sources=selected,
         protected_exclusions=True, semantic_review_pending=True, model_results_used=False))
    save(output / 'summary.json', summary)
    csv_rows(output / 'split.csv', rows, ['source_id', 'location', 'date_captured', 'scenario_family', 'scenario_number',
        'group_id', 'proposed_partition', 'existing_original_ids', 'excluded', 'errors', 'label_sha256', 'source_reference'])
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def fingerprint_bytes(raw, targets=(.1, .3, .5, .7, .9)):
    """Bounded five-frame CPU content probe, not re-encoding equivalence proof."""
    import av
    import numpy as np
    source = io.BytesIO(raw) if isinstance(raw, bytes) else str(raw)
    frames = []
    with av.open(source) as c:
        s = c.streams.video[0]
        if not s.duration: raise ValueError('Missing stream duration')
        duration = float(s.duration * s.time_base)
        for fraction in targets:
            target = duration * fraction
            c.seek(int(target / float(s.time_base)), stream=s, backward=True)
            frame = next((f for f in c.decode(s) if float(f.pts * f.time_base) >= target), None)
            if frame is None: raise ValueError('Fingerprint target unavailable')
            # Tiny grayscale content fingerprint; no raw frame is persisted.
            gray = frame.reformat(width=32, height=18, format='gray').to_ndarray()
            small = frame.reformat(width=8, height=8, format='gray').to_ndarray()
            bits = small >= np.median(small)
            ahash = ''.join('1' if x else '0' for x in bits.ravel())
            frames.append(dict(relative_target=fraction, actual_pts=float(frame.pts * frame.time_base),
                normalized_gray_sha256=hashlib.sha256(gray.tobytes()).hexdigest(), ahash=f'{int(ahash, 2):016x}'))
    return frames


def suspicious_content(a, b):
    exact = sum(x['normalized_gray_sha256'] == y['normalized_gray_sha256'] for x, y in zip(a, b))
    near = sum((int(x['ahash'], 16) ^ int(y['ahash'], 16)).bit_count() <= 2 for x, y in zip(a, b))
    return exact >= 3 or near >= 4


def quarantine_results(result, candidates, protected_complete):
    frozen = {r['source_id']: r for r in candidates}
    unsafe_ids = {r['source_id'] for r in result if r['status'] != 'bounded_duplicate_checks_passed_semantic_review_pending'}
    unsafe_ids.update(x for r in result for x in r.get('suspected_content_overlap', []))
    unsafe_groups = {frozen[sid]['group_id'] for sid in unsafe_ids if sid in frozen}
    for r in result:
        r['group_id'] = frozen[r['source_id']]['group_id']
        r['proposed_partition'] = frozen[r['source_id']]['proposed_partition']
        if r['group_id'] in unsafe_groups or r['source_id'] in unsafe_ids:
            r['status'] = 'quarantine_suspected_overlap_or_group'
        elif not protected_complete:
            r['status'] = 'quarantine_incomplete_protected_fingerprint_coverage'
    return result


def fingerprints(output):
    candidate = read(output / 'candidate-manifest.json'); split = read(OLD / 'combined-split-v3/split-manifest.json')
    old = [json.loads(l) for p in [OLD / 'data-audit/manifest.jsonl', OLD / 'normal-audit-v1/manifest.jsonl'] for l in p.open()]
    by_id = {r['source_id']: r for r in old}; baseline = read(OLD / 'baseline/attempt-002/baseline-lock.json')
    protected = [(r['source_id'], by_id[r['source_id']]['source_path'], r['source_sha256']) for r in split['assignments'] if r['split'] == 'test']
    protected += [('regression:' + r['video_id'], r['path'], r['sha256']) for r in baseline['regression_only_videos']]
    path = output / 'protected-content-fingerprints.jsonl'
    if path.exists(): raise ValueError('Fresh fingerprint output required')
    oldprints = []
    with path.open('x') as f:
        for i, (sid, source, h) in enumerate(protected):
            try: row = dict(source_id=sid, source_path=source, recorded_source_sha256=h, fingerprints=fingerprint_bytes(Path(source)))
            except Exception as e: row = dict(source_id=sid, source_path=source, error=type(e).__name__ + ':' + str(e))
            oldprints.append(row); f.write(json.dumps(row) + '\n'); f.flush()
            if (i + 1) % 25 == 0: print(json.dumps(dict(protected_fingerprints=i + 1)), flush=True)
    old_hashes = {r['source_sha256'] for r in old} | {r['sha256'] for r in baseline['regression_only_videos']}
    result = []; newprints = []
    for i, r in enumerate(candidate['sources']):
        ref = r['source_reference']
        try:
            if ref['bytes'] > 512 * 1024 * 1024: raise ValueError('Member exceeds512MiB bounded-memory cap')
            with zipfile.ZipFile(r['label_reference']['archive_path']) as z:
                if hashlib.sha256(z.read(r['label_reference']['member'])).hexdigest() != r['label_sha256']:
                    raise ValueError('Selected label changed after split freeze')
            with zipfile.ZipFile(ref['archive_path']) as z:
                current = z.getinfo(ref['member'])
                if (current.file_size, current.CRC) != (ref['bytes'], ref['crc32']):
                    raise ValueError('Selected source archive member changed after split freeze')
                raw = z.read(ref['member'])
            if len(raw) != ref['bytes']: raise ValueError('Source member length changed')
            h = hashlib.sha256(raw).hexdigest(); fp = fingerprint_bytes(raw); del raw
            collisions = [p['source_id'] for p in oldprints if 'fingerprints' in p and suspicious_content(fp, p['fingerprints'])]
            collisions += [p['source_id'] for p in newprints if suspicious_content(fp, p['fingerprints'])]
            duplicate = h in old_hashes
            row = dict(source_id=r['source_id'], proposed_partition=r['proposed_partition'], group_id=r['group_id'],
                source_reference=ref, source_sha256=h, label_reference=r['label_reference'], label_sha256=r['label_sha256'],
                fingerprints=fp, exact_existing_source_duplicate=duplicate, suspected_content_overlap=collisions,
                status='quarantine_suspected_overlap' if duplicate or collisions else 'bounded_duplicate_checks_passed_semantic_review_pending',
                training_eligible=False, events=r['events'])
            newprints.append(dict(source_id=r['source_id'], fingerprints=fp)); old_hashes.add(h)
        except Exception as e:
            row = dict(source_id=r['source_id'], group_id=r['group_id'], proposed_partition=r['proposed_partition'], status='quarantine_fingerprint_or_source_error', error=type(e).__name__ + ':' + str(e), training_eligible=False)
        result.append(row)
        print(json.dumps(dict(new_fingerprints=i + 1, total=len(candidate['sources']), status=row['status'])), flush=True)
    # Quarantine BOTH sides and their whole proposed event/multicamera group.
    # A late-discovered collision must not leave an earlier candidate released.
    protected_complete = all('fingerprints' in p for p in oldprints)
    quarantine_results(result, candidate['sources'], protected_complete)
    jsonl(output / 'verified-candidates.jsonl', result)
    save(output / 'fingerprint-summary.json', dict(schema_version=1, candidate_manifest_sha256=sha(output / 'candidate-manifest.json'),
        split_manifest_sha256=sha(output / 'split-manifest.json'), protected_sources=len(protected),
        protected_fingerprints_complete=sum('fingerprints' in p for p in oldprints),
        selected_new_sources=len(result), statuses=dict(Counter(r['status'] for r in result)),
        source_sha256_computed=sum('source_sha256' in r for r in result),
        model_loads=0, training=0, frames_persisted=0, semantic_truth_created=0,
        limitations=['Five relative positions cannot certify absence of re-encoded, cropped, shifted or partial duplicates.',
                    'Camera/static-background fingerprint matches are suspected overlap, not proof; flagged candidates stay quarantined.',
                    'No all-drive scan or protected-media full rehash; old hashes are recorded audit provenance.',
                    'Pixel fingerprints compare selected new sources against old296test+45regression and selected new sources; oldtrain/validation receive exactSHA/metadata checks only, not content reencoding checks.',
                    'Unfingerprinted candidate/inventory sources are not released for training.']))


def event_evidence(source, event, data):
    """Annotation-only review anchor, with no invented native decode/label truth."""
    from build_action_training_clips import center_indices, contextual_roi
    evidence = dict(source_id=source['source_id'], event_index=event['event_index'],
        actor_id=event['actor_id'], object_id=event['object_id'], action_class=event['class_name'],
        declared_start_frame=event['start_frame_declared'], declared_end_frame=event['end_frame_declared'],
        declared_start_time=event['start_time_declared'], declared_end_time=event['end_time_declared'],
        source_reference=source['source_reference'], label_reference=source['label_reference'],
        label_sha256=source['label_sha256'], location=source['location'], group_id=source['group_id'],
        proposed_partition=source['proposed_partition'], fps_from_label=source['fps'],
        native_center_decode_verified=False, semantic_ground_truth_verified=False,
        binary_training_label=None, training_eligible=False)
    try:
        indices = center_indices(event['start_frame_declared'], event['end_frame_declared'])
        required = set(indices) | {x + 1 for x in indices}
        matching = defaultdict(list)
        for ann in data['annotations']:
            if (ann['actor_id'], ann['object_id']) == (event['actor_id'], event['object_id']) and ann['cur_frame'] in required:
                matching[ann['cur_frame']].append(ann)
        if any(not matching[x] for x in required): raise ValueError('missing_box_frames_both_origins')
        if any(len(matching[x]) != 1 for x in required): raise ValueError('duplicate_box_frames_both_origins')
        boxes = [matching[x][0] for x in sorted(required)]
        if any(b['class_name'] != event['class_name'] for b in boxes): raise ValueError('class_ambiguity_both_origins')
        roi, union = contextual_roi(boxes, source['width'], source['height'])
        evidence.update(status='annotation_center_complete_native_and_semantic_review_pending',
            label_only_center_frame_indices=indices, both_origin_required_annotation_frames=sorted(required),
            candidate_roi_xyxy=roi, actor_union_xyxy=union,
            other_actor_action_classes_at_center=sorted({a['class_name'] for a in data['annotations']
                if a['cur_frame'] in required and a['actor_id'] != event['actor_id']}))
    except ValueError as error:
        evidence.update(status='annotation_center_unavailable', reason=str(error))
    return evidence


def interval_evidence(output):
    candidates = read(output / 'candidate-manifest.json')['sources']
    verified = {r['source_id']: r for r in (json.loads(l) for l in (output / 'verified-candidates.jsonl').open())}
    events = []
    for source in candidates:
        with zipfile.ZipFile(source['label_reference']['archive_path']) as z:
            raw = z.read(source['label_reference']['member'])
        if hashlib.sha256(raw).hexdigest() != source['label_sha256']: raise ValueError('Selected label changed')
        data = json.loads(raw)
        for event in source['events']:
            if event['class_name'] not in TARGET: continue
            e = event_evidence(source, event, data)
            e['source_sha256'] = verified[source['source_id']].get('source_sha256')
            e['content_verification_status'] = verified[source['source_id']]['status']
            events.append(e)
    jsonl(output / 'candidate-event-intervals.jsonl', events)
    csv_rows(output / 'candidate-event-intervals.csv', events, ['source_id', 'group_id', 'proposed_partition',
        'location', 'action_class', 'actor_id', 'event_index', 'declared_start_frame', 'declared_end_frame',
        'declared_start_time', 'declared_end_time', 'status', 'reason', 'content_verification_status',
        'source_sha256', 'label_sha256', 'label_only_center_frame_indices', 'candidate_roi_xyxy'])
    complete = [e for e in events if e['status'].startswith('annotation_center_complete')]
    save(output / 'interval-summary.json', dict(events=len(events), annotation_centers_complete=len(complete),
        counts_by_partition_action_status=dict(Counter('|'.join((e['proposed_partition'], e['action_class'], e['status'])) for e in events)),
        distinct_source_review_units=len({e['source_id'] for e in complete}),
        distinct_group_review_units=len({e['group_id'] for e in complete}),
        proposed_eight_sample_review_images=8 * len(complete), actual_images_generated=0,
        native_center_decode_verified=False, semantic_truth_verified=False, training_labels_created=0,
        candidate_manifest_sha256=sha(output / 'candidate-manifest.json'),
        verified_candidates_sha256=sha(output / 'verified-candidates.jsonl'), script_sha256=sha(__file__)))


def other_local(output):
    roots = [Path('/mnt/e/AI_HUB/07.지능형 관제 서비스 CCTV 영상 데이터'),
             Path('/mnt/e/AI_HUB/078.스마트 제조 시설 안전 감시를 위한 데이터')]
    summaries, labels = [], []
    for root in roots:
        files = sorted(f for f in root.rglob('*') if f.is_file())
        summary = dict(root=str(root), files=len(files), extensions=dict(Counter(f.suffix.lower() for f in files)),
                       archive_errors=[], archive_member_counts=[], qualified_augmentation_sources=0)
        pairs = defaultdict(list)
        if root.name.startswith('07.'):
            for path in files:
                if path.suffix.lower() != '.zip' or '원천' not in str(path.parent): continue
                members, _ = archive_index(path, '.mp4')
                for m in members: pairs[Path(m['member']).name].append(dict(archive_path=str(path), **m))
        for path in files:
            if path.suffix.lower() != '.zip': continue
            try:
                with zipfile.ZipFile(path) as z:
                    entries = [m for m in z.infolist() if not m.is_dir()]
                    summary['archive_member_counts'].append(dict(path=str(path), counts=dict(Counter(Path(m.filename).suffix.lower() for m in entries))))
                    if not root.name.startswith('07.') or '라벨링' not in str(path.parent): continue
                    for member in entries:
                        if not member.filename.lower().endswith('.json'): continue
                        raw = z.read(member); data = json.loads(raw.decode('utf-8-sig'))
                        info = data.get('metadata', {}); ann = data.get('annotations', {}); filename = info.get('file_name')
                        protected = filename in {f'E01_{i:03d}.mp4' for i in range(1, 46)}
                        labels.append(dict(label_archive=str(path), label_member=member.filename,
                            label_sha256=hashlib.sha256(raw).hexdigest(), filename=filename,
                            event_class=ann.get('event_class'), declared_event_frames=ann.get('event_frame'),
                            capture_date=info.get('date'), camera_distribution=info.get('cctv_distribution'),
                            source_references=pairs.get(filename, []), protected45=protected,
                            actor_target_normal_interval_verified=False, training_eligible=False))
            except (zipfile.BadZipFile, NotImplementedError, RuntimeError) as error:
                summary['archive_errors'].append(dict(path=str(path), error=type(error).__name__ + ':' + str(error)))
        summary['scope'] = ('All event-label JSONs and source ZIP directories; event classes/captions are not actor normal labels.'
            if root.name.startswith('07.') else '10000PNG/captionJSON stills in Sublabel; two split ZIP containers unreadable viazipfile, temporal action data not qualified. No claim of absence inside unreadable archives.')
        summaries.append(summary)
    jsonl(output / 'other-local-source-labels-v1.jsonl', labels)
    save(output / 'other-local-audit.json', dict(datasets=summaries, event_label_rows=len(labels),
        event_classes=dict(Counter(r['event_class'] for r in labels)),
        paired_sources=sum(bool(r['source_references']) for r in labels), protected45=sum(r['protected45'] for r in labels),
        qualified_actor_normal_intervals=0, media_full_hashes=0, script_sha256=sha(__file__)))


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('stage', choices=['inventory', 'plan', 'fingerprint', 'intervals', 'other-local'])
    p.add_argument('--base', type=Path, default=PARK); p.add_argument('--output', type=Path, default=OUTPUT)
    p.add_argument('--max-new-files', type=int, default=96); args = p.parse_args()
    args.output = checked_output(args.output)
    if not 1 <= args.max_new_files <= 96: raise ValueError('Bounded source selection must be1..96 files')
    if args.stage == 'inventory': inventory(args.base, args.output)
    elif args.stage == 'plan': plan(args.output, args.max_new_files)
    elif args.stage == 'fingerprint': fingerprints(args.output)
    elif args.stage == 'intervals': interval_evidence(args.output)
    else: other_local(args.output)


if __name__ == '__main__': main()
