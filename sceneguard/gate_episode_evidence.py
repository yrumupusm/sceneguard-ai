"""EXP-0045: remember a gate encounter; detect an observation born just inside it.

No model, optical-flow computation, person-ID merge, or automatic negative verdict.
An observation run is geometric continuity, NOT a resolved person's identity.
Automatic confirmation remains a fallible camera rule, separate from human review.
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import asdict, dataclass
import math
import statistics


@dataclass(frozen=True)
class EpisodePolicy:
    history_seconds: float = 3.0
    birth_lookback: float = 1.0
    birth_support_seconds: float = .10
    source_gap_seconds: float = .12
    detection_floor: float = .25
    near_height_fraction: float = .8
    minimum_near_pixels: float = 12.0
    maximum_near_image_fraction: float = .12
    association_overlap: float = .6

    def validate(self):
        for name, value in asdict(self).items():
            if type(value) not in (float, int) or not math.isfinite(value) or value <= 0:
                raise ValueError('Positive finite policy required: ' + name)
        if (self.detection_floor > 1 or self.association_overlap > 1
                or self.maximum_near_image_fraction > 1
                or self.birth_support_seconds >= self.birth_lookback):
            raise ValueError('Invalid policy bounds')
        return self


def number(value):
    if type(value) not in (float, int) or not math.isfinite(value):
        raise ValueError('Finite scalar required')
    return float(value)


def in_polygon(p, poly):
    x, y = p; result = False
    for a, b in zip(poly, poly[1:] + poly[:1]):
        cross = (b[0]-a[0])*(y-a[1]) - (b[1]-a[1])*(x-a[0])
        if abs(cross) < 1e-9 and min(a[0],b[0]) <= x <= max(a[0],b[0]) and min(a[1],b[1]) <= y <= max(a[1],b[1]):
            return True
        if (a[1] > y) != (b[1] > y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:
            result = not result
    return result


class Gate:
    def __init__(self, scene, policy=EpisodePolicy()):
        self.policy = policy.validate(); self.scene = deepcopy(scene)
        self.size = tuple(map(number, scene['source_size']))
        if len(self.size) != 2 or min(self.size) <= 0:
            raise ValueError('Positive source dimensions required')
        if len(scene['line']) != 2:
            raise ValueError('One finite gate segment required')
        self.a, b = [self.point(p) for p in scene['line']]
        self.v = (b[0]-self.a[0], b[1]-self.a[1]); self.length = math.hypot(*self.v)
        if self.length <= 1e-9:
            raise ValueError('Nondegenerate gate segment required')
        n = (-self.v[1]/self.length, self.v[0]/self.length)
        centers = {}
        for name in ('outside', 'inside'):
            poly = scene['zones'][name]
            if len(poly) < 3:
                raise ValueError('Inside and outside polygons required')
            coords = [self.point(p) for p in poly]
            centers[name] = tuple(statistics.mean(p[k] for p in coords) for k in (0, 1))
        delta = sum((centers['inside'][k]-centers['outside'][k])*n[k] for k in (0,1))
        if abs(delta) <= 1e-6:
            raise ValueError('Inside direction cannot be derived from these zones')
        self.normal = tuple(x*(1 if delta > 0 else -1) for x in n)

    def point(self, p):
        if len(p) != 2 or not all(0 <= number(v) <= 1 for v in p):
            raise ValueError('Normalized finite point required')
        return tuple(p[k]*self.size[k] for k in (0,1))

    def box(self, box):
        if len(box) != 4 or not all(0 <= number(x) <= 1 for x in box) or not (box[0]<box[2] and box[1]<box[3]):
            raise ValueError('Normalized nonempty actual box required')
        return tuple(box[k]*self.size[k%2] for k in range(4))

    def locate(self, bbox, *, birth=True):
        b = self.box(bbox); c = ((b[0]+b[2])/2, (b[1]+b[3])/2)
        along = sum((c[k]-self.a[k])*self.v[k] for k in (0,1))/(self.length*self.length)
        closest = tuple(self.a[k] + min(1., max(0., along))*self.v[k] for k in (0,1))
        distance = math.dist(c, closest)
        radius = max(self.policy.minimum_near_pixels, (b[3]-b[1])*self.policy.near_height_fraction)
        if birth:
            radius = max(self.policy.minimum_near_pixels, min(radius,
                min(self.size)*self.policy.maximum_near_image_fraction))
        signed = sum((c[k]-self.a[k])*self.normal[k] for k in (0,1))
        normalized = tuple(c[k]/self.size[k] for k in (0,1))
        return dict(center_pixels=c, distance_pixels=distance, radius_pixels=radius,
            along=along, signed_pixels=signed,
            near=distance <= radius,
            # A line EXTENSION is not the doorway. No far-inside first appearance.
            inside_birth_site=(0 <= along <= 1 and distance <= radius and signed > 0
                and in_polygon(normalized, self.scene['zones']['inside'])))


def history_decision(previous, segment, scene, policy=EpisodePolicy()):
    """Only replace EXP44's terminal-size proximity check, not its raw event.

    Inward direction must be observed at/after the remembered gate encounter.
    Current same-side continuation cannot prove intrusion absence; it simply is
    not a disappearance confirmation. Original alarms are never deleted here.
    """
    if 'inner_line' in scene:
        from .dual_boundary import guarded
        return guarded(previous)
    p = policy.validate(); gate = Gate(scene, p); result = deepcopy(previous)
    rows = segment['rows']; last = rows[-1]
    if any(number(a['pts']) >= number(b['pts']) for a,b in zip(rows, rows[1:])):
        raise ValueError('Chronological actual segment observations required')
    if abs(number(previous['last_observed_pts'])-number(last['pts'])) > 1e-6:
        raise ValueError('Decision and segment loss time differ')
    # Retain historical geometry for each REAL observation, not last tiny height.
    contacts = [dict(pts=r['pts'], frame_index=r['frame_index'], bbox=deepcopy(r['bbox']),
                     **gate.locate(r['bbox'], birth=False)) for r in rows
                if 0 <= last['pts']-r['pts'] <= p.history_seconds+1e-9]
    direction = previous.get('direction', {})
    end = direction.get('end_pts', last['pts'])
    eligible = [r for r in contacts if r['near'] and r['pts'] <= end+1e-9]
    result.update(rule_id='gate_history_loss_v1', gate_history=eligible,
        terminal_gate_test_required=False, human_verified=False, identity_verified=False)
    if previous.get('automatic_confirmation'):
        return result
    # Invalid/no observed waiting interval is not upgraded by this helper.
    if previous.get('reason') == 'loss_wait_not_observed':
        return result
    if (eligible and direction.get('direction') == 'inward'
            and previous.get('continuation') == 'unresolved'):
        result.update(status='침입 확인', automatic_confirmation=True, notify=True,
            reason='recent_gate_encounter_inward_then_loss',
            gate_contact=eligible[-1], decision_source='automatic_rule',
            confirmation_basis='camera_rule_not_manual_or_ground_truth')
    return result


def overlap(a, b):
    intersection = max(0.,min(a[2],b[2])-max(a[0],b[0]))*max(0.,min(a[3],b[3])-max(a[1],b[1]))
    return intersection/max(1e-12,min((a[2]-a[0])*(a[3]-a[1]),(b[2]-b[0])*(b[3]-b[1])))


def association(a, b, floor):
    """Short geometric continuity; IDs are intentionally ignored."""
    ov = overlap(a, b)
    ac, bc = ((a[0]+a[2])/2,(a[1]+a[3])/2), ((b[0]+b[2])/2,(b[1]+b[3])/2)
    scale = max(a[3]-a[1], b[3]-b[1], 1e-9)
    distance = math.dist(ac, bc)/scale
    if ov >= floor:
        return 2+ov
    return 1-distance if distance <= .5 else None


class InsideBirths:
    """ID-independent short observation runs, not a replacement person tracker.

    A run is eligible only at BIRTH: inside + near the finite gate. An existing
    corridor run approaching the gate never becomes a new gate birth. Temporary
    detector gaps/ID changes are checked against the recent all-frame history.
    """
    def __init__(self, scene, policy=EpisodePolicy()):
        self.policy = policy.validate(); self.gate = Gate(scene, policy)
        self.last_pts = None; self.warm_since = None; self.serial = 0; self.runs = []
        self.audit = []

    def step(self, frame):
        at = number(frame['pts']); p = self.policy
        if at < 0 or (self.last_pts is not None and at <= self.last_pts):
            raise ValueError('Increasing nonnegative original frame PTS required')
        if self.last_pts is None or at-self.last_pts > p.source_gap_seconds+1e-9:
            self.runs = []; self.warm_since = at
        self.last_pts = at
        self.runs = [r for r in self.runs if at-r['last_pts'] <= p.birth_lookback+1e-9]
        boxes = []
        for box in frame['actual_boxes']:
            self.gate.box(box['bbox'])
            score = number(box['score'])
            if not 0 <= score <= 1:
                raise ValueError('Bounded detector score required')
            if box.get('observed') is not False and score >= p.detection_floor:
                boxes.append(deepcopy(box))
        # Nested/duplicate detector footprints do not count as additional people.
        # Preserve every original output elsewhere; this is only birth bookkeeping.
        selected = []
        for b in sorted(boxes, key=lambda b:-((b['bbox'][2]-b['bbox'][0])*(b['bbox'][3]-b['bbox'][1]))):
            if not any(overlap(b['bbox'],old['bbox']) >= .9 for old in selected):
                selected.append(b)
        edges = []
        for i, b in enumerate(selected):
            for j, r in enumerate(self.runs):
                quality = association(self.gate.box(r['bbox']), self.gate.box(b['bbox']), p.association_overlap)
                if quality is not None:
                    edges.append((quality, i, j))
        matched_boxes, matched_runs, current = set(), set(), []
        for quality, i, j in sorted(edges, key=lambda e:(-e[0],e[1],e[2])):
            if i in matched_boxes or j in matched_runs:
                continue
            matched_boxes.add(i); matched_runs.add(j)
            r = self.runs[j]; b = selected[i]
            r.update(bbox=b['bbox'], last_pts=at, count=r['count']+1)
            r['observations'].append(dict(pts=at, frame_index=frame['frame_index'], cache_index=b['cache_index']))
            current.append(r)
        for i, b in enumerate(selected):
            if i in matched_boxes:
                continue
            self.serial += 1; site = self.gate.locate(b['bbox'])
            r = dict(run_id=f'observation-{self.serial:05d}', first_pts=at, last_pts=at,
                first_bbox=deepcopy(b['bbox']), bbox=b['bbox'], site=site, count=1,
                eligible=site['inside_birth_site'] and at-self.warm_since >= p.birth_lookback-1e-9,
                emitted=False, observations=[dict(pts=at,frame_index=frame['frame_index'],cache_index=b['cache_index'])])
            self.runs.append(r); current.append(r)
            self.audit.append(dict(run_id=r['run_id'], birth_pts=at, bbox=deepcopy(b['bbox']),
                eligible=r['eligible'], site=site, warmed=at-self.warm_since >= p.birth_lookback-1e-9))
        events = []
        for r in current:
            if r['eligible'] and not r['emitted'] and r['count'] >= 2 and at-r['first_pts'] >= p.birth_support_seconds-1e-9:
                r['emitted'] = True
                events.append(dict(status='침입 의심', reason='new_observation_just_inside_gate',
                    run_id=r['run_id'], birth_pts=r['first_pts'], decision_time_pts=at,
                    evidence_until_pts=at, first_actual_bbox=deepcopy(r['first_bbox']),
                    current_actual_bbox=deepcopy(r['bbox']), birth_site=deepcopy(r['site']),
                    observation_refs=deepcopy(r['observations']), automatic_confirmation=False,
                    human_verified=False, identity_verified=False,
                    warning='Camera-local appearance cue; redetection, overlap and normal occlusion remain possible.'))
        return events


def revised_scene(original, revision):
    """Allow inside geometry and an explicitly selected optional inner boundary.

    The original outer line and all other policy/calibration fields stay fixed.
    The optional inner contour is validated separately; no source is rewritten.
    """
    before, after = deepcopy(original), deepcopy(revision)
    before['zones'].pop('inside'); after['zones'].pop('inside')
    before.pop('inner_line', None); after.pop('inner_line', None)
    if 'inner_line' in revision:
        from .dual_boundary import Corridor
        Corridor(revision)
    if before != after:
        raise ValueError('Only zones.inside and optional inner_line may change in the approved scene revision')
    Gate(revision)
    return deepcopy(revision)
