"""Display-only review of two saved EXP-0005 candidate windows. No tracker/inference."""
import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path
import av
from PIL import Image, ImageDraw, ImageFont

ROOT = Path('outputs/cv_phase2f')
SAVED = Path('outputs/cv_phase2e')
FONT = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 15)
COLORS = ['#ffcc44', '#66ff66', '#ff7777', '#55ddff', '#ffaaee', '#bbbbff', '#ffffff']
WINDOWS = {'007': (54.9, 58., (1080, 100, 1680, 640)),
           '030': (88.6, 91.5, (650, 300, 1250, 840))}


def rows(path):
    return list(map(json.loads, path.read_text().splitlines()))


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def draw_panel(original, record, config, crop, title):
    tile = original.crop(crop)
    d = ImageDraw.Draw(tile)
    xy = lambda x, y: (x*1920-crop[0], y*1080-crop[1])
    labels = []
    if record is not None:
        d.line([xy(*p) for p in config['line']], fill='white', width=3)
        for item in record['states']:
            pred = not item['observed']
            box = item['prediction_bbox'] if pred else item['bbox']
            x1, y1 = xy(*box[:2]); x2, y2 = xy(*box[2:])
            if x2 < 0 or x1 > 600 or y2 < 0 or y1 > 540:
                continue
            color = 'magenta' if pred else COLORS[item['track_id'] % len(COLORS)]
            if pred:
                for y in (y1, y2):
                    for x in range(int(x1), int(x2), 10):
                        d.line((x,y,min(x+5,x2),y), fill=color,width=2)
                for x in (x1,x2):
                    for y in range(int(y1),int(y2),10):
                        d.line((x,y,x,min(y+5,y2)),fill=color,width=2)
                label = f"#{item['track_id']} PRED {item['unobserved_seconds']:.3f}s"
            else:
                d.rectangle((x1,y1,x2,y2),outline=color,width=2)
                x = (x1+x2)/2
                d.ellipse((x-4,y2-4,x+4,y2+4),fill=color,outline='black')
                label = f"#{item['track_id']} {item['score']:.3f} {'L' if item['association']=='low_second' else 'H'}"
                if not item['confirmed']: label += ' UNCONFIRMED'
            d.text((x1,max(0,y1-18)), f"#{item['track_id']}",font=FONT,fill=color,stroke_width=1,stroke_fill='black')
            labels.append((label,color))
    panel = Image.new('RGB',(600,740))
    panel.paste(tile,(0,40)); pd = ImageDraw.Draw(panel)
    pd.text((8,10),title,font=FONT,fill='white')
    for n,(label,color) in enumerate(labels):
        pd.text((8+(n%2)*300,590+(n//2)*23),label,font=FONT,fill=color)
    if record is not None:
        pd.text((8,710),'Dot: bbox bottom center, NOT feet | dashed: prediction',font=FONT,fill='white')
    return panel


def render(clip):
    start,end,crop = WINDOWS[clip]
    folder = ROOT / clip
    folder.mkdir(parents=True,exist_ok=False)
    saved = {c: {r['native_pts']:r for r in rows(SAVED/f'track{clip}/{c}/frames.jsonl')} for c in 'BC'}
    cache = {r['native_pts']:r for r in rows(Path(f'outputs/cv_phase2d/cache{clip}/person_cache.jsonl'))}
    config = json.loads((SAVED/f'track{clip}/A/summary.json').read_text())['config']
    events = rows(SAVED/f'track{clip}/C/events.jsonl')
    frames=[]; audit=[]
    with av.open(f'data/TS_침입/E01_{clip}.mp4') as source:
        source.seek(int((start-1)/source.streams.video[0].time_base),stream=source.streams.video[0])
        for frame in source.decode(video=0):
            pts=float(frame.pts*frame.time_base)
            if pts < start-1e-8: continue
            if pts > end+1e-8: break
            original=frame.to_image(); canvas=Image.new('RGB',(1800,780))
            detail=dict(pts=pts,native_pts=frame.pts,time_base=str(frame.time_base),conditions={})
            for i,c in enumerate(['RAW','B','C']):
                record=None if c=='RAW' else saved[c][frame.pts]
                canvas.paste(draw_panel(original,record,config,crop,f'{c} | ORIGINAL PTS {pts:.6f}'),(600*i,40))
                if record is None:continue
                values=[]
                for item in record['detections']:
                    idx=item['cache_index']; cached=cache[frame.pts]
                    assert item['score']==cached['scores'][idx]
                    b=item['bbox']; expected=[v/(1920 if j%2==0 else 1080) for j,v in enumerate(cached['boxes'][idx])]
                    assert max(abs(a-z) for a,z in zip(b,expected))<1e-7
                    x,y=(b[0]+b[2])/2,b[3]; a,z=config['line']; dx,dy=z[0]-a[0],z[1]-a[1]
                    dist=(dx*(y-a[1])-dy*(x-a[0]))/math.hypot(dx,dy)
                    values.append(item|dict(bottom_px=[x*1920,y*1080],height_px=(b[3]-b[1])*1080,distance=dist,side=1 if dist>config['band'] else -1 if dist < -config['band'] else 0))
                detail['conditions'][c]=values
            emitting=[e['track_id'] for e in events if abs(e['emitted_at_pts']-pts)<1e-6]
            if emitting:
                ImageDraw.Draw(canvas).text((1210,685),f'SAVED CANDIDATE: {emitting}',font=FONT,fill='yellow')
            canvas.save(folder/f'frame_{pts:.6f}.jpg',quality=95)
            frames.append(canvas);audit.append(detail)
    assert len(frames)==round((end-start)*30)+1
    assert all(b['native_pts']-a['native_pts']==512 for a,b in zip(audit,audit[1:]))
    for event in events:
        sequence = [f for f in audit if event['observed_pts_before']-1e-8 <= f['pts'] <= event['emitted_at_pts']+1e-8]
        assert sequence and all(any(r['track_id']==event['track_id'] for r in f['conditions']['C']) for f in sequence)
    path=folder/'raw_B_C_normal_then_quarter.mp4'
    with av.open(str(path),'w') as output:
        stream=output.add_stream('libx264',rate=30);stream.width=1800;stream.height=780;stream.pix_fmt='yuv420p';stream.options={'crf':'18','preset':'veryfast'}
        index=0
        for repeats,speed in [(1,'1.00x NORMAL'),(4,'0.25x SLOW')]:
            for canvas in frames:
                canvas=canvas.copy();ImageDraw.Draw(canvas).text((8,10),f'E01_{clip} | {speed} | display crop only | H: high / L: low second association | ID colors are NOT person truth',font=FONT,fill='white')
                for _ in range(repeats):
                    f=av.VideoFrame.from_image(canvas);f.pts=index;f.time_base=Fraction(1,30);index+=1
                    for packet in stream.encode(f):output.mux(packet)
        for packet in stream.encode():output.mux(packet)
    with av.open(str(path)) as check:
        count=sum(1 for _ in check.decode(video=0))
    assert count==len(frames)*5
    (folder/'audit.json').write_text(json.dumps(dict(window=[start,end],crop=crop,events=events,frames=audit,output_frames=count,normal_seconds=len(frames)/30,slow_seconds=len(frames)*4/30),indent=2))
    print(clip,len(frames),count,path,flush=True)


if __name__=='__main__':
    ROOT.mkdir(exist_ok=True)
    preserved={str(p):digest(p) for p in SAVED.rglob('*') if p.is_file()}
    for clip in WINDOWS:render(clip)
    assert all(digest(Path(p))==h for p,h in preserved.items())
    (ROOT/'preserved_exp0005.json').write_text(json.dumps(preserved,indent=2))
    print('Preserved EXP-0005 files:',len(preserved))
