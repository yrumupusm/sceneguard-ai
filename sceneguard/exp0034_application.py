"""CPU-only EXP-0034 application of the frozen analyzer to validated observations.

No detector, tracker, encoder, model load or scene annotation is performed here.
"""
import argparse
from bisect import bisect_left
from datetime import datetime, timezone
import json
from pathlib import Path

from .approach_disappearance import analyze, polygon, center, validate_scene
from .run_mvp_review import input_spec, load_video_inputs, load_json, REGION_BINDING
from .run_tracklet_linking import sha256, write_json

ANALYZER = Path('sceneguard/approach_disappearance.py')


def fresh_file(path, root='outputs'):
    path = Path(path)
    if (path.exists() or path.is_symlink() or any(p.is_symlink() for p in path.parents)
            or not path.resolve().is_relative_to(Path(root).resolve())):
        raise ValueError('A new non-symlink local output is required')
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def validate_scene_binding(scene, cached, regions, camera):
    validate_scene(scene)
    x1,y1,x2,y2 = camera['legacy_boundary_config']['roi']
    expected_roi = [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
    if (scene['source_size'] != cached[0]['source_size']
            or scene['line'] != camera['legacy_boundary_config']['line']
            or scene['approach_polygon'] != expected_roi
            or scene['zones'] != {k:regions[k] for k in ('outside','inside')}
            or set(scene['directions']) != {'outside_to_inside','inside_to_outside'}):
        raise ValueError('Scene must preserve current source/line/ROI/polygons/directions')


def validated_inputs(key, scene_path, scene_sha256):
    if sha256(scene_path) != scene_sha256:
        raise ValueError('Scene differs from root freeze GO SHA')
    spec = input_spec(key)
    data = load_video_inputs(spec, load_json(REGION_BINDING))
    scene = load_json(scene_path)
    cameras = load_json('configs/mvp0001_cameras.json')['cameras']
    validate_scene_binding(scene, data['cached'], data['zones'], cameras['C6' if key=='030' else 'C3'])
    return spec, data, scene


def enrich_timing(result, cached, scene):
    stamps = [f['pts'] for f in cached]
    by_id = {s['id']:s for s in result['segments']}
    for event in result['events']:
        event['source_observed_pts'] = event.get('last_observed_pts', event['pts'])
        i = bisect_left(stamps, event['pts']-1e-9)
        event['decision_time_pts'] = stamps[i] if i < len(stamps) else None
        event['available_after_pts'] = stamps[-1]
    for loss in result['losses']:
        i = bisect_left(stamps, loss['last_pts']+result['policy']['loss_wait']-1e-9)
        loss['decision_time_pts'] = stamps[i] if i < len(stamps) else None
        loss['available_after_pts'] = stamps[-1]
    for segment in result['segments']:
        rows = segment['rows']
        approach = next((r for r in rows if polygon(center(r,(1,1),.65),scene['approach_polygon'])),None)
        segment['approach_pts'] = approach['pts'] if approach else None
        segment['first_observed_pts'], segment['last_observed_pts'] = rows[0]['pts'], rows[-1]['pts']
        segment['exit_pts'] = [e['pts'] for e in result['events'] if e['segment']==segment['id'] and e['reason']=='observed_same_side_exit']
        for row in rows:
            f = cached[row['frame_index']]
            row.update(native_pts=f['native_pts'], time_base=f['time_base'])
    for pair in result['pairs']:
        pair['before_last_pts'] = by_id[pair['before']]['last_observed_pts']
        pair['after_first_pts'] = by_id[pair['after']]['first_observed_pts']
        pair['decision_time_pts'] = pair['after_first_pts']
        pair['available_after_pts'] = stamps[-1]
    result['available_after_pts'] = stamps[-1]
    result['timing_scope'] = 'offline whole-window analysis; decision_time_pts is logical evidence availability, not a measured realtime result'
    return result


def execute(key, scene_path, scene_sha256, output):
    output = fresh_file(output)
    spec,data,scene = validated_inputs(key,scene_path,scene_sha256)
    analyzer_sha = sha256(ANALYZER)
    result = enrich_timing(analyze(data['tracked'],scene),data['cached'],scene)
    result.update(video_id=spec['video_id'], source_size=scene['source_size'],
        source_window=[data['cached'][0]['pts'], data['cached'][-1]['pts']],
        frames=len(data['cached']), input_sha256=dict(data['hashes'],scene=scene_sha256,
            regions=sha256(spec['regions']), cameras=sha256('configs/mvp0001_cameras.json')),
        source_paths=dict(video=spec['video'],frames=spec['tracks'],cache=spec['cache'],scene=str(scene_path)),
        analyzer_sha256=analyzer_sha, existing_alerts=data['gap_events'],
        existing_alerts_policy='preserved separately; no status reassignment or identity merge',
        output_utc=datetime.now(timezone.utc).isoformat(), detector_calls=0,tracker_calls=0,encoder_calls=0)
    if sha256(scene_path)!=scene_sha256 or sha256(ANALYZER)!=analyzer_sha:
        raise ValueError('Frozen input/module changed while applying')
    for name,path in [('tracks',spec['tracks']),('video',spec['video']),('cache',Path(spec['cache'])/'person_cache.jsonl')]:
        if sha256(path)!=data['hashes'][name]:
            raise ValueError('Protected source input changed')
    write_json(output,result)
    return summary(result)


def summary(result):
    return dict(video_id=result['video_id'],frames=result['frames'],
        segments=[dict(id=s['id'],raw_id=s['raw_id'],first=s['rows'][0]['pts'],last=s['rows'][-1]['pts'],
                       observations=len(s['rows']),approach_pts=s['approach_pts']) for s in result['segments']],
        events=result['events'], losses=[{k:v for k,v in l.items() if k not in ('last_bbox',)} for l in result['losses']],pairs=result['pairs'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--key',choices=('030','007'),required=True)
    p.add_argument('--scene',type=Path,required=True)
    p.add_argument('--scene-sha256',required=True,help='Exact root scene-freeze GO SHA')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(execute(a.key,a.scene,a.scene_sha256,a.output),ensure_ascii=False))


if __name__=='__main__':
    main()
