"""Dataset-scope outward gate-loss confirmation, distinct from walking away.

The user includes inside-to-outside crossings in the positive class. Require
measured inside origin and recent finite gate context; outward flow alone is
still insufficient. This is a camera rule, not verified identity or permission.
"""
from copy import deepcopy
import math

from .approach_disappearance import Policy, center, zone
from .gate_episode_evidence import EpisodePolicy, Gate


def outward_loss_decision(previous, segment, scene, policy=Policy()):
    result = deepcopy(previous)
    if (previous.get('automatic_confirmation')
            or 'inside_to_outside' not in scene['directions']
            or previous.get('continuation') != 'unresolved'
            or previous.get('reason') in ('loss_wait_not_observed', 'source_gap_not_person_loss')):
        return result
    direction = previous.get('direction', {})
    if direction.get('direction') != 'outward':
        return result
    rows = segment['rows']
    last = rows[-1]['pts']
    at = previous['decision_time_pts']
    end = direction.get('end_pts')
    if (previous.get('last_observed_pts') != last or at-last < policy.loss_wait-1e-6
            or end is None or not 0 <= last-end <= EpisodePolicy().history_seconds+1e-9):
        return result
    policy.validate()
    if any(r.get('observed') is False for r in rows) or any(
            a['pts'] >= b['pts'] for a,b in zip(rows,rows[1:])):
        raise ValueError('Chronological actual observations required')
    gate = Gate(scene)
    recent = [r for r in rows if 0 <= last-r['pts'] <= gate.policy.history_seconds+1e-9]
    # Keep only the connected recent prefix ending at the last real box.
    start = 0
    for i, (a,b) in enumerate(zip(recent,recent[1:]), 1):
        ah, bh = a['bbox'][3]-a['bbox'][1], b['bbox'][3]-b['bbox'][1]
        aw, bw = a['bbox'][2]-a['bbox'][0], b['bbox'][2]-b['bbox'][0]
        size = scene['source_size']
        if (b['pts']-a['pts'] > policy.max_direction_step+1e-9
                or max(ah/bh,bh/ah,aw/bw,bw/aw) > policy.scale_jump
                or math.dist(center(a,size),center(b,size)) > .5*max(ah,bh)*size[1]):
            start = i
    recent = recent[start:]
    contacts = [r for r in recent if r['pts'] <= end+1e-9
                and gate.locate(r['bbox'], birth=False)['near']
                and 0 <= gate.locate(r['bbox'], birth=False)['along'] <= 1]
    if not contacts:
        return result
    # A stable inside streak must precede/contact the gate. An outsider
    # approaching then turning around cannot satisfy this origin requirement.
    streak = []; origin = []
    for r in recent:
        if r['pts'] > contacts[-1]['pts']+1e-9:
            break
        if zone(r,scene) != 'inside':
            streak = []; continue
        streak.append(r)
        if (len(streak) >= policy.stable_observations
                and streak[-1]['pts']-streak[0]['pts'] >= policy.stable_seconds-1e-9):
            origin = list(streak)
    if not origin:
        return result
    result.update(rule_id='outward_gate_loss_v1', status='침입 확인',
        automatic_confirmation=True, notify=True,
        reason='inside_origin_outward_motion_then_gate_loss',
        crossing_direction='inside_to_outside', inside_origin=deepcopy(origin),
        gate_contact=deepcopy(contacts[-1]), recent_gate_contact=True,
        decision_source='automatic_rule', human_verified=False, identity_verified=False,
        confirmation_basis='camera_rule_not_manual_or_ground_truth',
        evidence_until_pts=at)
    return result
