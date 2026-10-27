"""Dependency-free conservative adjacent-IoU linking and finite-line crossing."""
from dataclasses import dataclass
import math


def iou(a, b):
    w = max(0., min(a[2], b[2]) - max(a[0], b[0]))
    h = max(0., min(a[3], b[3]) - max(a[1], b[1]))
    intersection = w*h
    union = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - intersection
    return intersection/union if union > 0 else 0.


def cross(a, b):
    return a[0]*b[1] - a[1]*b[0]


def finite_crossing(p, q, a, b):
    """Intersection of observed motion segment and finite configured boundary."""
    r = (q[0]-p[0], q[1]-p[1]); s = (b[0]-a[0], b[1]-a[1])
    den = cross(r, s)
    if abs(den) < 1e-12:
        return False
    delta = (a[0]-p[0], a[1]-p[1])
    t, u = cross(delta, s)/den, cross(delta, r)/den
    return 0 <= t <= 1 and 0 <= u <= 1


@dataclass
class SideState:
    base: int = 0
    anchor: tuple | None = None
    anchor_pts: float | None = None
    pending: int = 0
    pending_since: float = 0.
    first_point: tuple | None = None
    last_direction: str | None = None
    last_emitted: float = -math.inf


class BoundaryTracker:
    def __init__(self, config):
        self.a, self.b = [tuple(p) for p in config['line']]
        self.roi = config['roi']
        self.band = config['band']; self.dwell = config['dwell_seconds']
        self.max_gap = config['max_gap_seconds']; self.min_iou = config['min_iou']
        self.cooldown = config['cooldown_seconds']
        self.directions = config.get('directions', ['negative_to_positive', 'positive_to_negative'])
        values = [*self.a, *self.b, *self.roi, self.band, self.dwell, self.max_gap, self.min_iou, self.cooldown]
        if not all(math.isfinite(x) for x in values):
            raise ValueError('Configuration must be finite')
        if any(not 0 <= x <= 1 for x in [*self.a, *self.b, *self.roi]):
            raise ValueError('Geometry must be normalized')
        if self.a == self.b or not (self.roi[0] < self.roi[2] and self.roi[1] < self.roi[3]):
            raise ValueError('Degenerate line/ROI')
        if not (self.band >= 0 and self.dwell > 0 and self.max_gap > 0 and 0 < self.min_iou <= 1 and self.cooldown >= 0):
            raise ValueError('Invalid rule parameters')
        if not set(self.directions) <= {'negative_to_positive', 'positive_to_negative'}:
            raise ValueError('Invalid direction')
        self.tracks = {}; self.next_id = 1; self.previous_pts = None
        self.stats = dict(new_tracks=0, disconnected_tracks=0, ambiguous_detections=0, roi_resets=0)

    def observe(self, state, point, pts):
        x, y = point
        if not (self.roi[0] <= x <= self.roi[2] and self.roi[1] <= y <= self.roi[3]):
            if state.base or state.pending:
                self.stats['roi_resets'] += 1
            state.base = state.pending = 0; state.anchor = None
            return None
        vector = (self.b[0]-self.a[0], self.b[1]-self.a[1])
        distance = cross(vector, (x-self.a[0], y-self.a[1]))/math.hypot(*vector)
        side = 1 if distance > self.band else -1 if distance < -self.band else 0
        if not side:
            state.pending = 0
            return None
        if side == state.base:
            state.anchor, state.anchor_pts = point, pts
            state.pending = 0
            return None
        if state.pending != side:
            state.pending, state.pending_since, state.first_point = side, pts, point
            return None
        if pts-state.pending_since + 1e-9 < self.dwell:
            return None
        event = None
        if state.base and finite_crossing(state.anchor, state.first_point, self.a, self.b):
            direction = 'negative_to_positive' if state.base < 0 else 'positive_to_negative'
            if direction in self.directions and (state.last_direction != direction or pts-state.last_emitted >= self.cooldown):
                event = dict(observed_pts_before=state.anchor_pts,
                             observed_pts_after=state.pending_since,
                             candidate_interval=[state.anchor_pts, state.pending_since],
                             candidate_pts=(state.anchor_pts+state.pending_since)/2,
                             emitted_at_pts=pts, direction=direction,
                             physical_climb_completion='unknown', legal_status='unknown',
                             uncertainty=['bbox_bottom_center_proxy', 'development_boundary', 'identity_not_verified'])
                state.last_direction, state.last_emitted = direction, pts
        state.base, state.anchor, state.anchor_pts = side, point, pts
        state.pending = 0
        return event

    def step(self, pts, detections):
        if not math.isfinite(pts) or (self.previous_pts is not None and pts <= self.previous_pts):
            raise ValueError('PTS must be finite and strictly increasing')
        for d in detections:
            box = d['bbox']
            if len(box) != 4 or not all(math.isfinite(v) for v in box) or not (0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1):
                raise ValueError('Invalid normalized bbox')
        old = self.tracks
        if self.previous_pts is not None and pts-self.previous_pts > self.max_gap:
            self.stats['disconnected_tracks'] += len(old)
            old = {}
        # Conservative unique admissible matches: ambiguous assignments break IDs.
        by_detection = {j: [] for j in range(len(detections))}
        by_track = {tid: [] for tid in old}
        for tid, track in old.items():
            for j, det in enumerate(detections):
                if iou(track['bbox'], det['bbox']) >= self.min_iou:
                    by_detection[j].append(tid); by_track[tid].append(j)
        current = {}; rows = []; events = []; retained = set()
        for j, det in enumerate(detections):
            candidates = by_detection[j]
            if len(candidates) == 1 and len(by_track[candidates[0]]) == 1:
                tid = candidates[0]; state = old[tid]['state']; retained.add(tid)
            else:
                self.stats['ambiguous_detections'] += bool(candidates)
                tid = self.next_id; self.next_id += 1; state = SideState()
                self.stats['new_tracks'] += 1
            bbox = det['bbox']; point = ((bbox[0]+bbox[2])/2, bbox[3])
            event = self.observe(state, point, pts)
            if event:
                events.append(event | {'track_id': tid})
            current[tid] = {'bbox': bbox, 'state': state}
            rows.append(det | {'track_id': tid, 'observed': True})
        self.stats['disconnected_tracks'] += len(set(old)-retained)
        self.tracks = current; self.previous_pts = pts
        return rows, events
