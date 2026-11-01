"""EXP-0047: replay actual observations into suspicion / release / confirmation.

No detector/tracker/flow/VLM invocation or raw-data mutation. This is an offline
proposal with NEW status-change notification intents, not external delivery.
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
from .incident_lifecycle import IncidentLifecycle, SUSPECTED, CONFIRMED, digest
from .lifecycle_followup import ObservationHistory, assess_loss, followup_run, loss_resolution


def locate_time(stamps, at):
    index = bisect_left(stamps, at-1e-7)
    if index==len(stamps) or abs(stamps[index]-at)>1e-6:
        raise ValueError('Candidate clock is not an actual saved source frame')
    return index


def replay(baseline, history, portal_events, runs, frames, scene, region,
           *, direction_engine=None, portal_gate=None):
    """Prefix-only replay. Existing A confirmations are immutable positive facts
    of the earlier rule, not human ground truth; retain their exact source PTS.
    Only linked evidence can be released. An unbound source stays pending.
    """
    if direction_engine is None:
        from .directional_loss import SavedGateDirection
        direction_engine = SavedGateDirection(frames,scene)
    if portal_gate is None:
        from .portal_births import PortalGate
        portal_gate = PortalGate(scene,region,history['events'][0]['camera_id'])
    obs = ObservationHistory(runs,frames)
    events = deepcopy(history['events']+list(portal_events))
    if len({e['event_id'] for e in events})!=len(events):
        raise ValueError('Duplicate or overlapping original and portal candidate IDs')
    if not events: raise ValueError('Expected the preserved candidate inputs')
    scopes = {tuple(e[k] for k in ('session_id','camera_id','gate_id')) for e in events}
    if len(scopes)!=1: raise ValueError('One recording/camera/gate per replay')
    namespace = 'EXP-0047:'+digest(dict(scope=next(iter(scopes)),region=region,scene=scene))[:16]
    lifecycle = IncidentLifecycle(GroupPolicy(**history['policy']),namespace=namespace)
    stamps = [r['pts'] for r in frames]
    scheduled, confirmations = defaultdict(list), defaultdict(list)
    segments = {s['id']:s for s in baseline['segments']}
    for event in events: scheduled[locate_time(stamps,event['decision_time_pts'])].append(event)
    for decision in history['decisions']:
        if not decision['automatic_confirmation']: continue
        index = locate_time(stamps,decision['decision_time_pts'])
        item=dict(kind='preserved_confirmation',event_ids=[decision['event_id']],
            decision_time_pts=frames[index]['pts'],evidence_until_pts=frames[index]['pts'],
            confirmation_source='EXP-0045',source_decision=deepcopy(decision))
        item['resolution_id']=digest(item); confirmations[index].append(item)
    attempted = set(); followup_audits=[]; counts=Counter()
    for index,frame in enumerate(frames):
        at=frame['pts']; obs.advance(frame)
        candidates=[obs.bind(e,segments) for e in scheduled[index]]
        # Include candidates first observed in this batch, without exposing them
        # before their original emitted time. Evidence collection stays separate.
        pending = defaultdict(list)
        for eid in lifecycle.pending():
            key=lifecycle.evidence[eid]['observation_key']
            if key is not None: pending[key].append(eid)
        for row in candidates:
            if row['observation_key'] is not None:
                pending[row['observation_key']].append(row['event']['event_id'])
        resolutions=deepcopy(confirmations[index]); proposals={}
        for rid,ids in pending.items():
            rows=obs.rows[rid]
            if not rows or rows[-1]['frame_index']==index: continue
            identity=(rid,rows[-1]['pts'],tuple(sorted(ids)))
            if identity in attempted: continue
            handoff=followup_run(obs,direction_engine,rid,index)
            if handoff['successor']:
                proposals[rid]=(handoff,ids,identity)
                continue
            if at-rows[-1]['pts'] < direction_engine.policy.loss_wait-1e-6: continue
            audit=assess_loss(obs,direction_engine,portal_gate,rid,index,
                              loss_wait=direction_engine.policy.loss_wait)
            audit.update(event_ids=sorted(ids),handoff=handoff)
            followup_audits.append(audit); counts[audit['reason']]+=1
            attempted.add(identity)
            if audit['outcome']: resolutions.append(loss_resolution(audit,ids))
        # Do not merge two independent disappearing observations into one person.
        destinations=Counter(p[0]['successor'] for p in proposals.values())
        for rid,(handoff,ids,identity) in proposals.items():
            dest=handoff['successor']
            if destinations[dest]>1:
                counts['competing_source_handoffs']+=1
                followup_audits.append(dict(run_id=rid,decision_time_pts=at,
                    event_ids=ids,reason='competing_source_handoffs',handoff=handoff,outcome=None))
                attempted.add(identity); continue
            item=dict(kind='observation_handoff',event_ids=sorted(ids),observation_key=rid,
                next_observation_key=dest,decision_time_pts=at,evidence_until_pts=at,
                actual_correspondence=True,evidence=handoff,human_verified=False)
            item['resolution_id']=digest(item); resolutions.append(item)
            obs.link(rid,dest)
            counts['observation_handoffs']+=1
        if candidates or resolutions:
            lifecycle.process(at,candidates,resolutions)
    result=lifecycle.export()
    expected={e['event_id']:e for e in events}
    if {e['event_id']:e for e in result['events']}!=expected:
        raise ValueError('Raw candidate payload changed during lifecycle replay')
    # No final flush: the end of a clip or feature-window expiration is not loss.
    result.update(video_id=history['video_id'],source_window=deepcopy(history['source_window']),
        available_after_pts=history.get('available_after_pts',history['source_window'][1]),
        binding_audit=obs.bindings,followup_audit=followup_audits,
        followup_counts=dict(counts),stored_observation_runs_reused=True,
        direction_rule_changed=False,source_end_forced_release=False,
        original_history_event_count=len(history['events']),portal_event_count=len(portal_events),
        unbound_candidates=sum(b['observation_key'] is None for b in obs.bindings),
        detector_calls=0,tracker_calls=0,flow_calls=0,vlm_calls=0)
    positive={d['event_id']:d for d in history['decisions'] if d['automatic_confirmation']}
    states={e['event_id']:e for e in result['evidence']}
    if any(states[eid]['automatic_status']!=CONFIRMED for eid in positive):
        raise ValueError('A preserved confirmation was lost')
    result['preserved_confirmation_source_pts']={eid:d['decision_time_pts'] for eid,d in positive.items()}
    result['first_confirmation_notice_pts']=[n['decision_time_pts'] for n in result['notification_intents']
                                              if n['kind']=='confirmation']
    return result


def execute(baseline_path,paths_directory,portal_directory,output):
    from .exp0044_application import prepared_inputs,sha,save
    from .exp0045_application import select_scene
    from .portal_births import PortalGate
    begin=time.perf_counter(); directory=Path(portal_directory); out=Path(output)
    if (out.exists() or out.is_symlink() or any(p.is_symlink() for p in out.parents)
            or not out.resolve().is_relative_to(Path('outputs').resolve())):
        raise ValueError('Use a fresh non-symlink local outputs directory')
    baseline,original,frames,old_scene,group,protected=prepared_inputs(baseline_path,paths_directory)
    read=lambda name:json.loads((directory/name).read_text(encoding='utf-8'))
    request, summary = read('request.json'),read('summary.json')
    if request.get('experiment')!='EXP-0046' or summary.get('experiment')!='EXP-0046':
        raise ValueError('Frozen EXP-0046 outputs required')
    if request['input_sha256']!=summary['input_sha256']:
        raise ValueError('EXP46 input binding mismatch')
    for path,expected in request['input_sha256'].items():
        if sha(path)!=expected: raise ValueError('Preserved input changed: '+path)
        protected[path]=expected
    names=('request.json','summary.json','history-cards.json','history-decisions.json',
           'scene-used.json','portal-region.json','inside-birth-events.json',
           'observation-runs.json','case-audit.json','portal-only-cards.json')
    protected.update({str(directory/n):sha(directory/n) for n in names})
    history=read('history-cards.json'); scene=read('scene-used.json')
    if (history['video_id']!=baseline['video_id'] or summary['video_id']!=baseline['video_id']
            or history['events']!=original['events'] or
            history['decisions']!=read('history-decisions.json') or
            scene!=select_scene(baseline['video_id'],old_scene,request.get('scene_override')) or
            summary['frames']!=len(frames)):
        raise ValueError('Saved history, scene or source window differs')
    region=read('portal-region.json'); events=read('inside-birth-events.json')
    if read('portal-only-cards.json')['events']!=events:
        raise ValueError('Portal candidate source differs')
    PortalGate(scene,region,history['events'][0]['camera_id'])
    runs=read('observation-runs.json')
    files=('incident_lifecycle.py','lifecycle_followup.py','exp0047_application.py',
           'directional_loss.py','portal_births.py','gate_episode_evidence.py','incident_cards.py')
    code={str(Path(__file__).with_name(n)):sha(Path(__file__).with_name(n)) for n in files}
    out.mkdir(parents=True,exist_ok=False)
    save(out/'request.json',dict(experiment='EXP-0047',input_sha256=protected,code_sha256=code,
        portal_directory=str(directory),new_inference=False,new_state_policy=True))
    try:
        result=replay(baseline,history,events,runs,frames,scene,region)
        if protected!={p:sha(p) for p in protected} or code!={p:sha(p) for p in code}:
            raise ValueError('Input or code changed during comparison')
        (out/'history-preserved.json').write_bytes((directory/'history-cards.json').read_bytes())
        (out/'portal-preserved.json').write_bytes((directory/'portal-only-cards.json').read_bytes())
        save(out/'lifecycle-cards.json',result)
        save(out/'notification-intents.json',result['notification_intents'])
        save(out/'binding-audit.json',result['binding_audit'])
        save(out/'followup-audit.json',result['followup_audit'])
        save(out/'resolutions.json',result['resolutions'])
        report=dict(experiment='EXP-0047',video_id=history['video_id'],frames=len(frames),
            counts=result['counts'],followup_counts=result['followup_counts'],
            unbound_candidates=result['unbound_candidates'],
            existing_confirmations_preserved=True,
            preserved_confirmation_source_pts=result['preserved_confirmation_source_pts'],
            first_confirmation_notice_pts=result['first_confirmation_notice_pts'],
            elapsed_seconds=time.perf_counter()-begin,input_sha256=protected,code_sha256=code,
            detector_calls=0,tracker_calls=0,flow_calls=0,vlm_calls=0,
            accuracy=None,realtime=False,visual_validation='pending',
            manual_reviews_modified=False,external_notifications_sent=0,
            limitations=['Release is a provisional camera rule, not proof no intrusion occurred.',
                'Saved geometric runs/point routing may mix people; audit every release.',
                'Unknown/unbound evidence is retained, not automatically timed out.',
                'First false suspicion is not undone by a later release.',
                'Card grouping may change; confirmation notifications have independent keys.',
                'Outputs require a new viewer adapter; old notification code is incompatible.'])
        save(out/'summary.json',report); return report
    except Exception as exc:
        save(out/'failure.json',dict(error=repr(exc),elapsed_seconds=time.perf_counter()-begin))
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline','paths','portal-result','output'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(execute(a.baseline,a.paths,a.portal_result,a.output),ensure_ascii=False,indent=2))

if __name__=='__main__': main()
