#!/usr/bin/env python3
"""Read-only EXP-0063 source/label audit; never creates training labels.

The default audit reads *all* supplied 월담 pairs, including excluded scenarios.
Packet PTS are presentation timestamps, sorted before checking the CFR grid;
demux order may differ because of B frames. No decoding occurs in the audit.
Optional local overlays require a completed, hash-bound split manifest first.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import platform
import re
import sys
import time

BASE = Path('/mnt/e/AI_HUB/173.공원 주요시설 및 불법행위 감시 CCTV 영상 데이터/01.데이터/1.Training')
SOURCES = Path('원천데이터/TS_행위(불법행위)데이터2/1.불법행위/4.월담행위')
LABELS = Path('라벨링데이터/TL_행위(불법행위)데이터2/1.불법행위/4.월담행위')
OUTPUT = Path('outputs/action-recognition/exp0063/data-audit')
VERSION = 'exp0063-audit-v1'


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def write_jsonl(path, rows):
    with Path(path).open('w') as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')


def scenario_number(relative):
    match = re.match(r'^4-(\d+)', Path(relative).parts[0])
    return int(match[1]) if match else None


def excluded_scenario(number):
    return number is not None and (19 <= number <= 35 or 69 <= number <= 70)


def seconds(value):
    parts = str(value).split(':')
    if len(parts) != 3:
        raise ValueError('expected HH:MM:SS')
    h, m, s = map(float, parts)
    if not all(math.isfinite(x) for x in (h, m, s)) or h < 0 or not 0 <= m < 60 or not 0 <= s < 60:
        raise ValueError('invalid clock time')
    return h * 3600 + m * 60 + s


def integer(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or int(value) != value:
        raise ValueError('expected integer')
    return int(value)


def issue(code, **detail):
    return {'code': code, **detail}


def inventory(base):
    """Pair by relative path stem, never by basename alone."""
    source_root, label_root = Path(base) / SOURCES, Path(base) / LABELS
    if not source_root.is_dir() or not label_root.is_dir():
        raise ValueError('both supplied source and label directories must exist')
    sources = {str(p.relative_to(source_root).with_suffix('')): p for p in source_root.rglob('*')
               if p.is_file() and p.suffix.lower() == '.mp4'}
    labels = {str(p.relative_to(label_root).with_suffix('')): p for p in label_root.rglob('*')
              if p.is_file() and p.suffix.lower() == '.json'}
    if not sources and not labels:
        raise ValueError('empty inventory')
    rows = []
    for key in sorted(sources.keys() | labels.keys()):
        scenario = scenario_number(key)
        rows.append({'source_id': key, 'scenario': scenario,
                     'excluded': excluded_scenario(scenario),
                     'exclusion_reason': 'user_excluded_scenario_range' if excluded_scenario(scenario) else None,
                     'source_path': str(sources[key]) if key in sources else None,
                     'label_path': str(labels[key]) if key in labels else None})
    return rows


def audit_label(data, source_name):
    """Check declared actor/object associations; absence stays unlabeled."""
    errors, warnings, events = [], [], []
    result = {'errors': errors, 'warnings': warnings, 'events': events,
              'annotation_classes': {}, 'event_classes': {}, 'frame_origin': 'unresolved',
              'negative_label_status': 'unreviewed_actor_events_only_no_training_negatives',
              'trainable': False}
    if not isinstance(data, dict) or not all(k in data for k in ('info', 'events', 'annotations')):
        errors.append(issue('schema_top_level'))
        return result
    info, raw_events, annotations = data['info'], data['events'], data['annotations']
    if not isinstance(info, dict) or not isinstance(raw_events, list) or not isinstance(annotations, list):
        errors.append(issue('schema_container_types'))
        return result
    result['info'] = info
    required = {'filename', 'height', 'width', 'date_captured', 'frame', 'fps', 'location', 'video_length'}
    missing = sorted(required - info.keys())
    if missing:
        errors.append(issue('schema_info_missing', fields=missing))
        return result
    try:
        fps = float(info['fps'])
        count, width, height = (integer(info[x]) for x in ('frame', 'width', 'height'))
        if not math.isfinite(fps) or fps <= 0 or min(count, width, height) <= 0:
            raise ValueError('nonpositive dimensions/rate/count')
        datetime.strptime(info['date_captured'], '%Y/%m/%d %H:%M:%S')
        if not isinstance(info['location'], str) or not info['location'].strip():
            raise ValueError('missing explicit location')
        duration = seconds(info['video_length'])
    except (TypeError, ValueError, OverflowError):
        errors.append(issue('invalid_info_values'))
        return result
    if info['filename'] != source_name:
        errors.append(issue('filename_mismatch', declared=info['filename'], actual=source_name))
    result['declared_duration_seconds'] = duration
    by_actor = defaultdict(list)
    classes = Counter()
    duplicate_keys = Counter()
    origin_valid = {0: True, 1: True}
    for index, annotation in enumerate(annotations):
        try:
            if not isinstance(annotation, dict):
                raise ValueError('annotation not object')
            frame = integer(annotation['cur_frame'])
            actor, obj = integer(annotation['actor_id']), integer(annotation['object_id'])
            name = annotation['class_name']
            if not isinstance(name, str) or not name:
                raise ValueError('class name')
            box = annotation['bbox']
            if len(box) != 2 or any(len(point) != 2 for point in box):
                raise ValueError('bbox is not two xy corners')
            x1, y1, x2, y2 = map(float, (*box[0], *box[1]))
            if not all(math.isfinite(v) for v in (x1, y1, x2, y2)):
                raise ValueError('nonfinite bbox')
        except (KeyError, TypeError, ValueError, OverflowError):
            errors.append(issue('annotation_schema', annotation_index=index))
            continue
        classes[name] += 1
        if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            errors.append(issue('bbox_bounds', annotation_index=index, bbox=box))
        for origin in (0, 1):
            if not 0 <= frame - origin < count:
                origin_valid[origin] = False
        if not (0 <= frame < count or 1 <= frame <= count):
            errors.append(issue('annotation_frame_out_of_range', annotation_index=index, frame=frame))
        by_actor[(actor, obj)].append((index, frame, name))
        duplicate_keys[(actor, obj, frame)] += 1
    duplicates = [(list(key), n) for key, n in duplicate_keys.items() if n > 1]
    if duplicates:
        warnings.append(issue('duplicate_actor_object_frame', keys=duplicates))
    covered = set()
    event_classes = Counter()
    for index, event in enumerate(raw_events):
        try:
            start, end = (integer(event['ev_' + side + '_frame']) for side in ('start', 'end'))
            ts, te = seconds(event['start_time']), seconds(event['end_time'])
            actor, obj = integer(event['actor_id']), integer(event['object_id'])
        except (KeyError, TypeError, ValueError, OverflowError):
            errors.append(issue('event_schema', event_index=index))
            continue
        if end < start or te < ts:
            errors.append(issue('event_reversed', event_index=index))
        for origin in (0, 1):
            if not (0 <= start - origin <= end - origin < count):
                origin_valid[origin] = False
        if not (0 <= start <= end < count or 1 <= start <= end <= count):
            errors.append(issue('event_frame_out_of_range', event_index=index))
        if not (0 <= ts <= te <= duration):
            errors.append(issue('event_time_out_of_range', event_index=index, start=ts, end=te))
        declared_actor_boxes = by_actor[(actor, obj)]
        matching = [(i, f, c) for i, f, c in declared_actor_boxes if start <= f <= end]
        covered.update(i for i, _, _ in matching)
        names = sorted({c for _, _, c in matching})
        event_class = names[0] if len(names) == 1 else 'ambiguous_or_missing'
        event_classes[event_class] += 1
        if not matching:
            errors.append(issue('event_without_declared_actor_boxes', event_index=index, actor_id=actor, object_id=obj))
        if len(names) > 1:
            warnings.append(issue('event_multiple_classes', event_index=index, classes=names))
        missing_frames = sorted(set(range(start, end + 1)) - {f for _, f, _ in matching}) if 0 <= end - start <= 1000000 else []
        if missing_frames:
            warnings.append(issue('event_sparse_boxes', event_index=index, missing_count=len(missing_frames)))
        origins = {}
        for origin in (0, 1):
            origins[str(origin)] = {'start_seconds_cfr': (start - origin) / fps,
                                    'end_seconds_cfr': (end - origin) / fps,
                                    'start_minus_declared_seconds': (start - origin) / fps - ts,
                                    'end_minus_declared_seconds': (end - origin) / fps - te}
        # Integer-second timestamps are not precise enough to decide index origin.
        if min(max(abs(x['start_minus_declared_seconds']), abs(x['end_minus_declared_seconds']))
               for x in origins.values()) > 1 + 1 / fps:
            warnings.append(issue('event_time_frame_large_disagreement', event_index=index))
        events.append({'event_index': index, 'actor_id': actor, 'object_id': obj,
                       'class_name': event_class, 'annotation_classes': names,
                       'start_frame_declared': start, 'end_frame_declared': end,
                       'start_time_declared': ts, 'end_time_declared': te,
                       'origin_alternatives': origins, 'matching_box_count': len(matching),
                       'missing_box_frames': missing_frames,
                       'box_frame_min': min((f for _, f, _ in matching), default=None),
                       'box_frame_max': max((f for _, f, _ in matching), default=None),
                       'training_label': None})
    orphan_count = sum(len(items) for items in by_actor.values()) - len(covered)
    if orphan_count:
        warnings.append(issue('boxes_outside_declared_actor_events', count=orphan_count))
    result.update(annotation_classes=dict(classes), event_classes=dict(event_classes),
                  annotation_count=len(annotations), event_count=len(raw_events),
                  origin_bounds_compatible={str(k): v for k, v in origin_valid.items()})
    return result


def audit_video(path):
    """Demux complete video packets without decoding or assuming packet=frame."""
    import av
    with av.open(str(path)) as container:
        if len(container.streams.video) != 1:
            raise ValueError('expected one video stream')
        stream = container.streams.video[0]
        result = {'codec': stream.codec_context.name, 'width': stream.width, 'height': stream.height,
                  'average_rate': str(stream.average_rate), 'time_base': str(stream.time_base),
                  'stream_declared_frames': stream.frames, 'stream_start_time_ticks': stream.start_time,
                  'stream_duration_ticks': stream.duration,
                  'stream_duration_seconds': float(stream.duration * stream.time_base) if stream.duration is not None else None,
                  'container_duration_seconds': container.duration / av.time_base if container.duration is not None else None,
                  'stream_count': len(container.streams), 'video_stream_count': len(container.streams.video),
                  'audio_stream_count': len(container.streams.audio), 'decoded_frame_count': None,
                  'packet_is_frame_assumption': False}
        pts, dts, durations, sizes = [], [], [], []
        missing_pts = missing_dts = 0
        for packet in container.demux(stream):
            if packet.size == 0:  # PyAV's final flush packet has no media payload.
                continue
            pts.append(packet.pts)
            dts.append(packet.dts)
            durations.append(packet.duration)
            sizes.append(packet.size)
            missing_pts += packet.pts is None
            missing_dts += packet.dts is None
        known = sorted(p for p in pts if p is not None)
        gaps = Counter(b - a for a, b in zip(known, known[1:]))
        known_dts = [d for d in dts if d is not None]
        result.update(packet_count=len(pts), packet_pts_missing=missing_pts, packet_dts_missing=missing_dts,
                      packet_pts_duplicate_count=len(known) - len(set(known)),
                      pts_decode_order_decreases=sum(b < a for a, b in zip(pts, pts[1:]) if a is not None and b is not None),
                      dts_nonincreasing=sum(b <= a for a, b in zip(known_dts, known_dts[1:])),
                      first_presentation_seconds=float(known[0] * stream.time_base) if known else None,
                      last_presentation_seconds=float(known[-1] * stream.time_base) if known else None,
                      presentation_gap_ticks={str(k): v for k, v in sorted(gaps.items())},
                      packet_duration_ticks=dict(Counter(str(v) for v in durations)),
                      packet_payload_bytes=sum(sizes))
        result['_sorted_pts'] = known
        result['_packet_records'] = {'pts': pts, 'dts': dts, 'duration': durations, 'size': sizes}
        return result


def audit_pair(row):
    row = dict(row)
    row['errors'], row['warnings'] = [], []
    row['source_sha256'] = row['label_sha256'] = None
    row['source_bytes'] = row['label_bytes'] = None
    row['label'] = None
    row['video'] = None
    for kind in ('source', 'label'):
        path = row[kind + '_path']
        if path is None:
            row['errors'].append(issue('missing_' + kind))
            continue
        try:
            before = Path(path).stat()
            row[kind + '_bytes'] = before.st_size
            row[kind + '_sha256'] = sha256(path)
            if kind == 'label':
                data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
                row['label'] = audit_label(data, Path(row['source_path']).name if row['source_path'] else '')
                row['errors'].extend(row['label']['errors'])
                row['warnings'].extend(row['label']['warnings'])
            else:
                row['video'] = audit_video(path)
            after = Path(path).stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                row['errors'].append(issue(kind + '_changed_during_read'))
        except Exception as exc:
            row['errors'].append(issue(kind + '_read_failed', error_type=type(exc).__name__, detail=str(exc)))
    if row['scenario'] is None:
        row['errors'].append(issue('unknown_scenario'))
    video, label = row['video'], row['label']
    if video:
        for key in ('packet_pts_missing', 'packet_dts_missing', 'packet_pts_duplicate_count', 'dts_nonincreasing'):
            if video[key]:
                row['errors'].append(issue(key, count=video[key]))
    if video and label and 'info' in label and not any(e['code'].startswith(('schema', 'invalid_info')) for e in label['errors']):
        info = label['info']
        for key in ('width', 'height'):
            if info[key] != video[key]:
                row['errors'].append(issue('label_video_' + key + '_mismatch'))
        try:
            rate = Fraction(video['average_rate'])
            if float(rate) != float(info['fps']):
                row['errors'].append(issue('label_video_fps_mismatch'))
            grid_step = Fraction(1, 1) / Fraction(str(info['fps'])) / Fraction(video['time_base'])
            pts = video['_sorted_pts']
            grid_bad = sum(Fraction(p - pts[0]) != i * grid_step for i, p in enumerate(pts))
            video['label_fps_grid_mismatches'] = grid_bad
            if grid_bad:
                row['errors'].append(issue('packet_pts_off_label_fps_grid', count=grid_bad))
            if pts and pts[0] != 0:
                row['warnings'].append(issue('nonzero_pts_origin', ticks=pts[0]))
        except (ValueError, TypeError, ZeroDivisionError):
            row['errors'].append(issue('invalid_stream_rate_or_timebase'))
        if info['frame'] != video['stream_declared_frames']:
            row['errors'].append(issue('label_stream_frame_count_mismatch', label=info['frame'], stream=video['stream_declared_frames']))
        if info['frame'] != video['packet_count']:
            row['warnings'].append(issue('label_packet_count_difference', label=info['frame'], packets=video['packet_count']))
        dur = video['stream_duration_seconds']
        if dur is not None:
            video['duration_minus_label_seconds'] = dur - label['declared_duration_seconds']
            if abs(video['duration_minus_label_seconds']) > 1 / float(info['fps']) + 1e-7:
                row['warnings'].append(issue('label_video_duration_difference', seconds=video['duration_minus_label_seconds']))
        # Map each label index directly to sorted native PTS under BOTH hypotheses.
        pts, tb = video['_sorted_pts'], Fraction(video['time_base'])
        for event in label['events']:
            for origin in (0, 1):
                alternative = event['origin_alternatives'][str(origin)]
                for side in ('start', 'end'):
                    index = event[side + '_frame_declared'] - origin
                    alternative[side + '_packet_presentation_seconds'] = float(pts[index] * tb) if 0 <= index < len(pts) else None
    if video:
        del video['_sorted_pts']
    row['audit_status'] = 'error' if row['errors'] else 'ok_with_review' if row['warnings'] else 'ok'
    return row


def grouped_split(rows):
    """Conservative connected components, not shuffled frames or actor crops.

    location/day joins all possibly overlapping sessions on that day. A scenario
    repeated at the same location joins dates as a precaution. Explicit overlap
    edges retain the narrower evidence too. Content duplicates join globally.
    Cross-location duplicates/missing grouping metadata are quarantined.
    """
    parent = {row['source_id']: row['source_id'] for row in rows}
    edges, buckets, metadata = [], defaultdict(list), {}

    def find(key):
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def join(a, b, reason):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
        edges.append({'a': a, 'b': b, 'reason': reason})

    for row in rows:
        key = row['source_id']
        info = (row.get('label') or {}).get('info', {})
        try:
            location = info['location']
            if not isinstance(location, str) or not location.strip():
                raise ValueError('location')
            start = datetime.strptime(info['date_captured'], '%Y/%m/%d %H:%M:%S')
            duration = (row.get('video') or {}).get('stream_duration_seconds') or seconds(info['video_length'])
            if not math.isfinite(duration) or duration <= 0 or row['scenario'] is None:
                raise ValueError('duration/scenario')
            end = start + timedelta(seconds=duration)
            metadata[key] = {'location': location, 'start': start, 'end': end}
            # Include midnight-crossing capture on every touched calendar day.
            date = start.date()
            while date <= end.date():
                buckets[('location_day', location, date.isoformat())].append(key)
                date += timedelta(days=1)
            buckets[('scenario_location', location, str(row['scenario']))].append(key)
        except (KeyError, TypeError, ValueError, OverflowError):
            pass
        if row.get('source_sha256'):
            buckets[('exact_source_sha256', row['source_sha256'])].append(key)
    for bucket, keys in sorted(buckets.items()):
        for key in keys[1:]:
            join(keys[0], key, '|'.join(bucket))
    by_location = defaultdict(list)
    for key, meta in metadata.items():
        by_location[meta['location']].append((meta['start'], meta['end'], key))
    for location, sessions in by_location.items():
        active = []
        for start, end, key in sorted(sessions):
            active = [(e, k) for e, k in active if e >= start]
            for _, other in active:
                join(other, key, 'overlapping_capture|' + location)
            active.append((end, key))
    components = defaultdict(list)
    for row in rows:
        components[find(row['source_id'])].append(row)
    included_locations = Counter(metadata[r['source_id']]['location'] for r in rows
                                 if not r['excluded'] and r['source_id'] in metadata)
    # Count-only, deterministic site choice, independent of model outcomes.
    ordered = sorted(included_locations, key=lambda x: (included_locations[x], x))
    heldout_test = ordered[0] if len(ordered) >= 3 else None
    heldout_val = ordered[1] if len(ordered) >= 3 else None
    assignments, groups = [], []
    for members in components.values():
        ids = sorted(r['source_id'] for r in members)
        gid = 'g-' + hashlib.sha256('\n'.join(ids).encode()).hexdigest()[:16]
        locations = sorted({metadata[k]['location'] for k in ids if k in metadata})
        ambiguity = []
        if any(k not in metadata for k in ids):
            ambiguity.append('missing_or_invalid_explicit_group_metadata')
        if len(locations) != 1:
            ambiguity.append('component_has_zero_or_multiple_locations')
        if heldout_test is None:
            ambiguity.append('fewer_than_three_explicit_locations')
        proposed = 'test' if locations == [heldout_test] else 'validation' if locations == [heldout_val] else 'train'
        split = 'quarantine' if ambiguity else proposed
        groups.append({'group_id': gid, 'source_ids': ids, 'locations': locations,
                       'split': split, 'quarantine_reasons': ambiguity})
        for row in members:
            reasons = list(ambiguity)
            if row['errors']:
                reasons.append('source_or_label_audit_errors')
            assignments.append({'source_id': row['source_id'], 'source_sha256': row['source_sha256'],
                                'label_sha256': row['label_sha256'], 'group_id': gid,
                                'location': metadata.get(row['source_id'], {}).get('location'),
                                'date_captured': ((row.get('label') or {}).get('info') or {}).get('date_captured'),
                                'excluded': row['excluded'], 'group_split': split,
                                'split': 'excluded' if row['excluded'] else 'quarantine' if reasons else split,
                                'quarantine_reasons': reasons,
                                'training_eligible': False,
                                'training_blockers': ['frame_origin_unreviewed', 'binary_negative_policy_not_validated', 'actor_to_scene_label_not_validated']})
    # Defensive invariant: exact bytes can never straddle proposed non-excluded splits.
    digest_splits = defaultdict(set)
    for row in assignments:
        if row['source_sha256'] and not row['excluded']:
            digest_splits[row['source_sha256']].add(row['group_split'])
    if any(len(splits) != 1 for splits in digest_splits.values()):
        raise AssertionError('exact source duplicate crossed splits')
    return {'schema_version': VERSION, 'status': 'grouping_proposal_not_training_approval',
            'policy': ['explicit_location_and_capture_date', 'same_location_calendar_day_conservative',
                       'same_scenario_same_location_across_dates_conservative', 'overlapping_capture_including_endpoints',
                       'exact_source_sha256_global', 'missing_metadata_or_cross_location_components_quarantined'],
            'test_location': heldout_test, 'validation_location': heldout_val,
            'site_selection': 'smallest_included_source_count_then_location_name; independent_of_class_and_model_outcomes',
            'assignments': sorted(assignments, key=lambda x: x['source_id']),
            'groups': sorted(groups, key=lambda x: x['group_id']), 'connections': edges}


def summarize(rows, split, elapsed):
    included = [r for r in rows if not r['excluded']]
    summary = {'inventory_pairs_or_orphans': len(rows), 'excluded': len(rows) - len(included),
               'included': len(included), 'elapsed_seconds': elapsed,
               'pair_counts': dict(Counter('paired' if r['source_path'] and r['label_path'] else 'source_only' if r['source_path'] else 'label_only' for r in rows)),
               'source_bytes': sum(r['source_bytes'] or 0 for r in rows),
               'sources_hashed': sum(bool(r['source_sha256']) for r in rows),
               'labels_hashed': sum(bool(r['label_sha256']) for r in rows),
               'videos_demuxed': sum(r['video'] is not None for r in rows),
               'frames_decoded_by_audit': 0, 'training_eligible_sources': 0,
               'training_negative_labels_created': 0,
               'split_counts': dict(Counter(a['split'] for a in split['assignments'])),
               'test_location': split['test_location'], 'validation_location': split['validation_location'],
               'groups': len(split['groups']), 'by_scope': {}}
    for scope, selected in [('all', rows), ('included', included), ('excluded', [r for r in rows if r['excluded']])]:
        loc = defaultdict(lambda: {'sources': 0, 'events': Counter(), 'annotation_boxes': Counter()})
        errors, warnings, events, boxes = Counter(), Counter(), Counter(), Counter()
        deltas = {'0': {'start': Counter(), 'end': Counter()}, '1': {'start': Counter(), 'end': Counter()}}
        for row in selected:
            errors.update(e['code'] for e in row['errors'])
            warnings.update(w['code'] for w in row['warnings'])
            label = row.get('label') or {}
            events.update(label.get('event_classes', {}))
            boxes.update(label.get('annotation_classes', {}))
            location = label.get('info', {}).get('location', 'unknown')
            loc[location]['sources'] += 1
            loc[location]['events'].update(label.get('event_classes', {}))
            loc[location]['annotation_boxes'].update(label.get('annotation_classes', {}))
            for event in label.get('events', []):
                for origin in ('0', '1'):
                    for side in ('start', 'end'):
                        delta = round(event['origin_alternatives'][origin][side + '_minus_declared_seconds'], 6)
                        deltas[origin][side][str(delta)] += 1
        summary['by_scope'][scope] = {'errors': dict(errors), 'warnings': dict(warnings),
            'sources_with_errors': sum(bool(r['errors']) for r in selected),
            'event_classes': dict(events), 'annotation_classes': dict(boxes), 'locations': dict(loc),
            'event_time_frame_deltas_seconds': deltas}
    source_dups, label_dups = defaultdict(list), defaultdict(list)
    for row in rows:
        if row['source_sha256']:
            source_dups[row['source_sha256']].append(row['source_id'])
        if row['label_sha256']:
            label_dups[row['label_sha256']].append(row['source_id'])
    summary['exact_source_duplicates'] = {k: v for k, v in source_dups.items() if len(v) > 1}
    summary['exact_label_duplicates'] = {k: v for k, v in label_dups.items() if len(v) > 1}
    return summary


def run_audit(args):
    import av
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'manifest.jsonl').exists() or (output / 'summary.json').exists():
        raise ValueError('refusing to overwrite a prior audit; use a new output directory')
    started, start_clock = datetime.now(timezone.utc).isoformat(), time.monotonic()
    inputs = inventory(args.base)
    write_jsonl(output / 'inventory.jsonl', inputs)
    rows = []
    with (output / 'manifest.partial.jsonl').open('w') as partial, (output / 'packet-pts.jsonl').open('w') as packet_file:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            for index, row in enumerate(executor.map(audit_pair, inputs), 1):
                if row['video']:
                    records = row['video'].pop('_packet_records')
                    packet_file.write(json.dumps({'source_id': row['source_id'], 'time_base': row['video']['time_base'], **records}) + '\n')
                    packet_file.flush()
                rows.append(row)
                partial.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
                partial.flush()
                if index % 25 == 0 or index == len(inputs):
                    print(json.dumps({'completed': index, 'total': len(inputs), 'elapsed_seconds': round(time.monotonic() - start_clock, 1)}), flush=True)
    (output / 'manifest.partial.jsonl').rename(output / 'manifest.jsonl')
    split = grouped_split(rows)
    split.update(created_at=datetime.now(timezone.utc).isoformat(),
                 source_manifest_sha256=sha256(output / 'manifest.jsonl'),
                 packet_pts_sha256=sha256(output / 'packet-pts.jsonl'))
    # This file is saved BEFORE the overlay command can open a decoder.
    write_json(output / 'split-manifest.json', split)
    write_jsonl(output / 'exclusions.jsonl', [r for r in rows if r['excluded']])
    write_jsonl(output / 'errors.jsonl', [{'source_id': r['source_id'], 'excluded': r['excluded'], 'errors': r['errors'], 'warnings': r['warnings']} for r in rows if r['errors'] or r['warnings']])
    write_jsonl(output / 'events.jsonl', [{'source_id': r['source_id'], 'excluded': r['excluded'], **event} for r in rows for event in (r.get('label') or {}).get('events', [])])
    summary = summarize(rows, split, time.monotonic() - start_clock)
    summary.update(schema_version=VERSION, started_at=started, completed_at=datetime.now(timezone.utc).isoformat(),
                   source_base=str(Path(args.base).resolve()), argv=sys.argv, python=platform.python_version(), pyav=av.__version__,
                   git_head=args.code_sha, script_sha256=sha256(Path(__file__)),
                   manifest_sha256=sha256(output / 'manifest.jsonl'), split_manifest_sha256=sha256(output / 'split-manifest.json'),
                   packet_pts_sha256=sha256(output / 'packet-pts.jsonl'),
                   limitations=['Demux packet count is not a decoded-frame census.',
                                'Frame-index origin unresolved; native packet PTS mapped under both hypotheses.',
                                'Explicit actor non-wall_over events do not certify scene-wide negative clips.',
                                'Unannotated times/persons are unknown, never negative.',
                                'Hashes identify byte-identical files only; transformed duplicates are not ruled out.',
                                'Capture clocks and location strings are supplied labels, not independently verified.',
                                'No training or quality/generalization metrics produced.'])
    write_json(output / 'summary.json', summary)
    print(json.dumps({k: summary[k] for k in ('included', 'excluded', 'sources_hashed', 'videos_demuxed', 'split_counts')}, ensure_ascii=False), flush=True)


def verify_regression_lock(output, lock_path):
    """Compare action source bytes with the coordinator's read-only baseline lock."""
    output, lock_path = Path(output), Path(lock_path)
    lock = json.loads(lock_path.read_text())
    sources = lock.get('regression_only_videos')
    if not isinstance(sources, list) or len(sources) != 45 or any(not v.get('sha256') for v in sources):
        raise ValueError('expected 45 SHA-bound regression-only videos in baseline lock')
    rows = [json.loads(line) for line in (output / 'manifest.jsonl').read_text().splitlines()]
    split = json.loads((output / 'split-manifest.json').read_text())
    if split['source_manifest_sha256'] != sha256(output / 'manifest.jsonl'):
        raise ValueError('source manifest differs from saved split')
    by_hash = defaultdict(list)
    for video in sources:
        by_hash[video['sha256']].append(video['video_id'])
    overlaps = [{'source_id': row['source_id'], 'excluded': row['excluded'],
                 'source_sha256': row['source_sha256'], 'regression_video_ids': by_hash[row['source_sha256']]}
                for row in rows if row['source_sha256'] in by_hash]
    result = {'status': 'blocked_exact_regression_overlap' if overlaps else 'no_exact_byte_overlap',
              'baseline_lock_path': str(lock_path), 'baseline_lock_sha256': sha256(lock_path),
              'source_manifest_sha256': sha256(output / 'manifest.jsonl'),
              'split_manifest_sha256': sha256(output / 'split-manifest.json'),
              'regression_videos': len(sources), 'action_sources': len(rows),
              'action_sources_with_sha256': sum(bool(r['source_sha256']) for r in rows),
              'overlaps': overlaps, 'scope': 'exact_bytes_only_no_transformed_duplicate_or_scene_semantic_certification'}
    write_json(output / 'regression-overlap.json', result)
    if overlaps:
        raise ValueError('regression-only source overlap; stop samples/training and quarantine through coordinator')


def save_event_statistics(output):
    """Summarize label-native spans, without converting them to training clips."""
    from statistics import median
    output = Path(output)
    rows = [json.loads(line) for line in (output / 'manifest.jsonl').read_text().splitlines()]
    split = json.loads((output / 'split-manifest.json').read_text())
    if split['source_manifest_sha256'] != sha256(output / 'manifest.jsonl'):
        raise ValueError('statistics require the saved matching source/split manifests')
    groups = {r['source_id']: r for r in split['assignments']}
    classes, explicit_other = defaultdict(list), []
    for row in rows:
        if row['excluded']:
            continue
        label = row.get('label') or {}
        fps = float(label.get('info', {}).get('fps', 0))
        if not fps:
            continue
        for event in label.get('events', []):
            start, end = event['start_frame_declared'], event['end_frame_declared']
            n = max(0, end - start + 1)
            core = max(0, end - start)
            item = {'source_id': row['source_id'], 'group_id': groups[row['source_id']]['group_id'],
                    'split': groups[row['source_id']]['split'], 'location': label['info']['location'],
                    'event_index': event['event_index'], 'actor_id': event['actor_id'], 'object_id': event['object_id'],
                    'class_name': event['class_name'], 'declared_start_frame': start, 'declared_end_frame': end,
                    'native_frame_count_inclusive': n, 'native_frame_span_seconds': (end - start) / fps,
                    'both_origin_intersection_decoded_indices_inclusive': [start, end - 1] if core else None,
                    'both_origin_intersection_frame_count': core,
                    'both_origin_intersection_span_seconds': max(0, end - start - 1) / fps,
                    'training_label': None}
            classes[event['class_name']].append(item)
            if event['class_name'] != 'wall_over':
                overlaps = [other['event_index'] for other in label.get('events', [])
                            if other['class_name'] == 'wall_over' and
                            other['start_frame_declared'] <= end and other['end_frame_declared'] >= start]
                item['overlapping_declared_wall_over_event_indices'] = overlaps
                # Even no overlap is not independent semantic verification.
                item['scene_negative_certified'] = False
                explicit_other.append(item)
    duration_summary = {}
    for name, events in classes.items():
        spans = sorted(e['native_frame_span_seconds'] for e in events)
        duration_summary[name] = {'events': len(events), 'source_files': len({e['source_id'] for e in events}),
            'scene_groups': len({e['group_id'] for e in events}), 'locations': dict(Counter(e['location'] for e in events)),
            'span_seconds': {'minimum': min(spans), 'median': median(spans), 'maximum': max(spans)},
            'inclusive_native_frame_count_histogram': dict(sorted(Counter(e['native_frame_count_inclusive'] for e in events).items())),
            'at_least_8_native_frames': sum(e['native_frame_count_inclusive'] >= 8 for e in events),
            'at_least_16_native_frames': sum(e['native_frame_count_inclusive'] >= 16 for e in events),
            'both_origin_intersection_at_least_8_frames': sum(e['both_origin_intersection_frame_count'] >= 8 for e in events),
            'both_origin_intersection_at_least_16_frames': sum(e['both_origin_intersection_frame_count'] >= 16 for e in events)}
    write_json(output / 'event-statistics.json', {'source_manifest_sha256': sha256(output / 'manifest.jsonl'),
        'split_manifest_sha256': sha256(output / 'split-manifest.json'), 'by_class': duration_summary,
        'explicit_non_wall_actor_events': explicit_other,
        'label_origin_status': 'quarantined_unresolved_0_or_1_based',
        'intersection_policy_status': 'hypothetical_label_native_reference_not_approved_training_labels',
        'negative_labels_created': 0})


def build_overlays(args):
    """Write local JPEG contact sheets without sending raw media to any tool."""
    import av
    from PIL import Image, ImageDraw
    output = Path(args.output)
    split_path = output / 'split-manifest.json'
    split = json.loads(split_path.read_text())  # Must already exist before decode.
    if split['source_manifest_sha256'] != sha256(output / 'manifest.jsonl'):
        raise ValueError('manifest no longer matches saved split')
    if split['packet_pts_sha256'] != sha256(output / 'packet-pts.jsonl'):
        raise ValueError('packet PTS no longer match saved split')
    rows = [json.loads(line) for line in (output / 'manifest.jsonl').read_text().splitlines()]
    assignments = {r['source_id']: r for r in split['assignments']}
    valid = [r for r in rows if not r['excluded'] and r['source_path'] and r['label'] and r['label']['events']
             and any(e['matching_box_count'] for e in r['label']['events'])]
    chosen = []
    # Four places, prefer a stand example when available; then multi-actor and bounds.
    for location in sorted({r['label']['info']['location'] for r in valid}):
        site = [r for r in valid if r['label']['info']['location'] == location]
        chosen.append(next((r for r in site if 'stand' in r['label']['event_classes']), site[0]))
    multi = next((r for r in valid if len({e['actor_id'] for e in r['label']['events']}) > 1 and r not in chosen), None)
    bounds = next((r for r in valid if any(e['code'] in ('bbox_bounds', 'annotation_frame_out_of_range', 'event_frame_out_of_range')
                                          for e in r['errors']) and r not in chosen), None)
    for extra in (multi, bounds):
        if extra and extra not in chosen:
            chosen.append(extra)
    # Include the long stand / concurrent-climbing context when distinct and bounded.
    long_stand = next((r for r in valid if r not in chosen and any(e['class_name'] == 'stand' and
                       e['end_frame_declared'] - e['start_frame_declared'] > 30 for e in r['label']['events'])), None)
    if long_stand and len(chosen) < 6:
        chosen.append(long_stand)
    selection_path = getattr(args, 'overlay_selection', None)
    selections = {}
    if selection_path:
        selections = {r['source_id']: r['event_index'] for r in json.loads(Path(selection_path).read_text())}
        by_id = {r['source_id']: r for r in valid}
        chosen = [by_id[key] for key in selections]
        if any(r['errors'] for r in chosen):
            raise ValueError('Explicit overlay selection contains quarantined data')
        multi = bounds = None
    sample_dir = output / 'overlays'
    sample_dir.mkdir(exist_ok=False)
    evidence = []
    for sample_index, row in enumerate(chosen):
        if sha256(row['label_path']) != row['label_sha256']:
            raise ValueError('label changed since split')
        # Full source hash recheck keeps overlays bound to the saved original bytes.
        if sha256(row['source_path']) != row['source_sha256']:
            raise ValueError('source changed since split')
        label = json.loads(Path(row['label_path']).read_text())
        event = next((e for e in row['label']['events'] if e['class_name'] == 'stand' and e['matching_box_count']),
                     next(e for e in row['label']['events'] if e['matching_box_count']))
        if row['source_id'] in selections:
            event = next(e for e in row['label']['events'] if e['event_index'] == selections[row['source_id']])
        if bounds is row:
            suspect = next((a for a in label['annotations'] if a.get('bbox') and
                            not (0 <= a['bbox'][0][0] < a['bbox'][1][0] <= label['info']['width'] and
                                 0 <= a['bbox'][0][1] < a['bbox'][1][1] <= label['info']['height'])), None)
            if suspect:
                event = next((e for e in row['label']['events'] if e['actor_id'] == suspect['actor_id'] and
                              e['object_id'] == suspect['object_id'] and e['start_frame_declared'] <= suspect['cur_frame'] <= e['end_frame_declared']), event)
        annotation = next((a for a in label['annotations'] if a['actor_id'] == event['actor_id'] and a['object_id'] == event['object_id'] and a['cur_frame'] == event['start_frame_declared']), None)
        if annotation is None:
            annotation = next(a for a in label['annotations'] if a['actor_id'] == event['actor_id'] and a['object_id'] == event['object_id'] and event['start_frame_declared'] <= a['cur_frame'] <= event['end_frame_declared'])
        if bounds is row and suspect:
            annotation = suspect
        label_frame = annotation['cur_frame']
        context_start, context_end = event['start_frame_declared'], event['end_frame_declared']
        if multi is row:
            context_start = min(e['start_frame_declared'] for e in row['label']['events'])
            context_end = max(e['end_frame_declared'] for e in row['label']['events'])
        first_label = max(0, context_start - 12)
        last_label = min(label['info']['frame'], context_end + 12)
        targets = {frame - origin for frame in range(first_label, last_label + 1) for origin in (0, 1)
                   if 0 <= frame - origin < label['info']['frame']}
        decoded = {}
        with av.open(row['source_path']) as container:
            for index, frame in enumerate(container.decode(video=0)):
                if index in targets:
                    decoded[index] = (frame.to_image(), float(frame.pts * frame.time_base) if frame.pts is not None else None)
                if index >= max(targets):
                    break
        canvas = Image.new('RGB', (1280, 410), (20, 20, 20))
        panels = []
        for origin in (0, 1):
            index = label_frame - origin
            if index not in decoded:
                continue
            original, pts = decoded[index]
            panel = original.resize((640, 360))
            draw = ImageDraw.Draw(panel)
            (x1, y1), (x2, y2) = annotation['bbox']
            draw.rectangle((x1 * 640 / original.width, y1 * 360 / original.height,
                            x2 * 640 / original.width, y2 * 360 / original.height), outline='red', width=3)
            canvas.paste(panel, (origin * 640, 50))
            ImageDraw.Draw(canvas).text((origin * 640 + 8, 8), f'UNREVIEWED origin={origin} label={label_frame} decoded_index={index}\nPTS={pts} actor={event["actor_id"]} class={event["class_name"]}', fill='white')
            panels.append({'origin_hypothesis': origin, 'decoded_frame_index_zero_based': index, 'native_pts_seconds': pts})
        target = sample_dir / f'{sample_index:02d}-origin-alternatives.jpg'
        canvas.save(target, quality=90)
        # Dual origin videos use one declared-label frame per presentation step.
        # Every available actor box at that label frame is shown, not just the selected actor.
        video_target = sample_dir / f'{sample_index:02d}-origin-alternatives.mp4'
        video_frames = 0
        by_frame = defaultdict(list)
        for box in label['annotations']:
            by_frame[box['cur_frame']].append(box)
        video_presentations = []
        with av.open(str(video_target), 'w') as output_video:
            stream = output_video.add_stream('libx264', rate=Fraction(str(label['info']['fps'])))
            stream.width, stream.height, stream.pix_fmt = 1280, 410, 'yuv420p'
            stream.options = {'crf': '23', 'preset': 'fast', 'movflags': '+faststart'}
            for declared_frame in range(first_label, last_label + 1):
                contact = Image.new('RGB', (1280, 410), (20, 20, 20))
                present = []
                for origin in (0, 1):
                    index = declared_frame - origin
                    if index not in decoded:
                        ImageDraw.Draw(contact).text((origin * 640 + 8, 8),
                            f'UNREVIEWED origin={origin} label={declared_frame}\nOUT OF SOURCE BOUNDS under this hypothesis', fill='white')
                        present.append({'origin_hypothesis': origin, 'decoded_index_zero_based': index,
                                        'native_pts_seconds': None, 'source_bounds_compatible': False})
                        continue
                    original, pts = decoded[index]
                    panel = original.resize((640, 360))
                    draw = ImageDraw.Draw(panel)
                    for box in by_frame[declared_frame]:
                        try:
                            (x1, y1), (x2, y2) = box['bbox']
                            if not all(math.isfinite(x) for x in (x1, y1, x2, y2)) or x1 >= x2 or y1 >= y2:
                                continue
                            draw.rectangle((x1 * 640 / original.width, y1 * 360 / original.height,
                                            x2 * 640 / original.width, y2 * 360 / original.height), outline='red', width=3)
                            draw.text((max(0, x1 * 640 / original.width), max(0, y1 * 360 / original.height - 12)),
                                      f'{box["class_name"]} actor={box["actor_id"]} obj={box["object_id"]}', fill='yellow')
                        except (ValueError, TypeError, KeyError):
                            continue
                    contact.paste(panel, (origin * 640, 50))
                    ImageDraw.Draw(contact).text((origin * 640 + 8, 8),
                        f'UNREVIEWED origin={origin} label={declared_frame} decoded_index={index}\nPTS={pts} all actor boxes; no boxes = UNKNOWN', fill='white')
                    present.append({'origin_hypothesis': origin, 'decoded_index_zero_based': index,
                                    'native_pts_seconds': pts, 'source_bounds_compatible': True})
                frame = av.VideoFrame.from_image(contact)
                for packet in stream.encode(frame):
                    output_video.mux(packet)
                video_frames += 1
                video_presentations.append({'label_frame': declared_frame, 'panels': present})
            for packet in stream.encode():
                output_video.mux(packet)
        evidence.append({'source_id': row['source_id'], 'source_sha256': row['source_sha256'],
                         'group_id': assignments[row['source_id']]['group_id'], 'split': assignments[row['source_id']]['split'],
                         'sample_path': str(target), 'sample_sha256': sha256(target), 'label_frame': label_frame,
                         'actor_id': event['actor_id'], 'object_id': event['object_id'], 'event_class': event['class_name'],
                         'annotation_bbox': annotation['bbox'], 'panels': panels, 'human_review_status': 'pending',
                         'frame_origin_asserted': False, 'training_label': None,
                         'video_path': str(video_target), 'video_sha256': sha256(video_target),
                         'video_frames': video_frames, 'video_fps': label['info']['fps'],
                         'video_presentations': video_presentations,
                         'selected_event_declared_start_frame': event['start_frame_declared'],
                         'selected_event_declared_end_frame': event['end_frame_declared'],
                         'selected_event_declared_start_seconds': event['start_time_declared'],
                         'selected_event_declared_end_seconds': event['end_time_declared'],
                         'context_label_frame_start': first_label, 'context_label_frame_end': last_label,
                         'pre_post_context_label_status': 'UNKNOWN_no_negative_inference',
                         'review_reasons': ['both_frame_origin_hypotheses', 'declared_actor_box_alignment',
                                           'out_of_bounds' if bounds is row else 'multi_actor' if multi is row else 'site_and_class_example']})
    write_json(output / 'overlay-manifest.json', {'created_at': datetime.now(timezone.utc).isoformat(),
                'split_manifest_sha256': sha256(split_path), 'samples': evidence,
                'purpose': 'local_only_actor_box_and_frame_origin_review_not_training', 'media_uploaded': False})
    print(json.dumps({'local_overlay_sources': len(evidence), 'local_panels': sum(len(e['panels']) for e in evidence)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=BASE)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--workers', type=int, default=2, choices=range(1, 5))
    parser.add_argument('--code-sha', default='unrecorded')
    parser.add_argument('--overlays-only', action='store_true')
    parser.add_argument('--overlay-selection', type=Path)
    parser.add_argument('--statistics-only', action='store_true')
    parser.add_argument('--verify-regression-lock', type=Path)
    args = parser.parse_args()
    if args.verify_regression_lock:
        verify_regression_lock(args.output, args.verify_regression_lock)
    elif args.statistics_only:
        save_event_statistics(args.output)
    elif args.overlays_only:
        build_overlays(args)
    else:
        run_audit(args)


if __name__ == '__main__':
    main()
