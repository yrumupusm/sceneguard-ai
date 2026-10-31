"""Four local original/EXP42/EXP43 videos from frozen saved evidence only.

Display and native-clock verification only; no scoring, flow, labels or models.
Original and two independent candidate-only timelines are never merged.
"""
import argparse
from collections import defaultdict,deque
from fractions import Fraction
import json
from pathlib import Path
import time

import numpy as np
from .exp0042_evidence import frame_clock,status_at
from .exp0043_media import short_paths,color
from .transition_diagnostics import sha,write_json


def validate_clocks(before,after):
    if len(before)!=len(after) or not before: raise ValueError('Complete paired frames required')
    last=None
    for old,new in zip(before,after):
        at=frame_clock(old)
        if (at!=frame_clock(new) or any(old[k]!=new[k] for k in ('native_pts','time_base','frame_index'))
                or last is not None and at<=last):
            raise ValueError('Exact same increasing native source frames required')
        last=at


def frame_metadata(old,new,bundles,first_source_pts):
    if frame_clock(old)!=frame_clock(new): raise ValueError('Source clocks differ')
    best=lambda r:max(r['signals'],key=lambda s:s['score'],default=None)
    oldbest,newbest=best(old),best(new)
    return dict(source_pts=old['pts'],source_native_pts=old['native_pts'],time_base=old['time_base'],
        frame_index=old['frame_index'],presentation_pts=float(frame_clock(old)-Fraction(str(first_source_pts))),
        baseline_score=old['score'],candidate_score=new['score'],
        old_selected_window=oldbest['window_id'] if oldbest else None,
        new_selected_window=newbest['window_id'] if newbest else None,
        old_recent_reference_pts=oldbest['reference_pts'] if oldbest else None,
        new_geometry_reference_pts=newbest['geometry_reference_pts'] if newbest else None,
        new_recent_reference_pts=newbest['recent_reference_pts'] if newbest else None,
        statuses={mode:status_at(bundle,old['pts']) for mode,bundle in bundles.items()})


def clip_specs(key,rows):
    a,b=(64,74) if key=='007' else (90,94)
    return [dict(name=f'{key}-full-comparison',range=[rows[0]['pts'],rows[-1]['pts']]),
            dict(name=f'{key}-core-comparison',range=[a,b])]


def execute(comparison,output):
    import av
    import cv2
    from .run_tracklet_linking import decode_native
    comparison=Path(comparison); output=Path(output); begin=time.perf_counter()
    if (output.exists() or output.is_symlink() or any(p.is_symlink() for p in output.parents)
            or not output.resolve().is_relative_to(Path('outputs/exp0043').resolve())
            or 'comparison' not in output.name):
        raise ValueError('New local comparison media directory required')
    output.mkdir(parents=True,exist_ok=False)
    videos=[]; decoded=0; encoded_count=0; protected={}
    for key in ('007','030'):
        source_dir=Path(f'outputs/exp0042/{key}-v1'); candidate_dir=comparison/key
        request=json.loads((source_dir/'request.json').read_text())
        source=next(p for p in request['input_sha256'] if p.endswith('.mp4'))
        scene_path=next(p for p in request['input_sha256'] if 'scene' in p and p.endswith('.json'))
        paths=[source,scene_path,str(source_dir/'frame-evidence.jsonl'),str(candidate_dir/'frame-evidence.jsonl'),
            str(candidate_dir/'baseline-cards.json'),str(candidate_dir/'exp0042-transition-only-cards.json'),
            str(candidate_dir/'candidate-only-cards.json'),str(candidate_dir/'summary.json')]
        hashes={p:sha(p) for p in paths}; protected.update(hashes)
        if any(hashes[p]!=request['input_sha256'][p] for p in (source,scene_path)):
            raise ValueError('Source/scene binding changed')
        scene=json.loads(Path(scene_path).read_text()); size=np.asarray(scene['source_size'])
        old=[json.loads(line) for line in (source_dir/'frame-evidence.jsonl').open()]
        new=[json.loads(line) for line in (candidate_dir/'frame-evidence.jsonl').open()]
        validate_clocks(old,new)
        if any(a['point_paths']!=b['point_paths'] for a,b in zip(old,new)):
            raise ValueError('Comparison changed saved points')
        bundles={name:json.loads((candidate_dir/path).read_text()) for name,path in [
            ('original','baseline-cards.json'),('exp42','exp0042-transition-only-cards.json'),
            ('exp43','candidate-only-cards.json')]}
        poly=np.asarray(scene['approach_polygon'])*size
        lo=np.maximum([0,0],np.floor(poly.min(axis=0)-30)).astype(int)
        hi=np.minimum(size,np.ceil(poly.max(axis=0)+30)).astype(int)
        crop=[int(v) for v in [*lo,*hi]]; x1,y1,x2,y2=crop
        line=np.rint(np.asarray(scene['line'])*size).astype(int)
        tb=Fraction(old[0]['time_base']); rate=1/(frame_clock(old[1])-frame_clock(old[0]))
        handles=[]; width=480;height=510;header=270;history=defaultdict(deque)
        for spec in clip_specs(key,old):
            chosen=[r for r in old if spec['range'][0]<=r['pts']<=spec['range'][1]]
            path=output/(spec['name']+'.mp4'); container=av.open(str(path),'w')
            stream=container.add_stream('libx264',rate=rate)
            stream.width=width*3;stream.height=height+header;stream.pix_fmt='yuv420p'
            stream.time_base=tb;stream.codec_context.time_base=tb;stream.options={'crf':'21','preset':'fast'}
            handles.append(dict(spec=spec,path=str(path),container=container,stream=stream,
                first_native_pts=chosen[0]['native_pts'],first_pts=chosen[0]['pts'],mapping=[]))
        def overlay(image,live,wid,boxes):
            canvas=image.copy()
            cv2.line(canvas,tuple(line[0]),tuple(line[1]),(255,100,255),1)
            for b in boxes:
                if b.get('observed') is False or b.get('bbox') is None or b['score']<.25:continue
                box=np.rint(np.asarray(b['bbox'])*np.tile(size,2)).astype(int)
                cv2.rectangle(canvas,tuple(box[:2]),tuple(box[2:]),(70,240,70),1)
            if wid is not None and wid in live:
                for trail in live[wid]['trails']:
                    points=np.rint(trail['vertices']).astype(np.int32);c=color(wid)
                    if len(points)>1:cv2.polylines(canvas,[points],False,c,1)
                    cv2.circle(canvas,tuple(points[-1]),2,c,-1)
            return canvas[y1:y2,x1:x2]
        try:
            for index,image in decode_native(source,old):
                decoded+=1; a,b=old[index],new[index]
                live=short_paths(history,a)
                best=lambda r:max(r['signals'],key=lambda s:s['score'],default=None)
                bs,cs=best(a),best(b)
                panels=(image[y1:y2,x1:x2],
                        overlay(image,live,bs['window_id'] if bs else None,a['actual_boxes']),
                        overlay(image,live,cs['window_id'] if cs else None,a['actual_boxes']))
                canvas=np.zeros((height+header,width*3,3),np.uint8)
                for n,panel in enumerate(panels):
                    scale=min(width/panel.shape[1],height/panel.shape[0])
                    small=cv2.resize(panel,(round(panel.shape[1]*scale),round(panel.shape[0]*scale)))
                    canvas[header:header+small.shape[0],n*width:n*width+small.shape[1]]=small
                metadata=frame_metadata(a,b,bundles,old[0]['pts'])
                labels=[f"EXP43 | source {a['pts']:.6f}s | native {a['native_pts']} x {a['time_base']} | frame {a['frame_index']}",
                    f"CURRENT EXP42 score {a['score']:.6f} | EXP43 score {b['score']:.6f} | threshold .55 unchanged | not probabilities"]
                for mode,s in metadata['statuses'].items():
                    labels.append(f"{mode} SEPARATE: rows {s['candidate_rows']} | cards {s['cards']} | notices {s['notification_intents']} | first notice {s['first_notification_pts']} | last candidate {s['latest_candidate_pts']}")
                if bs:labels.append(f"EXP42 winner {bs['window_id']} | recent ref {bs['reference_pts']:.6f}s | points {bs['point_count']} | {bs['route']}")
                else:labels.append('EXP42: no evaluated window at current frame')
                if cs:labels.append(f"EXP43 winner {cs['window_id']} | seed geometry ref {cs['geometry_reference_pts']:.6f}s (age {cs['geometry_dt']:.3f}s) | recent dynamics ref {cs['recent_reference_pts']:.6f}s")
                else:labels.append('EXP43: no evaluated window at current frame')
                labels.extend(['ORIGINAL FIXED SCENE CROP                        EXP42 WINNING WINDOW                         EXP43 WINNING WINDOW',
                    'Current dots + preceding 0.3s trails; colors are windows, not person IDs. Same saved points/boxes. No new flow/model.',
                    'Old18 alerts/5 notices stay separate. Candidate timelines are diagnostic. Pixels after a candidate are display context.'])
                for n,label in enumerate(labels):cv2.putText(canvas,label,(8,20+25*n),0,.46,(240,240,240),1)
                for h in handles:
                    if not h['spec']['range'][0]<=a['pts']<=h['spec']['range'][1]:continue
                    frame=av.VideoFrame.from_ndarray(canvas,format='bgr24')
                    frame.pts=a['native_pts']-h['first_native_pts'];frame.time_base=tb
                    for packet in h['stream'].encode(frame):h['container'].mux(packet)
                    m=frame_metadata(a,b,bundles,h['first_pts'])
                    m['presentation_pts']=float(frame.pts*tb)
                    h['mapping'].append(m);encoded_count+=1
        finally:
            for h in handles:
                for packet in h['stream'].encode():h['container'].mux(packet)
                h['container'].close()
        for h in handles:
            with av.open(h['path']) as container:
                clocks=[float(f.pts*f.time_base) for f in container.decode(video=0)]
            expected=[m['presentation_pts'] for m in h['mapping']]
            if len(clocks)!=len(expected) or any(abs(a-b)>1e-6 for a,b in zip(clocks,expected)):
                raise ValueError('Encoded clock/count mismatch')
            videos.append(dict(h['spec'],path=h['path'],frames=len(clocks),sha256=sha(h['path']),
                original_crop_pixels=crop,first_native_pts=h['first_native_pts'],time_base=str(tb),mapping=h['mapping']))
        if any(sha(p)!=digest for p,digest in hashes.items()):raise ValueError('Media input changed')
    report=dict(experiment='EXP-0043',videos=videos,source_frames_decoded=decoded,frames_encoded=encoded_count,
        input_sha256=protected,code_sha256=sha(__file__),test_sha256=sha('tests/test_exp0043_comparison_media.py'),
        elapsed_seconds=time.perf_counter()-begin,pixels_local_only=True,new_flow_calls=0,model_calls=0,
        trail_seconds=.3,scores='saved current-frame only',timelines='three independent causal prefixes',
        crop_from='existing approach_polygon plus30px display margin; same as earlier inspection',
        original_media_untouched=True,semantic_quality=None,clock_validation='every encoded frame decoded locally and checked')
    write_json(output/'manifest.json',report)
    return {k:v for k,v in report.items() if k not in ('videos','input_sha256')}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--comparison',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); print(json.dumps(execute(args.comparison,args.output),indent=2))


if __name__=='__main__':main()
