"""Directional geometry and independent gate loss/appearance evidence.

Reuse legacy policies/lifecycle. A source approach and a new destination box are
separate event evidence, never identity correspondence or an invisible path.
"""
from bisect import bisect_left
from copy import deepcopy
import math

from .approach_disappearance import Policy, center, polygon
from .directional_loss import SavedGateDirection, gate_geometry
from .gate_episode_evidence import EpisodePolicy, Gate, association
from .incident_lifecycle import digest

RULE = 'directional_loss_appearance_v1'


def boundary_zone(row, scene):
    """Bottom-center membership for new directional evidence only."""
    found = [name for name, poly in scene['zones'].items()
             if polygon(center(row, (1,1), 1.), poly)]
    return found[0] if len(found) == 1 else None


def source_scene(scene, origin, bbox=None):
    if origin != 'inside' or 'inner_line' not in scene:
        return scene
    lines = list(zip(scene['inner_line'], scene['inner_line'][1:]))
    if bbox is not None:
        line = min(lines, key=lambda line: BoundaryGate(dict(scene,line=line)).locate(bbox)['distance_pixels'])
    else:
        line = lines[0]
    # Preserve the legacy signed-alert orientation when the user draws the
    # inner contour in the opposite endpoint order.
    outer = scene['line']; size = scene['source_size']
    if sum((outer[1][k]-outer[0][k])*(line[1][k]-line[0][k])*size[k]**2 for k in (0,1)) < 0:
        line = line[::-1]
    return dict(scene, line=list(line))


class BoundaryGate(Gate):
    """Bottom-center geometry on a finite source polyline, without new states."""
    def __init__(self, scene, origin=None):
        self.lines = (list(zip(scene['inner_line'],scene['inner_line'][1:]))
                      if origin == 'inside' and 'inner_line' in scene else [scene['line']])
        if not self.lines:
            raise ValueError('A finite source boundary is required')
        super().__init__(dict(scene,line=list(self.lines[0])))
        self.parts = [Gate(dict(scene,line=list(line))) for line in self.lines]

    def locate(self, bbox, *, birth=True):
        b = self.box(bbox); c = ((b[0]+b[2])/2,b[3]); choices = []
        for index, gate in enumerate(self.parts):
            along = sum((c[k]-gate.a[k])*gate.v[k] for k in (0,1))/gate.length**2
            closest = tuple(gate.a[k]+min(1.,max(0.,along))*gate.v[k] for k in (0,1))
            distance = math.dist(c,closest)
            radius = max(self.policy.minimum_near_pixels,(b[3]-b[1])*self.policy.near_height_fraction)
            if birth:
                radius = max(self.policy.minimum_near_pixels,min(radius,min(self.size)*self.policy.maximum_near_image_fraction))
            signed = sum((c[k]-gate.a[k])*gate.normal[k] for k in (0,1))
            choices.append(dict(center_pixels=c,distance_pixels=distance,radius_pixels=radius,
                along=along,signed_pixels=signed,near=distance <= radius,segment=index,
                boundary_position_formula='bbox_bottom_center'))
        return min(choices,key=lambda r:(r['distance_pixels'],r['segment']))


def connected_rows(rows, scene, policy=Policy()):
    """Actual contiguous suffix only; raw ID never bridges gaps or box jumps."""
    start = 0
    for i, (a, b) in enumerate(zip(rows, rows[1:]), 1):
        ah, bh = a['bbox'][3]-a['bbox'][1], b['bbox'][3]-b['bbox'][1]
        aw, bw = a['bbox'][2]-a['bbox'][0], b['bbox'][2]-b['bbox'][0]
        if (b['pts']-a['pts'] > policy.max_direction_step+1e-9
                or b['pts'] <= a['pts'] or b['frame_index'] <= a['frame_index']
                or max(ah/bh,bh/ah,aw/bw,bw/aw) > policy.scale_jump
                or math.dist(center(a, scene['source_size']), center(b, scene['source_size']))
                > .5*max(ah,bh)*scene['source_size'][1]):
            start = i
    return rows[start:]


def measured_origin(rows, scene, policy=Policy()):
    """First stable side of the connected source, not a shared/recent ID label."""
    streak = []; side = None
    for row in connected_rows(rows, scene, policy):
        current = boundary_zone(row, scene)
        if current is None or current != side:
            streak = []; side = current
        if current is not None:
            streak.append(row)
            if (len(streak) >= policy.stable_observations
                    and streak[-1]['pts']-streak[0]['pts'] >= policy.stable_seconds-1e-9):
                return side, streak
    return None, []


def retained_origin(rows, scene, gate, origin, policy=Policy()):
    """Retain origin beyond 3 s only through measured gateward progress.

    Fresh observations on the source side refresh context. In an unlabelled
    approach strip, each old-history window needs aggregate progress; single
    box jitter does not reset it and indefinite stationary memory is rejected.
    """
    anchored = [r for r in rows if boundary_zone(r,scene) == origin]
    if not anchored:
        return False
    anchor = anchored[-1]; sign = 1 if origin == 'inside' else -1
    for row in rows:
        if row['pts']-anchor['pts'] <= EpisodePolicy().history_seconds+1e-9:
            continue
        before = gate.locate(anchor['bbox'],birth=False)['signed_pixels']
        after = gate.locate(row['bbox'],birth=False)['signed_pixels']
        if sign*(after-before) > -policy.min_motion_pixels:
            return False
        anchor = row
    return True


def validate_directional_inputs(frames, scene):
    """Shared admission contract for directional analysis and direct replay."""
    from .dual_boundary import Corridor
    Corridor(scene)
    if any(b.get('predicted') is True or b.get('observed') is False or b.get('confirmed') is False
           for frame in frames for b in frame['actual_boxes']):
        raise ValueError('Only actual observed boxes may enter directional rules')


class DirectionalGate(SavedGateDirection):
    """Legacy direction logic; only the outward source boundary differs."""
    def __init__(self, frames, scene):
        # Reuse historical geometry validation only, never its state machine.
        validate_directional_inputs(frames, scene)
        super().__init__(frames, scene)
        self.scene = scene

    def _engine(self, segment):
        if measured_origin(segment['rows'], self.scene)[0] != 'inside':
            return None
        engine = SavedGateDirection.__new__(SavedGateDirection)
        engine.__dict__.update(self.__dict__)
        engine.geometry = gate_geometry(source_scene(self.scene, 'inside', segment['rows'][-1]['bbox']))
        return engine

    def direction(self, segment):
        engine = self._engine(segment)
        if engine:
            return dict(engine.direction(segment), source_origin_side='inside',
                        source_boundary='inner_line')
        return super().direction(segment)

    def continuation(self, segment, index):
        engine = self._engine(segment)
        return engine.continuation(segment, index) if engine else super().continuation(segment, index)

    def classify(self, event, segment):
        engine = self._engine(segment)
        result = engine.classify(event, segment) if engine else super().classify(event, segment)
        if engine and result.get('automatic_confirmation'):
            result.update(status='침입 의심', automatic_confirmation=False,
                          reason='inside_source_moving_away_from_gate')
        return result


def _actual_rows(frames):
    p = EpisodePolicy()
    return [dict(pts=f['pts'], frame_index=f['frame_index'], **deepcopy(b))
            for f in frames for b in f['actual_boxes']
            if b.get('observed') is not False and b.get('predicted') is not True
            and b.get('confirmed') is not False and b.get('score', 0) >= p.detection_floor]


def _destination_site(row, scene, destination, gate, sign):
    """Qualify a measured box in this destination's finite gate context."""
    if boundary_zone(row, scene) != destination:
        return None
    site = gate.locate(row['bbox'])
    if not site['near'] or not 0 <= site['along'] <= 1 or -sign*site['signed_pixels'] <= 0:
        return None
    return site


def loss_appearance_candidates(baseline, frames, scene, scope, run_id):
    """Independent causal sequence, with no association across the hidden span.

    Use existing 1 s absence, 6 s pairing, stable origin and finite-gate policies.
    Birth lookback excludes earlier boxes qualifying in the same destination
    gate context. This is region-level first appearance, not a globally new
    person or a source-to-destination identity match. Each branch owns a birth
    once; later original strong evidence survives an earlier auxiliary claim.
    """
    policy = Policy(**baseline['policy']); ep = EpisodePolicy()
    actual = _actual_rows(frames)
    by_ref = {(r['frame_index'], r['cache_index']): r for r in actual}
    stamps = [f['pts'] for f in frames]
    candidates = []; decisions = []
    # Keep each causal contiguous piece, including an earlier disappearance
    # before a reused raw ID. Future rows cannot erase that observed evidence.
    segments = []
    for segment in baseline['segments']:
        pieces = []
        for row in segment['rows']:
            if not pieces or len(connected_rows([pieces[-1][-1],row],scene,policy)) == 1:
                pieces.append([])
            pieces[-1].append(row)
        segments.extend(dict(segment,rows=piece) for piece in pieces)
    for segment in segments:
        rows = segment['rows']
        if not rows or any((r['frame_index'], r.get('cache_index')) not in by_ref
                or by_ref[(r['frame_index'],r['cache_index'])]['bbox'] != r['bbox']
                or by_ref[(r['frame_index'],r['cache_index'])]['pts'] != r['pts']
                or r.get('observed') is False or r.get('predicted') is True
                or r.get('confirmed') is False for r in rows):
            continue
        origin, support = measured_origin(rows, scene, policy)
        if origin is None:
            continue
        destination = 'outside' if origin == 'inside' else 'inside'
        direction = origin+'_to_'+destination
        if direction not in scene['directions']:
            continue
        gate = BoundaryGate(scene, origin)
        dest_gate = BoundaryGate(scene, destination)
        last = rows[-1]; site = gate.locate(last['bbox'], birth=False)
        sign = 1 if origin == 'inside' else -1
        # Preserve the original side through a slow gate approach, but never
        # transfer it across a discontinuity, an opposite side or moving away.
        approach = [r for r in rows if r['pts'] >= support[0]['pts']]
        if (any(boundary_zone(r,scene) == destination for r in approach)
                or not retained_origin(approach,scene,gate,origin,policy)):
            continue
        recent = [r for r in approach if last['pts']-r['pts'] <= policy.direction_window+1e-9]
        if len(recent) < policy.stable_observations:
            continue
        first_site = gate.locate(recent[0]['bbox'], birth=False)
        displacement = sign*(site['signed_pixels']-first_site['signed_pixels'])
        if (not site['near'] or not 0 <= site['along'] <= 1
                or sign*first_site['signed_pixels'] <= 0):
            continue
        # Keep the strong branch byte-for-byte compatible. Only an ambiguous
        # measured terminal direction may use the opposite appearance as the
        # missing confirmation evidence; observed net retreat is not ambiguity.
        auxiliary = displacement > -policy.min_motion_pixels
        if auxiliary and displacement >= policy.min_motion_pixels:
            continue
        for birth in actual:
            if not last['pts'] < birth['pts'] <= last['pts']+policy.pair_seconds+1e-9:
                continue
            key = (birth['frame_index'],birth['cache_index'])
            dest_site = _destination_site(birth, scene, destination, dest_gate, sign)
            if dest_site is None:
                continue
            # Existing pair distance policy bounds context along the same gate;
            # we do not interpolate any path through the two measured endpoints.
            if math.dist(center(last,scene['source_size'],1.),center(birth,scene['source_size'],1.)) > (
                    policy.pair_distance_heights*max(last['bbox'][3]-last['bbox'][1],
                    birth['bbox'][3]-birth['bbox'][1])*scene['source_size'][1]):
                continue
            earlier = [r for r in actual if birth['pts']-ep.birth_lookback-1e-9 <= r['pts'] < birth['pts']]
            if birth['pts']-stamps[0] < ep.birth_lookback-1e-9 or any(
                    _destination_site(r, scene, destination, dest_gate, sign) is not None
                    and association(r['bbox'],birth['bbox'],ep.association_overlap) is not None
                    for r in earlier):
                continue
            index = bisect_left(stamps,max(last['pts']+policy.loss_wait,birth['pts'])-1e-9)
            if index == len(stamps):
                continue
            at = stamps[index]
            clock_rows = frames[rows[0]['frame_index']:index+1]
            if (not clock_rows or clock_rows[0]['pts'] != rows[0]['pts']
                    or any(b['pts']-a['pts'] > ep.source_gap_seconds+1e-9
                           for a,b in zip(clock_rows,clock_rows[1:]))):
                continue
            # Positive same-side continuation is not disappearance. This local
            # veto never associates the destination appearance with the source.
            if any(last['pts'] < r['pts'] <= at and boundary_zone(r,scene) == origin
                   and association(r['bbox'],last['bbox'],ep.association_overlap) is not None
                   for r in actual):
                continue
            evidence = dict(rule_id=RULE, direction=direction, segment=segment['id'],
                raw_id=segment['raw_id'], decision_time_pts=at, evidence_until_pts=at,
                last_observed_pts=last['pts'], loss_wait=policy.loss_wait,
                status='침입 확인', automatic_confirmation=True, notify=True,
                reason='measured_source_approach_loss_then_new_destination_appearance',
                source_origin_refs=deepcopy(support), source_direction_refs=deepcopy(recent),
                source_last_ref=deepcopy(last), destination_first_ref=deepcopy(birth),
                source_boundary=deepcopy(scene['inner_line'] if origin == 'inside' else scene['line']),
                destination_boundary=deepcopy(scene['inner_line'] if destination == 'inside' else scene['line']),
                source_site=site, destination_site=dest_site,
                direction_evidence=dict(method='measured_bottom_center_source_displacement',
                    signed_toward_pixels=-displacement, start_pts=recent[0]['pts'], end_pts=last['pts']),
                boundary_position_formula='bbox_bottom_center', source_clock_continuous=True,
                identity_verified=False, reconstructed_path=False, shared_point_lineage_required=False,
                decision_source='automatic_rule', human_verified=False,
                confirmation_basis='camera_event_sequence_not_identity_or_ground_truth')
            if auxiliary:
                evidence.update(
                    reason='uncertain_source_direction_loss_then_new_destination_appearance',
                    source_direction_uncertain=True,
                    confirmation_supplied_by='qualified_opposite_boundary_first_appearance',
                    direction_evidence=dict(method='measured_bottom_center_source_displacement',
                        direction='unknown', signed_toward_pixels=-displacement,
                        start_pts=recent[0]['pts'], end_pts=last['pts'],
                        interpretation='insufficient_signed_motion_not_proven_stationarity'))
            eid = digest(dict(scope=scope,run_id=run_id,evidence=evidence))
            raw = dict(segment=segment['id'],raw_id=segment['raw_id'],
                reason=evidence['reason'],decision_time_pts=at,last_observed_pts=last['pts'],
                evidence=deepcopy(evidence))
            event = dict(**scope,event_id=eid,video_id=baseline['video_id'],status='침입 의심',
                decision_time_pts=at,track_ids=[],source_event=raw,
                source_ref=dict(collection='measured_loss_appearance_events',
                    source_pointer='/measured_loss_appearance_events/'+eid,
                    segment=segment['id'],raw_id=segment['raw_id']))
            evidence.update(event_id=eid, source_ref=deepcopy(event['source_ref']),
                analysis_run_id=run_id,computed_in_current_run=True,rule_implementation=RULE)
            candidates.append(event); decisions.append(evidence)
            break
    # Preserve the original strong allocator independently, in causal order.
    # Auxiliary claims cannot remove its evidence. At the same decision clock
    # strong evidence wins; an earlier auxiliary claim can coexist with later
    # strong support for that birth, without rewriting the earlier timeline.
    ordered = sorted(zip(candidates,decisions),key=lambda pair:(
        pair[1]['decision_time_pts'],pair[1].get('source_direction_uncertain',False),
        -pair[1]['last_observed_pts'],pair[0]['event_id']))
    selected = []; claimed = []; strong_claimed = []
    for event, decision in ordered:
        birth = decision['destination_first_ref']
        auxiliary = decision.get('source_direction_uncertain',False)
        owners = claimed if auxiliary else strong_claimed
        if any(birth['frame_index'] == old['frame_index'] and
               association(birth['bbox'],old['bbox'],ep.association_overlap) is not None for old in owners):
            continue
        selected.append((event,decision));claimed.append(birth)
        if not auxiliary:
            strong_claimed.append(birth)
    return [p[0] for p in selected], [p[1] for p in selected]


def validate_loss_appearance(decision, event, at):
    """Validate separate source/destination provenance at the lifecycle boundary."""
    source = decision.get('source_last_ref',{}); destination = decision.get('destination_first_ref',{})
    origin = decision.get('source_origin_refs',[]); direction = decision.get('source_direction_refs',[])
    if (decision.get('rule_id') != RULE or decision.get('automatic_confirmation') is not True
            or decision.get('decision_time_pts') != at or decision.get('evidence_until_pts') != at
            or decision.get('event_id') != event['event_id']
            or decision.get('identity_verified') is not False or decision.get('reconstructed_path') is not False
            or decision.get('source_clock_continuous') is not True
            or not origin or not direction or not source or not destination
            or not 0 <= source['pts'] < destination['pts'] <= at
            or decision.get('last_observed_pts') != source['pts']
            or at-source['pts'] < decision.get('loss_wait',math.inf)-1e-6
            or direction[-1] != source or origin[-1]['pts'] > source['pts']
            or event['source_ref'].get('collection') != 'measured_loss_appearance_events'
            or event['source_event'].get('segment') != decision.get('segment')):
        raise ValueError('Causal source loss and separate new destination evidence required')
    expected = deepcopy(decision)
    for key in ('event_id','source_ref','analysis_run_id','computed_in_current_run','rule_implementation'):
        expected.pop(key,None)
    if event['source_event'].get('evidence') != expected:
        raise ValueError('Loss/appearance evidence differs from its source candidate')
