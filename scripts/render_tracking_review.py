"""Local A/B/C comparison videos, fixed 35 frames, dense event strips; no inference."""
import argparse
import json
from fractions import Fraction
from pathlib import Path
import av
from PIL import Image, ImageDraw

ROOT=Path('outputs/cv_phase2e')
COLORS=dict(high='lime',low_second='cyan',unconfirmed='orange',lost_prediction='magenta')


def panel(original, row, cfg, title, size=(640,360)):
    im=original.resize(size);d=ImageDraw.Draw(im);w,h=size
    xy=lambda b:[v*(w if i%2==0 else h) for i,v in enumerate(b)]
    d.rectangle(xy(cfg['roi']),outline='yellow')
    d.line([tuple(xy([*cfg['line'][0]])[:2]),tuple(xy([*cfg['line'][1]])[:2])],fill='white',width=2)
    for item in row['states']:
        pred=not item['observed'];b=item['prediction_bbox'] if pred else item['bbox']
        color=COLORS['lost_prediction' if pred else ('unconfirmed' if not item['confirmed'] else item['association'])]
        b=xy(b)
        if pred:
            # Dashed forecast rectangle: never used for boundary events.
            for a,z,hor in [(b[:2],b[2:3]+b[1:2],True),(b[0:1]+b[3:4],b[2:],True),(b[:2],b[0:1]+b[3:4],False),(b[2:3]+b[1:2],b[2:],False)]:
                lo,hi=(a[0],z[0]) if hor else (a[1],z[1])
                for x in range(int(lo),int(hi),8):
                    d.line((x,a[1],min(x+4,hi),a[1]) if hor else (a[0],x,a[0],min(x+4,hi)),fill=color,width=2)
        else:d.rectangle(b,outline=color,width=2)
        label=f"#{item['track_id']} "+(f"P {item['unobserved_seconds']:.2f}s" if pred else f"{item['score']:.2f} {'L' if item['association']=='low_second' else 'H'}")
        if not item['confirmed']:label+=' U'
        d.text((b[0],max(0,b[1]-12)),label,fill=color,stroke_width=1,stroke_fill='black')
    canvas=Image.new('RGB',(w,h+30));canvas.paste(im,(0,30))
    ImageDraw.Draw(canvas).text((5,8),title,fill='white')
    return canvas


def render(clip):
    folder=ROOT/f'review{clip}';folder.mkdir(exist_ok=False)
    all_rows={c:{r['pts']:r for r in map(json.loads,(ROOT/f'track{clip}/{c}/frames.jsonl').read_text().splitlines())} for c in 'ABC'}
    selected=json.loads(Path(f'outputs/cv_phase2d/review{clip}/review_manifest.json').read_text())
    selected_pts={m['pts'] for m in selected}
    cfg=json.loads((ROOT/f'track{clip}/A/summary.json').read_text())['config']
    native=[];dense=[]
    with av.open(f'data/TS_침입/E01_{clip}.mp4') as source, av.open(str(folder/'continuous_ABC.mp4'),'w') as output:
        rate=Fraction(30000,1001) if clip=='006' else Fraction(30)
        stream=output.add_stream('libx264',rate=rate);stream.width=1280;stream.height=780
        stream.pix_fmt='yuv420p';stream.options={'crf':'20','preset':'veryfast'}
        first=None
        for frame in source.decode(video=0):
            pts=float(frame.pts*frame.time_base)
            if pts>max(all_rows['A']):break
            if pts not in all_rows['A']:continue
            original=frame.to_image();canvas=Image.new('RGB',(1280,780))
            orig=Image.new('RGB',(640,390));orig.paste(original.resize((640,360)),(0,30))
            ImageDraw.Draw(orig).text((5,8),f'E01_{clip} PTS {pts:.6f} RAW | green H cyan L orange U magenta P',fill='white')
            canvas.paste(orig,(0,0))
            for condition,(x,y) in zip('ABC',[(640,0),(0,390),(640,390)]):
                canvas.paste(panel(original,all_rows[condition][pts],cfg,condition),(x,y))
            if first is None:first=frame.pts
            video_frame=av.VideoFrame.from_image(canvas);video_frame.pts=frame.pts-first;video_frame.time_base=frame.time_base
            for packet in stream.encode(video_frame):output.mux(packet)
            native.append(dict(pts=pts,native_pts=frame.pts,time_base=str(frame.time_base)))
            if pts in selected_pts:canvas.save(folder/f'compare_{pts:.6f}.jpg',quality=95)
            # Dense event crops for consecutive-frame review; display only, never model input.
            event_window=(clip=='030' and 89.6<=pts<=90.5) or (clip=='007' and 55.9<=pts<=57.)
            if event_window:
                crop=(650,360,1250,780) if clip=='030' else (1100,130,1600,570)
                row=Image.new('RGB',(1500,330))
                for i,c in enumerate(['RAW','B','C']):
                    annotated=original if c=='RAW' else panel(original,all_rows[c][pts],cfg,c,(1920,1080)).crop((0,30,1920,1110))
                    tile=annotated.crop(crop).resize((500,300));row.paste(tile,(i*500,30))
                    ImageDraw.Draw(row).text((i*500+5,8),f'{c} PTS {pts:.6f}',fill='white')
                dense.append(row)
        for packet in stream.encode():output.mux(packet)
    assert len(native)==len(all_rows['A'])
    assert len(list(folder.glob('compare*')))==len(selected)
    (folder/'native_pts.json').write_text(json.dumps(native,indent=2))
    (folder/'review_manifest.json').write_text(json.dumps(selected,indent=2))
    for i in range(0,len(dense),5):
        sheet=Image.new('RGB',(1500,330*len(dense[i:i+5])))
        for j,im in enumerate(dense[i:i+5]):sheet.paste(im,(0,330*j))
        sheet.save(folder/f'event_sequence_{i:03d}.jpg',quality=95)
    print(clip,len(native),'frames',len(selected),'fixed review',len(dense),'dense event frames',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('clips',nargs='+',choices=['030','006','007','031'])
    for clip in p.parse_args().clips:render(clip)
