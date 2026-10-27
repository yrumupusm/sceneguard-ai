"""Render the exact EXP-0002 review PTS for four cached threshold replays."""
import argparse
import json
from pathlib import Path
import av
from PIL import Image,ImageDraw

def run(clip):
    root=Path('outputs/cv_phase2d')
    replay=root/f'replay{clip}'
    manifests=json.loads(Path(f'outputs/cv_phase2b/review{clip}/review_manifest.json').read_text())
    selected={r['pts'] for r in manifests}
    conditions={}
    for tag in ['050','040','030','025']:
        conditions[tag]={r['pts']:r for r in map(json.loads,(replay/f't{tag}/frames.jsonl').read_text().splitlines())}
    output=root/f'review{clip}';output.mkdir(exist_ok=False)
    with av.open(f'data/TS_침입/E01_{clip}.mp4') as container:
        container.streams.video[0].thread_count=2
        for frame in container.decode(video=0):
            pts=float(frame.pts*frame.time_base)
            if pts>max(selected):break
            if pts not in selected:continue
            original=frame.to_image();original.thumbnail((960,540))
            canvas=Image.new('RGB',(1920,1160),'black')
            for k,(tag,rows) in enumerate(conditions.items()):
                im=original.copy();draw=ImageDraw.Draw(im)
                for box in rows[pts]['detections']:
                    b=[v*(960 if i%2==0 else 540) for i,v in enumerate(box['bbox'])]
                    draw.rectangle(b,outline='red',width=2)
                    draw.text((b[0],max(0,b[1]-12)),f"{box['score']:.2f} #{box['track_id']}",fill='yellow')
                x,y=(k%2)*960,(k//2)*580
                canvas.paste(im,(x,y+40))
                ImageDraw.Draw(canvas).text((x+10,y+10),f"E01_{clip} PTS {pts:.6f} threshold {int(tag)/100:.2f} | {len(rows[pts]['detections'])} boxes | IDs NOT verified identities",fill='white')
            canvas.save(output/f'compare_{pts:.6f}.jpg',quality=95)
    assert len(list(output.glob('compare*')))==len(manifests)
    (output/'review_manifest.json').write_text(json.dumps(manifests,indent=2))
    print(clip,len(manifests))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('clips',nargs='+',choices=['030','006','007','031'])
    for clip in p.parse_args().clips:run(clip)
