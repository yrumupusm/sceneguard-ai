"""Display-only adapter for saved EXP-0040 paths, actual boxes and native PTS.

No optical flow, models, identity labels or event decisions are computed here.
Pixels after an alert (including the 64--74s context) are display-only evidence.
"""
import argparse
from fractions import Fraction
import json
from pathlib import Path

from .exp0039_application import sha, write
from .gap_observation_support import catalog_frame


def extend_paths(paths, record, initial=False):
    ids,points=record['ids'],record['points']
    if len(ids)!=len(points) or len(ids)!=len(set(ids)):
        raise ValueError('Unique permanent point IDs required')
    if not initial and not set(ids)<=set(paths):
        raise ValueError('Dropped point reappeared; no reseeding allowed')
    return {i:paths.get(i,[])+[p] for i,p in zip(ids,points)}


def saved_paths(directory, audits, cached):
    """Validate all saved seed paths against exact source timing before rendering."""
    seeds=[]
    for audit in audits:
        for n,alt in enumerate(audit['alternatives']):
            file=Path(directory)/alt['path_file']
            if file.parent!=Path(directory) or file.name!=alt['path_file']:
                raise ValueError('Local path filename required')
            saved=json.loads(file.read_text())
            records=saved['records'];paths={};previous=None
            for record in records:
                i=record['frame_index'];native=cached[i]
                if (previous is not None and i!=previous+1) or any(
                    record[k]!=native[k] for k in ('pts','native_pts','time_base')):
                    raise ValueError('Saved path differs from native frame timeline')
                if record['pts']>audit['decision_time_pts']+1e-9:
                    raise ValueError('Future pixels in decision path')
                paths=extend_paths(paths,record,previous is None);previous=i
            if records and abs(records[-1]['pts']-audit['decision_time_pts'])>1e-6:
                raise ValueError('Path must end at original decision PTS')
            seeds.append(dict(segment=audit['segment'],seed=n+1,records={r['frame_index']:r for r in records},
                first=records[0]['frame_index'],last=records[-1]['frame_index'],paths={},file=str(file)))
    return seeds


def render(source,cached,tracked,audits,seeds,baseline,proposal,target,first,last,width=640):
    import av
    import cv2
    import numpy as np
    from .run_tracklet_linking import decode_native
    from .exp0039_evidence import alarm_label
    target=Path(target)
    if target.exists():raise ValueError('Fresh evidence target required')
    selected=cached[first:last+1];height=360;header=148;mapping=[]
    size=selected[0]['source_size'];w,h=size
    for seed in seeds:
        seed['paths']={}
        for i,record in seed['records'].items():
            if i<first:
                seed['paths']=extend_paths(seed['paths'],record,i==seed['first'])
    boxes=[a['endpoint_bbox'] for a in audits if a.get('endpoint_bbox')]
    for seed in seeds:
        points=np.asarray(seed['records'][seed['first']]['points']).reshape(-1,2)
        if len(points):boxes.append([points[:,0].min()/w,points[:,1].min()/h,
                                     points[:,0].max()/w,points[:,1].max()/h])
    crop=[0,0,w,h] if not boxes else [max(0,int(min(b[0] for b in boxes)*w)-70),
        max(0,int(min(b[1] for b in boxes)*h)-70),min(w,int(max(b[2] for b in boxes)*w)+70),
        min(h,int(max(b[3] for b in boxes)*h)+70)]
    colors=[(0,70,255),(255,220,0),(30,230,80),(230,50,200),(255,150,40),(150,220,255)]
    with av.open(str(target),'w') as output:
        stream=output.add_stream('libx264',rate=30)
        stream.width=3*width;stream.height=height+header;stream.pix_fmt='yuv420p'
        stream.time_base=Fraction(selected[0]['time_base']);stream.codec_context.time_base=stream.time_base
        stream.options={'crf':'20','preset':'fast'}
        for offset,bgr in decode_native(source,selected):
            i=first+offset;row=cached[i];measured=bgr.copy();featured=bgr.copy()
            for c in catalog_frame(row,tracked[i]):
                a,b,x,y=np.rint(np.asarray(c['bbox'])*[w,h,w,h]).astype(int)
                color=(0,230,0) if c['assignment']=='confirmed_track' else (0,180,255)
                cv2.rectangle(measured,(a,b),(x,y),color,2)
                cv2.putText(measured,f"c{c['cache_index']} ID{c['track_ids']}",(a,max(15,b-4)),0,.45,color,1)
            # Prediction state is deliberately absent: these panels display actual saved measurements.
            for j,seed in enumerate(seeds):
                record=seed['records'].get(i)
                if record is None:continue
                seed['paths']=extend_paths(seed['paths'],record,i==seed['first'])
                color=colors[j%len(colors)]
                for identity,vertices in seed['paths'].items():
                    pts=np.rint(vertices).astype(np.int32)
                    if len(pts)>1:cv2.polylines(featured,[pts],False,color,1)
                    cv2.circle(featured,tuple(pts[-1]),3,color,-1)
                    cv2.putText(featured,f"S{seed['seed']}:{identity}",tuple(pts[-1]),0,.32,color,1)
            x1,y1,x2,y2=crop
            panels=(bgr,measured,featured[y1:y2,x1:x2])
            canvas=np.zeros((height+header,width*3,3),dtype=np.uint8)
            for panel,img in enumerate(panels):
                scale=min(width/img.shape[1],height/img.shape[0])
                small=cv2.resize(img,(round(img.shape[1]*scale),round(img.shape[0]*scale)))
                canvas[header:header+small.shape[0],panel*width:panel*width+small.shape[1]]=small
            old=[e for e in baseline['events'] if e['decision_time_pts']<=row['pts']+1e-9]
            new=[e for e in proposal['events'] if e['decision_time_pts']<=row['pts']+1e-9]
            line='; '.join(f"{a['segment']} raw{a['raw_id']} {a['score']:.3f} "
                f"{alarm_label(row['pts'],a['decision_time_pts'])} -> "
                f"{a['notification_action'] if row['pts']>=a['decision_time_pts']-1e-9 else 'PENDING'}"
                for a in audits)
            labels=[f"EXP40 | native {row['native_pts']} * {row['time_base']} = {row['pts']:.6f}s | frame {i}",
                line[:205] if len(audits)<=2 else f"Context: {len(audits)} saved loss cases; each seed path ends at its ORIGINAL decision time",
                f"Original/proposal emitted rows so far: {len(old)}/{len(new)} | context after decision is DISPLAY ONLY",
                "ORIGINAL                           STORED ACTUAL BOXES                        SAVED SEED PATHS: permanent point IDs, NOT person boxes",
                "Heuristic image correspondence; identity/box quality NOT visually adjudicated | original/proposal are separate local views"]
            for n,label in enumerate(labels):cv2.putText(canvas,label,(10,23+27*n),0,.51,(235,235,235),1)
            frame=av.VideoFrame.from_ndarray(canvas,format='bgr24')
            frame.pts=row['native_pts']-selected[0]['native_pts'];frame.time_base=stream.time_base
            for packet in stream.encode(frame):output.mux(packet)
            mapping.append(dict(frame_index=i,native_pts=row['native_pts'],time_base=row['time_base'],
                source_pts=row['pts'],presentation_pts=float(frame.pts*frame.time_base)))
        for packet in stream.encode():output.mux(packet)
    with av.open(str(target)) as encoded:
        actual=[float(f.pts*f.time_base) for f in encoded.decode(video=0)]
    if len(actual)!=len(mapping) or any(abs(a-r['presentation_pts'])>1e-6 for a,r in zip(actual,mapping)):
        raise ValueError('Encoded native PTS mapping mismatch')
    return dict(path=str(target),sha256=sha(target),frames=len(mapping),pts_mapping=mapping,
        source_first_pts=selected[0]['pts'],source_last_pts=selected[-1]['pts'],
        flow_recomputed=False,identity_verified=False,crop_original_pixels=crop)


def execute(directory):
    from .exp0034_application import validated_inputs
    from .exp0039_evidence import render_original
    directory=Path(directory);summary=json.loads((directory/'summary.json').read_text())
    for file,digest in summary['input_sha256'].items():
        if sha(file)!=digest:raise ValueError('Rendering input differs from execution freeze')
    key=summary['video_id'][-3:]
    baseline_path=Path('outputs/exp0035')/(key+'-v1.json');raw=json.loads(baseline_path.read_text())
    spec,data,_=validated_inputs(key,raw['source_paths']['scene'],raw['input_sha256']['scene'])
    audits=json.loads((directory/'audits.json').read_text())
    baseline=json.loads((directory/'baseline-cards.json').read_text())
    proposal=json.loads((directory/'proposed-cards.json').read_text())
    media=directory/'evidence';media.mkdir(exist_ok=False);receipts=[];originals=[]
    all_seeds=saved_paths(directory,audits,data['cached'])
    for audit in audits:
        seeds=[s for s in all_seeds if s['segment']==audit['segment']]
        if not seeds:continue
        first=min(s['first'] for s in seeds);last=max(s['last'] for s in seeds)
        # Half a second of later source pixels is display-only and never enters saved paths/scores.
        last=min(len(data['cached'])-1,last+15)
        receipt=render(spec['video'],data['cached'],data['tracked'],[audit],seeds,baseline,proposal,
            media/(audit['segment']+'.mp4'),first,last)
        receipt.update(segment=audit['segment'],source_ref=audit['original_source_ref'],
            event_id=audit['original_event_id'],notification_action=audit['notification_action'],
            decision_time_pts=audit['decision_time_pts'])
        receipts.append(receipt)
        if audit['notification_action']=='review_only':
            plain=render_original(spec['video'],data['cached'],first,last,media/(audit['segment']+'-original.mp4'))
            plain.update(segment=audit['segment'],event_id=audit['original_event_id']);originals.append(plain)
    if key=='007':
        indexes=[i for i,f in enumerate(data['cached']) if 64-1e-9<=f['pts']<=74+1e-9]
        receipts.append(dict(render(spec['video'],data['cached'],data['tracked'],audits,all_seeds,
            baseline,proposal,media/'context-64-74.mp4',indexes[0],indexes[-1]),context=True))
        originals.append(render_original(spec['video'],data['cached'],indexes[0],indexes[-1],media/'context-64-74-original.mp4'))
    receipts.append(dict(render(spec['video'],data['cached'],data['tracked'],audits,all_seeds,
        baseline,proposal,media/'full-source-window.mp4',0,len(data['cached'])-1),
        full_source_window=True))
    for file,digest in summary['input_sha256'].items():
        if sha(file)!=digest:raise ValueError('Protected rendering input changed')
    receipt=dict(experiment='EXP-0040',video_id=summary['video_id'],videos=receipts,original_videos=originals,
        review_only_path=str(directory/'review-only.json'),baseline_path=str(directory/'baseline-cards.json'),
        proposal_path=str(directory/'proposed-cards.json'),flow_recomputed=False,
        render_code_sha256=sha(__file__),summary_sha256=sha(directory/'summary.json'),
        visual_review='not_performed; no new visual identity or box quality truth')
    write(media/'render-receipt.json',receipt)
    return dict(videos=len(receipts),original_videos=len(originals),path=str(media/'render-receipt.json'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,required=True)
    print(json.dumps(execute(parser.parse_args().directory),indent=2))
