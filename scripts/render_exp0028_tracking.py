"""Render preserved EXP-0028 CPU replay; display only, no tracker or inference.

Writes full-frame and display-crop continuous RAW/strict/gap videos, native-PTS
receipts, and per-ID observation diagnostics under a fresh local output folder.
"""
import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

import av
from PIL import Image, ImageDraw, ImageFont

CONDITIONS = ('strict', 'gap')
FONT_PATH = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
FONT = ImageFont.truetype(FONT_PATH, 14)
COLORS = ('#ffcc44', '#66ff66', '#ff7777', '#55ddff', '#ffaaee', '#bbbbff', '#ffffff')
CROPS = {'030': (650, 300, 1250, 840), '007': (1080, 100, 1680, 640)}


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def timing_key(row):
    return row['native_pts'] * Fraction(row['time_base'])


def validate_record(record, cached):
    """Reject a shifted video overlay or boxes not supported by cached input."""
    if timing_key(record) != timing_key(cached) or record['pts'] != cached['pts']:
        raise ValueError('Native timing mismatch')
    w, h = cached['source_size']
    for item in record['states']:
        if not item['observed']:
            continue
        index = item['cache_index']
        expected = [v / (w if i % 2 == 0 else h)
                    for i, v in enumerate(cached['boxes'][index])]
        if (item['score'] != cached['scores'][index]
                or max(abs(a-b) for a, b in zip(item['bbox'], expected)) > 1e-7):
            raise ValueError('Overlay observation differs from preserved cache')


def strict_reproduction(old, current):
    frames_exact = (old/'frames.jsonl').read_bytes() == (current/'frames.jsonl').read_bytes()
    clean = lambda values: [{k: v for k, v in r.items() if k != 'condition'} for r in values]
    events_exact = clean(rows(old/'events.jsonl')) == clean(rows(current/'events.jsonl'))
    gaps_exact = rows(old/'reobservations.jsonl') == rows(current/'reobservations.jsonl')
    if not (frames_exact and events_exact and gaps_exact):
        raise ValueError('Strict failed historical EXP-0005 C reproduction')
    return dict(frames_byte_exact=frames_exact, events_exact_except_condition=events_exact,
                reobservations_exact=gaps_exact)


def per_id(records, reobservations):
    result = {}
    for row in records:
        for item in row['detections']:
            tid = item['track_id']
            entry = result.setdefault(tid, dict(track_id=tid, first_observed_pts=row['pts'],
                last_observed_pts=row['pts'], observed_boxes=0, low_observations=0,
                reconnects=[], physical_identity='unverified'))
            entry['last_observed_pts'] = row['pts']
            entry['observed_boxes'] += 1
            entry['low_observations'] += item['association'] == 'low_second'
    for gap in reobservations:
        result[gap['track_id']]['reconnects'].append(gap)
    return list(result.values())


def event_labels(events, pts):
    """Emission flashes follow emitted_at_pts, never the inferred candidate time."""
    labels = []
    for event in events:
        if 0 <= pts - event['emitted_at_pts'] < 1.0:
            labels.append(f"ALERT #{event['track_id']} emit {event['emitted_at_pts']:.3f} "
                          f"candidate {event['candidate_pts']:.3f}")
    return labels


def dashed(draw, box, color):
    x1, y1, x2, y2 = box
    for y in (y1, y2):
        for x in range(math.floor(x1), math.ceil(x2), 10):
            draw.line((x, y, min(x+5, x2), y), fill=color, width=2)
    for x in (x1, x2):
        for y in range(math.floor(y1), math.ceil(y2), 10):
            draw.line((x, y, x, min(y+5, y2)), fill=color, width=2)


def panel(original, record, cfg, events, title, crop=None):
    w, h = (600, 540) if crop else (640, 360)
    tile = original.crop(crop) if crop else original.resize((w, h))
    canvas = Image.new('RGB', (w, h+240))
    d = ImageDraw.Draw(tile)
    source_w, source_h = original.size
    xy = (lambda x, y: (x*source_w-crop[0], y*source_h-crop[1])) if crop else (
          lambda x, y: (x*w, y*h))
    descriptions = []
    if record is not None:
        d.rectangle([xy(*cfg['roi'][:2]), xy(*cfg['roi'][2:])], outline='yellow', width=1)
        d.line([xy(*p) for p in cfg['line']], fill='white', width=2)
        for item in record['states']:
            pred = not item['observed']
            box = item['prediction_bbox'] if pred else item['bbox']
            x1, y1 = xy(*box[:2]); x2, y2 = xy(*box[2:])
            # Even a large prediction is display-only; clip drawing to the tile.
            if x2 < 0 or x1 > w or y2 < 0 or y1 > h:
                continue
            color = 'magenta' if pred else COLORS[item['track_id'] % len(COLORS)]
            if pred:
                dashed(d, (max(-10, x1), max(-10, y1), min(w+10, x2), min(h+10, y2)), color)
                label = f"#{item['track_id']} PRED {item['unobserved_seconds']:.2f}s"
            else:
                d.rectangle((x1, y1, x2, y2), outline=color, width=2)
                if item['confirmed']:
                    x = (x1+x2)/2
                    d.ellipse((x-3, y2-3, x+3, y2+3), fill=color)
                label = f"#{item['track_id']} {item['score']:.3f} " + (
                    'L' if item['association'] == 'low_second' else 'H')
                label += ' OBS' if item['confirmed'] else ' UNCONFIRMED'
            d.text((max(0, x1), max(0, y1-17)), f"#{item['track_id']}", font=FONT,
                   fill=color, stroke_width=1, stroke_fill='black')
            descriptions.append((label, color))
    canvas.paste(tile, (0, 40)); d = ImageDraw.Draw(canvas)
    d.text((8, 10), title, font=FONT, fill='white')
    top = h+48
    if record is None:
        labels = ['RAW original video; display resize/crop only.',
                  'Solid: measured box | dashed magenta: prediction',
                  'H >= .50 | L >= .25 second association',
                  'UNCONFIRMED: excluded from boundary evidence',
                  'Dot: bbox bottom center; not anatomical feet.',
                  'ID colors/numbers are not physical identity truth.',
                  'White: configured boundary | yellow: ROI',
                  'Alerts are candidates; no legal/completion decision.']
        for i, text in enumerate(labels):
            d.text((8, top+i*21), text, font=FONT, fill='white')
    else:
        for i, (text, color) in enumerate(descriptions):
            d.text((8+(i % 2)*(w//2), top+(i//2)*20), text, font=FONT, fill=color)
        alerts = event_labels(events, record['pts'])
        for i, label in enumerate(alerts):
            d.text((8, h+165+i*20), label, font=FONT, fill='yellow')
        emitted = sum(e['emitted_at_pts'] <= record['pts']+1e-9 for e in events)
        d.text((8, h+213), f'Actual observed: {len(record["detections"])} | emitted total: {emitted}',
               font=FONT, fill='white')
    return canvas


class Writer:
    def __init__(self, path, size, rate):
        self.output = av.open(str(path), 'w')
        self.stream = self.output.add_stream('libx264', rate=rate)
        self.stream.width, self.stream.height = size
        self.stream.pix_fmt = 'yuv420p'
        self.stream.options = {'crf': '19', 'preset': 'veryfast'}
    def add(self, canvas, timestamp, first):
        frame = av.VideoFrame.from_image(canvas)
        frame.pts = timestamp['native_pts']-first
        frame.time_base = Fraction(timestamp['time_base'])
        for packet in self.stream.encode(frame):
            self.output.mux(packet)
    def close(self):
        for packet in self.stream.encode():
            self.output.mux(packet)
        self.output.close()


def verify_video(path, expected):
    with av.open(str(path)) as source:
        actual = [frame.pts * frame.time_base for frame in source.decode(video=0)]
    origin = timing_key(expected[0])
    wanted = [timing_key(row)-origin for row in expected]
    if actual != wanted:
        raise ValueError('Rendered MP4 lost or shifted native frame timestamps')
    return dict(path=str(path), frames=len(actual), bytes=path.stat().st_size,
                sha256=digest(path), native_relative_timestamps_exact=True,
                duration_seconds=float(actual[-1] + wanted[1]-wanted[0]))


def render(clip, root, source_root, historical_root, cache_root, reid_root=None):
    track = root/f'track{clip}'
    conditions = CONDITIONS if reid_root is None else ('gap', 'botsort_reid')
    saved_folders = {c: track/c for c in conditions}
    if reid_root is not None:
        saved_folders['botsort_reid'] = reid_root/f'track{clip}/botsort_reid'
        summary = json.loads((saved_folders['botsort_reid']/'summary.json').read_text())
        if summary.get('status') != 'complete' or not summary.get('uses_reid'):
            raise ValueError('ReID comparison must be complete with actual ReID enabled')
    folder = root/(f'review{clip}' if reid_root is None else f'review{clip}_reid')
    if folder.exists() or folder.is_symlink():
        raise FileExistsError('Review folder must be new')
    cache_folder = cache_root/f'cache{clip}'
    cache = rows(cache_folder/'person_cache.jsonl')
    metadata = json.loads((cache_folder/'run.json').read_text())
    source_path = source_root/f'E01_{clip}.mp4'
    if digest(source_path) != metadata['source_sha256']:
        raise ValueError('Source video SHA differs from preserved detector input')
    protected = [source_path, *cache_folder.glob('*.json*')]
    protected += [p for p in (historical_root/f'track{clip}').rglob('*') if p.is_file()]
    protected += [p for p in track.rglob('*') if p.is_file()]
    if reid_root is not None:
        protected += [p for p in saved_folders['botsort_reid'].rglob('*') if p.is_file()]
    protected += [Path(p) for p in ('sceneguard/boundary.py', 'sceneguard/byte_adapter.py',
                                    'sceneguard/gap_boundary.py', 'sceneguard/replay_gap_tracking.py')]
    protected += list(Path('sceneguard/vendor/bytetrack').glob('*.py'))
    before = {str(p): digest(p) for p in protected}
    saved = {c: rows(saved_folders[c]/'frames.jsonl') for c in conditions}
    events = {c: rows(saved_folders[c]/'events.jsonl') for c in conditions}
    cfg = json.loads((track/'strict/summary.json').read_text())['config']
    reproduction = strict_reproduction(historical_root/f'track{clip}/C', track/'strict')
    for condition in conditions:
        if len(saved[condition]) != len(cache):
            raise ValueError('Cache and replay frame counts differ')
        for record, cached in zip(saved[condition], cache):
            validate_record(record, cached)
    folder.mkdir(parents=True, exist_ok=False)
    suffix = 'original_strict_gap' if reid_root is None else 'original_gap_reid'
    full = folder/f'continuous_{suffix}.mp4'
    focus = folder/f'focused_{suffix}.mp4'
    rate = 1/(timing_key(cache[1])-timing_key(cache[0]))
    writers = [Writer(full, (1920, 600), rate), Writer(focus, (1800, 780), rate)]
    native = []
    try:
        with av.open(str(source_path)) as source:
            stream = source.streams.video[0]
            source.seek(int(timing_key(cache[0])/stream.time_base), stream=stream)
            index = 0
            for frame in source.decode(video=0):
                instant = frame.pts*frame.time_base
                if instant < timing_key(cache[0]):
                    continue
                if index == len(cache):
                    break
                if instant != timing_key(cache[index]):
                    raise ValueError('Decoded source skipped/shifted a cached native frame')
                stamp = {k: cache[index][k] for k in ('pts', 'native_pts', 'time_base')}
                native.append(stamp)
                original = frame.to_image()
                for writer, crop, width, height in ((writers[0], None, 640, 600),
                                                    (writers[1], CROPS[clip], 600, 780)):
                    canvas = Image.new('RGB', (width*3, height))
                    for n, condition in enumerate(('RAW', *conditions)):
                        record = None if condition == 'RAW' else saved[condition][index]
                        display = 'BoT-ReID' if condition == 'botsort_reid' else condition
                        title = f'E01_{clip} {display} PTS {stamp["pts"]:.6f} '
                        title += f'[{stamp["native_pts"]} x {stamp["time_base"]}]'
                        canvas.paste(panel(original, record, cfg, events.get(condition, []), title, crop),
                                     (n*width, 0))
                    writer.add(canvas, stamp, cache[0]['native_pts'])
                    selected = [e['emitted_at_pts'] for ev in events.values() for e in ev]
                    if crop and (index in (0, len(cache)-1) or
                                 any(abs(stamp['pts']-t) < 1e-7 for t in selected)):
                        canvas.save(folder/f'focused_{stamp["pts"]:.6f}.jpg', quality=94)
                index += 1
        if len(native) != len(cache):
            raise ValueError('Source ended before final cached frame')
    finally:
        for writer in writers:
            writer.close()
    videos = [verify_video(path, native) for path in (full, focus)]
    if any(digest(Path(p)) != sha for p, sha in before.items()):
        raise ValueError('Preserved input/core/historical file changed during render')
    diagnostics = {}
    for c in conditions:
        diagnostics[c] = dict(per_id=per_id(saved[c], rows(saved_folders[c]/'reobservations.jsonl')),
            events=events[c], prediction_only_states=sum(not s['observed'] for r in saved[c] for s in r['states']),
            unconfirmed_observations=sum(s['observed'] and not s['confirmed'] for r in saved[c] for s in r['states']))
    receipt = dict(status='complete', clip=clip, frames=len(native), first_pts=native[0]['pts'],
        last_pts=native[-1]['pts'], source_sha256=metadata['source_sha256'],
        display_crop=list(CROPS[clip]), renderer_runs_inference=False,
        comparison_uses_reid=reid_root is not None, conditions=list(conditions),
        identity_verified=False, strict_exp0005_C_reproduction=reproduction,
        videos=videos, diagnostics=diagnostics, native_frames=native,
        preserved_sha256=before, renderer_sha256=digest(Path(__file__)))
    (folder/'render_receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps({k: receipt[k] for k in ('clip', 'frames', 'first_pts', 'last_pts', 'videos',
                                              'strict_exp0005_C_reproduction')}), flush=True)
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('clips', nargs='+', choices=['030', '007'])
    p.add_argument('--output-root', type=Path, default=Path('outputs/exp0028/practical-v1'))
    p.add_argument('--source-root', type=Path, default=Path('data/TS_침입'))
    p.add_argument('--historical-root', type=Path, default=Path('outputs/cv_phase2e'))
    p.add_argument('--cache-root', type=Path, default=Path('outputs/cv_phase2d'))
    p.add_argument('--reid-root', type=Path,
                   help='Read completed BoT-SORT/ReID results and write separate RAW/gap/ReID reviews')
    args = p.parse_args()
    if (not args.output_root.resolve().is_relative_to(Path('outputs').resolve())
            or args.output_root.is_symlink()
            or any(parent.is_symlink() for parent in args.output_root.parents)):
        p.error('Review media must stay under a non-symlink local outputs directory')
    for clip in args.clips:
        render(clip, args.output_root, args.source_root, args.historical_root, args.cache_root,
               args.reid_root)


if __name__ == '__main__':
    main()
