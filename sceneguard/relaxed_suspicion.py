"""EXP-0035: broader review candidates; never an automatic intrusion verdict.

A recent measured gate/occlusion presence followed by an observed wait is enough.
Origin zone, final motion, reappearance and VLM are supporting evidence only.
The immutable EXP-0034 analysis is copied, not rerun or edited in place.
"""
from bisect import bisect_left
from copy import deepcopy
from dataclasses import asdict, dataclass
import math
import statistics


@dataclass(frozen=True)
class RelaxedPolicy:
    history_seconds: float = 3.0
    min_near_observations: int = 2

    def validate(self):
        if (type(self.history_seconds) not in (int, float)
                or not math.isfinite(self.history_seconds) or self.history_seconds <= 0
                or type(self.min_near_observations) is not int
                or self.min_near_observations < 1):
            raise ValueError('Invalid relaxed review policy')
        return self


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('Expected finite numeric observation')
    return float(value)


def _box(values):
    if len(values) != 4:
        raise ValueError('Expected normalized xyxy box')
    a, b, c, d = map(_number, values)
    if not (0 <= a < c <= 1 and 0 <= b < d <= 1):
        raise ValueError('Invalid normalized measured box')
    return a, b, c, d


def _cross(a, b, p):
    return (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])


def _on(a, b, p):
    return (abs(_cross(a, b, p)) <= 1e-10
            and min(a[0], b[0])-1e-10 <= p[0] <= max(a[0], b[0])+1e-10
            and min(a[1], b[1])-1e-10 <= p[1] <= max(a[1], b[1])+1e-10)


def _inside(point, poly):
    x, y = point
    answer = False
    for a, b in zip(poly, poly[1:]+poly[:1]):
        if _on(a, b, point):
            return True
        if (a[1] > y) != (b[1] > y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:
            answer = not answer
    return answer


def _intersects(a, b, c, d):
    u, v, x, y = _cross(a, b, c), _cross(a, b, d), _cross(c, d, a), _cross(c, d, b)
    return ((u*v < 0 and x*y < 0)
            or _on(a, b, c) or _on(a, b, d) or _on(c, d, a) or _on(c, d, b))


def _box_overlaps(box, poly):
    """Geometric footprint only: overlap is NOT proof of bodily occlusion."""
    x1, y1, x2, y2 = _box(box)
    corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
    if any(_inside(p, poly) for p in corners):
        return True
    if any(x1 <= x <= x2 and y1 <= y <= y2 for x, y in poly):
        return True
    return any(_intersects(a, b, c, d)
               for a, b in zip(corners, corners[1:]+corners[:1])
               for c, d in zip(poly, poly[1:]+poly[:1]))


def _distance_to_segment(point, line, size):
    a, b = [(p[0]*size[0], p[1]*size[1]) for p in line]
    vx, vy = b[0]-a[0], b[1]-a[1]
    den = vx*vx+vy*vy
    if den <= 0:
        raise ValueError('Degenerate finite gate line')
    t = max(0., min(1., ((point[0]-a[0])*vx+(point[1]-a[1])*vy)/den))
    return math.dist(point, (a[0]+t*vx, a[1]+t*vy))


def _recent_support(rows, scene, near_line_heights):
    w, h = scene['source_size']
    # Recent measured height, not the final possibly tiny head-only box.
    typical_height = statistics.median((_box(r['bbox'])[3]-r['bbox'][1])*h for r in rows)
    radius = max(12., typical_height*near_line_heights)
    result = []
    for r in rows:
        x1, y1, x2, y2 = _box(r['bbox'])
        p = ((x1+x2)*w/2, (y1+y2)*h/2)
        near = _distance_to_segment(p, scene['line'], (w, h)) <= radius
        occ = [o['id'] for o in scene.get('occlusions', []) if _box_overlaps(r['bbox'], o['polygon'])]
        # OR deliberately replaces strict direction+zone+line+occlusion conjunction.
        if near or occ:
            result.append(dict(pts=r['pts'], frame_index=r['frame_index'],
                               near_finite_line=near, occlusions=occ))
    return result, typical_height, radius


def add_relaxed_candidates(baseline, scene, frame_pts, policy=RelaxedPolicy()):
    """Preserve baseline alerts, IDs and geometry; attach review-only loss candidates.

    frame_pts must describe the actual saved clip, including no-detection frames.
    Future reappearances never erase a candidate at the first elapsed wait.
    """
    policy.validate()
    if baseline.get('experiment') != 'EXP-0034':
        raise ValueError('Expected the preserved EXP-0034 analysis')
    stamps = [_number(t) for t in frame_pts]
    if not stamps or any(a >= b for a, b in zip(stamps, stamps[1:])):
        raise ValueError('Strictly increasing actual frame timestamps required')
    wait = _number(baseline['policy']['loss_wait'])
    near_factor = _number(baseline['policy']['near_line_heights'])
    if wait <= 0 or near_factor <= 0 or len(scene['source_size']) != 2 or any(v <= 0 for v in scene['source_size']):
        raise ValueError('Invalid preserved source or policy')
    result = deepcopy(baseline)
    result['experiment'] = 'EXP-0035'
    result['mode'] = 'offline_relaxed_review_candidates'
    result['baseline_experiment'] = 'EXP-0034'
    result['relaxed_policy'] = asdict(policy)
    result['mandatory_loss_conditions'] = ['recent_measured_gate_or_occlusion_presence', 'elapsed_loss_wait']
    result['soft_only_conditions'] = ['origin_side', 'motion', 'forward_90', 'reappearance', 'vlm_appearance']
    original_events = deepcopy(baseline['events'])
    result['baseline_events'] = deepcopy(original_events)
    segments = {s['id']: s for s in result['segments']}
    losses = result['losses']
    if len(segments) != len(result['segments']) or len(losses) != len(segments) or {l['segment'] for l in losses} != set(segments):
        raise ValueError('Unique measured segments and one loss record each required')
    added, audited = [], []
    for loss in losses:
        segment = segments[loss['segment']]
        rows = segment['rows']
        if not rows or segment['raw_id'] != loss['raw_id']:
            raise ValueError('Loss/segment mismatch')
        if any(_number(a['pts']) >= _number(b['pts']) for a, b in zip(rows, rows[1:])):
            raise ValueError('Rows must be ordered real measurements')
        for r in rows:
            i = r['frame_index']
            if type(i) is not int or not 0 <= i < len(stamps) or abs(stamps[i]-_number(r['pts'])) > 1e-6:
                raise ValueError('Measurement must bind to an actual frame timestamp')
            _box(r['bbox'])
        last = _number(rows[-1]['pts'])
        if abs(last-_number(loss['last_pts'])) > 1e-6:
            raise ValueError('Final measurement/loss mismatch')
        recent = [r for r in rows if last-r['pts'] <= policy.history_seconds+1e-9]
        support, height, radius = _recent_support(recent, scene, near_factor)
        i = bisect_left(stamps, last+wait-1e-9)
        decision = stamps[i] if i < len(stamps) else None
        audit = dict(segment=segment['id'], raw_id=segment['raw_id'], last_pts=last,
                     baseline_status=loss['status'], baseline_reason=loss['reason'],
                     support=support, support_count=len(support),
                     recent_height_pixels=height, near_radius_pixels=radius,
                     decision_time_pts=decision, action='not_added', reason=None,
                     origin_side=loss.get('origin_side'),
                     motion_reliable=bool(loss.get('motion', {}).get('reliable', False)))
        if decision is None:
            audit['reason'] = 'analysis_window_ended_before_loss_wait'
        elif loss['status'] == '침입 의심':
            audit['reason'] = 'baseline_suspicion_already_preserved'
        elif len(support) < policy.min_near_observations:
            audit['reason'] = 'insufficient_recent_gate_observations'
        else:
            last_support = support[-1]['pts']
            # Only an actual normal same-side exit after gate evidence vetoes this loss.
            # Merely leaving a proxy ROI or unknown origin is NOT a normal-exit proof.
            normal_exits = [e for e in original_events if e['segment'] == segment['id']
                            and e['reason'] == 'observed_same_side_exit'
                            and e['status'] == '침입 아님' and last_support < e['pts'] <= last]
            if normal_exits and not loss.get('ever_crossed', False):
                audit['reason'] = 'observed_normal_exit_after_gate_evidence'
            else:
                audit.update(action='added_review_candidate', reason='recent_gate_presence_then_loss')
                supporting = dict(origin_side=loss.get('origin_side'),
                                  motion_reliable=audit['motion_reliable'],
                                  toward_boundary=loss.get('toward_boundary'),
                                  identity_verified=False, vlm_required=False,
                                  angle_is_optional=True)
                event = dict(segment=segment['id'], raw_id=segment['raw_id'], pts=decision,
                             status='침입 의심', reason=audit['reason'],
                             candidate_source='relaxed_loss',
                             last_observed_pts=last, source_observed_pts=last,
                             decision_time_pts=decision, loss_wait_elapsed=decision-last,
                             available_after_pts=stamps[-1],
                             near_evidence_frame_indices=[r['frame_index'] for r in support],
                             reappearance_required=False, supporting_evidence=supporting,
                             identity_verified=False, confirmed_intrusion=False,
                             uncertainty=['unobserved_outcome', 'possible_detection_or_id_failure',
                                          'bbox_proxy_and_occlusion_overlap_not_ground_truth'])
                added.append(event)
                loss.update(baseline_status=loss['status'], baseline_reason=loss['reason'],
                            status='침입 의심', reason=audit['reason'],
                            candidate_source='relaxed_loss', confirmed_intrusion=False,
                            decision_time_pts=decision, relaxed_support=support)
        loss['relaxed_review'] = deepcopy(audit)
        audited.append(audit)
    result['events'].extend(added)
    result['events'].sort(key=lambda e: (e['pts'], e['segment']))
    result['relaxation_audit'] = audited
    result['relaxation_summary'] = dict(
        baseline_suspicions=sum(e['status'] == '침입 의심' for e in original_events),
        added_loss_candidates=len(added),
        total_suspicion_rows=sum(e['status'] == '침입 의심' for e in result['events']),
        automatic_confirmations=0, detector_calls=0, tracker_calls=0, vlm_calls=0,
        note='Rows are review candidates, NOT unique people, correct incidents or probabilities.')
    result['warning'] = 'Higher-sensitivity review rule; additional false alarms expected; no automatic confirmation.'
    return result
