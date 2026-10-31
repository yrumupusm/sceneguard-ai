"""EXP-0042: additive gate-transition candidates from causal image trajectories.

No training, pose/identity inference or suppression of previous suspicions.
Pixel crossing/deformation is a heuristic cue, NOT a verified human action.
The adapter uses real images; missing IDs and overlapping boxes are not vetoes.
"""
from collections import deque
from dataclasses import asdict, dataclass
import math
import numpy as np


@dataclass(frozen=True)
class TransitionPolicy:
    seed_interval: float = .5
    window_seconds: float = 2.5
    reference_seconds: float = .5
    max_frame_gap: float = .12
    max_windows: int = 16
    max_points: int = 48
    min_points: int = 3
    score_threshold: float = .55
    support_seconds: float = .10
    support_window: float = .35
    min_support_frames: int = 3
    cooldown_seconds: float = 1.0
    seed_score: float = .25
    fb_error: float = 1.5
    lk_error: float = 30.

    def validate(self):
        for k, v in asdict(self).items():
            if type(v) not in (int, float) or not math.isfinite(v) or v <= 0:
                raise ValueError('Positive finite policy required: ' + k)
        for k in ('max_windows', 'max_points', 'min_points', 'min_support_frames'):
            if type(getattr(self, k)) is not int:
                raise ValueError('Integer policy required: ' + k)
        if (not 3 <= self.min_points <= self.max_points or self.min_support_frames < 2
                or not self.support_seconds < self.support_window
                or not self.reference_seconds < self.window_seconds
                or self.score_threshold > 1 or self.seed_score > 1):
            raise ValueError('Invalid policy bounds')
        return self



def inside_polygon(point, poly):
    x, y = point; found = False
    for (ax, ay), (bx, by) in zip(poly, poly[1:]+poly[:1]):
        cross = (bx-ax)*(y-ay)-(by-ay)*(x-ax)
        if abs(cross) < 1e-9 and min(ax,bx) <= x <= max(ax,bx) and min(ay,by) <= y <= max(ay,by):
            return True
        if (ay > y) != (by > y) and x < (bx-ax)*(y-ay)/(by-ay)+ax:
            found = not found
    return found


def _clip(v):
    return float(np.clip(v, 0., 1.))


def _points(v):
    x = np.asarray(v, dtype=float)
    if x.ndim != 2 or x.shape[1] != 2 or not np.isfinite(x).all():
        raise ValueError('Finite Nx2 pixel coordinates required')
    return x


def geometry(line, size):
    size = np.asarray(size, dtype=float)
    line = np.asarray(line, dtype=float)
    if (size.shape != (2,) or not np.isfinite(size).all() or np.any(size <= 0)
            or line.shape != (2, 2) or not np.isfinite(line).all()
            or np.any(line < 0) or np.any(line > 1)):
        raise ValueError('Pixel size and normalized line required')
    a, b = line * size
    v = b - a; length = float(np.linalg.norm(v))
    if length < 1e-6:
        raise ValueError('Nondegenerate finite gate required')
    return a, v, length


def _box(b, size):
    b = np.asarray(b, dtype=float)
    if (b.shape != (4,) or not np.isfinite(b).all()
            or not 0 <= b[0] < b[2] <= 1 or not 0 <= b[1] < b[3] <= 1):
        raise ValueError('Actual normalized xyxy box required')
    return b * np.tile(size, 2)


def cue_metrics(before, after, *, line, size, height, prior_speed=0., dt=.5):
    """Compare the SAME surviving pixel points, in a camera-corrected coordinate frame.

    General approach/rigid motion alone does not activate the local-change route.
    No signed-side/ID/VLM certainty or complete body is required.
    """
    p, q = _points(before), _points(after)
    if (p.shape != q.shape or len(p) < 3 or not math.isfinite(height) or height <= 0
            or not math.isfinite(dt) or dt <= 0 or not math.isfinite(prior_speed)
            or prior_speed < 0):
        raise ValueError('At least three corresponding points and positive scale/time required')
    a, v, length = geometry(line, size)
    h = max(16., height)
    def signed(x):
        return (v[0] * (x[:, 1]-a[1]) - v[1] * (x[:, 0]-a[0])) / length
    s, t = signed(p), signed(q)
    projection = ((q-a) @ v) / (length*length)
    nearest = a + np.clip(projection, 0, 1)[:, None]*v
    distance = float(np.median(np.linalg.norm(q-nearest, axis=1)))
    proximity = _clip(1-distance/(.8*h))
    margin = max(2., .025*h)
    crossed = (s*t < 0) & (np.abs(s) > margin) & (np.abs(t) > margin)
    alpha = np.divide(s, s-t, out=np.zeros_like(s), where=np.abs(s-t)>1e-9)
    intercept = p + alpha[:, None]*(q-p)
    along = ((intercept-a) @ v)/(length*length)
    crossed &= (along >= 0) & (along <= 1)
    fraction = float(crossed.mean())
    crossing = _clip(fraction/.35)
    displacement = q-p
    median = np.median(displacement, axis=0)
    residual = displacement-median
    coherence = float(np.exp(-np.median(np.linalg.norm(residual, axis=1))/(.08*h)))
    upward = _clip(float(np.quantile(np.maximum(0, -displacement[:, 1]), .80))/(.12*h))
    deformation = _clip(float(np.quantile(np.linalg.norm(residual, axis=1), .80))/(.08*h))
    progress = _clip(float(np.quantile(np.maximum(0, np.abs(s)-np.abs(t)), .75))/(.12*h))
    speed = float(np.quantile(np.linalg.norm(displacement, axis=1), .80))/(h*dt)
    change = _clip((speed-prior_speed)/.18)
    cross_score = proximity*(.65*crossing+.20*progress+.15*coherence) if fraction else 0.
    local_score = proximity*upward*(.55*deformation+.25*change+.20*progress)
    quality = .8+.2*min(1., len(p)/8)
    score = _clip(max(cross_score, local_score)*quality)
    return dict(score=score, route='boundary_motion' if cross_score>=local_score else 'local_gate_change',
                proximity=proximity, crossing_fraction=fraction, crossing=crossing,
                upward_image_motion=upward, local_deformation=deformation,
                normal_progress=progress, motion_change=change, coherence=coherence,
                speed_heights_per_second=speed, point_count=len(p),
                probability=None, identity_verified=False)


class EvidenceLatch:
    """Accumulate short positive evidence, not an all-frames-must-pass condition."""
    def __init__(self, policy=TransitionPolicy()):
        self.policy = policy.validate(); self.samples = deque(); self.last_pts = -math.inf
        self.last_emit = -math.inf

    def push(self, pts, score):
        if not math.isfinite(pts) or pts < 0 or pts <= self.last_pts or not 0 <= score <= 1:
            raise ValueError('Increasing finite PTS and bounded score required')
        if pts-self.last_pts > self.policy.max_frame_gap:
            self.samples.clear()
        self.last_pts = pts
        self.samples.append((pts, score))
        while self.samples and pts-self.samples[0][0] > self.policy.support_window+1e-9:
            self.samples.popleft()
        positive = [t for t, s in self.samples if s >= self.policy.score_threshold]
        enough = (score >= self.policy.score_threshold
                  and len(positive) >= self.policy.min_support_frames
                  and positive[-1]-positive[0] >= self.policy.support_seconds-1e-9)
        emit = enough and pts-self.last_emit >= self.policy.cooldown_seconds-1e-9
        if emit: self.last_emit = pts
        return bool(emit)


def tracked_points(previous, current, points, policy):
    """Forward/backward LK. Invalid points are removed, never relabeled as observations."""
    import cv2
    p = np.asarray(points, dtype=np.float32).reshape(-1, 2)
    if not len(p): return p.copy(), np.zeros(0, dtype=bool)
    opts = dict(winSize=(21, 21), maxLevel=3,
                criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, .01))
    q, st, err = cv2.calcOpticalFlowPyrLK(previous, current, p[:, None], None, **opts)
    if q is None or st is None or err is None: return p.copy(), np.zeros(len(p), dtype=bool)
    q = q.reshape(-1, 2); safe = q.copy()
    valid = np.isfinite(q).all(axis=1); safe[~valid] = p[~valid]
    back, bst, _ = cv2.calcOpticalFlowPyrLK(current, previous, safe[:, None], None, **opts)
    if back is None or bst is None: return q, np.zeros(len(p), dtype=bool)
    good = valid & np.isfinite(back.reshape(-1, 2)).all(axis=1) & (st.ravel()==1) & (bst.ravel()==1)
    good &= np.isfinite(err.ravel()) & (err.ravel() <= policy.lk_error)
    good &= np.linalg.norm(back.reshape(-1, 2)-p, axis=1) <= policy.fb_error
    good &= (q[:, 0]>=0) & (q[:, 0]<current.shape[1]) & (q[:, 1]>=0) & (q[:, 1]<current.shape[0])
    return q, good


def _corners(gray, mask, maximum):
    import cv2
    p = cv2.goodFeaturesToTrack(gray, maxCorners=maximum, qualityLevel=.02,
                               minDistance=3, mask=mask, blockSize=3)
    return np.empty((0, 2), np.float32) if p is None else p.reshape(-1, 2)


class GateTransition:
    """Continuous short image windows seeded by actual detector boxes near a gate.

    Raw IDs are metadata only. New IDs cannot clear earlier gate evidence.
    Reference points use only preceding frames; no retrospective loss/label lookup.
    """
    def __init__(self, scene, policy=TransitionPolicy()):
        self.policy = policy.validate(); self.scene = scene
        self.size = tuple(scene['source_size']); self.line = scene['line']
        self.a, self.v, self.length = geometry(self.line, self.size)
        if set(scene.get('directions', [])) != {'outside_to_inside', 'inside_to_outside'}:
            raise ValueError('This pilot uses existing bidirectional C3/C6 gates only')
        self.previous = None; self.previous_catalog = []; self.pts = -math.inf
        self.frame_index = -1; self.last_seed = -math.inf; self.serial = 0
        self.camera_offset = np.zeros(2); self.windows = []
        self.latch = EvidenceLatch(policy)

    def _near(self, b):
        center = (b[:2]+b[2:])/2
        t = np.clip(np.dot(center-self.a, self.v)/(self.length*self.length), 0, 1)
        return np.linalg.norm(center-self.a-t*self.v) <= .9*max(16., b[3]-b[1])

    def step(self, gray, pts, catalog, frame_index):
        import cv2
        if (gray.dtype != np.uint8 or gray.shape != (self.size[1], self.size[0])
                or not math.isfinite(pts) or pts < 0 or pts <= self.pts
                or type(frame_index) is not int or frame_index <= self.frame_index):
            raise ValueError('Native grayscale images, increasing frame index and PTS required')
        candidates = []
        for c in catalog:
            if c.get('observed') is False or c.get('bbox') is None: continue
            b = _box(c['bbox'], self.size)
            if not math.isfinite(c['score']) or not 0 <= c['score'] <= 1:
                raise ValueError('Invalid cached detection score')
            candidates.append((c, b))
        camera_step = np.zeros(2); camera_support = False
        gap = self.previous is not None and pts-self.pts > self.policy.max_frame_gap+1e-9
        if gap: self.windows.clear()
        if self.previous is not None and not gap:
            mask = np.full_like(gray, 255)
            for c in self.previous_catalog:
                if c.get('bbox') is None or c.get('observed') is False: continue
                b = _box(c['bbox'], self.size).astype(int)
                mask[b[1]:b[3]+1, b[0]:b[2]+1] = 0
            # A missed detection must not turn the tracked target into camera background.
            for window in self.windows:
                p = window['points']
                if len(p):
                    lo = np.maximum(0, np.floor(p.min(axis=0)-6)).astype(int)
                    hi = np.minimum(self.size, np.ceil(p.max(axis=0)+7)).astype(int)
                    mask[lo[1]:hi[1], lo[0]:hi[0]] = 0
            bg = _corners(self.previous, mask, 80)
            nxt, good = tracked_points(self.previous, gray, bg, self.policy)
            if good.sum() >= 6:
                delta = nxt[good]-bg[good]; median = np.median(delta, axis=0)
                consistent = np.linalg.norm(delta-median, axis=1) <= 2.5
                if consistent.mean() >= .6:
                    camera_step = np.median(delta[consistent], axis=0); camera_support = True
            self.camera_offset += camera_step
        signals = []; live = []
        for window in self.windows:
            if pts-window['seed_pts'] > self.policy.window_seconds: continue
            q, good = tracked_points(self.previous, gray, window['points'], self.policy)
            window['points'], window['ids'] = q[good], window['ids'][good]
            if len(window['points']) < self.policy.min_points: continue
            corrected = window['points']-self.camera_offset
            reference = min(window['history'], key=lambda r: abs(r[0]-(pts-self.policy.reference_seconds)))
            if pts-reference[0] >= .10-1e-9:
                old = {int(k):p for k, p in zip(reference[1], reference[2])}
                pairs = [(old[int(k)], p) for k, p in zip(window['ids'], corrected) if int(k) in old]
                if len(pairs) >= self.policy.min_points:
                    before, after = map(np.asarray, zip(*pairs))
                    older = [s for t, s in window['speeds'] if t <= reference[0]]
                    metric = cue_metrics(before, after, line=self.line, size=self.size,
                        height=window['height'], prior_speed=float(np.median(older)) if older else 0.,
                        dt=pts-reference[0])
                    window['speeds'].append((pts, metric['speed_heights_per_second']))
                    metric.update(window_id=window['id'], seed_pts=window['seed_pts'],
                        reference_pts=reference[0], seed_track_ids=window['track_ids'],
                        seed_cache_index=window['cache_index'], camera_support=camera_support,
                        point_ids=window['ids'].tolist(), points_original_pixels=window['points'].tolist(),
                        source='actual_image_correspondences', evidence_until_pts=pts)
                    if not camera_support: metric['score'] = max(0., metric['score']-.10)
                    signals.append(metric)
            window['history'].append((pts, window['ids'].copy(), corrected.copy()))
            while len(window['history']) > 1 and pts-window['history'][0][0] > 1.5*self.policy.reference_seconds:
                window['history'].popleft()
            live.append(window)
        self.windows = live
        seeded = 0
        if pts-self.last_seed >= self.policy.seed_interval-1e-9:
            self.last_seed = pts
            for c, b in sorted(candidates, key=lambda z:-z[0]['score']):
                if len(self.windows) >= self.policy.max_windows: break
                center = (b[:2]+b[2:])/2/np.asarray(self.size)
                if (c['score'] < self.policy.seed_score or not self._near(b)
                        or not inside_polygon(tuple(center), self.scene['approach_polygon'])): continue
                mask = np.zeros_like(gray); dx, dy = .1*(b[2]-b[0]), .1*(b[3]-b[1])
                mask[int(b[1]+dy):math.ceil(b[3]-dy), int(b[0]+dx):math.ceil(b[2]-dx)] = 255
                points = _corners(gray, mask, self.policy.max_points)
                if len(points) < self.policy.min_points: continue
                # Do not erase overlapped pixels or require a confirmed tracker ID.
                self.serial += 1; ids = np.arange(len(points))
                self.windows.append(dict(id=f'w{self.serial:06d}', seed_pts=pts, points=points,
                    ids=ids, history=deque([(pts, ids.copy(), points-self.camera_offset)]),
                    speeds=deque(maxlen=90), height=float(b[3]-b[1]),
                    track_ids=list(c.get('track_ids', [])), cache_index=c['cache_index']))
                seeded += 1
        best = max(signals, key=lambda r:r['score'], default=None)
        score = best['score'] if best else 0.
        emit = self.latch.push(pts, score)
        event = None if not emit else dict(status='침입 의심', reason='gate_visual_transition',
            decision_time_pts=pts, frame_index=frame_index, evidence=dict(best),
            evidence_until_pts=pts, identity_verified=False, automatic_confirmation=False,
            visibility_is_not_a_negative_verdict=True)
        self.previous = gray.copy(); self.previous_catalog = list(catalog)
        self.pts, self.frame_index = pts, frame_index
        return dict(pts=pts, frame_index=frame_index, signals=signals, score=score, event=event,
                    windows=len(self.windows), seeded=seeded, source_gap=gap,
                    camera_step_pixels=camera_step.tolist(), camera_support=camera_support,
                    point_paths=[dict(window_id=w['id'], seed_pts=w['seed_pts'],
                        seed_track_ids=w['track_ids'], seed_cache_index=w['cache_index'],
                        point_ids=w['ids'].tolist(),
                        points_original_pixels=w['points'].tolist()) for w in self.windows])
