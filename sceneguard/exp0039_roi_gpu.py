"""Bounded EXP39 FCOS ROI comparison; no tracker, alarm change or implicit GPU entry.

TorchVision returns boxes in the supplied native crop coordinates. Restore by
adding the actual integer crop offset exactly once; do not reverse its internal
resize a second time. All model-returned person rows remain separately auditable.
"""
import argparse
from fractions import Fraction
import json
import math
import os
from pathlib import Path
import socket
import sys
import time
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def crop_bounds(size,roi):
    w,h=size
    if (len(roi)!=4 or not all(type(v) in (int,float) and math.isfinite(v) for v in roi)
        or not 0<=roi[0]<roi[2]<=1 or not 0<=roi[1]<roi[3]<=1):
        raise ValueError('Fixed normalized ROI required')
    return [max(0,math.floor(roi[0]*w)),max(0,math.floor(roi[1]*h)),
            min(w,math.ceil(roi[2]*w)),min(h,math.ceil(roi[3]*h))]


def restore_box(local_box,pixels,size):
    if len(local_box)!=4 or not all(type(v) in (int,float) and math.isfinite(v) for v in local_box):
        raise ValueError('Finite model-returned xyxy required')
    x1,y1,x2,y2=pixels;w,h=size;cw,ch=x2-x1,y2-y1
    if not 0<=x1<x2<=w or not 0<=y1<y2<=h:raise ValueError('Actual bounded integer crop required')
    a,b,c,d=local_box
    restored=[min(x2,max(x1,a+x1)),min(y2,max(y1,b+y1)),
              min(x2,max(x1,c+x1)),min(y2,max(y1,d+y1))]
    return dict(bbox_original_pixels=restored,bbox_normalized=[v/(w if i%2==0 else h) for i,v in enumerate(restored)],
        valid=restored[0]<restored[2] and restored[1]<restored[3],
        touches_crop_edge=a<=.5 or b<=.5 or c>=cw-.5 or d>=ch-.5,
        coordinate_mapping='native crop model output + integer offset once; no extra scaling')


def person_rows(prediction,pixels,size):
    """All model-returned person rows before project .5/.25 diagnostic views."""
    boxes,scores,labels=prediction['boxes'],prediction['scores'],prediction['labels']
    if not len(boxes)==len(scores)==len(labels):raise ValueError('Model output lengths differ')
    rows=[]
    for index,(box,score,label) in enumerate(zip(boxes,scores,labels)):
        if label!=1:continue
        if not math.isfinite(score) or not 0<=score<=1:raise ValueError('Invalid returned score')
        rows.append(dict(model_output_index=index,score=score,model_returned_crop_box=list(box),
                         **restore_box(box,pixels,size)))
    views={str(cut):[r['model_output_index'] for r in rows if r['valid'] and r['score']>=cut] for cut in (.5,.25)}
    return rows,views


# The canonical inherited-lock + recorded parent/child identity handshake is
# intentionally identical to the existing EXP29 runner, with this job's contract.
import fcntl
import sqlite3
from orchestration.mock_job import atomic_json
from orchestration.queue import digest,process_state,source_hash
from orchestration.exp39_roi_command import (ROOT,RUNTIME,LOCAL,CACHE,VIDEO,WEIGHT,INTERPRETER,
    SETTINGS,output_path,validate,validate_assignment,execution_guard,input_contract)
from batch04_pose.runner import resources,DeviceSampler,deny_network


def verify_lease(config, attempt, fd):
    if len(attempt) != 32 or any(c not in '0123456789abcdef' for c in attempt):
        raise ValueError('invalid EXP39 ROI attempt')
    inherited, canonical = os.fstat(fd), (RUNTIME / 'gpu.lock').stat()
    if (inherited.st_dev, inherited.st_ino) != (canonical.st_dev, canonical.st_ino):
        raise ValueError('canonical inherited queue descriptor required')
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        raise ValueError('descriptor does not own inherited reservation') from exc
    with (RUNTIME / 'gpu.lock').open('r') as other:
        try:
            fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            pass
        else:
            raise ValueError('canonical queue reservation is not held')
    # Parent records the child immediately after Popen; no model import during that handshake.
    row = None
    for _ in range(100):
        with sqlite3.connect(f'file:{RUNTIME / "queue.sqlite3"}?mode=ro', uri=True) as db:
            db.row_factory = sqlite3.Row
            row = db.execute('SELECT a.status AS attempt_status,a.supervisor_pid,a.supervisor_identity,'
                'a.child_pid,a.child_identity,j.* FROM attempts a JOIN jobs j USING(job_id) '
                'WHERE a.attempt_id=?', (attempt,)).fetchone()
        if row is None or row['child_pid'] is not None:
            break
        time.sleep(.01)
    if row is None or row['attempt_status'] != 'running' or row['status'] != 'running' or row['command'] != 'exp39-roi':
        raise ValueError('live EXP39 ROI queue attempt required')
    if row['supervisor_pid'] != os.getppid() or process_state(row['supervisor_pid'], row['supervisor_identity']) != 'live':
        raise ValueError('exact live queue supervisor must be parent')
    if row['child_pid'] != os.getpid() or process_state(row['child_pid'], row['child_identity']) != 'live':
        raise ValueError('recorded exact child identity required')
    if json.loads(row['config_json']) != config:
        raise ValueError('live queue config differs')
    authorization = validate_assignment(row['run_id'], row['task_id'], row['dispatch_id'])
    if authorization['code_sha'] != row['code_sha']:
        raise ValueError('queue commit differs from coordinator-confirmed code freeze')
    inputs = json.loads(row['input_json'])
    if digest(inputs) != row['input_hash'] or digest(config) != row['config_hash'] or source_hash('exp39-roi', config) != row['source_hash']:
        raise ValueError('source/input/config queue hashes differ')
    validate(config, inputs, RUNTIME)
    with sqlite3.connect(f'file:{RUNTIME / "queue.sqlite3"}?mode=ro', uri=True) as db:
        execution_guard(db, row, attempt)
    if Path(sys.executable).absolute() != INTERPRETER:
        raise ValueError('fixed original EXP39 ROI interpreter required')
    return dict(row)



def infer_windows(model,torch,contract,folder,summary):
    import numpy as np
    from sceneguard.run_tracklet_linking import decode_native
    pixels=crop_bounds([1920,1080],SETTINGS['roi']);x1,y1,x2,y2=pixels
    def tensor(bgr):
        rgb=np.ascontiguousarray(bgr[y1:y2,x1:x2,::-1])
        return torch.from_numpy(rgb).permute(2,0,1).to('cuda',dtype=torch.float32)/255.
    # Warmups use only 10 actual approved source crops, separate from the 86
    # measured samples. No zero image or additional unapproved native frame.
    warm_rows=contract['schedule'][0]['rows'][:10]
    start=time.perf_counter()
    for _,bgr in decode_native(VIDEO,warm_rows):
        summary['warmup_attempts']+=1
        with torch.inference_mode():model([tensor(bgr)])
        torch.cuda.synchronize();summary['warmup_calls']+=1
    summary['warmup_seconds']=time.perf_counter()-start
    torch.cuda.reset_peak_memory_stats()
    samples_begin=time.perf_counter()
    for window in contract['schedule']:
        target=folder/window['segment'];target.mkdir()
        entries=[]
        with (target/'person_cache.jsonl').open('x') as cache:
            for offset,bgr in decode_native(VIDEO,window['rows']):
                row=window['rows'][offset];begin=time.perf_counter();t=tensor(bgr)
                torch.cuda.synchronize();prepared=time.perf_counter()
                summary['sample_attempts']+=1
                with torch.inference_mode():prediction=model([t])[0]
                torch.cuda.synchronize();inferred=time.perf_counter();summary['sample_calls']+=1
                returned={k:prediction[k].detach().cpu().tolist() for k in ('boxes','scores','labels')}
                people,views=person_rows(returned,pixels,row['source_size'])
                valid=[r for r in people if r['valid']]
                record=dict(**row,boxes=[r['bbox_original_pixels'] for r in valid],scores=[r['score'] for r in valid],
                    model_returned_person_rows=people,diagnostic_views=views,
                    input_geometry=dict(source_size=row['source_size'],normalized_roi=SETTINGS['roi'],pixel_crop=pixels,
                        crop_size=[x2-x1,y2-y1],scale_external=[1.,1.],offset=[x1,y1],
                        detector_input='native ROI crop; original full-frame cache retained separately'),
                    observed_model_transform=summary['last_model_transform'],
                    scope='separateROIcomparison_notfullframecache_nottrackerinput',identity_truth=False,
                    uncertainty='Partial body / crop-edge / gate occlusion; box count is not visibility or identity truth',
                    seconds=dict(preprocess=prepared-begin,detector=inferred-prepared,total=time.perf_counter()-begin))
                cache.write(json.dumps(record,allow_nan=False)+'\n');cache.flush();entries.append(record)
        summary['windows'].append(dict(segment=window['segment'],frames=len(entries),
            first_pts=entries[0]['pts'],last_pts=entries[-1]['pts'],
            returned_person_rows=sum(len(r['model_returned_person_rows']) for r in entries),
            diagnostic_view_counts={str(c):sum(len(r['diagnostic_views'][str(c)]) for r in entries) for c in (.5,.25)}))
    summary['sample_loop_seconds']=time.perf_counter()-samples_begin
    summary['generation_peak_allocated_bytes']=torch.cuda.max_memory_allocated()
    summary['generation_peak_reserved_bytes']=torch.cuda.max_memory_reserved()
    if (summary['sample_calls']!=86 or summary['warmup_calls']!=10 or summary['model_loads']!=1
        or len(summary['windows'])!=2 or any(w['frames']!=43 for w in summary['windows'])):
        raise ValueError('Bounded calls/frame count mismatch')


def run(stage,attempt,fd):
    begin=time.perf_counter();config=dict(stage=stage,settings=SETTINGS)
    job=verify_lease(config,attempt,fd)
    contract=input_contract();folder=output_path(stage,attempt);folder.mkdir(parents=True,exist_ok=False)
    summary=dict(status='preflight',attempt_id=attempt,settings=SETTINGS,windows=[],model_loads=0,
        warmup_attempts=0,warmup_calls=0,sample_attempts=0,sample_calls=0,detector_sample_calls=0,
        tracker_calls=0,alarm_changes=0,identity_truth=False,automatic_adoption=False,
        registration={k:job[k] for k in ('job_id','run_id','task_id','dispatch_id','code_sha','source_hash','input_hash','config_hash')},
        baseline_fullframe_inference_calls=0,existing_fullframe_cache_sha256=contract['files']['outputs/cv_phase2d/cache030/person_cache.jsonl'])
    monitor=None
    try:
        summary['resource_gate']=resources()
        os.environ.update(HF_HUB_OFFLINE='1',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
        socket.socket.connect=deny_network;socket.socket.connect_ex=deny_network
        socket.socket.sendto=deny_network;socket.create_connection=deny_network;socket.getaddrinfo=deny_network
        import torch
        if not torch.cuda.is_available():raise ValueError('CUDA required; no fallback')
        torch.set_num_threads(2);torch.manual_seed(0)
        torch.backends.cudnn.benchmark=False;torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
        monitor=DeviceSampler();monitor.start()
        from sceneguard.detectors import build_detector
        load=time.perf_counter();model=build_detector('fcos800')
        model.load_state_dict(torch.load(WEIGHT,map_location='cpu',weights_only=True));model.to('cuda');torch.cuda.synchronize()
        summary['model_loads']=1;summary['model_load_seconds']=time.perf_counter()-load
        actual={k:getattr(model,k) for k in SETTINGS['model_postprocess']}
        if actual!=SETTINGS['model_postprocess'] or list(model.transform.min_size)!=[800] or model.transform.max_size!=1333:
            raise ValueError('Original FCOS transform/internal postprocess differs')
        def observe(module,inputs,result):
            summary['last_model_transform']=dict(resized_hw=[list(s) for s in result[0].image_sizes],padded_nchw=list(result[0].tensors.shape))
        model.transform.register_forward_hook(observe)
        atomic_json(folder/'summary.json',summary)
        infer_windows(model,torch,contract,folder,summary)
        summary['detector_sample_calls']=summary['sample_calls']
        validate(config,contract,RUNTIME)
        summary['status']='succeeded'
    except BaseException as exc:
        summary.update(status='failed',error_type=type(exc).__name__,error=str(exc),traceback=traceback.format_exc())
        raise
    finally:
        if monitor:
            monitor.stop();summary['device_samples']=monitor.samples;summary['device_sample_errors']=monitor.errors
        summary['run_entry_seconds']=time.perf_counter()-begin
        atomic_json(folder/'summary.json',summary)
        atomic_json(LOCAL/('roi-receipt-'+attempt+'.json'),summary)
    return summary


def render_comparisons(folder, output):
    """CPU-only original / saved full-frame / new ROI comparison, never inference."""
    import av
    import cv2
    import numpy as np
    from sceneguard.run_tracklet_linking import decode_native
    from orchestration.exp39_roi_command import schedule
    from orchestration.vlm_command import file_hash
    folder,output=Path(folder),Path(output)
    if output.exists():raise ValueError('Fresh comparison folder required')
    run=json.loads((folder/'summary.json').read_text())
    if run['status']!='succeeded':raise ValueError('Completed separate ROI comparison required')
    if file_hash(CACHE/'person_cache.jsonl')!=run['existing_fullframe_cache_sha256']:
        raise ValueError('Original full-frame cache changed')
    cached=[json.loads(line) for line in (CACHE/'person_cache.jsonl').read_text().splitlines()]
    expected=schedule(cached);pixels=crop_bounds([1920,1080],SETTINGS['roi']);x1,y1,x2,y2=pixels
    output.mkdir(parents=True,exist_ok=False);receipts=[]
    for window in expected:
        sid=window['segment'];rows=[json.loads(line) for line in (folder/sid/'person_cache.jsonl').read_text().splitlines()]
        if len(rows)!=43:raise ValueError('Exactly43 ROI frames required')
        for row,original in zip(rows,window['rows']):
            if any(row[k]!=v for k,v in original.items()):raise ValueError('ROI/native source mismatch')
            for person in row['model_returned_person_rows']:
                restored=restore_box(person['model_returned_crop_box'],pixels,[1920,1080])
                if restored['bbox_original_pixels']!=person['bbox_original_pixels']:
                    raise ValueError('ROI restored box mismatch')
        target=output/(sid+'.mp4');mapping=[]
        with av.open(str(target),'w') as container:
            stream=container.add_stream('libx264',rate=30);stream.width=1920;stream.height=488
            stream.pix_fmt='yuv420p';stream.time_base=Fraction('1/15360');stream.codec_context.time_base=stream.time_base
            stream.options={'crf':'20','preset':'fast'}
            for offset,bgr in decode_native(VIDEO,window['rows']):
                row=rows[offset];original=cached[row['frame_index']]
                panels=[bgr.copy(),bgr[y1:y2,x1:x2].copy(),bgr[y1:y2,x1:x2].copy()]
                for panel,boxes,scores in ((panels[1],original['boxes'],original['scores']),
                                           (panels[2],row['boxes'],row['scores'])):
                    for box,score in zip(boxes,scores):
                        a,b,c,d=box
                        if c<x1 or a>x2 or d<y1 or b>y2:continue
                        color=(0,220,0) if score>=.5 else (0,220,255) if score>=.25 else (190,190,190)
                        first=(round(a-x1),round(b-y1));last=(round(c-x1),round(d-y1))
                        cv2.rectangle(panel,first,last,color,2)
                        cv2.putText(panel,f'{score:.3f}',(max(0,first[0]),max(15,first[1]-3)),0,.45,color,1)
                canvas=np.zeros((488,1920,3),dtype=np.uint8)
                for i,panel in enumerate(panels):
                    ratio=min(640/panel.shape[1],360/panel.shape[0]);resized=cv2.resize(panel,(round(panel.shape[1]*ratio),round(panel.shape[0]*ratio)))
                    canvas[128:128+resized.shape[0],640*i:640*i+resized.shape[1]]=resized
                lines=[f"EXP39 ROI {sid} | native PTS {row['native_pts']} * {row['time_base']} = {row['pts']:.6f}s",
                    'ORIGINAL FULL FRAME                 FULL-FRAME STORED CACHE in ROI             NEW ROI INPUT FCOS (separate cache)',
                    'green >=.50 | yellow >=.25 | gray model-returned <.25 | same model/internal filters; input crop only',
                    'Partial body / gate occlusion / crop-edge uncertain; boxes NOT identity truth. Original alarms unchanged.']
                for n,line in enumerate(lines):cv2.putText(canvas,line,(10,23+n*28),0,.55,(230,230,230),1)
                frame=av.VideoFrame.from_ndarray(canvas,format='bgr24')
                frame.pts=row['native_pts']-rows[0]['native_pts'];frame.time_base=stream.time_base
                for packet in stream.encode(frame):container.mux(packet)
                mapping.append(dict(native_pts=row['native_pts'],time_base=row['time_base'],source_pts=row['pts'],
                    presentation_pts=float((row['native_pts']-rows[0]['native_pts'])*Fraction(row['time_base']))))
                if offset in (0,21,42):
                    if not cv2.imwrite(str(output/(sid+f'-{offset:02d}.jpg')),canvas):raise ValueError('Evidence still write failed')
            for packet in stream.encode():container.mux(packet)
        with av.open(str(target)) as container:stamps=[float(f.pts*f.time_base) for f in container.decode(video=0)]
        if len(stamps)!=43 or any(abs(t-r['presentation_pts'])>1e-6 for t,r in zip(stamps,mapping)):
            raise ValueError('ROIcomparison PTS mismatch')
        receipts.append(dict(segment=sid,path=str(target),sha256=file_hash(target),frames=43,pts_mapping=mapping,
            first_pts=stamps[0],last_pts=stamps[-1],visual_semantics='Codex draft, human review pending'))
    atomic_json(output/'render-receipt.json',dict(videos=receipts,code_sha256=file_hash(Path(__file__)),
        source_summary_sha256=file_hash(folder/'summary.json'),detector_calls=0,alarm_changes=0))
    return receipts


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage',choices=['roi030'],required=True);p.add_argument('--attempt',required=True)
    p.add_argument('--lock-fd',type=int,required=True)
    args=p.parse_args();run(args.stage,args.attempt,args.lock_fd)
