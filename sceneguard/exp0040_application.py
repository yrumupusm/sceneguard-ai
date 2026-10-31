"""EXP-0040 CPU-only proposal: actual notification filtering plus unchanged baseline.

Run with preserved EXP-0035 inputs; no detector/tracker/VLM or training invocation.
Use a fresh outputs directory. Actual CCTV execution is separate from unit tests.
"""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import argparse
import json
import time

from .practical_continuation import (PracticalPolicy, seed_pool, choose_seeds,
                                     trace, assess, notification_partition, seed_decision)


def proposal_bundle(baseline, audits, threshold):
    """Partition the original normalized events without changing their identities."""
    from .incident_cards import group_events, GroupPolicy
    decisions=deepcopy(audits)
    for row in decisions:
        row.update(seed_decision(row['alternatives'],threshold))
    active,review=notification_partition(baseline['events'],decisions)
    proposal=deepcopy(baseline)
    proposal.update(group_events(active,GroupPolicy(**baseline['policy'])))
    proposal.update(experiment='EXP-0040',baseline_experiment='EXP-0035',
        full_original_alerts=deepcopy(baseline['events']),review_only_events=review,
        notification_policy='experimental_soft_image_continuation',score_threshold=threshold,
        false_alarm_status='requires_actual_visual_review',accuracy=None,
        automatic_negative_decisions=0,detector_calls=0,tracker_calls=0,vlm_calls=0)
    original={e['event_id']:e for e in baseline['events']}
    partition={e['event_id']:e for e in active+review}
    if len(partition)!=len(active)+len(review) or partition!=original:
        raise ValueError('Proposal must exactly partition original normalized alerts')
    return proposal


def timeline_comparison(baseline, proposal):
    """Match by original event membership and source time, never by new card ID."""
    rows=[]
    for card in baseline['cards']:
        ids=set(card['event_ids'])
        related=[c for c in proposal['cards'] if ids.intersection(c['event_ids'])]
        retained=[e for e in proposal['events'] if e['event_id'] in ids]
        rows.append(dict(original_incident_id=card['incident_id'],
            original_event_ids=card['event_ids'],source_interval=[card['first_alert_pts'],card['last_alert_pts']],
            original_first_notification_pts=card['first_notification_pts'],
            retained_event_ids=[e['event_id'] for e in retained],
            retained_first_event_pts=min((e['decision_time_pts'] for e in retained),default=None),
            proposed_cards=[dict(incident_id=c['incident_id'],first_notification_pts=c['first_notification_pts'],
                                 event_ids=c['event_ids']) for c in related],
            removed_event_ids=[e for e in card['event_ids'] if e not in {r['event_id'] for r in retained}]))
    return rows


def execute(baseline_path, output, policy=PracticalPolicy()):
    from .exp0039_application import sha, write
    from .exp0034_application import validated_inputs
    from .exp0035_application import validate_measured_partition
    from .gap_observation_support import catalog_frame, audit_loss
    from .run_tracklet_linking import decode_native
    from .exp0036_application import make_bundle
    import cv2

    policy.validate(); begin=time.perf_counter()
    baseline_path,output=Path(baseline_path),Path(output)
    if (output.exists() or output.is_symlink() or any(p.is_symlink() for p in output.parents)
            or not output.resolve().is_relative_to(Path('outputs').resolve())):
        raise ValueError('Use a fresh local non-symlink outputs directory')
    baseline=json.loads(baseline_path.read_text(encoding='utf-8'))
    if baseline.get('experiment')!='EXP-0035' or baseline.get('video_id') not in ('E01_007','E01_030'):
        raise ValueError('Preserved EXP-0035 007/030 baseline required')
    key=baseline['video_id'][-3:]; camera='C3' if key=='007' else 'C6'
    cards_path=Path('outputs/exp0036')/(key+'-cards-v1.json')
    baseline_bundle=json.loads(cards_path.read_text(encoding='utf-8'))
    from .incident_cards import GroupPolicy
    regenerated=make_bundle(baseline,camera,camera+'_fence',baseline['video_id']+'-original',
                            GroupPolicy(**baseline_bundle['policy']))
    if any(regenerated[k]!=baseline_bundle[k] for k in ('events','cards','counts','timeline')):
        raise ValueError('Canonical original card bundle differs from preserved EXP-0035 source')
    spec,data,scene=validated_inputs(key,baseline['source_paths']['scene'],baseline['input_sha256']['scene'])
    if any(baseline['input_sha256'].get(k)!=v for k,v in data['hashes'].items()):
        raise ValueError('Baseline differs from validated inputs')
    validate_measured_partition(baseline,data['tracked'])
    if baseline['existing_alerts']!=data['gap_events']:
        raise ValueError('Preserved boundary events differ')
    protected=[baseline_path,cards_path,Path(spec['video']),Path(spec['tracks']),Path(spec['cache'])/'person_cache.jsonl',
        Path(spec['cache'])/'run.json',Path(baseline['source_paths']['scene']),Path(spec['regions']),
        Path('configs/mvp0001_cameras.json')]
    before={str(p):sha(p) for p in protected}
    code={str(p):sha(p) for p in [Path(__file__),Path(__file__).with_name('practical_continuation.py'),
        Path(__file__).with_name('exp0040_evidence.py'),Path(__file__).with_name('incident_cards.py'),
        Path(__file__).with_name('exp0036_application.py'),Path(__file__).with_name('run_tracklet_linking.py')]}
    output.mkdir(parents=True,exist_ok=False)
    catalogs={i:catalog_frame(c,t) for i,(c,t) in enumerate(zip(data['cached'],data['tracked']))}
    stamps={i:f['pts'] for i,f in enumerate(data['cached'])}
    by_id={s['id']:s for s in baseline['segments']}
    audits=[]
    write(output/'request.json',dict(experiment='EXP-0040',policy=asdict(policy),input_sha256=before,code_sha256=code))
    for j,event in enumerate(baseline['events']):
        if event.get('status')!='침입 의심' or event.get('reason')!='recent_gate_presence_then_loss':
            continue
        seg=by_id[event['segment']]
        gap=audit_loss(event,seg,data['cached'],data['tracked'])
        pool=seed_pool(seg['rows'],policy); end=gap['timeline'][-1]['frame_index']
        audit=dict(source_pointer=f'/events/{j}',segment=seg['id'],raw_id=seg['raw_id'],
            original_event_id=next(e['event_id'] for e in baseline_bundle['events']
                                   if e['source_ref']['source_pointer']==f'/events/{j}'),
            original_source_ref=next(e['source_ref'] for e in baseline_bundle['events']
                                    if e['source_ref']['source_pointer']==f'/events/{j}'),
            original_status=event['status'],last_observed_pts=seg['rows'][-1]['pts'],
            components=None,
            decision_time_pts=event['decision_time_pts'], evidence_until_pts=event['decision_time_pts'],
            score=0.,recommendation='keep',reason='no_earlier_observed_seed',alternatives=[])
        if pool:
            first=pool[0]['frame_index']
            grays={first+offset:cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY)
                   for offset,bgr in decode_native(spec['video'],data['cached'][first:end+1])}
            if set(grays)!=set(range(first,end+1)):
                raise ValueError('Incomplete original frame interval')
            choices=choose_seeds(seg['rows'],grays,catalogs,scene['source_size'],policy)
            for n,(rank,seed,points,overlap) in enumerate(choices):
                path=trace(grays,stamps,seed,points,seg['rows'],scene['source_size'],policy)
                for record in path['records']:
                    native=data['cached'][record['frame_index']]
                    record.update(native_pts=native['native_pts'],time_base=native['time_base'])
                result=assess(path,catalogs,scene['source_size'],scene['line'],
                              seg['rows'][-1]['pts'],overlap,policy)
                result.update(seed_pts=seed['pts'],seed_frame_index=seed['frame_index'],seed_rank=rank,
                              path_file=f"{seg['id']}-seed{n+1}.json")
                write(output/result['path_file'],dict(records=path['records'],summary=result))
                audit['alternatives'].append(result)
            if audit['alternatives']:
                best=max(audit['alternatives'],key=lambda r:r['score'])
                audit.update({k:v for k,v in best.items() if k!='evidence_until_pts'})
                audit.update(seed_decision(audit['alternatives'],policy.score_threshold))
            del grays
        audits.append(audit)
    proposal=proposal_bundle(baseline_bundle,audits,policy.score_threshold)
    review=proposal['review_only_events']
    removed_ids={e['event_id'] for e in review}
    for audit in audits:
        audit['notification_action']='review_only' if audit['original_event_id'] in removed_ids else 'keep'
        audit['partition_reason']=audit['reason'] if audit['notification_action']=='review_only' else (
            'independent_boundary_evidence_preserved' if audit['recommendation']=='review_only' else audit['reason'])
    write(output/'baseline-cards.json',baseline_bundle)
    write(output/'proposed-cards.json',proposal)
    write(output/'audits.json',audits)
    for audit in audits:
        write(output/(audit['segment']+'-audit.json'),audit)
    write(output/'review-only.json',dict(events=review,removed_cases=[a for a in audits
        if a['notification_action']=='review_only'],identity_verified=False))
    write(output/'timeline-comparison.json',timeline_comparison(baseline_bundle,proposal))
    sensitivity=[]
    for threshold in (.55,.65,.70,.75,.85):
        diagnostic=proposal_bundle(baseline_bundle,audits,threshold)
        sensitivity.append(dict(threshold=threshold,counts=diagnostic['counts'],
            removed_event_ids=[e['event_id'] for e in diagnostic['review_only_events']],
            removed_source_refs=[e['source_ref'] for e in diagnostic['review_only_events']],
            timeline=timeline_comparison(baseline_bundle,diagnostic)))
    write(output/'sensitivity.json',dict(diagnostic_only=True,flow_recomputed=False,
        adoption_tuning=False,default_threshold=policy.score_threshold,rows=sensitivity))
    if before!={str(p):sha(p) for p in protected} or code!={p:sha(p) for p in code}:
        raise ValueError('Read-only inputs or code changed during comparison')
    report=dict(experiment='EXP-0040',video_id=baseline['video_id'],policy=asdict(policy),
        baseline_counts=baseline_bundle['counts'],proposed_counts=proposal['counts'],
        review_only_count=len(review),cases=len(audits),outcomes=dict(Counter(r['reason'] for r in audits)),
        notification_changes=len(review),accuracy=None,visual_validation='pending',
        elapsed_seconds=time.perf_counter()-begin,opencv_version=cv2.__version__,
        protected_inputs_unchanged=True,input_sha256=before,code_sha256=code,
        inference_calls=0,realtime=False)
    write(output/'summary.json',report)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(execute(a.baseline,a.output),ensure_ascii=False,indent=2))


if __name__=='__main__': main()
