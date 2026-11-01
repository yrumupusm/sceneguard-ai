"""EXP-0048 read-only audit of ALL saved observation runs, not only alarms.

A run is not a unique person. No-suspicion passages are not successful releases.
Box-centre motion is diagnostic only; it never becomes a release/confirmation.
The endpoint audit is retrospective; lifecycle decisions remain causal.
"""
from __future__ import annotations
from bisect import bisect_left
from collections import Counter, defaultdict
from copy import deepcopy
import math

from .incident_lifecycle import clock, SUSPECTED, CONFIRMED, RELEASED


def candidate_links(lifecycle):
    linked = defaultdict(set)
    for evidence in lifecycle['evidence']:
        keys = {evidence.get('observation_key'),
                evidence.get('binding', {}).get('source_observation_key')}
        for edge in evidence.get('observation_history', []):
            keys.update((edge['from_key'], edge['to_key']))
        for key in keys - {None}:
            linked[key].add(evidence['event_id'])
    return linked


def box_motion(rows, geometry, window=1.):
    """A visible-box proxy for explaining missing optical-flow coverage ONLY."""
    last=rows[-1]; recent=[r for r in rows if last['pts']-r['pts']<=window+1e-9]
    result=dict(diagnostic_only=True, used_for_status=False, direction='unavailable')
    if len(recent)<2 or last['pts']-recent[0]['pts']<.1-1e-9:
        return result
    first=min(recent[:-1],key=lambda r:abs(last['pts']-r['pts']-.5))
    w,h=geometry['size']; a,b=first['bbox'],last['bbox']
    delta=[((b[0]+b[2])-(a[0]+a[2]))*w/2,
           ((b[1]+b[3])-(a[1]+a[3]))*h/2]
    normal=geometry.get('inward_normal'); length=math.hypot(*delta)
    component=None if normal is None else sum(x*y for x,y in zip(delta,normal))
    # These mirror the old direction scale for display, NOT a new detector rule.
    label='unknown' if length<1 or component is None else 'parallel'
    if component is not None and abs(component)>=2 and abs(component)/max(length,1e-9)>=.35:
        label='inward' if component>0 else 'outward'
    sizes=[(r[2]-r[0],r[3]-r[1]) for r in (a,b)]
    scale=max(sizes[0][k]/sizes[1][k] for k in (0,1))
    scale=max(scale,*(sizes[1][k]/sizes[0][k] for k in (0,1)))
    return dict(result,direction=label,reference_pts=first['pts'],end_pts=last['pts'],
                displacement_pixels=delta,inward_pixels=component,box_scale_ratio=scale,
                caveat='Partial boxes and camera motion can mimic movement; do not use as an outcome.')


def summarize_runs(runs, frames, lifecycle, endpoint_assessments, geometry):
    """Describe coverage/state without manufacturing normal or intrusion labels."""
    stamps=[clock(f['pts']) for f in frames]
    if not stamps or any(a>=b for a,b in zip(stamps,stamps[1:])):
        raise ValueError('Full increasing source clock required')
    linked=candidate_links(lifecycle)
    states={e['event_id']:e['automatic_status'] for e in lifecycle['evidence']}
    records=[]
    for rid, rows in runs.items():
        if not rows:
            raise ValueError('Nonempty observation runs required')
        for a,b in zip(rows,rows[1:]):
            if clock(a['pts'])>=clock(b['pts']):raise ValueError('Increasing actual run PTS required')
        for row in rows:
            i=row['frame_index']; box=row['bbox']
            if not 0<=i<len(frames) or abs(row['pts']-frames[i]['pts'])>1e-9:
                raise ValueError('Run clock must reference an actual source frame')
            if len(box)!=4 or not (0<=box[0]<box[2]<=1 and 0<=box[1]<box[3]<=1):
                raise ValueError('Normalized actual box required')
        ids=sorted(linked.get(rid,()))
        status_set={states[eid] for eid in ids}
        category=('no_suspicion' if not ids else 'confirmed_related' if CONFIRMED in status_set
                  else 'pending' if SUSPECTED in status_set else 'released')
        assessment=deepcopy(endpoint_assessments.get(rid,{}))
        records.append(dict(run_id=rid,first_pts=rows[0]['pts'],last_pts=rows[-1]['pts'],
            actual_observations=len(rows),first_actual_bbox=rows[0]['bbox'],
            last_actual_bbox=rows[-1]['bbox'],event_ids=ids,state_category=category,
            candidate_states={eid:states[eid] for eid in ids},
            endpoint_assessment=assessment,box_motion_diagnostic=box_motion(rows,geometry),
            actual_release_event_ids=[eid for eid in ids if states[eid]==RELEASED],
            normal_pedestrian_verified=False,person_identity_verified=False))
    return dict(records=records,run_counts=dict(Counter(r['state_category'] for r in records)),
        endpoint_reasons=dict(Counter(r['endpoint_assessment'].get('reason','not_evaluated') for r in records)),
        unit='geometric_observation_runs_not_people_or_independent_samples',
        statuses_changed=False,accuracy=None,
        note='No-suspicion runs are NOT counted as released suspicions or verified normal pedestrians.')


def audit_all_runs(runs, frames, lifecycle, engine, portal, *, history_factory=None,
                   assessor=None):
    """Use existing signed-direction/absence rule for every recorded endpoint.

    Evaluates at the first real frame after the unchanged wait. Source gaps and
    clip termination never manufacture a successful departure. Diagnostic raw
    runs do not acquire alarms, handoffs or status changes here.
    """
    if history_factory is None or assessor is None:
        from .lifecycle_followup import ObservationHistory, assess_loss
        history_factory=history_factory or ObservationHistory
        assessor=assessor or assess_loss
    history=history_factory(runs,frames)
    stamps=[f['pts'] for f in frames]; due=defaultdict(list); assessments={}
    for rid,rows in runs.items():
        i=bisect_left(stamps,rows[-1]['pts']+engine.policy.loss_wait-1e-7)
        if i==len(stamps):
            assessments[rid]=dict(outcome=None,reason='recording_ends_before_loss_wait',
                                  last_observed_pts=rows[-1]['pts'])
        else:due[i].append(rid)
    for index,frame in enumerate(frames):
        history.advance(frame)
        for rid in due[index]:
            assessments[rid]=assessor(history,engine,portal,rid,index,
                                      loss_wait=engine.policy.loss_wait)
    result=summarize_runs(runs,frames,lifecycle,assessments,engine.geometry)
    result.update(diagnostic_endpoints=len(assessments),
                  new_model_calls=0,new_tracking_calls=0,synthetic_suspicions_created=0)
    return result
