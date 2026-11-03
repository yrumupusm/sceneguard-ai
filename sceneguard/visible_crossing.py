"""Confirm a continuously observed outside-to-inside passage without a loss wait.

This uses measured box/region continuity, not a claim of verified identity or
physical/legal intrusion. The existing disappearance branch remains separate.
"""
from __future__ import annotations

from copy import deepcopy
import math

from .approach_disappearance import Policy, center, line_distance, polygon, signed_distance, validate_scene, zone
from .gate_episode_evidence import EpisodePolicy


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('Finite source timestamp required')
    return float(value)


def _ref(row):
    return {k: deepcopy(row[k]) for k in ('pts', 'frame_index', 'cache_index', 'bbox') if k in row}


def _finite_crossings(rows, scene, outside_sign):
    """Find actual adjacent proxy paths across the finite configured segment.

    Require the same signed direction as the stable outside-to-inside anchors.
    Radius-to-endpoint proximity is insufficient. With exact on-line samples,
    require opposite nonzero sides around the whole on-line run and keep every
    on-line point within the gate; touching then walking past an endpoint does
    not establish a crossing through the gate.
    """
    size = scene['source_size']
    points = [center(row, size, .65) for row in rows]
    distances = [signed_distance(point, scene) for point in points]
    a, b = [tuple(q[k]*size[k] for k in (0,1)) for q in scene['line']]
    v = (b[0]-a[0], b[1]-a[1]); length2 = v[0]**2+v[1]**2

    def along(point):
        return sum((point[k]-a[k])*v[k] for k in (0,1))/length2

    result = []
    previous = None
    for i, distance in enumerate(distances):
        if abs(distance) <= 1e-7:
            continue
        if (previous is not None and distances[previous]*distance < 0
                and distances[previous]*outside_sign > 0 and distance*outside_sign < 0):
            if i == previous+1:
                fraction = distances[previous]/(distances[previous]-distance)
                point = tuple(points[previous][k]+fraction*(points[i][k]-points[previous][k]) for k in (0,1))
                positions = [along(point)]
            else:
                positions = [along(point) for point in points[previous+1:i]]
                point = points[previous+1]
            if all(-1e-9 <= position <= 1+1e-9 for position in positions):
                result.append(dict(before=_ref(rows[previous]), after=_ref(rows[i]),
                    crossing_point_pixels=list(point), gate_along=positions,
                    crossing_location='interpolated_between_measured_proxies'))
        previous = i
    return result


def visible_crossing_decision(source, segment, scene, policy=Policy()):
    """Validate a causal measured transition at the candidate's existing clock.

    Both sides require the existing stable observation duration/count. A source
    event alone is insufficient: rebuild the observation support from the prefix
    ending at its timestamp, dropping continuity across gaps/size jumps/box jumps.
    Future rows never help the decision and are not returned as evidence.
    """
    policy.validate()
    validate_scene(scene)
    at = _number(source.get('decision_time_pts', source.get('pts')))
    if (at < 0 or source.get('segment') != segment.get('id')
            or source.get('raw_id') != segment.get('raw_id')):
        raise ValueError('Candidate and measured segment binding differ')
    for key in ('pts', 'source_observed_pts'):
        if key in source and abs(_number(source[key])-at) > 1e-6:
            raise ValueError('Visible crossing must use its actual observation clock')
    result = dict(segment=segment['id'], raw_id=segment['raw_id'],
        decision_time_pts=at, last_observed_pts=at, evidence_until_pts=at,
        status='침입 의심', automatic_confirmation=False, notify=False,
        rule_id='visible_gate_crossing_v1', loss_wait_required=False,
        human_verified=False, identity_verified=False,
        decision_source='automatic_rule',
        confirmation_basis='camera_rule_not_manual_or_ground_truth')

    def reject(reason):
        return dict(result, reason=reason)

    if (source.get('reason') != 'observed_side_transition'
            or source.get('direction') != 'outside_to_inside'
            or 'outside_to_inside' not in scene['directions']):
        return reject('not_an_enabled_observed_inward_transition')
    # Inspect the prefix only. A later disappearance or crossing cannot prove
    # what was observable at this candidate's timestamp.
    prefix = [r for r in segment['rows'] if _number(r['pts']) <= at+1e-9]
    if not prefix or abs(prefix[-1]['pts']-at) > 1e-6:
        raise ValueError('Visible crossing requires an actual observation at decision time')
    for i, row in enumerate(prefix):
        if row.get('observed') is False:
            raise ValueError('Predicted boxes cannot confirm a visible crossing')
        b = row['bbox']
        if (len(b) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) for v in b)
                or not 0 <= b[0] < b[2] <= 1 or not 0 <= b[1] < b[3] <= 1
                or type(row.get('frame_index')) is not int or row['frame_index'] < 0):
            raise ValueError('Measured normalized box and source frame required')
        if i and (row['pts'] <= prefix[i-1]['pts'] or row['frame_index'] <= prefix[i-1]['frame_index']):
            raise ValueError('Ordered actual source observations required')
    history = EpisodePolicy().history_seconds
    rows = [r for r in prefix if at-r['pts'] <= history+1e-9]
    # Same geometric association distance as existing short-run bookkeeping;
    # numeric track ID alone is not enough after a disconnected box jump.
    size = scene['source_size']
    start = 0
    for i, (a, b) in enumerate(zip(rows, rows[1:]), 1):
        aw, ah = a['bbox'][2]-a['bbox'][0], a['bbox'][3]-a['bbox'][1]
        bw, bh = b['bbox'][2]-b['bbox'][0], b['bbox'][3]-b['bbox'][1]
        jump = math.dist(center(a, size), center(b, size))/max(ah*size[1], bh*size[1])
        if (b['pts']-a['pts'] > policy.max_direction_step+1e-9
                or max(aw/bw, bw/aw, ah/bh, bh/ah) > policy.scale_jump
                or jump > .5):
            start = i
    rows = rows[start:]

    def stable(streak):
        return (len(streak) >= policy.stable_observations
                and streak[-1]['pts']-streak[0]['pts'] >= policy.stable_seconds-1e-9)

    inside = []
    for row in reversed(rows):
        if zone(row, scene) != 'inside':
            break
        inside.append(row)
    inside.reverse()
    if not stable(inside):
        return reject('inside_observations_not_stable')
    outside, streak = [], []
    for row in rows:
        if row['pts'] >= inside[0]['pts']:
            break
        if zone(row, scene) == 'outside':
            streak.append(row)
            if stable(streak):
                outside = list(streak)
        else:
            streak = []
    if not outside:
        return reject('continuous_stable_outside_history_missing')
    passage = [r for r in rows if outside[-1]['pts'] <= r['pts'] <= at]
    # Require the observed proxies to cross the configured boundary, not merely
    # transition between arbitrary disconnected image polygons.
    before = center(outside[-1], size, .65)
    after = center(inside[-1], size, .65)
    if signed_distance(before, scene)*signed_distance(after, scene) >= 0:
        return reject('no_observed_boundary_side_change')
    crossings = _finite_crossings(passage, scene, signed_distance(before, scene))
    if not crossings:
        return reject('no_observed_finite_gate_crossing')
    contacts = [r for r in passage if polygon(center(r, (1, 1), .65), scene['approach_polygon'])
                and line_distance(center(r, size, .65), scene)
                <= max(12., (r['bbox'][3]-r['bbox'][1])*size[1]*policy.near_line_heights)]
    if not contacts:
        return reject('no_recent_finite_gate_contact')
    result.update(status='침입 확인', automatic_confirmation=True, notify=True,
        reason='continuous_observed_outside_to_inside', continuation='cross_side_observation',
        direction='outside_to_inside',
        direction_evidence=dict(method='measured_box_region_transition',
                                start_pts=outside[-1]['pts'], end_pts=at),
        outside_support=[_ref(r) for r in outside], inside_support=[_ref(r) for r in inside],
        gate_contact=_ref(contacts[-1]), finite_gate_crossings=crossings, observation_refs=[_ref(r) for r in passage],
        stable_seconds=policy.stable_seconds, stable_observations=policy.stable_observations,
        maximum_observation_gap_seconds=max((b['pts']-a['pts'] for a,b in zip(passage,passage[1:])),default=0.))
    return result
