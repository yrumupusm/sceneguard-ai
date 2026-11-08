"""CPU-only source inspection for EXP0070, without detection or label release."""
import argparse
import hashlib
import html
import io
import json
from pathlib import Path
import zipfile

import av
from PIL import Image, ImageDraw

from audit_person_data_readiness import AUG, OLD, ROOT, read, rows, save, sha
from prepare_action_augmentation import fingerprint_bytes, suspicious_content


def get_bytes(ref):
    if 'path' in ref:
        return Path(ref['path']).read_bytes()
    with zipfile.ZipFile(ref['archive_path']) as z:
        return z.read(ref['member'])


def main(folder):
    plan = read(folder / 'candidate-plan-before-decode.json')
    media = folder / 'media'; media.mkdir(exist_ok=False)
    protected = rows(AUG / 'protected-content-fingerprints.jsonl')
    assert len(protected) == 341 and all('fingerprints' in r for r in protected)
    old = rows(OLD / 'data-audit/manifest.jsonl') + rows(OLD / 'normal-audit-v1/manifest.jsonl')
    old_splits = {r['source_id']: r['split'] for r in read(OLD / 'combined-split-v3/split-manifest.json')['assignments']}
    old_hashes = {}
    for r in old:
        old_hashes.setdefault(r['source_sha256'], set()).add(old_splits[r['source_id']])
    protected_hashes = {r['sha256'] for r in read(OLD / 'baseline/attempt-002/baseline-lock.json')['regression_only_videos']}
    results = []; cards = []; html_cards = []
    for r in plan['cases']:
        cid = r['candidate_id']; raw = get_bytes(r['resolved']['source_reference'])
        actual_sha = hashlib.sha256(raw).hexdigest()
        if r['source_sha256'] and actual_sha != r['source_sha256']:
            raise ValueError('Source hash changed: '+cid)
        labelraw = get_bytes(r['resolved']['label_reference'])
        assert hashlib.sha256(labelraw).hexdigest() == r['label_sha256']
        labels = json.loads(labelraw)
        with av.open(io.BytesIO(raw)) as source:
            s = source.streams.video[0]
            s.codec_context.thread_count = 1
            props = dict(actual_fps=str(s.average_rate), width=s.width, height=s.height,
                         time_base=str(s.time_base), start_pts=s.start_time,
                         duration_seconds=float(s.duration*s.time_base))
            assert float(s.average_rate) == r['fps'] == 3
            assert [s.width,s.height] == [r['width'],r['height']]
            assert s.start_time == 0
            shots = []; window_results = []
            for wi, window in enumerate(r['review_windows']):
                start,end = window['start_seconds'],window['end_seconds']
                source.seek(max(0,int(start/float(s.time_base))), stream=s, backward=True)
                clip_path = media/f'{cid}-w{wi+1}.mp4'
                encoded = av.open(str(clip_path), 'w')
                stream = encoded.add_stream('libx264', rate=3)
                stream.width=960;stream.height=540;stream.pix_fmt='yuv420p'
                stream.options={'crf':'22','preset':'fast','threads':'1'}
                pts=[]; images=[]
                for frame in source.decode(s):
                    t=float(frame.pts*frame.time_base)
                    if t+1e-6 < start: continue
                    if t > end+1e-6: break
                    im=frame.to_image(); images.append((t,im.copy()));pts.append(t)
                    # Raw source image with original PTS; no predicted boxes.
                    pic=im.resize((960,540));ImageDraw.Draw(pic).text((10,10),f'{cid} ORIGINAL PTS {t:.3f}s - UNREVIEWED',fill='yellow',stroke_width=1,stroke_fill='black')
                    vf=av.VideoFrame.from_image(pic)
                    for packet in stream.encode(vf):encoded.mux(packet)
                for packet in stream.encode():encoded.mux(packet)
                encoded.close()
                assert images and all(abs(b-a-1/3)<1e-5 for a,b in zip(pts,pts[1:]))
                anchors=[images[0],images[len(images)//2],images[-1]]
                for t, im in anchors:
                    thumb=im.resize((480,270));draw=ImageDraw.Draw(thumb)
                    draw.rectangle((0,0,480,24),fill='black');draw.text((5,5),f'{cid} {window["kind"]} PTS={t:.3f}',fill='white')
                    shots.append(thumb)
                # Persist one full-resolution original and label-only draft.
                t, im = anchors[1]
                im.save(media/f'{cid}-w{wi+1}-original.jpg',quality=95)
                draft=im.copy();draw=ImageDraw.Draw(draft)
                index=round(t*3); drawn=[]
                for a in labels.get('annotations',[]):
                    if a.get('cur_frame')==index+1:
                        (x1,y1),(x2,y2)=a['bbox']
                        if x2>x1 and y2>y1:
                            draw.rectangle((x1,y1,x2,y2),outline='yellow',width=3)
                            draw.text((x1,max(30,y1-15)),f'{a.get("actor_id")} {a.get("class_name")}',fill='yellow')
                            drawn.append(a)
                draw.rectangle((0,0,im.width,28),fill='black')
                draw.text((5,8),f'{cid} PTS={t:.3f} ORIGINAL ANNOTATIONS ONLY; origin=1 UNVERIFIED; not complete person labels',fill='yellow')
                draft.save(media/f'{cid}-w{wi+1}-label-draft.jpg',quality=95)
                window_results.append(dict(**window,actual_pts=pts,frames=len(pts),
                    video=str(clip_path.relative_to(folder)),sha256=sha(clip_path),
                    displayed_annotation_origin=1,frame_origin_certified=False,
                    center_actual_pts=t,center_annotation_count=len(drawn),
                    no_boxes_is_not_background=True))
            sheet=Image.new('RGB',(1440,540))
            for j,im in enumerate(shots):sheet.paste(im,((j%3)*480,(j//3)*270))
            sheet.save(media/f'{cid}-contact.jpg',quality=92)
            # Two representative original frames per case for bounded visual audit.
            card=Image.new('RGB',(960,300),'black');card.paste(shots[1],(0,30));card.paste(shots[4],(480,30))
            ImageDraw.Draw(card).text((5,7),f'{cid} {r["proposal_split"]} {r["original_filename"]}',fill='white');cards.append(card)
        prints=fingerprint_bytes(raw)
        cross_old=old_hashes.get(actual_sha,set())
        allowed_old='validation' if r['proposal_split']=='development' else r['proposal_split']
        exact_conflict=actual_sha in protected_hashes or bool(cross_old-{allowed_old})
        suspects=[p['source_id'] for p in protected if suspicious_content(prints,p['fingerprints'])]
        result=dict(candidate_id=cid,source_id=r['source_id'],group_id=r['group_id'],
            proposed_split=r['proposal_split'],source_sha256=actual_sha,
            source_size_bytes=len(raw),actual_video=props,windows=window_results,
            fingerprints=prints,exact_protected_or_other_split_match=exact_conflict,
            protected_content_suspects=suspects,training_eligible=False)
        results.append(result)
        save(folder/f'{cid}-source-check.json',result)
        print(json.dumps({'candidate':cid,'frames':sum(w['frames'] for w in window_results),'protected_content_suspects':len(suspects)}),flush=True)
        links=' '.join(f'<a href="media/{cid}-w{i}-label-draft.jpg">라벨 초안 {i}</a>' for i in (1,2))
        html_cards.append(f'<article><h2>{cid} · {html.escape(r["proposal_split"])} · {html.escape(r["original_filename"])}</h2><p>{html.escape(r["location"])} / {html.escape(r["group_id"])}</p><p>원본 영상입니다. 모든 사람의 박스·행동·빈 배경은 아직 검수되지 않았습니다. 라벨 초안은 원래 라벨만 표시하며 누락된 사람은 추가해야 합니다.</p><video controls preload="none" src="media/{cid}-w1.mp4"></video><video controls preload="none" src="media/{cid}-w2.mp4"></video><p>{links}</p><a href="media/{cid}-contact.jpg">원본 시각별 모음</a></article>')
    overlaps=[];hold_groups=set()
    for i,a in enumerate(results):
        if a['exact_protected_or_other_split_match'] or a['protected_content_suspects']:
            hold_groups.add(a['group_id'])
        for b in results[i+1:]:
            if a['source_sha256']==b['source_sha256'] or suspicious_content(a['fingerprints'],b['fingerprints']):
                overlaps.append(dict(a=a['candidate_id'],b=b['candidate_id'],same_proposed_split=a['proposed_split']==b['proposed_split'],same_group=a['group_id']==b['group_id']))
                if a['group_id']!=b['group_id']:
                    hold_groups.update((a['group_id'],b['group_id']))
    for r in results:
        r['status']='hold_content_similarity_review' if r['group_id'] in hold_groups else 'bounded_source_checks_passed_labels_and_capture_review_pending'
    save(folder/'source-checks.json',dict(results=results,candidate_content_suspects=overlaps,held_groups=sorted(hold_groups),
        protected_fingerprint_binding=dict(path=str(AUG/'protected-content-fingerprints.jsonl'),sha256=sha(AUG/'protected-content-fingerprints.jsonl')),
        limitation='Five relative-time fingerprints cannot prove absence of shifted/cropped/partial copies. Similar static backgrounds can be false matches. No automatic release.',
        gpu_inference=0,training=0))
    for start in range(0,len(cards),5):
        sheet=Image.new('RGB',(960,300*len(cards[start:start+5])),'black')
        for j,card in enumerate(cards[start:start+5]):sheet.paste(card,(0,j*300))
        sheet.save(media/f'overview-{start//5+1:02d}.jpg',quality=93)
    (folder/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>EXP-0070 보강 후보</title><style>body{font-family:sans-serif;margin:24px;background:#161616;color:#eee}video{width:48%;}article{border-bottom:1px solid #777;padding:20px 0}a{color:#9dd5ff}</style><h1>데이터 보강 후보 — 검수 전 / 학습 불가</h1><p>왼쪽: 라벨 기반 선정 구간. 오른쪽: 시작 0–8초의 보행·대기·빈 배경 탐색. 박스 없음은 사람이 없다는 뜻이 아닙니다. 새 시험은 모델 선택에 사용하지 않습니다.</p>'+''.join(html_cards))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--folder',type=Path,required=True)
    main(p.parse_args().folder)
