"""Pair native-PTS diagnostics and render systematic review sheets locally."""
import argparse
import hashlib
import json
import math
from pathlib import Path

def read(path):
    return json.loads(path.read_text())

def compare(old, new):
    a, b = read(old/'run.json'), read(new/'run.json')
    assert a['status'] == b['status'] == 'complete'
    for key in ['source_sha256', 'config_sha256', 'requested_window', 'frames']:
        assert a[key] == b[key], key
    assert a['code_file_sha256']['sceneguard/boundary.py'] == b['code_file_sha256']['sceneguard/boundary.py']
    rows = [[json.loads(x) for x in (p/'frames.jsonl').read_text().splitlines()] for p in (old,new)]
    assert len(rows[0]) == len(rows[1]) == a['frames']
    assert all(x['pts'] == y['pts'] for x,y in zip(*rows))
    return a,b,rows

def render(old,new,video,out,step):
    import av
    from PIL import Image,ImageDraw
    a,b,rows=compare(old,new)
    assert hashlib.sha256(video.read_bytes()).hexdigest() == b['source_sha256']
    # Refuse tracked/outside paths; render into a new local output directory.
    root=Path(__file__).resolve().parents[1]
    out=out.resolve()
    assert out.is_relative_to(root/'outputs')
    out.mkdir(parents=True,exist_ok=False)
    start,end=b['requested_window']
    if end is None:
        raise ValueError('Review requires a finite short window')
    targets=[];t=start
    while t<end:
        idx=min(range(len(rows[0])),key=lambda i:abs(rows[0][i]['pts']-t))
        targets.append({'requested':t,'pts':rows[0][idx]['pts'],'index':idx})
        t+=step
    selected={r['pts']:r for r in targets}
    panels=[]
    with av.open(str(video)) as container:
        container.streams.video[0].thread_count=2
        for frame in container.decode(video=0):
            pts=float(frame.pts*frame.time_base)
            if pts > max(selected):break
            if pts not in selected:continue
            item=selected[pts];idx=item['index']
            pair=Image.new('RGB',(1920,580))
            for col,(run,seq) in enumerate(zip((a,b),rows)):
                im=frame.to_image();im.thumbnail((960,540))
                d=ImageDraw.Draw(im);w,h=im.size
                for row in seq[idx]['detections']:
                    box=[v*(w if k%2==0 else h) for k,v in enumerate(row['bbox'])]
                    d.rectangle(box,outline='red',width=2)
                    d.text((box[0],max(0,box[1]-12)),f"{row['score']:.2f}",fill='red')
                pair.paste(im,(col*960,40))
                ImageDraw.Draw(pair).text((col*960+8,8),f"{run['model']} | PTS {pts:.6f}",fill='white')
            pair.save(out/f"pair_{pts:.6f}.jpg",quality=95)
            panels.append(pair)
            if len(panels)==4:
                sheet=Image.new('RGB',(1920,580*4))
                for k,p in enumerate(panels):sheet.paste(p,(0,k*580))
                sheet.save(out/f"sheet_{len(list(out.glob('sheet*'))):02d}.jpg",quality=95)
                panels=[]
    if panels:
        sheet=Image.new('RGB',(1920,580*len(panels)))
        for k,p in enumerate(panels):sheet.paste(p,(0,k*580))
        sheet.save(out/f"sheet_{len(list(out.glob('sheet*'))):02d}.jpg",quality=95)
    assert len(list(out.glob('pair*'))) == len(targets)
    (out/'review_manifest.json').write_text(json.dumps(targets,indent=2))
    print(json.dumps({'video':b['video_id'],'paired_frames':b['frames'],'review_frames':len(targets)}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('old','new','video','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--step',type=float,default=2)
    args=p.parse_args()
    if not math.isfinite(args.step) or args.step<=0:p.error('step must be positive')
    render(args.old,args.new,args.video,args.output,args.step)
