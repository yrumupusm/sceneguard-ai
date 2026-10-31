"""Display saved EXP-0042 evidence only; never compute flow or new candidates.

All pixels stay local. Native source time and prefix-only event/card snapshots
are displayed beside actual cached detections and permanent image-point paths.
"""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import time

from .exp0042_application import sha, save
from .incident_notifications import notification_cards_at

MODES=('baseline','transition-only','combined')


def frame_clock(record):
    exact=Fraction(record['native_pts'])*Fraction(record['time_base'])
    if abs(float(exact)-record['pts'])>1e-9:
        raise ValueError('Saved native PTS differs from source seconds')
    return exact


def status_at(bundle, pts):
    """Only causally available candidates and detached prefix card snapshots."""
    events=[e for e in bundle['events'] if e['decision_time_pts']<=pts+1e-9]
    cards=notification_cards_at(bundle['timeline'],pts)
    notices=[t['decision_time_pts'] for t in bundle['timeline']
             if t['decision_time_pts']<=pts+1e-9 and t.get('notify')]
    return dict(candidate_rows=len(events),cards=len(cards),notification_intents=len(notices),
        first_notification_pts=min(notices,default=None),
        latest_candidate_pts=max((e['decision_time_pts'] for e in events),default=None))


class SavedPaths:
    """Keep point identities within each seed window; never infer person identity."""
    def __init__(self):
        self.paths={}; self.active=set(); self.seen=set(); self.last_pts=None

    def push(self, row):
        at=frame_clock(row)
        if self.last_pts is not None and at<=self.last_pts:
            raise ValueError('Increasing exact native PTS required')
        current=set(); live={}
        for window in row['point_paths']:
            wid=window['window_id']; ids=window['point_ids']; points=window['points_original_pixels']
            if wid in current or len(ids)!=len(set(ids)) or len(ids)!=len(points):
                raise ValueError('Unique permanent point IDs and windows required')
            if wid in self.seen and wid not in self.active:
                raise ValueError('Retired seed window reappeared')
            current.add(wid)
            previous=self.paths.get(wid,{})
            if wid in self.seen and not set(ids)<=set(previous):
                raise ValueError('Dropped permanent point reappeared')
            live[wid]={pid:previous.get(pid,[])+[p] for pid,p in zip(ids,points)}
        self.paths=live;self.active=current;self.seen.update(current);self.last_pts=at
        return self.paths


def intervals(rows, events, key):
    start,end=rows[0]['pts'],rows[-1]['pts']
    targets=[dict(name='continuous',start=start,end=end,event_ids=[])]
    core=[('core-64-74',64.,74.),('normal-56-63',56.,63.)] if key=='007' else [('core-90-94',90.,94.)]
    targets.extend(dict(name=name,start=max(a,start),end=min(b,end),event_ids=[]) for name,a,b in core)
    merged=[]
    for event in sorted(events,key=lambda e:e['decision_time_pts']):
        at=event['decision_time_pts']; a=max(start,at-2.);b=min(end,at+1.)
        if merged and a<=merged[-1]['end']:
            merged[-1]['end']=max(merged[-1]['end'],b);merged[-1]['event_ids'].append(event['event_id'])
        else:merged.append(dict(start=a,end=b,event_ids=[event['event_id']]))
    targets.extend(dict(name=f'new-candidates-{n:02d}',**v) for n,v in enumerate(merged,1))
    return targets


def execute(directory):
    import av
    import cv2
    import numpy as np
    from .run_tracklet_linking import decode_native
    begin=time.perf_counter(); directory=Path(directory)
    request=json.loads((directory/'request.json').read_text())
    summary=json.loads((directory/'summary.json').read_text())
    evidence=directory/'frame-evidence.jsonl'; evidence_sha=sha(evidence)
    rows=[json.loads(line) for line in evidence.read_text().splitlines()]
    if len(rows)!=summary['frames'] or any(r['frame_index']!=i for i,r in enumerate(rows)):
        raise ValueError('Complete saved continuous evidence required')
    clocks=[frame_clock(r) for r in rows]
    if any(b<=a for a,b in zip(clocks,clocks[1:])):raise ValueError('Nonincreasing evidence PTS')
    video=next(p for p in request['input_sha256'] if p.endswith('.mp4'))
    if sha(video)!=request['input_sha256'][video]:raise ValueError('Original video changed')
    scene_path=next(p for p in request['input_sha256'] if 'scene' in p and p.endswith('.json'))
    scene=json.loads(Path(scene_path).read_text());w,h=scene['source_size']
    bundles={mode:json.loads((directory/(mode+'-cards.json')).read_text()) for mode in MODES}
    events=json.loads((directory/'transition-events.json').read_text())
    target=directory/'evidence';target.mkdir(exist_ok=False)
    width=640;height=360;header=230
    poly=np.asarray(scene['approach_polygon'])*[w,h]
    lo=np.maximum([0,0],np.floor(poly.min(axis=0)-30)).astype(int)
    hi=np.minimum([w,h],np.ceil(poly.max(axis=0)+30)).astype(int)
    crop=[int(lo[0]),int(lo[1]),int(hi[0]),int(hi[1])]
    targets=intervals(rows,events,summary['video_id'][-3:]);handles=[]
    rate=1/(clocks[1]-clocks[0]);timebase=Fraction(rows[0]['time_base'])
    for spec in targets:
        chosen=[r for r in rows if spec['start']-1e-9<=r['pts']<=spec['end']+1e-9]
        spec.update(path=str(target/(spec['name']+'.mp4')),mapping=[],first_native_pts=chosen[0]['native_pts'])
        output=av.open(spec['path'],'w');stream=output.add_stream('libx264',rate=rate)
        stream.width=width*3;stream.height=height+header;stream.pix_fmt='yuv420p'
        stream.time_base=timebase;stream.codec_context.time_base=timebase
        stream.options={'crf':'20','preset':'fast'}
        handles.append((spec,output,stream))
    paths=SavedPaths();colors=[(0,200,255),(255,100,50),(60,255,80),(255,80,210),(240,220,70)]
    try:
        for index,bgr in decode_native(video,rows):
            row=rows[index];paths.push(row); measured=bgr.copy();featured=bgr.copy()
            for box in row['actual_boxes']:
                if box.get('observed') is False:continue
                x1,y1,x2,y2=np.rint(np.asarray(box['bbox'])*[w,h,w,h]).astype(int)
                color=(60,255,80) if box['track_ids'] else (0,180,255)
                cv2.rectangle(measured,(x1,y1),(x2,y2),color,2)
                cv2.putText(measured,f"cache{box['cache_index']} raw{box['track_ids']} {box['score']:.2f}",
                    (x1,max(15,y1-4)),0,.45,color,1)
            line=np.rint(np.asarray(scene['line'])*[w,h]).astype(int)
            for image in (measured,featured):cv2.line(image,tuple(line[0]),tuple(line[1]),(250,100,255),2)
            for window in row['point_paths']:
                wid=window['window_id'];color=colors[int(wid[1:])%len(colors)]
                for pid,vertices in paths.paths[wid].items():
                    pts=np.rint(vertices).astype(np.int32)
                    if len(pts)>1:cv2.polylines(featured,[pts],False,color,1)
                    cv2.circle(featured,tuple(pts[-1]),2,color,-1)
                    cv2.putText(featured,f'{wid[1:]}:{pid}',tuple(pts[-1]),0,.28,color,1)
            x1,y1,x2,y2=crop
            canvas=np.zeros((height+header,width*3,3),dtype=np.uint8)
            for n,image in enumerate((bgr,measured,featured[y1:y2,x1:x2])):
                scale=min(width/image.shape[1],height/image.shape[0])
                small=cv2.resize(image,(round(image.shape[1]*scale),round(image.shape[0]*scale)))
                canvas[header:header+small.shape[0],n*width:n*width+small.shape[1]]=small
            statuses={mode:status_at(bundle,row['pts']) for mode,bundle in bundles.items()}
            labels=[f"EXP42 | source PTS {row['native_pts']} * {row['time_base']} = {row['pts']:.6f}s | source frame {index}",
                f"CURRENT image cue score {row['score']:.4f} (heuristic, NOT probability) | signals {len(row['signals'])} | active windows {row['windows']} | camera support {row['camera_support']}"]
            for mode,status in statuses.items():
                labels.append(f"{mode}: candidates {status['candidate_rows']} | cards {status['cards']} | notices {status['notification_intents']} | first notice {status['first_notification_pts']} | latest candidate {status['latest_candidate_pts']}")
            labels.extend(['ORIGINAL                                             STORED ACTUAL BOXES: raw IDs only                       SAVED POINT PATHS: window:permanent-point IDs',
                'Paths are pixel correspondences; raw seed IDs are NOT resolved person identities. No predicted boxes. No automatic intrusion confirmation.',
                'Transition-only: diagnostic without baseline fallback. Combined: preserves old false alarms. Post-candidate pixels are display-only context.'])
            for n,label in enumerate(labels):cv2.putText(canvas,label,(10,23+27*n),0,.53,(235,235,235),1)
            for spec,output,stream in handles:
                if not spec['start']-1e-9<=row['pts']<=spec['end']+1e-9:continue
                frame=av.VideoFrame.from_ndarray(canvas,format='bgr24')
                frame.pts=row['native_pts']-spec['first_native_pts'];frame.time_base=timebase
                for packet in stream.encode(frame):output.mux(packet)
                spec['mapping'].append(dict(frame_index=index,native_pts=row['native_pts'],time_base=row['time_base'],
                    source_pts=row['pts'],presentation_pts=float(frame.pts*timebase),current_score=row['score'],statuses=statuses))
    finally:
        for spec,output,stream in handles:
            for packet in stream.encode():output.mux(packet)
            output.close()
    for spec,_,_ in handles:
        with av.open(spec['path']) as encoded:actual=[float(f.pts*f.time_base) for f in encoded.decode(video=0)]
        expected=[r['presentation_pts'] for r in spec['mapping']]
        if len(actual)!=len(expected) or any(abs(a-b)>1e-6 for a,b in zip(actual,expected)):
            raise ValueError('Encoded frame count/native PTS mapping differs')
        spec.update(frames=len(expected),sha256=sha(spec['path']))
    if sha(evidence)!=evidence_sha:raise ValueError('Saved evidence changed during render')
    covered={eid for spec in targets for eid in spec['event_ids']}
    if covered!={e['event_id'] for e in events}:raise ValueError('Candidate clip coverage incomplete')
    report=dict(experiment='EXP-0042',video_id=summary['video_id'],videos=targets,
        source_frame_count=len(rows),frame_evidence_sha256=evidence_sha,renderer_sha256=sha(__file__),
        renderer_elapsed_seconds=time.perf_counter()-begin,flow_recomputed=False,
        all_new_candidates_covered=True,identity_verified=False,feature_crop_original_pixels=crop,
        scores='saved current-frame only',card_status='prefix-only event clock',pixels_local_only=True)
    save(target/'manifest.json',report)
    return {k:v for k,v in report.items() if k!='videos'}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--directory',type=Path,required=True)
    print(json.dumps(execute(parser.parse_args().directory),indent=2))

if __name__=='__main__':main()
