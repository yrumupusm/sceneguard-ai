"""Local-only evidence for independent comparison outputs. No model execution or inferred GT."""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
if __package__:
    from .comparison_saved_evidence import checked_rows, result_provenance, checked_head_scores
else:
    from comparison_saved_evidence import checked_rows, result_provenance, checked_head_scores

ROOT=Path(__file__).resolve().parents[1]


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))


def extract(video,window,output):
    import av,cv2
    wanted={int(x) for x in window['sample_native_pts']};frames={}
    with av.open(video['source_path']) as container:
        stream=container.streams.video[0]
        if Fraction(stream.time_base)!=Fraction(window['time_base']):raise ValueError('Original time base differs')
        container.seek(min(wanted),stream=stream,backward=True,any_frame=False)
        for f in container.decode(stream):
            if f.pts in wanted:frames[f.pts]=f.to_ndarray(format='rgb24')
            if f.pts>max(wanted):break
    if set(frames)!=wanted:raise ValueError('Missing exact source samples')
    scale=960/video['source_size'][0];height=round(video['source_size'][1]*scale/2)*2
    thumb=frames[window['sample_native_pts'][8]]
    native_path=output/'native-keyframe.jpg'
    if not cv2.imwrite(str(native_path),cv2.cvtColor(thumb,cv2.COLOR_RGB2BGR)):
        raise ValueError('Native keyframe write failed')
    thumb=cv2.resize(thumb,(960,height))
    cv2.imwrite(str(output/'keyframe.jpg'),cv2.cvtColor(thumb,cv2.COLOR_RGB2BGR))
    with av.open(str(output/'input.mp4'),'w') as dest:
        stream=dest.add_stream('libx264',rate=Fraction(15,2));stream.width=960;stream.height=height
        stream.pix_fmt='yuv420p';stream.options={'crf':'20','preset':'fast'}
        for i,p in enumerate(window['sample_native_pts']):
            rgb=cv2.resize(frames[p],(960,height))
            text=f"{video['video_id']} original PTS {window['sample_pts'][i]:.6f}s  sample {i+1}/16"
            cv2.putText(rgb,text,(12,28),cv2.FONT_HERSHEY_SIMPLEX,.6,(255,255,255),2,cv2.LINE_AA)
            for packet in stream.encode(av.VideoFrame.from_ndarray(rgb,format='rgb24')):dest.mux(packet)
        for packet in stream.encode():dest.mux(packet)
    return dict(input_video='input.mp4',keyframe='keyframe.jpg',display_size=[960,height],source_size=video['source_size'],
                native_keyframe='native-keyframe.jpg',native_keyframe_sha256=sha(native_path),
                source_sample_rgb_sha256=[hashlib.sha256(frames[p].tobytes()).hexdigest() for p in window['sample_native_pts']],
                display_encoding=dict(av_version=av.__version__,opencv_version=cv2.__version__,
                    libraries=av.library_versions,codec='libx264',crf=20,preset='fast',pixel_format='yuv420p',rate='15/2',
                    resize=[960,height],jpeg_encoder='opencv default JPEG',lossy_display_not_model_tensor=True),
                source_sample_pts=window['sample_pts'],keyframe_pts=window['sample_pts'][8],
                last_input_pts=window['available_after_pts'],video_semantics='exact model samples played at7.5Hz; repeated slots are not new observations')


def saved_results(paths,expected,cohort_sha):
    models={}
    for path in paths:
        result,provenance=result_provenance(path,cohort_sha);folder=path.parent
        if result['model_id'] in models:raise ValueError('Duplicate model result')
        rows={}
        for row in checked_rows(folder/'windows.jsonl',result,expected):
            key=row['window']['window_id']
            if expected[key]['role']=='diagnostic':rows[key]=row
        models[result['model_id']]=dict(result=result,provenance=provenance,rows=rows)
    return models


def render(results,output,head_scores=()):
    renderer_sha=sha(__file__)
    cohort_path=ROOT/'outputs/model-comparison/exp0066/cohort-v1/manifest.json'
    cohort_sha=sha(cohort_path)
    cohort=read(cohort_path)
    expected={}
    for v in cohort['videos']:
        if sha(v['plan']['path'])!=v['plan']['sha256']:raise ValueError('Window plan changed')
        plan=read(v['plan']['path'])
        for role,windows in (('regular',plan['windows']),('diagnostic',plan['supplemental_windows'])):
            for w in windows:
                if w['window_id'] in expected:raise ValueError('Duplicate planned window')
                expected[w['window_id']]=dict(window=w,role=role,video_id=v['video_id'],source_sha256=v['source_sha256'])
    models=saved_results(results,expected,cohort_sha)
    heads={}
    for path in head_scores:
        model=read(path)['model_id']
        if model not in models or model in heads:raise ValueError('Unknown or duplicate scoring model')
        report,rows,proof=checked_head_scores(path,models[model]['result'],models[model]['provenance'],expected)
        heads[model]=dict(report=report,rows=rows,proof=proof)
    review_path=ROOT/'runtime/model-comparison/exp0066/cohort/current-review-snapshot.json'
    if sha(review_path)!=cohort['consumed_sha256'][str(review_path)]:raise ValueError('Frozen reviews changed')
    reviews=read(review_path)['requests']
    output.mkdir(parents=True,exist_ok=False);cases=[]
    for v in cohort['videos']:
        if sha(v['plan']['path'])!=v['plan']['sha256']:raise ValueError('Window plan changed')
        plan=read(v['plan']['path'])
        selected=[w for w in plan['supplemental_windows'] if any(w['window_id'] in m['rows'] for m in models.values())]
        if not selected:continue
        if sha(v['source_path'])!=v['source_sha256']:raise ValueError('Original video changed')
        if sha(v['cache']['path'])!=v['cache']['sha256']:raise ValueError('FCOS cache changed')
        by_pts={}
        with Path(v['cache']['path']).open() as stream:
            for line in stream:
                r=json.loads(line);by_pts[r['native_pts']]=r
        for w in selected:
            folder=output/w['window_id'];folder.mkdir()
            info=extract(v,w,folder);baseline=by_pts[w['sample_native_pts'][8]]
            baseline_output=dict(boxes=baseline['boxes'],person_scores=baseline['scores'],threshold=0.5,
                                 score_semantics='FCOS post internal0.2 and NMS; project threshold0.5',
                                 source_cache_sha256=v['cache']['sha256'],action_scores=[],action_label_names=[])
            outs={'FCOS':baseline_output}
            for name,m in models.items():
                row=m['rows'].get(w['window_id'])
                if row:
                    o={k:x for k,x in row['output'].items() if k!='pooled_features'}
                    if 'pooled_features' in row['output']:o['feature_dimension']=len(row['output']['pooled_features'])
                    if name in heads:
                        scored=heads[name]['rows'][w['window_id']]
                        o['task_head_scores']=scored['scores'];o['task_head_threshold']=scored['head_threshold']
                        o['task_head_scope']=scored['scope']
                    outs[name]=o
            cases.append(dict(window_id=w['window_id'],video_id=v['video_id'],window=w,media=info,outputs=outs,
                              previous_reviews=[{k:r[k] for k in ('id','version','answer_version','question','answer','note','processing_note')}
                                                for r in reviews if r.get('source_label','').startswith(v['video_id']+' ')],
                              person_recovery=None,climbing_correctness=None,intrusion_completion=None))
    payload=dict(status='local_model_output_review_not_semantic_evaluation',cases=cases,cohort_sha256=cohort_sha,
                 renderer_sha256=renderer_sha,evidence_verifier_sha256=sha(Path(__file__).with_name('comparison_saved_evidence.py')),
                 models={name:{k:v for k,v in m.items() if k!='rows'} for name,m in models.items()},
                 heads={name:{k:v for k,v in m.items() if k!='rows'} for name,m in heads.items()},
                 default_display_thresholds={'FCOS':0.5,'evad_vitb_vmaev2':0.7,'evad_vitl':0.7,'stmixer_vitb_vmaev2':0.6},
                 baseline_event_result='EXP0062 AFTER37/52 preserved; no new intrusion decision',
                 all_eight_raw_full_passes_complete=all(m['result']['status']=='inference_complete' for m in models.values()) and len(models)==8,
                 semantic_evaluation_complete=False)
    (output/'comparison.json').write_text(json.dumps(payload,sort_keys=True,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    page=PAGE.replace('__DATA__',json.dumps(payload,ensure_ascii=False,allow_nan=False).replace('</','<\\/'))
    (output/'index.html').write_text(page,encoding='utf-8')
    if sha(__file__)!=renderer_sha:raise ValueError('Renderer source changed during generation')
    print(json.dumps(dict(cases=len(cases),models=list(models),path=str(output/'index.html')),ensure_ascii=False))


PAGE=r'''<!doctype html><html lang="ko"><meta charset="utf-8"><title>SceneGuard 모델별 실제 출력 비교</title>
<style>body{font:16px system-ui;background:#101722;color:#edf1f7;max-width:1500px;margin:24px auto;padding:0 20px}button,select,input{font:inherit;margin:6px;padding:6px}canvas,video{max-width:100%;background:black}main{display:grid;grid-template-columns:1fr 1fr;gap:20px}.note{color:#bdc9d8;line-height:1.7}pre{white-space:pre-wrap;overflow-wrap:anywhere}fieldset{border:1px solid #526178}</style>
<h1>모델별 실제 출력 비교</h1><p class="note">원본의 같은 입력 구간을 비교합니다. 박스 수는 사람 수나 검출 성공 수가 아닙니다. AVA 행동 점수는 담장 넘기 확률이 아니며, 전용 넘기 분류기가 연결된 경우 점수를 따로 표시합니다. 새 분류기의 기준은 공식 라벨 기반 임시 기준이며, 동일 오경보율을 사람 검수로 확인한 결과가 아닙니다.</p>
<label>장면 <select id="case"></select></label><label>모델 <select id="model"></select></label>
<label>박스 표시 기준 <input id="threshold" type="number" min="0" max="1" step="0.05" value="0.5"></label>
<p class="note">표시 기준은 검수용입니다. 모델 평가 임계값이나 기존 판정을 변경하지 않습니다. 화면에는 선택한 실제 시점의 박스만 표시합니다. 박스 번호는 이 시점의 후보 번호이며, 사람의 고정 ID가 아닙니다.</p>
<main><section><label><input id="native" type="checkbox">원본 해상도로 확대 보기</label><div style="overflow:auto;max-width:100%"><canvas id="canvas"></canvas></div><p id="caption"></p><pre id="scores"></pre></section>
<section><h2>입력으로 선택한 원본 16시점</h2><video id="video" controls preload="metadata"></video><p class="note">원본 장면을 확인하는 영상입니다. 실제 모델 입력에는 모델별 크기 조정과 정규화가 적용됩니다.</p><p id="times" class="note"></p></section></main>
<details><summary>이미 받은 이 영상의 검수</summary><p class="note">아래는 이전 입력·박스에 대한 답변입니다. 새 모델 박스의 동일인·성공 정답으로 자동 적용하지 않습니다.</p><pre id="previous"></pre></details>
<p class="note">확인할 내용: 박스가 관심 사람을 잡았는지, 다른 사람·배경·합쳐진 몸을 잡았는지, 실제 넘기와 보행·대기를 구분했는지. 불명확하면 미확정으로 남깁니다.</p>
<script>const thresholdText=value=>value>1?'1 초과 (모든 점수 제외)':`약 ${value.toPrecision(5)}`;const data=__DATA__;const el=id=>document.getElementById(id);let img=new Image();
data.cases.forEach((c,i)=>el('case').add(new Option(`${c.video_id} · ${c.window.anchor_pts.toFixed(3)}초 · ${c.window.case_id||c.window_id}`,i)));
function updateModels(){let c=data.cases[Number(el('case').value)];el('model').replaceChildren();Object.keys(c.outputs).forEach(n=>el('model').add(new Option(n,n)));el('previous').textContent=c.previous_reviews.map(r=>`${r.question}\n답변: ${r.answer}\n메모: ${r.note}\n반영 범위: ${r.processing_note}`).join('\n\n')||'이 영상에 연결된 기존 답변 없음';show()}
function show(){let c=data.cases[Number(el('case').value)],m=el('model').value,o=c.outputs[m];el('threshold').value=data.default_display_thresholds[m]??0.5;img.onload=draw;const native=el('native').checked&&c.media.native_keyframe;el('canvas').style.maxWidth=native?'none':'100%';const photo=c.window_id+'/'+(native?c.media.native_keyframe:'keyframe.jpg'),clip=c.window_id+'/input.mp4';if(img.getAttribute('src')!==photo)img.src=photo;else if(img.complete)draw();if(el('video').getAttribute('src')!==clip)el('video').src=clip;el('times').textContent=`첫 입력 ${c.window.sample_pts[0].toFixed(6)}초 → 마지막 입력 ${c.media.last_input_pts.toFixed(6)}초. 이 마지막 시점 이전의 알림으로 셀 수 없습니다. 원본에서 관측한 고유 프레임 ${c.window.unique_native_frames}개 / 입력 칸16개.`;}
function draw(){let c=data.cases[Number(el('case').value)],m=el('model').value,o=c.outputs[m],canvas=el('canvas'),ctx=canvas.getContext('2d');canvas.width=img.naturalWidth;canvas.height=img.naturalHeight;ctx.drawImage(img,0,0);let sx=canvas.width/c.media.source_size[0],sy=canvas.height/c.media.source_size[1],threshold=Number(el('threshold').value),visible=0,notes=[];(o.boxes||[]).forEach((b,i)=>{let s=o.person_scores[i];if(s<threshold||o.valid_boxes?.[i]===false)return;visible++;ctx.strokeStyle=m==='FCOS'?'#facc15':'#21e6ca';ctx.lineWidth=2;ctx.strokeRect(b[0]*sx,b[1]*sy,(b[2]-b[0])*sx,(b[3]-b[1])*sy);ctx.fillStyle=ctx.strokeStyle;ctx.font='14px sans-serif';let text=`${i}: 사람 ${s.toFixed(3)}`;if(o.action_scores?.[i]?.length){let climb=o.action_scores[i][19];text+=` / AVA climb ${climb.toFixed(3)}`;notes.push(text)}if(o.task_head_scores?.[i])text+=` / 넘기 ${o.task_head_scores[i].climbing_action_score.toFixed(3)}`;ctx.fillText(text,b[0]*sx,Math.max(16,b[1]*sy-4));});el('caption').textContent=`${c.video_id} 실제 박스 시점 ${c.media.keyframe_pts.toFixed(6)}초 · 표시 박스 ${visible}개 · 동일인/성공 검수 미확정`;el('scores').textContent=o.climbing_score!=null?`R3D 넘기 점수 ${o.climbing_score.toFixed(6)} / 고정 기준0.5\n전체 화면16프레임으로 바뀐 입력 조건입니다. 침입 완료 판정이 아닙니다.`:o.feature_dimension?`영상 특징 ${o.feature_dimension}차원 추출. 아직 전용 넘기 분류 결과가 아닙니다.`:notes.join('\n');if(o.task_head_scores){let visibleScores=o.task_head_scores.filter((s,i)=>s.query_index==null||(o.person_scores[i]>=threshold&&o.valid_boxes?.[i]!==false));el('scores').textContent=visibleScores.map(s=>`${s.query_index==null?'전체 장면':`후보 ${s.query_index}`} 넘기 ${s.climbing_action_score.toFixed(6)} · 고정 행동 기준 ${thresholdText(o.task_head_threshold)} · 행동 기준 ${s.climbing_action_candidate?'통과':'미달'}`).join('\n')+'\n공식 라벨로 학습한 보조 점수입니다. 사람 대응·침입 완료·동일 오경보율은 미확정입니다.'+(o.task_head_scope.includes('no_actor')?'\n어느 사람의 행동인지 위치를 특정하지 못하는 장면 점수입니다.':'');}}
el('case').onchange=updateModels;el('model').onchange=show;el('threshold').oninput=draw;el('native').onchange=()=>{const threshold=el('threshold').value;show();el('threshold').value=threshold;};if(data.cases.length)updateModels();</script></html>'''


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--result',type=Path,action='append',required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--head-score',type=Path,action='append',default=[])
    args=p.parse_args();render(args.result,args.output,args.head_score)
