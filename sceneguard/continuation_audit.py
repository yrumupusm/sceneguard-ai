"""EXP-0037: optional notification view for clearly continuous measured tracks.

This is a narrow false-alert hypothesis, NOT identity recognition. All original
alerts remain untouched. Only recent_gate_presence_then_loss may be flagged;
line/region alarms are never suppressed. Missing or competing evidence => KEEP.
No detector, tracker, VLM, training, future observations, or geometry tuning.
"""
from copy import deepcopy
from dataclasses import asdict, dataclass
import math
from typing import Any


@dataclass(frozen=True)
class ContinuationPolicy:
    max_gap_seconds: float = 0.25
    history_seconds: float = 0.4
    confirmation_seconds: float = 0.4
    max_observation_gap: float = 0.2
    min_observations: int = 3
    min_iou: float = 0.65
    max_scale_ratio: float = 1.5
    competition_iou: float = 0.25

    def validate(self):
        for key, value in asdict(self).items():
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"Invalid continuation parameter: {key}")
        if (type(self.min_observations) is not int or self.min_observations < 2
                or not 0 < self.competition_iou < self.min_iou <= 1
                or self.max_scale_ratio <= 1):
            raise ValueError("Invalid counts, overlap or scale limits")
        return self


def _finite(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError("Finite nonnegative time required")
    return float(value)


def _box(values):
    if (not isinstance(values, (list, tuple)) or len(values) != 4
            or any(type(x) not in (int, float) or not math.isfinite(x) for x in values)
            or not 0 <= values[0] < values[2] <= 1
            or not 0 <= values[1] < values[3] <= 1):
        raise ValueError("Actual normalized xyxy box required")
    return values


def _iou(a, b):
    x = max(0., min(a[2], b[2])-max(a[0], b[0]))
    y = max(0., min(a[3], b[3])-max(a[1], b[1]))
    inter = x*y
    return inter / ((a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter)


def _scale(a, b):
    aw, ah, bw, bh = a[2]-a[0], a[3]-a[1], b[2]-b[0], b[3]-b[1]
    return max(aw/bw, bw/aw, ah/bh, bh/ah)


def _inside(point, poly):
    x, y = point
    found = False
    for a, b in zip(poly, poly[1:]+poly[:1]):
        ax, ay = a; bx, by = b
        c = (bx-ax)*(y-ay)-(by-ay)*(x-ax)
        if abs(c) < 1e-10 and min(ax,bx)-1e-10 <= x <= max(ax,bx)+1e-10 and min(ay,by)-1e-10 <= y <= max(ay,by)+1e-10:
            return True
        if (ay > y) != (by > y) and x < (bx-ax)*(y-ay)/(by-ay)+ax:
            found = not found
    return found


def _zone(box, zones):
    # Same 3-point proxy as EXP-0034. This is NOT a ground-plane location.
    x1, y1, x2, y2 = box
    pts = [(x1+f*(x2-x1), y1+.65*(y2-y1)) for f in (.35, .5, .65)]
    matches = [k for k, p in zones.items() if sum(_inside(q,p) for q in pts) >= 2]
    return matches[0] if len(matches) == 1 else None


def _validated(result, scene):
    if result.get('experiment') != 'EXP-0035':
        raise ValueError('Read the preserved EXP-0035 result')
    zones = scene.get('zones', {})
    if set(zones) != {'outside','inside'}:
        raise ValueError('Existing outside/inside zones required')
    for poly in zones.values():
        if (not isinstance(poly,list) or len(poly)<3
                or any(not isinstance(p,list) or len(p)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1 for v in p) for p in poly)):
            raise ValueError('Invalid existing zone polygon')
        if abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(poly,poly[1:]+poly[:1]))) < 1e-9:
            raise ValueError('Degenerate polygon')
    by_id, measured = {}, set()
    for seg in result['segments']:
        if not isinstance(seg.get('id'),str) or seg['id'] in by_id or not seg.get('rows') or type(seg.get('raw_id')) is not int:
            raise ValueError('Unique nonempty measured segments required')
        by_id[seg['id']] = seg
        previous = -1.
        for row in seg['rows']:
            at = _finite(row['pts']); _box(row['bbox'])
            if at <= previous or (row.get('observed') is False):
                raise ValueError('Only ordered measured rows, never predictions')
            key=(row.get('frame_index'),seg['raw_id'])
            if type(key[0]) is not int or key[0]<0 or key in measured:
                raise ValueError('Observed partition is not unique')
            measured.add(key); previous=at
    for e in result['events']:
        if e.get('segment') not in by_id:
            raise ValueError('Event references missing segment')
        _finite(e['decision_time_pts'])
    return by_id, zones


def _consistent(rows, zones, side, policy):
    return (len(rows) >= policy.min_observations
            and all(_zone(r['bbox'],zones)==side for r in rows)
            and all(0 < b['pts']-a['pts'] <= policy.max_observation_gap+1e-9
                    and _scale(a['bbox'], b['bbox']) <= policy.max_scale_ratio
                    for a,b in zip(rows,rows[1:])))


def audit_continuations(result: dict[str, Any], scene: dict[str, Any],
                        policy: ContinuationPolicy = ContinuationPolicy()) -> dict:
    """Decide using only measurements available by each original alert's time.

    Same-side is a veto prerequisite, not a prerequisite for producing suspicion.
    No old ID is ever assigned to a new person. Unseen/ambiguous data is KEEP.
    """
    policy.validate()
    by_id, zones = _validated(result,scene)
    audits=[]
    for index, event in enumerate(result['events']):
        if event.get('status') != '침입 의심' or event.get('reason') != 'recent_gate_presence_then_loss':
            continue
        seg=by_id[event['segment']]; last=seg['rows'][-1]; at=event['decision_time_pts']
        if last['pts']>at or abs(event.get('last_observed_pts',last['pts'])-last['pts'])>1e-6:
            raise ValueError('Loss/event endpoint binding differs')
        audit=dict(source_pointer=f'/events/{index}', segment=seg['id'], raw_id=seg['raw_id'],
                   decision_time_pts=at, evidence_until_pts=at,
                   recommendation='keep', reason='insufficient_continuation_evidence',
                   matches=[], identity_verified=False)
        audits.append(audit)
        # A prior suspicion supported by an independent rule is never downgraded.
        if any(e.get('segment')==seg['id'] and e.get('status')=='침입 의심'
               and e.get('reason')!='recent_gate_presence_then_loss'
               and e['decision_time_pts']<=at for e in result['events']):
            audit['reason']='independent_suspicion_preserved'; continue
        before=[r for r in seg['rows'] if last['pts']-r['pts']<=policy.history_seconds+1e-9]
        side=_zone(last['bbox'],zones)
        if side is None or not _consistent(before,zones,side,policy):
            audit['reason']='source_side_or_box_uncertain'; continue
        # A new target must appear immediately after loss, not a pre-existing bystander.
        candidates=[]
        for other in by_id.values():
            first=other['rows'][0]
            gap=first['pts']-last['pts']
            if other['id']==seg['id'] or not 0<gap<=policy.max_gap_seconds+1e-9 or first['pts']>at:
                continue
            observed=[r for r in other['rows'] if r['pts']<=at]
            overlap=_iou(last['bbox'],first['bbox'])
            if overlap < policy.min_iou or _scale(last['bbox'],first['bbox'])>policy.max_scale_ratio:
                continue
            span=observed[-1]['pts']-observed[0]['pts']
            if span<policy.confirmation_seconds-1e-9 or at-observed[-1]['pts']>policy.max_observation_gap+1e-9:
                continue
            if not _consistent(observed,zones,side,policy):
                continue
            candidates.append(other)
            audit['matches'].append(dict(segment=other['id'], raw_id=other['raw_id'], gap_seconds=gap,
                    initial_iou=overlap, observed_span_seconds=span,
                    last_evidence_pts=observed[-1]['pts'], side=side))
        if len(candidates)!=1:
            audit['reason']='competing_continuations' if candidates else 'no_clear_continuation'
            continue
        target=candidates[0]
        # Another visible body overlapping either prefix makes identity ambiguous.
        window=before+[r for r in target['rows'] if r['pts']<=at]
        snapshots={r['frame_index']:r for r in window}
        competing=False
        for other in by_id.values():
            if other['id'] in (seg['id'],target['id']): continue
            for r in other['rows']:
                match=snapshots.get(r['frame_index'])
                if r['pts']<=at and match is not None and _iou(r['bbox'],match['bbox'])>=policy.competition_iou:
                    competing=True; break
            if competing: break
        if competing:
            audit['reason']='overlapping_person_or_duplicate_unresolved'; continue
        audit.update(recommendation='review_only', reason='unique_same_side_measured_continuation')
    # A later alert cannot retroactively change an earlier notification decision.
    claimed={}
    for row in sorted(audits,key=lambda r:(r['decision_time_pts'],r['source_pointer'])):
        if row['recommendation']!='review_only': continue
        target=row['matches'][0]['segment']
        if target in claimed:
            row.update(recommendation='keep',reason='continuation_already_claimed')
        else:
            claimed[target]=row['source_pointer']
    return dict(experiment='EXP-0037', policy=asdict(policy), audits=audits,
                proposed_review_only=sum(x['recommendation']=='review_only' for x in audits),
                validated_identity_count=0, intrusion_accuracy=None,
                scope='notification_reduction_hypothesis_not_a_negative_intrusion_verdict')


def notification_view(result: dict, audit: dict, apply: bool = False) -> dict:
    """Original result is copied, never edited. A suppressed alert is still a suspicion.

    Use apply=False until the small actual-video comparison has been inspected.
    Persist audit and review_only_events next to the unchanged original result.
    """
    out=deepcopy(result)
    indices=set()
    if apply:
        for row in audit['audits']:
            if row['recommendation']!='review_only': continue
            index=int(row['source_pointer'].split('/')[-1])
            original=out['events'][index]
            if (original.get('segment')!=row['segment'] or original.get('reason')!='recent_gate_presence_then_loss'
                    or original.get('status')!='침입 의심' or original['decision_time_pts']!=row['decision_time_pts']):
                raise ValueError('Audit does not belong to these source alerts')
            indices.add(index)
    out['review_only_events']=[dict(source_pointer=f'/events/{i}', source_event=deepcopy(e))
                              for i,e in enumerate(out['events']) if i in indices]
    out['events']=[e for i,e in enumerate(out['events']) if i not in indices]
    out['continuation_audit']=deepcopy(audit)
    out['continuation_applied']=bool(apply)
    out['automatic_negative_decisions']=0
    return out
