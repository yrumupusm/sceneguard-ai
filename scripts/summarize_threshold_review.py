"""Summarize cached replay diagnostics, never identity/accuracy ground truth."""
import json
from pathlib import Path


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def main():
    root = Path('outputs/cv_phase2d')
    result = {}
    for clip in ['030', '006', '007', '031']:
        manifest = json.loads((root / f'review{clip}/review_manifest.json').read_text())
        old = json.loads(Path(f'outputs/cv_phase2b/review{clip}/review_manifest.json').read_text())
        assert manifest == old
        result[clip] = []
        for tag in ['050', '040', '030', '025']:
            folder = root / f'replay{clip}/t{tag}'
            rows = read_rows(folder / 'frames.jsonl')
            summary = json.loads((folder / 'summary.json').read_text())
            tracks = {}
            for frame in rows:
                for d in frame['detections']:
                    tracks.setdefault(d['track_id'], []).append((frame['pts'], d))
            longest = max(tracks, key=lambda tid: tracks[tid][-1][0] - tracks[tid][0][0])
            span = tracks[longest]
            # Fixed visually reviewed anchor frames, no model-selected good frames.
            anchor_pts = {'030': 84., '007': 50., '031': 30.}.get(clip)
            anchors = []
            if anchor_pts is not None:
                anchor = next(r for r in rows if r['pts'] == anchor_pts)
                for d in anchor['detections']:
                    if d['score'] < .5:
                        continue  # Same original high-score boxes across all conditions.
                    values = tracks[d['track_id']]
                    anchors.append(dict(bbox=d['bbox'], track_id=d['track_id'],
                                        first=values[0][0], last=values[-1][0], frames=len(values)))
            selected = {r['pts']: len(r['detections']) for r in rows}
            climb_tracks = []
            if clip == '030':
                for d in next(r for r in rows if r['pts'] == 90.)['detections']:
                    values = tracks[d['track_id']]
                    climb_tracks.append(dict(score=d['score'], track_id=d['track_id'],
                                             first=values[0][0], last=values[-1][0], frames=len(values)))
            result[clip].append(dict(threshold=summary['threshold'],
                review_counts=[selected[m['pts']] for m in manifest],
                longest=dict(track_id=longest, first=span[0][0], last=span[-1][0],
                             first_bbox=span[0][1]['bbox'], last_bbox=span[-1][1]['bbox']),
                anchor_tracks=anchors, climb_90_tracks=climb_tracks, identity_verified=False))
    destination = root / 'temporal_review.json'
    if destination.exists():
        raise FileExistsError(destination)
    destination.write_text(json.dumps(result, indent=2))
    print(destination)


if __name__ == '__main__':
    main()
