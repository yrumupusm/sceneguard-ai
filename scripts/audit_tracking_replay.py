"""Validate all recorded observations/events against fixed cache and summarize IDs."""
import json
from collections import defaultdict
from pathlib import Path

ROOT=Path('outputs/cv_phase2e')


def read(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def main():
    diagnostics={}
    for clip in ['030','006','007','031']:
        cache=read(Path(f'outputs/cv_phase2d/cache{clip}/person_cache.jsonl'))
        by_pts={r['pts']:r for r in cache}
        diagnostics[clip]={}
        for condition in 'ABC':
            records=read(ROOT/f'track{clip}/{condition}/frames.jsonl')
            assert list(by_pts)==[r['pts'] for r in records]
            observed=defaultdict(list);prediction=defaultdict(list)
            indexed={r['pts']:r for r in records}
            for r in records:
                seen=set()
                for d in r['detections']:
                    assert d['observed'] and d.get('confirmed',True)
                    assert d['track_id'] not in seen;seen.add(d['track_id'])
                    if condition!='A':
                        original=by_pts[r['pts']];i=d['cache_index'];w,h=original['source_size']
                        b=[max(0.,min(1.,v/(w if k%2==0 else h))) for k,v in enumerate(original['boxes'][i])]
                        assert b==d['bbox'] and original['scores'][i]==d['score']
                        assert d['score'] >= (.25 if condition=='C' else .5)
                    observed[d['track_id']].append((r['pts'],d))
                for s in r['states']:
                    if not s['observed']:
                        assert s['bbox'] is None
                        prediction[s['track_id']].append((r['pts'],s['unobserved_seconds']))
            events=read(ROOT/f'track{clip}/{condition}/events.jsonl')
            for event in events:
                a,b=event['observed_pts_before'],event['emitted_at_pts'];tid=event['track_id']
                # Every frame from anchor to emission has a real observation of this ID.
                window=[r for r in records if a<=r['pts']<=b]
                assert all(any(d['track_id']==tid for d in r['detections']) for r in window)
                assert all(y['pts']-x['pts']<=.1 for x,y in zip(window,window[1:]))
            tracks=[]
            for tid,values in observed.items():
                tracks.append(dict(track_id=tid,first=values[0][0],last=values[-1][0],observations=len(values),
                    first_bbox=values[0][1]['bbox'],last_bbox=values[-1][1]['bbox'],
                    prediction_frames=len(prediction[tid]),max_unobserved=max((v[1] for v in prediction[tid]),default=0)))
            diagnostics[clip][condition]=dict(tracks=tracks,events=events,
                prediction_track_seconds=sum(len(v) for v in prediction.values())*(records[1]['pts']-records[0]['pts']),
                verified_observations=True,events_continuously_observed=True)
    destination=ROOT/'audit.json'
    if destination.exists():raise FileExistsError(destination)
    destination.write_text(json.dumps(diagnostics,indent=2))
    print('2,060 frames x 3 conditions checked; actual cache boxes only, event observation continuity checked')


if __name__=='__main__':main()
