"""EXP-0029: offline tracklet association, not a new detector or identity oracle.

Only measured boxes are used. Raw IDs remain intact; accepted links add an
independent chain ID. Time/geometry/appearance gates allow non-overlapping boxes.
All thresholds are development starting values, not calibrated probabilities.
"""
from dataclasses import asdict, dataclass
import math
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class LinkSettings:
    max_gap_seconds: float = 5.0
    split_gap_seconds: float = 1.0
    min_observations: int = 3
    min_span_seconds: float = 0.1
    representative_count: int = 3
    endpoint_seconds: float = 1.0
    min_similarity: float = 0.65
    ambiguity_margin: float = 0.05
    max_distance: float = 0.30  # distance in normalized xy, divided by sqrt(2)
    max_area_ratio: float = 4.0

    def validate(self):
        for name, value in asdict(self).items():
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f'{name} must be finite and positive')
        if self.min_similarity >= 1 or self.ambiguity_margin >= 1 or self.max_distance > 1:
            raise ValueError('Similarity, margin and normalized distance out of range')
        if self.max_area_ratio < 1 or self.min_observations < 2:
            raise ValueError('Invalid area ratio or minimum observations')
        if type(self.representative_count) is not int or type(self.min_observations) is not int:
            raise ValueError('Counts must be integers')
        return self


def valid_box(box):
    if (len(box) != 4 or not all(math.isfinite(x) for x in box)
            or not 0 <= box[0] < box[2] <= 1 or not 0 <= box[1] < box[3] <= 1):
        raise ValueError('Finite, ordered normalized xyxy box required')
    return list(map(float, box))


def box_geometry(box):
    x1, y1, x2, y2 = box
    return ((x1+x2)/2, (y1+y2)/2), (x2-x1)*(y2-y1)


def build_tracklets(frames: Iterable[dict], settings=LinkSettings()):
    """Split each raw ID at long gaps or implausible box jumps/scale changes.

    This cannot repair an ID switch hidden inside a smooth-looking original track.
    Short segments are retained for display but excluded from appearance linking.
    """
    settings.validate()
    segments, active, previous = [], {}, None
    for frame_index, frame in enumerate(frames):
        pts = float(frame['pts'])
        if not math.isfinite(pts) or (previous is not None and pts <= previous):
            raise ValueError('Strictly increasing finite frame PTS required')
        seen = set()
        for detection in frame['detections']:
            if not detection.get('observed', False) or not detection.get('confirmed', True):
                continue
            raw_id = detection['track_id']
            if type(raw_id) is not int or raw_id in seen:
                raise ValueError('Unique integer measured track IDs required in each frame')
            seen.add(raw_id)
            box = valid_box(detection['bbox'])
            score = float(detection['score'])
            if not math.isfinite(score) or not 0 <= score <= 1:
                raise ValueError('Invalid measured score')
            row = dict(frame_index=frame_index, pts=pts, raw_id=raw_id, bbox=box,
                       score=score, cache_index=detection.get('cache_index'))
            segment = active.get(raw_id)
            reason = 'first_observation'
            split = segment is None
            if segment is not None:
                before = segment['rows'][-1]
                p, area = box_geometry(before['bbox'])
                q, new_area = box_geometry(box)
                if pts-before['pts'] > settings.split_gap_seconds + 1e-9:
                    split, reason = True, 'observation_gap'
                elif math.dist(p, q)/math.sqrt(2) > settings.max_distance:
                    split, reason = True, 'position_jump'
                elif max(area/new_area, new_area/area) > settings.max_area_ratio:
                    split, reason = True, 'box_scale_jump'
            if split:
                segment = dict(id=f't{len(segments)+1:04d}', raw_id=raw_id,
                               split_reason=reason, rows=[])
                segments.append(segment)
                active[raw_id] = segment
            segment['rows'].append(row)
        previous = pts
    for segment in segments:
        rows = segment['rows']
        segment.update(start=rows[0]['pts'], end=rows[-1]['pts'], observations=len(rows))
        segment['eligible'] = (len(rows) >= settings.min_observations
                               and rows[-1]['pts']-rows[0]['pts']+1e-9 >= settings.min_span_seconds)
    return segments


def endpoint_rows(segment, end, settings=LinkSettings()):
    """Select up to three temporally distributed, scored crop representatives."""
    if end not in ('head', 'tail'):
        raise ValueError('Endpoint must be head or tail')
    rows = segment['rows']
    if end == 'head':
        rows = [r for r in rows if r['pts'] <= segment['start']+settings.endpoint_seconds+1e-9]
    else:
        rows = [r for r in rows if r['pts'] >= segment['end']-settings.endpoint_seconds-1e-9]
    chunks = np.array_split(np.arange(len(rows)), min(settings.representative_count, len(rows)))
    chosen = []
    for chunk in chunks:
        best = max((rows[int(i)] for i in chunk),
                   key=lambda r: (r['score']*math.sqrt(box_geometry(r['bbox'])[1]), -r['pts']))
        chosen.append(best)
    return chosen


def unit_features(features):
    array = np.asarray(features, dtype=np.float64)
    if array.ndim != 2 or not array.shape[0] or not array.shape[1] or not np.isfinite(array).all():
        raise ValueError('Nonempty finite 2-D appearance features required')
    norms = np.linalg.norm(array, axis=1, keepdims=True)
    if np.any(norms < 1e-12):
        raise ValueError('Zero-norm appearance feature')
    return array/norms


def candidate_links(segments, features, settings=LinkSettings()):
    """Produce scored candidates and explicit rejection reasons; no IoU gate."""
    settings.validate()
    eligible = [s for s in segments if s['eligible']]
    candidates = []
    for before in eligible:
        for after in eligible:
            dt = after['start']-before['end']
            if dt <= 1e-9 or dt > settings.max_gap_seconds+1e-9:
                continue  # concurrent segments are never stitched into one chain
            a = np.median([r['bbox'] for r in endpoint_rows(before, 'tail', settings)], axis=0)
            b = np.median([r['bbox'] for r in endpoint_rows(after, 'head', settings)], axis=0)
            p, area_a = box_geometry(a)
            q, area_b = box_geometry(b)
            distance = math.dist(p, q)/math.sqrt(2)
            area_ratio = max(area_a/area_b, area_b/area_a)
            row = dict(before=before['id'], after=after['id'], gap_seconds=dt,
                       distance=distance, area_ratio=float(area_ratio), similarity=None,
                       utility=None, status='rejected', reason=None)
            if distance > settings.max_distance:
                row['reason'] = 'spatial_gate'
            elif area_ratio > settings.max_area_ratio:
                row['reason'] = 'scale_gate'
            elif before['id'] not in features or after['id'] not in features:
                row['reason'] = 'missing_appearance'
            else:
                fa = unit_features(features[before['id']]['tail'])
                fb = unit_features(features[after['id']]['head'])
                if fa.shape[1] != fb.shape[1]:
                    raise ValueError('Embedding dimensions differ')
                similarity = float(np.median(np.clip(fa @ fb.T, -1, 1)))
                row['similarity'] = similarity
                if similarity < settings.min_similarity:
                    row['reason'] = 'appearance_gate'
                else:
                    row['utility'] = (0.8*similarity + 0.15*(1-distance/settings.max_distance)
                                      + 0.05*(1-dt/settings.max_gap_seconds))
                    row.update(status='eligible', reason=None)
            candidates.append(row)
    return candidates


def link_tracklets(segments, features, settings=LinkSettings()):
    """Offline one-to-one association with unmatched alternatives and ambiguity checks.

    Hungarian assignment is applied to forward-time edges only. One predecessor and
    one successor per segment prevent branches. Ambiguous appearance comparisons are
    left unlinked rather than forced into a second-best match.
    """
    from scipy.optimize import linear_sum_assignment
    candidates = candidate_links(segments, features, settings)
    eligible = [r for r in candidates if r['status'] == 'eligible']
    for row in eligible:
        peers = [r for r in eligible if r is not row and
                 (r['before'] == row['before'] or r['after'] == row['after'])]
        # Use appearance, not a tiny geometric advantage, to break identity ties.
        if peers and row['similarity']-max(r['similarity'] for r in peers) < settings.ambiguity_margin:
            row.update(status='deferred', reason='ambiguous_appearance')
    ids = [s['id'] for s in segments]
    if len(ids) != len(set(ids)):
        raise ValueError('Segment IDs must be unique')
    index = {sid: i for i, sid in enumerate(ids)}
    accepted = []
    if ids:
        # Separate dummy columns let every row remain unmatched at zero utility.
        costs = np.full((len(ids), 2*len(ids)), 1e6)
        costs[:, len(ids):] = 0.0
        lookup = {}
        for row in candidates:
            if row['status'] == 'eligible':
                pair = (index[row['before']], index[row['after']])
                costs[pair] = -row['utility']
                lookup[pair] = row
        rr, cc = linear_sum_assignment(costs)
        for i, j in zip(rr, cc):
            row = lookup.get((i, j))
            if row is not None:
                row.update(status='accepted', reason='appearance_time_space')
                accepted.append(row)
        for row in candidates:
            if row['status'] == 'eligible':
                row.update(status='deferred', reason='one_to_one_conflict')
    predecessor = {r['after']: r['before'] for r in accepted}
    successor = {r['before']: r['after'] for r in accepted}
    chains, mapping = [], {}
    for segment in sorted(segments, key=lambda s: (s['start'], s['id'])):
        sid = segment['id']
        if sid in predecessor:
            continue
        members = [sid]
        while members[-1] in successor:
            members.append(successor[members[-1]])
        chain_id = f'p{len(chains)+1:04d}'
        chains.append(dict(id=chain_id, segments=members))
        mapping.update({member: chain_id for member in members})
    if set(mapping) != set(ids):
        raise AssertionError('Invalid chain graph')
    return dict(links=candidates, chains=chains, mapping=mapping,
                settings=asdict(settings), identity_verified=False, mode='offline')


def point_in_polygon(point, polygon):
    """Even-odd rule; boundary points count as inside (overlap stays unknown)."""
    x, y = point
    inside = False
    for a, b in zip(polygon, polygon[1:]+polygon[:1]):
        ax, ay = a
        bx, by = b
        cross_value = (bx-ax)*(y-ay)-(by-ay)*(x-ax)
        if abs(cross_value) < 1e-10 and min(ax,bx)-1e-10 <= x <= max(ax,bx)+1e-10 and min(ay,by)-1e-10 <= y <= max(ay,by)+1e-10:
            return True
        if (ay > y) != (by > y) and x < (bx-ax)*(y-ay)/(by-ay)+ax:
            inside = not inside
    return inside


def validate_zones(zones):
    for name in ('outside', 'inside'):
        polygon = zones.get(name)
        if not isinstance(polygon, list) or len(polygon) < 3:
            raise ValueError(f'{name}: draw a polygon on the local camera image first')
        if any(len(p) != 2 or not all(math.isfinite(v) and 0 <= v <= 1 for v in p) for p in polygon):
            raise ValueError('Zone points must be finite normalized xy')
        area = sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(polygon, polygon[1:]+polygon[:1]))
        if abs(area) < 1e-8:
            raise ValueError('Degenerate zone polygon')
    return zones


def observation_zone(box, zones):
    """Vote over three interior box points, NOT estimated feet or true ground position.

    Camera-specific safe-side polygons should exclude the fence/transition band.
    Partial-body boxes and perspective can still cause mistakes; review is required.
    """
    x1, y1, x2, y2 = valid_box(box)
    points = [(x1+f*(x2-x1), y1+0.65*(y2-y1)) for f in (.35,.5,.65)]
    outside = sum(point_in_polygon(p, zones['outside']) for p in points) >= 2
    inside = sum(point_in_polygon(p, zones['inside']) for p in points) >= 2
    if outside == inside:
        return None
    return 'outside' if outside else 'inside'


def region_events(segments, associations, zones, observation_interval,
                  max_gap_seconds=5., dwell_seconds=.3, min_observations=3,
                  available_after_pts=None):
    """Offline side transitions supported by real measurements on both sides.

    A gap does not add dwell time. More than max_gap_seconds discards old evidence.
    This outputs inferred crossing candidates, not a legal/physical-climb verdict.
    """
    validate_zones(zones)
    if observation_interval <= 0 or not math.isfinite(observation_interval):
        raise ValueError('Positive native frame interval required')
    if (not math.isfinite(max_gap_seconds) or max_gap_seconds <= 0 or
            not math.isfinite(dwell_seconds) or dwell_seconds <= 0 or min_observations < 2):
        raise ValueError('Invalid region confirmation settings')
    by_id = {s['id']: s for s in segments}
    events = []
    for chain in associations['chains']:
        rows = sorted((dict(r, segment_id=sid) for sid in chain['segments']
                       for r in by_id[sid]['rows']), key=lambda r: r['pts'])
        stable, anchor, pending, first = None, None, None, None
        count, visible, previous_pts, previous_zone = 0, 0., None, None
        max_gap = 0.
        for row in rows:
            pts = row['pts']
            dt = None if previous_pts is None else pts-previous_pts
            if dt is not None and dt <= 0:
                raise ValueError('Linked chain has simultaneous/overlapping observations')
            if dt is not None and dt > max_gap_seconds+1e-9:
                stable = anchor = pending = first = None
                count, visible, max_gap = 0, 0., 0.
            if stable is not None and dt is not None:
                max_gap = max(max_gap, dt)
            zone = observation_zone(row['bbox'], zones)
            if zone is None:
                pending, first, count, visible = None, None, 0, 0.
            elif zone == stable:
                anchor = row
                pending, first, count, visible, max_gap = None, None, 0, 0., 0.
            else:
                if zone != pending:
                    pending, first, count, visible = zone, row, 1, 0.
                else:
                    count += 1
                    if previous_zone == zone and dt is not None and dt <= 1.5*observation_interval+1e-9:
                        visible += dt
                if count >= min_observations and visible+1e-9 >= dwell_seconds:
                    if stable is not None:
                        events.append(dict(chain_id=chain['id'], direction=f'{stable}_to_{zone}',
                            observed_before=anchor['pts'], observed_after=first['pts'],
                            confirmed_at=pts, candidate_interval=[anchor['pts'], first['pts']],
                            available_after_pts=available_after_pts, mode='offline_postprocessing',
                            confirmation_observations=count, confirmation_visible_seconds=visible,
                            largest_observation_interval=max_gap,
                            before_segment=anchor['segment_id'], after_segment=first['segment_id'],
                            linked_tracklets=anchor['segment_id'] != first['segment_id'],
                            identity_verified=False, physical_climb_completion='unknown'))
                    stable, anchor = zone, row
                    pending, first, count, visible, max_gap = None, None, 0, 0., 0.
            previous_pts, previous_zone = pts, zone
    return events
