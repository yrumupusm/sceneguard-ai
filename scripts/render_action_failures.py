"""Render annotation-reference action errors from an immutable evaluated manifest.

These are model/annotation disagreements, not automatically human-confirmed errors.
No detector, tracker, model inference, training or truth edits are performed.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def select_failures(manifest, scores, maximum_each=4):
    test={r['clip_id']:r for r in manifest['clips'] if r['split']=='test'}
    found={}
    for score in scores:
        key=score['clip_id']
        if key in found or key not in test or score['label']!=test[key]['label']:
            raise ValueError('Score ids/labels differ from frozen test clips')
        if not math.isfinite(score['score']) or not 0<=score['score']<=1:
            raise ValueError('Invalid action score')
        found[key]=score
    if set(found)!=set(test):raise ValueError('Incomplete test evaluation')
    by_kind={'false_positive':[],'false_negative':[]}
    for key,score in found.items():
        label=score['label'];prediction=int(score['score']>=.5)
        if label!=prediction:
            kind='false_positive' if prediction else 'false_negative'
            by_kind[kind].append({**test[key],**score,'reference_disagreement':kind})
    chosen=[]
    for kind,items in by_kind.items():
        items.sort(key=lambda r:((-r['score'] if kind=='false_positive' else r['score']),r['clip_id']))
        chosen.extend(items[:maximum_each])
    return chosen, {kind:len(items) for kind,items in by_kind.items()}


def render(row, output, font_path):
    import av
    from PIL import Image,ImageDraw,ImageFont
    from fractions import Fraction
    if sha(row['source_path'])!=row['source_sha256']:raise ValueError('Source changed')
    targets=row['sample_pts'];images=[];native=[]
    font=ImageFont.truetype(str(font_path),18)
    classes={'wall_over':'넘기','moving':'걷기','stand':'서 있기·대기',
             'sit_down_bench':'벤치에 앉기','sit_down_floor':'바닥에 앉기'}
    prediction='넘기' if row['score']>=.5 else '넘기 아님'
    reference=classes.get(row.get('action_class'),'넘기' if row['label'] else '넘기 아님')
    with av.open(row['source_path']) as source:
        stream=source.streams.video[0]
        source.seek(max(0,int((targets[0]-1)/float(stream.time_base))),stream=stream)
        for frame in source.decode(stream):
            t=float(frame.time)
            if t<targets[len(images)]-1e-5:continue
            if abs(t-targets[len(images)])>1e-5:raise ValueError('Native PTS mismatch')
            im=frame.to_image().resize((960,540));draw=ImageDraw.Draw(im)
            x1,y1,x2,y2=row['roi_xyxy'];sx=960/frame.width;sy=540/frame.height
            draw.rectangle([x1*sx,y1*sy,x2*sx,y2*sy],outline='cyan',width=3)
            canvas=Image.new('RGB',(960,630),'black');canvas.paste(im,(0,90));d=ImageDraw.Draw(canvas)
            d.multiline_text((10,6),f"모델: {prediction} (넘기 점수 {row['score']:.3f})  |  공식 라벨: {reference}\n원본 영상 시각: {t:.3f}초 · 청록색 테두리는 모델 입력 범위\n실제 행동 검수 전입니다. 넘기 점수는 침입 완료 판정이 아닙니다.",font=font,spacing=5,fill='white')
            images.append(canvas);native.append({'native_pts':frame.pts,'time_base':str(frame.time_base),'seconds':t})
            if len(images)==len(targets):break
    if len(images)!=len(targets):raise ValueError('Incomplete clip decode')
    with av.open(str(output),'w') as result:
        stream=result.add_stream('libx264',rate=Fraction(3));stream.width=960;stream.height=630;stream.pix_fmt='yuv420p';stream.options={'crf':'23','preset':'fast'}
        for im in images:
            for packet in stream.encode(av.VideoFrame.from_image(im)):result.mux(packet)
        for packet in stream.encode():result.mux(packet)
    images[len(images)//2].save(output.with_suffix('.jpg'),quality=90)
    return {'video_path':str(output.resolve()),'video_sha256':sha(output),'image_path':str(output.with_suffix('.jpg').resolve()),'image_sha256':sha(output.with_suffix('.jpg')),'native_frames':native}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('manifest','scores','model_result','output'):p.add_argument('--'+key.replace('_','-'),type=Path,required=True)
    p.add_argument('--model-contract',type=Path,required=True)
    p.add_argument('--font',type=Path,default=Path('/mnt/c/Windows/Fonts/malgun.ttf'))
    p.add_argument('--maximum-each',type=int,default=4)
    a=p.parse_args()
    if not 0<=a.maximum_each<=8:raise ValueError('Bounded representative count required')
    manifest=json.loads(a.manifest.read_text());scores=json.loads(a.scores.read_text());result=json.loads(a.model_result.read_text())
    contract=json.loads(a.model_contract.read_text())
    if contract.get('manifest_sha256')!=sha(a.manifest) or contract.get('mode')!='train':
        raise ValueError('Training contract does not bind this manifest')
    if result.get('status')!='trained' or not result.get('weights_sha256'):
        raise ValueError('Completed training result required')
    if not (a.model_result.parent.resolve()==a.model_contract.parent.resolve()==a.scores.parent.resolve()):
        raise ValueError('Result, scores and contract must belong to the same training output')
    if sha(a.model_result.parent/'best.pt')!=result['weights_sha256']:
        raise ValueError('Selected checkpoint differs from completed result')
    selected,counts=select_failures(manifest,scores,a.maximum_each)
    a.output.mkdir(parents=True,exist_ok=False);records=[]
    for i,row in enumerate(selected):
        records.append({**{k:row.get(k) for k in ('clip_id','source_id','source_sha256','actor_id','event_group','evaluation_cohort','label','score','reference_disagreement')},**render(row,a.output/f'{i:02d}-{row["reference_disagreement"]}.mp4',a.font)})
    out={'manifest_sha256':sha(a.manifest),'scores_sha256':sha(a.scores),'model_result_sha256':sha(a.model_result),'model_contract_sha256':sha(a.model_contract),'weights_sha256':result['weights_sha256'],'selection':f'up_to{a.maximum_each}_each_sorted_wrong_confidence_then_clip_id','counts':counts,'samples':records,'human_semantic_verification':False,'detector_failure_evaluation':'not_applicable_annotation_roi','intrusion_completion_accuracy':None}
    out['font_sha256']=sha(a.font)
    (a.output/'failure-manifest.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'reference_disagreements':counts,'rendered_samples':len(records)}))


if __name__=='__main__':main()
