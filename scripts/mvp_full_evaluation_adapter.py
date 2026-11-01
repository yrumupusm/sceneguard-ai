"""Local inventory, frozen truth and current MVP-output adapter; never runs inference.

Run with the existing PyAV environment. ``inventory`` fully decodes the supplied
original directories without extracting images. ``truth`` is prediction-blind.
``manifest`` consumes an execution index of {video_id, execution_status, reason,
run_directory} rows and binds the current pipeline's outputs to a Git revision.
All generated artifacts contain local data and belong under ignored outputs/.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from fractions import Fraction
import hashlib
import inspect
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PROTOCOL = 'MVP-ALL-EVENT-EVIDENCE-v1'
BASELINE = '548ff7098045f9efc5bd2edfd5ce61431a5e210e'
CAMERA_EVIDENCE = 'docs/data/AIHUB_INTRUSION_EVALUATION_PLAN.md'
CAMERAS = {'E01_001': 'C1', 'E01_004': 'C2', 'E01_006': 'C3',
           'E01_007': 'C3', 'E01_013': 'C4', 'E01_021': 'C5',
           'E01_030': 'C6', 'E01_031': 'C7', 'E01_039': 'C4', 'E01_045': 'C4'}
SCENES = {'C3': 'runtime/region-revisions/007-inside-20261101-v1/scene007.json',
          'C6': 'runtime/EXP-0034/scene030.json'}
PORTALS = {k: f'runtime/portal-regions/exp0046/{k}.json' for k in SCENES}
STATUSES = {'complete', 'partial', 'unsupported', 'failed', 'not_run'}


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f'Duplicate JSON key: {key}')
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda v: (_ for _ in ()).throw(ValueError(v)))


def save(path, value):
    """Immutable local files; an identical rerun leaves bytes and mtimes alone."""
    path = Path(path).absolute()
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError('Output symlinks are forbidden')
    raw = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError(f'Refusing to overwrite frozen artifact: {path}')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)


def relative(path, root=ROOT):
    path = Path(path).absolute()
    return str(path.relative_to(root)) if path.is_relative_to(root) else str(path)


def resolve(path, root=ROOT):
    path = Path(path)
    return path if path.is_absolute() else root / path


def probe_native(path):
    """Decode all video frames and retain exact integer presentation clocks."""
    import av
    started = time.perf_counter()
    pts, durations = [], []
    with av.open(str(path)) as container:
        if len(container.streams.video) != 1:
            raise ValueError('Expected one original video stream')
        stream = container.streams.video[0]
        stream.codec_context.thread_count = 2
        tb = stream.time_base
        info = dict(source_size=[stream.width, stream.height], codec=stream.codec_context.name,
                    average_rate=str(stream.average_rate), base_rate=str(stream.base_rate),
                    time_base=str(tb), stream_frame_count=stream.frames,
                    stream_start_pts=stream.start_time, stream_duration_pts=stream.duration,
                    container_duration_seconds=(None if container.duration is None
                                                else container.duration / av.time_base),
                    av_version=av.__version__)
        for frame in container.decode(stream):
            if (frame.pts is None or frame.time_base != tb or frame.pts < 0
                    or (pts and frame.pts <= pts[-1])):
                raise ValueError('Missing, changing or non-increasing native PTS')
            if [frame.width, frame.height] != info['source_size']:
                raise ValueError('Changing frame dimensions')
            pts.append(frame.pts)
            durations.append(frame.duration)
    if not pts or info['stream_duration_pts'] is None:
        raise ValueError('No decoded frames or unknown stream duration')
    delta_counts = Counter(b-a for a, b in zip(pts, pts[1:]))
    exact30 = all(Fraction(delta) * tb == Fraction(1, 30) for delta in delta_counts)
    info.update(decoded_frame_count=len(pts), first_native_pts=pts[0], last_native_pts=pts[-1],
                first_pts_seconds=float(pts[0]*tb), last_pts_seconds=float(pts[-1]*tb),
                duration_seconds=float(info['stream_duration_pts']*tb),
                pts_delta_counts={str(k): v for k, v in sorted(delta_counts.items())},
                exact_native_30fps=(info['average_rate'] == '30' and exact30),
                decode_status='complete', decode_elapsed_seconds=time.perf_counter()-started)
    clocks = dict(schema_version=1, time_base=str(tb), native_pts=pts,
                  frame_duration_pts=durations, decoded_frame_count=len(pts))
    return info, clocks


def history_index(root):
    """Conservative prior-use facts; mere official-label inventory is not viewing."""
    evidence = defaultdict(set)
    manifest = root / 'data/aihub_intrusion_audit/manifest.json'
    if manifest.exists():
        for item in read(manifest):
            evidence[Path(item['name']).stem].add(relative(manifest, root))
    # These documents name actually used source clips, rather than all label rows.
    for folder in ('docs/experiments', 'docs/reviews', 'records', 'configs'):
        for path in sorted((root / folder).rglob('*')):
            if path.suffix not in ('.md', '.json') or path.stat().st_size > 3_000_000:
                continue
            for name in set(re.findall(r'\bE01_\d{3}\b', path.read_text(encoding='utf-8'))):
                evidence[name].add(relative(path, root))
    return evidence


def cache_index(root):
    result = defaultdict(list)
    for path in sorted((root / 'outputs').rglob('run.json')):
        if 'validation' in path.parts or path.is_symlink():
            continue
        try:
            meta = read(path)
        except (ValueError, OSError):
            continue
        if not isinstance(meta, dict) or meta.get('model') != 'fcos_resnet50_fpn.COCO_V1':
            continue
        if meta.get('source_sha256'):
            result[meta['source_sha256']].append((path, meta))
    return result


def support_for(video_id, info, root=ROOT):
    camera = CAMERAS.get(video_id)
    reasons = []
    if camera not in SCENES:
        reasons.append('camera_identity_unresolved' if camera is None
                       else 'camera_not_supported_by_fixed_C3_C6_pipeline')
    if not info.get('exact_native_30fps'):
        reasons.append('native_rate_or_PTS_spacing_not_exact_30fps')
    if info.get('stream_start_pts') not in (None, 0) or info.get('first_native_pts') != 0:
        reasons.append('source_PTS_origin_not_zero')
    for name, table in (('scene', SCENES), ('portal', PORTALS)):
        if camera in table and not (root / table[camera]).exists():
            reasons.append(name + '_configuration_missing')
    return dict(supported=not reasons, reasons=reasons, camera_id=camera,
                scene=SCENES.get(camera), portal=PORTALS.get(camera))


def inspect_caches(candidates, video, info, camera, root, clocks):
    """Report fragments and validate whole-source matches using the actual adapter."""
    from sceneguard import video_cards as vc
    configs = read(root / 'configs/mvp0001_cameras.json')['cameras']
    result = []
    for path, meta in candidates:
        data = path.parent / 'person_cache.jsonl'
        record = dict(directory=relative(path.parent, root), metadata_sha256=sha256(path),
                      cache_sha256=sha256(data) if data.exists() else None,
                      frames=meta.get('frames'), first_pts=meta.get('first_pts'),
                      last_pts=meta.get('last_pts'), whole_source_match=False)
        try:
            if camera not in SCENES:
                raise ValueError('No supported scene binding')
            vc.validate_cached(video, configs[camera], path.parent, 0,
                info['duration_seconds'], dict(size=info['source_size'],
                    time_base=info['time_base'], duration=info['duration_seconds']))
            validate_native_partition(data,clocks,0,info['duration_seconds'])
            record['whole_source_match'] = True
            record['reason'] = None
        except (ValueError, KeyError, TypeError, OSError) as exc:
            record['reason'] = str(exc)
        result.append(record)
    return result


def inventory(root, video_roots, label_roots, output):
    videos = sorted({p.absolute() for folder in video_roots for p in Path(folder).rglob('*')
                     if p.is_file() and p.suffix.lower() == '.mp4'})
    labels = sorted({p.absolute() for folder in label_roots for p in Path(folder).rglob('*')
                     if p.is_file() and p.suffix.lower() == '.json'})
    if not videos:
        raise ValueError('No supplied original videos found')
    label_map, official = defaultdict(list), []
    for path in labels:
        raw = read(path)
        meta, ann = raw['metadata'], raw['annotations']
        row = dict(path=relative(path, root), sha256=sha256(path), metadata=meta,
                   annotations=ann, original_event_row_count=len(ann['event_frame']))
        official.append(row)
        label_map[meta['file_name']].append(row)
    history, caches = history_index(root), cache_index(root)
    rows, seen_hashes, seen_ids = [], {}, set()
    for video in videos:
        vid = video.stem
        if vid in seen_ids:
            raise ValueError('Duplicate video stems require explicit recording IDs')
        seen_ids.add(vid)
        video_hash = sha256(video)
        matches = label_map.get(video.name, [])
        if len(matches) != 1:
            raise ValueError(f'Expected exactly one official file_name match: {video.name}')
        label = matches[0]
        clocks_path = Path(output) / 'native-pts' / (vid + '.json')
        # Resume an interrupted inventory only after checking the original hash.
        if clocks_path.exists():
            stored = read(clocks_path)
            if stored['source_sha256'] != video_hash:
                raise ValueError('Frozen native clocks belong to different source bytes')
            info, clocks = stored['media'], stored['clocks']
        else:
            info, clocks = probe_native(video)
            save(clocks_path, dict(source_sha256=video_hash, media=info, clocks=clocks))
        camera = CAMERAS.get(vid)
        prior = sorted(history.get(vid, []))
        development = vid in CAMERAS or bool(prior)
        support = support_for(vid, info, root)
        gate = camera + '_fence' if camera in ('C3', 'C6', 'C7') else (
            camera + '_reference_gate' if camera else 'unresolved_gate:' + vid)
        row = dict(video_id=vid, path=relative(video, root), bytes=video.stat().st_size,
                   sha256=video_hash, duplicate_of=seen_hashes.get(video_hash), media=info,
                   native_pts_path=relative(clocks_path, root), native_pts_sha256=sha256(clocks_path),
                   official_label_path=label['path'], official_label_sha256=label['sha256'],
                   official_metadata=label['metadata'], official_annotations=label['annotations'],
                   original_event_row_count=label['original_event_row_count'],
                   label_frame_count_matches=label['metadata']['frame_count']==info['decoded_frame_count'],
                   label_size_matches=[label['metadata']['width'],label['metadata']['height']]==info['source_size'],
                   camera_id=camera, camera_assignment_status='existing_conservative_visual_group' if camera else 'unresolved',
                   camera_assignment_provenance=CAMERA_EVIDENCE if camera else None,
                   site_group='site_unresolved_do_not_claim_independence',
                   recording_id=vid, session_group=None, session_status='capture_session_unresolved',
                   recording_date=label['metadata'].get('date'), gate_id=gate,
                   split='development' if development else 'prior_use_unknown',
                   prior_use_status='documented_development_or_audit' if development else 'history_incomplete_not_blind',
                   prior_use_evidence=prior, support=support,
                   detector_caches=inspect_caches(caches.get(video_hash, []), video, info, camera, root, clocks),
                   execution_status='not_run' if support['supported'] else 'unsupported',
                   reason='awaiting_current_whole_source_execution' if support['supported'] else '; '.join(support['reasons']))
        rows.append(row)
        seen_hashes.setdefault(video_hash, vid)
        print(f'{vid}: decoded={info["decoded_frame_count"]} rate={info["average_rate"]} '
              f'supported={support["supported"]}', flush=True)
    unique = [r for r in rows if r['duplicate_of'] is None]
    summary = dict(original_video_files=len(rows), unique_original_sha256=len(unique),
                   official_json_files=len(official), original_event_rows=sum(r['original_event_row_count'] for r in rows),
                   duration_seconds=sum(r['media']['duration_seconds'] for r in unique),
                   decoded_frames=sum(r['media']['decoded_frame_count'] for r in unique),
                   supported_video_count=sum(r['support']['supported'] for r in unique),
                   supported_seconds=sum(r['media']['duration_seconds'] for r in unique if r['support']['supported']),
                   rate_counts=dict(Counter(r['media']['average_rate'] for r in unique)),
                   frame_count_mismatches=[r['video_id'] for r in rows if not r['label_frame_count_matches']],
                   unpaired_labels=[r['path'] for r in official if r['metadata']['file_name'] not in {v.name for v in videos}])
    result = dict(schema_version=1, protocol_id=PROTOCOL, baseline_revision=BASELINE,
                  inventory_script_sha256=sha256(Path(__file__)), video_roots=[relative(p,root) for p in video_roots],
                  native_decoder_function_sha256=hashlib.sha256(inspect.getsource(probe_native).encode()).hexdigest(),
                  label_roots=[relative(p,root) for p in label_roots], summary=summary,
                  videos=rows, official_labels=official,
                  invariants=['cctv_distribution is not an independent camera ID',
                              'No inference, pixel extraction, scene changes or negative-label expansion',
                              'Native clocks are decode indexes, not frame/30 approximations'])
    save(Path(output) / 'inventory.json', result)
    return result


def merge_official_events(events):
    """Union only overlapping same-gate ranges before consulting predictions."""
    merged = []
    for event in sorted(events, key=lambda e: (e['gate_id'], e['start'], e['end'], e['id'])):
        if (merged and event['gate_id']==merged[-1]['gate_id']
                and event['start'] < merged[-1]['end']):
            merged[-1]['end'] = max(event['end'], merged[-1]['end'])
            merged[-1]['original_row_indices'] += event['original_row_indices']
            merged[-1]['id'] += '+' + event['id']
        else:
            merged.append(deepcopy(event))
    return merged


def official_truth(row, pts, index_base):
    raw = row['official_annotations']['event_frame']
    events, problems = [], []
    if not row['label_frame_count_matches']:
        problems.append('official_frame_count_differs_from_decoded_count_no_automatic_correction')
    if not row['label_size_matches']:
        problems.append('official_source_dimensions_differ')
    for i, pair in enumerate(raw):
        if (not isinstance(pair,list) or len(pair)!=2 or any(type(v) is not int for v in pair)
                or not 0 <= pair[0]-index_base < pair[1]-index_base < len(pts)):
            problems.append(f'row_{i}_invalid_under_index_base_{index_base}')
    if not problems:
        for i, (a,b) in enumerate(raw):
            events.append(dict(id=f'official-row-{i:03d}', gate_id=row['gate_id'],
                start=pts[a-index_base], end=pts[b-index_base], onset_precise=False,
                provenance=f'official JSON SHA256 {row["official_label_sha256"]}; '
                           f'{index_base}-based reference, indexing unresolved',
                original_row_indices=[i], original_event_frame=[a,b]))
    return dict(video_id=row['video_id'], truth_basis='unresolved' if problems else 'official_reference',
        original_event_frame=deepcopy(raw), original_event_row_count=len(raw),
        original_label_order_preserved=True, index_base=index_base, index_base_status='unresolved_two_separate_references',
        endpoint_rule='map the stated start and end frame boundaries to native PTS; score [start,end)',
        event_unit='same-camera/gate overlapping intervals unioned before predictions',
        events=merge_official_events(events), unresolved_reference_events=len(raw) if problems else 0,
        verified_non_event_intervals=[], unresolved_reasons=problems,
        official_label_sha256=row['official_label_sha256'], video_sha256=row['sha256'])


def reviewed_evidence(root):
    """Reuse direct user evidence, never model output or Codex visual drafts."""
    labels_path = root / 'configs/mvp_small_eval_labels_r1.json'
    labels = read(labels_path)
    masks, positives, candidates = defaultdict(list), defaultdict(list), defaultdict(list)
    for item in labels['labels']:
        record = dict(start=item['interval_seconds'][0], end=item['interval_seconds'][1],
            provenance=f'{relative(labels_path, root)} SHA256 {sha256(labels_path)}; '
                       f'user {item["review_clip_id"]}; scheduled-window scope only',
            evidence_id=item['review_clip_id'], completion_reference=item['completion_reference'])
        if item['label_status'] != 'human_confirmed_for_window':
            raise ValueError('Reviewed mask requires existing direct user confirmation')
        target = masks if item['reference_label']=='no_climbing_observed' else positives
        target[item['source_id']].append(record)
    vpath = root / 'docs/experiments/EXP-0016-prompt-evidence-rubric.md'
    vprovenance = f'{relative(vpath, root)} SHA256 {sha256(vpath)}; direct user original-window review'
    for vid, eid in [('E01_004','v02'), ('E01_021','v04')]:
        masks[vid].append(dict(start=0., end=5., provenance=vprovenance, evidence_id=eid))
    for vid, eid, a,b in [('E01_004','v01',60.,65.), ('E01_021','v03',65.,70.)]:
        positives[vid].append(dict(start=a, end=b, provenance=vprovenance, evidence_id=eid,
            onset_precise=False, interval_is_review_window_not_event_bounds=True,
            boundary_relation='uncertain_gate_side_gap' if eid=='v03' else 'observed_attempt_progress'))
    late = root / 'docs/experiments/EXP-0048-user-review.md'
    masks['E01_007'].append(dict(start=84., end=104., evidence_id='EXP48-late-pedestrians',
        provenance=f'{relative(late,root)} SHA256 {sha256(late)}; user confirmed all ordinary passage'))
    # The user judged these particular original clips. Read only their source
    # presentation clocks, never candidate decisions or scores, from old receipts.
    for vid, segment, review in [('E01_007','s0007','EXP-0040'),
                                 ('E01_007','s0008','EXP-0041'),
                                 ('E01_030','s0002','EXP-0041')]:
        receipt_path = root / f'outputs/exp0040/{vid[-3:]}-v1/evidence/render-receipt.json'
        review_path = root / f'docs/experiments/{review}-user-review.md'
        receipt = read(receipt_path)
        clips = [v for v in receipt['videos'] if Path(v['path']).name == segment+'.mp4']
        if len(clips) != 1:
            raise ValueError('Exact existing user-review clip scope missing')
        clocks = clips[0]['pts_mapping']
        masks[vid].append(dict(start=clocks[0]['source_pts'], end=clocks[-1]['source_pts'],
            evidence_id=review+'-'+segment,
            provenance=f'{relative(review_path,root)} SHA256 {sha256(review_path)}; '
                f'original-clip clocks {relative(receipt_path,root)} SHA256 {sha256(receipt_path)}',
            scope_rule='conservative [first displayed source PTS,last displayed source PTS); no extension'))
    candidate = root / 'docs/data/AIHUB_INTRUSION_USER_REVIEW.md'
    candidates['E01_006'].append(dict(start=119., end=132.,
        provenance=f'{relative(candidate,root)} SHA256 {sha256(candidate)}',
        status='user_reviewed_non_event_candidate_not_verified',
        reason='precise interval/gate scope not approved; not a scored negative mask'))
    return masks, positives, candidates


def freeze_truth(inv_path, output, root=ROOT):
    inv = read(inv_path)
    masks, positives, candidates = reviewed_evidence(root)
    qualitative = {
        'E01_007': [dict(approximate_pts=56.7,behavior='approach_without_crossing',
            provenance='docs/experiments/EXP-0028-user-tracking-review.md',
            precision='approximate observation; does not create an interval mask'),
            dict(approximate_pts=66.,behavior='crossing_begins',
                provenance='docs/experiments/EXP-0028-user-tracking-review.md',
                precision='approximate only; later EXP41 review confirms onset somewhere in its clip'),
            dict(review_window=[61.86666666666667,65.83333333333333],behavior='attempt_onset_seen',
                provenance='docs/experiments/EXP-0041-user-review.md',
                exact_onset_pts=None,completion_reference='not_assessed')],
        'E01_031': [dict(all_people_completed=False,completion_reference='incomplete_at_clip_end',
            exact_onset_pts=None,completion_pts=None,
            provenance='docs/data/AIHUB_INTRUSION_USER_REVIEW.md',
            precision='group completion not observed; not a negative-video label')],
        'E01_030': [dict(approximate_pts=90.,behavior='people_climbing_with_detection_gaps',
            provenance='docs/experiments/EXP-0028-user-tracking-review.md',
            event_context_id='E01_030-existing-positive-context',exact_onset_pts=None),
            dict(observed_pts=90.,behavior='three_people_climbing; limited_person_and_joint_detection',
                provenance='docs/experiments/EXP-0024-user-pose-review.md',
                event_context_id='E01_030-existing-positive-context',exact_onset_pts=None),
            dict(observed_pts=94.,behavior='one_person_on_gate_and_one_already_beyond',
                provenance='docs/experiments/EXP-0024-user-pose-review.md',
                event_context_id='E01_030-existing-positive-context',
                all_people_completed=None,completion_pts=None),
            dict(review_window=[92.,93.4],behavior='first_two_crossers_briefly_visible_after_gate_overlap',
                provenance='docs/experiments/EXP-0039-user-review.md',
                event_context_id='E01_030-existing-positive-context',third_person_reviewed=False,
                interval_is_review_window_not_event_bounds=True),
            dict(review_window=[97.833,99.233],behavior='late_person_visibility_with_partial_occlusion_and_loss',
                provenance='docs/experiments/EXP-0039-user-review.md',
                event_context_id='E01_030-existing-positive-context',
                interval_is_review_window_not_event_bounds=True)],
    }
    variants = {'official-zero-based': [], 'official-one-based': [], 'reviewed': []}
    for row in inv['videos']:
        clocks_path = resolve(row['native_pts_path'],root)
        if sha256(clocks_path) != row['native_pts_sha256']:
            raise ValueError('Inventory native-clock artifact changed')
        clock = read(clocks_path)['clocks']
        pts = [float(v*Fraction(clock['time_base'])) for v in clock['native_pts']]
        vid = row['video_id']
        negatives = [dict(m,gate_id=row['gate_id']) for m in masks[vid]]
        for name, base in [('official-zero-based',0),('official-one-based',1)]:
            gold = official_truth(row,pts,base)
            compatible, conflicts = [], []
            for mask in negatives:
                overlap = any(e['gate_id']==mask['gate_id'] and
                    max(e['start'],mask['start']) < min(e['end'],mask['end']) for e in gold['events'])
                (conflicts if overlap else compatible).append(deepcopy(mask))
            gold.update(verified_non_event_intervals=compatible,
                non_event_truth_basis='existing_user_review_only',
                conflicting_reviewed_non_event_intervals=conflicts)
            variants[name].append(gold)
        variants['reviewed'].append(dict(video_id=vid, truth_basis='reviewed' if negatives else 'unresolved',
            video_sha256=row['sha256'], official_label_sha256=row['official_label_sha256'],
            original_event_frame=deepcopy(row['official_annotations']['event_frame']),
            original_event_row_count=row['original_event_row_count'],
            events=[], unresolved_reference_events=len(positives[vid])+(1 if vid=='E01_030' else 0),
            unresolved_reference_unit='unique reviewed positive windows or recording contexts; not repeated observations',
            reviewed_positive_windows=positives[vid],
            qualitative_user_observations=[dict(o,provenance_sha256=sha256(root/o['provenance']))
                                          for o in qualitative.get(vid,[])],
            unresolved_reasons=['Reviewed positive windows or context do not establish exact continuous event bounds']
                if positives[vid] or vid=='E01_030' else [],
            verified_non_event_intervals=negatives, non_event_candidates=candidates[vid],
            outside_review_masks='unreviewed; never negative'))
    result = {}
    from sceneguard.accuracy_evaluation import union_seconds
    for name, videos in variants.items():
        value = dict(schema_version=1, protocol_id=PROTOCOL, truth_version='MVP-ALL-TRUTH-v1',
            variant=name, inventory_sha256=sha256(inv_path), truth_builder_sha256=sha256(__file__),
            prediction_inputs_used=False, original_event_rows=sum(v['original_event_row_count'] for v in videos),
            scored_event_count=sum(len(v['events']) for v in videos),
            unresolved_reference_events=sum(v['unresolved_reference_events'] for v in videos),
            verified_non_event_seconds=sum(union_seconds(v['verified_non_event_intervals']) for v in videos),
            videos=videos)
        save(Path(output)/(name+'.json'),value)
        result[name] = {k:value[k] for k in ('original_event_rows','scored_event_count',
            'unresolved_reference_events','verified_non_event_seconds')}
    save(Path(output)/'coverage.json', result)
    return result


def extract_predictions(cards):
    """Read each original candidate and its own actual first confirmation once."""
    if (cards.get('execution_mode') != 'current_input_analysis'
            or cards.get('source_evidence_mode') != 'computed_in_current_run'
            or cards.get('contract') != 'gate_activity_episodes_v1'):
        raise ValueError('Current mvp_pipeline output required, not an EXP replay')
    events, evidence = {}, {}
    for collection, target in [('events',events),('evidence',evidence)]:
        for row in cards[collection]:
            key = row['event_id']
            if key in target:
                raise ValueError('Duplicate original candidate/evidence')
            target[key] = row
    if set(events) != set(evidence):
        raise ValueError('Candidate/evidence partition differs')
    predictions, owner, expected_notices = {}, {}, set()
    for card in cards['cards']:
        cid = card['incident_id']
        if cid in predictions:
            raise ValueError('Duplicate incident card')
        pred = dict(id=cid, gate_id=card['gate_id'], suspicion_evidence_pts=[],
                    confirmation_evidence_pts=[], notifications=[], source_evidence=[])
        for eid in card['event_ids']:
            if eid in owner or eid not in events:
                raise ValueError('Missing or multiply assigned candidate')
            owner[eid] = cid
            event, state = events[eid], evidence[eid]
            at = event['decision_time_pts']
            if (event['gate_id'] != card['gate_id'] or state['incident_id'] != cid
                    or state['opened_pts'] != at):
                raise ValueError('Card/evidence source scope or original decision differs')
            pred['suspicion_evidence_pts'].append(at)
            confirmed = state.get('first_confirmation_pts')
            if confirmed is not None:
                if confirmed < at:
                    raise ValueError('Backdated first confirmation')
                pred['confirmation_evidence_pts'].append(confirmed)
            pred['source_evidence'].append(dict(event_id=eid, suspicion_pts=at,
                first_confirmation_pts=confirmed, automatic_status=state['automatic_status']))
        # Equal source timestamps may represent separate original candidates;
        # source_evidence preserves all of them; scorer needs unique points only.
        for field in ('suspicion_evidence_pts','confirmation_evidence_pts'):
            pred[field] = sorted(set(pred[field]))
        if card.get('first_confirmation_pts') != min(pred['confirmation_evidence_pts'],default=None):
            raise ValueError('Card confirmation differs from its actually confirmed evidence')
        for kind, flag in [('suspicion','suspicion_notified'),('confirmation','confirmation_notified')]:
            if card.get(flag) is True:
                expected_notices.add((cid,kind))
        if card.get('confirmation_notified') is not bool(pred['confirmation_evidence_pts']):
            raise ValueError('Confirmed evidence must preserve the first confirmation intent')
        predictions[cid] = pred
    if set(owner) != set(events):
        raise ValueError('Original candidates missing from incident cards')
    kinds, keys = set(), set()
    for notice in cards['notification_intents']:
        cid, kind = notice['incident_id'], notice['kind']
        if (cid not in predictions or kind not in ('suspicion','confirmation')
                or (cid,kind) in kinds or notice['notification_key'] in keys):
            raise ValueError('Invalid or duplicate first notification intent')
        kinds.add((cid,kind)); keys.add(notice['notification_key'])
        predictions[cid]['notifications'].append(dict(kind=kind, pts=notice['decision_time_pts']))
    if kinds != expected_notices:
        raise ValueError('Missing or extra actual first notification intent')
    # Notifications are a separate stream. Cross-check their timeline, including
    # timestamps, so omitting a list entry cannot silently improve alarm metrics.
    timeline_notices = [(r['incident_id'],r['notification_kind'],r['decision_time_pts'],r['notification_key'])
                        for r in cards['timeline'] if r['notify']]
    actual_notices = [(r['incident_id'],r['kind'],r['decision_time_pts'],r['notification_key'])
                      for r in cards['notification_intents']]
    if sorted(timeline_notices) != sorted(actual_notices):
        raise ValueError('Notification intents differ from actual first-notification timeline')
    return list(predictions.values())


def revision_code_hashes(root, revision):
    if not re.fullmatch(r'[0-9a-f]{40}',revision):
        raise ValueError('Use the full actual analysis Git revision')
    names = subprocess.check_output(['git','ls-tree','-r','--name-only',revision,'--','sceneguard'],
                                    cwd=root,text=True).splitlines()
    result = {name: hashlib.sha256(subprocess.check_output(['git','show',revision+':'+name],cwd=root)).hexdigest()
              for name in names if name.endswith('.py')}
    if not result or 'sceneguard/mvp_pipeline.py' not in result:
        raise ValueError('Analysis revision has no MVP pipeline source tree')
    return result


def validate_stage(folder, request_hash):
    receipt = read(folder/'stage.json')
    if receipt['binding']['request_sha256'] != request_hash:
        raise ValueError('Pipeline stage belongs to another request')
    actual = {}
    for path in folder.rglob('*'):
        if path.is_symlink():
            raise ValueError('Pipeline stage artifacts must not be symlinks')
        if path.is_file() and path.name != 'stage.json':
            actual[str(path.relative_to(folder))] = sha256(path)
    if actual != receipt['artifacts']:
        raise ValueError('Pipeline stage artifact bytes changed or omitted')
    for name, digest in receipt['artifacts'].items():
        path = folder/name
        if not path.resolve().is_relative_to(folder.resolve()) or sha256(path) != digest:
            raise ValueError('Pipeline stage artifact bytes changed')
    return receipt


def validate_native_partition(path, clocks, begin, end, *, indexed=False, allow_outside=False):
    """Compare to decoded clocks, including frame zero and every internal frame."""
    expected = [p for p in clocks['native_pts']
                if begin <= float(p*Fraction(clocks['time_base'])) < end]
    count, previous = 0, None
    with Path(path).open(encoding='utf-8') as stream:
        for line in stream:
            frame = json.loads(line)
            at = float(frame['native_pts']*Fraction(frame['time_base']))
            if previous is not None and at <= previous:
                raise ValueError('Duplicated or reordered native source frames')
            previous = at
            if allow_outside and not begin <= at < end:
                continue
            if (count >= len(expected) or frame['native_pts'] != expected[count]
                    or frame['time_base'] != clocks['time_base'] or frame['pts'] != at
                    or (indexed and frame['frame_index'] != count)):
                raise ValueError('Missing, duplicated or changed native source frame partition')
            count += 1
    if count != len(expected) or not count:
        raise ValueError('Incomplete pipeline source frame partition')
    return count


def adapt_execution(row, execution, expected_code, root=ROOT):
    status = execution['execution_status']
    if status not in STATUSES:
        raise ValueError('Unknown execution status')
    result = dict(execution_status=status, processed_seconds=0., predictions=[])
    if status in ('unsupported','failed','not_run'):
        if not execution.get('reason'):
            raise ValueError('Noncomplete execution needs a reason')
        result['reason'] = execution['reason']
        return result
    directory = execution.get('run_directory') or execution.get('output_path')
    if not directory:
        raise ValueError('Execution needs a current pipeline run_directory/output_path')
    folder = resolve(directory,root)
    request, state, viewer = [read(folder/name) for name in ('request.json','status.json','viewer-manifest.json')]
    if state['state'] != 'analysis_complete':
        raise ValueError('A complete upstream pipeline result is required for adapted output')
    if (request['code_sha256'] != expected_code or viewer['source_sha256'] != row['sha256']
            or request['input_sha256'].get(request['video']) != row['sha256']
            or viewer['video_id'] != row['video_id'] or request['camera'] != row['camera_id']
            or viewer['gate_id'] != row['gate_id']):
        raise ValueError('Analysis code/source/camera/gate binding differs from inventory')
    for path, digest in request['input_sha256'].items():
        if sha256(resolve(path,root)) != digest:
            raise ValueError('Pipeline input changed since execution')
    request_hash = sha256(folder/'request.json')
    decision_receipt = validate_stage(folder/'decision',request_hash)
    validate_stage(folder/'image-paths',request_hash)
    cards_path = Path(viewer['cards_path'])
    if cards_path.resolve() != (folder/'decision/cards.json').resolve() or sha256(cards_path) != viewer['cards_sha256']:
        raise ValueError('Viewer/card artifact binding differs')
    clocks_path = resolve(row['native_pts_path'],root)
    if sha256(clocks_path) != row['native_pts_sha256']:
        raise ValueError('Frozen source clock changed')
    clocks = read(clocks_path)['clocks']
    begin, end = viewer['requested_window']
    count = validate_native_partition(folder/'image-paths/frame-evidence.jsonl',clocks,begin,end,indexed=True)
    tracking = folder/'source/tracking/frames.jsonl'
    baseline_path = folder/'source/analysis/analysis.json'
    binding = decision_receipt['binding']
    if (sha256(tracking) != binding['tracking_sha256']
            or sha256(baseline_path) != binding['analysis_sha256']):
        raise ValueError('Decision source analysis/tracking bytes changed')
    validate_native_partition(tracking,clocks,begin,end)
    cache_folder = resolve(read(baseline_path)['source_paths']['cache'],root)
    if binding['cache_sha256'] != dict(cache=sha256(cache_folder/'person_cache.jsonl'),
                                      metadata=sha256(cache_folder/'run.json')):
        raise ValueError('Decision detector-cache bytes changed')
    validate_native_partition(cache_folder/'person_cache.jsonl',clocks,begin,end,allow_outside=True)
    if state['frames'] != count:
        raise ValueError('Incomplete pipeline source frame partition')
    if status=='complete' and (request.get('whole') is not True or begin != 0
            or abs(end-row['media']['duration_seconds'])>1e-9
            or count != row['media']['decoded_frame_count']):
        raise ValueError('Complete requires every original frame from beginning to end')
    result.update(processed_seconds=end-begin, predictions=extract_predictions(read(cards_path)),
        execution_binding=dict(run_directory=relative(folder,root), request_sha256=request_hash,
            viewer_sha256=sha256(folder/'viewer-manifest.json'), cards_sha256=sha256(cards_path),
            pipeline_status_sha256=sha256(folder/'status.json'), native_frames=count,
            full_native_pts_verified=status=='complete', detector_cache_sha256=binding['cache_sha256'],
            elapsed_seconds=state.get('elapsed_seconds')))
    if status=='partial':
        if not execution.get('reason'):
            raise ValueError('Partial execution requires a reason')
        result['reason'] = execution['reason']
    return result


def build_manifest(inv_path, truth_path, executions_path, revision, output, root=ROOT):
    inv, truth, executions = read(inv_path), read(truth_path), read(executions_path)
    if truth['inventory_sha256'] != sha256(inv_path):
        raise ValueError('Truth was frozen against a different inventory')
    truth_rows = {v['video_id']:v for v in truth['videos']}
    entries = executions['videos'] if isinstance(executions,dict) else executions
    index = {}
    for e in entries:
        if e['video_id'] in index:
            raise ValueError('Duplicate execution video row')
        index[e['video_id']] = e
    if set(index) != {r['video_id'] for r in inv['videos']} or set(truth_rows) != set(index):
        raise ValueError('Preserve the complete inventory/truth/execution row set')
    expected_code = revision_code_hashes(root,revision)
    videos, seen_hashes = [], set()
    for row in inv['videos']:
        if row['sha256'] in seen_hashes:
            continue  # Files remain in inventory; one report counts each source once.
        seen_hashes.add(row['sha256'])
        gold = truth_rows[row['video_id']]
        if gold['video_sha256'] != row['sha256']:
            raise ValueError('Truth source hash differs')
        v = dict(video_id=row['video_id'], split=row['split'], duration_seconds=row['media']['duration_seconds'],
            truth_basis=gold['truth_basis'], events=deepcopy(gold['events']),
            unresolved_reference_events=gold['unresolved_reference_events'],
            verified_non_event_intervals=deepcopy(gold['verified_non_event_intervals']),
            video_sha256=row['sha256'], official_label_sha256=row['official_label_sha256'],
            original_event_row_count=gold['original_event_row_count'])
        v.update(adapt_execution(row,index[row['video_id']],expected_code,root))
        videos.append(v)
    manifest = dict(schema_version=1, protocol_id=PROTOCOL, analysis_revision=revision,
        inventory_sha256=sha256(inv_path), truth_sha256=sha256(truth_path),
        execution_index_sha256=sha256(executions_path), adapter_sha256=sha256(__file__),
        truth_variant=truth['variant'], videos=videos)
    from sceneguard.accuracy_evaluation import evaluate
    evaluate(manifest)  # Validate the scorer contract, without pretending inference ran.
    save(output,manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    sub = parser.add_subparsers(dest='command',required=True)
    p = sub.add_parser('inventory')
    p.add_argument('--video-root',type=Path,action='append')
    p.add_argument('--label-root',type=Path,action='append')
    p.add_argument('--output',type=Path,required=True)
    p = sub.add_parser('truth')
    p.add_argument('--inventory',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p = sub.add_parser('manifest')
    for name in ('inventory','truth','executions','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--analysis-revision',required=True)
    args = parser.parse_args()
    root = args.root.absolute()
    if args.command=='inventory':
        result = inventory(root,args.video_root or [root/'data/TS_침입'],
                           args.label_root or [root/'data/TL_침입'],args.output)
        print(json.dumps(result['summary'],ensure_ascii=False,indent=2))
    elif args.command=='truth':
        print(json.dumps(freeze_truth(args.inventory,args.output,root),ensure_ascii=False,indent=2))
    else:
        result = build_manifest(args.inventory,args.truth,args.executions,args.analysis_revision,args.output,root)
        print(json.dumps(dict(videos=len(result['videos']),output=str(args.output))))


if __name__=='__main__':
    main()
