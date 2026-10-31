"""EXP-0043 sole isolated seed_geometry_recent_dynamics_v1 comparison.

Geometry uses the same surviving seed/current points; dynamics retain the saved
rolling reference. These are intentionally two different time bases. This is a
developmental image-motion hypothesis, not an action/identity classifier or MVP
replacement. No pixels, optical flow, model, tracker, or remote service is used.
"""
import argparse
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np

from .gate_transition import cue_metrics, EvidenceLatch, TransitionPolicy
from .transition_diagnostics import explain_score, point_map, sha, write_json
from .exp0042_application import normalize_transition

ALGORITHM = 'seed_geometry_recent_dynamics_v1'
DYNAMIC_FIELDS = ('motion_change', 'speed_heights_per_second')
GEOMETRY_FIELDS = ('crossing_fraction', 'crossing', 'upward_image_motion',
                   'local_deformation', 'normal_progress', 'coherence')


def seed_geometry_metric(before, after, *, scene, height, saved, dt=.5):
    """Change spatial reference only; never replace saved recent dynamics.

    The existing equation, scale, current proximity, point quality and camera
    penalty remain exact. ``dt`` is the real seed age, never a fictitious .5s.
    Geometric cue computation has no velocity dependence; its newly computed
    velocity/change values are discarded before scoring.
    """
    if len(before) != saved['point_count']:
        raise ValueError('Same surviving points and saved point quality required')
    geometry = cue_metrics(before, after, line=scene['line'],
                           size=scene['source_size'], height=height, dt=dt)
    metric = deepcopy(saved)
    metric.update({k: geometry[k] for k in GEOMETRY_FIELDS})
    cross = (metric['proximity']*(.65*metric['crossing']+.20*metric['normal_progress']
             +.15*metric['coherence'])) if metric['crossing_fraction'] else 0.
    local = metric['proximity']*metric['upward_image_motion']*(
        .55*metric['local_deformation']+.25*metric['motion_change']
        +.20*metric['normal_progress'])
    quality = .8+.2*min(1., metric['point_count']/8)
    metric['score'] = max(0., float(np.clip(max(cross,local)*quality,0,1))
                          -(0 if metric.get('camera_support',True) else .10))
    metric['route'] = 'boundary_motion' if cross >= local else 'local_gate_change'
    return metric


class SeedGeometryReplay:
    """Causal replay from complete saved window points; preserves seed allocation."""
    def __init__(self, scene, policy):
        if asdict(policy) != asdict(TransitionPolicy()):
            raise ValueError('Only the fixed EXP-0042 policy is authorized')
        self.scene=deepcopy(scene); self.policy=policy.validate()
        self.offset=np.zeros(2); self.seeds={}; self.last_pts=-math.inf
        self.last_index=-1; self.latch=EvidenceLatch(policy)

    def step(self, row):
        at=row['pts']
        if not math.isfinite(at) or at < 0 or at <= self.last_pts or row['frame_index'] <= self.last_index:
            raise ValueError('Strictly increasing native source clock required')
        step=np.asarray(row['camera_step_pixels'],dtype=float)
        if step.shape != (2,) or not np.isfinite(step).all():
            raise ValueError('Finite saved camera correction required')
        self.offset+=step
        old_seeds=self.seeds; self.seeds={}; current={}
        for path in row['point_paths']:
            wid=path['window_id']
            if wid in current: raise ValueError('Duplicate saved window')
            mapped=point_map(path)
            points={i:np.asarray(p)-self.offset for i,p in mapped.items()}
            if wid in old_seeds and not row['source_gap']:
                seed=old_seeds[wid]
                if seed['pts'] != path['seed_pts']:
                    raise ValueError('Immutable window seed required')
            else:
                if path['seed_pts'] != at:
                    raise ValueError('Complete replay must include actual birth, not a synthetic seed')
                box=next(b for b in row['actual_boxes'] if b['cache_index']==path['seed_cache_index'])
                seed=dict(pts=at,points=points,
                    height=(box['bbox'][3]-box['bbox'][1])*self.scene['source_size'][1])
            if at-seed['pts'] > self.policy.window_seconds+1e-9:
                raise ValueError('Saved window exceeds frozen lifetime')
            if not set(points).issubset(seed['points']):
                raise ValueError('Point identities cannot be added or relabeled')
            self.seeds[wid]=seed; current[wid]=(path,points)
        signals=[]
        for saved in row['signals']:
            wid=saved['window_id']; seed=self.seeds[wid]; path,points=current[wid]
            if not seed['pts'] <= saved['reference_pts'] < at:
                raise ValueError('Saved dynamics must use a strictly preceding reference')
            if saved['point_ids'] != path['point_ids']:
                raise ValueError('Saved signal and current path point IDs differ')
            if saved['points_original_pixels'] != path['points_original_pixels']:
                raise ValueError('Saved signal and current path pixel coordinates differ')
            ids=path['point_ids']; dt=at-seed['pts']
            if dt < .1-1e-9: raise ValueError('Original minimum reference age required')
            before=np.asarray([seed['points'][i] for i in ids])
            after=np.asarray([points[i] for i in ids])
            metric=seed_geometry_metric(before,after,scene=self.scene,height=seed['height'],
                                        saved=saved,dt=dt)
            metric.update(reference_pts=seed['pts'],geometry_reference_pts=seed['pts'],
                geometry_dt=dt,recent_reference_pts=saved['reference_pts'],
                recent_dt=at-saved['reference_pts'],recent_motion_change=saved['motion_change'],
                recent_speed_heights_per_second=saved['speed_heights_per_second'],
                baseline_score=saved['score'],algorithm=ALGORITHM,
                height_pixels=seed['height'],evidence_until_pts=at)
            signals.append(metric)
        best=max(signals,key=lambda s:s['score'],default=None)
        score=best['score'] if best else 0.
        emit=self.latch.push(at,score)
        event=None if not emit else dict(status='침입 의심',reason='gate_visual_transition',
            decision_time_pts=at,frame_index=row['frame_index'],evidence=deepcopy(best),
            evidence_until_pts=at,identity_verified=False,automatic_confirmation=False,
            visibility_is_not_a_negative_verdict=True,native_pts=row['native_pts'],time_base=row['time_base'])
        self.last_pts=at; self.last_index=row['frame_index']
        result=deepcopy(row)
        result.update(baseline_score=row.get('score'),baseline_event=deepcopy(row.get('event')),
                      signals=signals,score=score,event=event,comparison_algorithm=ALGORITHM)
        return result


def normalize_candidate(raw, *, scope, video_id, source_sha256):
    event=normalize_transition(raw,scope=scope,video_id=video_id,source_sha256=source_sha256)
    binding=dict(scope=scope,video_id=video_id,source_sha256=source_sha256,
        pts=raw['decision_time_pts'],window=raw['evidence']['window_id'],algorithm=ALGORITHM)
    eid=hashlib.sha256(json.dumps(binding,sort_keys=True,allow_nan=False).encode()).hexdigest()
    event.update(event_id=eid,algorithm=ALGORITHM)
    event['source_ref'].update(source_pointer='/transition_events/'+eid)
    return event


def context_counts(key, baseline, candidate):
    ranges=([('approach',52.5,58),('waiting',58,64),('missed',64,74),('early',65,66)]
            if key=='007' else [('approach',84,89),('intrusion_context',90,94)])
    return {name:dict(start=start,end=end,
        before_pts=[e['decision_time_pts'] for e in baseline if start <= e['decision_time_pts'] <= end],
        after_pts=[e['decision_time_pts'] for e in candidate if start <= e['decision_time_pts'] <= end])
        for name,start,end in ranges}


def run_one(directory, output):
    from .incident_notifications import group_notifications
    from .incident_cards import GroupPolicy
    begin=time.perf_counter(); directory=Path(directory); output=Path(output)
    request=json.loads((directory/'request.json').read_text())
    policy=TransitionPolicy(**request['policy'])
    scene_path=next(Path(p) for p in request['input_sha256'] if 'scene' in p and p.endswith('.json'))
    scene=json.loads(scene_path.read_text()); engine=SeedGeometryReplay(scene,policy)
    original=json.loads((directory/'baseline-cards.json').read_text())
    old_new=json.loads((directory/'transition-events.json').read_text())
    scope={k:original['events'][0][k] for k in ('session_id','camera_id','gate_id')}
    video=original['video_id']; key=video[-3:]
    source_hash=next(h for p,h in request['input_sha256'].items() if p.endswith('.mp4'))
    old_summary=json.loads((directory/'summary.json').read_text())
    output.mkdir(parents=True,exist_ok=False)
    original_latch=EvidenceLatch(policy); reproduced=[]; events=[]; count=signals=0; baseline_error=0.
    dynamics_errors=proximity_errors=0; baseline_max_score=0.; candidate_max_score=0.
    with (directory/'frame-evidence.jsonl').open() as src, (output/'frame-evidence.jsonl').open('x') as dst:
        for line in src:
            row=json.loads(line); at=row['pts']
            for s in row['signals']:
                explanation=explain_score(s,policy.score_threshold)
                baseline_error=max(baseline_error,abs(explanation['difference']))
            original_best=max((s['score'] for s in row['signals']),default=0.)
            if abs(original_best-row['score'])>1e-10: raise ValueError('Baseline maximum score differs')
            if original_latch.push(at,original_best): reproduced.append(at)
            r=engine.step(row); count+=1; signals+=len(r['signals'])
            for before,after in zip(row['signals'],r['signals']):
                dynamics_errors+=any(before[k]!=after[k] for k in DYNAMIC_FIELDS)
                proximity_errors+=before['proximity']!=after['proximity']
            baseline_max_score=max(baseline_max_score,original_best)
            candidate_max_score=max(candidate_max_score,r['score'])
            if r['event']:
                events.append(normalize_candidate(r['event'],scope=scope,video_id=video,source_sha256=source_hash))
            dst.write(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n')
    expected=[e['decision_time_pts'] for e in old_new]
    if reproduced!=expected or count!=old_summary['frames']:
        raise ValueError('Incomplete source partition or original candidate replay differs')
    if dynamics_errors or proximity_errors: raise ValueError('Frozen dynamics/proximity changed')
    if not set(e['event_id'] for e in events).isdisjoint(e['event_id'] for e in old_new+original['events']):
        raise ValueError('Candidate IDs collide with preserved timelines')
    # Preserve baseline and EXP-0042 bytes separately; never group old+new together.
    for name,newname in [('baseline-cards.json','baseline-cards.json'),
                         ('transition-events.json','exp0042-transition-events.json'),
                         ('transition-only-cards.json','exp0042-transition-only-cards.json')]:
        (output/newname).write_bytes((directory/name).read_bytes())
    bundle=group_notifications(events,policy=GroupPolicy(**original['policy']))
    bundle.update(experiment='EXP-0043',algorithm=ALGORITHM,video_id=video,
        source_window=original['source_window'],comparison_mode='candidate-only',
        live_notifications_enabled=False,accuracy=None,realtime=False)
    write_json(output/'candidate-only-cards.json',bundle)
    write_json(output/'transition-events.json',events)
    report=dict(experiment='EXP-0043',algorithm=ALGORITHM,video_id=video,frames=count,signals=signals,
        source_window=old_summary['source_window'],policy=asdict(policy),
        baseline_replay_candidate_pts=reproduced,baseline_arithmetic_max_error=baseline_error,
        before_candidate_pts=expected,after_candidate_pts=[e['decision_time_pts'] for e in events],
        contexts=context_counts(key,old_new,events),
        baseline_max_score=baseline_max_score,candidate_max_score=candidate_max_score,
        baseline_alert_rows=len(original['events']),
        baseline_first_notification_pts=[c['first_notification_pts'] for c in original['alert_cards']],
        candidate_only_first_notification_pts=[c['first_notification_pts'] for c in bundle['alert_cards']],
        baseline_counts=original['counts'],candidate_only_counts=bundle['counts'],
        baseline_bytes_preserved=True,baseline_alerts_suppressed=0,merged_timeline_generated=False,
        saved_dynamic_field_mismatches=dynamics_errors,current_proximity_mismatches=proximity_errors,
        model_calls=0,detector_calls=0,tracker_calls=0,vlm_calls=0,flow_calls=0,
        elapsed_seconds=time.perf_counter()-begin,accuracy=None,realtime=False,
        semantic_improvement=None,held_out_validation=False)
    write_json(output/'summary.json',report)
    return report


def execute(freeze_path, output):
    begin=time.perf_counter(); freeze_path=Path(freeze_path); output=Path(output)
    frozen=json.loads(freeze_path.read_text())
    if frozen['algorithm']!=ALGORITHM or frozen['policy']!=asdict(TransitionPolicy()):
        raise ValueError('Frozen algorithm/policy differs')
    for group in ('code_sha256','input_sha256'):
        if any(sha(p)!=h for p,h in frozen[group].items()):
            raise ValueError('Frozen code/input hash differs')
    if (output.exists() or output.is_symlink() or any(p.is_symlink() for p in output.parents)
            or not output.resolve().is_relative_to(Path('outputs/exp0043').resolve())
            or 'comparison' not in output.name):
        raise ValueError('New comparison directory under outputs/exp0043 required')
    output.mkdir(parents=True,exist_ok=False)
    write_json(output/'request.json',dict(frozen,freeze_sha256=sha(freeze_path),
        actual_task_id='task_be82a26baf5b',actual_dispatch_id='ctx_4a0fd8da28d7',
        started_utc=datetime.now(timezone.utc).isoformat()))
    reports=[]
    try:
        for directory in frozen['input_runs']:
            key=Path(directory).name[:3]
            reports.append(run_one(directory,output/key))
        for group in ('code_sha256','input_sha256'):
            if any(sha(p)!=h for p,h in frozen[group].items()):
                raise ValueError('Frozen code/input changed during run')
        report=dict(experiment='EXP-0043',algorithm=ALGORITHM,videos=reports,
            total_frames=sum(r['frames'] for r in reports),total_signals=sum(r['signals'] for r in reports),
            flow_calls=0,model_calls=0,protected_inputs_unchanged=True,
            elapsed_seconds=time.perf_counter()-begin,freeze_sha256=sha(freeze_path),
            actual_task_id='task_be82a26baf5b',actual_dispatch_id='ctx_4a0fd8da28d7',
            independent_validation=False,accuracy=None,adopted=False)
        write_json(output/'summary.json',report)
        return report
    except Exception as exc:
        write_json(output/'failure.json',dict(error=repr(exc),completed_videos=len(reports),
            elapsed_seconds=time.perf_counter()-begin))
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); report=execute(args.freeze,args.output)
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
