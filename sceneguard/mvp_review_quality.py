"""Frozen, diagnostic-only checks of saved real observations and embeddings.

Flags describe possible overlapping/partial/drifting inputs, never person truth.
No representatives are removed and no association decisions are changed.
"""
from dataclasses import asdict, dataclass
import numpy as np

from .tracklet_linking import unit_features, valid_box


@dataclass(frozen=True)
class QualitySettings:
    overlap_iou: float = .5
    containment: float = .8
    extent_ratio: float = 1.5
    extent_window_seconds: float = .2
    inconsistency_similarity: float = .65
    inconsistency_margin: float = .15


def feature_consistency(values):
    """Retain every representative and expose the least consistent index (zero based)."""
    arr = unit_features(values)
    matrix = np.clip(arr @ arr.T, -1., 1.)
    if len(arr) < 2:
        affinities, least = [None], None
    else:
        affinities = [(float(matrix[i].sum())-float(matrix[i, i]))/(len(arr)-1)
                      for i in range(len(arr))]
        least = int(np.argmin(affinities))
    settings = QualitySettings()
    ordered = sorted(v for v in affinities if v is not None)
    margin = ordered[1]-ordered[0] if len(ordered) >= 2 else None
    return dict(pair_cosines=matrix.tolist(), mean_similarity_to_others=affinities,
                least_consistent_representative_index=least,
                least_index_tied=(len(ordered) > 1 and abs(ordered[1]-ordered[0]) < 1e-12),
                inconsistency_margin=margin,
                possible_inconsistent_representative=(len(arr) >= 3 and ordered[0] < settings.inconsistency_similarity
                    and margin >= settings.inconsistency_margin),
                representatives_retained=len(arr), identity_verified=False)


def overlap_geometry(a, b):
    a, b = valid_box(a), valid_box(b)
    intersection = max(0., min(a[2], b[2])-max(a[0], b[0])) * max(0., min(a[3], b[3])-max(a[1], b[1]))
    aa, ab = (a[2]-a[0])*(a[3]-a[1]), (b[2]-b[0])*(b[3]-b[1])
    return dict(iou=intersection/(aa+ab-intersection),
                fraction_a_contained=intersection/aa, fraction_b_contained=intersection/ab)


def quality_diagnostics(cached, tracked, segments, saved_features, representatives):
    settings = QualitySettings()
    overlaps, extents = [], []
    row_segments = {(r['frame_index'], r['cache_index']): s['id'] for s in segments for r in s['rows']}
    for index, (frame, measured) in enumerate(zip(cached, tracked)):
        rows = [r for r in measured['detections'] if r.get('observed', False) and r.get('confirmed', True)]
        for i, a in enumerate(rows):
            for b in rows[i+1:]:
                geometry = overlap_geometry(a['bbox'], b['bbox'])
                if (geometry['iou'] >= settings.overlap_iou or
                        max(geometry['fraction_a_contained'], geometry['fraction_b_contained']) >= settings.containment):
                    overlaps.append(dict(frame_index=index, pts=frame['pts'],
                        raw_ids=[a['track_id'], b['track_id']],
                        tracklets=[row_segments[(index, a['cache_index'])], row_segments[(index, b['cache_index'])]],
                        cache_indices=[a['cache_index'], b['cache_index']], geometry=geometry,
                        status='possible_overlap_duplicate_or_multi_person_crop', identity_verified=False))
    # Inspect the whole raw-ID sequence, including saved tracklet boundaries.
    raw_rows = {}
    for segment in segments:
        for row in segment['rows']:
            raw_rows.setdefault(segment['raw_id'], []).append(dict(row, tracklet_id=segment['id']))
    for raw_id, rows in sorted(raw_rows.items()):
        rows.sort(key=lambda r: r['pts'])
        for previous, row in zip(rows, rows[1:]):
            dt = row['pts']-previous['pts']
            if not 0 < dt <= settings.extent_window_seconds+1e-9:
                continue
            a, b = previous['bbox'], row['bbox']
            aw, ah, bw, bh = a[2]-a[0], a[3]-a[1], b[2]-b[0], b[3]-b[1]
            width_ratio, height_ratio = max(aw/bw, bw/aw), max(ah/bh, bh/ah)
            if max(width_ratio, height_ratio) >= settings.extent_ratio:
                extents.append(dict(raw_id=raw_id, before_frame_index=previous['frame_index'],
                    after_frame_index=row['frame_index'], before_pts=previous['pts'], after_pts=row['pts'],
                    before_tracklet=previous['tracklet_id'], after_tracklet=row['tracklet_id'],
                    width_ratio=width_ratio, height_ratio=height_ratio,
                    top_shift_over_min_height=(b[1]-a[1])/min(ah, bh),
                    bottom_shift_over_min_height=(b[3]-a[3])/min(ah, bh),
                    status='possible_partial_crop_extent_change_or_raw_id_drift', identity_verified=False))
    feature_map = saved_features['features']
    appearance = {}
    for sid, pair in sorted(feature_map.items()):
        endpoints = {}
        for end in ('head', 'tail'):
            endpoints[end] = dict(feature_consistency(pair[end]),
                                 representative_rows=representatives[sid][end])
        joined = pair['head']+pair['tail']
        references = [dict(endpoint=end, endpoint_index=i, frame_index=row['frame_index'],
                           cache_index=row['cache_index'], pts=row['pts'])
                      for end in ('head', 'tail') for i, row in enumerate(representatives[sid][end])]
        endpoints['head_and_tail'] = dict(feature_consistency(joined), representative_indices=references)
        appearance[sid] = endpoints
    return dict(settings=asdict(settings), concurrent_overlaps=overlaps, extent_changes=extents,
                appearance=appearance, counts=dict(concurrent_overlaps=len(overlaps), extent_changes=len(extents)),
                status='diagnostic_possibilities_not_person_truth',
                note='Stable partial/multi-person boxes and smooth ID drift can be missed; real motion can also trigger flags')


QUESTION_PAIRS = {
    '030': [('Q01', 't0001', 't0007'), ('Q02', 't0007', 't0008'), ('Q03', 't0002', 't0004')],
    '007': [('Q04', 't0006', 't0012'), ('Q05', 't0011', 't0012'), ('Q06', 't0006', 't0013'),
            ('Q07', 't0011', 't0013'), ('Q08', 't0007', 't0008')],
}


def question_audit(video_key, segments, associations, saved_features, feed):
    by_id = {s['id']: s for s in segments}
    originals = {(r['before'], r['after']): r for r in associations['links']}
    proposals = {(r['before_tracklet'], r['after_tracklet']): r for r in feed['link_suggestions']}
    results = []
    for question, before, after in QUESTION_PAIRS[video_key]:
        a, b = by_id[before], by_id[after]
        gap = b['start']-a['end']
        fa = unit_features(saved_features['features'][before]['tail'])
        fb = unit_features(saved_features['features'][after]['head'])
        matrix = np.clip(fa @ fb.T, -1., 1.)
        original, proposal = originals.get((before, after)), proposals.get((before, after))
        if original is None:
            if gap > associations['settings']['max_gap_seconds']+1e-9:
                status = 'outside_original_time_limit_audit_only'
            elif gap <= 0:
                status = 'concurrent_or_reverse_time_audit_only'
            else:
                raise ValueError('Expected saved original candidate for in-time Q pair')
        else:
            status = proposal['status'] if proposal else 'original_rejected_not_in_limited_review_suggestions'
        concerns = []
        if question == 'Q02':
            concerns = ['possible_raw11_first_representative_mix_partial_or_shadow_unconfirmed']
        if question == 'Q08':
            concerns = ['possible_two_people_overlap_in_crop', 'accepted_same_raw_id_gap_not_cross_id_identity_recovery']
        results.append(dict(question=question, before_tracklet=before, after_tracklet=after,
            before_raw_id=a['raw_id'], after_raw_id=b['raw_id'], gap_seconds=gap, status=status,
            original_link=original, in_feed_suggestions=proposal is not None,
            stored_representative_cosines=matrix.tolist(), similarity=float(np.median(matrix)),
            similarity_scope='saved_features_review_diagnostic_not_new_automatic_proposal',
            user_context=[], review_context=[dict(observation=concern,
                source='continuation_instruction_previous_review_draft',
                status='review_concern_not_identity_ground_truth', identity_verified=False) for concern in concerns],
            identity_verified=False, physical_climb_completion='unknown'))
    return results
