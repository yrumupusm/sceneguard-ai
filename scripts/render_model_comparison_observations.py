"""Sequence verified comparison stills; never synthesize continuous boxes or tracks."""
import argparse
from collections import defaultdict
from fractions import Fraction
import hashlib
import json
from pathlib import Path


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def render(folder):
    import av
    import numpy as np
    from PIL import Image,ImageDraw,ImageFont
    source=folder/'comparison.json';panels=folder/'panel-manifest.json'
    data=json.loads(source.read_text(encoding='utf-8'));proof=json.loads(panels.read_text(encoding='utf-8'))
    if proof['comparison_sha256']!=sha(source):raise ValueError('Comparison changed after panel creation')
    images={a['window_id']:a for a in proof['artifacts']};groups=defaultdict(list)
    for case in data['cases']:
        groups[(case['video_id'],case['window']['case_id'])].append(case)
    font_path=Path('/home/jhc7484/.local/share/fonts/sceneguard-portfolio/malgun.ttf')
    font=ImageFont.truetype(str(font_path),20);artifacts=[]
    for (video,case_id),cases in sorted(groups.items()):
        if len(cases)<2:continue
        if not case_id or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in case_id):
            raise ValueError('Unsafe case name')
        cases.sort(key=lambda c:c['media']['keyframe_pts'])
        if len({c['media']['keyframe_pts'] for c in cases})!=len(cases):raise ValueError('Duplicate original observation')
        path=folder/(case_id+'-observations.mp4')
        if path.exists():raise ValueError('Preserve existing observation movie')
        used=[]
        with av.open(str(path),'w') as dest:
            stream=None
            for case in cases:
                entry=images[case['window_id']];image_path=Path(entry['path'])
                if sha(image_path)!=entry['sha256'] or entry['source_pts']!=case['media']['keyframe_pts']:
                    raise ValueError('Actual panel/source time differs')
                image=Image.open(image_path).convert('RGB');canvas=Image.new('RGB',(image.width,image.height+64),'#101722')
                canvas.paste(image,(0,64));draw=ImageDraw.Draw(canvas)
                draw.text((16,10),'선택한 시점의 실제 검출 결과를 순서대로 보여줍니다. 원본 재생 속도·연속 추적 영상이 아닙니다.',font=font,fill='white')
                draw.text((16,36),f"현재 원본 시각 {entry['source_pts']:.6f}초 · 각 정지화면을 1초씩 표시 · 박스 보간 없음",font=font,fill='#bdc9d8')
                if stream is None:
                    stream=dest.add_stream('libx264',rate=Fraction(1));stream.width=canvas.width;stream.height=canvas.height
                    stream.pix_fmt='yuv420p';stream.options={'crf':'18','preset':'fast'}
                if (canvas.width,canvas.height)!=(stream.width,stream.height):raise ValueError('Panel dimensions changed')
                for packet in stream.encode(av.VideoFrame.from_ndarray(np.array(canvas),format='rgb24')):dest.mux(packet)
                used.append(dict(window_id=case['window_id'],source_pts=entry['source_pts'],panel_sha256=entry['sha256']))
            for packet in stream.encode():dest.mux(packet)
        artifacts.append(dict(video_id=video,case_id=case_id,path=str(path.resolve()),sha256=sha(path),observations=used,
                              unique_people=None,same_person_tracking=False,box_interpolation=False,playback='one_still_per_second_not_source_speed'))
    result=dict(status='actual_observation_slides_generated_not_tracking_evaluation',comparison_sha256=sha(source),
                panels_sha256=sha(panels),renderer_sha256=sha(__file__),font_sha256=sha(font_path),artifacts=artifacts)
    with (folder/'observation-manifest.json').open('x',encoding='utf-8') as output:json.dump(result,output,ensure_ascii=False,indent=2)
    print(json.dumps({'observation_movies':len(artifacts),'tracking_evaluation':False}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--folder',type=Path,required=True)
    render(parser.parse_args().folder)
