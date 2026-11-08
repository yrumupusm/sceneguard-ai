"""Local original/confirmed GT, before, after comparison on reviewed validation25."""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.evaluate_person_detector_pair import MANIFEST_SHA, sha, validate_predictions
from scripts.render_comparison_validation_errors import encode


def render(manifest_path, before_path, after_path, output):
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    if sha(manifest_path) != MANIFEST_SHA:
        raise ValueError('Fixed human-confirmed dataset required')
    manifest = json.loads(manifest_path.read_text())
    frames = [f for f in manifest['frames'] if f['split'] == 'validation']
    if len(frames) != 25:
        raise ValueError('Validation25 required')
    before, after = [validate_predictions([json.loads(line) for line in p.read_text().splitlines()], frames)
                     for p in (before_path, after_path)]
    output.mkdir(parents=True, exist_ok=False)
    font_path = Path('/mnt/c/Windows/Fonts/malgun.ttf')
    font = ImageFont.truetype(str(font_path), 27)
    small = ImageFont.truetype(str(font_path), 22)
    images, proof = [], []
    for f in frames:
        image_path = manifest_path.parent/f['image']
        if sha(image_path) != f['image_sha256']:
            raise ValueError('Image changed')
        with Image.open(image_path) as source:
            im = Image.new('RGB', (2880, 640), '#14202b')
            thumbnail = source.resize((960, 540))
            for x in (0, 960, 1920):
                im.paste(thumbnail, (x, 100))
        draw = ImageDraw.Draw(im)
        titles = ['원본 + 검수된 사람 박스', '학습 전 · 사람 1클래스 변환 초기값', '학습 후 · 고정 5회 학습 마지막 가중치']
        layers = [[(b['xyxy'], None) for b in f['confirmed_person_boxes']]]
        for rows in (before, after):
            r = rows[f['frame_id']]
            layers.append([(b, s) for b, s in zip(r['boxes'], r['person_scores']) if s >= .5])
        sx, sy = 960/f['source_size'][0], 540/f['source_size'][1]
        for panel, (title, boxes) in enumerate(zip(titles, layers)):
            ox = panel*960
            draw.text((ox+12, 8), title, font=font, fill='white')
            draw.text((ox+12, 50), f"원본 {f['source_pts']:.3f}초 · 사람 위치 비교 · 넘기 판정 아님", font=small, fill='#c6d5df')
            color = '#39ffff' if panel == 0 else '#ffb347'
            for number, (box, score) in enumerate(boxes, 1):
                x1, y1, x2, y2 = box
                xy = (ox+x1*sx, 100+y1*sy, ox+x2*sx, 100+y2*sy)
                draw.rectangle(xy, outline=color, width=3)
                label = str(number) if score is None else f'{number} {score:.2f}'
                draw.text((xy[0], max(100, xy[1]-25)), label, font=small, fill=color)
        proof.append(dict(frame_id=f['frame_id'], source_pts=f['source_pts'], image_sha256=f['image_sha256'],
                          shown_box_counts=[len(layer) for layer in layers]))
        images.append(np.asarray(im))
    video = output/'validation-before-after.mp4'
    encode(video, images, Fraction(3))
    result = dict(video=str(video.resolve()), video_sha256=sha(video), frame_count=25, fps=3,
                  manifest_sha256=sha(manifest_path), before_sha256=sha(before_path), after_sha256=sha(after_path),
                  renderer_sha256=sha(__file__), font_sha256=sha(font_path), frames=proof,
                  displayed_person_threshold=.5, action_predictions=False, school_evaluation=False)
    (output/'manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(frame_count=25, video_sha256=result['video_sha256'])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'before', 'after', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    render(args.manifest, args.before, args.after, args.output)
