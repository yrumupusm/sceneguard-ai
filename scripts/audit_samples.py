"""Download exactly eight label-linked clips and decode them; all artifacts stay in data/."""
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request

import imageio_ffmpeg
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1] / 'data/safe_unsafe_audit'
REVISION = '7369ff1830b5f6c00f7d7383eeeaa90704bfc5b5'
BASE = f'https://huggingface.co/datasets/Voxel51/Safe_and_Unsafe_Behaviours/resolve/{REVISION}/'
LABELS = ['Safe Walkway', 'Safe Walkway Violation', 'Closed Panel Cover', 'Opened Panel Cover']


def download(remote, dest):
    if dest.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(dest.suffix + '.part')
    with urllib.request.urlopen(BASE + remote, timeout=120) as response, partial.open('wb') as out:
        while chunk := response.read(1024 * 1024):
            out.write(chunk)
    partial.replace(dest)


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / 'revision.txt').write_text(REVISION + '\n')
    for name in ['samples.json', 'metadata.json', 'frames.json', 'README.md']:
        download(name, ROOT / name)
    samples = json.loads((ROOT / 'samples.json').read_text())['samples']
    selected = []
    for label in LABELS:
        for split in ['train', 'test']:
            group = sorted((s for s in samples if s['ground_truth']['label'] == label and split in s['tags']), key=lambda s: s['filepath'])
            selected.append(group[len(group) // 2])
    assert len(selected) == len({s['filepath'] for s in selected}) == 8
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    results = []
    for sample in selected:
        remote = sample['filepath']
        path = ROOT / remote
        download(remote, path)
        assert path.stat().st_size == sample['metadata']['size_bytes'], remote
        # Decode the entire clip, not just the frames shown on the contact sheet.
        frames = imageio_ffmpeg.read_frames(str(path), pix_fmt='rgb24')
        meta = next(frames)
        count = 0
        for _ in frames:
            count += 1
        check = subprocess.run([ffmpeg, '-v', 'error', '-xerror', '-i', str(path), '-f', 'null', '-'], capture_output=True, text=True)
        check.check_returncode()
        preview = ROOT / 'previews' / path.stem
        preview.mkdir(parents=True, exist_ok=True)
        # Inspect 12 evenly spaced frames per clip; exact requested timestamps recorded.
        times = [round(i * (meta['duration'] - 0.08) / 11, 3) for i in range(12)]
        sheet = Image.new('RGB', (1280, 4 * 384), 'white')
        draw = ImageDraw.Draw(sheet)
        for i, timestamp in enumerate(times):
            dest = preview / f'{i:02d}.png'
            subprocess.run([ffmpeg, '-v', 'error', '-ss', str(timestamp), '-i', str(path), '-frames:v', '1', '-y', str(dest)], check=True)
            with Image.open(dest) as im:
                im.thumbnail((640, 360))
                x, y = (i % 2) * 640, (i // 2) * 256
                # 640x360 rendered to 448x252 for six rows on a compact sheet.
                im.thumbnail((448, 252))
                sheet.paste(im, (x, y + 4))
                draw.text((x + 450, y + 15), f'{path.stem}\n{timestamp:.3f}s', fill='black')
        sheet.save(ROOT / 'previews' / f'{path.stem}.jpg')
        row = {'id': sample['_id']['$oid'], 'filepath': remote, 'label': sample['ground_truth']['label'], 'tags': sample['tags'], 'url': BASE + remote, 'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'source_metadata': sample['metadata'], 'decoded_metadata': meta, 'decoded_frames': count, 'decode_errors': check.stderr, 'preview_times': times}
        results.append(row)
        (ROOT / 'manifest.json').write_text(json.dumps({'revision': REVISION, 'samples': results}, indent=2))
        print(path.name, row['label'], meta['size'], meta['fps'], meta['duration'], count, flush=True)
    print('Total bytes:', sum(r['bytes'] for r in results))


if __name__ == '__main__':
    main()
