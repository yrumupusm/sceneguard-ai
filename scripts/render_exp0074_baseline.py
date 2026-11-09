"""Local-only paired source/GT/prediction videos from already frozen dev frames."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.evaluate_person_detector_pair import sha


def render(manifest_path, baseline, output):
    import av
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    m=json.loads(manifest_path.read_text())
    evaluation=json.loads((baseline/'A-evaluation.json').read_text())
    if evaluation['manifest_sha256']!=sha(manifest_path):raise ValueError('Frozen manifest mismatch')
    pred={p['frame_id']:p for p in map(json.loads,(baseline/'A-predictions.jsonl').read_text().splitlines())}
    matched={p['frame_id']:p for p in evaluation['frames']}
    groups=defaultdict(list)
    for f in m['frames']:
        if f['split']=='development':
            groups[(f['event_group'],bool(f['confirmed_person_boxes']))].append(f)
    output.mkdir(parents=True,exist_ok=False)
    font=ImageFont.truetype('/home/jhc7484/.local/share/fonts/sceneguard-portfolio/malgun.ttf',23)
    evidence=[]
    for index, ((event,occupied),frames) in enumerate(sorted(groups.items()),1):
        frames.sort(key=lambda f:f['source_pts'])
        video=output/f'development-{index:02d}.mp4'
        with av.open(str(video),'w') as container:
            stream=container.add_stream('libx264',rate=3)
            stream.width=1920;stream.height=640;stream.pix_fmt='yuv420p'
            stream.options={'crf':'19','preset':'fast'}
            for f in frames:
                image_path=manifest_path.parent/f['image']
                if sha(image_path)!=f['image_sha256']:raise ValueError('Image changed')
                source=Image.open(image_path).convert('RGB')
                if list(source.size)!=f['source_size']:raise ValueError('Geometry changed')
                overlay=source.copy();d=ImageDraw.Draw(overlay)
                for b in f['confirmed_person_boxes']:d.rectangle(b['xyxy'],outline='#00ffbb',width=4)
                p=pred[f['frame_id']]
                for b,s in zip(p['boxes'],p['person_scores']):
                    if s<.5:continue
                    d.rectangle(b,outline='#ff9900',width=4)
                    d.text((b[0],max(0,b[1]-27)),f'A {s:.2f}',font=font,fill='#ff9900')
                canvas=Image.new('RGB',(1920,640),'#161616')
                canvas.paste(source.resize((960,540)),(0,65));canvas.paste(overlay.resize((960,540)),(960,65))
                d=ImageDraw.Draw(canvas);r=matched[f['frame_id']]
                d.text((12,4),f'EXP-0074 A | 원본 {f["source_pts"]:.3f}초 | 왼쪽 원본 / 오른쪽 검수 정답·실제 검출',font=font,fill='white')
                d.text((12,34),f'청록: 확정 사람 정답 | 주황: YOLO26m 점수≥0.5 | TP {r["tp"]} / FP {r["fp"]} / FN {r["fn"]}',font=font,fill='white')
                d.text((12,608),'사람 검출 개발 평가입니다. 넘기·침입 판단이나 독립 시험 성능이 아닙니다.',font=font,fill='white')
                for packet in stream.encode(av.VideoFrame.from_ndarray(np.asarray(canvas),format='rgb24')):container.mux(packet)
            for packet in stream.encode():container.mux(packet)
        evidence.append(dict(artifact_id=f'exp0074-dev-{index:02d}',path=str(video.resolve()),sha256=sha(video),
            event_group=event,frames=len(frames),person_present=occupied,start=frames[0]['source_pts'],end=frames[-1]['source_pts'],
            continuous=all(abs(b['source_pts']-a['source_pts']-1/3)<1e-5 for a,b in zip(frames,frames[1:]))))
    (output/'evidence.json').write_text(json.dumps(evidence,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(evidence,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('manifest','baseline','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();render(a.manifest.resolve(),a.baseline.resolve(),a.output.resolve())
