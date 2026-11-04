"""Render local review videos from saved actual boxes, without inference."""
import argparse
import csv
from fractions import Fraction
import hashlib
import html
import json
from pathlib import Path

import av
from PIL import Image, ImageDraw, ImageFont


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--video', type=Path, required=True)
    p.add_argument('--observations', type=Path, required=True)
    p.add_argument('--scene', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--start', type=float, required=True)
    p.add_argument('--end', type=float, required=True)
    p.add_argument('--focus-track', type=int, required=True)
    p.add_argument('--crop', nargs=4, type=int, required=True)
    p.add_argument('--font', type=Path, required=True)
    args = p.parse_args()
    if not 0 <= args.start < args.end:
        raise ValueError('Increasing source interval required')
    scene = json.loads(args.scene.read_text())
    w, h = scene['source_size']
    x0, y0, x1, y1 = args.crop
    if not 0 <= x0 < x1 <= w or not 0 <= y0 < y1 <= h:
        raise ValueError('Crop outside source frame')
    inputs = {str(f.resolve()): sha(f) for f in
              (args.video, args.observations, args.scene)}
    rows = []
    with args.observations.open() as f:
        for line in f:
            r = json.loads(line)
            if r['pts'] >= args.end:
                break
            if r['pts'] >= args.start:
                rows.append(r)
    if not rows:
        raise ValueError('No measured frames in selected interval')
    by_clock = {(r['native_pts'], Fraction(r['time_base'])): r for r in rows}
    if len(by_clock) != len(rows):
        raise ValueError('Repeated source clock')
    args.output.mkdir(parents=True, exist_ok=False)
    font = ImageFont.truetype(str(args.font), 23)
    small = ImageFont.truetype(str(args.font), 18)
    tiny = ImageFont.truetype(str(args.font), 15)
    yellow, green, gray, purple, red = '#ffe04b', '#46e895', '#a2a7af', '#d06aff', '#ff534d'

    def label(draw, xy, text, fill, use_font=tiny):
        bounds = draw.textbbox(xy, text, font=use_font)
        draw.rectangle((bounds[0]-2, bounds[1]-1, bounds[2]+2, bounds[3]+1), fill='#142028')
        draw.text(xy, text, font=use_font, fill=fill)

    def paint(original, row, all_candidates):
        im = original.copy()
        d = ImageDraw.Draw(im)
        line = [(round(x*w), round(y*h)) for x, y in scene['line']]
        d.line(line, fill=purple, width=3)
        boxes = [b for b in row['actual_boxes'] if b.get('observed') is not False]
        # Put raw unassigned candidates behind the boxes used by tracked evidence.
        boxes.sort(key=lambda b: (b.get('assignment') == 'confirmed_track',
                                  args.focus_track in b.get('track_ids', [])))
        for b in boxes:
            ids = b.get('track_ids', [])
            tracked = b.get('assignment') == 'confirmed_track'
            if not tracked and not all_candidates:
                continue
            focus = tracked and args.focus_track in ids
            color = yellow if focus else green if tracked else gray
            box = [round(v*(w if i % 2 == 0 else h)) for i, v in enumerate(b['bbox'])]
            d.rectangle(box, outline=color, width=3 if focus else 2 if tracked else 1)
            if tracked:
                text = f"ID {','.join(map(str, ids))}  {b['score']:.2f}"
                label(d, (box[0], max(0, box[1]-22)), text, color)
            if focus:
                cx, cy = (box[0]+box[2])/2, box[3]
                d.ellipse((cx-5, cy-5, cx+5, cy+5), fill=red)
        return im

    def zoom(original, marked, row, all_candidates):
        canvas = Image.new('RGB', (1280, 720), '#122028')
        # Both panels use the same fixed crop, scale and source frame.
        a = original.crop(args.crop)
        b = marked.crop(args.crop)
        scale = min(640/a.width, 600/a.height)
        size = (round(a.width*scale), round(a.height*scale))
        for i, panel in enumerate((a, b)):
            canvas.paste(panel.resize(size, Image.Resampling.LANCZOS),
                         (i*640+(640-size[0])//2, 60+(600-size[1])//2))
        d = ImageDraw.Draw(canvas)
        at = row['pts']
        clock = f'{int(at//60):02d}:{at%60:06.3f}'
        d.text((16, 12), f'원본 · {clock}', fill='white', font=font)
        d.text((656, 12), '모든 검출 후보' if all_candidates else '판정에 사용된 관측 박스', fill='white', font=font)
        d.text((16, 666), f'노랑: 판정 ID {args.focus_track}   초록: 다른 추적 관측   빨강점: 박스 하단 중앙', fill='white', font=small)
        d.text((16, 692), '보라: 실제 설정 경계선' + ('   회색: 미연결·미확정 검출 후보' if all_candidates else '   현재 관측이 없는 박스는 표시하지 않음'), fill='#b9c7d0', font=small)
        return canvas

    outputs = {}
    with av.open(str(args.video)) as source:
        video = source.streams.video[0]
        rate = video.average_rate
        first_clock = Fraction(rows[0]['native_pts'])*Fraction(rows[0]['time_base'])
        for name, size in [('boxes_zoom', (1280, 720)), ('all_candidates_zoom', (1280, 720)),
                           ('all_boxes_full', (w, h+80))]:
            out = av.open(str(args.output/f'{name}.mp4'), 'w', options={'movflags': '+faststart'})
            stream = out.add_stream('libx264', rate=rate)
            stream.width, stream.height = size
            stream.pix_fmt = 'yuv420p'
            stream.options = {'crf': '19', 'preset': 'veryfast', 'threads': '2'}
            outputs[name] = (out, stream)
        source.seek(int(Fraction(str(args.start))/video.time_base), stream=video, backward=True)
        mapping = []
        for frame in source.decode(video=0):
            clock = Fraction(frame.pts)*frame.time_base
            if float(clock) < args.start-1e-9:
                continue
            if float(clock) >= args.end-1e-9:
                break
            row = by_clock[(frame.pts, frame.time_base)]
            if abs(float(clock)-row['pts']) > 1e-8 or (frame.width, frame.height) != (w, h):
                raise ValueError('Saved observation does not match original frame')
            original = frame.to_image()
            tracked = paint(original, row, False)
            all_boxes = paint(original, row, True)
            full = Image.new('RGB', (w, h+80), '#122028')
            full.paste(all_boxes, (0, 80))
            d = ImageDraw.Draw(full)
            d.text((18, 10), f"{args.video.stem} · 원본 {row['pts']:.3f}초 · 저장된 실제 관측 박스", fill='white', font=font)
            d.text((18, 46), f'노랑 ID {args.focus_track} / 초록 다른 추적 관측 / 회색 미연결 후보 / 빨강 박스 하단 중앙 / 보라 설정 경계', fill='white', font=small)
            views = {'boxes_zoom': zoom(original, tracked, row, False),
                     'all_candidates_zoom': zoom(original, all_boxes, row, True), 'all_boxes_full': full}
            for name, im in views.items():
                out, stream = outputs[name]
                vf = av.VideoFrame.from_image(im)
                vf.time_base = frame.time_base
                vf.pts = int((clock-first_clock)/frame.time_base)
                for packet in stream.encode(vf):
                    out.mux(packet)
            target = [b for b in row['actual_boxes'] if b.get('assignment') == 'confirmed_track'
                      and args.focus_track in b.get('track_ids', [])]
            mapping.append(dict(source_pts=row['pts'], frame_index=row['frame_index'], native_pts=frame.pts,
                time_base=str(frame.time_base), playback_pts=float(clock-first_clock),
                focus_observations=len(target), actual_boxes=len(row['actual_boxes'])))
        for out, stream in outputs.values():
            for packet in stream.encode():
                out.mux(packet)
            out.close()
    if [m['frame_index'] for m in mapping] != [r['frame_index'] for r in rows]:
        raise ValueError('Missing, duplicated or reordered original frames')
    if any(sha(path) != expected for path, expected in inputs.items()):
        raise ValueError('Source file changed during rendering')
    with (args.output/'frame_mapping.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(mapping[0]))
        writer.writeheader(); writer.writerows(mapping)
    receipt = dict(video=str(args.video.resolve()), source_interval=[args.start, args.end],
        first_actual_pts=rows[0]['pts'], last_actual_pts=rows[-1]['pts'], frames=len(rows),
        crop=args.crop, focus_track=args.focus_track, inputs_sha256=inputs,
        renderer_sha256=sha(__file__), new_detector_calls=0, new_tracker_calls=0,
        predicted_or_interpolated_boxes_drawn=False, unchanged_inputs=True,
        files={name+'.mp4': sha(args.output/(name+'.mp4')) for name in outputs})
    (args.output/'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')
    title = html.escape(args.video.stem)
    page = '''<!doctype html><html lang="ko"><meta charset="utf-8"><title>VIDEO 박스 검수</title>
<style>body{margin:24px auto;max-width:1280px;background:#122028;color:#edf4f7;font:17px system-ui}video{width:100%;max-height:78vh;background:black}button{padding:10px;margin:5px;border:0;border-radius:6px;cursor:pointer}p{line-height:1.6}</style>
<h2>VIDEO · 52–68초 박스 검수</h2>
<p>원본과 저장된 실제 관측 박스를 같은 시각으로 비교합니다. 새 모델 추론 없이 표시했습니다.<br>노랑은 59.933초 판정에 쓰인 추적 ID 16입니다. 추적 ID는 사람의 신원 확인을 뜻하지 않습니다.</p>
<div><button onclick="change('boxes_zoom.mp4')">확대 · 판정용 박스</button><button onclick="change('all_candidates_zoom.mp4')">확대 · 모든 검출 후보</button><button onclick="change('all_boxes_full.mp4')">전체 화면</button></div>
<video id="v" controls preload="metadata" src="boxes_zoom.mp4"></video>
<div><button onclick="v.currentTime=56-START">56초</button><button onclick="v.currentTime=59.933333-START">59.933초 확인 시점</button><button onclick="v.currentTime=63-START">63초</button><button onclick="v.playbackRate=.5">0.5배속</button><button onclick="v.playbackRate=1">정상 속도</button></div>
<p>영상 상단 시간은 원본 시각입니다. 플레이어의 0초는 원본 START초입니다.<br>회색 후보가 존재해도 해당 사람을 정확히 검출했다는 뜻은 아닙니다. 박스가 실제 몸을 감싸는지 함께 확인해 주세요.</p>
<script>const v=document.getElementById('v');function change(src){const t=v.currentTime,r=v.playbackRate,paused=v.paused;v.src=src;v.addEventListener('loadedmetadata',()=>{v.currentTime=t;v.playbackRate=r;if(!paused)v.play()},{once:true})}</script></html>'''
    # Source-specific bookmarks describe this requested review, not model labels.
    page = page.replace('VIDEO', title).replace('START', str(rows[0]['pts']))
    (args.output/'index.html').write_text(page)
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == '__main__':
    main()
