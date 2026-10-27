"""Render RAW / saved C candidates / causal review states; no inference."""
import json
from pathlib import Path
from fractions import Fraction
import av
from PIL import Image,ImageDraw
from scripts.render_candidate_focus import draw_panel, FONT, WINDOWS

ROOT=Path('outputs/cv_phase2g')
LABEL={'pending':'PENDING','passed':'PASSED (not event truth)','deferred':'DEFERRED (not normal)','insufficient':'INSUFFICIENT'}


def render(clip):
    start,end,crop=WINDOWS[clip]
    source=Path(f'outputs/cv_phase2e/track{clip}/C')
    rows={r['native_pts']:r for r in map(json.loads,(source/'frames.jsonl').read_text().splitlines())}
    events=list(map(json.loads,(source/'events.jsonl').read_text().splitlines()))
    updates=json.loads((ROOT/f'comparison/{clip}/updates.json').read_text())
    cfg=json.loads((source/'summary.json').read_text())['config']
    folder=ROOT/f'video{clip}';folder.mkdir(exist_ok=False)
    frames=[];manifest=[]
    with av.open(f'data/TS_침입/E01_{clip}.mp4') as inp:
        inp.seek(int((start-1)/inp.streams.video[0].time_base),stream=inp.streams.video[0])
        for f in inp.decode(video=0):
            pts=float(f.pts*f.time_base)
            if pts<start-1e-8:continue
            if pts>end+1e-8:break
            canvas=Image.new('RGB',(1800,980));original=f.to_image()
            for i,title in enumerate(['RAW','C ORIGINAL CANDIDATES','C + REVIEW']):
                panel=draw_panel(original,None if i==0 else rows[f.pts],cfg,crop,f'{title} | PTS {pts:.6f}')
                canvas.paste(panel,(600*i,40))
            d=ImageDraw.Draw(canvas)
            for n,e in enumerate(events):
                if e['emitted_at_pts']>pts+1e-9:continue
                y=790+n*85
                d.text((610,y),f"#{e['track_id']} ORIGINAL {e['emitted_at_pts']:.6f}",font=FONT,fill='yellow')
                d.text((610,y+22),e['direction'],font=FONT,fill='white')
                eligible=[u for u in updates if u['original']==e and u['status_at_pts']<=pts+1e-9]
                u=eligible[-1]
                d.text((1210,y),f"#{e['track_id']} {LABEL[u['status']]}",font=FONT,fill='yellow')
                decision='--' if u['decision_pts'] is None else f"{u['decision_pts']:.6f}"
                wait=pts-e['emitted_at_pts'] if u['status']=='pending' else u['additional_wait']
                d.text((1210,y+22),f"emit {e['emitted_at_pts']:.6f} | decision {decision}",font=FONT,fill='white')
                last=u['last_observation_pts'];last='--' if last is None else f'{last:.6f}'
                d.text((1210,y+44),f"last used {last} | wait {wait:.3f}s",font=FONT,fill='white')
                if u['status']!='pending':
                    d.text((1210,y+64),f"scope flag={u['anomaly_detected']} | missing={len(u['missing_pts'])}",font=FONT,fill='white')
            frames.append(canvas);manifest.append(dict(pts=pts,native_pts=f.pts,time_base=str(f.time_base)))
    path=folder/'raw_C_review_normal_then_quarter.mp4'
    with av.open(str(path),'w') as out:
        stream=out.add_stream('libx264',rate=30);stream.width=1800;stream.height=980;stream.pix_fmt='yuv420p';stream.options={'crf':'18','preset':'veryfast'}
        index=0
        for repeats,speed in [(1,'1x'),(4,'0.25x')]:
            for j,canvas in enumerate(frames):
                canvas=canvas.copy();ImageDraw.Draw(canvas).text((8,10),f'E01_{clip} | {speed} | Status uses only arrivals by displayed original PTS | H/L actual, dashed prediction',font=FONT,fill='white')
                if repeats==1 and any(abs(manifest[j]['pts']-t)<1e-6 for t in [56.633333,56.833333,56.966667,90.3,90.5]):
                    canvas.save(folder/f"check_{manifest[j]['pts']:.6f}.jpg",quality=95)
                for _ in range(repeats):
                    f=av.VideoFrame.from_image(canvas);f.pts=index;f.time_base=Fraction(1,30);index+=1
                    for packet in stream.encode(f):out.mux(packet)
        for packet in stream.encode():out.mux(packet)
    with av.open(str(path)) as inp:
        count=0
        for f in inp.decode(video=0):
            assert abs(float(f.pts*f.time_base)-count/30)<1e-6
            count+=1
    assert count==5*len(frames)
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print(clip,len(frames),count,path,flush=True)


if __name__=='__main__':
    for clip in ['007','030']:render(clip)
