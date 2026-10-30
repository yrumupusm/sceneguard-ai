"""EXP-0031 alternative representative selection, diagnostic only.

No person count, occlusion, or identity is inferred from boxes. This module
never edits source tracklets/IDs, pretrained weights, regions or thresholds.
"""
from dataclasses import dataclass, asdict
import math
import numpy as np


@dataclass(frozen=True)
class SelectionPolicy:
    endpoint_seconds: float = 2.0
    per_endpoint: int = 3
    overlap_iou: float = 0.5
    overlap_containment: float = 0.8
    extent_ratio: float = 1.5
    extent_window_seconds: float = 0.2
    small_area_fraction: float = 0.45

    def validate(self):
        vals = asdict(self)
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or
               not math.isfinite(v) or v <= 0 for v in vals.values()):
            raise ValueError('All selection parameters must be finite positive numbers')
        if not isinstance(self.per_endpoint, int) or self.per_endpoint < 1:
            raise ValueError('per_endpoint must be a positive integer')
        if self.overlap_iou > 1 or self.overlap_containment > 1 or self.small_area_fraction >= 1:
            raise ValueError('Invalid fractional selection parameter')
        if self.extent_ratio <= 1:
            raise ValueError('Extent ratio must exceed one')
        return self


def _key(row):
    fi, di = row['frame_index'], row['cache_index']
    if type(fi) is not int or type(di) is not int or fi < 0 or di < 0:
        raise ValueError('Each observed row needs nonnegative integer frame/cache indices')
    return fi, di


def _box(box):
    if (len(box) != 4 or not all(math.isfinite(v) for v in box) or
            not 0 <= box[0] < box[2] <= 1 or not 0 <= box[1] < box[3] <= 1):
        raise ValueError('Expected normalized xyxy bbox')
    return box


def _area(box):
    _box(box)
    return (box[2]-box[0])*(box[3]-box[1])


def _overlap(a, b):
    ax1, ay1, ax2, ay2 = _box(a)
    bx1, by1, bx2, by2 = _box(b)
    intersect = max(0., min(ax2, bx2)-max(ax1, bx1))*max(0., min(ay2, by2)-max(ay1, by1))
    aa, bb = _area(a), _area(b)
    return intersect/(aa+bb-intersect), max(intersect/aa, intersect/bb)


def _overlaps_other_measurement(box, frame_measurements, own_cache_index, policy):
    for other in frame_measurements:
        if other['cache_index'] == own_cache_index:
            continue
        iou, containment = _overlap(box, other['bbox'])
        if iou >= policy.overlap_iou or containment >= policy.overlap_containment:
            return True
    return False


def make_quality_index(segments, tracked_frames, policy=SelectionPolicy()):
    """Observable geometry warnings, never an automatic two-person label."""
    policy.validate()
    keys = {}
    for seg in segments:
        for row in seg['rows']:
            k = _key(row)
            if k in keys:
                raise ValueError('Duplicate observed cache measurement across segments')
            if row['raw_id'] != seg['raw_id']:
                raise ValueError('Tracklet/raw ID mismatch')
            _box(row['bbox'])
            keys[k] = row
    frame_rows = {}
    for frame_index, frame in enumerate(tracked_frames):
        current = frame['detections']
        for row in current:
            if not row.get('observed', False) or not row.get('confirmed', True):
                continue
            k = frame_index, row.get('cache_index')
            if k not in keys:
                raise ValueError('Observed tracking cache row not found in tracklets')
            if row['track_id'] != keys[k]['raw_id'] or row['bbox'] != keys[k]['bbox']:
                raise ValueError('Tracklet observation differs from saved tracking measurement')
            frame_rows.setdefault(frame_index, []).append(row)
    if sum(len(x) for x in frame_rows.values()) != len(keys):
        raise ValueError('Incomplete measured-row partition')
    risk = {}
    for seg in segments:
        rows = seg['rows']
        for i, row in enumerate(rows):
            key = _key(row)
            fi = row['frame_index']
            overlap = _overlaps_other_measurement(row['bbox'], frame_rows.get(fi, []),
                                                   row['cache_index'], policy)
            sudden = False
            for neighbor in (rows[i-1] if i > 0 else None,
                             rows[i+1] if i+1 < len(rows) else None):
                if neighbor is None or abs(neighbor['pts']-row['pts']) > policy.extent_window_seconds:
                    continue
                a, b = _box(row['bbox']), _box(neighbor['bbox'])
                aw, ah, bw, bh = a[2]-a[0], a[3]-a[1], b[2]-b[0], b[3]-b[1]
                if max(aw/bw, bw/aw, ah/bh, bh/ah) >= policy.extent_ratio:
                    sudden = True
            risk[key] = dict(overlap_warning=bool(overlap), abrupt_extent_warning=bool(sudden),
                             # Other-person-in-crop cannot be inferred from these two proxies.
                             mixed_person_verified=False)
    return risk


def choose_representatives(segments, tracked_frames, policy=SelectionPolicy()):
    """Same raw segments, wider endpoint pool, temporally distributed low-risk boxes.

    Every endpoint gets up to per_endpoint samples; if all are risky, retain
    them with a warning rather than silently asserting clean identity crops.
    """
    policy.validate()
    risk = make_quality_index(segments, tracked_frames, policy)
    selected, audit = {}, {}
    for seg in segments:
        if not seg['eligible']:
            continue
        sid, rows = seg['id'], seg['rows']
        selected[sid], audit[sid] = {}, {}
        for end in ('head', 'tail'):
            boundary = seg['start'] if end == 'head' else seg['end']
            pool = [r for r in rows if abs(r['pts']-boundary) <= policy.endpoint_seconds+1e-9]
            if not pool:
                raise ValueError('Eligible segment has no endpoint observations')
            areas = [_area(r['bbox']) for r in pool]
            median_area = float(np.median(areas))
            flags = {}
            for r in pool:
                f = dict(risk[_key(r)])
                f['small_relative_box_warning'] = bool(_area(r['bbox']) < policy.small_area_fraction*median_area)
                flags[_key(r)] = f
            bins = np.array_split(np.arange(len(pool)), min(policy.per_endpoint, len(pool)))
            def rank(row):
                f = flags[_key(row)]
                severity = sum(f[k] for k in ('overlap_warning', 'abrupt_extent_warning', 'small_relative_box_warning'))
                confidence = row['score']
                if not math.isfinite(confidence) or not 0 <= confidence <= 1:
                    raise ValueError('Invalid observed confidence')
                return severity, -confidence*math.sqrt(_area(row['bbox'])), abs(row['pts']-boundary), _key(row)
            choice = [min((pool[int(i)] for i in b), key=rank) for b in bins]
            selected[sid][end] = choice
            audit[sid][end] = dict(source_raw_id=seg['raw_id'], endpoint_pts=boundary,
                                    pool_observations=len(pool), selected=[dict(frame_index=r['frame_index'],
                                        cache_index=r['cache_index'], pts=r['pts'], risk=flags[_key(r)]) for r in choice],
                                    warning='geometry_risk_present_not_verified_mixed_person'
                                        if any(any(flags[_key(r)][k] for k in ('overlap_warning','abrupt_extent_warning','small_relative_box_warning'))
                                               for r in choice) else None,
                                    clean_endpoint_proxy=all(not any(flags[_key(r)][k]
                                         for k in ('overlap_warning','abrupt_extent_warning','small_relative_box_warning'))
                                         for r in choice))
    return selected, audit


def build_feature_map(original_representatives, original_features):
    """Reuses exact old crop embeddings by native cache key; detects inconsistencies."""
    saved = original_features.get('features', original_features)
    mapping = {}
    for sid, endpoints in original_representatives.items():
        if sid not in saved:
            raise ValueError('Original representative has no features')
        for end in ('head', 'tail'):
            rows, vectors = endpoints[end], saved[sid][end]
            if len(rows) != len(vectors):
                raise ValueError('Original selection/feature shape mismatch')
            for row, values in zip(rows, vectors):
                k = _key(row)
                arr = np.asarray(values, dtype=float)
                if arr.ndim != 1 or arr.size < 2 or not np.isfinite(arr).all() or np.linalg.norm(arr) < 1e-12:
                    raise ValueError('Invalid cached feature')
                normalized = arr/np.linalg.norm(arr)
                if k in mapping and not np.allclose(mapping[k], normalized, atol=1e-5, rtol=0):
                    raise ValueError('Conflicting embeddings for the same measured crop')
                mapping[k] = normalized
    return mapping


def changed_pair_report(segments, original_associations, alternative_associations, audit):
    """A/B association diagnostics; never claims improved identity accuracy."""
    by_id = {s['id']: s for s in segments}
    old = {(x['before'], x['after']):x for x in original_associations['links']}
    new = {(x['before'], x['after']):x for x in alternative_associations['links']}
    if set(old) != set(new):
        raise ValueError('Geometry/temporal candidate pairs changed between conditions')
    table = []
    for pair in sorted(old):
        a, b = old[pair], new[pair]
        table.append(dict(before=pair[0], after=pair[1],
                          before_raw_id=by_id[pair[0]]['raw_id'], after_raw_id=by_id[pair[1]]['raw_id'],
                          old_status=a['status'], alternative_status=b['status'],
                          old_similarity=a.get('similarity'), alternative_similarity=b.get('similarity'),
                          before_tail_clean_proxy=audit[pair[0]]['tail']['clean_endpoint_proxy'],
                          after_head_clean_proxy=audit[pair[1]]['head']['clean_endpoint_proxy'],
                          identity_verified=False,
                          action='human_review_only_not_adopted'))
    return table
