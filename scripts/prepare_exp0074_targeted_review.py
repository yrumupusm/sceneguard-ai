"""Three unresolved P01 frames only, with source-verified local enlargements.

No detector run, no automatic acceptance, no return of removed background boxes.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.evaluate_person_detector_pair import sha


def prepare(output):
    import av
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    repaired_path=ROOT/'outputs/model-comparison/exp0073/box-repairs-v1/R03-repaired-draft.json'
    draft_path=ROOT/'outputs/model-comparison/exp0072/person-drafts-v1/R03-drafts.json'
    repair=json.loads(repaired_path.read_text());draft=json.loads(draft_path.read_text())
    cases=json.loads((ROOT/'outputs/model-comparison/exp0070/data-readiness-v1/split-proposal.json').read_text())['cases']
    case=next(c for c in cases if c['candidate_id']=='P01')
    assert case['reserved_split']=='development' and repair['capture_reservation']=='capture-reservation-01'
    ref=case['source_reference']
    if 'path' in ref: raw=Path(ref['path']).read_bytes()
    else:
        with zipfile.ZipFile(ref['archive_path']) as z:raw=z.read(ref['member'])
    assert hashlib.sha256(raw).hexdigest()==repair['source_sha256']==draft['source_sha256']
    indices={168,175,185}
    rows={f['decoded_index']:f for f in repair['frames'] if f['decoded_index'] in indices}
    original={f['decoded_index']:f for f in draft['frames']}
    output.mkdir(parents=True,exist_ok=False);(output/'images').mkdir()
    font=ImageFont.truetype('/home/jhc7484/.local/share/fonts/sceneguard-portfolio/malgun.ttf',25)
    frames=[];slides=[]
    with av.open(io.BytesIO(raw)) as source:
        stream=source.streams.video[0];stream.codec_context.thread_count=1
        source.seek(int(56/float(stream.time_base)),stream=stream,backward=True)
        for decoded in source.decode(stream):
            t=float(decoded.pts*decoded.time_base);i=round(t*3)
            if i>max(indices):break
            if i not in rows:continue
            row=rows[i];rgb=decoded.to_ndarray(format='rgb24')
            assert abs(t-row['source_pts'])<1e-6 and hashlib.sha256(rgb.tobytes()).hexdigest()==row['source_rgb_sha256']
            fid=f'exp0074-p01-frame-{i:06d}';pic=Image.fromarray(rgb);image=output/'images'/f'{fid}.png';pic.save(image)
            candidates=[];drawn=pic.copy();d=ImageDraw.Draw(drawn)
            for j,b in enumerate(row['boxes'],1):
                score=original[i]['model_proposals']['person_scores'][b['source_proposal_index']]
                candidates.append(dict(id=b['id'],kind='model',label=f'미확정 초안 {j}',xyxy=b['xyxy'],score=score))
                d.rectangle(b['xyxy'],outline='#ff9900',width=2)
                d.text((b['xyxy'][0],max(0,b['xyxy'][1]-25)),str(j),font=font,fill='#ff9900')
            frames.append(dict(frame_id=fid,case_number=1,split='validation',event_group=repair['capture_reservation'],
                source_sha256=repair['source_sha256'],source_size=[1920,1080],source_pts=t,
                native_pts_tick=decoded.pts,frame_index=i,source_rgb_sha256=row['source_rgb_sha256'],
                image_path=str(image.resolve()),image_sha256=sha(image),candidates=candidates,
                training_release=False,complete_person_ground_truth=False))
            canvas=Image.new('RGB',(1920,1080),'#161616');canvas.paste(drawn.resize((1280,720)),(0,90))
            # Pixel-preserving nearest enlargement adds no imagined detail.
            crop=(510,110,625,195);zoom=pic.crop(crop).resize((575,425),Image.Resampling.NEAREST)
            canvas.paste(zoom,(1310,105));canvas.paste(drawn.crop(crop).resize((575,425),Image.Resampling.NEAREST),(1310,570))
            d=ImageDraw.Draw(canvas)
            d.text((15,10),f'P01 원본 {t:.3f}초 | 추가 확인 3장 중 {len(frames)}장 | 기존 배경 오검출 제거 반영',font=font,fill='white')
            d.text((15,48),'주황색은 미확정 초안입니다. 오른쪽은 먼 산책로의 원본 픽셀 확대입니다.',font=font,fill='#ff9900')
            d.text((15,840),'확인할 것: 먼 대상이 사람인지, 한 사람의 중복 박스인지, 빠진 사람이 있는지.',font=font,fill='white')
            d.text((15,885),'잘 보이지 않으면 판단 어려움으로 남깁니다. 기존 승인 좌표5개·배경 위치는 다시 묻지 않습니다.',font=font,fill='white')
            d.text((15,930),'이 영상은 비연속 정지화면3장을 각각4초 표시합니다. 원본 재생 시간과 다릅니다.',font=font,fill='white')
            d.text((1310,535),'같은 확대 영역 + 미확정 박스',font=font,fill='white')
            canvas.save(output/f'{fid}-review.jpg',quality=95);slides.append(canvas)
    assert len(frames)==3
    package=dict(schema_version=1,experiment_id='EXP-0074',training_release=False,
        original_repair_sha256=sha(repaired_path),draft_sha256=sha(draft_path),frames=frames,
        selection='three representative small-person/overlap candidates; not baseline-selected misses',
        frozen_dataset_changed=False)
    (output/'editor-package.json').write_text(json.dumps(package,indent=2,ensure_ascii=False)+'\n')
    video=output/'P01-three-unresolved-frames.mp4'
    with av.open(str(video),'w') as container:
        stream=container.add_stream('libx264',rate=1);stream.width=1920;stream.height=1080;stream.pix_fmt='yuv420p'
        stream.options={'crf':'18','preset':'fast'}
        for slide in slides:
            for _ in range(4):
                for packet in stream.encode(av.VideoFrame.from_ndarray(np.asarray(slide),format='rgb24')):container.mux(packet)
        for packet in stream.encode():container.mux(packet)
    (output/'summary.json').write_text(json.dumps(dict(frames=3,source_indices=sorted(indices),
        package_sha256=sha(output/'editor-package.json'),video_sha256=sha(video),
        approved_boxes_reasked=0,held_night_frame_used=False,new_gt_frames=0,model_runs=0),indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();prepare(a.output.resolve())
