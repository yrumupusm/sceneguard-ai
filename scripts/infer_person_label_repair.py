"""One queue-only75-image proposal pass; original annotations never become merged GT."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]


def infer_one(model,rgb,spec,infer):
    import numpy as np
    if rgb.ndim!=3 or rgb.shape[-1]!=3 or rgb.dtype!=np.uint8:raise ValueError('One native RGB uint8 image required')
    # The existing adapter consumes only slot8. This view does not copy16 frames,
    # add temporal evidence, interpolate pixels, or use another source instant.
    return infer(model,np.broadcast_to(rgb,(16,)+rgb.shape),spec)


def proposal_rows(frame,output,spec_sha):
    import math
    boxes,scores,labels,valid=(output[k] for k in ('boxes','person_scores','native_class_ids','valid_boxes'))
    fixed=dict(input_frame_index=8,actual_input_frames=1,input_color='BGR',input_resolution=[640,640],
               full_frame=True,person_threshold=.5,retained_person_threshold=.05,
               box_format='xyxy_original_input_pixels',native_end2end=True,additional_nms=False,
               external_person_proposals=False,fcos_gating=False,climbing_score=None,action_scores=None)
    if (not len(boxes)==len(scores)==len(labels)==len(valid) or len(boxes)>300
            or any(output.get(k)!=v for k,v in fixed.items())):raise ValueError('Fixed native person-only output required')
    width,height=frame['source_size'];rows=[]
    for index,(box,score,label,ok) in enumerate(zip(boxes,scores,labels,valid)):
        if (len(box)!=4 or any(not math.isfinite(x) for x in box) or not math.isfinite(score)
                or not .05<=score<=1 or label!=0 or type(ok) is not bool
                or not 0<=box[0]<=width or not 0<=box[2]<=width
                or not 0<=box[1]<=height or not 0<=box[3]<=height
                or ok!=(box[2]>box[0] and box[3]>box[1])):raise ValueError('Invalid native person row')
        rows.append(dict(proposal_id=frame['frame_id']+f':yolo26x:{index:04d}',xyxy=box,person_score=score,
                         valid_box=ok,native_class_id=0,model_id='yolo26x',model_spec_sha256=spec_sha,
                         review_state='unreviewed_model_proposal',human_verified=False,training_eligible=False))
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--queue-config',type=Path,required=True)
    p.add_argument('--queue-config-sha256',required=True);p.add_argument('--queue-attempt',required=True)
    p.add_argument('--output',type=Path,required=True);args=p.parse_args();sys.path.insert(0,str(ROOT))
    from orchestration import person_label_repair_command as command
    from orchestration.queue import digest
    config,inputs=command.runner_guard(args)
    # No model/GPU imports occur before the actual held-FD/live assignment guard.
    import torch
    import numpy as np
    from PIL import Image
    from scripts import exp0066_yolo as adapter
    torch.set_num_threads(2);torch.manual_seed(66);torch.cuda.manual_seed_all(66)
    torch.backends.cudnn.benchmark=False;torch.cuda.reset_peak_memory_stats()
    args.output.mkdir(parents=True,exist_ok=False)
    spec=command.read(config['files']['model_spec']['path']);manifest=command.read(config['files']['preparation']['path'])
    auth=command.read(config['authorization']['path']);source_map=command.sources(config)
    started=time.perf_counter();model=adapter.load_model(spec,'cuda');torch.cuda.synchronize();load_seconds=time.perf_counter()-started
    counts=Counter();cases=Counter();proposal_count=0
    output_path=args.output/'proposals.jsonl'
    with output_path.open('x',encoding='utf-8') as stream:
        for frame in manifest['frames']:
            image=Path(frame['image']['path'])
            if command.file_hash(image)!=frame['image']['sha256']:raise ValueError('Prepared image changed')
            with Image.open(image) as im:
                if im.mode!='RGB' or list(im.size)!=frame['source_size']:raise ValueError('Native image format/geometry differs')
                rgb=np.asarray(im)
                if hashlib.sha256(rgb.tobytes()).hexdigest()!=frame['source_rgb_sha256']:raise ValueError('Native image RGB changed')
                native=infer_one(model,rgb,spec,adapter.infer_clip)
            proposals=proposal_rows(frame,native,config['files']['model_spec']['sha256'])
            row=dict(frame,proposals=proposals,detector_output=native,training_release=False,
                     detector_proposals_are_ground_truth=False,box_pts=frame['source_pts'],box_frame_index=frame['frame_index'],
                     model_provenance=dict(queue_command='person-label-repair',queue_attempt=args.queue_attempt,
                         code_sha=auth['code_sha'],source_hash=digest(source_map),input_hash=digest(inputs),
                         model_spec_sha256=config['files']['model_spec']['sha256'],checkpoint_sha256=spec['bindings'][spec['checkpoint_path']]))
            stream.write(json.dumps(row,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n');stream.flush()
            counts[frame['split']]+=1;cases[frame['case_number']]+=1;proposal_count+=len(proposals)
    if counts!={'train':50,'validation':25} or cases!={1:25,3:25,5:25}:raise ValueError('Exact75 frame coverage required')
    if command.sources(config)!=source_map or command.input_contract(config)!=inputs:raise ValueError('Source/input/environment changed during run')
    result=dict(status='draft_proposals_complete',queue_command='person-label-repair',queue_attempt=args.queue_attempt,
                stage='draft75',model_id='yolo26x',code_sha=auth['code_sha'],source_hash=digest(source_map),input_hash=digest(inputs),
                preparation_sha256=config['files']['preparation']['sha256'],model_spec_sha256=config['files']['model_spec']['sha256'],
                proposals_sha256=command.file_hash(output_path),frames_scored=75,frame_counts=dict(counts),case_counts=dict(cases),
                proposal_count=proposal_count,training_release=False,human_verified=False,detector_proposals_are_ground_truth=False,
                original_annotations_modified=False,person_precision=None,person_recall=None,intrusion_state_changed=False,
                actual_input_frames_per_scored_image=1,adapter_slots_are_repeated_single_rgb_view=True,
                total_forward_calls_measured=None,native_speed_excludes_official_warmup=True,
                load_seconds=load_seconds,elapsed_seconds=time.perf_counter()-started,
                peak_gpu_allocated_bytes=torch.cuda.max_memory_allocated(),peak_gpu_reserved_bytes=torch.cuda.max_memory_reserved())
    with (args.output/'result.json').open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2,sort_keys=True,allow_nan=False);stream.write('\n')
    print(json.dumps(result,sort_keys=True),flush=True)


if __name__=='__main__':main()
