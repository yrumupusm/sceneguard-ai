"""Create local comparison stills for the existing image/video evidence viewer."""
import argparse
import hashlib
import json
from pathlib import Path

MODELS=['evad_vitb_vmaev2','evad_vitl','stmixer_vitb_vmaev2','internvideo_next_s2_l',
        'vjepa2_l','vjepa2_1_l','videomaev2_b','r3d18_exp0064']
JOINT=set(MODELS[:3])


def score_rows(case,thresholds):
    """Display only saved decisions; person-filtered maxima never imply target identity."""
    rows=[]
    for name in MODELS:
        out=case['outputs'].get(name)
        row=dict(model=name,scope='미실행/결과 없음',score=None,query_index=None,threshold=None,candidate=None)
        if out is not None:
            row['scope']='사람 표시 기준 통과 후보 중 최대' if name in JOINT else '전체 장면 · 사람 위치 없음'
            if name=='r3d18_exp0064':
                if out['threshold']!=.5:raise ValueError('R3D threshold changed')
                row.update(score=out['climbing_score'],threshold=.5,candidate=out['climbing_score']>=.5)
            elif out.get('task_head_scores'):
                scores=out['task_head_scores'];row['threshold']=out['task_head_threshold']
                if name in JOINT:
                    eligible=[i for i,p in enumerate(out['person_scores']) if p>=thresholds[name] and out['valid_boxes'][i]]
                    if eligible:
                        i=max(eligible,key=lambda i:(scores[i]['climbing_action_score'],-i))
                        if scores[i]['query_index']!=i:raise ValueError('Head query index differs')
                        row.update(score=scores[i]['climbing_action_score'],query_index=i,
                                   candidate=scores[i]['person_and_action_candidate'])
                    else:row.update(scope='사람 표시 기준 통과 후보 없음',candidate=False)
                else:
                    if len(scores)!=1 or scores[0]['query_index'] is not None:raise ValueError('Scene score shape differs')
                    row.update(score=scores[0]['climbing_action_score'],candidate=scores[0]['climbing_action_candidate'])
            else:row['scope']='전용 넘기 점수 미생성 · AVA 출력만' if name in JOINT else '특징 추출만 · 넘기 점수 미생성'
        rows.append(row)
    return rows


def threshold_text(value):
    if value is None:return '—'
    if value>1:return '1 초과 · 모든 점수 제외'
    return f'약 {value:.6g}'


def render(folder,native_resolution=False):
    from PIL import Image, ImageDraw, ImageFont
    manifest=folder/'comparison.json';data=json.loads(manifest.read_text(encoding='utf-8'))
    names=['FCOS','evad_vitb_vmaev2','evad_vitl','stmixer_vitb_vmaev2']
    font_path=Path('/home/jhc7484/.local/share/fonts/sceneguard-portfolio/malgun.ttf')
    artifacts=[]
    for case in data['cases']:
        case_dir=folder/case['window_id']
        source_path=case_dir/(case['media']['native_keyframe'] if native_resolution else 'keyframe.jpg')
        if native_resolution and hashlib.sha256(source_path.read_bytes()).hexdigest()!=case['media']['native_keyframe_sha256']:
            raise ValueError('Native keyframe changed')
        source=Image.open(source_path).convert('RGB');width,height=source.size
        if native_resolution and [width,height]!=case['media']['source_size']:raise ValueError('Native image dimensions differ')
        scale=width/960;px=lambda value:max(1,round(value*scale))
        font=ImageFont.truetype(str(font_path),px(16));small=ImageFont.truetype(str(font_path),px(13))
        header=px(70);footer=px(28)
        table_top=(height+header+footer)*2
        canvas=Image.new('RGB',(width*2,table_top+px(310)),'#101722')
        for panel,name in enumerate(names):
            left=(panel%2)*width;top=(panel//2)*(height+header+footer)
            image=source.copy();draw=ImageDraw.Draw(image);out=case['outputs'].get(name)
            threshold=data['default_display_thresholds'][name];shown=0
            if out:
                sx=width/case['media']['source_size'][0];sy=height/case['media']['source_size'][1]
                for i,(box,score) in enumerate(zip(out.get('boxes',[]),out.get('person_scores',[]))):
                    if score<threshold or out.get('valid_boxes',[True]*len(out['boxes']))[i] is False:continue
                    shown+=1;color='#facc15' if name=='FCOS' else '#21e6ca'
                    coords=(box[0]*sx,box[1]*sy,box[2]*sx,box[3]*sy)
                    draw.rectangle(coords,outline=color,width=px(2))
                    label=f'q{i} 사람={score:.3f}'
                    if out.get('action_scores'):label+=f" AVA20={out['action_scores'][i][19]:.3f}"
                    if out.get('task_head_scores'):label+=f" 넘기={out['task_head_scores'][i]['climbing_action_score']:.3f}"
                    x,y=coords[0],max(0,coords[1]-px(17))
                    extent=draw.textbbox((x,y),label,font=small);draw.rectangle(extent,fill='#101722')
                    draw.text((x,y),label,font=small,fill=color)
            canvas.paste(image,(left,top+header));draw=ImageDraw.Draw(canvas)
            draw.text((left+px(12),top+px(8)),f"{case['video_id']} 원본 {case['media']['keyframe_pts']:.6f}초 | {name}",font=font,fill='white')
            text=f'사람 표시 기준 {threshold:.2f} | 박스 {shown}개 (인원수 아님)' if out else '완료된 결과가 아직 없습니다'
            if out and 'task_head_threshold' in out:text+=f" | 임시 넘기 기준 {threshold_text(out['task_head_threshold'])}"
            draw.text((left+px(12),top+px(33)),text,font=small,fill='#bdc9d8')
            timing=(f"행동 입력 {case['window']['sample_pts'][0]:.3f}–{case['media']['last_input_pts']:.3f}초 · 마지막 입력 이후에 사용 가능한 점수"
                    if name!='FCOS' else '기존 FCOS의 해당 시점 실제 사람 박스 · 행동 점수 없음')
            draw.text((left+px(12),top+px(52)),timing,font=small,fill='#bdc9d8')
            draw.text((left+px(12),top+header+height+px(5)),'q는 이 시점의 후보 번호이며 추적 ID가 아닙니다. AVA20은 CCTV 넘기 확률이 아닙니다.',font=small,fill='#bdc9d8')
        rows=score_rows(case,data['default_display_thresholds']);draw=ImageDraw.Draw(canvas)
        draw.text((px(12),table_top+px(8)),'8개 모델의 저장된 넘기 점수 · 서로 같은 오경보율이나 검출 성공을 뜻하지 않습니다.',font=font,fill='white')
        columns=[12,340,870,1100,1450]
        for x,label in zip(columns,['모델','점수의 대상','점수 / 후보 번호','고정 행동 기준','저장된 기준 통과 여부']):
            draw.text((px(x),table_top+px(40)),label,font=small,fill='#bdc9d8')
        for index,row in enumerate(rows):
            y=table_top+px(65+index*25)
            score='—' if row['score'] is None else f"{row['score']:.6f}"+(f" / q{row['query_index']}" if row['query_index'] is not None else '')
            decision='미측정' if row['candidate'] is None else '통과 · 침입 완료 아님' if row['candidate'] else '미달/후보 없음'
            for x,label in zip(columns,[row['model'],row['scope'],score,threshold_text(row['threshold']),decision]):
                draw.text((px(x),y),label,font=small,fill='white')
        draw.text((px(12),table_top+px(278)),'사람 후보의 최대 점수는 다른 사람일 수 있습니다. 전체 장면 점수는 어느 사람의 행동인지 특정하지 못합니다.',font=small,fill='#bdc9d8')
        path=case_dir/'comparison-panels.jpg'
        if path.exists():raise ValueError('Preserve prior generated panels')
        canvas.save(path,quality=95)
        artifacts.append(dict(window_id=case['window_id'],path=str(path.resolve()),
                              sha256=hashlib.sha256(path.read_bytes()).hexdigest(),source_pts=case['media']['keyframe_pts'],
                              source_image_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),panel_image_size=[width,height],
                              score_rows=rows))
    receipt=dict(status='generated_local_stills_not_semantic_validation',
                 comparison_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
                 renderer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),artifacts=artifacts)
    receipt['font_sha256']=hashlib.sha256(font_path.read_bytes()).hexdigest()
    receipt['native_resolution']=native_resolution
    with (folder/'panel-manifest.json').open('x',encoding='utf-8') as stream:json.dump(receipt,stream,indent=2,ensure_ascii=False)
    print(json.dumps({'images':len(artifacts),'folder':str(folder)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--folder',type=Path,required=True)
    parser.add_argument('--native-resolution',action='store_true')
    args=parser.parse_args();render(args.folder,args.native_resolution)
