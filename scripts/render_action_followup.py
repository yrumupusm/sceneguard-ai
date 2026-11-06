"""CPU-only review media from immutable EXP-0064 inputs and saved scores.

Boxes are actual stored observations, never interpolated. Scores belong to the
eight-frame window, not the displayed frame or an intrusion completion event.
"""
import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re

from infer_action_regression import letterbox
from audit_action_event_coverage import PLAN_SHA, RESULT_SHA


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def reviewed_coverage(directory, summary_sha, rows_sha):
    paths = [directory/'summary.json', directory/'per-video.json']
    raw = [p.read_bytes() for p in paths]
    if [hashlib.sha256(b).hexdigest() for b in raw] != [summary_sha, rows_sha]:
        raise ValueError('Coverage differs from independently reviewed bytes')
    summary, audits = map(json.loads, raw)
    videos = [r['video_id'] for r in audits]
    events = [e for a in audits for e in a['events']]
    ids = [(e['video_id'],e['reference_id']) for e in events]
    if len(videos)!=45 or len(set(videos))!=45 or len(ids)!=52 or len(set(ids))!=52:
        raise ValueError('Expected unique 45-video / 52-reference inventory')
    if any(e['video_id']!=a['video_id'] for a in audits for e in a['events']):
        raise ValueError('Event video identity differs')
    if dict(Counter(e['diagnostic'] for e in events))!=summary['event_diagnostic_counts']:
        raise ValueError('Event counts differ from reviewed summary')
    return summary,audits


def camera_map(protocol):
    result = {}
    for camera, numbers in re.findall(r'^\|(C\d+)\|[^|]+\|([\d,]+)\|\d+\|', protocol, re.M):
        result.update({'E01_' + number: camera for number in numbers.split(',')})
    if len(result) != 45:
        raise ValueError('Expected the user-provided 45-video camera registry')
    return result


def select_events(audits, cameras):
    """All baseline misses plus one stable representative per camera/diagnosis."""
    events = sorted((e for a in audits for e in a['events']),
                    key=lambda e: (e['video_id'], e['start'], e['reference_id']))
    selected, covered, decisions = [], set(), []
    # Select misses first so they can cover their camera/diagnosis stratum.
    for event in sorted(events, key=lambda e: e['baseline_confirmation_matched'] is not False):
        stratum = (cameras[event['video_id']], event['diagnostic'])
        reason = ('baseline_missed_reference' if event['baseline_confirmation_matched'] is False
                  else 'camera_diagnostic_representative' if stratum not in covered else None)
        if reason:
            selected.append({**event, 'camera_id': stratum[0], 'selection_reason': reason})
            covered.add(stratum)
        decisions.append({**event, 'camera_id': stratum[0], 'selected': reason is not None,
                          'selection_reason': reason or 'stratum_already_represented'})
    return selected, decisions


def choose_window(event, plan, scores):
    overlapping = [s for s in scores if any(event['start'] <= p < event['end'] for p in s['sample_pts'])]
    if overlapping:
        return max(overlapping, key=lambda s: (s['score'], -s['start_target_index'])), None
    partial = []
    for w in plan['missing_windows']:
        first = w['start_target_index']
        observed = [s for s in plan['samples'][first:first + 8] if w['track_id'] in s['observed']]
        within = [s for s in observed if event['start'] <= s['pts'] < event['end']]
        if within:
            partial.append((len(within), len(observed), -first, w))
    return None, max(partial, key=lambda r: r[:3])[-1] if partial else None


def annotation_boxes(label, frame_index, origin):
    return [{'id': str(a['actor_id']), 'class_name': a['class_name'],
             'xyxy': [*a['bbox'][0], *a['bbox'][1]], 'annotation_frame': a['cur_frame']}
            for a in label['annotations'] if a['cur_frame'] == frame_index + origin]


def intersects(a, b):
    return max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3])


def annotation_roi_audit(row, label):
    origins = {}
    for origin in (0, 1):
        frames = []
        for index in row['sample_frame_indices']:
            boxes = annotation_boxes(label, index, origin)
            other = [b for b in boxes if b['id'] != str(row['actor_id']) and intersects(b['xyxy'], row['roi_xyxy'])]
            frames.append({'source_frame_index': index,
                           'target_annotated': any(b['id'] == str(row['actor_id']) for b in boxes),
                           'other_annotated_actors_in_roi': other})
        origins[str(origin)] = frames
    return {'origins': origins, 'absence_of_annotation_is_not_absence_of_person': True,
            'actual_target_behavior': None, 'unannotated_other_climber_in_roi': None}


def decode_exact(path, points):
    import av
    position = 0
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        container.seek(max(0, int((points[0] - 1) / float(stream.time_base))), stream=stream)
        for frame in container.decode(stream):
            t = float(frame.time)
            if t < points[position] - 1e-5:
                continue
            if abs(t - points[position]) > 1e-5:
                raise ValueError(f'Expected native PTS {points[position]}, got {t}')
            yield frame
            position += 1
            if position == len(points):
                break
    if position != len(points):
        raise ValueError('Incomplete exact-PTS decode')


DIAG = {'candidate_time_overlap': '시간대가 겹치는 행동 후보 있음',
        'scored_without_candidate_time_overlap': '입력 있음 · 점수 0.5 미만',
        'partial_observations_only': '일부 관측 있음 · 8시점 입력 부족',
        'no_observed_window_in_reference': '해당 시간대 관측 입력 없음',
        'annotation_disagreement': '공식 서 있기 라벨 · 모델은 넘기 후보'}


def render(item, output, font_path, expected_array=None):
    import av
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(str(font_path), 19)
    small = ImageFont.truetype(str(font_path), 16)
    frames, receipts, input_hashes = [], [], []
    window = item['window']
    points = [s['pts'] for s in item['samples']]
    for decoded, sample in zip(decode_exact(item['source_path'], points), item['samples']):
        array = decoded.to_ndarray(format='rgb24')
        canvas = Image.new('RGB', (1280, 680), 'black')
        original = Image.fromarray(array).resize((960, 540))
        draw = ImageDraw.Draw(original)
        sx, sy = 960 / decoded.width, 540 / decoded.height
        for box in sample['boxes']:
            color = 'red' if box['id'] == item.get('target_id') else '#aaaaaa'
            b = box['xyxy']
            draw.rectangle([b[0]*sx, b[1]*sy, b[2]*sx, b[3]*sy], outline=color, width=3)
            draw.text((b[0]*sx, max(0, b[1]*sy-21)), box['id'] + ' ' + box.get('class_name', ''), font=small, fill=color)
        input_index = None
        if window:
            roi = window['roi_xyxy']
            draw.rectangle([roi[0]*sx, roi[1]*sy, roi[2]*sx, roi[3]*sy], outline='cyan', width=3)
            input_index = next((i for i,p in enumerate(window['sample_pts']) if abs(p-sample['pts']) < 1e-5), None)
        canvas.paste(original, (0, 140))
        d = ImageDraw.Draw(canvas)
        score_text = f"8시점 창의 점수 {window['score']:.6f} (기준 0.5)" if window else '완전한 모델 입력 없음 · 점수 없음'
        d.multiline_text((10, 8), f"{item['title']} | {DIAG[item['diagnostic']]}\n원본 PTS {sample['pts']:.3f}초 | {score_text}\n{item['reference_text']}\n빨강: 선택 대상의 실제 박스 · 회색: 다른 실제 박스 · 청록: 선택 입력 영역\n동일인·행동 의미 미검수 / 넘기 점수는 침입 완료 판정이 아닙니다.", font=font, fill='white', spacing=3)
        d.text((980, 148), '모델 입력 112 × 112', font=font, fill='white')
        if input_index is not None:
            crop = letterbox(array, window['roi_xyxy'])
            if expected_array is not None and not np.array_equal(crop, expected_array[input_index]):
                raise ValueError('Rendered input differs from evaluated prepared pixels')
            digest = hashlib.sha256(crop.tobytes()).hexdigest()
            input_hashes.append({'input_index': input_index, 'pts': sample['pts'], 'rgb_sha256': digest})
            canvas.paste(Image.fromarray(crop).resize((280,280), Image.Resampling.NEAREST), (980,180))
            d.text((980, 478), f'실제 입력 {input_index+1}/8', font=font, fill='cyan')
        else:
            d.multiline_text((980, 210), '현재 시점은\n선택한 8시점 입력 밖' if window else '관측이 부족하여\n입력을 만들지 못함\n\n입력 영역을\n임의로 만들지 않음', font=font, fill='white', spacing=8)
        if window:
            d.multiline_text((980, 526), f"선택 창\n{window['sample_pts'][0]:.3f}–\n{window['sample_pts'][-1]:.3f}초\n\n점수는 창 전체에 해당", font=small, fill='white', spacing=4)
        elif item.get('partial_sample_plan'):
            d.multiline_text((980, 370), '예정 8시점 · 실제 관측\n' + '\n'.join(
                f"{s['pts']:.3f}초 : {'있음' if s['observed'] else '없음'}" for s in item['partial_sample_plan']),
                font=small, fill='white', spacing=4)
        receipts.append({**sample, 'native_pts': decoded.pts, 'time_base': str(decoded.time_base), 'input_index': input_index})
        frames.append(canvas)
    if window and sorted(r['input_index'] for r in input_hashes) != list(range(8)):
        raise ValueError('Exactly eight model input frames must be displayed')
    with av.open(str(output), 'w') as container:
        stream = container.add_stream('libx264', rate=Fraction(3))
        stream.width, stream.height, stream.pix_fmt = 1280,680,'yuv420p'
        stream.options = {'crf':'23','preset':'fast'}
        for frame in frames:
            for packet in stream.encode(av.VideoFrame.from_image(frame)):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    frames[len(frames)//2].save(output.with_suffix('.jpg'), quality=90)
    return {'video_path':str(output.resolve()), 'video_sha256':sha(output),
            'image_path':str(output.with_suffix('.jpg').resolve()), 'image_sha256':sha(output.with_suffix('.jpg')),
            'frame_count':len(frames), 'display_fps':3, 'duration_seconds':len(frames)/3,
            'frame_receipts':receipts, 'input_pixel_sha256':input_hashes,
            'prepared_pixels_equal':True if expected_array is not None else None}


def school_item(event, plan, scores):
    window, partial = choose_window(event, plan, scores)
    partial_samples = plan['samples'][partial['start_target_index']:partial['start_target_index']+8] if partial else []
    focus = window['sample_pts'] if window else [s['pts'] for s in partial_samples] if partial_samples else [event['start'], min(event['end'], event['start']+8)]
    start, end = max(0, focus[0]-3), min(plan['last_pts'], focus[-1]+3)
    target = str(window['track_id']) if window else str(partial['track_id']) if partial else None
    samples = []
    for s in plan['samples']:
        if start <= s['pts'] <= end:
            boxes = [{'id':str(track), 'xyxy':[b[0]*plan['width'],b[1]*plan['height'],b[2]*plan['width'],b[3]*plan['height']]}
                     for track,b in s['observed'].items()]
            samples.append({'pts':s['pts'], 'source_frame_index':s['frame_index'], 'boxes':boxes})
    return {'kind':'school_reference','title':f"{event['video_id']} · {event['camera_id']} · {event['reference_id']}",
            'diagnostic':event['diagnostic'], 'source_path':plan['source_path'], 'source_sha256':plan['source_sha256'],
            'target_id':target, 'window':window, 'partial_window':partial, 'samples':samples,
            'partial_sample_plan':[{'pts':s['pts'],'observed':target in s['observed']} for s in partial_samples],
            'event':event, 'reference_text':f"공식 시간 참조 {event['start']:.3f}–{event['end']:.3f}초 · 기존 확인 {'있음' if event['baseline_confirmation_matched'] else '누락'}"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for arg in ('coverage','plan','inference-result','clip-manifest','test-scores','prepared','output'):
        p.add_argument('--'+arg, type=Path, required=True)
    p.add_argument('--coverage-summary-sha256',required=True)
    p.add_argument('--coverage-per-video-sha256',required=True)
    p.add_argument('--camera-protocol',type=Path,default=Path('docs/experiments/MVP-0005-protocol.md'))
    p.add_argument('--font',type=Path,default=Path('/mnt/c/Windows/Fonts/malgun.ttf'))
    a=p.parse_args()
    if a.output.exists(): raise ValueError('Use a fresh output directory')
    summary,audits = reviewed_coverage(a.coverage,a.coverage_summary_sha256,a.coverage_per_video_sha256)
    manifest = read(a.plan)
    if sha(a.plan)!=PLAN_SHA or sha(a.inference_result)!=RESULT_SHA:
        raise ValueError('Frozen EXP-0064 plan/result changed')
    inputs = (a.coverage/'summary.json',a.coverage/'per-video.json',a.plan,a.inference_result,a.clip_manifest,a.test_scores,a.prepared,a.camera_protocol,a.font)
    input_receipts = {str(path.absolute()):sha(path) for path in inputs}
    renderer_sha = sha(__file__)
    if summary['official_reference_events'] != 52 or summary['videos'] != 45:
        raise ValueError('Full diagnostic result required')
    if summary['input_sha256'].get(str(a.plan.absolute())) != sha(a.plan):
        raise ValueError('Plan differs from diagnosed input')
    if summary['input_sha256'].get(str(a.inference_result.absolute())) != sha(a.inference_result):
        raise ValueError('Inference result differs from diagnosed input')
    for path, expected in ((a.clip_manifest,'72912fab027a068d0e6043f328d86a2c7d15a239afa751d126984c5c10498931'),
                           (a.test_scores,'bf9afead01f4c89b0f388e2fd86051058d02ba6d3e684c17ee81fdf93543dc70'),
                           (a.prepared,'9d8d05f20da34a797a0619c066e9142df3ad15d8aafb6b1f991290a83631f1b4')):
        if sha(path) != expected: raise ValueError('Frozen EXP-0064 failure input changed')
    selected, decisions = select_events(audits, camera_map(a.camera_protocol.read_text()))
    plans = {r['video_id']:r for r in manifest['videos']}
    items=[]
    for event in selected:
        entry=plans[event['video_id']]
        if sha(entry['path']) != entry['sha256']: raise ValueError('Plan changed')
        score_path=a.inference_result.parent/event['video_id']/'window-scores.jsonl'
        if summary['input_sha256'].get(str(score_path.absolute())) != sha(score_path): raise ValueError('Scores changed')
        scores=[json.loads(line) for line in score_path.read_text().splitlines()]
        items.append(school_item(event,read(entry['path']),scores))
    clips={r['clip_id']:r for r in read(a.clip_manifest)['clips']}
    prepared=read(a.prepared)['clips']
    for score in read(a.test_scores):
        if score['label'] != 0 or score['score'] < .5: continue
        row=clips[score['clip_id']]
        if row['split']!='test' or row['evaluation_cohort']!='heldout_place': raise ValueError('Unexpected failure cohort')
        label=read(row['label_path'])
        if sha(row['label_path'])!=row['label_sha256']: raise ValueError('Label changed')
        samples=[{'pts':i/3,'source_frame_index':i,'boxes':annotation_boxes(label,i,1)}
                 for i in range(max(0,row['sample_frame_indices'][0]-9),min(label['info']['frame'],row['sample_frame_indices'][-1]+10))]
        items.append({'kind':'heldout_annotation_disagreement','title':f"별도 장소 정상 라벨 · actor {row['actor_id']} · {row['clip_id'][-8:]}",
                      'diagnostic':'annotation_disagreement','source_path':row['source_path'],'source_sha256':row['source_sha256'],
                      'target_id':str(row['actor_id']),'window':{**row,**score},'samples':samples,
                      'reference_text':'공식 서 있기 라벨 / 박스는 기존 검수의 1번 시작 해석 / 행동 의미는 새 검수 필요',
                      'annotation_roi_audit':annotation_roi_audit(row,label), 'prepared':prepared[row['clip_id']],
                      'label_path':row['label_path'],'label_sha256':row['label_sha256'], 'display_annotation_origin':1})
    a.output.mkdir(parents=True)
    results=[];verified_sources={}
    for number,item in enumerate(items):
        source=item['source_path']
        if source not in verified_sources: verified_sources[source]=sha(source)
        if verified_sources[source]!=item['source_sha256']: raise ValueError('Selected source changed')
        expected=None
        if 'prepared' in item:
            import numpy as np
            if sha(item['prepared']['path']) != item['prepared']['sha256']: raise ValueError('Prepared input changed')
            expected=np.load(item['prepared']['path'],allow_pickle=False)
        media=render(item,a.output/f'{number:02d}-{item["kind"]}.mp4',a.font,expected)
        results.append({**item,**media})
        print(json.dumps({'rendered':number+1,'total':len(items),'title':item['title']},ensure_ascii=False),flush=True)
    for path,digest in input_receipts.items():
        if sha(path)!=digest: raise ValueError('Input changed during rendering')
    if sha(__file__)!=renderer_sha: raise ValueError('Renderer changed during execution')
    out={'experiment_id':'EXP-0065','status':'rendered_semantic_review_pending','selection_policy':'all_baseline_misses_plus_first_per_camera_diagnostic',
         'selection_decisions':decisions,'samples':results,'selected_source_sha256':verified_sources,
         'input_sha256':input_receipts,
         'script_sha256':renderer_sha,'human_semantic_verification':False,'action_true_positives':None,'intrusion_improvement':None}
    (a.output/'review-manifest.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


if __name__=='__main__': main()
