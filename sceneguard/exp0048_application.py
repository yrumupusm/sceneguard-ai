"""EXP-0048: incident-scoped outcomes plus all-run pedestrian coverage audit.

Uses frozen EXP35/42/46/47 files. No detector, tracker, flow, VLM, training, new
regions, live notifications, raw ID merging, or human-review mutation.
"""
from __future__ import annotations
from bisect import bisect_left
from collections import defaultdict, Counter
from copy import deepcopy
from pathlib import Path
import argparse
import json
import time

from .incident_cards import GroupPolicy
from .incident_lifecycle import CONFIRMED, digest
from .incident_outcome_scope import ScopedIncidentLifecycle
from .passage_audit import audit_all_runs


def locate_time(stamps, at):
    index=bisect_left(stamps,at-1e-7)
    if index==len(stamps) or abs(stamps[index]-at)>1e-6:
        raise ValueError('Candidate clock must be an actual source frame')
    return index


def replay_scoped(baseline,history,portal_events,runs,frames,scene,region,
                  *,direction_engine=None,portal_gate=None):
    from .directional_loss import SavedGateDirection
    from .portal_births import PortalGate
    from .lifecycle_followup import ObservationHistory, followup_run, assess_loss, loss_resolution
    engine=direction_engine or SavedGateDirection(frames,scene)
    obs=ObservationHistory(runs,frames)
    events=deepcopy(history['events']+list(portal_events))
    if not events or len({e['event_id'] for e in events})!=len(events):
        raise ValueError('Nonempty distinct frozen candidate stream required')
    scopes={tuple(e[k] for k in ('session_id','camera_id','gate_id')) for e in events}
    if len(scopes)!=1:raise ValueError('One session/camera/gate per replay')
    portal=portal_gate or PortalGate(scene,region,events[0]['camera_id'])
    namespace='EXP-0048:'+digest(dict(scope=next(iter(scopes)),region=region,scene=scene))[:16]
    life=ScopedIncidentLifecycle(GroupPolicy(**history['policy']),namespace=namespace)
    scheduled=defaultdict(list); confirmations=defaultdict(list)
    stamps=[f['pts'] for f in frames]; segments={s['id']:s for s in baseline['segments']}
    for e in events:scheduled[locate_time(stamps,e['decision_time_pts'])].append(e)
    for d in history['decisions']:
        if not d['automatic_confirmation']:continue
        i=locate_time(stamps,d['decision_time_pts'])
        r=dict(kind='preserved_confirmation',event_ids=[d['event_id']],
            decision_time_pts=stamps[i],evidence_until_pts=stamps[i],
            confirmation_source='EXP-0045',source_decision=deepcopy(d))
        r['resolution_id']=digest(r);confirmations[i].append(r)
    attempted=set();audits=[];counts=Counter()
    for index,frame in enumerate(frames):
        at=frame['pts'];obs.advance(frame)
        candidates=[obs.bind(e,segments) for e in scheduled[index]]
        pending=defaultdict(list)
        for eid in life.pending():
            key=life.evidence[eid]['observation_key']
            if key is not None:pending[key].append(eid)
        for c in candidates:
            if c['observation_key'] is not None:pending[c['observation_key']].append(c['event']['event_id'])
        resolutions=deepcopy(confirmations[index]);proposals={}
        for rid,ids in pending.items():
            rows=obs.rows[rid]
            if not rows or rows[-1]['frame_index']==index:continue
            identity=(rid,rows[-1]['pts'],tuple(sorted(ids)))
            if identity in attempted:continue
            handoff=followup_run(obs,engine,rid,index)
            if handoff['successor']:
                proposals[rid]=(handoff,ids,identity);continue
            if at-rows[-1]['pts']<engine.policy.loss_wait-1e-6:continue
            audit=assess_loss(obs,engine,portal,rid,index,loss_wait=engine.policy.loss_wait)
            audit.update(event_ids=sorted(ids),handoff=handoff)
            audits.append(audit);counts[audit['reason']]+=1;attempted.add(identity)
            if audit['outcome']:resolutions.append(loss_resolution(audit,ids))
        destinations=Counter(h[0]['successor'] for h in proposals.values())
        for rid,(handoff,ids,identity) in proposals.items():
            dest=handoff['successor']
            if destinations[dest]>1:
                counts['competing_source_handoffs']+=1
                audits.append(dict(run_id=rid,decision_time_pts=at,event_ids=ids,
                    reason='competing_source_handoffs',handoff=handoff,outcome=None))
                attempted.add(identity);continue
            r=dict(kind='observation_handoff',event_ids=sorted(ids),observation_key=rid,
                next_observation_key=dest,decision_time_pts=at,evidence_until_pts=at,
                actual_correspondence=True,evidence=handoff,human_verified=False)
            r['resolution_id']=digest(r);resolutions.append(r);obs.link(rid,dest)
            counts['observation_handoffs']+=1
        if candidates or resolutions:life.process(at,candidates,resolutions)
    result=life.export()
    if {e['event_id']:e for e in result['events']}!={e['event_id']:e for e in events}:
        raise ValueError('Original candidate payload changed')
    states={e['event_id']:e for e in result['evidence']}
    positive={d['event_id']:d for d in history['decisions'] if d['automatic_confirmation']}
    if any(states[eid]['automatic_status']!=CONFIRMED for eid in positive):
        raise ValueError('Original confirmation lost')
    result.update(video_id=history['video_id'],source_window=deepcopy(history['source_window']),
        available_after_pts=history.get('available_after_pts',history['source_window'][1]),
        binding_audit=obs.bindings,followup_audit=audits,followup_counts=dict(counts),
        preserved_confirmation_source_pts={eid:d['decision_time_pts'] for eid,d in positive.items()},
        direction_rule_changed=False,source_end_forced_release=False,
        detector_calls=0,tracker_calls=0,flow_calls=0,vlm_calls=0)
    audit=audit_all_runs(runs,frames,result,engine,portal)
    return result,audit


def prepare_inputs(baseline_path,paths_directory,portal_directory,previous_directory):
    from .exp0044_application import prepared_inputs,sha,save
    from .exp0045_application import select_scene
    from .portal_births import PortalGate
    directory=Path(portal_directory);previous=Path(previous_directory)
    baseline,original,frames,old_scene,group,protected=prepared_inputs(baseline_path,paths_directory)
    read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
    request=read(directory/'request.json');summary=read(directory/'summary.json')
    old_request=read(previous/'request.json');old_summary=read(previous/'summary.json')
    if (request.get('experiment')!='EXP-0046' or summary.get('experiment')!='EXP-0046'
            or old_request.get('experiment')!='EXP-0047' or old_summary.get('experiment')!='EXP-0047'):
        raise ValueError('Preserved EXP46 and successful EXP47 sources required')
    for req,summ in ((request,summary),(old_request,old_summary)):
        if req['input_sha256']!=summ['input_sha256']:raise ValueError('Input binding mismatch')
        for path,expected in req['input_sha256'].items():
            if sha(path)!=expected:raise ValueError('Frozen source changed: '+path)
            protected[path]=expected
    names=('request.json','summary.json','history-cards.json','history-decisions.json',
           'scene-used.json','portal-region.json','inside-birth-events.json','observation-runs.json',
           'portal-only-cards.json')
    protected.update({str(directory/n):sha(directory/n) for n in names})
    protected.update({str(previous/n):sha(previous/n) for n in ('request.json','summary.json','lifecycle-cards.json')})
    history=read(directory/'history-cards.json');scene=read(directory/'scene-used.json')
    events=read(directory/'inside-birth-events.json');region=read(directory/'portal-region.json')
    runs=read(directory/'observation-runs.json');prior=read(previous/'lifecycle-cards.json')
    if (history['video_id']!=baseline['video_id'] or summary['video_id']!=baseline['video_id']
            or old_summary['video_id']!=baseline['video_id'] or prior['video_id']!=baseline['video_id']
            or history['events']!=original['events']
            or history['decisions']!=read(directory/'history-decisions.json')
            or scene!=select_scene(baseline['video_id'],old_scene,request.get('scene_override'))
            or summary['frames']!=len(frames) or old_summary['frames']!=len(frames)
            or read(directory/'portal-only-cards.json')['events']!=events):
        raise ValueError('Sources, scene, candidate payloads or clocks differ')
    expected={e['event_id']:e for e in history['events']+events}
    if {e['event_id']:e for e in prior['events']}!=expected:raise ValueError('EXP47 candidates differ')
    PortalGate(scene,region,history['events'][0]['camera_id'])
    files=('exp0048_application.py','incident_outcome_scope.py','passage_audit.py',
           'incident_lifecycle.py','lifecycle_followup.py','directional_loss.py',
           'portal_births.py','gate_episode_evidence.py','incident_cards.py')
    code={str(Path(__file__).with_name(n)):sha(Path(__file__).with_name(n)) for n in files}
    from .lifecycle_followup import ObservationHistory
    from .directional_loss import SavedGateDirection
    ObservationHistory(runs,frames)
    SavedGateDirection(frames,scene)
    return baseline,history,events,runs,frames,scene,region,prior,protected,code


def execute(baseline_path,paths_directory,portal_directory,previous_directory,output):
    from .exp0044_application import sha,save
    start=time.perf_counter();directory=Path(portal_directory);previous=Path(previous_directory);out=Path(output)
    if out.exists() or out.is_symlink() or any(p.is_symlink() for p in out.parents) or not out.resolve().is_relative_to(Path('outputs').resolve()):
        raise ValueError('Use a fresh local outputs directory without symlinks')
    baseline,history,events,runs,frames,scene,region,prior,protected,code=prepare_inputs(
        baseline_path,paths_directory,portal_directory,previous_directory)
    out.mkdir(parents=True,exist_ok=False)
    save(out/'request.json',dict(experiment='EXP-0048',input_sha256=protected,code_sha256=code,
        prior_directory=str(previous),portal_directory=str(directory),new_inference=False))
    try:
        result,audit=replay_scoped(baseline,history,events,runs,frames,scene,region)
        if protected!={p:sha(p) for p in protected} or code!={p:sha(p) for p in code}:
            raise ValueError('Input or code changed during comparison')
        (out/'prior-lifecycle-preserved.json').write_bytes((previous/'lifecycle-cards.json').read_bytes())
        (out/'history-preserved.json').write_bytes((directory/'history-cards.json').read_bytes())
        save(out/'lifecycle-cards.json',result);save(out/'all-observations-audit.json',audit)
        save(out/'outcome-routing.json',result['outcome_routing'])
        save(out/'notification-intents.json',result['notification_intents'])
        save(out/'followup-audit.json',result['followup_audit'])
        notices=lambda bundle:[dict(kind=n['kind'],pts=n['decision_time_pts'],incident_id=n['incident_id'])
                                for n in bundle['notification_intents']]
        report=dict(experiment='EXP-0048',video_id=history['video_id'],frames=len(frames),
            prior_counts=prior['counts'],counts=result['counts'],
            prior_notices=notices(prior),notices=notices(result),
            outcome_routing_reasons=dict(Counter(r['reason'] for r in result['outcome_routing'])),
            all_run_categories=audit['run_counts'],all_run_endpoint_reasons=audit['endpoint_reasons'],
            preserved_confirmation_source_pts=result['preserved_confirmation_source_pts'],
            elapsed_seconds=time.perf_counter()-start,input_sha256=protected,code_sha256=code,
            detector_calls=0,tracker_calls=0,flow_calls=0,vlm_calls=0,
            accuracy=None,realtime=False,visual_validation='pending',external_notifications_sent=0,
            limitations=['Latest connected incident ownership is bookkeeping, not identity or a verified incident boundary.',
                'Old cards excluded from a newer confirmation remain pending; they are not silently cleared.',
                'Mixed-origin outward loss is retained rather than clearing unrelated evidence.',
                'Passing without a suspicion is not a successful release.',
                'Diagnostic box motion is not used for state changes; feature coverage outside the gate may be poor.',
                'All-run counts are geometric runs, not independent people or accuracy samples.'])
        save(out/'summary.json',report);return report
    except Exception as exc:
        save(out/'failure.json',dict(error=repr(exc),elapsed_seconds=time.perf_counter()-start));raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline','paths','portal-result','previous','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(json.dumps(execute(a.baseline,a.paths,a.portal_result,a.previous,a.output),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
