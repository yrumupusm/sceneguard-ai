"""Revalidate preserved boundary alerts from their actual bottom-center boxes.

The historical alert is a candidate, not proof. Rebuild both signed dwells and
the finite gate crossing at its emission clock. The bottom-center proxy matches
the original boundary rule; it does not reconstruct feet, action or identity.
"""
import math

from .approach_disappearance import Policy, center, polygon, signed_distance, validate_scene
from .directional_loss import gate_geometry
from .gate_episode_evidence import EpisodePolicy
from .visible_crossing import _number, _ref


def _crossings(rows, scene, origin_sign):
    """Intersections of adjacent measured bottom-center paths with the gate."""
    size = scene['source_size']
    points = [center(r, size, 1.) for r in rows]
    distances = [signed_distance(p, scene) for p in points]
    a, b = [tuple(p[k]*size[k] for k in (0, 1)) for p in scene['line']]
    vector = tuple(b[k]-a[k] for k in (0, 1))
    length2 = sum(v*v for v in vector)

    def along(p):
        return sum((p[k]-a[k])*vector[k] for k in (0, 1))/length2

    result = []; previous = None
    for i, distance in enumerate(distances):
        if abs(distance) <= 1e-7:
            continue
        if (previous is not None and distances[previous]*origin_sign > 0
                and distance*origin_sign < 0):
            if i == previous+1:
                fraction = distances[previous]/(distances[previous]-distance)
                point = tuple(points[previous][k]+fraction*(points[i][k]-points[previous][k]) for k in (0, 1))
                on_line = [point]
            else:
                on_line = points[previous+1:i]
            if (all(-1e-9 <= along(p) <= 1+1e-9 for p in on_line)
                    and all(polygon(tuple(p[k]/size[k] for k in (0, 1)), scene['approach_polygon']) for p in on_line)):
                result.append(dict(before=_ref(rows[previous]), after=_ref(rows[i]),
                    crossing_point_pixels=list(on_line[0]), gate_along=[along(p) for p in on_line],
                    crossing_location='interpolated_between_measured_bottom_centers'))
        previous = i
    return result


def existing_alert_crossing_decision(source, segments, scene, policy=Policy()):
    """Return a confirmation only for a causally supported preserved alert.

    ``source`` is one raw existing_alerts row; ``segments`` is the unmodified
    baseline segment collection. A unique fragment must contain emission and
    both original anchors. No candidate metadata substitutes for actual boxes.
    """
    policy.validate(); validate_scene(scene)
    at = _number(source['emitted_at_pts'])
    before = _number(source['observed_pts_before'])
    after = _number(source['observed_pts_after'])
    tid = source.get('track_id')
    if at < 0 or not 0 <= before < after <= at or type(tid) is not int or tid < 0:
        raise ValueError('Chronological existing-alert clocks and actual track ID required')
    if 'decision_time_pts' in source and abs(_number(source['decision_time_pts'])-at) > 1e-6:
        raise ValueError('Use the original alert emission clock')
    if 'candidate_interval' in source:
        interval = source['candidate_interval']
        if (len(interval) != 2 or abs(_number(interval[0])-before) > 1e-6
                or abs(_number(interval[1])-after) > 1e-6):
            raise ValueError('Candidate interval differs from its actual anchors')
    result = dict(segment=None, raw_id=tid, decision_time_pts=at,
        last_observed_pts=at, evidence_until_pts=at, status='침입 의심',
        automatic_confirmation=False, notify=False, rule_id='existing_alert_gate_crossing_v1',
        loss_wait_required=False, human_verified=False, identity_verified=False,
        decision_source='automatic_rule', confirmation_basis='camera_rule_not_manual_or_ground_truth',
        observation_proxy='bbox_bottom_center_matching_original_boundary_rule')

    def reject(reason):
        return dict(result, reason=reason)

    direction_signs = {'positive_to_negative': 1, 'negative_to_positive': -1}
    signed_direction = source.get('direction')
    if source.get('condition', 'gap') != 'gap' or signed_direction not in direction_signs:
        return reject('not_a_supported_preserved_boundary_alert')
    origin_sign = direction_signs[signed_direction]
    # Bind to exactly one fragment at the current clock, never stitch reused IDs.
    candidates = [s for s in segments if s.get('raw_id') == tid
        and any(abs(_number(r['pts'])-at) <= 1e-6 for r in s['rows'])]
    if len(candidates) != 1:
        return reject('existing_alert_measured_fragment_not_unique')
    segment = candidates[0]; result['segment'] = segment['id']
    prefix = [r for r in segment['rows'] if _number(r['pts']) <= at+1e-9]
    if not prefix or abs(prefix[-1]['pts']-at) > 1e-6:
        return reject('existing_alert_missing_emission_observation')
    for i, row in enumerate(prefix):
        b = row['bbox']
        if (row.get('observed') is False or row.get('confirmed') is False
                or len(b) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) for v in b)
                or not 0 <= b[0] < b[2] <= 1 or not 0 <= b[1] < b[3] <= 1
                or type(row.get('frame_index')) is not int or row['frame_index'] < 0):
            raise ValueError('Actual confirmed normalized boxes and frame references required')
        if i and (row['pts'] <= prefix[i-1]['pts'] or row['frame_index'] <= prefix[i-1]['frame_index']):
            raise ValueError('Strictly ordered measured source rows required')
    anchors = []
    for clock in (before, after):
        matched = [r for r in prefix if abs(r['pts']-clock) <= 1e-6]
        if len(matched) != 1:
            return reject('existing_alert_anchor_not_in_emission_fragment')
        anchors.append(matched[0])
    size = scene['source_size']
    # Reuse the existing polygon-center orientation, but reject centers that
    # fail to establish opposite physical sides of the configured boundary.
    geometry = gate_geometry(scene)
    side_distances = {name: signed_distance(p, scene) for name, p in geometry['zone_centers'].items()}
    if (side_distances['inside']*side_distances['outside'] >= 0
            or min(abs(v) for v in side_distances.values()) < policy.min_motion_pixels):
        return reject('ambiguous_configured_boundary_orientation')
    destination_side = 'inside' if side_distances['inside']*origin_sign < 0 else 'outside'
    origin_side = 'outside' if destination_side == 'inside' else 'inside'
    from .legacy_directional import source_scene
    scene = source_scene(scene, origin_side, anchors[0]['bbox'])
    direction = origin_side+'_to_'+destination_side
    if direction not in scene['directions']:
        return reject('existing_alert_crossing_direction_disabled')
    # Anchor interval can contain slow visible travel through the boundary band.
    # The preceding origin dwell is bounded; every intervening row must remain
    # continuous, even when the original candidate interval exceeds three seconds.
    rows = [r for r in prefix if r['pts'] >= before-EpisodePolicy().history_seconds-1e-9]
    start = 0
    for i, (a, b) in enumerate(zip(rows, rows[1:]), 1):
        aw, ah = a['bbox'][2]-a['bbox'][0], a['bbox'][3]-a['bbox'][1]
        bw, bh = b['bbox'][2]-b['bbox'][0], b['bbox'][3]-b['bbox'][1]
        if (b['pts']-a['pts'] > policy.max_direction_step+1e-9
                or max(aw/bw, bw/aw, ah/bh, bh/ah) > policy.scale_jump
                or math.dist(center(a, size), center(b, size)) > .5*max(ah, bh)*size[1]):
            start = i
    rows = rows[start:]
    if rows[0]['pts'] > before+1e-9:
        return reject('existing_alert_discontinuous_anchor_path')

    def side(row):
        distance = signed_distance(center(row, size, 1.), scene)
        return 1 if distance >= policy.min_motion_pixels else -1 if distance <= -policy.min_motion_pixels else 0

    if side(anchors[0]) != origin_sign or side(anchors[1]) != -origin_sign:
        return reject('existing_alert_signed_direction_not_measured')
    origin = []
    for row in reversed([r for r in rows if r['pts'] <= before+1e-9]):
        if side(row) != origin_sign:
            break
        origin.append(row)
    origin.reverse()
    destination = [r for r in rows if r['pts'] >= after-1e-9]

    def stable(streak):
        return (len(streak) >= policy.stable_observations
                and streak[-1]['pts']-streak[0]['pts'] >= policy.stable_seconds-1e-9)

    if not stable(origin):
        return reject('existing_alert_origin_dwell_not_measured')
    if not stable(destination) or any(side(r) != -origin_sign for r in destination):
        return reject('existing_alert_destination_dwell_not_measured')
    passage = [r for r in rows if before-1e-9 <= r['pts'] <= after+1e-9]
    crossings = _crossings(passage, scene, origin_sign)
    if not crossings:
        return reject('existing_alert_no_measured_finite_gate_crossing')
    support = {origin_side: origin, destination_side: destination}
    result.update(status='침입 확인', automatic_confirmation=True, notify=True,
        reason='validated_existing_alert_'+direction, direction=direction,
        source_signed_direction=signed_direction, continuation='cross_side_observation',
        direction_evidence=dict(method='measured_bottom_center_finite_boundary_crossing',
            start_pts=before, end_pts=at, orientation_source=geometry['orientation_source']),
        outside_support=[_ref(r) for r in support['outside']],
        inside_support=[_ref(r) for r in support['inside']],
        observation_refs=[_ref(r) for r in rows if r['pts'] >= origin[0]['pts']],
        finite_gate_crossings=crossings, stable_seconds=policy.stable_seconds,
        stable_observations=policy.stable_observations, signed_deadband_pixels=policy.min_motion_pixels,
        maximum_observation_gap_seconds=max((b['pts']-a['pts'] for a,b in zip(rows,rows[1:])),default=0.))
    return result
