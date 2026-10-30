"""Apply EXP-0035 once to preserved EXP-0034 results, with no model inference.

Reuses EXP-0034 source/scene validation and its renderer-compatible result schema.
The source videos, measurements, scenes, prior JSON and original alerts are read-only.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from .relaxed_suspicion import add_relaxed_candidates


ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()


def validate_measured_partition(baseline, tracked):
    """Every saved segment row must be a real confirmed observation, not a prediction."""
    actual={}
    for i,frame in enumerate(tracked):
        for d in frame['detections']:
            if not d.get('observed',False) or not d.get('confirmed',True):
                continue
            key=(i,d['track_id'])
            if key in actual:
                raise ValueError('Duplicate actual track in one frame')
            actual[key]=(frame['pts'],d.get('cache_index'),d['bbox'])
    seen={}
    for segment in baseline['segments']:
        for row in segment['rows']:
            key=(row['frame_index'],segment['raw_id'])
            observed=(row['pts'],row.get('cache_index'),row['bbox'])
            if key in seen or actual.get(key)!=observed:
                raise ValueError('Saved segment is not an unchanged actual observation')
            seen[key]=observed
    if seen!=actual:
        raise ValueError('Saved segments must cover every actual observation')


def execute(key, output, baseline_path=None):
    # Existing full-repository dependencies are loaded only for actual local application.
    from .exp0034_application import validated_inputs, enrich_timing, fresh_file
    from .run_tracklet_linking import write_json
    baseline_path=Path(baseline_path or f'outputs/exp0034/{key}-v1.json')
    output=fresh_file(output)
    baseline_sha=digest(baseline_path)
    baseline=json.loads(baseline_path.read_text(encoding='utf-8'))
    if baseline.get('video_id')!=f'E01_{key}' or baseline.get('experiment')!='EXP-0034':
        raise ValueError('Expected the original matching EXP-0034 output')
    scene_path=Path(baseline['source_paths']['scene'])
    spec,data,scene=validated_inputs(key,scene_path,baseline['input_sha256']['scene'])
    if any(baseline['input_sha256'].get(k)!=v for k,v in data['hashes'].items()):
        raise ValueError('Preserved analysis and current validated source differ')
    if baseline.get('source_size')!=scene['source_size']:
        raise ValueError('Source dimensions differ')
    validate_measured_partition(baseline,data['tracked'])
    if baseline.get('existing_alerts')!=data['gap_events']:
        raise ValueError('Original gap candidates differ')
    protected=[baseline_path,scene_path,Path(spec['tracks']),Path(spec['video']),
               Path(spec['cache'])/'person_cache.jsonl',Path(spec['cache'])/'run.json',
               Path(spec['regions']),Path('configs/mvp0001_cameras.json')]
    before={str(p):digest(p) for p in protected}
    code_paths=[Path(__file__),Path(__file__).with_name('relaxed_suspicion.py')]
    code_hashes={str(p.relative_to(ROOT)):digest(p) for p in code_paths}
    result=add_relaxed_candidates(baseline,scene,[f['pts'] for f in data['cached']])
    result=enrich_timing(result,data['cached'],scene)
    result.update(baseline_sha256=baseline_sha,baseline_path=str(baseline_path),
                  baseline_analyzer_sha256=baseline.get('analyzer_sha256'),
                  analyzer_sha256=code_hashes['sceneguard/relaxed_suspicion.py'],
                  application_code_sha256=code_hashes,
                  output_utc=datetime.now(timezone.utc).isoformat(),
                  detector_calls=0,tracker_calls=0,encoder_calls=0,vlm_calls=0,
                  scene_policy='current_user_geometry_and_static_occlusion_annotations_unchanged')
    # Add row/segment-level changes for review; never treat these as true incidents.
    result['review_changes']=[deepcopy(r) for r in result['relaxation_audit'] if r['action']=='added_review_candidate']
    if before!={str(p):digest(p) for p in protected}:
        raise ValueError('Protected input changed during local CPU application')
    if code_hashes!={str(p.relative_to(ROOT)):digest(p) for p in code_paths}:
        raise ValueError('Application source changed during execution')
    result['protected_inputs_unchanged']=True
    write_json(output,result)
    return dict(video_id=result['video_id'],output=str(output),
                **result['relaxation_summary'],
                changes=[{k:r[k] for k in ('segment','raw_id','last_pts','decision_time_pts','support_count')}
                         for r in result['review_changes']])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--key',choices=('007','030'),required=True)
    p.add_argument('--baseline',type=Path)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(execute(a.key,a.output,a.baseline),ensure_ascii=False,indent=2,allow_nan=False))


if __name__=='__main__':main()
