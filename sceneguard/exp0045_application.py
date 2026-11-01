"""EXP-0045 saved-data comparison; no inference, old-file edits or live delivery.

007 explicitly selects the approved local inside revision. Historical inputs are
validated against their ORIGINAL scene first; their hashes are never rewritten.
"""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import argparse
import hashlib
import json
import time

from .gate_episode_evidence import EpisodePolicy, InsideBirths, history_decision, revised_scene

APPROVED_007_SCENE = Path('runtime/region-revisions/007-inside-20261101-v1/scene007.json')


def select_scene(video_id, original, scene_path=None):
    if video_id == 'E01_007':
        if scene_path is None or Path(scene_path).resolve() != APPROVED_007_SCENE.resolve():
            raise ValueError('007 requires the explicitly approved revised inside scene')
        return revised_scene(original, json.loads(Path(scene_path).read_text(encoding='utf-8')))
    if video_id != 'E01_030' or scene_path is not None:
        raise ValueError('030 must retain its original scene without override')
    return deepcopy(original)


def grouping_effects(baseline, proposal):
    """Quantify raw-event preservation separately from changed notification intents."""
    current = {r['event_id']: r for r in proposal['timeline']}
    old_cards = {eid: c for c in baseline['cards'] for eid in c['event_ids']}
    new_cards = {eid: c for c in proposal['cards'] for eid in c['event_ids']}
    rows = []
    for old in baseline['timeline']:
        eid = old['event_id']; new = current[eid]
        a, b = old_cards[eid], new_cards[eid]
        rows.append(dict(event_id=eid, decision_time_pts=old['decision_time_pts'],
            baseline_incident_id=a['incident_id'], proposed_incident_id=b['incident_id'],
            baseline_notify=old['notify'], proposed_notify=new['notify'],
            original_notice_absorbed=old['notify'] and not new['notify'],
            baseline_first_notification_pts=a['first_notification_pts'],
            proposed_first_notification_pts=b['first_notification_pts'],
            first_notification_shift_pts=b['first_notification_pts']-a['first_notification_pts'],
            original_membership_preserved=set(a['event_ids']) == set(b['event_ids']) & set(old_cards)))
    return dict(original_event_rows=len(rows),
        baseline_notification_intents=sum(r['baseline_notify'] for r in rows),
        original_notification_intents_retained=sum(r['baseline_notify'] and r['proposed_notify'] for r in rows),
        original_notification_intents_absorbed=sum(r['original_notice_absorbed'] for r in rows),
        original_rows_with_changed_incident=sum(r['baseline_incident_id'] != r['proposed_incident_id'] for r in rows),
        original_rows_with_changed_membership=sum(not r['original_membership_preserved'] for r in rows),
        rows=rows)


def normalize_birth(raw, baseline, scene):
    if not baseline['events']:
        raise ValueError('Original scoped candidate stream required')
    scope={k:baseline['events'][0][k] for k in ('session_id','camera_id','gate_id')}
    if not raw['birth_site']['inside_birth_site'] or raw['evidence_until_pts']!=raw['decision_time_pts']:
        raise ValueError('Gate-local, causal birth evidence required')
    binding=dict(algorithm='EXP-0045-inside-birth',scope=scope,video_id=baseline['video_id'],
                 birth_pts=raw['birth_pts'],refs=raw['observation_refs'],scene=scene)
    eid=hashlib.sha256(json.dumps(binding,sort_keys=True,allow_nan=False).encode()).hexdigest()
    return dict(**scope,event_id=eid,video_id=baseline['video_id'],
        status='침입 의심',decision_time_pts=raw['decision_time_pts'],track_ids=[],
        source_ref=dict(collection='inside_birth_events',source_pointer='/inside_birth_events/'+eid,
                        segment=raw['run_id'],raw_id=None),source_event=deepcopy(raw))


def annotate(bundle, decisions):
    result=deepcopy(bundle); by_id={d['event_id']:d for d in decisions}
    def card_status(card):
        confirmed=[by_id[eid] for eid in card['event_ids'] if eid in by_id and by_id[eid]['automatic_confirmation']]
        card.update(automatic_status='침입 확인' if confirmed else '침입 의심',
            automatic_confirmation=bool(confirmed),human_verified=False,
            decision_source='automatic_rule',
            first_confirmation_pts=min((d['decision_time_pts'] for d in confirmed),default=None))
    for card in result['cards']:card_status(card)
    for row in result['timeline']:
        if 'card' in row:card_status(row['card'])
    result['alert_cards']=[deepcopy(c) for c in result['cards'] if c['notification_eligible']]
    result['review_only_cards']=[deepcopy(c) for c in result['cards'] if not c['notification_eligible']]
    result.update(experiment='EXP-0045',decisions=deepcopy(decisions),
        baseline_alerts_suppressed=0,manual_reviews_modified=False,
        live_notifications_enabled=False,accuracy=None,realtime=False)
    return result


def evaluate(baseline, bundle, frames, scene, group, policy=EpisodePolicy(), engine_factory=None):
    if engine_factory is None:
        from .directional_loss import SavedGateDirection
        engine_factory=SavedGateDirection
    engine=engine_factory(frames,scene); segments={s['id']:s for s in baseline['segments']}
    if abs(baseline['policy']['loss_wait']-engine.policy.loss_wait)>1e-6:
        raise ValueError('Keep the original disappearance waiting time')
    decisions=[]
    for event in bundle['events']:
        source=event['source_event']
        if source.get('reason')!='recent_gate_presence_then_loss':continue
        segment=segments[source['segment']]
        if source['raw_id']!=segment['raw_id'] or source['decision_time_pts']!=event['decision_time_pts']:
            raise ValueError('Candidate/segment source mismatch')
        result=history_decision(engine.classify(source,segment),segment,scene,policy)
        result.update(event_id=event['event_id'],source_ref=deepcopy(event['source_ref']))
        decisions.append(result)
    births=InsideBirths(scene,policy); raw_births=[]
    for frame in frames:raw_births.extend(births.step(frame))
    new=[normalize_birth(r,bundle,scene) for r in raw_births]
    old_ids={e['event_id'] for e in bundle['events']}
    if len({e['event_id'] for e in new})!=len(new) or old_ids.intersection(e['event_id'] for e in new):
        raise ValueError('Distinct new candidate identities required')
    views={}
    for name,rows in [('history',bundle['events']),('birth-only',new),('combined',bundle['events']+new)]:
        ids = {r['event_id'] for r in rows}
        result=annotate(group(rows,[]),[d for d in decisions if d['event_id'] in ids])
        result.update(video_id=bundle['video_id'],source_window=deepcopy(bundle['source_window']),
            available_after_pts=bundle.get('available_after_pts',bundle['source_window'][1]),
            comparison_mode=name,episode_policy=asdict(policy),
            person_detector_changed=False,candidate_generation_changed=(name!='history'),
            new_birth_alone_is_confirmation=False)
        views[name]=result
        if name != 'birth-only':
            result['grouping_effects'] = grouping_effects(bundle, result)
    for field in ('events','cards','timeline','counts'):
        # Annotation may add automatic fields, but original grouping is fixed.
        if field in ('cards','timeline'):
            continue
        if views['history'][field] != bundle[field]:
            raise ValueError('History-only changed original grouping: '+field)
    if any(views['history']['grouping_effects'][k] for k in
           ('original_notification_intents_absorbed','original_rows_with_changed_incident',
            'original_rows_with_changed_membership')):
        raise ValueError('History-only changed baseline first notices or membership')
    preserved={e['event_id']:e for e in views['combined']['events'] if e['event_id'] in old_ids}
    if preserved!={e['event_id']:e for e in bundle['events']}:
        raise ValueError('An original candidate changed')
    return views,decisions,new,births.audit


def execute(baseline_path, paths_directory, output, scene_path=None):
    from .exp0044_application import prepared_inputs,sha,save
    from .approach_disappearance import validate_scene
    begin=time.perf_counter();out=Path(output)
    if out.exists() or out.is_symlink() or any(p.is_symlink() for p in out.parents) or not out.resolve().is_relative_to(Path('outputs').resolve()):
        raise ValueError('Use a fresh non-symlink outputs directory')
    baseline,bundle,frames,original,group,before=prepared_inputs(baseline_path,paths_directory)
    scene=select_scene(baseline['video_id'],original,scene_path)
    if scene_path is not None:
        scene_path=Path(scene_path);before[str(scene_path)]=sha(scene_path)
    validate_scene(scene)
    policy=EpisodePolicy().validate()
    files=['exp0045_application.py','gate_episode_evidence.py','exp0044_application.py',
        'directional_loss.py','incident_notifications.py','incident_cards.py']
    code={str(Path(__file__).with_name(n)):sha(Path(__file__).with_name(n)) for n in files}
    out.mkdir(parents=True,exist_ok=False)
    save(out/'request.json',dict(experiment='EXP-0045',policy=asdict(policy),input_sha256=before,
        code_sha256=code,scene_override=None if scene_path is None else str(scene_path),
        old_scene_binding_preserved=True,stored_paths_not_regenerated=True))
    views,decisions,new,audits=evaluate(baseline,bundle,frames,scene,group,policy)
    if before!={p:sha(p) for p in before} or code!={p:sha(p) for p in code}:
        raise ValueError('Protected source changed during execution')
    (out/'baseline-cards.json').write_bytes((Path(paths_directory)/'baseline-cards.json').read_bytes())
    for name,view in views.items():save(out/(name+'-cards.json'),view)
    save(out/'history-decisions.json',decisions);save(out/'inside-birth-events.json',new)
    save(out/'birth-audits.json',audits);save(out/'scene-used.json',scene)
    effects={name:views[name]['grouping_effects'] for name in ('history','combined')}
    save(out/'grouping-effects.json',effects)
    report=dict(experiment='EXP-0045',video_id=baseline['video_id'],frames=len(frames),
        loss_cases=len(decisions),automatic_loss_confirmations=sum(d['automatic_confirmation'] for d in decisions),
        inside_birth_candidates=len(new),counts={k:v['counts'] for k,v in views.items()},
        first_notifications={k:[c['first_notification_pts'] for c in v['alert_cards']] for k,v in views.items()},
        first_confirmations={k:[c['first_confirmation_pts'] for c in v['alert_cards']] for k,v in views.items()},
        original_first_notifications=[c['first_notification_pts'] for c in bundle['alert_cards']],
        grouping_effects={name:{k:v for k,v in effect.items() if k!='rows'} for name,effect in effects.items()},
        newly_confirmed_loss_cases=[d['segment'] for d in decisions if d['automatic_confirmation']
            and d['rule_id']=='gate_history_loss_v1' and d['reason']=='recent_gate_encounter_inward_then_loss'],
        elapsed_seconds=time.perf_counter()-begin,input_sha256=before,code_sha256=code,
        detector_calls=0,tracker_calls=0,flow_calls=0,vlm_calls=0,accuracy=None,
        reviewed_intrusion_successes=None,manual_reviews_modified=False,
        limitation='Both geometry and policy are revised for 007; not an isolated region experiment. New births are suspicions, not people counts. Combined grouping can alter first notifications; inspect before adoption.')
    save(out/'summary.json',report);return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline',type=Path,required=True);p.add_argument('--paths',type=Path,required=True)
    p.add_argument('--scene',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(execute(a.baseline,a.paths,a.output,a.scene),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
