"""Render actual source / original annotation / separate model drafts for local review."""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.render_comparison_validation_errors import encode, sha


def render(package_path, output):
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np
    package = json.loads(package_path.read_text())
    if 'execution_binding' not in package or package['training_release'] is not False:
        raise ValueError('Executed draft-only package required')
    output.mkdir(parents=True, exist_ok=False)
    font_path = Path('/mnt/c/Windows/Fonts/malgun.ttf')
    font = ImageFont.truetype(str(font_path), 26)
    small = ImageFont.truetype(str(font_path), 22)
    cases = []
    for number in sorted({f['case_number'] for f in package['frames']}):
        selected = [f for f in package['frames'] if f['case_number'] == number]
        images, shown = [], []
        for frame in selected:
            if sha(frame['image_path']) != frame['image_sha256']:
                raise ValueError('Image changed')
            with Image.open(frame['image_path']) as source:
                im = Image.new('RGB', (2880, 640), '#14202b')
                preview = source.resize((960, 540))
                for x in (0, 960, 1920):
                    im.paste(preview, (x, 100))
            draw = ImageDraw.Draw(im)
            labels = ['원본 · 모든 사람을 확인', '기존 라벨 · 청록색', '모델 초안 · 주황색 · 아직 정답 아님']
            for x, label in zip((12, 972, 1932), labels):
                draw.text((x, 8), label, font=font, fill='white')
                draw.text((x, 48), f"라벨 {number} · 원본 {frame['source_pts']:.3f}초 · 박스가 없어도 정상으로 확정하지 않음", font=small, fill='#c6d5df')
            displayed = []
            for box in frame['candidates']:
                if box['kind'] == 'model' and box['score'] < .5:
                    continue
                offset = 960 if box['kind'] == 'original' else 1920
                color = '#39ffff' if box['kind'] == 'original' else '#ffb347'
                sx, sy = 960/frame['source_size'][0], 540/frame['source_size'][1]
                x1,y1,x2,y2 = box['xyxy']
                rect = (offset+x1*sx, 100+y1*sy, offset+x2*sx, 100+y2*sy)
                draw.rectangle(rect, outline=color, width=3)
                label = box['label'] + (f" {box['score']:.2f}" if box['kind']=='model' else '')
                draw.text((rect[0], max(100,rect[1]-25)), label, font=small, fill=color)
                if box['kind'] == 'model':
                    displayed.append(dict(id=box['id'], xyxy=box['xyxy'], score=box['score']))
            shown.append(dict(frame_id=frame['frame_id'], source_pts=frame['source_pts'], image_sha256=frame['image_sha256'], displayed_proposals=displayed))
            images.append(np.asarray(im))
        video = output/f'case-{number:02d}.mp4'
        encode(video, images, Fraction(3))
        cases.append(dict(case_number=number, frame_count=len(images), video=str(video.resolve()), video_sha256=sha(video), frames=shown))
    result = dict(package_sha256=sha(package_path), renderer_sha256=sha(__file__), font_sha256=sha(font_path),
                  display_threshold=.5, fps=3, training_release=False, cases=cases)
    (output/'manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(cases=len(cases),frames=sum(c['frame_count'] for c in cases),manifest_sha256=sha(output/'manifest.json'))))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();render(args.package,args.output)
