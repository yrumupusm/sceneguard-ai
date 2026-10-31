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
                                     trace, assess, notification_partition)


def execute(baseline_path, output, policy=PracticalPolicy()):
    from .exp0039_application import sha, write
    from .exp0034_application import validated_inputs
    from .exp0035_application import validate_measured_partition
    from .gap_observation_support import catalog_frame, audit_loss
    from .run_tracklet_linking import decode_native
    from .exp0036_application import make_bundle
    from .incident_cards import group_events
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
    spec,data,scene=validated_inputs(key,baseline['source_paths']['scene'],baseline['input_sha256']['scene'])
    if any(baseline['input_sha256'].get(k)!=v for k,v in data['hashes'].items()):
        raise ValueError('Baseline differs from validated inputs')
    validate_measured_partition(baseline,data['tracked'])
    if baseline['existing_alerts']!=data['gap_events']:
        raise ValueError('Preserved boundary events differ')
    protected=[baseline_path,Path(spec['video']),Path(spec['tracks']),Path(spec['cache'])/'person_cache.jsonl',
        Path(spec['cache'])/'run.json',Path(baseline['source_paths']['scene']),Path(spec['regions']),
        Path('configs/mvp0001_cameras.json')]
    before={str(p):sha(p) for p in protected}
    code={str(p):sha(p) for p in (Path(__file__),Path(__file__).with_name('practical_continuation.py'))}
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
                result=assess(path,catalogs,scene['source_size'],scene['line'],
                              seg['rows'][-1]['pts'],overlap,policy)
                result.update(seed_pts=seed['pts'],seed_frame_index=seed['frame_index'],seed_rank=rank,
                              path_file=f"{seg['id']}-seed{n+1}.json")
                write(output/result['path_file'],dict(records=path['records'],summary=result))
                audit['alternatives'].append(result)
            if audit['alternatives']:
                best=max(audit['alternatives'],key=lambda r:r['score'])
                audit.update({k:v for k,v in best.items() if k!='evidence_until_pts'})
                # Different candidate boxes with substantially overlapping support
                # are duplicates; different spatial endpoints across seeds compete.
                winners=[r for r in audit['alternatives'] if r['recommendation']=='review_only']
                def overlap_box(a,b):
                    x=max(0,min(a[2],b[2])-max(a[0],b[0]));y=max(0,min(a[3],b[3])-max(a[1],b[1]))
                    return x*y/max(1e-12,min((a[2]-a[0])*(a[3]-a[1]),(b[2]-b[0])*(b[3]-b[1])))
                if any(overlap_box(a['endpoint_bbox'],b['endpoint_bbox'])<.3
                       for a in winners for b in winners):
                    audit.update(recommendation='keep',reason='different_seed_paths_disagree')
            del grays
        audits.append(audit)
        write(output/(seg['id']+'-audit.json'),audit)
    baseline_bundle=make_bundle(baseline,camera,camera+'_fence',baseline['video_id']+'-original')
    active,review=notification_partition(baseline_bundle['events'],audits)
    proposal=deepcopy(baseline_bundle); proposal.update(group_events(active))
    proposal.update(experiment='EXP-0040',baseline_experiment='EXP-0035',
        full_original_alerts=deepcopy(baseline_bundle['events']),review_only_events=review,
        notification_policy='experimental_soft_image_continuation',
        false_alarm_status='requires_actual_visual_review',accuracy=None,
        automatic_negative_decisions=0,detector_calls=0,tracker_calls=0,vlm_calls=0)
    assert len(active)+len(review)==len(baseline_bundle['events'])
    write(output/'baseline-cards.json',baseline_bundle)
    write(output/'proposed-cards.json',proposal)
    write(output/'audits.json',audits)
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
