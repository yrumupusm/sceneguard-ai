"""Local saved-path inspection: no flow, scoring changes, labels or model calls."""
import argparse
import base64
from collections import defaultdict, deque
import csv
from fractions import Fraction
import json
from pathlib import Path
import time

import numpy as np

from .gate_transition import geometry, inside_polygon, cue_metrics
from .transition_diagnostics import sha, write_json, parse_range


def quantiles(values):
    return None if not values else dict(zip(('min','p25','median','p75','max'),
        map(float, np.quantile(values, [0,.25,.5,.75,1]))))


def geometry_metrics(before, after, scene, height):
    a,v,length=geometry(scene['line'], scene['source_size'])
    p,q=np.asarray(before),np.asarray(after)
    normal=np.array([-v[1],v[0]])/length
    tangent=v/length
    signed=lambda x:(x-a)@normal
    s,t=signed(p),signed(q)
    along=(q-a)@v/(length*length)
    distance=np.linalg.norm(q-(a+np.clip(along,0,1)[:,None]*v),axis=1)
    d=q-p; residual=d-np.median(d,axis=0)
    return dict(distance_px=float(np.median(distance)), height_px=height,
        distance_over_height=float(np.median(distance))/max(16.,height),
        median_dx_px=float(np.median(d[:,0])), median_dy_px=float(np.median(d[:,1])),
        median_normal_px=float(np.median(d@normal)), median_tangent_px=float(np.median(d@tangent)),
        upward_q80_px=float(np.quantile(np.maximum(0,-d[:,1]),.8)),
        deformation_q80_px=float(np.quantile(np.linalg.norm(residual,axis=1),.8)),
        progress_q75_px=float(np.quantile(np.maximum(0,np.abs(s)-np.abs(t)),.75)),
        median_signed_before_px=float(np.median(s)), median_signed_after_px=float(np.median(t)),
        beyond_segment_points=int(((along<0)|(along>1)).sum()))


def analyze(rows, scene, policy):
    """Inspect every live window, including newborn windows without a signal."""
    size=np.asarray(scene['source_size']); offset=np.zeros(2)
    histories=defaultdict(dict); births={}; last={}; allrows=[]; seedrows=[]
    speeds=defaultdict(lambda:deque(maxlen=90)); camera=[]; max_component_error=0.
    a,v,length=geometry(scene['line'],size)
    for row in rows:
        at=row['pts']; step=np.asarray(row['camera_step_pixels']); offset+=step
        camera.append(dict(pts=at,supported=row['camera_support'],dx=float(step[0]),dy=float(step[1]),
                           norm=float(np.linalg.norm(step))))
        signals={s['window_id']:s for s in row['signals']}
        best=max(signals.values(),key=lambda s:s['score'],default=None)
        born=[]
        for path in row['point_paths']:
            wid=path['window_id']; ids=path['point_ids']; q=np.asarray(path['points_original_pixels'])-offset
            if wid not in births:
                box=next(b for b in row['actual_boxes'] if b['cache_index']==path['seed_cache_index'])
                births[wid]=dict(seed_pts=at, height_px=(box['bbox'][3]-box['bbox'][1])*size[1],
                    seed_points=len(ids), cache_index=path['seed_cache_index'], bbox=box['bbox'],
                    track_ids=path['seed_track_ids'])
                born.append(path['seed_cache_index'])
            birth=births[wid]; prev=last.get(wid,len(ids))
            record=dict(pts=at,frame_index=row['frame_index'],window_id=wid,seed_pts=birth['seed_pts'],
                age_seconds=at-birth['seed_pts'],seed_points=birth['seed_points'],point_count=len(ids),
                lost_since_previous=prev-len(ids),retention=len(ids)/birth['seed_points'],
                signal_present=wid in signals,winning=best is not None and wid==best['window_id'],
                camera_support=row['camera_support'],camera_step_px=float(np.linalg.norm(step)),
                height_px=birth['height_px'],seed_cache_index=birth['cache_index'])
            if wid in signals:
                s=signals[wid]; old=histories[wid][s['reference_pts']]
                p=np.asarray([old[k] for k in ids]); reference_age=at-s['reference_pts']
                older=[speed for t,speed in speeds[wid] if t<=s['reference_pts']]
                prior=float(np.median(older)) if older else 0.
                reproduced=cue_metrics(p,q,line=scene['line'],size=size,height=birth['height_px'],
                    prior_speed=prior,dt=reference_age)
                component_names=('proximity','crossing_fraction','upward_image_motion','local_deformation',
                    'normal_progress','motion_change','coherence','speed_heights_per_second')
                error=max(abs(reproduced[k]-s[k]) for k in component_names)
                max_component_error=max(max_component_error,error)
                if error>1e-5: raise ValueError(f'Geometry components disagree: {at} {wid} {error}')
                speeds[wid].append((at,s['speed_heights_per_second']))
                record.update(geometry_metrics(p,q,scene,birth['height_px']))
                record.update({k:s[k] for k in component_names})
                record.update(score=s['score'],route=s['route'],reference_pts=s['reference_pts'],
                    reference_age_seconds=reference_age,prior_speed=prior,prior_speed_samples=len(older),
                    local_ceiling=s['proximity']*s['upward_image_motion']*(.8+.2*min(1,len(ids)/8)))
            histories[wid][at]=dict(zip(ids,q.tolist()));last[wid]=len(ids);allrows.append(record)
        # Every scheduled tick is known from the first frame and the fixed interval.
        tick=abs((at-rows[0]['pts'])/policy['seed_interval']-round((at-rows[0]['pts'])/policy['seed_interval']))<1e-7
        if tick:
            for box in row['actual_boxes']:
                if box.get('observed') is False or box.get('bbox') is None:continue
                b=np.asarray(box['bbox'])*np.tile(size,2); center=(b[:2]+b[2:])/2
                t=np.clip(np.dot(center-a,v)/(length*length),0,1)
                eligible=(box['score']>=policy['seed_score'] and
                    np.linalg.norm(center-a-t*v)<=.9*max(16.,b[3]-b[1]) and
                    inside_polygon(tuple(center/size),scene['approach_polygon']))
                if eligible:
                    seedrows.append(dict(pts=at,cache_index=box['cache_index'],score=box['score'],
                        seeded=box['cache_index'] in born,capacity_reached=row['windows']>=policy['max_windows'],
                        no_seed_reason='capacity_or_corner_count_not_saved' if box['cache_index'] not in born else None,
                        raw_track_ids=box['track_ids'],bbox=box['bbox']))
    return allrows,seedrows,camera,births,max_component_error


def summarize(records,seeds,camera,ranges):
    result=[]
    for spec in ranges:
        rs=[r for r in records if spec['start']<=r['pts']<=spec['end']]
        ss=[r for r in rs if r['signal_present']]; non=[r for r in ss if not r['winning']]
        seed=[r for r in seeds if spec['start']<=r['pts']<=spec['end']]
        cam=[r for r in camera if spec['start']<=r['pts']<=spec['end']]
        fields=('score','proximity','upward_image_motion','local_deformation','normal_progress',
            'motion_change','coherence','distance_px','height_px','distance_over_height',
            'median_dx_px','median_dy_px','median_normal_px','median_tangent_px',
            'reference_age_seconds','prior_speed','point_count','retention','local_ceiling')
        result.append(dict(**spec,live_window_frames=len(rs),signals=len(ss),
            unique_live_windows=len({r['window_id'] for r in rs}),nonwinning_signals=len(non),
            nonwinning_highest_score=max((r['score'] for r in non),default=None),
            proximity_ceiling_below_threshold=sum(r['proximity']*(.8+.2*min(1,r['point_count']/8))<.55 for r in ss),
            local_ceiling_below_threshold=sum(r['local_ceiling']<.55 for r in ss),
            crossing_signals=sum(r['crossing_fraction']>0 for r in ss),
            point_losses=sum(r['lost_since_previous'] for r in rs),
            seeding_eligible_boxes=len(seed),seeded_boxes=sum(r['seeded'] for r in seed),
            unseeded_at_capacity=sum(not r['seeded'] and r['capacity_reached'] for r in seed),
            unseeded_below_capacity=sum(not r['seeded'] and not r['capacity_reached'] for r in seed),
            camera_unsupported_frames=sum(not r['supported'] for r in cam),
            camera_step_px=quantiles([r['norm'] for r in cam]),
            distributions={k:quantiles([r[k] for r in ss]) for k in fields}))
    return result


def execute(directory,output,ranges):
    begin=time.perf_counter();directory=Path(directory);output=Path(output)
    request=json.loads((directory/'request.json').read_text())
    scene_path=next(Path(p) for p in request['input_sha256'] if 'scene' in p and p.endswith('.json'))
    paths=[directory/name for name in ('request.json','summary.json','frame-evidence.jsonl','transition-events.json',
        'baseline-cards.json','transition-only-cards.json','combined-cards.json')]
    paths.extend(map(Path,request['input_sha256']))
    before={str(p):sha(p) for p in paths}
    for p,expected in request['input_sha256'].items():
        if before[p]!=expected:raise ValueError('Protected input differs: '+p)
    if output.exists() or not output.resolve().is_relative_to(Path('outputs').resolve()):
        raise ValueError('New outputs directory required')
    output.mkdir(parents=True)
    rows=[json.loads(line) for line in (directory/'frame-evidence.jsonl').read_text().splitlines()]
    scene=json.loads(scene_path.read_text()); records,seeds,camera,births,error=analyze(rows,scene,request['policy'])
    fields=sorted(set().union(*(r.keys() for r in records)))
    with (output/'all-live-windows.csv').open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(records)
    write_json(output/'seed-coverage.json',seeds)
    write_json(output/'window-births.json',births)
    report=dict(experiment='EXP-0043',source=str(directory),frames=len(rows),
        all_live_window_frames=len(records),signals=sum(r['signal_present'] for r in records),
        component_max_error=error,ranges=summarize(records,seeds,camera,ranges),
        input_sha256=before,code_sha256=sha(__file__),flow_calls=0,model_calls=0,
        semantic_quality=None,elapsed_seconds=time.perf_counter()-begin)
    if before!={p:sha(p) for p in before}:raise ValueError('Protected input changed')
    write_json(output/'summary.json',report)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--range',action='append',required=True)
    args=parser.parse_args();report=execute(args.directory,args.output,[parse_range(v) for v in args.range])
    print(json.dumps({k:v for k,v in report.items() if k!='input_sha256'},indent=2))


if __name__=='__main__':main()
