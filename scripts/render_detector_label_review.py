"""CPU-only original/all-annotation review pairs; does not create or correct training truth."""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.render_comparison_validation_errors import encode, sha


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def render(selection_path, output):
    import av
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    selection=read(selection_path)
    plan_path=ROOT/'outputs/model-comparison/exp0066/head-plan-v2/manifest.json'
    plan=read(plan_path)
    windows={w['window_id']:w for w in plan['windows']}
    output.mkdir(parents=True,exist_ok=False)
    font_path=Path('/mnt/c/Windows/Fonts/malgun.ttf')
    font=ImageFont.truetype(str(font_path),22)
    small=ImageFont.truetype(str(font_path),18)
    cases=[]
    names={'wall_over':'넘기','moving':'보행','stand':'서 있기','sit_down_floor':'바닥에 앉기'}
    for n,selected in enumerate(selection['cases'],1):
        w=windows[selected['window_id']]
        if w['split'] not in ('train','validation') or w['source_sha256']!=selected['source_sha256']:
            raise ValueError('Only fixed train/validation candidates allowed')
        if sha(w['source_path'])!=w['source_sha256']:
            raise ValueError('Original source changed')
        annotations=[];bindings={}
        for target in w['targets']:
            p=target['label_path']
            if p in bindings:continue
            if sha(p)!=target['label_sha256']:raise ValueError('Annotation changed')
            bindings[p]=target['label_sha256'];annotations.extend(read(p)['annotations'])
        start=max(0,w['sample_pts'][0]-3);end=w['sample_pts'][-1]+3
        frames=[];meta=[]
        with av.open(w['source_path']) as src:
            stream=src.streams.video[0];stream.codec_context.thread_count=1
            if Fraction(stream.average_rate)!=3 or Fraction(stream.time_base)!=Fraction(w['time_base']):
                raise ValueError('Expected audited native3FPS/timebase')
            src.seek(max(0,int((start-.5)/float(stream.time_base))),stream=stream,backward=True)
            for f in src.decode(stream):
                t=float(f.pts*stream.time_base)
                if t<start-1e-6:continue
                if t>end+1e-6:break
                rgb=f.to_ndarray(format='rgb24');idx=round(t*3)
                if abs(t-idx/3)>1e-6 or list(rgb.shape[1::-1])!=w['source_size']:
                    raise ValueError('Actual source geometry/timing differs')
                boxes={str(o):[dict(actor=a['actor_id'],action=a['class_name'],xyxy=[*a['bbox'][0],*a['bbox'][1]])
                              for a in annotations if a['cur_frame']==idx+o] for o in (0,1)}
                meta.append(dict(source_pts=t,native_pts_tick=f.pts,frame_index=idx,
                                 source_rgb_sha256=hashlib.sha256(rgb.tobytes()).hexdigest(),boxes=boxes))
                im=Image.new('RGB',(1920,600),'#111820')
                preview=Image.fromarray(rgb).resize((960,540))
                im.paste(preview,(0,60));im.paste(preview,(960,60))
                draw=ImageDraw.Draw(im)
                draw.text((12,4),f'원본 {t:.3f}초 · 왼쪽: 원본 / 오른쪽: 파일에 있는 모든 사람 박스',font=font,fill='white')
                draw.text((12,32),'박스가 아예 없는 사람이 있는지 확인 · 조금 어긋난 박스는 별도 · 자동 정답 수정 없음',font=small,fill='#64e6d0')
                sx,sy=960/w['source_size'][0],540/w['source_size'][1]
                for b in boxes['1']:
                    x1,y1,x2,y2=b['xyxy']
                    if not (0<=x1<x2<=w['source_size'][0] and 0<=y1<y2<=w['source_size'][1]):
                        raise ValueError('Review annotation geometry invalid')
                    rect=(960+x1*sx,60+y1*sy,960+x2*sx,60+y2*sy)
                    draw.rectangle(rect,outline='#39ffff',width=3)
                    draw.text((rect[0],max(60,rect[1]-22)),f"사람 {b['actor']} · {names.get(b['action'],b['action'])}",font=small,fill='#39ffff')
                frames.append(np.asarray(im))
        if not frames or any(abs(b['source_pts']-a['source_pts']-1/3)>1e-6 for a,b in zip(meta,meta[1:])):
            raise ValueError('Missing/noncontinuous review frames')
        video=output/f'case-{n:02d}.mp4';poster=output/f'case-{n:02d}.jpg'
        encode(video,frames,Fraction(3));Image.fromarray(frames[len(frames)//2]).save(poster,quality=90)
        cases.append(dict(number=n,window_id=w['window_id'],source_id=w['source_id'],source_sha256=w['source_sha256'],
            split=w['split'],event_group=w['event_group'],source_size=w['source_size'],label_bindings=bindings,
            declared_actions=selected['actions'],video=str(video.resolve()),video_sha256=sha(video),
            poster=str(poster.resolve()),poster_sha256=sha(poster),frames=meta,
            displayed_frame_origin=1,frame_origin_certified=False,all_visible_people_annotated_verified=False))
        print(json.dumps(dict(rendered=n,total=len(selection['cases']))),flush=True)
    result=dict(cases=cases,selection_sha256=sha(selection_path),plan_sha256=sha(plan_path),renderer_sha256=sha(__file__),
        font_sha256=sha(font_path),new_model_inference=0,training_release=False,questions_registered=False,
        interpretation='Candidate review only. Known actors without current labels can be outside the camera; no missing-person truth inferred.')
    (output/'review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--selection',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    args=p.parse_args();render(args.selection,args.output)
