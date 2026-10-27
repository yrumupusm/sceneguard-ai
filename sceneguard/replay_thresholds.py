"""Replay only model-returned person boxes; no torch, model, NMS or raw-head recovery."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from .boundary import BoundaryTracker
from .run_cv import digest, json_save, safe_output

THRESHOLDS=(.5,.4,.3,.25)
STAGE='model_return_after_internal_filters_nms_global_cap_before_project_score'

def normalize(frame, threshold):
    width,height=frame['source_size']
    if len(frame['boxes']) != len(frame['scores']):raise ValueError('Cache arrays mismatch')
    result=[]
    for box,score in zip(frame['boxes'],frame['scores']):
        if not math.isfinite(score) or len(box)!=4 or not all(math.isfinite(v) for v in box):
            raise ValueError('Invalid cached detection')
        if score < threshold:continue
        b=[max(0.,min(1.,v/(width if i%2==0 else height))) for i,v in enumerate(box)]
        if b[0]<b[2] and b[1]<b[3]:result.append(dict(bbox=b,score=score))
    return result

def replay(cache, config, threshold):
    cfg=config | {'score_threshold':threshold}
    tracker=BoundaryTracker(cfg)
    frames=[];events=[];spans={}
    for frame in cache:
        rows,ev=tracker.step(frame['pts'],normalize(frame,threshold))
        frames.append({k:frame[k] for k in ['pts','native_pts','time_base']} | {'detections':rows})
        events.extend(ev)
        for row in rows:spans.setdefault(row['track_id'],[]).append(frame['pts'])
    durations=[max(v)-min(v) for v in spans.values()]
    return frames,events,dict(frames=len(frames),frames_with_person=sum(bool(f['detections']) for f in frames),
        person_boxes=sum(len(f['detections']) for f in frames),candidate_count=len(events),
        tracker_stats=tracker.stats,max_track_span=max(durations,default=0.),
        tracks_with_span_at_least_1s=sum(v>=1. for v in durations),
        timing_type='cache_replay_only_no_inference_fps',identity_verified=False)

def run(cache_dir,baseline,output):
    meta=json.loads((cache_dir/'run.json').read_text())
    old=json.loads((baseline/'run.json').read_text())
    assert meta['status']=='complete'
    assert meta['person_cache']['schema']==1 and meta['person_cache']['stage']==STAGE
    assert digest(cache_dir/'person_cache.jsonl')==meta['person_cache']['sha256']
    assert meta['model_postprocess']==dict(score_thresh=.2,topk_candidates=1000,nms_thresh=.6,detections_per_img=100)
    for k in ['source_sha256','config_sha256','model_sha256','model_input_observed','requested_window','frames']:
        assert meta[k]==old[k],k
    for k in ['sceneguard/boundary.py','sceneguard/detectors.py']:
        assert meta['code_file_sha256'][k]==old['code_file_sha256'][k],k
    cache=[json.loads(x) for x in (cache_dir/'person_cache.jsonl').read_text().splitlines()]
    old_frames=[json.loads(x) for x in (baseline/'frames.jsonl').read_text().splitlines()]
    collected=[json.loads(x) for x in (cache_dir/'frames.jsonl').read_text().splitlines()]
    assert collected==old_frames, 'Fresh 0.5 inference changed'
    assert len(cache)==meta['frames'] and [r['pts'] for r in cache]==[r['pts'] for r in old_frames]
    output=safe_output(output);output.mkdir(parents=True,exist_ok=False)
    summaries=[]
    for threshold in THRESHOLDS:
        folder=output/f't{round(threshold*100):03d}';folder.mkdir()
        frames,events,stats=replay(cache,meta['config'],threshold)
        cfg=meta['config'] | {'score_threshold':threshold}
        json_save(folder/'config.json',cfg)
        for event in events:
            event.update(video_id=meta['video_id'],boundary_id=cfg['boundary_id'],
                model_sha256=meta['model_sha256'],config_sha256=digest(folder/'config.json'),
                final_person_score=threshold,source_cache_sha256=meta['person_cache']['sha256'])
        for name,rows in [('frames',frames),('events',events)]:
            with (folder/(name+'.jsonl')).open('w') as f:
                for row in rows:f.write(json.dumps(row)+'\n')
        if threshold==.5:
            assert frames==old_frames, '0.5 replay does not reproduce baseline'
            old_events=[json.loads(x) for x in (baseline/'events.jsonl').read_text().splitlines()]
            # Provenance changes; compare event semantics to the original run.
            for before,after in zip(old_events,events):
                for k in ['track_id','candidate_interval','emitted_at_pts','direction']:
                    assert before[k]==after[k]
            assert len(old_events)==len(events)
        stats.update(threshold=threshold,video_id=meta['video_id'],config=cfg,
            base_config_sha256=meta['config_sha256'],effective_config_sha256=digest(folder/'config.json'),
            source_cache_sha256=meta['person_cache']['sha256'],
            replay_code_sha256=digest(Path(__file__)),baseline_0_5_exact=True,
            model_sha256=meta['model_sha256'],requested_window=meta['requested_window'])
        json_save(folder/'summary.json',stats);summaries.append(stats)
    json_save(output/'summary.json',summaries)
    print(json.dumps([{'threshold':s['threshold'],'frames':s['frames'],'boxes':s['person_boxes'],
                      'candidates':s['candidate_count']} for s in summaries]))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['cache','baseline','output']:p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();run(a.cache,a.baseline,a.output)
