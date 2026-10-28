"""CPU-only provenance preparation for the eleven fixed native frames."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELECTION = (('030', (84, 90, 94)), ('007', (52, 64, 66)),
             ('031', (32, 40)), ('006', (119, 125, 131)))
FCOS_SHA = '99b0c9b7cfb1527d782db86b91d207f00547c792fb4103fc612b651d0a07b9e7'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def bind_cache(root=ROOT):
    records, pins = [], {}
    for suffix, times in SELECTION:
        source = 'E01_' + suffix
        cache = root / 'outputs/cv_phase2d' / ('cache' + suffix)
        run = json.loads((cache / 'run.json').read_text())
        video = root / 'data/TS_침입' / (source + '.mp4')
        if sha(video) != run['source_sha256'] or run['model_sha256'] != FCOS_SHA:
            raise ValueError('historical source or FCOS weight binding differs')
        for name in ('run.json', 'person_cache.jsonl', 'frames.jsonl'):
            p = cache / name
            pins[str(p.relative_to(root))] = sha(p)
        review_path = root / 'outputs/cv_phase2d' / ('review' + suffix) / 'review_manifest.json'
        reviews = json.loads(review_path.read_text())
        pins[str(review_path.relative_to(root))] = sha(review_path)
        rows = [json.loads(line) for line in (cache / 'person_cache.jsonl').read_text().splitlines()]
        for requested in times:
            targets = [r for r in reviews if r['requested'] == requested]
            if len(targets) != 1:
                raise ValueError('requested instant unbound in historical review manifest')
            selected = [r for r in rows if r['pts'] == targets[0]['pts']]
            if len(selected) != 1:
                raise ValueError('exact FCOS native frame missing; no automatic rerun')
            row = selected[0]
            records.append(dict(frame_id=f'{suffix}_{requested:03d}', source_id=source,
                requested_seconds=requested, pts_seconds=row['pts'], native_pts=row['native_pts'],
                time_base=row['time_base'], source_size=row['source_size'],
                source_path=str(video.relative_to(root)), source_sha256=run['source_sha256'],
                cache_path=str((cache / 'person_cache.jsonl').relative_to(root)),
                fcos_person_count=sum(score >= .5 for score in row['scores'])))
    loc = root / 'outputs/cv_phase2c/review_locations.json'
    pins[str(loc.relative_to(root))] = sha(loc)
    return records, pins


def decode(records, destination, root=ROOT):
    import av
    import numpy as np
    destination.mkdir(parents=True, exist_ok=True)
    for source in sorted({r['source_id'] for r in records}):
        group = [r for r in records if r['source_id'] == source]
        needed = {r['native_pts']: r for r in group}
        with av.open(str(root / group[0]['source_path'])) as container:
            for frame in container.decode(video=0):
                if frame.pts not in needed:
                    continue
                item = needed.pop(frame.pts)
                if str(frame.time_base) != item['time_base']:
                    raise ValueError('native time base differs')
                rgb = frame.to_ndarray(format='rgb24')
                if list(rgb.shape) != [item['source_size'][1], item['source_size'][0], 3]:
                    raise ValueError('original full RGB shape differs')
                path = destination / (item['frame_id'] + '.npy')
                if path.exists():
                    if not np.array_equal(np.load(path, allow_pickle=False), rgb):
                        raise ValueError('refuse to replace existing different RGB')
                else:
                    np.save(path, rgb, allow_pickle=False)
                item.update(rgb_path=str(path.relative_to(root)), rgb_sha256=sha(path),
                            rgb_bytes_sha256=hashlib.sha256(rgb.tobytes()).hexdigest(),
                            rgb_shape=list(rgb.shape))
                if not needed:
                    break
        if needed:
            raise ValueError('native decoder frame unavailable')
    return records


if __name__ == '__main__':
    records, pins = bind_cache()
    records = decode(records, ROOT / 'outputs/batch0002/cv/inputs')
    target = ROOT / 'runtime/BATCH-0002/cv/frame-binding.json'
    target.write_text(json.dumps(dict(frames=records, historical_pins=pins), indent=2) + '\n')
    print('Bound eleven original RGB frames; no model constructed or executed.')
