"""Protected school regression review from saved YOLO26 outputs, no inference.

Purposeful first batch, not a representative school-wide accuracy sample.
Every candidate remains unconfirmed; no label or training manifest is exported.
"""
import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.render_yolo_baseline_panels import load_completed, sha

COHORT=ROOT/'outputs/model-comparison/exp0066/cohort-v1/manifest.json'
COHORT_SHA='480b1410c568b9a038c7be6d124f7be1890b3b7375cbed43e87b165346a2aa18'
# Locked from historical failure/control contexts, before any B/C predictions.
SELECTION=[
 (1,'006',124.99153333333334,'원거리 사람 · 과거 누락 관찰'),
 (1,'007',66.,'겹친 사람 · 기준선 출력 공백'),
 (1,'030',90.,'문을 넘는 자세 · 기존 사람 관찰 재사용'),
 (1,'031',40.,'울타리 가림 · 과거 누락 관찰'),
 (1,'028',67.,'넘는 사람 · 기존 동일인 관찰 재사용'),
 (1,'043',68.,'사용자가 지적한 박스 소실 시점'),
 (2,'007',56.,'접근 중 · 기존 검출 유지 비교'),
 (2,'030',84.,'문 앞 여러 사람 · 기존 검출 유지 비교'),
 (2,'031',32.,'기존 검출과 먼 배경 후보 함께 확인'),
 (3,'031',44.,'과거 배경 오검출 의심 위치와 가림 사람'),
 (3,'030',0.,'영상 시작 배경 · 사람 없음은 미확정'),
 (3,'007',0.,'다른 카메라 시작 배경 · 사람 없음은 미확정'),
]


def write(path,value):
    with path.open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')


def select_output(rows,video,seconds):
    choices=[r for r in rows.values() if r['video_id']==video and abs(r['box_pts']-seconds)<1e-7]
    if not choices:raise ValueError('No saved exact native frame: '+video+str(seconds))
    choices.sort(key=lambda r:(r['window']['role']!='fullvideo_regular',r['window']['window_id']))
    chosen=choices[0]
    for r in choices:
        if r['output']!=chosen['output']:
            # Timing measurements may differ for duplicate forwards; predictions may not.
            for k in ('boxes','person_scores','valid_boxes'):
                if r['output'][k]!=chosen['output'][k]:raise ValueError('Duplicate-frame predictions disagree')
    if (chosen['box_frame_index']!=chosen['window']['sample_frame_indices'][8]
            or chosen['box_pts']!=chosen['window']['sample_pts'][8]
            or chosen['output']['actual_input_frames']!=1):
        raise ValueError('Wrong saved box clock')
    return chosen


def iou(a,b):
    inter=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    return inter/((a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter)


def proposals(outputs,fid):
    result=[]
    for model in ('yolo26m','yolo26x','yolo26l'):
        out=outputs[model]['output']
        for index,(box,score,valid) in enumerate(zip(out['boxes'],out['person_scores'],out['valid_boxes'])):
            if not valid or score<.15:continue
            if any(iou(box,b['xyxy'])>=.8 for b in result):continue
            result.append(dict(id=f'{fid}-{model}-{index}',kind='model',
                label=f'{model} 참고 {index+1}',xyxy=box,score=score))
    return result


def prepare(output,review_snapshot):
    import av
    import numpy as np
    from PIL import Image,ImageDraw,ImageFont
    if sha(COHORT)!=COHORT_SHA:raise ValueError('Cohort changed')
    cohort=json.loads(COHORT.read_text());videos={v['video_id']:v for v in cohort['videos']}
    models={};bindings={}
    for model in ('yolo26m','yolo26l','yolo26x'):
        completion=ROOT/f'runtime/model-comparison/exp0066/yolo26-execution-v3/stages/{model}/all45/completion.json'
        name,rows,binding=load_completed(completion,COHORT_SHA);models[name]=rows;bindings[name]=binding
    output.mkdir(parents=True,exist_ok=False)
    for name in ('images','context','previews'):(output/name).mkdir()
    write(output/'selection.json',dict(selection=SELECTION,cohort_sha256=COHORT_SHA,
        prior_review_snapshot_sha256=sha(review_snapshot),training_use=False,threshold_selection_use=False,
        sampling='historical failure/control contexts and fixed start-frame controls; purposeful regression only'))
    frames=[];evidence=[];media={};verified_sources=set()
    font=ImageFont.truetype('/home/jhc7484/.local/share/fonts/sceneguard-portfolio/malgun.ttf',22)
    for batch,number,seconds,reason in SELECTION:
        vid='E01_'+number;v=videos[vid];source=Path(v['source_path'])
        if vid not in verified_sources:
            if sha(source)!=v['source_sha256']:raise ValueError('Raw school video changed')
            verified_sources.add(vid)
        selected={m:select_output(rows,vid,seconds) for m,rows in models.items()}
        reference=selected['yolo26m'];index=reference['box_frame_index']
        if any(r['source_sha256']!=v['source_sha256'] or r['box_frame_index']!=index for r in selected.values()):
            raise ValueError('Cross-model source/frame mismatch')
        clock_path=Path(v['native_pts_binding']['path'])
        if sha(clock_path)!=v['native_pts_binding']['sha256']:raise ValueError('Clock changed')
        clock=json.loads(clock_path.read_text())['clocks'];tb=Fraction(clock['time_base']);tick=clock['native_pts'][index]
        if abs(float(tick*tb)-seconds)>1e-7:raise ValueError('Native PTS mismatch')
        fid=f'school-{number}-frame-{index:06d}'
        path=output/'context'/f'{fid}.mp4';raw_image=None;context_pts=[]
        with av.open(str(source)) as src,av.open(str(path),'w') as dst:
            stream=src.streams.video[0];stream.codec_context.thread_count=1
            src.seek(max(0,int((seconds-1.5)/float(tb))),stream=stream,backward=True)
            enc=dst.add_stream('libx264',rate=Fraction(v['current_source_header']['average_rate']))
            enc.width=960;enc.height=600;enc.pix_fmt='yuv420p';enc.options={'crf':'20','preset':'fast'}
            for decoded in src.decode(stream):
                t=float(decoded.pts*decoded.time_base)
                if t>seconds+1.5+1e-8:break
                if t<max(0,seconds-1.5)-1e-8:continue
                rgb=decoded.to_ndarray(format='rgb24');pic=Image.fromarray(rgb)
                if decoded.pts==tick:
                    raw_image=pic.copy();rgb_sha=hashlib.sha256(rgb.tobytes()).hexdigest()
                context_pts.append(t)
                canvas=Image.new('RGB',(960,600),'#161616');canvas.paste(pic.resize((960,540)),(0,60));d=ImageDraw.Draw(canvas)
                d.text((10,3),f'{vid} 원본 {t:.3f}초 | 검수할 정지화면 {seconds:.3f}초',font=font,fill='white')
                d.text((10,29),'움직임 참고용 원본 · 박스는 정지화면에서만 수정',font=font,fill='white')
                for packet in enc.encode(av.VideoFrame.from_ndarray(np.asarray(canvas),format='rgb24')):dst.mux(packet)
            for packet in enc.encode():dst.mux(packet)
        if raw_image is None:raise ValueError('Exact keyframe not decoded')
        image=output/'images'/f'{fid}.png';raw_image.save(image)
        candidates=proposals(selected,fid)
        # Overview shows saved m at the frozen .5, not combined reference proposals.
        preview=raw_image.copy();d=ImageDraw.Draw(preview)
        for box,score in zip(reference['output']['boxes'],reference['output']['person_scores']):
            if score>=.5:d.rectangle(box,outline='#ff9900',width=3)
        preview_path=output/'previews'/f'{fid}.jpg';preview.resize((960,540)).save(preview_path,quality=92)
        media[fid]=dict(path=str(path.resolve()),sha256=sha(path),kind='video',pts=context_pts)
        media[fid+'-preview']=dict(path=str(preview_path.resolve()),sha256=sha(preview_path),kind='image')
        count=sum(s>=.5 for s in reference['output']['person_scores'])
        frames.append(dict(frame_id=fid,case_number=batch,case_label={1:'1 · 누락 후보 6장',2:'2 · 검출 유지 3장',3:'3 · 배경·오검출 3장'}[batch],
            source_label=vid,review_instruction=reason+' | 저장된 YOLO26m 0.5 이상 박스 '+str(count)+'개. 정답 수가 아닙니다.',
            context_media=fid,source_sha256=v['source_sha256'],source_size=v['source_size'],source_pts=seconds,
            frame_index=index,native_pts_tick=tick,time_base=str(tb),source_rgb_sha256=rgb_sha,
            image_path=str(image.resolve()),image_sha256=sha(image),candidates=candidates,
            split='validation',evaluation_role='protected_school_regression_only',event_group='school-'+v['camera_id'],
            training_release=False,training_eligible=False,threshold_selection_eligible=False,
            person_completeness_verified=False))
        label_path=ROOT/f'data/TL_침입/{vid}.json';label=json.loads(label_path.read_text())
        evidence.append(dict(frame_id=fid,video_id=vid,camera_id=v['camera_id'],source_path=str(source),
            source_sha256=v['source_sha256'],official_label_sha256=sha(label_path),
            official_annotation_keys=list(label['annotations']),official_box_gt_available=False,
            source_frame=index,source_pts=seconds,native_pts_tick=tick,source_rgb_sha256=rgb_sha,
            selection_reason=reason,case_number=batch,outputs=selected,
            yolo26m_display_boxes=count,reviewed_person_count=None,fn=None,fp=None))
        print(json.dumps(dict(frame=fid,candidates=len(candidates),m_at_half=count)),flush=True)
    write(output/'editor-package.json',dict(schema_version=1,experiment_id='EXP-0075',frames=frames,
        review_title='학교 영상 · 학습 전후 비교용 사람 박스 검수',
        evaluation_only=True,training_release=False,media=media,
        cohort_sha256=COHORT_SHA,model_bindings=bindings,
        candidate_policy='saved m/x/l score>=.15, display-only overlap dedup IoU>=.8; no automatic GT adoption',
        no_boxes_means_empty=False))
    write(output/'evidence.json',dict(frames=evidence,all_school_model_inputs_per_model=6219,
        selected_frames=len(frames),selected_sources=len(verified_sources),new_model_forwards=0,
        new_ground_truth_frames=0,training_runs=0,person_recall=None,false_positive_rate=None,
        package_sha256=sha(output/'editor-package.json')))
    print('prepared',len(frames),'unconfirmed school frames')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--review-snapshot',type=Path,required=True)
    a=p.parse_args();prepare(a.output.resolve(),a.review_snapshot.resolve())
