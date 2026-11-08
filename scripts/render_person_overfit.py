"""Local four-condition EXP69 videos using saved predictions only."""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.evaluate_person_detector_pair import sha,validate_predictions
from scripts.render_comparison_validation_errors import encode


def render(folder,output):
    import numpy as np
    from PIL import Image,ImageDraw,ImageFont
    result=json.loads((folder/'result.json').read_text())
    source=ROOT/'outputs/model-comparison/exp0067/confirmed-person-v1/manifest.json'
    assert sha(source)==result['manifest_sha256']
    frames=json.loads(source.read_text())['frames']
    names=list(result['groups'])
    predictions={}
    for name in names:
        p=folder/(name+'-predictions.jsonl');assert sha(p)==result['artifacts'][p.name]
        predictions[name]=validate_predictions([json.loads(l) for l in p.read_text().splitlines()],frames)
    output.mkdir(parents=True,exist_ok=False)
    fontpath=Path('/mnt/c/Windows/Fonts/malgun.ttf')
    font=ImageFont.truetype(str(fontpath),24);small=ImageFont.truetype(str(fontpath),20)
    titles=['A 학습 전 그대로','B 학습 후 그대로','C 학습 후 + 내부 통계만 학습 전으로','D 학습 전 + 내부 통계만 학습 후로']
    artifacts=[]
    for case in (1,3,5):
        images=[];proof=[]
        selected=[f for f in frames if f['case_number']==case]
        for frame in selected:
            source_image=source.parent/frame['image'];assert sha(source_image)==frame['image_sha256']
            with Image.open(source_image) as im:thumb=im.convert('RGB').resize((960,540))
            canvas=Image.new('RGB',(1920,1280),'#14202b');draw=ImageDraw.Draw(canvas);counts=[]
            for n,name in enumerate(names):
                ox=(n%2)*960;oy=(n//2)*640;canvas.paste(thumb,(ox,oy+100))
                row=predictions[name][frame['frame_id']]
                draw.text((ox+10,oy+6),titles[n],font=font,fill='white')
                split='검증' if frame['split']=='validation' else '학습'
                draw.text((ox+10,oy+37),f"{split} {case}번 · 원본 {frame['source_pts']:.3f}초 · 사람 위치",font=small,fill='white')
                draw.text((ox+10,oy+66),'청록: 검수 정답 / 주황: 실제 검출·점수 (0.5 이상)',font=small,fill='#c6d5df')
                sx,sy=960/frame['source_size'][0],540/frame['source_size'][1]
                for box in frame['confirmed_person_boxes']:
                    x1,y1,x2,y2=box['xyxy'];draw.rectangle((ox+x1*sx,oy+100+y1*sy,ox+x2*sx,oy+100+y2*sy),outline='#39ffff',width=2)
                shown=0
                for b,s in zip(row['boxes'],row['person_scores']):
                    if s<.5:continue
                    shown+=1;x1,y1,x2,y2=b
                    xy=(ox+x1*sx,oy+100+y1*sy,ox+x2*sx,oy+100+y2*sy)
                    draw.rectangle(xy,outline='#ffb347',width=3)
                    draw.text((xy[0],max(oy+100,xy[1]-24)),f'{s:.2f}',font=small,fill='#ffb347')
                counts.append(shown)
            images.append(np.asarray(canvas));proof.append(dict(frame_id=frame['frame_id'],source_pts=frame['source_pts'],
                image_sha256=frame['image_sha256'],predicted_boxes=counts,gt_boxes=len(frame['confirmed_person_boxes'])))
        path=output/f'case-{case:02}-four-conditions.mp4';encode(path,images,Fraction(3))
        artifacts.append(dict(case_number=case,split=selected[0]['split'],file=path.name,sha256=sha(path),frames=proof))
    metadata=dict(result_sha256=sha(folder/'result.json'),renderer_sha256=sha(__file__),font_sha256=sha(fontpath),
        conditions=names,frame_count=75,fps=3,width=1920,height=1280,artifacts=artifacts)
    (output/'manifest.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
    blocks=''.join(f'<h2>{"검증" if a["split"]=="validation" else "학습"} 자료 {a["case_number"]}번</h2><video controls preload="metadata" src="{a["file"]}"></video>' for a in artifacts)
    html='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>EXP-0069 과적합·내부 통계 진단</title>
<style>body{font:18px system-ui;background:#14202b;color:#eef3f7;max-width:1100px;margin:32px auto;padding:0 20px}video{width:100%}p{line-height:1.6}</style>
<h1>EXP-0069 과적합·내부 통계 진단</h1><p>학습 전후와 내부 통계 교환의 4조건을 비교합니다. A/B는 원래 모델, C/D는 원인 확인용 조합이며 채택한 모델이 아닙니다. 청록은 검수된 사람 박스, 주황은 실제 검출입니다. 넘기 행동 판정이 아닙니다.</p>'''+blocks+'</html>'
    (output/'index.html').write_text(html)
    print(json.dumps(dict(videos=len(artifacts),frames=75,manifest_sha256=sha(output/'manifest.json'))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--folder',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();render(a.folder,a.output)
