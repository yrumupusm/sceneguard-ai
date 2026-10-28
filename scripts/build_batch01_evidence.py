"""Local display only: continuous source beside the frozen 2 fps source samples.

Never used as model input. No inference, external upload, or old output overwrite.
"""
import argparse
import json
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageDraw


def build(asset_root, output_root, manifest_path):
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    output_root.mkdir(parents=True, exist_ok=False)
    records = []
    for clip in manifest['clips']:
        cid = clip['id']
        cached = asset_root / 'outputs/vlm_exp0007' / cid
        samples = np.load(cached / 'rgb.npy', mmap_mode='r')
        source = json.loads((cached / 'input.json').read_text())
        pts = [f['pts'] for f in source['frames']]
        target = output_root / (cid + '-source-and-samples.mp4')
        observed = []
        with av.open(str(asset_root / 'data/TS_침입' / (clip['source'] + '.mp4'))) as inp, av.open(str(target), 'w') as out:
            v = inp.streams.video[0]
            dest = out.add_stream('libx264', rate=v.average_rate)
            dest.width, dest.height, dest.pix_fmt = 1280, 414, 'yuv420p'
            dest.options = {'crf': '19', 'preset': 'fast'}
            inp.seek(int(max(0, clip['start']-1) / v.time_base), stream=v)
            for frame in inp.decode(video=0):
                t = float(frame.pts * frame.time_base)
                if t < clip['start'] - 1e-9:
                    continue
                if t >= clip['end'] - 1e-9:
                    break
                index = max(i for i, p in enumerate(pts) if p <= t + 1e-9)
                canvas = Image.new('RGB', (1280, 414))
                canvas.paste(frame.to_image().resize((640, 360)), (0, 54))
                canvas.paste(Image.fromarray(np.asarray(samples[index])).resize((640, 360)), (640, 54))
                draw = ImageDraw.Draw(canvas)
                draw.text((8, 7), f'{cid} CONTINUOUS SOURCE | ORIGINAL PTS {t:.6f}', fill='white')
                draw.text((648, 7), f'2 FPS SOURCE SAMPLE | ORIGINAL PTS {pts[index]:.6f}', fill='white')
                draw.text((8, 29), 'LOCAL HUMAN REVIEW ONLY - NOT MODEL INPUT', fill='white')
                draw.text((648, 29), 'HELD BETWEEN SAMPLES; BEFORE MODEL-SPECIFIC RESIZE', fill='white')
                output_frame = av.VideoFrame.from_image(canvas)
                output_frame.pts = None
                for packet in dest.encode(output_frame):
                    out.mux(packet)
                observed.append({'display_index': len(observed), 'original_pts': t,
                                 'native_pts': frame.pts, 'time_base': str(frame.time_base),
                                 'sample_index': index, 'sample_pts': pts[index]})
            for packet in dest.encode():
                out.mux(packet)
        record = {'clip_id': cid, 'source_hash_from_frozen_input': source['source_sha256'],
                  'display_only': True, 'model_input': False, 'frames': observed}
        (output_root / (cid + '-display-map.json')).write_text(json.dumps(record, indent=2))
        records.append({'clip_id': cid, 'file': target.name, 'frames': len(observed)})
        print(json.dumps(records[-1]), flush=True)
    (output_root / 'index.json').write_text(json.dumps(records, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--asset-root', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, default=Path('configs/vlm_exp0007_manifest.json'))
    args = parser.parse_args()
    build(args.asset_root, args.output_root, args.manifest)
