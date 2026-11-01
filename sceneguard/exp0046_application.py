"""Compare a fixed projected portal with EXP45 B; copy EXP45 A unchanged.

Requires preserved local EXP35/42/45 inputs and a separately calibrated polygon.
No person inference, flow, identity inference, new loss rule or live notification.
"""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import argparse
import json
import time

from .portal_births import compare_births, digest, KIND
from .gate_episode_evidence import EpisodePolicy


def normalize_portal(raw, history, region):
    if not history['events']:
        raise ValueError('A scoped historical stream is required')
    scope={k:history['events'][0][k] for k in ('session_id','camera_id','gate_id')}
    if any(any(e[k]!=scope[k] for k in scope) for e in history['events']):
        raise ValueError('Do not mix cameras, gates or recording sessions')
    if (raw.get('rule_id')!=KIND or not raw['birth_site']['inside_birth_site'] or
            raw['evidence_until_pts']!=raw['decision_time_pts'] or
            raw.get('automatic_confirmation') is not False or
            raw.get('status')!='침입 의심' or
            not 0 <= raw['birth_pts'] <= raw['decision_time_pts'] or
            any(not raw['birth_pts'] <= r['pts'] <= raw['decision_time_pts']
                for r in raw['observation_refs'])):
        raise ValueError('Causal portal suspicion required; never promote a birth to confirmation')
    binding=dict(algorithm='EXP-0046',region_digest=digest(region),scope=scope,
        video_id=history['video_id'],birth_pts=raw['birth_pts'],refs=raw['observation_refs'])
    eid=digest(binding)
    return dict(**scope,event_id=eid,video_id=history['video_id'],status='침입 의심',
        decision_time_pts=raw['decision_time_pts'],track_ids=[],
        source_ref=dict(collection='inside_birth_events',source_pointer='/inside_birth_events/'+eid,
                        segment=raw['run_id'],raw_id=None),source_event=deepcopy(raw))


def build_views(history, events, region, group):
    from .exp0045_application import annotate, grouping_effects
    old_ids={e['event_id'] for e in history['events']}
    new_ids={e['event_id'] for e in events}
    if len(new_ids)!=len(events) or old_ids & new_ids:
        raise ValueError('Distinct new event IDs required')
    views={}
    for name,rows in [('portal-only',events),('combined',history['events']+events)]:
        ids={e['event_id'] for e in rows}
        decisions=[deepcopy(d) for d in history['decisions'] if d['event_id'] in ids]
        view=annotate(group(rows,[]),decisions)
        view.update(experiment='EXP-0046',video_id=history['video_id'],
            source_window=deepcopy(history['source_window']),
            available_after_pts=history.get('available_after_pts',history['source_window'][1]),
            comparison_mode=name,portal_region_digest=digest(region),geometry_kind=KIND,
            new_birth_alone_is_confirmation=False,baseline_alerts_suppressed=0,
            history_rule_changed=False,person_detector_changed=False,
            candidate_generation_changed=True,detection_rules_changed=True,
            live_notifications_enabled=False,accuracy=None,realtime=False)
        if name=='combined':
            preserved={e['event_id']:e for e in view['events'] if e['event_id'] in old_ids}
            if preserved!={e['event_id']:e for e in history['events']}:
                raise ValueError('Original event changed')
            view['grouping_effects']=grouping_effects(history,view)
        views[name]=view
    return views


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def execute(baseline_path, paths_directory, history_directory, portal_path,
            output, scene_path=None):
    from .exp0044_application import prepared_inputs,sha,save
    from .exp0045_application import select_scene
    begin=time.perf_counter();out=Path(output);hdir=Path(history_directory)
    if (out.exists() or out.is_symlink() or any(p.is_symlink() for p in out.parents)
            or not out.resolve().is_relative_to(Path('outputs').resolve())):
        raise ValueError('Use a new non-symlink directory under outputs/')
    baseline,original,frames,old_scene,group,protected=prepared_inputs(baseline_path,paths_directory)
    scene=select_scene(baseline['video_id'],old_scene,scene_path)
    source_files=[hdir/n for n in ('history-cards.json','history-decisions.json',
                                  'scene-used.json','summary.json','request.json')]
    protected.update({str(p):sha(p) for p in source_files})
    protected[str(portal_path)]=sha(portal_path)
    if scene_path is not None:protected[str(scene_path)]=sha(scene_path)
    history=load_json(hdir/'history-cards.json')
    summary=load_json(hdir/'summary.json');request=load_json(hdir/'request.json')
    if (history.get('experiment')!='EXP-0045' or request.get('experiment')!='EXP-0045'
            or summary.get('video_id')!=baseline['video_id']
            or history.get('video_id')!=baseline['video_id']
            or load_json(hdir/'scene-used.json')!=scene
            or history['events']!=original['events']
            or history['decisions']!=load_json(hdir/'history-decisions.json')
            or summary['frames']!=len(frames)):
        raise ValueError('Frozen EXP45 history must match these source inputs and selected scene')
    if request['input_sha256']!=summary['input_sha256']:
        raise ValueError('EXP45 input binding differs')
    for path,expected in request['input_sha256'].items():
        if sha(path)!=expected:raise ValueError('EXP45 input changed: '+path)
        protected[path]=expected
    policy=EpisodePolicy()
    if request['policy']!=asdict(policy):
        raise ValueError('Keep the EXP45 temporal/association policy unchanged')
    region=load_json(portal_path)
    camera=history['events'][0]['camera_id']
    files=['portal_births.py','exp0046_application.py','gate_episode_evidence.py',
           'exp0045_application.py','exp0044_application.py','incident_notifications.py','incident_cards.py']
    code={str(Path(__file__).with_name(n)):sha(Path(__file__).with_name(n)) for n in files}
    # Constructor validates the new region; it never silently falls back to the whole inside zone.
    comparison=compare_births(frames,scene,region,camera,policy)
    events=[normalize_portal(e,history,region) for e in comparison['portal_events']]
    views=build_views(history,events,region,group)
    if protected!={p:sha(p) for p in protected} or code!={p:sha(p) for p in code}:
        raise ValueError('Protected inputs or source changed')
    out.mkdir(parents=True,exist_ok=False)
    # A is not reclassified: these bytes and its confirmation times stay exactly as measured.
    for name in ('history-cards.json','history-decisions.json','scene-used.json'):
        (out/name).write_bytes((hdir/name).read_bytes())
    (out/'baseline-cards.json').write_bytes((Path(paths_directory)/'baseline-cards.json').read_bytes())
    save(out/'portal-region.json',region)
    save(out/'request.json',dict(experiment='EXP-0046',policy=asdict(policy),input_sha256=protected,
        code_sha256=code,geometry_kind=KIND,portal_path=str(portal_path),
        history_directory=str(history_directory),scene_override=None if scene_path is None else str(scene_path)))
    for name,view in views.items():save(out/(name+'-cards.json'),view)
    save(out/'inside-birth-events.json',events)
    save(out/'legacy-birth-events.json',comparison['legacy_events'])
    save(out/'birth-audits.json',dict(legacy=comparison['legacy_audits'],portal=comparison['portal_audits']))
    report=dict(experiment='EXP-0046',video_id=history['video_id'],frames=len(frames),
        legacy_birth_candidates=len(comparison['legacy_events']),portal_birth_candidates=len(events),
        legacy_eligible_first_sites=sum(r['site']['inside_birth_site'] for r in comparison['legacy_audits']),
        portal_eligible_first_sites=sum(r['site']['inside_birth_site'] for r in comparison['portal_audits']),
        portal_first_sites_after_warmup=sum(r['eligible'] for r in comparison['portal_audits']),
        new_candidate_pts=[e['decision_time_pts'] for e in events],
        counts={k:v['counts'] for k,v in views.items()},
        grouping_effects=views['combined']['grouping_effects'],
        history_confirmations_unchanged=True,
        elapsed_seconds=time.perf_counter()-begin,input_sha256=protected,code_sha256=code,
        detector_calls=0,tracker_calls=0,flow_calls=0,vlm_calls=0,
        accuracy=None,realtime=False,manual_reviews_modified=False,
        limitations=['Projected overlap does not verify a physical side or intrusion.',
            'Long re-detection gaps and mixed boxes remain ambiguous.',
            'Combined grouping can absorb an earlier independent notification; inspect the report.',
            'This is a geometry comparison, not a calibrated accuracy estimate.'])
    save(out/'summary.json',report)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline','paths','history','portal','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--scene',type=Path)
    a=p.parse_args()
    print(json.dumps(execute(a.baseline,a.paths,a.history,a.portal,a.output,a.scene),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
