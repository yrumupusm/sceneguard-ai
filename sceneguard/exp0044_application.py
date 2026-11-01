"""Offline EXP-0044: signed direction + existing gate disappearance candidates.

Reuses actual EXP35 observations and EXP42 saved image paths. No detector, flow,
VLM, learning, external notification, or mutation of original alerts/reviews.
"""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import argparse
import hashlib
import json
import time

from .directional_loss import DirectionPolicy, SavedGateDirection, annotated_bundle


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    with Path(path).open('x',encoding='utf-8') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False)
        stream.write('\n')


def evaluate(baseline, bundle, frames, scene, group, policy=DirectionPolicy()):
    """Pure application logic: preserve event IDs and only annotate loss rows."""
    engine = SavedGateDirection(frames,scene,policy)
    if abs(baseline['policy']['loss_wait']-policy.loss_wait)>1e-6:
        raise ValueError('Keep the original disappearance waiting time')
    segments = {s['id']:s for s in baseline['segments']}
    decisions = []
    for event in bundle['events']:
        original = event['source_event']
        if original.get('reason') != 'recent_gate_presence_then_loss':
            continue
        segment = segments[original['segment']]
        if (original['raw_id'] != segment['raw_id'] or
                original['decision_time_pts'] != event['decision_time_pts']):
            raise ValueError('Original candidate/segment clock differs')
        result = engine.classify(original,segment)
        result.update(event_id=event['event_id'],source_ref=deepcopy(event['source_ref']))
        decisions.append(result)
    proposal = annotated_bundle(bundle,decisions,group)
    proposal.update(video_id=bundle['video_id'],source_window=deepcopy(bundle['source_window']),
                    available_after_pts=bundle.get('available_after_pts',bundle['source_window'][1]),
                    direction_policy=asdict(policy),geometry=engine.geometry,realtime=False,
                    detector_calls=0,flow_calls=0,tracker_calls=0,vlm_calls=0,
                    changes='directional status of existing loss candidates, not a new person detector')
    return proposal


def prepared_inputs(baseline_path, paths_directory):
    """Validate real repository contracts without classifying any candidate."""
    from .exp0034_application import validated_inputs
    from .exp0035_application import validate_measured_partition
    from .exp0036_application import make_bundle
    from .gap_observation_support import catalog_frame
    from .incident_notifications import group_notifications
    from .incident_cards import GroupPolicy
    from .run_mvp_review import REGION_BINDING

    src,paths = Path(baseline_path),Path(paths_directory)
    baseline = json.loads(src.read_text(encoding='utf-8'))
    if baseline.get('experiment')!='EXP-0035' or baseline.get('video_id') not in ('E01_007','E01_030'):
        raise ValueError('Preserved EXP35 source required')
    key = baseline['video_id'][-3:]
    spec,data,scene = validated_inputs(key,baseline['source_paths']['scene'],baseline['input_sha256']['scene'])
    if any(baseline['input_sha256'].get(k)!=v for k,v in data['hashes'].items()):
        raise ValueError('Baseline source changed')
    validate_measured_partition(baseline,data['tracked'])
    if baseline['existing_alerts']!=data['gap_events']:
        raise ValueError('Original boundary events changed')
    request_path,summary_path = paths/'request.json',paths/'summary.json'
    request = json.loads(request_path.read_text())
    summary = json.loads(summary_path.read_text())
    if request.get('experiment')!='EXP-0042' or summary.get('video_id')!=baseline['video_id']:
        raise ValueError('Matching original EXP42 saved paths required')
    for path,expected in request['input_sha256'].items():
        if sha(path)!=expected:
            raise ValueError('EXP42 protected input changed: '+path)
    evidence = paths/'frame-evidence.jsonl'
    protected = list(dict.fromkeys([src,request_path,summary_path,evidence,paths/'baseline-cards.json',
        *(Path(p) for p in request['input_sha256']),Path(spec['gap_events']),
        Path('configs/mvp0001_cameras.json'),Path(REGION_BINDING)]))
    before = {str(p):sha(p) for p in protected}
    frames = [json.loads(line) for line in evidence.read_text().splitlines() if line.strip()]
    if len(frames)!=len(data['cached']) or len(frames)!=summary['frames']:
        raise ValueError('Full saved source window required')
    for i,(row,cache,track) in enumerate(zip(frames,data['cached'],data['tracked'])):
        if row['frame_index']!=i or any(row[k]!=cache[k] for k in ('pts','native_pts','time_base')):
            raise ValueError('Native source clock mismatch')
        if row['actual_boxes']!=catalog_frame(cache,track):
            raise ValueError('Saved actual detections differ from the source')
    camera = 'C3' if key=='007' else 'C6'
    base = make_bundle(baseline,camera,camera+'_fence',baseline['video_id']+'-original')
    group = lambda events,review: group_notifications(events,review,GroupPolicy(**base['policy']))
    base.update(group(base['events'], []))
    preserved = json.loads((paths/'baseline-cards.json').read_text())
    for field in ('events','cards','timeline','counts'):
        if base[field] != preserved[field]:
            raise ValueError('Original notification contract differs: '+field)
    return baseline,preserved,frames,scene,group,before


def execute(baseline_path, paths_directory, output, policy=DirectionPolicy()):
    started = time.perf_counter(); policy.validate()
    out = Path(output)
    if (out.exists() or out.is_symlink() or any(p.is_symlink() for p in out.parents)
            or not out.resolve().is_relative_to(Path('outputs').resolve())):
        raise ValueError('Use a new non-symlink output directory under outputs/')
    baseline,base,frames,scene,group,before = prepared_inputs(baseline_path,paths_directory)
    code = {str(p):sha(p) for p in (Path(__file__),Path(__file__).with_name('directional_loss.py'))}
    proposal = evaluate(baseline,base,frames,scene,group,policy)
    if before!={p:sha(p) for p in before} or code!={p:sha(p) for p in code}:
        raise ValueError('Input or source changed during analysis')
    out.mkdir(parents=True,exist_ok=False)
    with (out/'baseline-cards.json').open('xb') as stream:
        stream.write((Path(paths_directory)/'baseline-cards.json').read_bytes())
    save(out/'directional-cards.json',proposal)
    save(out/'decisions.json',proposal['decisions'])
    save(out/'geometry.json',proposal['geometry'])
    save(out/'case-summary.json',[dict(video_id=baseline['video_id'],
        **{k:d.get(k) for k in ('segment','raw_id','event_id','decision_time_pts',
            'last_observed_pts','near_gate_at_loss','paired_point_count','continuation',
            'automatic_confirmation','status','notify','reason')},
        direction=d.get('direction',{}).get('direction'),
        moving_points=d.get('direction',{}).get('moving_points',0),
        last_valid_direction_pts=d.get('direction',{}).get('end_pts'))
        for d in proposal['decisions']])
    summary = dict(experiment='EXP-0044',video_id=baseline['video_id'],policy=asdict(policy),
        cases=len(proposal['decisions']),
        automatic_confirmations=sum(d['automatic_confirmation'] for d in proposal['decisions']),
        unknown_or_outward=sum(d['notify'] and not d['automatic_confirmation'] for d in proposal['decisions']),
        not_a_loss=sum(not d['notify'] for d in proposal['decisions']),
        baseline_alert_rows=len(base['events']),counts=proposal['counts'],
        input_sha256=before,code_sha256=code,elapsed_seconds=time.perf_counter()-started,
        detector_calls=0,flow_calls=0,tracker_calls=0,vlm_calls=0,
        manual_reviews_modified=False,accuracy=None,realtime=False,
        limitation='Automatic confirmation is a gate-direction rule, not observed ground-truth entry.')
    save(out/'summary.json',summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--paths',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.baseline,args.paths,args.output),ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
