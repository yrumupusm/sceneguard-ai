"""Render existing detector evidence on seven previously verified native keyframes."""
import argparse
import hashlib
import html
import json
import math
import sqlite3
from pathlib import Path

YOLO = ('yolo26m', 'yolo26l', 'yolo26x')
OTHER = ('FCOS', 'evad_vitb_vmaev2', 'evad_vitl', 'stmixer_vitb_vmaev2')
THRESHOLDS = dict(zip(OTHER + YOLO, (.5, .7, .7, .6, .5, .5, .5)))
REVIEWED_COMPARISON_SHA = 'ad7016f934b97316a0616f0a0668b43c86df4d9ac276f3f378674a26effa629c'
QUEUE = Path('/home/jhc7484/dev/sceneguard-orca-lab/runtime/orca-lab/gpu-queue')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''): h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def checked_file(binding):
    path = Path(binding['path'])
    if sha(path) != binding['sha256']: raise ValueError('Evidence hash differs')
    return path


def check_receipt(receipt, result, result_path, completion):
    if (receipt['execution_status'] != 'succeeded' or receipt.get('synthetic') is not False
            or receipt['attempt_id'] != completion['attempt_id']
            or receipt['result_sha256'] != completion['result']['sha256']
            or Path(receipt['result_path']).resolve() != result_path.resolve().parent
            or receipt['registration']['command'] != 'model-compare'
            or receipt['registration']['job_id'] != completion['job_id']
            or any(result[k] != completion[k] or result[k] != receipt['registration'][k]
                   for k in ('source_hash', 'input_hash', 'code_sha'))):
        raise ValueError('Successful canonical receipt correspondence differs')


def check_queue(receipt_path, receipt, result):
    canonical_path = QUEUE/'attempts'/result['queue_attempt']/'manifest.json'
    if receipt_path.resolve() != canonical_path.resolve(): raise ValueError('Noncanonical receipt path')
    with sqlite3.connect('file:'+str(QUEUE/'queue.sqlite3')+'?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        row = db.execute('SELECT j.*,a.status AS attempt_status,a.result_manifest FROM jobs j '
                         'JOIN attempts a USING(job_id) WHERE a.attempt_id=?', (result['queue_attempt'],)).fetchone()
    keys = ('command','job_id','run_id','task_id','dispatch_id','owner','code_sha','source_hash','input_hash','config_hash')
    if (row is None or row['status'] != 'succeeded' or row['attempt_status'] != 'succeeded'
            or row['result_manifest'] != str(canonical_path)
            or any(receipt['registration'].get(k) != row[k] for k in keys)):
        raise ValueError('Successful canonical queue correspondence differs')
    config = json.loads(row['config_json']); spec = config['files']['model_spec']
    if (config['model_id'] != result['model_id'] or config['stage'] != result['stage']
            or spec['sha256'] != result['model_spec_sha256']
            or config['files']['cohort']['sha256'] != result['cohort_sha256']):
        raise ValueError('Executed model/input configuration differs')
    checked_file(spec)


def load_completed(completion_path, cohort_sha):
    completion = read(completion_path)
    if (completion['status'] != 'succeeded' or completion['stage'] != 'all45'
            or completion['model_id'] not in YOLO
            or completion['process_states'] != dict(child='exited', supervisor='exited')):
        raise ValueError('Completed all45 detector stage required')
    result_path = checked_file(completion['result']); result = read(result_path)
    receipt_path = checked_file(completion['receipt']); receipt = read(receipt_path)
    if (result['status'] != 'inference_complete' or result['stage'] != 'all45'
            or result['model_id'] != completion['model_id']
            or result['cohort_sha256'] != cohort_sha
            or result['scored_windows'] != 6219 or result['decoded_native_frames'] != 184300
            or result['queue_attempt'] != completion['attempt_id']
            or receipt['attempt_id'] != completion['attempt_id']
            or receipt['result_sha256'] != completion['result']['sha256']):
        raise ValueError('Canonical result/receipt/coverage differs')
    check_receipt(receipt, result, result_path, completion)
    check_queue(receipt_path, receipt, result)
    path = result_path.parent / 'windows.jsonl'
    if sha(path) != result['windows_sha256'] or result['windows_sha256'] != completion['windows_sha256']:
        raise ValueError('Saved outputs changed')
    rows = {}
    for line in path.open():
        row = json.loads(line); key = row['window']['window_id']
        if key in rows: raise ValueError('Duplicate output')
        rows[key] = row
    if len(rows) != 6219: raise ValueError('Incomplete saved output')
    return completion['model_id'], rows, dict(path=str(completion_path.resolve()), sha256=sha(completion_path))


def checked_case_output(case, row):
    window = case['window']; out = row['output']
    if (row['window'] != window or row['video_id'] != case['video_id']
            or row['box_frame_index'] != window['sample_frame_indices'][8]
            or row['box_pts'] != window['sample_pts'][8]
            or row['box_pts'] != case['media']['keyframe_pts']
            or row['model_input_available_after_pts'] != row['box_pts']
            or out['actual_input_frames'] != 1 or out['input_frame_index'] != 8
            or out['person_threshold'] != .5 or out['action_scores'] is not None
            or out['climbing_score'] is not None):
        raise ValueError('Single-frame evidence or timing differs')
    return out


def render(comparison_path, completion_paths, destination):
    from PIL import Image, ImageDraw, ImageFont
    if sha(comparison_path) != REVIEWED_COMPARISON_SHA: raise ValueError('Previously verified comparison changed')
    comparison = read(comparison_path)
    if len(comparison['cases']) != 7: raise ValueError('Use the seven verified native diagnostic cases')
    models = {}; bindings = {}
    for path in completion_paths:
        name, rows, binding = load_completed(path, comparison['cohort_sha256'])
        if name in models: raise ValueError('Duplicate model')
        models[name] = rows; bindings[name] = binding
    if set(models) != set(YOLO): raise ValueError('All three completed detector baselines required')
    if any(comparison['default_display_thresholds'][m] != THRESHOLDS[m] for m in OTHER):
        raise ValueError('Existing display thresholds changed')
    destination.mkdir(parents=True, exist_ok=False)
    font_path = Path('/home/jhc7484/.local/share/fonts/sceneguard-portfolio/malgun.ttf')
    font = ImageFont.truetype(str(font_path), 13)
    cases = []; sections = []
    labels = dict(FCOS='기존 FCOS', evad_vitb_vmaev2='EVAD-B', evad_vitl='EVAD-L',
                  stmixer_vitb_vmaev2='STMixer', yolo26m='YOLO26m', yolo26l='YOLO26l', yolo26x='YOLO26x')
    for case in comparison['cases']:
        media = case['media']; key = case['window_id']
        source_path = comparison_path.parent / key / media['native_keyframe']
        if sha(source_path) != media['native_keyframe_sha256']: raise ValueError('Native keyframe changed')
        source = Image.open(source_path).convert('RGB')
        if list(source.size) != media['source_size']: raise ValueError('Native dimensions differ')
        if media['keyframe_pts'] != case['window']['sample_pts'][8]: raise ValueError('Keyframe time differs')
        size = (960, round(source.height * 960 / source.width)); sx = size[0]/source.width; sy = size[1]/source.height
        outputs = {m: case['outputs'][m] for m in OTHER}
        outputs.update({m: checked_case_output(case, models[m][key]) for m in YOLO})
        entries = []; cards = []
        for name in ('original',) + OTHER + YOLO:
            picture = source.resize(size); draw = ImageDraw.Draw(picture); shown = []
            if name != 'original':
                out = outputs[name]; boxes = out['boxes']; scores = out['person_scores']
                valid = out.get('valid_boxes', [True]*len(boxes))
                if not len(boxes) == len(scores) == len(valid): raise ValueError('Box and score lengths differ')
                for index, (box, score, ok) in enumerate(zip(boxes, scores, valid)):
                    if not math.isfinite(score) or not 0 <= score <= 1: raise ValueError('Invalid person score')
                    if not ok or score < THRESHOLDS[name]: continue
                    if len(box) != 4 or not all(math.isfinite(x) for x in box): raise ValueError('Invalid box')
                    x1,y1,x2,y2 = box
                    if not 0 <= x1 < x2 <= source.width or not 0 <= y1 < y2 <= source.height:
                        raise ValueError('Original-pixel box geometry differs')
                    coords = (x1*sx,y1*sy,x2*sx,y2*sy)
                    draw.rectangle(coords, outline='#21e6ca', width=2)
                    text = f'q{index} {score:.3f}'; pos=(coords[0],max(0,coords[1]-16))
                    draw.rectangle(draw.textbbox(pos,text,font=font),fill='#101722');draw.text(pos,text,font=font,fill='white')
                    shown.append(dict(query_index=index,box=box,person_score=score))
            filename=f'{key}-{name}.jpg';picture.save(destination/filename,quality=95)
            title='원본' if name=='original' else f'{labels[name]} · 사람 기준 {THRESHOLDS[name]:.2f} · 박스 {len(shown)}개'
            timing=('단일 원본 프레임' if name in YOLO or name in ('FCOS','original') else
                    f"16프레임 입력 {case['window']['sample_pts'][0]:.3f}–{media['last_input_pts']:.3f}초")
            cards.append(f'<figure><figcaption>{html.escape(title)}<br>{html.escape(timing)}</figcaption><a href="{filename}"><img loading="lazy" src="{filename}"></a></figure>')
            entries.append(dict(model=name,path=filename,sha256=sha(destination/filename),shown=shown,
                                threshold=THRESHOLDS.get(name),source_pts=media['keyframe_pts']))
        cases.append(dict(window_id=key,video_id=case['video_id'],source_image_sha256=sha(source_path),
                          source_size=media['source_size'],display_size=size,panels=entries,
                          same_person_verified=False,person_recall=None))
        sections.append(f'<section><h2>{html.escape(key)} · 원본 {media["keyframe_pts"]:.6f}초</h2><div class="grid">'+''.join(cards)+'</div></section>')
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>EXP-0066 학습 전 검출 비교</title>
<style>body{background:#101722;color:#eee;font:16px sans-serif;margin:24px}a{color:#8ddfff}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}figure{margin:0}img{width:100%}figcaption{padding:8px}section{margin-top:32px}@media(max-width:850px){.grid{grid-template-columns:1fr}}</style>
<h1>학습 전 사람 검출 · 같은 시점 비교</h1><p>기존 진단7장면의 저장된 박스입니다. 추가 학습 후 결과가 아닙니다. 영상 모델은 앞뒤16프레임, YOLO는 표시 시점1프레임을 사용했습니다.</p>
<p>모델별 표시 기준이 다르므로 박스 수로 성능 순위를 매기지 않습니다. q는 해당 시점 후보 번호이며 추적 ID가 아닙니다. 실제 관심 사람의 복구·정밀도·재현율은 미확정입니다. 사진은 원본 비율로 축소한 보기이며 모델 입력 텐서가 아닙니다.</p>'''+''.join(sections)+'</html>'
    (destination/'index.html').write_text(page,encoding='utf-8')
    manifest=dict(status='saved_detector_display_not_semantic_evaluation',comparison_path=str(comparison_path.resolve()),
        comparison_sha256=sha(comparison_path),completion_bindings=bindings,renderer_sha256=sha(__file__),
        font_sha256=sha(font_path),cases=cases,html_sha256=sha(destination/'index.html'),semantic_evaluation_complete=False)
    (destination/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(cases=len(cases),panels=sum(len(c['panels']) for c in cases),output=str(destination))))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--comparison',type=Path,required=True)
    parser.add_argument('--completion',type=Path,action='append',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();render(args.comparison,args.completion,args.output)
