"""Queue-only advisory EXP-0064 inference. Model imports occur only after runner_guard."""
import argparse
from collections import Counter, deque
from fractions import Fraction
import importlib.util
from itertools import zip_longest
import json
import math
import os
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]


def load_plan_module():
    spec=importlib.util.spec_from_file_location('action_plan',ROOT/'scripts/prepare_action_regression.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def letterbox(array, roi, size=112):
    import cv2
    import numpy as np
    x1,y1,x2,y2=roi
    if not (0<=x1<x2<=array.shape[1] and 0<=y1<y2<=array.shape[0]): raise ValueError('Invalid ROI')
    crop=array[y1:y2,x1:x2];height,width=crop.shape[:2];scale=size/max(height,width)
    resized=cv2.resize(crop,(max(1,round(width*scale)),max(1,round(height*scale))))
    canvas=np.zeros((size,size,3),dtype=np.uint8)
    top,left=(size-resized.shape[0])//2,(size-resized.shape[1])//2
    canvas[top:top+resized.shape[0],left:left+resized.shape[1]]=resized
    return canvas


def card_relations(window,cards,last_pts):
    """Temporal co-occurrence only; no causal/person match or baseline status propagation."""
    start,end=window['sample_pts'][0],window['sample_pts'][-1]
    return [dict(incident_id=c['incident_id'],relation='temporal_overlap_only_identity_unknown')
            for c in cards if c['first_notification_pts']<=end
            and (c.get('observation_closed_pts') if c.get('observation_closed_pts') is not None else last_pts)>=start]


def process_video(row, frames, score_batch, sink, cards):
    """Decode once to EOF; at most eight sampled full images and four 112px clips."""
    import numpy as np
    samples=row['samples'];cursor=0;ring=deque(maxlen=8);pending=[]
    by_end={}
    for w in row['windows']: by_end.setdefault(w['end_target_index'],[]).append(w)
    counts=Counter(scored_windows=0,candidate_windows=0,decoded_native_frames=0,
                   peak_sampled_frame_buffer=0,peak_clip_batch=0)
    batches=[];first=None;last=None
    def flush():
        if not pending:return
        scores=score_batch([arr for _,arr in pending])
        if len(scores)!=len(pending):raise ValueError('Incomplete action score batch')
        batches.append(len(pending))
        for (window,_),score in zip(pending,scores):
            if not math.isfinite(score) or not 0<=score<=1:raise ValueError('Invalid action score')
            candidate=score>=.5
            sink(dict(**window,video_id=row['video_id'],score=score,threshold=.5,
                      action='climbing_action_candidate' if candidate else None,
                      baseline_relations=card_relations(window,cards,row['last_pts']),
                      baseline_state_modified=False,identity_verified=False,
                      batch_flushed_at_source_pts=last,real_time_notice_measured=False,
                      sample_provenance=[{k:s[k] for k in ('target_index','target_pts','native_pts','time_base','pts','frame_index')}
                                         for s in samples[window['start_target_index']:window['end_target_index']+1]],
                      source_sha256=row['source_sha256'],tracking_sha256=row['input_hashes'][row['tracking_path']]))
            counts['scored_windows']+=1;counts['candidate_windows']+=int(candidate)
        pending.clear()
    for index,(pts,array) in enumerate(frames):
        first=pts if first is None else first;last=pts;counts['decoded_native_frames']+=1
        if cursor>=len(samples) or index!=samples[cursor]['frame_index']:continue
        sample=samples[cursor]
        if abs(pts-sample['pts'])>1e-6:raise ValueError('Selected native PTS differs')
        if array.shape[:2]!=(row['height'],row['width']):raise ValueError('Source dimensions changed')
        ring.append((cursor,array));counts['peak_sampled_frame_buffer']=max(counts['peak_sampled_frame_buffer'],len(ring))
        for window in by_end.get(cursor,[]):
            wanted=list(range(window['start_target_index'],cursor+1))
            if [i for i,_ in ring]!=wanted or pts!=window['available_after_pts']:
                raise ValueError('Window uses missing/future frames')
            clip=np.stack([letterbox(a,window['roi_xyxy']) for _,a in ring])
            pending.append((window,clip));counts['peak_clip_batch']=max(counts['peak_clip_batch'],len(pending))
            if len(pending)==4:flush()
        cursor+=1
    flush()
    if (cursor!=len(samples) or counts['decoded_native_frames']!=row['native_frames']
            or first is None or abs(first-row['first_pts'])>1e-6 or abs(last-row['last_pts'])>1e-6
            or counts['scored_windows']!=len(row['windows'])):
        raise ValueError('Incomplete whole-video execution coverage')
    return dict(**counts,actual_batch_sizes=batches,first_decoded_pts=first,last_decoded_pts=last,
                source_duration_seconds=row['duration_seconds'],target_grid_from_pts=0,
                target_grid_through_pts=samples[-1]['target_pts'],sampled_frames=cursor,
                planned_coverage=row['counts'],precision=None,recall=None,f1=None,
                observation_coverage_insufficient_windows=row['counts']['insufficient_active_observation_windows'],
                active_observation_window_denominator=row['counts']['active_observation_window_denominator'],
                no_observations_crossproduct_windows=row['counts']['no_observations_windows'],
                human_confirmed_detector_false_negatives=None,action_annotation_reference_disagreement=None,
                baseline_intrusion_decision_error=None,causal_error_truth=None)


def native_frames(row):
    import av
    with av.open(row['source_path']) as container,Path(row['tracking_path']).open() as stream:
        tracking=(json.loads(line) for line in stream)
        selected={s['frame_index'] for s in row['samples']} if 'samples' in row else None
        for index,(frame,record) in enumerate(zip_longest(container.decode(container.streams.video[0]),tracking)):
            if frame is None or record is None:raise ValueError('Decode/tracking whole-video length mismatch')
            actual=Fraction(frame.pts)*frame.time_base
            expected=Fraction(record['native_pts'])*Fraction(record['time_base'])
            if actual!=expected:raise ValueError('Native decode/tracking PTS mismatch')
            # Decode the native stream once; RGB conversion only for the 3FPS selections.
            yield float(actual),frame.to_ndarray(format='rgb24') if selected is None or index in selected else None


def preserve_baseline(row, output, module):
    """Copy original bytes into the separate output; never serialize baseline event state."""
    target=output/'baseline';target.mkdir()
    copied={}
    for path,h in row['baseline_hashes'].items():
        source=module.verify(path,h);destination=target/source.name
        shutil.copyfile(source,destination);module.verify(destination,h);copied[str(destination)]=h
    return copied


def gpu_scorer(config, inputs):
    # This function is called exclusively after live queue + held inherited FD + reviewed GO checks.
    import numpy as np
    os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
    import torch
    import torchvision
    module=load_plan_module();settings=module.read(config['files']['training_config']['path'])
    if not torch.cuda.is_available():raise ValueError('Canonical CUDA required')
    torch.set_num_threads(2);torch.backends.cudnn.benchmark=False
    torch.use_deterministic_algorithms(True)
    checkpoint=torch.load(config['files']['checkpoint']['path'],weights_only=False,map_location='cpu')
    if (checkpoint['config']!=settings or checkpoint['epoch']!=inputs['standalone']['selected_epoch']
            or checkpoint['manifest_sha256']!=inputs['standalone']['training_manifest_sha256']):
        raise ValueError('Final checkpoint training/config/validation provenance differs')
    model=torchvision.models.video.r3d_18(weights=None)
    model.fc=torch.nn.Linear(model.fc.in_features,2);model.load_state_dict(checkpoint['model'])
    model=model.cuda().eval();del checkpoint
    mean=torch.tensor(module.POLICY['mean'],device='cuda').view(1,3,1,1,1)
    std=torch.tensor(module.POLICY['std'],device='cuda').view(1,3,1,1,1)
    def score(arrays):
        if not 1<=len(arrays)<=4:raise ValueError('Fixed batch4 with final remainder only')
        tensor=torch.from_numpy(np.stack(arrays)).permute(0,4,1,2,3).cuda().float()/255
        with torch.no_grad(),torch.autocast('cuda',dtype=torch.float16):logits=model((tensor-mean)/std)
        return logits.float().softmax(-1)[:,1].cpu().tolist()
    return score


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--queue-config',type=Path,required=True)
    parser.add_argument('--queue-config-sha256',required=True)
    parser.add_argument('--queue-attempt',required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args(argv)
    sys.path.insert(0,str(ROOT))
    from orchestration.action_inference_command import runner_guard
    config,inputs=runner_guard(args)
    module=load_plan_module();manifest=module.read(config['files']['manifest']['path'])
    if args.output.exists():raise ValueError('Fresh inference attempt output required')
    args.output.mkdir(parents=True)
    score=gpu_scorer(config,inputs);reports=[];total=Counter()
    for entry in manifest['videos']:
        module.verify(entry['path'],entry['sha256']);row=module.read(entry['path'])
        directory=args.output/row['video_id'];directory.mkdir()
        copied=preserve_baseline(row,directory,module)
        with (directory/'window-scores.jsonl').open('x') as stream:
            def sink(value):
                value['model_provenance']=config['files']['checkpoint']
                value['plan_sha256']=entry['sha256'];value['queue_attempt']=args.queue_attempt
                stream.write(json.dumps(value,ensure_ascii=False,allow_nan=False)+'\n')
            report=process_video(row,native_frames(row),score,sink,module.read(row['cards_path'])['cards'])
        for path,h in {**row['baseline_hashes'],**copied}.items():module.verify(path,h)
        report.update(video_id=row['video_id'],baseline_output_hash_equivalence=True,
                      preserved_baseline_hashes=row['baseline_hashes'],copied_baseline_hashes=copied,
                      source_and_settings_hashes=row['input_hashes'],state_changes=False)
        module.save(directory/'report.json',report);reports.append(report)
        total.update({k:report[k] for k in ('scored_windows','candidate_windows','decoded_native_frames')})
    for path,h in inputs['baseline_outputs'].items():module.verify(path,h)
    module.save(args.output/'result.json',dict(status='advisory_inference_complete',videos=reports,
        totals=dict(total),planned_all45_coverage=manifest['counts'],baseline_output_hash_equivalence=True,
        precision=None,recall=None,f1=None,intrusion_completion_accuracy=None,performance_improvement=None,
        baseline_official_reference='52 time references; 006 unresolved and 008 deferred unchanged',
        baseline_state_changes=False,production_integration=False,input_contract=inputs,
        config_sha256=module.sha(args.queue_config),queue_attempt=args.queue_attempt,
        interpretation='Unchanged intrusion output is advisory architecture preservation, not accuracy improvement'))


if __name__=='__main__':main()
