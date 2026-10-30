"""Offline SceneGuard MVP review feed from existing tracking and ReID outputs.

No detector, ReID forward, polygon tuning, or identity adjudication happens here.
Line-motion alerts remain review candidates even without two-sided evidence.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np


def _finite_number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{label} must be finite')
    return float(value)


def _features_stats(head, tail):
    """Diagnostic similarities; low similarity is not a proven ID switch."""
    def normalized(values):
        arr = np.asarray(values, dtype=float)
        if arr.ndim != 2 or arr.shape[0] < 1 or arr.shape[1] < 1 or not np.isfinite(arr).all():
            raise ValueError('Valid nonempty 2D features expected')
        lengths = np.linalg.norm(arr, axis=1)
        if np.any(lengths < 1e-12):
            raise ValueError('Zero-norm features')
        return arr / lengths[:, None]

    h, t = normalized(head), normalized(tail)
    if h.shape[1] != t.shape[1]:
        raise ValueError('Feature dimensionality mismatch')

    def within(arr):
        if len(arr) < 2:
            return None
        mat = arr @ arr.T
        values = mat[np.triu_indices(len(arr), 1)]
        return dict(min_similarity=float(values.min()), median_similarity=float(np.median(values)),
                    max_similarity=float(values.max()), pairs=len(values))

    return dict(head=within(h), tail=within(t),
                head_tail_cosine_median=float(np.median(h @ t.T)),
                head_count=len(h), tail_count=len(t), dimension=h.shape[1])


def appearance_diagnostics(saved):
    """Use precomputed features only, never silently infer a person's identity."""
    feature_map = saved.get('features', saved)
    if not isinstance(feature_map, dict):
        raise ValueError('Expected features object')
    return {sid: _features_stats(pair['head'], pair['tail'])
            for sid, pair in sorted(feature_map.items())}


def propose_links(associations, tracklets, limit_per_before=2):
    """Expose rejected appearance candidates for review WITHOUT accepting their IDs."""
    if not isinstance(limit_per_before, int) or isinstance(limit_per_before, bool) or limit_per_before < 1:
        raise ValueError('limit_per_before must be a positive integer')
    by_id = {item['id']: item for item in tracklets}
    if len(by_id) != len(tracklets):
        raise ValueError('Duplicate tracklet IDs')
    candidates = associations.get('links', [])
    if not isinstance(candidates, list):
        raise ValueError('Expected associations.links list')
    accepted, for_review = [], {}
    for link in candidates:
        before, after = link['before'], link['after']
        if before not in by_id or after not in by_id:
            raise ValueError('Link refers to missing tracklet')
        similarity = link.get('similarity')
        if similarity is not None:
            similarity = _finite_number(similarity, 'similarity')
            if not -1 <= similarity <= 1:
                raise ValueError('Cosine similarity out of range')
        base = dict(before_tracklet=before, after_tracklet=after,
                    before_raw_id=by_id[before]['raw_id'], after_raw_id=by_id[after]['raw_id'],
                    similarity=similarity, gap_seconds=link.get('gap_seconds'),
                    original_status=link.get('status'), original_reason=link.get('reason'),
                    identity_verified=False)
        if link.get('status') == 'accepted':
            base.update(status='auto_associated_unverified', note='Not human-verified identity')
            accepted.append(base)
        elif similarity is not None and link.get('status') in ('rejected', 'deferred'):
            base.update(status='possible_match_needs_review',
                        note='Rejected or deferred by original linker; NOT an accepted ID link')
            for_review.setdefault(before, []).append(base)
    proposed=[]
    for key in sorted(for_review):
        selected=sorted(for_review[key], key=lambda e:(-e['similarity'],e['after_tracklet']))
        proposed.extend(selected[:limit_per_before])
    return sorted(accepted,key=lambda e:(e['before_tracklet'],e['after_tracklet']))+proposed


def review_events(line_events, region_events, *, start, end, video_id, pre_seconds=4., post_seconds=8.):
    """Keep line and region claims separate; never infer completion or merge people."""
    start, end = _finite_number(start, 'start'), _finite_number(end, 'end')
    if end <= start:
        raise ValueError('Invalid video interval')
    if not video_id:
        raise ValueError('Video ID required')
    rows=[]
    for ix, item in enumerate(line_events):
        event_video = item.get('video_id', video_id)
        if event_video != video_id:
            raise ValueError('Line event from a different video')
        at = _finite_number(item['emitted_at_pts'], 'emitted_at_pts')
        if not start <= at <= end:
            raise ValueError('Line event outside available video window')
        rows.append(dict(id=f'line-{ix+1:04d}', video_id=video_id, at_pts=at,
                         source='existing_gap_line', category='boundary_motion_requires_review',
                         raw_track_id=item.get('track_id'), linked_id=None,
                         identity_verified=False, physical_climb_completion='unknown',
                         evidence_window=[max(start, at-pre_seconds),min(end, at+post_seconds)],
                         uncertainty=['bbox_bottom_center_proxy','possible_body_box_change'],
                         note='Existing candidate; not proven physical climb or crossing'))
    for ix, item in enumerate(region_events):
        at = _finite_number(item['confirmed_at'], 'confirmed_at')
        if not start <= at <= end:
            raise ValueError('Region event outside available video window')
        rows.append(dict(id=f'region-{ix+1:04d}', video_id=video_id, at_pts=at,
                         source='current_polygon_two_side', category='two_side_transition_requires_review',
                         raw_track_id=None, linked_id=item.get('chain_id'),
                         direction=item.get('direction'), identity_verified=False,
                         physical_climb_completion='unknown',
                         evidence_window=[max(start, at-pre_seconds),min(end, at+post_seconds)],
                         uncertainty=['bbox_proxy_not_ground_point','identity_not_verified'],
                         note='Two-sided observation candidate; not verified climb completion'))
    return sorted(rows,key=lambda row:(row['at_pts'],row['source'],row['id']))


def _load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _load_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()]


def make_feed(*, video_id, start, end, gap_events, associations, tracklets, saved_features,
              current_region_events=None):
    rows=review_events(gap_events,current_region_events or [],start=start,end=end,video_id=video_id)
    links=propose_links(associations,tracklets)
    diagnostic=appearance_diagnostics(saved_features)
    return dict(status='review_feed_ready_not_human_adjudicated', video_id=video_id,
                interval=[start,end], region_status=('current_region_results_supplied' if current_region_events is not None
                                                     else 'no_current_region_results_supplied'),
                events=rows, link_suggestions=links, appearance_diagnostics=diagnostic,
                counts=dict(motion_candidates=sum(r['source']=='existing_gap_line' for r in rows),
                            two_side_candidates=sum(r['source']=='current_polygon_two_side' for r in rows),
                            auto_associations_unverified=sum(r['status']=='auto_associated_unverified' for r in links),
                            possible_matches_for_review=sum(r['status']=='possible_match_needs_review' for r in links)),
                note='No inference, no polygon A/B, no manually confirmed identities or completed crossings')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--video-id',required=True)
    p.add_argument('--start',required=True,type=float)
    p.add_argument('--end',required=True,type=float)
    p.add_argument('--gap-events',required=True,type=Path)
    p.add_argument('--associations',required=True,type=Path)
    p.add_argument('--tracklets',required=True,type=Path)
    p.add_argument('--features',required=True,type=Path)
    p.add_argument('--region-events',type=Path,help='ONLY output from normal run using current user-approved polygon')
    p.add_argument('--output',required=True,type=Path)
    args=p.parse_args()
    target=args.output.resolve()
    if not target.is_relative_to(Path('outputs').resolve()) or target.exists():
        p.error('Use a NEW local Git-ignored outputs/ file; do not overwrite history')
    target.parent.mkdir(parents=True,exist_ok=True)
    result=make_feed(video_id=args.video_id,start=args.start,end=args.end,
                     gap_events=_load_jsonl(args.gap_events), associations=_load_json(args.associations),
                     tracklets=_load_json(args.tracklets),saved_features=_load_json(args.features),
                     current_region_events=_load_json(args.region_events) if args.region_events else None)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(result['counts'],ensure_ascii=False))


if __name__=='__main__':
    main()
