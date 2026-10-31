"""Bounded local three-panel review of saved paths, without new CV inference.

The standalone HTML selects every live window without a dashboard or server.
Colors identify seed windows; neither box overlap nor paths imply identity.
"""
import argparse
import base64
from collections import defaultdict, deque
from fractions import Fraction
import json
from pathlib import Path
import time

import numpy as np

from .run_tracklet_linking import decode_native
from .transition_diagnostics import sha, write_json


def short_paths(history,row,seconds=.3):
    at=row['pts'];live={}
    for w in row['point_paths']:
        wid=w['window_id'];h=history[wid]
        h.append((at,dict(zip(w['point_ids'],w['points_original_pixels']))))
        while h and at-h[0][0]>seconds+1e-9:h.popleft()
        live[wid]=dict(w, trails=[dict(point_id=pid,vertices=[points[pid] for _,points in h if pid in points])
                                    for pid in w['point_ids']])
    for wid in list(history):
        if wid not in live:del history[wid]
    return live


def color(wid):
    import colorsys
    r,g,b=colorsys.hsv_to_rgb((int(wid[1:])*.61803398875)%1,.75,1)
    return tuple(round(c*255) for c in (b,g,r))


HTML=r'''<!doctype html><meta charset="utf-8"><title>EXP43 local saved-window review</title>
<style>body{background:#111;color:#eee;font:15px sans-serif}canvas{width:100%;max-width:1500px}button,select,input{font-size:17px}pre{white-space:pre-wrap}#scrub{width:65%}</style>
<h2>007 64–74s · local original / all live / selected window</h2>
<p>Pixels stay in this file. Display crop is fixed from the existing scene; no inference region changes.
Colors are seed windows, not people. Lines show only the preceding 0.3s; circles are current points.</p>
<button id="play">Play / pause</button> <input id="scrub" type="range" min="0" value="0"> <span id="clock"></span><br>
<label>Window: <select id="window"></select></label> <label><input type="checkbox" id="best" checked>Follow highest score</label>
<p>Uncheck Follow highest score and choose ANY window. Gray options are inactive at the current frame.
Use the frame slider to inspect seeds before and after a dropout. This file covers every live window in 64–74s.</p>
<canvas id="canvas" width="1440" height="560"></canvas><pre id="details"></pre>
<script>const data=DATA;const images=data.frames.map(f=>{let i=new Image();i.src=f.jpeg;return i});
const slider=document.getElementById('scrub'),sel=document.getElementById('window'),best=document.getElementById('best'),cv=document.getElementById('canvas'),ctx=cv.getContext('2d');
slider.max=data.frames.length-1;data.windows.forEach(w=>{let o=new Option(w,w);sel.add(o)});let playing=false;
document.getElementById('play').onclick=()=>playing=!playing;
const clr=w=>`hsl(${(Number(w.slice(1))*.61803398875%1)*360} 75% 65%)`;
function draw(){let k=Number(slider.value),f=data.frames[k];if(best.checked&&f.best)sel.value=f.best;
for(let o of sel.options){o.style.color=f.paths[o.value]?'black':'#999'}let wid=sel.value;
ctx.fillStyle='#111';ctx.fillRect(0,0,1440,560);let scale=Math.min(480/data.cropWidth,510/data.cropHeight);
function pos(p,n){return [n*480+(p[0]-data.crop[0])*scale,50+(p[1]-data.crop[1])*scale]}
for(let n=0;n<3;n++){ctx.drawImage(images[k],n*480,50,data.cropWidth*scale,data.cropHeight*scale);ctx.fillStyle='#fff';ctx.font='16px sans-serif';ctx.fillText(['ORIGINAL FIXED SCENE CROP','ALL LIVE: current dots + 0.3s trails','SELECTED '+wid][n],n*480+4,22);
if(n===0)continue;ctx.save();ctx.beginPath();ctx.rect(n*480,50,480,510);ctx.clip();
ctx.strokeStyle='#f6f';ctx.lineWidth=1;ctx.beginPath();data.line.forEach((p,j)=>{let [x,y]=pos(p,n);j?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.stroke();
for(let b of f.boxes){let p=pos([b.bbox[0]*data.size[0],b.bbox[1]*data.size[1]],n);ctx.strokeStyle='#6f6';ctx.strokeRect(...p,(b.bbox[2]-b.bbox[0])*data.size[0]*scale,(b.bbox[3]-b.bbox[1])*data.size[1]*scale)}
for(let [w,path] of Object.entries(f.paths)){if(n===2&&w!==wid)continue;ctx.strokeStyle=ctx.fillStyle=clr(w);ctx.lineWidth=n===2?1.4:.8;
for(let t of path.trails){ctx.beginPath();t.vertices.forEach((p,j)=>{let[x,y]=pos(p,n);j?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.stroke();let[x,y]=pos(t.vertices.at(-1),n);ctx.beginPath();ctx.arc(x,y,n===2?2.5:1.6,0,7);ctx.fill();if(n===2){ctx.font='10px sans-serif';ctx.fillText(t.point_id,x+3,y)}}}ctx.restore()}
document.getElementById('clock').textContent=f.pts.toFixed(6)+'s · frame '+f.frame_index;
let s=f.signals.find(s=>s.window_id===wid);document.getElementById('details').textContent=JSON.stringify({native_pts:f.native_pts,time_base:f.time_base,selected:wid,active:!!f.paths[wid],best:f.best,score:f.score,camera_step_pixels:f.camera_step_pixels,camera_support:f.camera_support,path:f.paths[wid]?{seed_pts:f.paths[wid].seed_pts,seed_cache_index:f.paths[wid].seed_cache_index,points:f.paths[wid].point_ids.length}:null,signal:s||'No signal yet / window inactive'},null,2)}
images.forEach(i=>i.onload=draw);slider.oninput=draw;sel.onchange=()=>{best.checked=false;draw()};best.onchange=draw;setInterval(()=>{if(playing){slider.value=(Number(slider.value)+1)%data.frames.length;draw()}},1000/30);</script>'''


def execute(directory,output,start=64.,end=74.):
    import av
    import cv2
    begin=time.perf_counter();directory=Path(directory);output=Path(output)
    request=json.loads((directory/'request.json').read_text())
    source=next(p for p in request['input_sha256'] if p.endswith('.mp4'))
    scene_path=next(p for p in request['input_sha256'] if 'scene' in p and p.endswith('.json'))
    scene=json.loads(Path(scene_path).read_text());size=np.asarray(scene['source_size'])
    inputs={p:sha(p) for p in (source,scene_path,str(directory/'frame-evidence.jsonl'))}
    if inputs[source]!=request['input_sha256'][source]:raise ValueError('Source changed')
    if inputs[scene_path]!=request['input_sha256'][scene_path]:raise ValueError('Scene changed')
    if output.exists() or not output.resolve().is_relative_to(Path('outputs').resolve()):raise ValueError('New local output required')
    rows=[json.loads(line) for line in (directory/'frame-evidence.jsonl').read_text().splitlines()]
    history=defaultdict(deque);frames=[];chosen=[]
    for row in rows:
        paths=short_paths(history,row)
        if start<=row['pts']<=end:
            selected=max(row['signals'],key=lambda s:s['score'],default=None)
            frames.append(dict(pts=row['pts'],native_pts=row['native_pts'],time_base=row['time_base'],
                frame_index=row['frame_index'],score=row['score'],best=selected['window_id'] if selected else None,
                signals=[{k:v for k,v in s.items() if k not in ('point_ids','points_original_pixels')} for s in row['signals']],
                boxes=[b for b in row['actual_boxes'] if b.get('observed') is not False and b['score']>=.25],
                paths=paths,camera_step_pixels=row['camera_step_pixels'],camera_support=row['camera_support']))
            chosen.append(row)
    if not frames:raise ValueError('Range missing')
    poly=np.asarray(scene['approach_polygon'])*size
    lo=np.maximum([0,0],np.floor(poly.min(axis=0)-30)).astype(int)
    hi=np.minimum(size,np.ceil(poly.max(axis=0)+30)).astype(int)
    crop=list(map(int,[*lo,*hi]));x1,y1,x2,y2=crop
    windows=sorted({wid for f in frames for wid in f['paths']})
    # All seeds at 64.5 and 65.0, without choosing IDs by score or semantic guess.
    individual=sorted({w['window_id'] for r in chosen for w in r['point_paths']
                       if 64.5<=w['seed_pts']<=65.0})
    output.mkdir(parents=True);handles=[];width=480;height=510;header=190
    tb=Fraction(chosen[0]['time_base']);rate=1/(Fraction(chosen[1]['native_pts']-chosen[0]['native_pts'])*tb)
    for wid in [None]+individual:
        target=output/('all-live-64-74.mp4' if wid is None else f'individual-{wid}.mp4')
        out=av.open(str(target),'w');stream=out.add_stream('libx264',rate=rate)
        stream.width=width*3;stream.height=height+header;stream.pix_fmt='yuv420p'
        stream.time_base=tb;stream.codec_context.time_base=tb;stream.options={'crf':'21','preset':'fast'}
        handles.append(dict(wid=wid,path=str(target),output=out,stream=stream,mapping=[],first=None))
    line=np.rint(np.asarray(scene['line'])*size).astype(int)
    def panel(image,paths,boxes,selected=None):
        image=image.copy()
        for b in boxes:
            box=np.rint(np.asarray(b['bbox'])*np.tile(size,2)).astype(int)
            cv2.rectangle(image,tuple(box[:2]),tuple(box[2:]),(70,240,70),1)
        cv2.line(image,tuple(line[0]),tuple(line[1]),(255,100,255),1)
        for wid,path in paths.items():
            if selected is not None and wid!=selected:continue
            for trail in path['trails']:
                points=np.rint(trail['vertices']).astype(np.int32);c=color(wid)
                if len(points)>1:cv2.polylines(image,[points],False,c,1)
                cv2.circle(image,tuple(points[-1]),2,c,-1)
                if selected:cv2.putText(image,str(trail['point_id']),tuple(points[-1]),0,.3,c,1)
        return image[y1:y2,x1:x2]
    try:
        for index,image in decode_native(source,chosen):
            frame=frames[index]; raw=image[y1:y2,x1:x2]
            ok,jpeg=cv2.imencode('.jpg',raw,[cv2.IMWRITE_JPEG_QUALITY,78])
            if not ok:raise ValueError('JPEG encoding failed')
            frame['jpeg']='data:image/jpeg;base64,'+base64.b64encode(jpeg).decode()
            all_panel=panel(image,frame['paths'],frame['boxes'])
            for handle in handles:
                wid=handle['wid'] or frame['best']
                if handle['wid'] and wid not in frame['paths']:continue
                s=next((s for s in frame['signals'] if s['window_id']==wid),None)
                selected_panel=panel(image,frame['paths'],frame['boxes'],wid)
                canvas=np.zeros((height+header,width*3,3),np.uint8)
                for n,p in enumerate((raw,all_panel,selected_panel)):
                    scale=min(width/p.shape[1],height/p.shape[0]);small=cv2.resize(p,(round(p.shape[1]*scale),round(p.shape[0]*scale)))
                    canvas[header:header+small.shape[0],n*width:n*width+small.shape[1]]=small
                labels=[f"EXP43 saved evidence | source {frame['pts']:.6f}s | frame {frame['frame_index']} | window {wid}",
                    'ORIGINAL FIXED SCENE CROP                         ALL LIVE: CURRENT DOTS + 0.3s TRAILS                  SELECTED WINDOW: POINT IDs',
                    f"Camera supported {frame['camera_support']} | step {frame['camera_step_pixels']} | window colors are NOT person IDs"]
                if s:
                    labels.extend([f"seed {s['seed_pts']:.6f}s | reference {s['reference_pts']:.6f}s | points {s['point_count']} | score {s['score']:.6f} | {s['route']}",
                        f"proximity {s['proximity']:.4f} | up {s['upward_image_motion']:.4f} | deform {s['local_deformation']:.4f} | change {s['motion_change']:.4f}",
                        f"progress {s['normal_progress']:.4f} | crossing fraction {s['crossing_fraction']:.4f} | coherence {s['coherence']:.4f} | threshold .55"])
                else:labels.append('No scoring signal yet: newly seeded window. Current points remain displayed.')
                for n,label in enumerate(labels):cv2.putText(canvas,label,(8,22+27*n),0,.50,(240,240,240),1)
                if handle['first'] is None:handle['first']=frame['native_pts']
                video=av.VideoFrame.from_ndarray(canvas,format='bgr24');video.pts=frame['native_pts']-handle['first'];video.time_base=tb
                for packet in handle['stream'].encode(video):handle['output'].mux(packet)
                handle['mapping'].append(dict(source_pts=frame['pts'],source_native_pts=frame['native_pts'],
                    presentation_pts=float(video.pts*tb),window_id=wid))
    finally:
        for handle in handles:
            for packet in handle['stream'].encode():handle['output'].mux(packet)
            handle['output'].close()
    data=dict(frames=frames,windows=windows,crop=crop,cropWidth=x2-x1,cropHeight=y2-y1,
        size=size.tolist(),line=(np.asarray(scene['line'])*size).tolist())
    html=output/'review-all-windows.html'
    html.write_text(HTML.replace('DATA',json.dumps(data,separators=(',',':'))),encoding='utf-8')
    clips=[]
    for h in handles:
        with av.open(h['path']) as encoded:clocks=[float(f.pts*f.time_base) for f in encoded.decode(video=0)]
        expected=[m['presentation_pts'] for m in h['mapping']]
        if len(clocks)!=len(expected) or any(abs(a-b)>1e-6 for a,b in zip(clocks,expected)):
            raise ValueError('Encoded clock mismatch')
        clips.append(dict(window_id=h['wid'],path=h['path'],frames=len(clocks),sha256=sha(h['path']),mapping=h['mapping']))
    if inputs!={p:sha(p) for p in inputs}:raise ValueError('Media inputs changed')
    report=dict(experiment='EXP-0043',pixels_local_only=True,new_flow_calls=0,model_calls=0,
        range=[start,end],source_frames=len(frames),windows=len(windows),trail_seconds=.3,
        original_crop_pixels=crop,crop_from='existing approach_polygon plus30px display margin',
        inspection_html=str(html),inspection_html_sha256=sha(html),videos=clips,input_sha256=inputs,
        code_sha256=sha(__file__),elapsed_seconds=time.perf_counter()-begin,
        individual_selection='ALL seeds born64.5–65.0 inclusive, not score-picked',
        semantic_quality=None,point_identity_is_not_person_identity=True)
    write_json(output/'manifest.json',report)
    return {k:v for k,v in report.items() if k!='videos'}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    print(json.dumps(execute(args.directory,args.output),indent=2))


if __name__=='__main__':main()
