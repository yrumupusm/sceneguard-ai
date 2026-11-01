"""EXP-0044: gate-local disappearance plus signed image direction.

No learned action score, visibility veto, raw-ID merge, or manual confirmation.
Automatic confirmation is a fallible camera rule, not verified physical entry.
Coordinates are original pixels; observations and saved paths are read-only.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from copy import deepcopy
import math
import statistics as st


@dataclass(frozen=True)
class DirectionPolicy:
    history_seconds: float = 1.0
    direction_seconds: float = 0.5
    loss_wait: float = 1.0
    minimum_points: int = 3
    moving_pixels: float = 1.0
    normal_pixels: float = 2.0
    normal_fraction: float = 0.35
    near_height_fraction: float = 0.8
    minimum_near_pixels: float = 12.0

    def validate(self):
        if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0
               for v in asdict(self).values()):
            raise ValueError('Positive finite direction policy required')
        if (type(self.minimum_points) is not int or self.minimum_points < 2
                or self.normal_fraction > 1 or self.direction_seconds > self.history_seconds):
            raise ValueError('Invalid direction policy')
        return self


def point(p):
    if len(p) != 2 or any(type(x) not in (int, float) or not math.isfinite(x) for x in p):
        raise ValueError('Finite 2D point required')
    return tuple(float(x) for x in p)


def pixel_box(b, size):
    if len(b) != 4 or not all(type(v) in (int, float) and math.isfinite(v) for v in b):
        raise ValueError('Finite normalized box required')
    if not (0 <= b[0] < b[2] <= 1 and 0 <= b[1] < b[3] <= 1):
        raise ValueError('Nonempty normalized box required')
    return [b[i]*size[i % 2] for i in range(4)]


def inside(p, b, margin=0.):
    dx, dy = (b[2]-b[0])*margin, (b[3]-b[1])*margin
    return b[0]-dx <= p[0] <= b[2]+dx and b[1]-dy <= p[1] <= b[3]+dy


def overlap(a, b):
    area = max(0., min(a[2], b[2])-max(a[0], b[0])) * max(0., min(a[3], b[3])-max(a[1], b[1]))
    return area/max(1e-9, min((a[2]-a[0])*(a[3]-a[1]), (b[2]-b[0])*(b[3]-b[1])))


def gate_geometry(scene):
    size = point(scene['source_size'])
    if min(size) <= 0:
        raise ValueError('Positive source dimensions required')
    a, b = [tuple(x*s for x, s in zip(point(p), size)) for p in scene['line']]
    v = (b[0]-a[0], b[1]-a[1]); length = math.hypot(*v)
    if length <= 1e-9:
        raise ValueError('Nondegenerate gate required')
    normal = (-v[1]/length, v[0]/length)
    # The names inside/outside define orientation, NOT the order of line endpoints.
    centers = {}
    for name in ('outside', 'inside'):
        poly = scene.get('zones', {}).get(name, [])
        if poly:
            points = [point(p) for p in poly]
            centers[name] = tuple(st.mean(p[k] for p in points)*size[k] for k in (0, 1))
    delta = None
    if len(centers) == 2:
        delta = sum((centers['inside'][k]-centers['outside'][k])*normal[k] for k in (0, 1))
    inward = None if delta is None or abs(delta) < 1e-6 else tuple(x*(1 if delta > 0 else -1) for x in normal)
    return dict(size=size, a=a, vector=v, length=length, inward_normal=inward,
                orientation_source='existing_inside_outside_polygon_centers', zone_centers=centers)


def signed(p, geometry):
    n = geometry['inward_normal']
    return None if n is None else sum((p[k]-geometry['a'][k])*n[k] for k in (0, 1))


def gate_distance(p, geometry):
    a, v, length = geometry['a'], geometry['vector'], geometry['length']
    t = max(0., min(1., sum((p[k]-a[k])*v[k] for k in (0, 1))/(length*length)))
    return math.dist(p, (a[0]+t*v[0], a[1]+t*v[1]))


def vectors_direction(vectors, geometry, policy=DirectionPolicy()):
    """Robust average of SAME-point displacements; ignore nearly static residue."""
    policy.validate()
    moving = [point(v) for v in vectors if math.hypot(*point(v)) >= policy.moving_pixels]
    result = dict(direction='unknown', moving_points=len(moving), displacement_pixels=None,
                  inward_pixels=None, probability=None)
    if geometry['inward_normal'] is None or len(moving) < policy.minimum_points:
        return result
    def trimmed(values):
        values = sorted(values); cut = len(values)//10
        return st.mean(values[cut:len(values)-cut] if cut else values)
    mean = tuple(trimmed([v[k] for v in moving]) for k in (0, 1))
    component = sum(mean[k]*geometry['inward_normal'][k] for k in (0, 1))
    magnitude = math.hypot(*mean)
    label = 'unknown' if magnitude < policy.moving_pixels else 'parallel'
    if abs(component) >= policy.normal_pixels and abs(component)/max(magnitude, 1e-9) >= policy.normal_fraction:
        label = 'inward' if component > 0 else 'outward'
    result.update(direction=label, displacement_pixels=list(mean), inward_pixels=component)
    return result


def path_map(path):
    ids, positions = path['point_ids'], path['points_original_pixels']
    if len(ids) != len(positions) or len(set(ids)) != len(ids):
        raise ValueError('Unique permanent point correspondence required')
    return dict(zip(ids, map(point, positions)))


class SavedGateDirection:
    """Use EXP42 saved pixel paths only; never interpret a window timeout as loss."""
    def __init__(self, frames, scene, policy=DirectionPolicy()):
        self.policy = policy.validate(); self.geometry = gate_geometry(scene)
        self.frames = {}; self.paths = {}; self.offsets = {}; self.births = {}
        offset = [0., 0.]; previous = -math.inf; previous_index = -1
        for row in frames:
            at = row['pts']; index = row['frame_index']
            if not math.isfinite(at) or at <= previous or index <= previous_index:
                raise ValueError('Increasing actual frame clocks required')
            previous, previous_index = at, index
            step = point(row.get('camera_step_pixels', (0., 0.)))
            offset = [offset[k]+step[k] for k in (0, 1)]
            self.frames[index] = row; self.offsets[index] = tuple(offset)
            self.paths[index] = {}
            for path in row['point_paths']:
                wid = path['window_id']
                if wid in self.paths[index]:
                    raise ValueError('Duplicate window')
                path_map(path)
                self.paths[index][wid] = path
                if wid not in self.births:
                    if abs(path['seed_pts']-at) > 1e-6:
                        raise ValueError('Full saved window birth required')
                    seed = next((b for b in row['actual_boxes'] if b['cache_index']==path['seed_cache_index']), None)
                    if seed is None or seed.get('observed') is False:
                        raise ValueError('Actual seed detection required')
                    self.births[wid] = (index, seed)

    def corrected(self, index, wid):
        offset = self.offsets[index]
        return {pid: tuple(p[k]-offset[k] for k in (0, 1))
                for pid, p in path_map(self.paths[index][wid]).items()}

    def direction(self, segment):
        rows = segment['rows']; last = rows[-1]; by_frame = {r['frame_index']:r for r in rows}
        size = self.geometry['size']; candidates = []
        # Try the latest usable actual observation, not an extrapolated bbox.
        for target in reversed(rows):
            if last['pts']-target['pts'] > self.policy.history_seconds:
                break
            end = target['frame_index']; bbox = pixel_box(target['bbox'], size)
            for wid, path in self.paths.get(end, {}).items():
                born, seed = self.births[wid]
                observed = by_frame.get(born)
                if observed is None:
                    continue
                exact = observed.get('cache_index') == seed['cache_index']
                if not exact and overlap(pixel_box(observed['bbox'],size), pixel_box(seed['bbox'],size)) < .6:
                    continue
                history = [i for i, r in self.frames.items() if i < end and wid in self.paths[i]
                           and .1-1e-9 <= target['pts']-r['pts'] <= self.policy.history_seconds+1e-9]
                if not history:
                    continue
                ref = min(history, key=lambda i: abs(target['pts']-self.frames[i]['pts']-self.policy.direction_seconds))
                p, q = self.corrected(ref,wid), self.corrected(end,wid)
                raw = path_map(path)
                ids = [pid for pid in q if pid in p and inside(raw[pid],bbox,.15)]
                vec = [tuple(q[pid][k]-p[pid][k] for k in (0,1)) for pid in ids]
                result = vectors_direction(vec,self.geometry,self.policy)
                result.update(window_id=wid, reference_index=ref, end_index=end,
                              reference_pts=self.frames[ref]['pts'], end_pts=target['pts'],
                              point_ids=ids, exact_seed_binding=exact)
                candidates.append(result)
            usable = [r for r in candidates if r['direction'] != 'unknown']
            if usable:
                directions = {r['direction'] for r in usable}
                best = max(usable,key=lambda r:(r['exact_seed_binding'],r['moving_points']))
                if 'inward' in directions and 'outward' in directions:
                    best = dict(best,direction='unknown',reason='opposite_target_paths')
                return dict(best,alternatives=candidates)
        return dict(direction='unknown',reason='no_target_bound_motion',alternatives=candidates)

    def continuation(self, segment, decision_index):
        """Positive same-side continuation can refute ID loss, not intrusion itself.

        One nearby person or surviving background points alone are insufficient:
        require target-bound SAME points in actual endpoint detector boxes.
        Missing/expired paths simply leave the disappearance hypothesis unresolved.
        """
        last = segment['rows'][-1]; start = last['frame_index']; g = self.geometry
        by_frame = {r['frame_index']:r for r in segment['rows']}; votes = []
        target_box = pixel_box(last['bbox'],g['size'])
        for wid, path in self.paths.get(start,{}).items():
            born, seed = self.births[wid]; measured = by_frame.get(born)
            if measured is None or (measured.get('cache_index') != seed['cache_index'] and
                overlap(pixel_box(measured['bbox'],g['size']),pixel_box(seed['bbox'],g['size'])) < .6):
                continue
            p = path_map(path)
            anchor_ids = [pid for pid in p if inside(p[pid],target_box,.15)]
            for index, row in self.frames.items():
                if not start < index <= decision_index or wid not in self.paths[index]:
                    continue
                q = path_map(self.paths[index][wid])
                common = [pid for pid in anchor_ids if pid in q]
                for detected in row['actual_boxes']:
                    if detected.get('observed') is False or detected.get('score',0.) < .25:
                        continue
                    b = pixel_box(detected['bbox'],g['size'])
                    ids = [pid for pid in common if inside(q[pid],b)]
                    if len(ids) < self.policy.minimum_points or len(ids)/max(1,len(anchor_ids)) < .6:
                        continue
                    # Gate and observed boxes use original pixels. Camera-corrected
                    # coordinates are only for motion, not this fixed gate test.
                    sides = [(signed(p[pid],g),signed(q[pid],g)) for pid in ids]
                    crossing = any(a is not None and ((a < -2 and z > 2) or
                        (a > 2 and z < -2)) for a,z in sides)
                    same = [a is not None and a*z > 0 for a,z in sides]
                    if crossing:
                        votes.append('crossing')
                    elif index == decision_index and sum(same)/len(same) >= .6:
                        votes.append('same_side')
        if 'crossing' in votes:
            return 'cross_side_observation'
        return 'same_side_continuation' if 'same_side' in votes else 'unresolved'

    def classify(self, event, segment):
        p = self.policy; last = segment['rows'][-1]; at = event['decision_time_pts']
        result = dict(segment=segment['id'], raw_id=segment['raw_id'], decision_time_pts=at,
                      last_observed_pts=last['pts'], status='침입 의심', notify=True,
                      decision_source='automatic_rule', human_verified=False, identity_verified=False,
                      automatic_confirmation=False, rule_id='gate_direction_loss_v1')
        ending = next((i for i,r in self.frames.items() if abs(r['pts']-at)<1e-6),None)
        if ending is None or at-last['pts'] < p.loss_wait-1e-6:
            return dict(result,status='판단 불가',notify=False,reason='loss_wait_not_observed')
        # Preserve positive visual continuation separately from the alarm status.
        continued = self.continuation(segment,ending)
        direction = self.direction(segment)
        rows = [r for r in segment['rows'] if last['pts']-r['pts'] <= p.history_seconds+1e-9]
        heights = [(r['bbox'][3]-r['bbox'][1])*self.geometry['size'][1] for r in rows]
        radius = max(p.minimum_near_pixels,st.median(heights)*p.near_height_fraction)
        bbox = pixel_box(last['bbox'],self.geometry['size'])
        center = ((bbox[0]+bbox[2])/2,(bbox[1]+bbox[3])/2)
        near = gate_distance(center,self.geometry) <= radius
        result.update(direction=direction,continuation=continued,near_gate_at_loss=near,
                      last_actual_bbox=last['bbox'], last_actual_center_pixels=center,
                      paired_point_count=len(direction.get('point_ids', [])),
                      gate_distance_pixels=gate_distance(center,self.geometry),
                      near_radius_pixels=radius,evidence_until_pts=at)
        # Continuing to be visible is NOT a negative intrusion verdict.
        if continued == 'cross_side_observation':
            return dict(result,reason='visible_cross_side_keep_suspicion')
        if continued == 'same_side_continuation':
            return dict(result,status='판단 불가',notify=False,reason='id_ended_but_observation_continues')
        if near and direction['direction'] == 'inward':
            return dict(result,status='침입 확인',automatic_confirmation=True,
                        reason='inward_motion_then_gate_loss',
                        confirmation_basis='camera_rule_not_manual_or_ground_truth')
        return dict(result,reason='gate_loss_with_outward_or_unclear_direction' if near
                    else 'existing_suspicion_without_terminal_gate_proximity')


def annotated_bundle(baseline, decisions, group):
    """Keep all raw candidates in grouping; decisions are a separate immutable layer.

    Existing crossing alerts are retained. A confirmed status never overwrites
    manual review. A stronger status is a card update, not a per-person popup.
    """
    by_id = {d['event_id']:d for d in decisions}
    if len(by_id) != len(decisions) or not set(by_id) <= {e['event_id'] for e in baseline['events']}:
        raise ValueError('Decisions must uniquely reference original events')
    events = baseline['events']
    review = []
    for e in events:
        d = by_id.get(e['event_id'])
        protected = any(o['decision_time_pts']<=e['decision_time_pts'] and
                        bool(set(o['track_ids'])&set(e['track_ids'])) and
                        o['source_event'].get('reason') != 'recent_gate_presence_then_loss'
                        for o in events)
        if d and not d['notify'] and not protected:
            review.append(e['event_id'])
    result = group(deepcopy(events), review)
    def decorate(card):
        confirmations = [by_id[eid] for eid in card['event_ids'] if eid in by_id
                         and by_id[eid]['automatic_confirmation']]
        card.update(automatic_status='침입 확인' if confirmations else '침입 의심',
                    automatic_confirmation=bool(confirmations),human_verified=False,
                    decision_source='automatic_rule',
                    first_confirmation_pts=min((d['decision_time_pts'] for d in confirmations),default=None))
    for card in result['cards']:
        decorate(card)
    for row in result['timeline']:
        if 'card' in row:
            decorate(row['card'])  # prefix membership: no future confirmation leakage
    result['alert_cards'] = [deepcopy(c) for c in result['cards'] if c['notification_eligible']]
    result['review_only_cards'] = [deepcopy(c) for c in result['cards'] if not c['notification_eligible']]
    result.update(experiment='EXP-0044',decisions=deepcopy(decisions),
                  rule_id='gate_direction_loss_v1',manual_reviews_modified=False,
                  live_notifications_enabled=False,accuracy=None)
    return result
