"""CPU-only EXP-0064 advisory regression manifest; never decodes pixels or runs a model."""
import argparse
from bisect import bisect_left
from collections import Counter
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT/'outputs/action-recognition/exp0063/baseline/attempt-002/baseline-lock.json'
LOCK_SHA = '3799ae3eee427b60e698b21f6ee958ac5306eacba07b5d85e4c35dbfa6457b40'
BASE = ROOT/'outputs/validation/false-confirmation-guard-all45-v1/run-001'
PREVIOUS = ROOT/'outputs/action-recognition/exp0064/regression-plan-v1'
OUTPUT = ROOT/'outputs/action-recognition/exp0064/regression-plan-v2'
POLICY = dict(sample_fps=3, frames=8, step=3, threshold=.5, image_size=112,
              batch_size=4, precision='amp_float16', roi='observed_union_3x_width_2x_height_clamped',
              mean=[.43216,.394666,.37645], std=[.22803,.22145,.216989],
              semantics='climbing_action_candidate', state_changes=False)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def verify(path, expected):
    path = Path(path)
    if not path.is_absolute() or path.is_symlink() or sha(path) != expected:
        raise ValueError('Immutable absolute input differs: '+str(path))
    return path


def roi(boxes, width, height):
    """Normalized actual boxes; same geometric union/context/rounding as trainer builder."""
    if not boxes or any(len(b)!=4 or not all(math.isfinite(v) for v in b)
                        or not (0<=b[0]<b[2]<=1 and 0<=b[1]<b[3]<=1) for b in boxes):
        raise ValueError('Invalid normalized observed box')
    x1=min(b[0]*width for b in boxes); y1=min(b[1]*height for b in boxes)
    x2=max(b[2]*width for b in boxes); y2=max(b[3]*height for b in boxes)
    w,h=x2-x1,y2-y1
    return [max(0,math.floor(x1-w)),max(0,math.floor(y1-h/2)),
            min(width,math.ceil(x2+w)),min(height,math.ceil(y2+h/2))]


def sample_grid(frames):
    """Nearest native PTS, earlier tie; target grid anchored at zero through last PTS."""
    pts=[Fraction(f['native_pts'])*Fraction(f['time_base']) for f in frames]
    if not pts or pts[0]!=0 or any(b<=a for a,b in zip(pts,pts[1:])):
        raise ValueError('Full strictly increasing native PTS from zero required')
    result=[]
    for k in range(int(pts[-1]*3)+1):
        target=Fraction(k,3); right=bisect_left(pts,target)
        choices=[i for i in (right-1,right) if 0<=i<len(pts)]
        i=min(choices,key=lambda i:(abs(pts[i]-target),pts[i]))
        frame=frames[i]
        observed={}
        for state in frame['states']:
            if state.get('observed') is True:
                key=str(state['track_id'])
                if key in observed:
                    raise ValueError('Duplicate observed track in native frame')
                observed[key]=state['bbox']
        result.append(dict(target_index=k,target_pts=float(target),frame_index=i,
                           native_pts=frame['native_pts'],time_base=frame['time_base'],
                           pts=float(pts[i]),observed=observed))
    if len({s['frame_index'] for s in result})!=len(result):
        raise ValueError('3FPS selection repeats native frames')
    return result


def plan_windows(samples, track_ids, width, height):
    windows=[]; missing=[]; counts=Counter(global_windows=max(0,(len(samples)-8)//3+1),
                                         tracks=len(track_ids),sampled_frames=len(samples))
    for start in range(0,len(samples)-7,3):
        chunk=samples[start:start+8]
        for track in sorted(track_ids):
            absent=[s['target_index'] for s in chunk if track not in s['observed']]
            counts['track_window_denominator']+=1
            if absent:
                counts['missing_observation_windows']+=1
                counts['missing_observation_samples']+=len(absent)
                counts['no_observations_windows' if len(absent)==8 else 'partial_observations_windows']+=1
                missing.append(dict(track_id=track,start_target_index=start,missing_target_indices=absent))
            else:
                boxes=[s['observed'][track] for s in chunk]
                windows.append(dict(window_id=f'{start:06d}-{track}',track_id=track,
                    start_target_index=start,end_target_index=start+7,
                    sample_pts=[s['pts'] for s in chunk],sample_frame_indices=[s['frame_index'] for s in chunk],
                    boxes=boxes,roi_xyxy=roi(boxes,width,height),available_after_pts=chunk[-1]['pts']))
                counts['eligible_windows']+=1
    for key in ('track_window_denominator','missing_observation_windows','missing_observation_samples',
                'no_observations_windows','partial_observations_windows','eligible_windows'):
        counts.setdefault(key,0)
    counts['observation_sample_denominator']=counts['track_window_denominator']*8
    counts['active_observation_window_denominator']=counts['eligible_windows']+counts['partial_observations_windows']
    counts['insufficient_active_observation_windows']=counts['partial_observations_windows']
    return windows,missing,dict(counts)


def source_plan(entry, lock):
    bindings=lock['verified_paths']
    def locked(path):
        path=Path(path); verify(path,bindings[str(path)]); return path
    input_path=locked(entry['input_manifest']); manifest=read(input_path)
    if manifest['video_id']!=entry['video_id'] or not manifest['full_original_input']:
        raise ValueError('Full original video identity required')
    analysis=[Path(p) for p in manifest['protected_sources'] if p.endswith('/source/analysis/analysis.json')]
    if len(analysis)!=1:
        raise ValueError('Ambiguous protected measurement source')
    measurement=analysis[0].parents[2]
    locked(analysis[0]); request=read(locked(measurement/'request.json'))
    if request['video']!=entry['path'] or request['input_sha256'][entry['path']]!=entry['sha256']:
        raise ValueError('Protected source identity differs')
    stage_path=locked(measurement/'source/tracking/stage.json'); stage=read(stage_path)
    if stage['status']!='complete': raise ValueError('Incomplete tracking')
    tracking=measurement/'source/tracking/frames.jsonl'
    verify(tracking,stage['artifacts']['frames.jsonl'])
    with tracking.open() as stream: frames=[json.loads(line) for line in stream]
    if len(frames)!=manifest['frames'] or abs(frames[-1]['pts']-manifest['last_pts'])>1e-6:
        raise ValueError('Whole video tracking coverage differs')
    samples=sample_grid(frames)
    tracks={str(s['track_id']) for f in frames for s in f['states'] if s.get('observed') is True}
    # Container headers only: no pixel decoding and no redundant original-media hash audit.
    import av
    with av.open(entry['path']) as container:
        stream=container.streams.video[0]; width,height=stream.width,stream.height
    windows,missing,counts=plan_windows(samples,tracks,width,height)
    after=Path(entry['after'])
    if after != BASE/'after'/entry['video_id']: raise ValueError('Wrong protected AFTER')
    # Five canonical all45 AFTER directories are historical symlink aliases.
    # Bind their resolved files to the exact already-frozen lock entries.
    baseline={str(p.resolve()):bindings[str(p.resolve())] for p in sorted(after.glob('*.json'))}
    for p,h in baseline.items(): verify(p,h)
    inputs={str(p):bindings[str(p)] for p in (input_path,analysis[0],measurement/'request.json',stage_path)}
    inputs[str(tracking)]=stage['artifacts']['frames.jsonl']
    inputs[entry['path']]=entry['sha256']
    return dict(video_id=entry['video_id'],source_path=entry['path'],source_sha256=entry['sha256'],
                tracking_path=str(tracking),input_hashes=inputs,baseline_hashes=baseline,
                cards_path=str((after/'cards.json').resolve()),baseline_after_alias=str(after),
                baseline_after_resolved=str(after.resolve()),width=width,height=height,
                native_frames=len(frames),first_pts=frames[0]['pts'],last_pts=frames[-1]['pts'],
                duration_seconds=manifest['duration_seconds'],samples=samples,windows=windows,
                missing_windows=missing,counts=counts)


def prepare(output=OUTPUT):
    if Path(output).resolve()!=OUTPUT or OUTPUT.exists(): raise ValueError('Fresh canonical plan output required')
    verify(LOCK,LOCK_SHA); lock=read(LOCK)
    if lock['status']!='verified' or lock['baseline_experiment']!='EXP-0062' or len(lock['regression_only_videos'])!=45:
        raise ValueError('Verified all45 EXP0062 lock required')
    # Metadata-only revision from the preserved initial CPU plan, no repeated source audit.
    previous_path=PREVIOUS/'manifest.json';previous=read(previous_path)
    if previous['policy']!=POLICY or previous['baseline_lock']!={'path':str(LOCK),'sha256':LOCK_SHA}:
        raise ValueError('Preserved initial policy/baseline differs')
    rows=[]
    for entry in previous['videos']:
        if Path(entry['path'])!=PREVIOUS/(entry['video_id']+'.json'):
            raise ValueError('Canonical initial plan required')
        row=read(verify(entry['path'],entry['sha256']))
        row['counts']['active_observation_window_denominator']=row['counts']['eligible_windows']+row['counts']['partial_observations_windows']
        row['counts']['insufficient_active_observation_windows']=row['counts']['partial_observations_windows']
        rows.append(row)
    if {r['video_id'] for r in rows}!={f'E01_{i:03d}' for i in range(1,46)}:
        raise ValueError('Exact protected all45 required')
    OUTPUT.mkdir(parents=True)
    entries=[]; total=Counter()
    for row in rows:
        path=OUTPUT/(row['video_id']+'.json');save(path,row)
        entries.append(dict(video_id=row['video_id'],path=str(path),sha256=sha(path)))
        total.update(row['counts'])
    result=dict(schema_version=1,experiment_id='EXP-0064',status='cpu_plan_only_no_inference',
                baseline_lock=dict(path=str(LOCK),sha256=LOCK_SHA),policy=POLICY,videos=entries,
                counts=dict(total),media_hash_policy='reuse_frozen_lock_now_verify_actual_selected_sources_before_inference',
                precision=None,recall=None,f1=None,ground_truth_used=False,checkpoint=None,
                predecessor_manifest=dict(path=str(previous_path),sha256=sha(previous_path)),
                source_samples_eligible_windows_missing_lists_identical_to_v1=True,
                missing_coverage_policy='primary_partial_observation_windows_over_eligible_plus_partial; absent_crossproduct_is_not_operational_miss',
                score_timing_policy='available_after_pts_is_last_actual_sample; batch_flushed_at_source_pts_records_actual_flush; real_time_notice_unmeasured',
                execution_requires='completed_standalone_training_and_evaluation_independent_review_root_GO_canonical_queue')
    save(OUTPUT/'manifest.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.parse_args()
    result=prepare();print(json.dumps(dict(videos=len(result['videos']),counts=result['counts'])))
