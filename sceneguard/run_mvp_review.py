"""EXP-0030 current-region CPU MVP: immutable measurements -> review feed/media.

Freeze and independently review before executing once. There is no detector,
tracker, encoder, relinking, old-region control, or parameter tuning path.
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import time

from .mvp_review_candidates import make_feed
from .mvp_review_quality import QualitySettings, quality_diagnostics, question_audit
from .run_tracklet_linking import (REID_SHA, endpoint_rows, load_inputs, read_jsonl,
                                   sha256, validate_features, write_json)
from .tracklet_linking import LinkSettings, region_events, validate_zones


REGION_BINDING = Path('runtime/EXP-0030/current-regions.json')
OUTPUT = Path('outputs/exp0030/current-v1')
REGION_PATHS = {
    '030': 'outputs/exp0029_region_review/030-inside-user-v1/regions030-inside-expanded.json',
    '007': 'runtime/EXP-0029/regions007.json',
}
SOURCE_FILES = ['sceneguard/run_mvp_review.py', 'sceneguard/mvp_review_quality.py',
                'sceneguard/mvp_review_candidates.py', 'sceneguard/run_tracklet_linking.py',
                'sceneguard/tracklet_linking.py', 'sceneguard/mvp_review_evidence.py']


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def input_spec(key):
    cache = 'outputs/cv_phase2d/cache030' if key == '030' else 'outputs/exp0029/cache007'
    tracking = ('outputs/exp0028/practical-v1/track030/gap' if key == '030'
                else 'outputs/exp0029/replay007/gap')
    prior = f'outputs/exp0029/track{key}/v1'
    return dict(key=key, video_id=f'E01_{key}', start=84. if key == '030' else 48.,
                end=100. if key == '030' else 105., expected_frames=480 if key == '030' else 1710,
                cache=cache, tracks=f'{tracking}/frames.jsonl', gap_events=f'{tracking}/events.jsonl',
                video=f'data/TS_침입/E01_{key}.mp4',
                tracklets=f'{prior}/tracklets.json', associations=f'{prior}/associations.json',
                features=f'{prior}/features.local.json', representatives=f'{prior}/representatives.json',
                summary=f'{prior}/summary.json', representative_directory=f'{prior}/representatives',
                regions=REGION_PATHS[key])


def validate_saved_observations(cached, tracked, segments, associations, representatives, settings):
    """Verify saved tracklets partition actual observed rows without regenerating them."""
    expected = {}
    for index, frame in enumerate(tracked):
        seen = set()
        for row in frame['detections']:
            if not row.get('observed', False) or not row.get('confirmed', True):
                continue
            raw = row['track_id']
            if type(raw) is not int or raw in seen:
                raise ValueError('Repeated or invalid measured raw ID')
            seen.add(raw)
            expected[(index, raw)] = dict(frame_index=index, pts=frame['pts'], raw_id=raw,
                bbox=row['bbox'], score=row['score'], cache_index=row['cache_index'])
    consumed, by_id = set(), {}
    for segment in segments:
        sid, rows = segment['id'], segment['rows']
        if sid in by_id or not rows:
            raise ValueError('Duplicate or empty saved tracklet')
        by_id[sid] = segment
        if (segment['start'] != rows[0]['pts'] or segment['end'] != rows[-1]['pts']
                or segment['observations'] != len(rows)):
            raise ValueError('Tracklet summary disagrees with saved observations')
        eligible = len(rows) >= settings.min_observations and segment['end']-segment['start']+1e-9 >= settings.min_span_seconds
        if segment['eligible'] != eligible:
            raise ValueError('Saved tracklet eligibility mismatch')
        previous = -math.inf
        for row in rows:
            key = row['frame_index'], row['raw_id']
            if (key in consumed or expected.get(key) != row or row['raw_id'] != segment['raw_id']
                    or row['pts'] <= previous):
                raise ValueError('Saved tracklets must retain each real observed row exactly once')
            consumed.add(key)
            previous = row['pts']
    if consumed != set(expected):
        raise ValueError('Saved tracklets omit observed rows')
    selections = {s['id']: {end: endpoint_rows(s, end, settings) for end in ('head', 'tail')}
                  for s in segments if s['eligible']}
    if selections != representatives:
        raise ValueError('Saved representative selections do not match immutable tracklet rows')
    mapping, chain_ids, chain_edges = {}, set(), set()
    for chain in associations['chains']:
        if chain['id'] in chain_ids or not chain['segments']:
            raise ValueError('Duplicate/empty saved chain')
        chain_ids.add(chain['id'])
        for sid in chain['segments']:
            if sid not in by_id or sid in mapping:
                raise ValueError('Saved chain partition mismatch')
            mapping[sid] = chain['id']
        for before, after in zip(chain['segments'], chain['segments'][1:]):
            if by_id[after]['start'] <= by_id[before]['end']:
                raise ValueError('Concurrent saved chain segments')
            chain_edges.add((before, after))
    accepted = {(r['before'], r['after']) for r in associations['links'] if r['status'] == 'accepted'}
    if mapping != associations['mapping'] or set(mapping) != set(by_id) or accepted != chain_edges:
        raise ValueError('Accepted original links and chain mapping disagree')
    return selections


def load_video_inputs(spec, region_binding):
    meta, cached, tracked, interval, hashes = load_inputs(spec['cache'], spec['tracks'], spec['video'])
    if (meta['video_id'] != spec['video_id'] or len(cached) != spec['expected_frames']
            or abs(cached[0]['pts']-spec['start']) > 1e-9
            or abs(cached[-1]['pts']+interval-spec['end']) > 1e-6):
        raise ValueError('Expected exact current MVP window and native frame count')
    summary = load_json(spec['summary'])
    saved = load_json(spec['features'])
    segments, associations = load_json(spec['tracklets']), load_json(spec['associations'])
    representatives = load_json(spec['representatives'])
    settings = LinkSettings(**associations['settings']).validate()
    expected_binding = dict(inputs=hashes, weights=REID_SHA, settings=asdict(settings))
    if (summary['status'] != 'complete' or summary['source_hashes'] != hashes
            or summary['settings'] != asdict(settings) or summary['frames'] != len(cached)
            or saved['binding'] != expected_binding):
        raise ValueError('Saved EXP29 artifacts belong to other source/cache/settings/weights')
    selections = validate_saved_observations(cached, tracked, segments, associations, representatives, settings)
    validate_features(saved['features'], selections)
    if any(len(feature) != 512 for pair in saved['features'].values() for values in pair.values() for feature in values):
        raise ValueError('Expected saved 512-dimensional embeddings')
    binding = region_binding[spec['key']]
    if binding['path'] != REGION_PATHS[spec['key']] or spec['regions'] != binding['path']:
        raise ValueError('Use exactly the user-approved current region path')
    zones = validate_zones(load_json(spec['regions']))
    if (sha256(spec['regions']) != binding['sha256'] or binding['source_sha256'] != hashes['video']
            or zones['source_sha256'] != hashes['video'] or zones['source_size'] != cached[0]['source_size']):
        raise ValueError('Current region SHA/source/dimensions mismatch')
    gap_events = read_jsonl(spec['gap_events'])
    for event in gap_events:
        if (event['video_id'] != spec['video_id'] or not spec['start'] <= event['emitted_at_pts'] < spec['end']
                or not spec['start'] <= event['candidate_pts'] <= event['emitted_at_pts']
                or not all(math.isfinite(event[k]) for k in ('candidate_pts', 'emitted_at_pts'))):
            raise ValueError('Original gap event timing/video mismatch')
    return dict(meta=meta, cached=cached, tracked=tracked, interval=interval, hashes=hashes,
                segments=segments, associations=associations, saved_features=saved,
                representatives=representatives, settings=settings, zones=zones, gap_events=gap_events)


def snapshot_files(specs):
    paths = [REGION_BINDING, Path('runtime/EXP-0029/regions030.json')]
    for spec in specs:
        paths.extend(Path(spec[k]) for k in ('tracks', 'video', 'gap_events', 'tracklets', 'associations',
                                             'features', 'representatives', 'summary', 'regions'))
        paths.extend(Path(spec['cache'])/name for name in ('run.json', 'person_cache.jsonl'))
        paths.extend(sorted(Path(spec['representative_directory']).glob('*.jpg')))
    return {str(p): sha256(p) for p in sorted(set(paths))}


def verify_hashes(hashes):
    for path, expected in hashes.items():
        if sha256(path) != expected:
            raise ValueError(f'Frozen file changed: {path}')


def freeze(manifest):
    """Read-only input preflight; creates no feed/events or region comparisons."""
    specs = [input_spec(key) for key in ('030', '007')]
    bindings = load_json(REGION_BINDING)
    for spec in specs:
        load_video_inputs(spec, bindings)
    inputs = snapshot_files(specs)
    protected = load_json('runtime/EXP-0030/protected-files.json')
    for path, digest in inputs.items():
        if path in protected and protected[path] != digest:
            raise ValueError(f'Input differs from coordinator preservation snapshot: {path}')
    frozen = dict(schema=1, experiment_id='EXP-0030', created_utc=utc_now(),
                  status='frozen_requires_preflight_review_before_execute', specs=specs,
                  input_sha256=inputs, source_sha256={p: sha256(p) for p in SOURCE_FILES},
                  quality_settings=asdict(QualitySettings()), region_mode='current_only_no_control',
                  detector_calls=0, tracker_calls=0, encoder_calls=0, output=str(OUTPUT))
    write_json(manifest, frozen)
    return frozen


def enrich_feed(feed, data, spec, output_utc):
    available = data['cached'][-1]['pts']
    # make_feed sorts globally; source-specific IDs still retain original input order.
    originals = {f'line-{i+1:04d}': e for i, e in enumerate(data['gap_events'])}
    region_originals = {f'region-{i+1:04d}': e for i, e in enumerate(data['region_events'])}
    for event in feed['events']:
        if event['source'] == 'existing_gap_line':
            original = originals[event['id']]
            at = original['candidate_pts']
            original_emitted = original['emitted_at_pts']
            interval = original['candidate_interval']
            matches = [s['id'] for s in data['segments'] if s['raw_id'] == original['track_id']
                       and any(interval[0]-1e-9 <= r['pts'] <= original_emitted+1e-9 for r in s['rows'])]
            event.update(original_event=original, tracklet_ids=matches,
                associated_chain_ids=sorted({data['associations']['mapping'][sid] for sid in matches}),
                original_emitted_at_pts=original_emitted)
        else:
            original = region_originals[event['id']]
            interval = original['candidate_interval']
            at = sum(interval)/2
            event.update(original_event=original, original_emitted_at_pts=None,
                         region_confirmed_at_pts=original['confirmed_at'],
                         tracklet_ids=[original['before_segment'], original['after_segment']],
                         associated_chain_ids=[original['chain_id']])
        event.update(estimated_at_pts=at, estimated_interval_pts=interval,
                     available_after_pts=available, output_utc=output_utc,
                     output_utc_scope='feed_prepared_not_media_available',
                     review_status='needs_review', legal_status='unknown')
    feed.update(available_after_pts=available, output_utc=output_utc, feed_prepared_utc=output_utc,
                output_utc_scope='feed_prepared_not_media_available', mode='offline_cpu_saved_observations',
                region_sha256=sha256(spec['regions']),
                original_associations=data['associations'],
                question_audit=question_audit(spec['key'], data['segments'], data['associations'],
                                              data['saved_features'], feed),
                input_quality=quality_diagnostics(data['cached'], data['tracked'], data['segments'],
                                                  data['saved_features'], data['representatives']),
                user_context=([dict(pts=56.7, observation='approach_not_actual_climb',
                                    source='previous_user_observation', algorithm_detection=False)]
                              if spec['key'] == '007' else []))
    suggestions = feed['link_suggestions']
    feed['linkage_counts'] = dict(
        automatic_same_raw_id_gap=sum(r['status'] == 'auto_associated_unverified'
            and r['before_raw_id'] == r['after_raw_id'] for r in suggestions),
        automatic_different_raw_ids=sum(r['status'] == 'auto_associated_unverified'
            and r['before_raw_id'] != r['after_raw_id'] for r in suggestions),
        review_different_raw_ids=sum(r['status'] == 'possible_match_needs_review'
            and r['before_raw_id'] != r['after_raw_id'] for r in suggestions),
        q_pairs_outside_time_limit_audit_only=sum(q['status'] == 'outside_original_time_limit_audit_only'
                                                for q in feed['question_audit']))
    return feed


def execute(manifest, renderer=None):
    frozen = load_json(manifest)
    if (frozen['specs'] != [input_spec(key) for key in ('030', '007')]
            or frozen['quality_settings'] != asdict(QualitySettings()) or frozen['output'] != str(OUTPUT)
            or frozen['region_mode'] != 'current_only_no_control'
            or set(frozen['source_sha256']) != set(SOURCE_FILES)):
        raise ValueError('Frozen run configuration mismatch')
    verify_hashes(frozen['source_sha256'])
    verify_hashes(frozen['input_sha256'])
    # Validate both videos before reserving outputs or computing any candidates.
    bindings = load_json(REGION_BINDING)
    loaded = [load_video_inputs(spec, bindings) for spec in frozen['specs']]
    if renderer is None:
        from .mvp_review_evidence import render_review_bundle
        renderer = render_review_bundle
    if OUTPUT.exists() or OUTPUT.is_symlink() or any(p.is_symlink() for p in OUTPUT.parents):
        raise FileExistsError('EXP0030 outputs must be new, with no symlink parents')
    OUTPUT.mkdir(parents=True, exist_ok=False)
    started, output_utc = time.perf_counter(), utc_now()
    receipt = dict(experiment_id='EXP-0030', status='running', started_utc=output_utc,
                   manifest_sha256=sha256(manifest), frames=0, videos=[],
                   detector_calls=0, tracker_calls=0, encoder_calls=0,
                   polygon_comparisons=0, identity_verified=False, physical_climb_completion='unknown')
    try:
        for spec, data in zip(frozen['specs'], loaded):
            output = OUTPUT/f'track{spec["key"]}'
            output.mkdir(exist_ok=False)
            run_started = time.perf_counter()
            data['region_events'] = region_events(data['segments'], data['associations'], data['zones'],
                data['interval'], max_gap_seconds=data['settings'].max_gap_seconds,
                available_after_pts=data['cached'][-1]['pts'])
            feed = make_feed(video_id=spec['video_id'], start=spec['start'], end=spec['end'],
                gap_events=data['gap_events'], associations=data['associations'], tracklets=data['segments'],
                saved_features=data['saved_features'], current_region_events=data['region_events'])
            enrich_feed(feed, data, spec, utc_now())
            write_json(output/'region-events.json', data['region_events'])
            write_json(output/'feed.json', feed)
            write_json(output/'quality-diagnostics.json', feed['input_quality'])
            write_json(output/'question-audit.json', feed['question_audit'])
            render_receipt = renderer(Path(spec['video']), data['cached'], data['tracked'], data['segments'],
                                      data['associations'], feed, data['zones'], output)
            media_available_utc = utc_now()
            write_json(output/'render-receipt.json', render_receipt)
            summary = dict(video_id=spec['video_id'], status='complete', frames=len(data['cached']),
                requested_window=[spec['start'], spec['end']],
                native_window=[data['cached'][0]['pts'], data['cached'][-1]['pts']],
                available_after_pts=data['cached'][-1]['pts'], output_utc=feed['output_utc'],
                output_utc_scope='feed_prepared_not_media_available', media_available_utc=media_available_utc,
                counts=feed['counts'], linkage_counts=feed['linkage_counts'], quality_counts=feed['input_quality']['counts'],
                question_statuses={q['question']: q['status'] for q in feed['question_audit']},
                input_sha256={p: h for p, h in frozen['input_sha256'].items()
                              if p in {spec[k] for k in ('tracks', 'video', 'gap_events', 'tracklets',
                                  'associations', 'features', 'representatives', 'summary', 'regions')}},
                region_mode='current_only_no_control', raw_ids_preserved=True, accepted_links_preserved=True,
                detector_calls=0, tracker_calls=0, encoder_calls=0, identity_verified=False,
                physical_climb_completion='unknown', wall_seconds=time.perf_counter()-run_started,
                finished_utc=utc_now(), render_receipt=render_receipt)
            write_json(output/'summary.json', summary)
            receipt['videos'].append(summary)
            receipt['frames'] += len(data['cached'])
        verify_hashes(frozen['input_sha256'])
        verify_hashes(frozen['source_sha256'])
        if sha256(manifest) != receipt['manifest_sha256']:
            raise ValueError('Frozen manifest changed during execution')
        receipt.update(status='complete', inputs_unchanged=True, source_unchanged=True,
                       finished_utc=utc_now(), wall_seconds=time.perf_counter()-started)
        write_json(OUTPUT/'execution-receipt.json', receipt)
        return receipt
    except Exception as exc:
        receipt.update(status='failed', error_type=type(exc).__name__, error=str(exc), finished_utc=utc_now())
        write_json(OUTPUT/'failure-receipt.json', receipt)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['freeze', 'execute'])
    parser.add_argument('--manifest', type=Path, default=Path('runtime/EXP-0030/run-freeze.json'))
    args = parser.parse_args()
    result = freeze(args.manifest) if args.action == 'freeze' else execute(args.manifest)
    print(json.dumps(dict(status=result['status'], manifest=str(args.manifest)), ensure_ascii=False))


if __name__ == '__main__':
    main()
