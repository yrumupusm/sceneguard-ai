"""Continuous native-image gate cues, compared separately with preserved EXP-0035.

New CPU optical flow IS computed. No model, tracker, VLM, training or suppression.
The combined view is additive: it cannot claim baseline false-alert reduction.
"""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import math
import time

from .gate_transition import GateTransition, TransitionPolicy


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()


def save(path, value):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False)
        f.write('\n')


def normalize_transition(raw, *, scope, video_id, source_sha256):
    """A NEW candidate, never an edited historical alert or identity assertion."""
    e=deepcopy(raw); at=e.get('decision_time_pts')
    if (type(at) not in (int,float) or not math.isfinite(at) or at<0
            or e.get('evidence_until_pts')!=at or e.get('status')!='침입 의심'
            or e.get('reason')!='gate_visual_transition'):
        raise ValueError('Causal new transition candidate required')
    if set(scope)!={'session_id','camera_id','gate_id'} or any(not isinstance(v,str) or not v for v in scope.values()):
        raise ValueError('Explicit session/camera/gate scope required')
    evidence=e['evidence']
    if not 0<=evidence['seed_pts']<=evidence['reference_pts']<at:
        raise ValueError('Only preceding image references are allowed')
    track_ids=evidence.get('seed_track_ids',[])
    if any(type(t) is not int or t<0 for t in track_ids):
        raise ValueError('Raw seed IDs must be nonnegative integers, not resolved identities')
    binding=dict(scope=scope,video_id=video_id,source_sha256=source_sha256,
                 pts=at,window=evidence['window_id'],algorithm='EXP-0042')
    eid=hashlib.sha256(json.dumps(binding,sort_keys=True,allow_nan=False).encode()).hexdigest()
    return dict(**scope,event_id=eid,video_id=video_id,decision_time_pts=at,
                status='침입 의심',track_ids=sorted(set(track_ids)),
                source_ref=dict(collection='transition_events',
                    source_pointer='/transition_events/'+eid,segment=evidence['window_id'],raw_id=None),
                source_event=e)


def comparison_bundles(baseline, new_events, group=None):
    """Independent diagnostic and additive view; never reuse the rejected 0.55 veto."""
    if group is None:
        from .incident_notifications import group_notifications
        from .incident_cards import GroupPolicy
        group=lambda rows:group_notifications(rows,policy=GroupPolicy(**baseline['policy']))
    original=deepcopy(baseline['events']); added=deepcopy(list(new_events))
    old_ids={e['event_id'] for e in original}
    if len({e['event_id'] for e in added})!=len(added) or old_ids.intersection(e['event_id'] for e in added):
        raise ValueError('New candidates must have distinct IDs')
    result={}
    for name,rows in [('baseline',original),('transition-only',added),('combined',original+added)]:
        bundle=group(rows)
        bundle.update(experiment='EXP-0042',video_id=baseline['video_id'],
            source_window=deepcopy(baseline['source_window']),
            available_after_pts=baseline.get('available_after_pts',baseline['source_window'][1]),
            comparison_mode=name,live_notifications_enabled=False,
            person_detector_changed=False,candidate_generation_changed=(name!='baseline'),
            detection_rules_changed=(name!='baseline'),
            baseline_alerts_suppressed=0,transition_only_is_diagnostic=(name=='transition-only'),
            accuracy=None,realtime=False,
            false_alarm_reduction_claim=False)
        result[name]=bundle
    preserved={e['event_id']:e for e in result['combined']['events'] if e['event_id'] in old_ids}
    if preserved!={e['event_id']:e for e in original}:
        raise ValueError('Combined view changed a baseline candidate')
    return result


def execute(baseline_path, output, policy=TransitionPolicy()):
    from .exp0034_application import validated_inputs
    from .exp0035_application import validate_measured_partition
    from .exp0036_application import make_bundle
    from .gap_observation_support import catalog_frame
    from .run_tracklet_linking import decode_native
    import cv2
    policy.validate(); begin=time.perf_counter()
    src,out=Path(baseline_path),Path(output)
    if (out.exists() or out.is_symlink() or any(p.is_symlink() for p in out.parents)
            or not out.resolve().is_relative_to(Path('outputs').resolve())):
        raise ValueError('Use a new non-symlink output directory under outputs/')
    baseline=json.loads(src.read_text(encoding='utf-8'))
    if baseline.get('experiment')!='EXP-0035' or baseline.get('video_id') not in ('E01_007','E01_030'):
        raise ValueError('Use preserved EXP-0035 007/030 source results')
    key=baseline['video_id'][-3:]
    spec,data,scene=validated_inputs(key,baseline['source_paths']['scene'],baseline['input_sha256']['scene'])
    if any(baseline['input_sha256'].get(k)!=v for k,v in data['hashes'].items()):
        raise ValueError('Baseline input binding differs')
    validate_measured_partition(baseline,data['tracked'])
    if baseline['existing_alerts']!=data['gap_events']:
        raise ValueError('Original boundary alerts differ')
    camera='C3' if key=='007' else 'C6'
    scope=dict(session_id=baseline['video_id']+'-original',camera_id=camera,gate_id=camera+'_fence')
    original=make_bundle(baseline,camera,scope['gate_id'],scope['session_id'])
    protected=[src,Path(spec['video']),Path(spec['tracks']),Path(spec['cache'])/'run.json',
               Path(spec['cache'])/'person_cache.jsonl',Path(baseline['source_paths']['scene']),Path(spec['regions'])]
    inputs={str(p):sha(p) for p in protected}
    code={str(p):sha(p) for p in [Path(__file__),Path(__file__).with_name('gate_transition.py'),
        Path(__file__).with_name('incident_notifications.py'),Path(__file__).with_name('incident_cards.py')]}
    out.mkdir(parents=True,exist_ok=False)
    save(out/'request.json',dict(experiment='EXP-0042',policy=asdict(policy),input_sha256=inputs,
        code_sha256=code,utc=datetime.now(timezone.utc).isoformat(),scope='continuous_selected_source_window',
        rejected_continuation_suppression_used=False))
    engine=GateTransition(scene,policy); events=[]; count=0; frames_with_cues=0
    try:
        with (out/'frame-evidence.jsonl').open('x',encoding='utf-8') as sink:
            # EVERY saved frame in the selected interval, not just previous loss endpoints.
            for index,bgr in decode_native(spec['video'],data['cached']):
                cache=data['cached'][index]
                catalog=catalog_frame(cache,data['tracked'][index])
                r=engine.step(cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY),cache['pts'],catalog,index)
                r.update(native_pts=cache['native_pts'],time_base=cache['time_base'],
                         actual_boxes=catalog)
                count+=1; frames_with_cues+=bool(r['signals'])
                if r['event']:
                    r['event'].update(native_pts=cache['native_pts'],time_base=cache['time_base'])
                    events.append(normalize_transition(r['event'],scope=scope,video_id=baseline['video_id'],
                                                       source_sha256=data['hashes']['video']))
                sink.write(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n')
        if count!=len(data['cached']): raise ValueError('Incomplete continuous source window')
        bundles=comparison_bundles(original,events)
        for name,bundle in bundles.items(): save(out/(name+'-cards.json'),bundle)
        save(out/'transition-events.json',events)
        if inputs!={str(p):sha(p) for p in protected} or code!={p:sha(p) for p in code}:
            raise ValueError('Input or code changed during comparison')
        report=dict(experiment='EXP-0042',video_id=baseline['video_id'],frames=count,
            frames_with_cues=frames_with_cues,new_candidates=len(events),
            new_candidate_pts=[e['decision_time_pts'] for e in events],
            counts={k:v['counts'] for k,v in bundles.items()},
            first_notification_pts={k:[c['first_notification_pts'] for c in v['alert_cards']]
                                    for k,v in bundles.items()},
            source_window=baseline['source_window'],
            first_native_pts=data['cached'][0]['native_pts'],
            last_native_pts=data['cached'][-1]['native_pts'],
            time_base=data['cached'][0]['time_base'],
            first_new_candidate_pts=min((e['decision_time_pts'] for e in events),default=None),
            baseline_alerts_suppressed=0,policy=asdict(policy),
            detector_calls=0,tracker_calls=0,vlm_calls=0,model_calls=0,
            new_cpu_image_flow=True,elapsed_seconds=time.perf_counter()-begin,
            opencv_version=cv2.__version__,accuracy=None,visual_review='pending',
            realtime=False,input_sha256=inputs,code_sha256=code,
            limitations=['Image motion is not semantic action or identity recognition.',
                'New candidates may include walking, handling objects, or background drift.',
                'Combined view retains old false alarms; no false-alarm reduction claim.',
                'Transition-only view omits old fallback: diagnostic, not a replacement.',
                'New events can change grouping; original candidate payloads, not all old card IDs, are preserved.'])
        save(out/'summary.json',report)
        return report
    except Exception as exc:
        save(out/'failure.json',dict(error=repr(exc),processed_frames=count,
            elapsed_seconds=time.perf_counter()-begin))
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); print(json.dumps(execute(a.baseline,a.output),ensure_ascii=False,indent=2))

if __name__=='__main__': main()
