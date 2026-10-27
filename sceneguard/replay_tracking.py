"""EXP-0005: fixed FCOS cache, original IoU vs ByteTrack high-only / two-stage."""
import argparse
import hashlib
import json
import platform
import subprocess
import time
from pathlib import Path
import numpy as np
from .boundary import BoundaryTracker, ObservedBoundary
from .byte_adapter import ByteAdapter, SETTINGS
from .replay_thresholds import normalize, STAGE
from .run_cv import digest, safe_output, json_save


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def run(clip, root):
    cache_dir = Path(f'outputs/cv_phase2d/cache{clip}')
    meta = json.loads((cache_dir/'run.json').read_text())
    cache_path = cache_dir/'person_cache.jsonl'
    assert meta['person_cache']['stage'] == STAGE
    assert meta['person_cache']['sha256'] == digest(cache_path)
    assert meta['model_postprocess'] == dict(score_thresh=.2,topk_candidates=1000,nms_thresh=.6,detections_per_img=100)
    cache = rows(cache_path)
    baseline = rows(Path(f'outputs/cv_phase2d/replay{clip}/t050/frames.jsonl'))
    assert len(cache) == len(baseline) == meta['frames']
    assert [(x['pts'],x['native_pts'],x['time_base']) for x in cache] == [(x['pts'],x['native_pts'],x['time_base']) for x in baseline]
    intervals = np.diff([x['pts'] for x in cache])
    # This frame-step tracker is restricted to the existing near-30Hz windows.
    assert np.all(np.abs(intervals-np.median(intervals)) < 1e-6)
    output = safe_output(root/f'track{clip}');output.mkdir(parents=True,exist_ok=False)
    summary=[]
    for condition in ['A','B','C']:
        tracker = BoundaryTracker(meta['config']) if condition=='A' else ByteAdapter(condition=='C')
        boundary = None if condition=='A' else ObservedBoundary(meta['config'])
        records=[];events=[];timings=[];all_ids=set();observed_ids=set();last_obs={};gaps=[]
        for frame in cache:
            start=time.perf_counter()
            if condition=='A':
                obs, ev=tracker.step(frame['pts'],normalize(frame,.5))
                states=[d | dict(confirmed=True,state='tracked',association='high',last_observed_pts=frame['pts'],unobserved_seconds=0.) for d in obs]
                unmatched=[]
            else:
                obs, states, unmatched=tracker.step(frame)
                ev=boundary.step(frame['pts'],obs)
            timings.append((time.perf_counter()-start)*1000)
            for o in obs:
                tid=o['track_id'];observed_ids.add(tid)
                if tid in last_obs and frame['pts']-last_obs[tid] > np.median(intervals)+1e-6:
                    gaps.append(dict(track_id=tid,before=last_obs[tid],after=frame['pts'],seconds=frame['pts']-last_obs[tid]))
                last_obs[tid]=frame['pts']
            all_ids.update(d['track_id'] for d in states)
            record={k:frame[k] for k in ['pts','native_pts','time_base']} | dict(detections=obs,states=states,unmatched=unmatched)
            records.append(record)
            events.extend(e | dict(video_id=meta['video_id'],condition=condition) for e in ev)
        if condition=='A':
            assert [{k:r[k] for k in ['pts','native_pts','time_base','detections']} for r in records] == baseline
            old_events=rows(Path(f'outputs/cv_phase2d/replay{clip}/t050/events.jsonl'))
            assert [dict(e,video_id=meta['video_id'],condition='A') for e in old_events] == events
        folder=output/condition;folder.mkdir()
        for name, values in [('frames',records),('events',events),('reobservations',gaps)]:
            (folder/f'{name}.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in values))
        predicted=[s for r in records for s in r['states'] if not s['observed']]
        s=dict(condition=condition,frames=len(records),observed_boxes=sum(len(r['detections']) for r in records),
               frames_with_observations=sum(bool(r['detections']) for r in records),
               observed_ids=len(observed_ids),all_state_ids=len(all_ids),
               low_observations=sum(d.get('association')=='low_second' for r in records for d in r['detections']),
               prediction_only_states=len(predicted),max_unobserved_seconds=max((p['unobserved_seconds'] for p in predicted),default=0),
               reobservations_after_gap=len(gaps),max_reobservation_gap=max((g['seconds'] for g in gaps),default=0),
               candidates=len(events),tracking_boundary_ms=dict(mean=float(np.mean(timings)),p50=float(np.percentile(timings,50)),p95=float(np.percentile(timings,95))),
               timing_scope='CPU cache tracking and boundary only, excludes inference/decode/render/IO; diagnostics included',
               identity_ground_truth=False,config=meta['config'],cache_sha256=digest(cache_path),
               settings=SETTINGS if condition!='A' else None,low_second=condition=='C',
               native_interval=float(np.median(intervals)),baseline_A_exact=True)
        json_save(folder/'summary.json',s);summary.append(s)
    code_files=[Path('sceneguard/boundary.py'),Path(__file__),Path('sceneguard/byte_adapter.py'),*Path('sceneguard/vendor/bytetrack').glob('*.py')]
    json_save(output/'provenance.json',dict(source_cache_run=meta,head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        code_sha256={str(p):digest(p) for p in code_files},python=platform.python_version(),
        selection_document_sha256=digest(Path('docs/decisions/ADR-0010-bytetrack-cache-comparison.md'))))
    json_save(output/'summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('clips',nargs='+',choices=['030','006','007','031'])
    p.add_argument('--output-root',type=Path,default=Path('outputs/cv_phase2e'))
    args=p.parse_args()
    for clip in args.clips:run(clip,args.output_root)
