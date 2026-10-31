"""Read-only EXP-0039 CPU application to existing EXP-0035 output and original video.

Writes detection-gap audits, short LK paths and local evidence stills. It does
not re-run FCOS/ByteTrack/VLM or modify candidates, cards, scenes, or reviews.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from .gap_observation_support import (FlowPolicy, ShortImageFlow, audit_loss,
                                      catalog_frame, flow_crop, select_seed)


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()


def write(path,value):
    with Path(path).open('x',encoding='utf-8') as f:
        json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False)
        f.write('\n')


def snapshot(bgr, frame, audit, flow, target):
    import cv2
    image=bgr.copy();h,w=image.shape[:2]
    for candidate in frame:
        b=candidate['bbox']
        a=(int(b[0]*w),int(b[1]*h));z=(int(b[2]*w),int(b[3]*h))
        color=(0,220,0) if candidate['assignment']=='confirmed_track' else (220,160,0)
        cv2.rectangle(image,a,z,color,2)
        cv2.putText(image,f"cache {candidate['cache_index']} {candidate['assignment']}",
                    (a[0],max(15,a[1]-4)),cv2.FONT_HERSHEY_SIMPLEX,.4,color,1)
    for x,y in flow.records[-1]['points_original_pixels']:
        cv2.circle(image,(round(x),round(y)),3,(0,0,255),-1)
    text=f"{audit['segment']} raw{audit['raw_id']} PTS {flow.last_pts:.6f} | image points, NOT identity"
    cv2.putText(image,text,(12,26),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,255,255),2)
    if not cv2.imwrite(str(target),image):
        raise OSError('Could not write local evidence image')


def execute(baseline_path, output, policy=FlowPolicy()):
    # Original local environments supply PyAV and the project's validated decoder.
    from .exp0034_application import validated_inputs
    from .exp0035_application import validate_measured_partition
    from .run_tracklet_linking import decode_native
    import cv2

    begin=time.perf_counter();policy.validate()
    baseline_path,output=Path(baseline_path),Path(output)
    if (output.exists() or output.is_symlink() or any(p.is_symlink() for p in output.parents)
            or not output.resolve().is_relative_to(Path('outputs').resolve())):
        raise ValueError('Use a fresh non-symlink local directory under outputs/')
    baseline_bytes=baseline_path.read_bytes()
    baseline=json.loads(baseline_bytes)
    if baseline.get('experiment')!='EXP-0035' or baseline.get('video_id') not in ('E01_007','E01_030'):
        raise ValueError('Existing EXP-0035 007/030 output required')
    key=baseline['video_id'][-3:]
    spec,data,scene=validated_inputs(key,baseline['source_paths']['scene'],baseline['input_sha256']['scene'])
    if any(baseline['input_sha256'].get(k)!=v for k,v in data['hashes'].items()):
        raise ValueError('Baseline and original source bindings differ')
    validate_measured_partition(baseline,data['tracked'])
    if baseline['existing_alerts']!=data['gap_events']:
        raise ValueError('Original boundary alerts differ')
    protected=[baseline_path,Path(spec['video']),Path(spec['tracks']),Path(spec['cache'])/'run.json',
               Path(spec['cache'])/'person_cache.jsonl',Path(baseline['source_paths']['scene']),Path(spec['regions'])]
    before={str(p):sha(p) for p in protected}
    sources=[Path(__file__),Path(__file__).with_name('gap_observation_support.py')]
    source_hashes={p.name:sha(p) for p in sources}
    by_id={s['id']:s for s in baseline['segments']}
    plans=[]
    for index,event in enumerate(baseline['events']):
        if event.get('status')!='침입 의심' or event.get('reason')!='recent_gate_presence_then_loss':
            continue
        segment=by_id[event['segment']]
        audit=audit_loss(event,segment,data['cached'],data['tracked'])
        audit['source_pointer']=f'/events/{index}'
        seed=select_seed(segment,policy)
        plans.append(dict(audit=audit,segment=segment,seed=seed,
            end=audit['timeline'][-1]['frame_index'],flow=None,
            crop=flow_crop(seed['bbox'],segment['rows'][-1]['bbox'],scene['source_size']) if seed else None))
    output.mkdir(parents=True,exist_ok=False)
    (output/'evidence').mkdir()
    flow_begin=time.perf_counter()
    eligible=[p for p in plans if p['seed'] is not None]
    if eligible:
        first=min(p['seed']['frame_index'] for p in eligible)
        end=max(p['end'] for p in eligible)
        selected=data['cached'][first:end+1]
        for offset,bgr in decode_native(spec['video'],selected):
            index=first+offset
            active=[p for p in eligible if p['seed']['frame_index']<=index<=p['end']]
            if not active:
                continue
            gray=cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY)
            candidates=catalog_frame(data['cached'][index],data['tracked'][index])
            pts=data['cached'][index]['pts']
            for p in active:
                x1,y1,x2,y2=p['crop'];crop=gray[y1:y2,x1:x2]
                if p['flow'] is None:
                    p['flow']=ShortImageFlow(crop,p['seed'],scene['source_size'],(x1,y1),candidates,policy)
                else:
                    p['flow'].update(crop,pts,index)
                if index in (p['seed']['frame_index'],p['segment']['rows'][-1]['frame_index'],p['end']):
                    filename=f"{p['audit']['segment']}-{index:06d}.jpg"
                    snapshot(bgr,candidates,p['audit'],p['flow'],output/'evidence'/filename)
        for p in eligible:
            if p['flow'] is None or abs(p['flow'].last_pts-p['audit']['decision_time_pts'])>1e-6:
                raise ValueError('Incomplete native flow interval')
    outcomes=[]
    for p in plans:
        audit=p['audit'];flow=p['flow']
        if flow is None:
            support=dict(outcome='no_earlier_measured_seed',cancel_alarm=False,identity_verified=False)
        else:
            end=catalog_frame(data['cached'][p['end']],data['tracked'][p['end']])
            support=flow.summary(audit['last_observed_pts'],end)
        write(output/(audit['segment']+'-support.json'),dict(detector_audit=audit,flow_support=support,
            flow_records=[] if flow is None else flow.records,working_crop=p['crop']))
        outcomes.append(dict(segment=audit['segment'],raw_id=audit['raw_id'],
            source_pointer=audit['source_pointer'],last_observed_pts=audit['last_observed_pts'],
            decision_time_pts=audit['decision_time_pts'],detector_counts=audit['counts'],flow_support=support))
    flow_seconds=time.perf_counter()-flow_begin
    if (before!={str(p):sha(p) for p in protected} or baseline_path.read_bytes()!=baseline_bytes
            or source_hashes!={p.name:sha(p) for p in sources}):
        raise ValueError('Protected source or code changed during read-only analysis')
    report=dict(experiment='EXP-0039',video_id=baseline['video_id'],utc=datetime.now(timezone.utc).isoformat(),
        policy=policy.__dict__,opencv_version=cv2.__version__,baseline_sha256=sha(baseline_path),
        input_sha256=before,code_sha256=source_hashes,results=outcomes,
        flow_outcomes=dict(Counter(r['flow_support']['outcome'] for r in outcomes)),
        baseline_alerts=sum(e.get('status')=='침입 의심' for e in baseline['events'])+len(baseline['existing_alerts']),
        alarm_changes=0,detector_calls=0,tracker_calls=0,vlm_calls=0,new_labels=0,
        original_inputs_unchanged=True,performance_improvement=None,
        flow_and_evidence_seconds=flow_seconds,total_seconds=time.perf_counter()-begin,
        limitations=['Nearby boxes can belong to another person.',
          'Flow point survival does not prove target identity or rule out intrusion.',
          'Flow loss does not prove physical disappearance.',
          'Only original alert-time-or-earlier images used; offline execution, not real-time latency.'])
    write(output/'summary.json',report)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=execute(args.baseline,args.output)
    print(json.dumps({k:report[k] for k in ('video_id','flow_outcomes','baseline_alerts','alarm_changes','total_seconds')},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
