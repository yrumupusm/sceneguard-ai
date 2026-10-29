"""Practical boundary memory across short detection gaps; no identity inference.

Consume real boxes with externally assigned tracking IDs. A lost track retains
its confirmed side for a bounded time. Predicted boxes neither refresh the TTL
nor supply dwell evidence. Old strict boundary classes remain unchanged.
"""
from dataclasses import dataclass
import math

from .boundary import BoundaryRules, cross, finite_crossing


@dataclass
class _Memory:
    last_seen: float
    base: int = 0
    anchor: tuple | None = None
    anchor_pts: float | None = None
    pending: int = 0
    first_point: tuple | None = None
    first_pts: float | None = None
    visible_seconds: float = 0.0
    samples: int = 0
    crossed_gap: bool = False
    max_gap_seconds: float = 0.0
    last_emitted: float = -math.inf

    def clear_pending(self):
        self.pending = 0
        self.first_point = self.first_pts = None
        self.visible_seconds = 0.0
        self.samples = 0


class GapTolerantBoundary(BoundaryRules):
    """Remember each ID for retain_seconds, confirm using observed evidence.

    config['max_gap_seconds'] bounds an interval eligible for dwell accumulation,
    NOT the memory lifetime. A single missing frame pauses dwell, not the track.
    This class cannot repair a tracker ID switch or determine physical identity.
    """
    def __init__(self, config, retain_seconds=3.0, min_observations=3):
        super().__init__(config)
        if not math.isfinite(retain_seconds) or retain_seconds <= 0:
            raise ValueError('retain_seconds must be finite and positive')
        if type(min_observations) is not int or min_observations < 2:
            raise ValueError('min_observations must be an integer >= 2')
        self.retain_seconds = float(retain_seconds)
        self.min_observations = min_observations
        self.stats.update(expired_memories=0, reobservations_after_gap=0,
                          candidates=0, suppressed_cooldown=0)

    def step(self, pts, observations):
        if not math.isfinite(pts) or (self.previous_pts is not None and pts <= self.previous_pts):
            raise ValueError('PTS must be finite and strictly increasing')
        # Validate the whole frame before modifying state.
        accepted = []
        seen = set()
        for row in observations:
            if not row.get('observed') or not row.get('confirmed', True):
                continue
            tid = row['track_id']
            if type(tid) is not int or tid < 0 or tid in seen:
                raise ValueError('Unique nonnegative integer observed IDs required')
            b = row['bbox']
            if (len(b) != 4 or not all(math.isfinite(v) for v in b)
                    or not (0 <= b[0] < b[2] <= 1 and 0 <= b[1] < b[3] <= 1)):
                raise ValueError('Invalid measured bbox')
            seen.add(tid)
            accepted.append((tid, ((b[0] + b[2]) / 2, b[3])))
        for tid in list(self.tracks):
            if pts - self.tracks[tid].last_seen > self.retain_seconds + 1e-9:
                del self.tracks[tid]
                self.stats['expired_memories'] += 1
        events = []
        for tid, point in accepted:
            state = self.tracks.get(tid)
            if state is None:
                state = _Memory(last_seen=pts)
                self.tracks[tid] = state
                self.stats['new_tracks'] += 1
                adjacent, elapsed = False, 0.0
            else:
                elapsed = pts - state.last_seen
                adjacent = (self.previous_pts is not None
                            and abs(state.last_seen - self.previous_pts) <= 1e-9
                            and elapsed <= self.max_gap + 1e-9)
                if not adjacent:
                    state.crossed_gap = True
                    state.max_gap_seconds = max(state.max_gap_seconds, elapsed)
                    self.stats['reobservations_after_gap'] += 1
            event = self._observe(state, point, pts, elapsed if adjacent else 0.0)
            state.last_seen = pts
            if event is not None:
                events.append(event | {'track_id': tid})
                self.stats['candidates'] += 1
        self.previous_pts = pts
        return events

    def _observe(self, state, point, pts, visible_delta):
        x, y = point
        if not (self.roi[0] <= x <= self.roi[2] and self.roi[1] <= y <= self.roi[3]):
            if state.base or state.pending:
                self.stats['roi_resets'] += 1
            state.base = 0
            state.anchor = state.anchor_pts = None
            state.clear_pending()
            state.crossed_gap = False
            state.max_gap_seconds = 0.0
            return None
        vector = (self.b[0] - self.a[0], self.b[1] - self.a[1])
        distance = cross(vector, (x - self.a[0], y - self.a[1])) / math.hypot(*vector)
        side = 1 if distance > self.band else -1 if distance < -self.band else 0
        if side == 0:
            state.clear_pending()
            return None
        if side == state.base:
            state.anchor, state.anchor_pts = point, pts
            state.clear_pending()
            state.crossed_gap = False
            state.max_gap_seconds = 0.0
            return None
        if state.pending != side:
            state.clear_pending()
            state.pending = side
            state.first_point, state.first_pts = point, pts
            state.samples = 1
        else:
            state.samples += 1
            state.visible_seconds += visible_delta
        if state.samples < self.min_observations or state.visible_seconds + 1e-9 < self.dwell:
            return None
        event = None
        if state.base and finite_crossing(state.anchor, state.first_point, self.a, self.b):
            direction = 'negative_to_positive' if state.base < 0 else 'positive_to_negative'
            if direction in self.directions:
                # Apply across directions too: a quick box-size bounce is not two alarms.
                if pts - state.last_emitted + 1e-9 >= self.cooldown:
                    event = dict(
                        observed_pts_before=state.anchor_pts, observed_pts_after=state.first_pts,
                        candidate_interval=[state.anchor_pts, state.first_pts],
                        candidate_pts=(state.anchor_pts + state.first_pts) / 2,
                        emitted_at_pts=pts, direction=direction,
                        bridged_observation_gap=state.crossed_gap,
                        largest_observation_gap_seconds=state.max_gap_seconds,
                        confirmation_observations=state.samples,
                        confirmation_visible_seconds=state.visible_seconds,
                        physical_climb_completion='unknown', legal_status='unknown',
                        uncertainty=['bbox_bottom_center_proxy', 'identity_not_verified',
                                     'crossing_between_observations_is_inferred'])
                    state.last_emitted = pts
                else:
                    self.stats['suppressed_cooldown'] += 1
        state.base, state.anchor, state.anchor_pts = side, point, pts
        state.clear_pending()
        state.crossed_gap = False
        state.max_gap_seconds = 0.0
        return event
