"""Local-only viewer for saved validation label disagreements; no inference or GT edits."""
import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.exp0066_encoders import letterbox

MODELS = {'videomaev2_b': ('VideoMAE', 224), 'vjepa2_l': ('V-JEPA2', 256),
          'vjepa2_1_l': ('V-JEPA2.1', 384)}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def selection(plan):
    windows = {w['window_id']: w for w in plan['windows']}
    scores, proofs, selected = {}, {}, set()
    for model in MODELS:
        completion = read(ROOT/'runtime/model-comparison/exp0066/head-execution/stages'/model/'train/completion.json')
        result_path = Path(completion['result']['path'])
        if sha(result_path) != completion['result']['sha256']:
            raise ValueError('Training result changed')
        result = read(result_path)
        sp = result_path.parent/'selection.json'
        if sha(sp) != result['selection_sha256']:
            raise ValueError('Validation scores changed')
        saved = read(sp)
        if result['model_id'] != model or saved['selection'] != result['selection']:
            raise ValueError('Model/threshold mismatch')
        keys = [key for key in saved['sample_keys'] if windows[key[0]]['split'] == 'validation']
        if len(keys) != len(saved['validation_scores']) or len(keys) != len(saved['validation_labels']):
            raise ValueError('Validation keys and scores differ')
        if len({k[0] for k in keys}) != len(keys) or any(k[1] is not None for k in keys):
            raise ValueError('Unique scene scores required')
        threshold = saved['selection']['threshold']
        scores[model] = {}
        for (wid, _), label, score in zip(keys, saved['validation_labels'], saved['validation_scores']):
            if windows[wid]['label'] != label:
                raise ValueError('Reference label changed')
            fp = label == 0 and score >= threshold
            scores[model][wid] = dict(score=score, threshold=threshold, reference_false_positive=fp)
            if fp:
                selected.add(wid)
        if sum(s['reference_false_positive'] for s in scores[model].values()) != result['selection']['fp']:
            raise ValueError('FP count differs')
        proofs[model] = dict(result_path=str(result_path), result_sha256=sha(result_path),
                             selection_sha256=sha(sp), head_sha256=result['head_sha256'])
    rows = sorted((windows[wid] for wid in selected), key=lambda w: (w['source_id'], w['anchor_pts'], w['window_id']))
    return rows, scores, proofs


def encode(path, frames, rate):
    import av
    with av.open(str(path), 'w') as dest:
        stream = dest.add_stream('libx264', rate=rate)
        stream.width, stream.height = frames[0].shape[1], frames[0].shape[0]
        stream.pix_fmt = 'yuv420p'
        stream.options = {'crf': '18', 'preset': 'fast', 'threads': '1'}
        for rgb in frames:
            for packet in stream.encode(av.VideoFrame.from_ndarray(rgb, format='rgb24')):
                dest.mux(packet)
        for packet in stream.encode():
            dest.mux(packet)


def render(output):
    import av
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    cv2.setNumThreads(1)
    plan_path = ROOT/'outputs/model-comparison/exp0066/head-plan-v2/manifest.json'
    plan = read(plan_path)
    rows, scores, proofs = selection(plan)
    prep = read(ROOT/'outputs/model-comparison/exp0066/head-preparation/native-v2/review-ready.json')
    source_proofs = {r['source_sha256']: r for r in prep['sources']}
    verified = set()
    output.mkdir(parents=True, exist_ok=False)
    font_path = ROOT.parent.parent/'.local/share/fonts/sceneguard-portfolio/malgun.ttf'
    if not font_path.exists():
        font_path = Path('/mnt/c/Windows/Fonts/malgun.ttf')
    font = ImageFont.truetype(str(font_path), 20)
    cases = []
    for n, w in enumerate(rows, 1):
        if w['source_path'] not in verified:
            if sha(w['source_path']) != w['source_sha256']:
                raise ValueError('Source changed')
            verified.add(w['source_path'])
        annotations = []
        seen = set()
        for target in w['targets']:
            if target['label_path'] in seen:
                continue
            seen.add(target['label_path'])
            if sha(target['label_path']) != target['label_sha256']:
                raise ValueError('Annotation changed')
            annotations.extend(read(target['label_path'])['annotations'])
        proof = source_proofs[w['source_sha256']]
        if sha(proof['path']) != proof['sha256']:
            raise ValueError('Pixel preparation receipt changed')
        rgb_hashes = {r['pts_tick']: r['rgb_sha256'] for r in read(proof['path'])['frames']}
        folder = output/w['window_id']
        folder.mkdir()
        start, end = w['sample_pts'][0], w['sample_pts'][-1]
        frames, meta, selected_rgb = [], [], {}
        targets = {str(t['actor_id']) for t in w['targets']}
        with av.open(w['source_path']) as src:
            stream = src.streams.video[0]
            stream.codec_context.thread_count = 1
            if Fraction(stream.time_base) != Fraction(w['time_base']) or Fraction(stream.average_rate) != 3:
                raise ValueError('Expected actual 3FPS source timebase')
            src.seek(max(0, int((start - 3.5)/float(stream.time_base))), stream=stream, backward=True)
            for f in src.decode(stream):
                t = float(f.pts * stream.time_base)
                if t < max(0, start-3)-1e-6:
                    continue
                if t > end+3+1e-6:
                    break
                rgb = f.to_ndarray(format='rgb24')
                if f.pts in w['sample_pts_ticks']:
                    if hashlib.sha256(rgb.tobytes()).hexdigest() != rgb_hashes[f.pts]:
                        raise ValueError('Exact model sample pixels changed')
                    selected_rgb[f.pts] = rgb
                frame_index = round(t*3)
                if abs(frame_index/3-t) > 1e-6:
                    raise ValueError('Unexpected source frame timing')
                boxes = {}
                for origin in (0, 1):
                    boxes[str(origin)] = [dict(actor=str(a['actor_id']), action=a['class_name'],
                        xyxy=[*a['bbox'][0], *a['bbox'][1]], target=str(a['actor_id']) in targets)
                        for a in annotations if a['cur_frame'] == frame_index+origin]
                meta.append(dict(pts=t, native_pts=f.pts, frame_index=frame_index, boxes=boxes))
                image = Image.new('RGB', (960,600), '#101722')
                image.paste(Image.fromarray(rgb).resize((960,540)), (0,60))
                draw = ImageDraw.Draw(image)
                inside = start-1e-6 <= t <= end+1e-6
                draw.text((12,5), f'원본 {t:.3f}초  |  '+('모델이 본 구간' if inside else '앞뒤 참고 장면 — 모델 입력 밖'),
                          font=font, fill='#57e4cf' if inside else '#eeeeee')
                draw.text((12,31), '라벨: 바닥에 앉기 · 실제 행동 미검수 · 전체 화면 입력', font=font, fill='#eeeeee')
                frames.append(np.asarray(image))
        if set(selected_rgb) != set(w['sample_pts_ticks']):
            raise ValueError('Missing actual sample frames')
        if any(abs(b['pts']-a['pts']-1/3)>1e-6 for a,b in zip(meta,meta[1:])):
            raise ValueError('Context frames are not continuous')
        encode(folder/'context.mp4', frames, Fraction(3))
        Image.fromarray(frames[len(frames)//2]).save(folder/'poster.jpg', quality=90)
        inputs, input_hashes = {}, {}
        raw = np.stack([selected_rgb[t] for t in w['sample_pts_ticks']])
        for model, (_, size) in MODELS.items():
            pixels, geometry = letterbox(raw, size)
            name = f'input-{size}.mp4'
            encode(folder/name, pixels, Fraction(15,2))
            inputs[model] = dict(path=w['window_id']+'/'+name, resolution=size, geometry=geometry,
                sha256=sha(folder/name), before_normalization_rgb_sha256=hashlib.sha256(pixels.tobytes()).hexdigest())
            input_hashes[model] = inputs[model]['before_normalization_rgb_sha256']
        cases.append(dict(number=n, window_id=w['window_id'], source_name=Path(w['source_path']).name,
            source_sha256=w['source_sha256'], source_size=w['source_size'], start=start, end=end,
            context=w['window_id']+'/context.mp4', context_sha256=sha(folder/'context.mp4'),
            poster=w['window_id']+'/poster.jpg', frames=meta, inputs=inputs,
            scores={m: scores[m][w['window_id']] for m in MODELS},
            source_sample_pts=w['sample_pts'], unique_frames=w['observed_unique_frames'],
            annotation_origins_verified=False, human_semantic_verification=False))
        print(json.dumps(dict(rendered=n, total=len(rows))), flush=True)
    payload = dict(status='local_validation_reference_disagreement_review', cases=cases,
        models={m: v[0] for m,v in MODELS.items()}, model_provenance=proofs,
        counts={m:sum(c['scores'][m]['reference_false_positive'] for c in cases) for m in MODELS},
        unique_windows=len(cases), unique_sources=len({c['source_sha256'] for c in cases}),
        plan_sha256=sha(plan_path), renderer_sha256=sha(__file__),
        preprocess_sha256=sha(ROOT/'scripts/exp0066_encoders.py'), font_sha256=sha(font_path),
        new_model_inference=0, training_changed=False, human_semantic_verification=False,
        encoding='H264 lossy preview; exact selected source RGB verified against preparation; input preview is before normalization')
    (output/'review.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    page = PAGE.replace('__DATA__', json.dumps(payload,ensure_ascii=False).replace('</','<\\/'))
    (output/'index.html').write_text(page,encoding='utf-8')


PAGE = r'''<!doctype html><html lang="ko"><meta charset="utf-8"><title>SceneGuard 정상 라벨 오판 후보</title>
<style>body{font:16px system-ui;background:#101722;color:#edf1f7;max-width:1450px;margin:24px auto;padding:0 18px}select,button{font:inherit;padding:8px;margin:4px;background:#243347;color:white;border:1px solid #718096;border-radius:5px}main{display:grid;grid-template-columns:2fr 1fr;gap:20px}video{width:100%;background:black}.frame{position:relative}canvas{position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none}p{line-height:1.6}.muted{color:#bfcbdb}table{border-collapse:collapse;width:100%}td,th{padding:9px;text-align:left;border-bottom:1px solid #42516a}.warn{color:#ffbc78}#input{max-width:384px;image-rendering:pixelated}@media(max-width:850px){main{display:block}}</style>
<h1>정상 라벨인데 ‘넘기’로 판단한 장면</h1>
<p>세 모델 각각 14개 · 중복을 합친 41개 입력 구간입니다. 라벨은 모두 ‘바닥에 앉기’입니다. <b>실제 행동을 확인하기 전이므로 확정된 오탐은 아닙니다.</b></p>
<label>모델별 후보 <select id="filter"><option value="all">전체 41개</option></select></label>
<label>장면 <select id="case"></select></label><button id="prev">이전</button><button id="next">다음</button>
<p id="desc"></p><main><section><h2>원본 앞뒤 장면</h2>
<div class="frame"><video id="context" controls preload="metadata"></video><canvas id="overlay" width="960" height="600"></canvas></div>
<label><input id="boxes" type="checkbox" checked>라벨 박스 표시</label>
<details><summary>라벨 시간 대응 설정</summary><label>프레임 번호 해석 <select id="origin"><option value="1">1번부터 시작</option><option value="0">0번부터 시작</option></select></label><p class="muted">0/1 시작에 따른 한 프레임 차이를 비교하는 표시 옵션입니다. 이 선택은 정답·평가 값을 수정하지 않습니다.</p></details>
<p class="muted">빨강은 라벨 대상, 회색은 다른 라벨 대상입니다. <b>모델이 검출한 박스가 아닙니다.</b> 박스가 없어도 사람이 없거나 정상이라는 뜻은 아닙니다.</p>
</section><section><h2>실제 입력 구성</h2><label>입력 크기 <select id="inputModel"></select></label><video id="input" controls preload="metadata" loop></video>
<p id="inputInfo" class="muted"></p><p class="muted">전체 화면을 줄이고 검은 여백을 붙인, 정규화 전 입력의 재생용 영상입니다. 16칸 중 고유 원본은 7프레임이며 반복이 포함됩니다. 재생용 압축 영상은 모델 텐서와 바이트가 같지는 않습니다.</p>
<table><thead><tr><th>모델</th><th>넘기 점수</th><th>판정 기준</th><th>결과</th></tr></thead><tbody id="scores"></tbody></table>
<p class="muted">점수는 선택한 짧은 입력 전체의 값입니다. 앞뒤 참고 장면이나 현재 재생 프레임의 점수가 아닙니다. 모델마다 기준이 다르므로 점수 크기로 우열을 비교하지 않습니다.</p></section></main>
<p class="muted">이 자료는 AI-Hub 검증 자료입니다. 학교 CCTV 성능이나 학습 전후 박스 개선 결과가 아닙니다. 실제로 앉는 장면인지, 다른 사람의 넘는 동작이 함께 들어왔는지, 라벨 박스가 사람을 따라가는지 확인할 수 있습니다.</p>
<script>const data=__DATA__;const el=id=>document.getElementById(id);let shown=[],current;const fmt=x=>x===0?'0':x.toPrecision(6);
for(const [m,n] of Object.entries(data.models)){el('filter').add(new Option(n+' · 14개',m));el('inputModel').add(new Option(n,m));}
function fill(){shown=data.cases.filter(c=>el('filter').value==='all'||c.scores[el('filter').value].reference_false_positive);el('case').replaceChildren();shown.forEach((c,i)=>el('case').add(new Option(`${c.number}. ${c.source_name.replace('.mp4','')} · ${c.start.toFixed(2)}–${c.end.toFixed(2)}초`,i)));show();}
function show(){resetVideoFrames();current=shown[Number(el('case').value)];el('context').src=current.context;el('context').poster=current.poster;el('desc').textContent=`장면 ${current.number} / 41 · 모델 입력: 원본 ${current.start.toFixed(3)}–${current.end.toFixed(3)}초 · 넘기로 판단한 모델: ${Object.entries(current.scores).filter(([m,s])=>s.reference_false_positive).map(([m])=>data.models[m]).join(', ')}`;el('scores').replaceChildren();for(const [m,s] of Object.entries(current.scores)){const tr=document.createElement('tr');for(const v of [data.models[m],fmt(s.score),fmt(s.threshold),s.reference_false_positive?'넘기 후보':'기준 미달']){const td=document.createElement('td');td.textContent=v;tr.append(td);}if(s.reference_false_positive)tr.className='warn';el('scores').append(tr);}if(el('filter').value!=='all')el('inputModel').value=el('filter').value;input();startVideoFrames();draw();}
function input(){const m=el('inputModel').value,v=current.inputs[m];el('input').src=v.path;el('inputInfo').textContent=`${data.models[m]} · ${v.resolution}×${v.resolution} · 같은 원본 16개 입력 시점`;}
let presentedTime=0,videoFrameId=null,videoGeneration=0;
function resetVideoFrames(){videoGeneration++;if(videoFrameId!==null&&el('context').cancelVideoFrameCallback)el('context').cancelVideoFrameCallback(videoFrameId);videoFrameId=null;presentedTime=0;}
function startVideoFrames(){const video=el('context'),generation=videoGeneration;if(!video.requestVideoFrameCallback)return;const frame=(now,metadata)=>{if(generation!==videoGeneration)return;presentedTime=metadata.mediaTime;draw();videoFrameId=video.requestVideoFrameCallback(frame);};videoFrameId=video.requestVideoFrameCallback(frame);}
function draw(){const ctx=el('overlay').getContext('2d');ctx.clearRect(0,0,960,600);if(!current||!el('boxes').checked)return;const idx=Math.min(current.frames.length-1,Math.floor(presentedTime*3+0.0001));const f=current.frames[idx];for(const b of f.boxes[el('origin').value]){let [x1,y1,x2,y2]=b.xyxy;const sx=960/current.source_size[0],sy=540/current.source_size[1];ctx.strokeStyle=ctx.fillStyle=b.target?'#ff4b4b':'#d3d3d3';ctx.lineWidth=3;ctx.strokeRect(x1*sx,y1*sy+60,(x2-x1)*sx,(y2-y1)*sy);ctx.font='16px sans-serif';ctx.fillText('라벨 대상 '+b.actor,x1*sx,Math.max(78,y1*sy+55));}}
el('filter').onchange=fill;el('case').onchange=show;el('inputModel').onchange=input;el('boxes').onchange=draw;el('origin').onchange=draw;function fallbackFrame(){if(!el('context').requestVideoFrameCallback){presentedTime=el('context').currentTime;draw();}}el('context').ontimeupdate=fallbackFrame;el('context').onseeked=fallbackFrame;el('context').onloadeddata=fallbackFrame;
for(const [id,delta]of [['prev',-1],['next',1]])el(id).onclick=()=>{el('case').selectedIndex=(el('case').selectedIndex+delta+shown.length)%shown.length;show();};fill();</script></html>'''


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    render(parser.parse_args().output)
