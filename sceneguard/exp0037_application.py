"""One fixed CPU comparison on actual EXP-0035 outputs, no model calls.

Both card views preserve original event IDs/pointers. Proposed muted rows stay
in a review-only list with their original '침입 의심' payload, never become normal.
"""
from copy import deepcopy
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path

from .continuation_audit import audit_continuations


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def build_comparison(result,scene,camera_id,gate_id,session_id):
    from .exp0036_application import make_bundle
    from .incident_cards import group_events
    audit=audit_continuations(result,scene)
    baseline=make_bundle(result,camera_id,gate_id,session_id)
    pointers={r['source_pointer'] for r in audit['audits'] if r['recommendation']=='review_only'}
    kept=[]; muted=[]
    for event in baseline['events']:
        target=(event['source_ref']['collection']=='events'
                and event['source_ref']['source_pointer'] in pointers)
        (muted if target else kept).append(deepcopy(event))
    proposed=deepcopy(baseline)
    proposed.update(group_events(kept))
    proposed.update(comparison_experiment='EXP-0037', review_only_alerts=muted,
            full_original_alerts=deepcopy(baseline['events']),
            automatic_negative_decisions=0, default_adoption=False,
            false_alarm_status='unvalidated_continuation_hypothesis; muted_alerts_remain_suspicions')
    if ({e['event_id'] for e in kept} & {e['event_id'] for e in muted}
            or sorted(e['event_id'] for e in kept+muted)!=sorted(e['event_id'] for e in baseline['events'])):
        raise AssertionError('Every original alert must remain in exactly one view list')
    return baseline,proposed,audit


def execute(key,result_path,output):
    from .exp0034_application import validated_inputs
    from .exp0035_application import validate_measured_partition
    from .run_mvp_review import load_json
    root=Path('outputs').resolve();out=Path(output);src=Path(result_path)
    if out.exists() or out.is_symlink() or any(p.is_symlink() for p in out.parents) or not out.resolve().is_relative_to(root):
        raise ValueError('Use a NEW non-symlink local outputs directory')
    raw=src.read_bytes();result=json.loads(raw)
    if key not in ('007','030') or result.get('video_id')!=f'E01_{key}' or result.get('experiment')!='EXP-0035':
        raise ValueError('Expected original EXP-0035 result for selected source')
    scene_path=Path(result['source_paths']['scene'])
    spec,data,scene=validated_inputs(key,scene_path,result['input_sha256']['scene'])
    if any(result['input_sha256'].get(k)!=v for k,v in data['hashes'].items()):
        raise ValueError('Result does not bind to these actual observations')
    validate_measured_partition(result,data['tracked'])
    if result['existing_alerts']!=data['gap_events']:
        raise ValueError('Existing line alerts were changed')
    camera_id='C3' if key=='007' else 'C6'
    camera=load_json('configs/mvp0001_cameras.json')['cameras'][camera_id]
    gate_id=camera['legacy_boundary_config']['boundary_id']
    protected=[src,scene_path,Path(spec['tracks']),Path(spec['video']),Path(spec['regions'])]
    before={str(p):digest(p) for p in protected}
    baseline,proposed,audit=build_comparison(result,scene,camera_id,gate_id,f'E01_{key}-original')
    provenance=dict(source_result=str(src),source_sha256=hashlib.sha256(raw).hexdigest(),
        code_sha256={p.name:digest(p) for p in (Path(__file__),Path(__file__).with_name('continuation_audit.py'))},
        utc=datetime.now(timezone.utc).isoformat())
    for bundle in (baseline,proposed):bundle['provenance']=deepcopy(provenance)
    if before!={str(p):digest(p) for p in protected}:
        raise ValueError('Protected inputs changed while comparing')
    out.mkdir(parents=True,exist_ok=False)
    receipt=dict(experiment='EXP-0037',source=spec['video_id'],baseline_counts=baseline['counts'],
        proposed_counts=proposed['counts'],review_only_alerts=len(proposed['review_only_alerts']),
        interpretation='notification_view_comparison_not_intrusion_accuracy',
        protected_inputs_unchanged=True,input_sha256=before,
        detector_calls=0,tracker_calls=0,vlm_calls=0,**provenance)
    for name,value in [('baseline-cards.json',baseline),('proposed-cards.json',proposed),
                       ('continuation-audit.json',audit),('receipt.json',receipt)]:
        with (out/name).open('x',encoding='utf-8') as stream:
            json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
    return receipt


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--key',choices=('007','030'),required=True)
    p.add_argument('--result',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(execute(a.key,a.result,a.output),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
