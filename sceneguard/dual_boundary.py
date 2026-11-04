"""Optional finite dual-boundary passage from saved measurements, never feet/ID truth.

``inner_line`` is a normalized ordered polyline. ``line`` remains the original
outer segment. No detector, tracker, image/flow generation, or truth clock enters
this module. All state is advanced in recording order and is bounded by actual
continuity, the adopted pair horizon and an explicit episode horizon.
"""
from collections import Counter, defaultdict, deque
from copy import deepcopy
import math

from .approach_disappearance import Policy, center, polygon, validate_scene
from .directional_loss import path_map, inside, pixel_box
from .gate_observation import GateObservationDirection
from .incident_cards import GroupPolicy
from .incident_lifecycle import digest
from .incident_outcome_scope import ScopedIncidentLifecycle
from .lifecycle_followup import ObservationHistory

RULE = 'dual_boundary_passage_v1'
PROXY = 'actual_bbox_height_65_percent_not_reconstructed_feet'
# An episode may retain a measured origin beyond the old 3s lookback, but not
# indefinitely through a gate corridor. This is a common bound, not video tuning.
EPISODE_SECONDS = 60.0


def active(scene):
    return 'inner_line' in scene


def guarded(previous):
    """Old rules cannot promote a dual-boundary input before causal replay."""
    return dict(deepcopy(previous), automatic_confirmation=False, notify=False,
        status='침입 의심', rule_id=RULE,
        reason='dual_boundary_requires_causal_lifecycle', observation_proxy=PROXY)


def cross(a, b):
    return a[0]*b[1]-a[1]*b[0]


def sub(a, b):
    return (a[0]-b[0], a[1]-b[1])


def nearest(p, a, b):
    v = sub(b, a); length = math.hypot(*v)
    t = sum(x*y for x, y in zip(sub(p, a), v))/length**2
    q = tuple(a[k]+max(0., min(1., t))*v[k] for k in (0, 1))
    return math.dist(p, q), t, q


class Corridor:
    def __init__(self, scene):
        validate_scene(scene)
        self.scene = deepcopy(scene); self.size = scene['source_size']
        raw = scene['inner_line']
        if (not isinstance(raw, list) or len(raw) < 2 or any(len(p) != 2 or any(
                type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1
                for v in p) for p in raw)):
            raise ValueError('inner_line requires a normalized finite polyline')
        self.outer = [tuple(p[k]*self.size[k] for k in (0, 1)) for p in scene['line']]
        inner = [tuple(p[k]*self.size[k] for k in (0, 1)) for p in raw]
        direct = math.dist(self.outer[0], inner[0])+math.dist(self.outer[-1], inner[-1])
        reverse = math.dist(self.outer[0], inner[-1])+math.dist(self.outer[-1], inner[0])
        self.inner_reversed = reverse < direct
        self.inner = inner[::-1] if self.inner_reversed else inner
        self.poly = self.outer+self.inner[::-1]
        edges = list(zip(self.poly, self.poly[1:]+self.poly[:1]))
        if any(math.dist(a, b) < 1e-6 for a, b in edges):
            raise ValueError('Dual boundary edges must be nondegenerate')
        for i, (a, b) in enumerate(edges):
            c = edges[(i+1) % len(edges)][1]
            v, w = sub(b, a), sub(c, b)
            if abs(cross(v, w)) < 1e-9 and sum(x*y for x, y in zip(v, w)) < 0:
                raise ValueError('Dual boundary contour cannot backtrack')
            for j, (c, d) in enumerate(edges):
                if j <= i+1 or (i == 0 and j == len(edges)-1): continue
                # The crossing helper intentionally ignores parallel motion;
                # contour validation must also reject collinear overlap/touch.
                if (self.intersection(a, b, c, d) is not None or
                        min(nearest(a, c, d)[0], nearest(b, c, d)[0],
                            nearest(c, a, b)[0], nearest(d, a, b)[0]) < 1e-7):
                    raise ValueError('Dual boundary corridor must be simple and finite')
        if abs(sum(cross(a, b) for a, b in edges)) < 1e-6:
            raise ValueError('Dual boundary corridor has no area')
        self.boundaries = {'outer': self.outer, 'inner': self.inner}
        self.normals = {}
        for name, line in self.boundaries.items():
            other = self.inner if name == 'outer' else self.outer
            normals = []
            for a, b in zip(line, line[1:]):
                mid = tuple((a[k]+b[k])/2 for k in (0, 1))
                _, _, target = min(nearest(mid, c, d) for c, d in zip(other, other[1:]))
                v = sub(b, a); n = (-v[1], v[0]); length = math.hypot(*n)
                dot = sum(n[k]*(target[k]-mid[k]) for k in (0, 1))
                if abs(dot) < 1e-6: raise ValueError('Boundary orientation is ambiguous')
                normals.append(tuple(x/length*(1 if dot > 0 else -1) for x in n))
            self.normals[name] = normals

    @staticmethod
    def intersection(p, q, a, b):
        v, w = sub(q, p), sub(b, a); den = cross(v, w)
        if abs(den) < 1e-9: return None
        t, u = cross(sub(a, p), w)/den, cross(sub(a, p), v)/den
        return (t, u) if -1e-9 <= t <= 1+1e-9 and -1e-9 <= u <= 1+1e-9 else None

    def locate(self, point, name):
        line = self.boundaries[name]
        choices = [(nearest(point, a, b)[0], i, nearest(point, a, b)[1])
                   for i, (a, b) in enumerate(zip(line, line[1:]))]
        distance, i, along = min(choices)
        a = line[i]; n = self.normals[name][i]
        return dict(distance=distance, along=along, segment=i,
                    signed=sum((point[k]-a[k])*n[k] for k in (0, 1)))

    def classify(self, row):
        p = center(row, self.size, .65)
        outer, inner = self.locate(p, 'outer'), self.locate(p, 'inner')
        deadband = Policy().min_motion_pixels
        # Classification never extends the two gate endpoints into infinite lines.
        if 0 <= outer['along'] <= 1 and outer['signed'] < -deadband:
            return 'outside'
        inner_finite = ((inner['along'] >= 0 or inner['segment'] > 0) and
            (inner['along'] <= 1 or inner['segment'] < len(self.inner)-2))
        if inner_finite and inner['signed'] < -deadband:
            return 'inside'
        if polygon(p, self.poly): return 'corridor'
        return None

    def intersections(self, a, b):
        result = []
        for name, line in self.boundaries.items():
            for i, (p, q) in enumerate(zip(line, line[1:])):
                hit = self.intersection(a, b, p, q)
                if hit is None: continue
                n = self.normals[name][i]
                motion = sum((b[k]-a[k])*n[k] for k in (0, 1))
                if abs(motion) < 1e-6: continue
                result.append(dict(boundary=name, segment=i, fraction=hit[0],
                    into_corridor=motion > 0, along=hit[1]))
        return sorted(result, key=lambda x:(x['fraction'], x['boundary'], x['segment']))

    def advance_path(self, trackers, point, reference):
        """Opposite nonzero anchors, including every finite on-line sample.

        A touch is not a crossing. Walking along the boundary beyond an endpoint
        invalidates the whole on-line run before any opposite-side arrival.
        """
        result = []
        for name, line in self.boundaries.items():
            loc = self.locate(point, name)
            finite = ((loc['along'] >= -1e-9 or loc['segment'] > 0) and
                (loc['along'] <= 1+1e-9 or loc['segment'] < len(line)-2))
            tracker = trackers.setdefault(name, dict(anchor=None, on_line=[]))
            if abs(loc['signed']) < 1e-7:
                sample = (point, deepcopy(reference), finite, loc)
                if tracker['on_line'] and reference['pts']-tracker['on_line'][0][1]['pts'] > EPISODE_SECONDS:
                    tracker['on_line_expired'] = True
                    tracker['on_line'] = [tracker['on_line'][0], sample]
                elif tracker.get('on_line_expired'):
                    tracker['on_line'] = [tracker['on_line'][0], sample]
                else: tracker['on_line'].append(sample)
                continue
            old = tracker['anchor']; online = tracker['on_line']
            if old is not None and old[2]*loc['signed'] < 0:
                hits = [h for h in self.intersections(old[0], point) if h['boundary'] == name
                    and h['into_corridor'] == (loc['signed'] > 0)]
                if online:
                    if not tracker.get('on_line_expired') and all(sample[2] for sample in online):
                        first = online[0][3]
                        hits = [dict(boundary=name, segment=first['segment'], fraction=0.,
                            into_corridor=loc['signed'] > 0, along=first['along'])]
                    else: hits = []
                for hit in hits:
                    result.append(dict(hit, before=deepcopy(old[1]), after=deepcopy(reference),
                        on_line_observation_refs=[deepcopy(sample[1]) for sample in online]))
            tracker['anchor'] = (point, deepcopy(reference), loc['signed'])
            tracker['on_line'] = []; tracker['on_line_expired'] = False
        return sorted(result, key=lambda h:(h['after']['frame_index'], h['fraction']))

    def audit(self):
        return dict(inner_endpoint_order_reversed=self.inner_reversed,
            outer_pixels=self.outer, inner_pixels=self.inner, finite_corridor_pixels=self.poly,
            observation_proxy=PROXY)


def connected(a, b, size, policy=Policy()):
    aw, ah = a['bbox'][2]-a['bbox'][0], a['bbox'][3]-a['bbox'][1]
    bw, bh = b['bbox'][2]-b['bbox'][0], b['bbox'][3]-b['bbox'][1]
    return (b['frame_index'] == a['frame_index']+1
        and 0 < b['pts']-a['pts'] <= policy.max_direction_step+1e-9
        and max(aw/bw, bw/aw, ah/bh, bh/ah) <= policy.scale_jump
        and math.dist(center(a, size), center(b, size)) <= .5*max(ah, bh)*size[1])


def contiguous_ambiguities(previous, current, size):
    """Competing actual-box edges, before greedy birth bookkeeping chooses one.

    Inspect the complete causal frame pair, including actual footprints omitted
    from observation runs as nested duplicates. A selected run or numeric ID
    cannot make a one-to-many or many-to-one geometric association unique.
    """
    def rows(frame):
        return [dict(pts=frame['pts'], frame_index=frame['frame_index'],
                     cache_index=b['cache_index'], bbox=b['bbox'])
                for b in frame['actual_boxes']
                if b.get('observed') is not False and b['score'] >= .25]
    sources, targets = rows(previous), rows(current)
    edges = [(a, b) for a in sources for b in targets if connected(a, b, size)]
    outgoing = Counter(a['cache_index'] for a, b in edges)
    incoming = Counter(b['cache_index'] for a, b in edges)
    return [dict(source=deepcopy(a), target=deepcopy(b),
                 source_successors=outgoing[a['cache_index']],
                 target_predecessors=incoming[b['cache_index']])
            for a, b in edges
            if outgoing[a['cache_index']] > 1 or incoming[b['cache_index']] > 1]


class PassageState:
    """Compact causal episode. Only measured continuity or explicit proof inherits it."""
    def __init__(self, corridor):
        self.corridor = corridor; self.policy = Policy(); self.last = None
        self.reset('origin_not_stable')

    def reset(self, reason):
        self.origin = None; self.origin_refs = []; self.streak = []
        self.entry = None; self.exit = None; self.destination = []
        self.tail = deque(); self.associations = []; self.started = None
        self.boundary_paths = {}
        self.reason = reason; self.proof = None

    def stable(self, rows):
        return (len(rows) >= self.policy.stable_observations and
            rows[-1]['pts']-rows[0]['pts'] >= self.policy.stable_seconds-1e-9)

    def step(self, row, *, association=None):
        row = deepcopy(row)
        if row.get('observed') is False or row.get('confirmed') is False or row.get('predicted') is True:
            raise ValueError('Prediction-only rows cannot advance passage')
        b = row['bbox']
        if (len(b) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) for v in b)
                or not 0 <= b[0] < b[2] <= 1 or not 0 <= b[1] < b[3] <= 1):
            raise ValueError('Actual normalized bbox required')
        if self.last and (row['pts'] <= self.last['pts'] or row['frame_index'] <= self.last['frame_index']):
            raise ValueError('Passage must advance causal actual observations')
        previous = self.last
        continuous = previous is not None and connected(previous, row, self.corridor.size)
        if previous is not None and not continuous and association is None:
            self.reset('disconnected_actual_box_path')
        if self.started is not None and row['pts']-self.started > EPISODE_SECONDS:
            self.reset('episode_origin_expired')
        if association is not None:
            self.associations.append(deepcopy(association))
        # Exact-on-line samples need nonzero anchors on both sides.
        # Missing boxes cannot create an interpolated bbox crossing.
        if not continuous: self.boundary_paths = {}
        hits = self.corridor.advance_path(self.boundary_paths,
            center(row, self.corridor.size, .65), row)
        if association is not None:
            hits = association.get('boundary_crossings', [])
        side = self.corridor.classify(row)
        if self.origin:
            entry_name = 'outer' if self.origin == 'outside' else 'inner'
            exit_name = 'inner' if self.origin == 'outside' else 'outer'
            for hit in hits:
                ref = dict(hit, measurement='saved_point_path' if association is not None else 'actual_bbox_65_percent_proxy_path')
                if association is not None:
                    ref.update(source_actual_bbox=deepcopy(previous), destination_actual_bbox=deepcopy(row))
                if hit['boundary'] == entry_name and hit['into_corridor']:
                    self.entry = ref; self.exit = None
                elif self.entry and hit['boundary'] == exit_name and not hit['into_corridor']:
                    self.exit = ref
                elif hit['boundary'] == exit_name and hit['into_corridor']:
                    self.exit = None; self.destination = []
                elif hit['boundary'] == entry_name and not hit['into_corridor']:
                    self.entry = None; self.exit = None; self.destination = []
            destination = 'inside' if self.origin == 'outside' else 'outside'
            if side is None and self.entry:
                self.entry = None; self.exit = None; self.destination = []
                self.reason = 'left_finite_corridor_without_opposing_passage'
            if side == destination and self.exit:
                if self.proof is None: self.destination.append(row)
                if self.proof is None and self.stable(self.destination):
                    self.proof = dict(origin_side=self.origin, direction=self.origin+'_to_'+destination,
                        origin_observation_refs=deepcopy(self.origin_refs), entry=deepcopy(self.entry),
                        exit=deepcopy(self.exit), destination_observation_refs=deepcopy(self.destination),
                        associations=deepcopy(self.associations), observation_proxy=PROXY)
                    self.reason = 'measured_opposing_boundary_passage'
            else:
                self.destination = []
                self.reason = 'corridor_observation_not_passage' if self.entry else 'no_ordered_finite_boundary_passage'
        if side in ('outside', 'inside') and (not self.origin or side == self.origin):
            if self.streak and self.corridor.classify(self.streak[-1]) != side: self.streak = []
            self.streak.append(row)
            # Stable evidence is a bounded anchor, not the full history.
            while len(self.streak) > self.policy.stable_observations and self.streak[-1]['pts']-self.streak[1]['pts'] >= self.policy.stable_seconds:
                self.streak.pop(0)
            if self.stable(self.streak):
                if self.origin is None: self.started = row['pts']
                self.origin = side; self.origin_refs = deepcopy(self.streak)
                if not self.entry: self.started = row['pts']
        else: self.streak = []
        self.last = row; self.tail.append(row)
        while self.tail and row['pts']-self.tail[0]['pts'] > self.policy.direction_window+1e-9:
            self.tail.popleft()
        return self.proof

    def decision(self, at, *, loss=False, direction=None, continuous=True, ambiguous=False):
        result = dict(rule_id=RULE, automatic_confirmation=False, notify=False,
            status='침입 의심', reason=self.reason, decision_time_pts=at, evidence_until_pts=at,
            last_observed_pts=None if self.last is None else self.last['pts'],
            observation_proxy=PROXY, human_verified=False, identity_verified=False,
            enabled_directions=deepcopy(self.corridor.scene['directions']),
            origin_side=self.origin, origin_observation_refs=deepcopy(self.origin_refs),
            entry=deepcopy(self.entry), exit=deepcopy(self.exit), associations=deepcopy(self.associations),
            loss_wait_required=loss, loss_wait=self.policy.loss_wait)
        if ambiguous: return dict(result, reason='competing_or_untrusted_successor')
        if not continuous: return dict(result, reason='source_gap_not_person_loss')
        if self.last is None: return result
        if self.started is not None and at-self.started > EPISODE_SECONDS:
            return dict(result, reason='episode_origin_expired')
        if self.proof:
            result.update(passage=deepcopy(self.proof), direction=self.proof['direction'],
                entry=deepcopy(self.proof['entry']), exit=deepcopy(self.proof['exit']),
                origin_observation_refs=deepcopy(self.proof['origin_observation_refs']))
        elif loss:
            if at-self.last['pts'] < self.policy.loss_wait-1e-6:
                return dict(result, reason='waiting_since_last_actual_observation')
            if not self.origin or not self.entry:
                return dict(result, reason='loss_missing_origin_or_measured_entry')
            terminal = center(self.last, self.corridor.size, .65)
            origin_boundary = 'outer' if self.origin == 'outside' else 'inner'
            other = 'inner' if self.origin == 'outside' else 'outer'
            a, b = self.corridor.locate(terminal, origin_boundary), self.corridor.locate(terminal, other)
            # Mere approach/lingering near the entry edge never supplies loss proof.
            if self.corridor.classify(self.last) != 'corridor' or a['distance'] <= b['distance']:
                return dict(result, reason='loss_terminal_not_in_opposing_corridor_half')
            tail = list(self.tail)
            if len(tail) < 3 or any(not connected(x, y, self.corridor.size) for x, y in zip(tail, tail[1:])):
                return dict(result, reason='loss_recent_actual_path_missing')
            progress = self.corridor.locate(center(tail[0], self.corridor.size, .65), other)['distance']-b['distance']
            expected = 'inward' if self.origin == 'outside' else 'outward'
            if (progress < self.policy.min_motion_pixels or not direction or direction.get('direction') != expected
                    or direction.get('end_pts') is None or not 0 <= self.last['pts']-direction['end_pts'] <= self.policy.direction_window+1e-9):
                return dict(result, reason='loss_fresh_destination_direction_missing', measured_progress_pixels=progress)
            result.update(direction=self.origin+'_to_'+('inside' if self.origin == 'outside' else 'outside'),
                direction_evidence=deepcopy(direction), measured_recent_path=deepcopy(tail),
                measured_progress_pixels=progress, reason='origin_entry_progress_and_directed_corridor_loss')
        else: return result
        if result['direction'] not in self.corridor.scene['directions']:
            return dict(result, reason='passage_direction_disabled')
        return dict(result, status='침입 확인', automatic_confirmation=True, notify=True,
            decision_source='automatic_rule', confirmation_basis='camera_rule_not_manual_or_ground_truth')


class DualBoundaryDirection(GateObservationDirection):
    """Existing saved-path reader, with bounded unique actual-point associations."""
    def __init__(self, frames, scene):
        if any(b.get('predicted') is True for f in frames for b in f['actual_boxes']):
            raise ValueError('Predicted boxes cannot be used as actual measurements')
        self.corridor = Corridor(scene)
        super().__init__(frames, scene)

    def classify(self, event, segment):
        return guarded(event)

    def delayed_raw_loss(self, source, segment, decision_index):
        return guarded(dict(source, decision_time_pts=self.frames[decision_index]['pts']))

    def observed_crossing(self, segment, decision_index, details=None):
        return None

    def successor(self, history, rid, index, *, source_rows=None, allow_same=False):
        rows = history.motion_rows(rid) if source_rows is None else source_rows
        last = rows[-1]; start = last['frame_index']
        at = self.frames[index]['pts']; policy = Policy(); matches = {}
        if not 0 < at-last['pts'] <= policy.pair_seconds+1e-9:
            return dict(successor=None, reason='association_horizon_expired', matches=[])
        if start < self.continuous_start[index]:
            return dict(successor=None, reason='source_gap_not_person_loss', matches=[])
        actual = {r['frame_index']:r for r in rows}; size = self.corridor.size
        for wid, path in self.paths.get(start, {}).items():
            born, seed = self.births[wid]; source = actual.get(born)
            if source is None or source['cache_index'] != seed['cache_index']: continue
            p = path_map(path)
            anchors = [pid for pid in p if inside(p[pid], pixel_box(last['bbox'], size), .15)]
            cohort = self._source_motion_cohort(dict(rows=rows), wid, anchors)
            if len(cohort) < self.policy.minimum_points: continue
            maps = {}; valid = True
            for i in range(start, index+1):
                if wid not in self.paths.get(i, {}): valid = False; break
                maps[i] = path_map(self.paths[i][wid])
            if not valid: continue
            common = set(cohort).intersection(*(set(m) for m in maps.values()))
            if len(common) < self.policy.minimum_points or len(common)/len(cohort) < .6: continue
            for box in self.frames[index]['actual_boxes']:
                if box.get('observed') is False or box['score'] < .25: continue
                ids = [pid for pid in common if inside(maps[index][pid], pixel_box(box['bbox'], size))]
                if len(ids) < self.policy.minimum_points or len(ids)/len(cohort) < .6: continue
                row = dict(pts=at, frame_index=index, cache_index=box['cache_index'], bbox=box['bbox'])
                a, b = last['bbox'], row['bbox']; ah, bh = a[3]-a[1], b[3]-b[1]
                aw, bw = a[2]-a[0], b[2]-b[0]
                if (max(aw/bw, bw/aw, ah/bh, bh/ah) > policy.scale_jump or
                        math.dist(center(last, size), center(row, size)) > policy.pair_distance_heights*max(ah, bh)*size[1]): continue
                # Cohort displacement must follow the actual box displacement.
                delta = sub(center(row, size), center(last, size))
                vectors = [sub(self.corrected(index, wid)[pid], self.corrected(start, wid)[pid]) for pid in ids]
                if (math.hypot(*delta) < policy.min_motion_pixels or
                        sum(sum(v[k]*delta[k] for k in (0, 1)) > 0 for v in vectors)/len(vectors) < .6): continue
                # Count every physically plausible actual endpoint before run
                # mapping. Birth deduplication cannot remove a competitor from
                # the saved-point association proof across a missing-box gap.
                choices = history.by_reference.get((index, box['cache_index']), set())
                dest = next(iter(choices)) if len(choices) == 1 else None
                if dest is not None and ((dest == rid and not allow_same) or
                        history.current_key(dest) != dest): dest = None
                hits = defaultdict(list)
                for pid in ids:
                    trackers = {}
                    for i in range(start, index+1):
                        reference = dict(frame_index=i, pts=self.frames[i]['pts'], point_id=pid,
                            point_original_pixels=list(maps[i][pid]))
                        for hit in self.corridor.advance_path(trackers, maps[i][pid], reference):
                            hits[(hit['boundary'], hit['segment'], hit['into_corridor'])].append((pid, i, hit))
                crossings = []
                for (boundary, segment, inward), observations in hits.items():
                    support = {p for p, _, _ in observations}
                    if len(support) >= self.policy.minimum_points and len(support)/len(cohort) >= .6:
                        _, i, hit = min(observations, key=lambda x:x[1])
                        crossings.append(dict(hit, frame_index=i, point_ids=sorted(support), window_id=wid))
                evidence = dict(successor=dest, window_id=wid, point_ids=sorted(ids), source_frame=start,
                    target_frame=index, target_cache_index=box['cache_index'], coverage=len(ids)/len(cohort),
                    gap_seconds=at-last['pts'], actual_correspondence=True, identity_verified=False,
                    missing_box_interval_is_not_measured_box_path=True,
                    boundary_crossings=sorted(crossings, key=lambda x:(x['frame_index'],x['fraction'])))
                ci = box['cache_index']
                if ci not in matches or matches[ci]['coverage'] < evidence['coverage']: matches[ci] = evidence
        successor = next(iter(matches.values()))['successor'] if len(matches) == 1 else None
        return dict(successor=successor,
            reason='unique_saved_moving_point_successor' if successor is not None else
                'competing_successors' if len(matches) > 1 else 'no_trusted_successor', matches=list(matches.values()))


def replay(baseline, history, portal_events, runs, frames, scene, region, *, portal_gate=None):
    """Single guarded production lifecycle; old positive decisions are only audits.

    Every source candidate is preserved. No old positive resolution, raw-loss
    retry, outward release or preserved-confirmation branch is executed here.
    Actual measured states may predate suspicion, but may never predate the
    recording's current causal prefix. Only pending, exactly bound evidence can
    consume the measured outcome and proven confirmations remain sticky.
    """
    from .portal_births import PortalGate
    from .passage_audit import audit_all_runs
    if abs(baseline['policy']['loss_wait']-Policy().loss_wait) > 1e-6:
        raise ValueError('Keep the adopted one-second loss wait')
    engine = DualBoundaryDirection(frames, scene)
    obs = ObservationHistory(runs, frames)
    events = deepcopy(history['events']+list(portal_events))
    if not events or len({e['event_id'] for e in events}) != len(events):
        raise ValueError('Distinct nonempty candidate stream required')
    scopes = {tuple(e[k] for k in ('session_id', 'camera_id', 'gate_id')) for e in events}
    if len(scopes) != 1: raise ValueError('One recording/camera/gate per replay')
    portal = portal_gate or PortalGate(scene, region, events[0]['camera_id'])
    life = ScopedIncidentLifecycle(GroupPolicy(**history['policy']),
        namespace=RULE+':'+digest(dict(scope=next(iter(scopes)), scene=scene, region=region))[:16])
    segments = {s['id']: s for s in baseline['segments']}
    by_time = {f['pts']:i for i, f in enumerate(frames)}
    scheduled = defaultdict(list)
    for event in events:
        at = event['decision_time_pts']
        if at not in by_time: raise ValueError('Candidate requires an actual source clock')
        scheduled[by_time[at]].append(event)
    states = {}; audits = []; counts = Counter(); ambiguous = set(); emitted = set()
    suppressed = [dict(event_id=d.get('event_id'), reason='legacy_confirmation_suppressed_in_dual_mode',
        source_rule=d.get('rule_id'), decision_time_pts=d['decision_time_pts'])
        for d in history['decisions'] if d.get('automatic_confirmation')]

    def bind(event):
        if event['source_ref'].get('collection') != 'existing_alerts':
            return obs.bind(event, segments)
        raw = event['source_event']; at = event['decision_time_pts']
        anchors = [raw.get('observed_pts_before'), raw.get('observed_pts_after'), at]
        choices = []
        if (all(type(t) in (int, float) and math.isfinite(t) for t in anchors)
                and 0 <= anchors[0] < anchors[1] <= at
                and raw.get('emitted_at_pts') == at):
            for segment in segments.values():
                if segment['raw_id'] != raw.get('track_id'): continue
                if all(any(abs(row['pts']-t) < 1e-7 for row in segment['rows']) for t in anchors):
                    choices.append(segment)
        proxy = deepcopy(event)
        proxy['source_event'] = dict(raw, segment=choices[0]['id'] if len(choices) == 1 else None)
        bound = obs.bind(proxy, segments)
        bound['event'] = deepcopy(event)
        bound['binding']['existing_alert_anchor_segment_choices'] = [s['id'] for s in choices]
        bound['binding']['existing_alert_binding_is_not_passage_proof'] = True
        return bound

    def audit(rid, decision):
        # Log changes, not duplicate every frame of a lingering observation.
        key = (rid, decision['reason'], decision['last_observed_pts'] if decision['automatic_confirmation'] else None)
        if key in emitted: return
        emitted.add(key); audits.append(dict(run_id=rid, decision_time_pts=decision['decision_time_pts'],
            reason=decision['reason'], outcome=RULE if decision['automatic_confirmation'] else None,
            source_decision=deepcopy(decision)))
        counts[decision['reason']] += 1

    for index, frame in enumerate(frames):
        at = frame['pts']; obs.advance(frame)
        if index and at-frames[index-1]['pts'] > obs.gap_seconds+1e-9:
            for state in states.values():
                state.reset('source_gap_not_person_loss'); state.last = None
            ambiguous.clear()
        current = dict(obs.scheduled[index])
        if index:
            competition = contiguous_ambiguities(frames[index-1], frame, engine.corridor.size)
            affected = set()
            for edge in competition:
                for row in (edge['source'], edge['target']):
                    affected.update(obs.current_key(rid) for rid in obs.by_reference.get(
                        (row['frame_index'], row['cache_index']), ()))
            # Conservative lineage veto: later unique boxes do not silently
            # revive uncertain origin/proof or confirm its older candidates.
            # Episode recovery needs separate evidence-ownership isolation.
            ambiguous.update(affected)
            if competition:
                audits.append(dict(decision_time_pts=at,
                    reason='competing_contiguous_actual_box_associations',
                    run_ids=sorted(affected), association_edges=competition))
                counts['competing_contiguous_actual_box_associations'] += 1
        for rid, row in current.items():
            if obs.current_key(rid) != rid: continue
            state = states.setdefault(rid, PassageState(engine.corridor))
            association = None
            if state.last and not connected(state.last, row, engine.corridor.size):
                prefix = [r for r in obs.motion_rows(rid) if r['pts'] <= state.last['pts']]
                handoff = engine.successor(obs, rid, index, source_rows=prefix, allow_same=True)
                if handoff['successor'] == rid:
                    association = handoff['matches'][0]
                elif handoff['reason'] == 'competing_successors':
                    ambiguous.add(rid)
            state.step(row, association=association)
        candidates = [bind(e) for e in scheduled[index]]
        pending = defaultdict(list)
        for eid in life.pending():
            key = life.evidence[eid]['observation_key']
            if key is not None: pending[key].append(eid)
        for candidate in candidates:
            if candidate['observation_key'] is not None:
                pending[candidate['observation_key']].append(candidate['event']['event_id'])
        resolutions = []; proposals = {}
        # Track origin continuity before the first candidate too. A later loss
        # candidate must not erase a pre-gate origin just because it arrived late.
        for rid, state in list(states.items()):
            if obs.current_key(rid) != rid or state.last is None or state.last['frame_index'] == index: continue
            if at-state.last['pts'] > Policy().pair_seconds+1e-9: continue
            handoff = engine.successor(obs, rid, index)
            if handoff['reason'] == 'competing_successors':
                ambiguous.add(rid)
                audit(rid, state.decision(at, ambiguous=True))
            if handoff['successor']:
                dest = handoff['successor']
                # Never overwrite a run already observed alongside this source.
                if obs.rows[dest][0]['pts'] <= state.last['pts']:
                    ambiguous.add(rid); continue
                proposals[rid] = handoff
        destinations = Counter(h['successor'] for h in proposals.values())
        for rid, handoff in proposals.items():
            dest = handoff['successor']
            if destinations[dest] != 1:
                ambiguous.add(rid); ambiguous.add(dest)
                audit(rid, states[rid].decision(at, ambiguous=True)); continue
            inherited = deepcopy(states[rid]); row = obs.rows[dest][-1]
            # Only the endpoint has correspondence proof. Earlier unbound rows
            # cannot be silently reconstructed or credited as a box path.
            inherited.step(row, association=handoff['matches'][0])
            states[dest] = inherited
            if rid in ambiguous: ambiguous.add(dest)
            ids = pending.pop(rid, [])
            if ids:
                resolution = dict(kind='observation_handoff', event_ids=sorted(ids), observation_key=rid,
                    next_observation_key=dest, decision_time_pts=at, evidence_until_pts=at,
                    actual_correspondence=True, evidence=handoff, human_verified=False)
                resolution['resolution_id'] = digest(resolution); resolutions.append(resolution)
                pending[dest].extend(ids)
            obs.link(rid, dest); counts['observation_handoffs'] += 1
            audits.append(dict(run_id=rid, decision_time_pts=at, reason=handoff['reason'], handoff=handoff))
        for rid, ids in pending.items():
            state = states.get(rid)
            if state is None or state.last is None: continue
            loss = state.last['frame_index'] != index
            if loss and at-state.last['pts'] > Policy().pair_seconds+1e-9:
                audit(rid, dict(state.decision(at), reason='association_horizon_expired')); continue
            direction = engine.direction(dict(id=rid, raw_id=None, rows=obs.motion_rows(rid))) if loss else None
            decision = state.decision(at, loss=loss, direction=direction,
                continuous=state.last['pts'] >= obs.continuous_since-1e-9, ambiguous=rid in ambiguous)
            audit(rid, decision)
            if not decision['automatic_confirmation']: continue
            if decision['last_observed_pts'] > at: raise ValueError('Future passage evidence')
            physical = (dict(kind='passage', entry=decision['entry'], exit=decision['exit'])
                if decision.get('passage') else dict(kind='loss', last=state.last, entry=decision['entry']))
            decision.update(segment=rid, event_ids=sorted(ids), physical_evidence_ref=deepcopy(physical))
            resolution = dict(kind='preserved_confirmation', event_ids=sorted(ids), observation_key=rid,
                decision_time_pts=at, evidence_until_pts=at, confirmation_source=RULE,
                source_decision=decision, last_observed_pts=state.last['pts'],
                physical_crossing_ref=dict(direction=decision['direction'], evidence=physical))
            resolution['resolution_id'] = digest(resolution); resolutions.append(resolution)
        if candidates or resolutions: life.process(at, candidates, resolutions)
        # A consumed passage can start a new measured episode on its arrival
        # side. Previously confirmed evidence remains sticky in the lifecycle.
        for resolution in resolutions:
            if resolution.get('confirmation_source') != RULE: continue
            rid = resolution['observation_key']; state = states[rid]
            proof = state.proof
            if proof:
                destination = deepcopy(proof['destination_observation_refs'])
                state.reset('previous_passage_consumed'); state.last = None
                for row in destination: state.step(row)
    result = life.export()
    if {e['event_id']:e for e in result['events']} != {e['event_id']:e for e in events}:
        raise ValueError('Dual boundary replay edited source candidates')
    result.update(video_id=history['video_id'], source_window=deepcopy(history['source_window']),
        available_after_pts=history.get('available_after_pts', history['source_window'][1]),
        binding_audit=obs.bindings, followup_audit=audits, followup_counts=dict(counts),
        dual_boundary_audit=dict(rule_id=RULE, geometry=engine.corridor.audit(),
            suppressed_legacy_confirmations=suppressed, episode_seconds=EPISODE_SECONDS,
            association_horizon_seconds=Policy().pair_seconds, loss_wait=Policy().loss_wait),
        preserved_confirmation_source_pts={}, direction_rule_changed=True,
        source_end_forced_release=False, detector_calls=0, tracker_calls=0, flow_calls=0, vlm_calls=0)
    return result, audit_all_runs(runs, frames, result, engine, portal)


def validate_decision(decision, at):
    """Lifecycle guard: dual resolutions must carry causal measured support."""
    if (decision.get('rule_id') != RULE or decision.get('automatic_confirmation') is not True
            or decision.get('decision_time_pts') != at or decision.get('evidence_until_pts') != at
            or type(decision.get('last_observed_pts')) not in (int, float)
            or not math.isfinite(decision['last_observed_pts']) or decision['last_observed_pts'] > at
            or decision.get('direction') not in ('outside_to_inside', 'inside_to_outside')
            or not decision.get('origin_observation_refs') or not decision.get('entry')
            or decision.get('direction') not in decision.get('enabled_directions', [])
            or decision.get('origin_side') != decision.get('direction', '').split('_to_')[0]
            or not decision.get('physical_evidence_ref')):
        raise ValueError('Dual boundary confirmation requires causal origin and measured path')
    if decision.get('passage'):
        if not decision.get('exit') or not decision['passage'].get('destination_observation_refs'):
            raise ValueError('Dual boundary visible passage requires opposing measured destination')
    elif (decision.get('reason') != 'origin_entry_progress_and_directed_corridor_loss'
            or not decision.get('measured_recent_path') or not decision.get('direction_evidence')
            or at-decision['last_observed_pts'] < Policy().loss_wait-1e-6):
        raise ValueError('Dual boundary loss requires actual absence and fresh target direction')
    def check(value):
        if isinstance(value, dict):
            if 'pts' in value and value['pts'] > at+1e-9: raise ValueError('Future dual boundary observation')
            for child in value.values(): check(child)
        elif isinstance(value, (list, tuple)):
            for child in value: check(child)
    check(decision)
