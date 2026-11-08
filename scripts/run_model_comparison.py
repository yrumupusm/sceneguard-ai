"""Queue-only EXP-0066 native-PTS comparison. GPU imports follow runner_guard."""
import argparse
from collections import Counter, defaultdict
from fractions import Fraction
import importlib.util
import json
import math
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]


def load_adapter(joint, yolo=False):
    path=ROOT/'scripts'/('exp0066_yolo.py' if yolo else
                         'exp0066_joint_models.py' if joint else 'exp0066_encoders.py')
    spec=importlib.util.spec_from_file_location('comparison_adapter',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def validate_window(window,clocks):
    indices=window['sample_frame_indices']
    native=clocks['native_pts'];tb=Fraction(clocks['time_base'])
    if (len(indices)!=16 or any(type(i)!=int or i<0 or i>=len(native) for i in indices)
            or indices!=sorted(indices)):
        raise ValueError('Exact ordered16 native samples required')
    pts=[float(native[i]*tb) for i in indices]
    if (len(window['sample_pts'])!=16 or any(not math.isfinite(b) or abs(a-b)>1e-8
                                            for a,b in zip(pts,window['sample_pts']))):
        raise ValueError('Window sample PTS do not match original native clocks')
    if not math.isfinite(window['available_after_pts']) or abs(window['available_after_pts']-max(pts))>1e-8:
        raise ValueError('Output cannot be available before last actual input')
    return indices


def process_video(video,windows,frames,infer,sink):
    """Stream decode to EOF, retaining only frames needed by pending windows."""
    import numpy as np
    clocks=read(video['native_pts_binding']['path'])['clocks']
    native=clocks['native_pts'];tb=Fraction(clocks['time_base'])
    endings=defaultdict(list);uses=Counter()
    ids=set()
    for w in windows:
        if w['window_id'] in ids:raise ValueError('Duplicate window')
        ids.add(w['window_id']);indices=validate_window(w,clocks)
        endings[max(indices)].append(w);uses.update(set(indices))
    buffer={};count=0;scored=0;decode_seconds=0;peak=0;begin=time.perf_counter()
    stream=iter(frames)
    while True:
        start=time.perf_counter()
        try:pts,pixels=next(stream)
        except StopIteration:break
        decode_seconds+=time.perf_counter()-start
        if count>=len(native) or not math.isfinite(pts) or abs(pts-float(native[count]*tb))>1e-8:
            raise ValueError('Actual decode native PTS differ')
        if list(pixels.shape[1::-1])!=video['source_size']:
            raise ValueError('Decoded dimensions differ')
        if count in uses:buffer[count]=pixels
        peak=max(peak,len(buffer))
        for w in endings.get(count,[]):
            if any(i not in buffer for i in w['sample_frame_indices']):raise ValueError('Missing actual input')
            start=time.perf_counter();clip=np.stack([buffer[i] for i in w['sample_frame_indices']])
            assemble=time.perf_counter()-start
            output=infer(clip)
            # JSON serialization below rejects NaN/Infinity in every model score/coordinate.
            record=dict(video_id=video['video_id'],source_sha256=video['source_sha256'],
                        window=w,output=output,assembly_seconds=assemble,
                        observed_unique_frames=len(set(w['sample_frame_indices'])),
                        same_person_verified=False,intrusion_completed=False)
            if output.get('actual_input_frames') == 1:
                slot=output['input_frame_index']
                if type(slot)!=int or not 0<=slot<len(w['sample_frame_indices']):
                    raise ValueError('Single-frame output must identify its actual native input')
                record.update(box_frame_index=w['sample_frame_indices'][slot],
                              box_pts=w['sample_pts'][slot],
                              model_input_available_after_pts=w['sample_pts'][slot])
            sink(record);scored+=1
            for i in set(w['sample_frame_indices']):
                uses[i]-=1
                if not uses[i]:del uses[i];del buffer[i]
        count+=1
    if count!=len(native) or scored!=len(windows) or uses or buffer:
        raise ValueError('Incomplete original decode or requested window execution')
    return dict(video_id=video['video_id'],decoded_native_frames=count,scored_windows=scored,
                peak_buffer_frames=peak,decode_seconds=decode_seconds,
                elapsed_seconds=time.perf_counter()-begin)


def decode(path):
    import av
    with av.open(str(path)) as container:
        stream=container.streams.video[0];stream.thread_type='AUTO'
        for frame in container.decode(stream):
            if frame.pts is None or frame.time_base is None:raise ValueError('Missing native PTS')
            yield float(frame.pts*frame.time_base),frame.to_ndarray(format='rgb24')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--queue-config',required=True,type=Path)
    parser.add_argument('--queue-config-sha256',required=True)
    parser.add_argument('--queue-attempt',required=True)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args(argv)
    sys.path.insert(0,str(ROOT))
    from orchestration.model_comparison_command import runner_guard,JOINT,YOLO,sources,input_contract,file_hash
    from orchestration.queue import digest
    config,inputs=runner_guard(args)
    source_snapshot=sources(config)
    auth=read(config['authorization']['path'])
    import torch
    torch.set_num_threads(2);torch.manual_seed(66);torch.cuda.manual_seed_all(66)
    torch.backends.cudnn.benchmark=False
    torch.cuda.reset_peak_memory_stats()
    args.output.mkdir(parents=True,exist_ok=False)
    spec=read(config['files']['model_spec']['path'])
    adapter=load_adapter(config['model_id'] in JOINT, config['model_id'] in YOLO)
    started=time.perf_counter();model=adapter.load_model(spec,'cuda')
    torch.cuda.synchronize();load_seconds=time.perf_counter()-started
    cohort=read(config['files']['cohort']['path'])
    smoke=read(config['files']['smoke_windows']['path'])
    smoke_rows=smoke['windows']
    if len(smoke_rows)!=7:raise ValueError('Exact7 smoke windows required')
    plans={v['video_id']:read(v['plan']['path']) for v in cohort['videos']}
    if (sum(len(p['windows']) for p in plans.values())!=6177
            or sum(len(p['supplemental_windows']) for p in plans.values())!=42
            or any(not p['windows'] for p in plans.values())):
        raise ValueError('Complete frozen6177+42 window plan required')
    counts=[]
    with (args.output/'windows.jsonl').open('x') as stream:
        def sink(row):
            stream.write(json.dumps(row,sort_keys=True,allow_nan=False)+'\n');stream.flush()
        for v in cohort['videos']:
            plan=plans[v['video_id']]
            windows=(plan['windows']+plan['supplemental_windows'] if config['stage']=='all45' else
                     [r['window'] if 'window' in r else r for r in smoke_rows if r['video_id']==v['video_id']])
            if not windows:continue
            result=process_video(v,windows,decode(v['source_path']),
                                 lambda frames:adapter.infer_clip(model,frames,spec),sink)
            counts.append(result);print(json.dumps(result),flush=True)
    expected_windows=6219 if config['stage']=='all45' else 7
    if (sum(v['scored_windows'] for v in counts)!=expected_windows
            or (config['stage']=='all45' and (len(counts)!=45 or sum(v['decoded_native_frames'] for v in counts)!=184300))):
        raise ValueError('Incomplete requested comparison execution')
    if sources(config)!=source_snapshot or input_contract(config)!=inputs:
        raise ValueError('Reviewed source/input/environment changed during execution')
    result=dict(status='smoke_passed' if config['stage']=='smoke' else 'inference_complete',
                model_id=config['model_id'],stage=config['stage'],queue_command='model-compare',
                queue_attempt=args.queue_attempt,model_spec_sha256=config['files']['model_spec']['sha256'],
                input_hash=digest(inputs),source_hash=digest(source_snapshot),code_sha=auth['code_sha'],
                windows_sha256=file_hash(args.output/'windows.jsonl'),
                cohort_sha256=config['files']['cohort']['sha256'],videos=counts,
                scored_windows=sum(v['scored_windows'] for v in counts),
                decoded_native_frames=sum(v['decoded_native_frames'] for v in counts),
                load_seconds=load_seconds,elapsed_seconds=time.perf_counter()-started,
                peak_gpu_allocated_bytes=torch.cuda.max_memory_allocated(),
                peak_gpu_reserved_bytes=torch.cuda.max_memory_reserved(),
                semantic_evaluation_complete=False,person_recall=None,climbing_precision=None,
                climbing_recall=None,intrusion_state_changed=False)
    (args.output/'result.json').write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n')
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
