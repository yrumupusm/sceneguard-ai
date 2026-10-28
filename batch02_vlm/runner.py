"""Canonical queue child. All authority and hash checks precede torch imports."""
import argparse
from datetime import datetime,timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from orchestration.batch02_vlm_command import (ROOT,RUNTIME,MODEL,SETTINGS,QUANTIZATION,
    input_contract,manifest,output_path,source_hash,validate,validate_assignment)
from orchestration.queue import digest,process_state
from orchestration.mock_job import atomic_json


def verify_lease(config,attempt,lock_fd):
    output_path(config['condition_id'],attempt)
    inherited,canonical=os.fstat(lock_fd),(RUNTIME/'gpu.lock').stat()
    if (inherited.st_dev,inherited.st_ino)!=(canonical.st_dev,canonical.st_ino):
        raise ValueError('canonical inherited lock required')
    try:
        fcntl.flock(lock_fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError as exc:
        raise ValueError('descriptor does not own inherited reservation') from exc
    with (RUNTIME/'gpu.lock').open() as other:
        try:
            fcntl.flock(other,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            pass
        else:
            raise ValueError('canonical lock not held')
    with sqlite3.connect(f'file:{RUNTIME/"queue.sqlite3"}?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        # Supervisor records the child immediately after Popen. Wait only for that receipt.
        for _ in range(100):
            row=db.execute('SELECT a.status AS attempt_status,a.supervisor_pid,a.supervisor_identity,a.child_pid,a.child_identity,a.started_at AS attempt_started_at,j.* FROM attempts a JOIN jobs j USING(job_id) WHERE a.attempt_id=?',(attempt,)).fetchone()
            if row is None or row['child_pid'] is not None:
                break
            time.sleep(.01)
    if row is None or row['attempt_status']!='running' or row['status']!='running' or row['command']!='vlm-batch02':
        raise ValueError('live exact VLM attempt required')
    if row['supervisor_pid']!=os.getppid() or process_state(row['supervisor_pid'],row['supervisor_identity'])!='live':
        raise ValueError('live exact supervisor must be parent')
    if row['child_pid']!=os.getpid() or process_state(row['child_pid'],row['child_identity'])!='live':
        raise ValueError('live exact child identity required')
    if json.loads(row['config_json'])!=config or row['config_hash']!=digest(config):
        raise ValueError('live attempt config differs')
    assignment=validate_assignment(row['run_id'],row['task_id'],row['dispatch_id'])
    inputs=input_contract(config['condition_id'])
    if json.loads(row['input_json'])!=inputs or row['input_hash']!=digest(inputs) or row['source_hash']!=source_hash():
        raise ValueError('live attempt input/source hashes differ')
    if row['code_sha']!=assignment['source_commit']:
        raise ValueError('committed source differs from assignment')
    validate(config,inputs,RUNTIME)
    return dict(row)


def resources():
    raw=subprocess.check_output(['nvidia-smi','-i','0','--query-gpu=memory.used,memory.free','--format=csv,noheader,nounits'],text=True)
    used,free=map(int,raw.strip().split(','))
    if free<6144:
        raise ValueError('minimum free 6144 MiB gate failed')
    return dict(used_mib=used,free_mib=free)


def decode(row):
    import av
    import numpy as np
    from fractions import Fraction
    source=json.loads((ROOT/row['source_metadata']).read_text())
    found=[]
    with av.open(str(ROOT/row['source_path'])) as container:
        stream=container.streams.video[0]
        stream.thread_type='NONE'
        for native,base in zip(source['native_pts'],source['time_base']):
            if stream.time_base!=Fraction(base):
                raise ValueError('native time base differs')
            container.seek(native,stream=stream,backward=True,any_frame=False)
            for frame in container.decode(stream):
                if frame.pts==native:
                    found.append(frame.to_ndarray(format='rgb24'))
                    break
                if frame.pts is not None and frame.pts>native:
                    raise ValueError('exact native PTS missing')
            else:
                raise ValueError('native PTS not decoded')
    rgb=np.stack(found)
    if len(rgb)!=10 or hashlib.sha256(rgb.tobytes()).hexdigest()!=source['rgb_sha256']:
        raise ValueError('exact source RGB differs')
    if [hashlib.sha256(f.tobytes()).hexdigest() for f in rgb]!=row['source_frame_sha256']:
        raise ValueError('per-frame original RGB differs')
    source['last_decoded_pts']=source['pts_seconds'][-1]
    return rgb,source


def validate_prepared(row,info,frames,expanded):
    import numpy as np
    expected=row['expected_metadata']
    for key,value in expected.items():
        if key=='last_decoded_pts':
            continue  # Seek decoder stops on the last observation; old traversal decoded further.
        if info.get(key)!=value:
            raise ValueError('processor baseline metadata differs: '+key)
    if not np.array_equal(frames,np.load(ROOT/row['parity_rgb'],allow_pickle=False)):
        raise ValueError('saved EXP17 processor RGB differs')
    if row['parity_prompt'] is not None and expanded!=(ROOT/row['parity_prompt']).read_text():
        raise ValueError('saved original v expanded prompt differs')
    return dict(source_pts_rgb_crop_and_metadata=True,
        actual_last_decoded_pts=info['last_decoded_pts'],historical_last_decoded_pts=expected['last_decoded_pts'],processor_RGB_matches_saved_EXP17=True,
        original_baseline_processor_RGB='exact_saved_v' if row['parity_prompt'] else 'unavailable_historical_q',
        original_baseline_expanded_prompt='exact_saved_v' if row['parity_prompt'] else 'unavailable_historical_q')


def load_kwargs(torch,BitsAndBytesConfig):
    q=dict(QUANTIZATION)
    q['bnb_4bit_compute_dtype']=torch.bfloat16
    q['bnb_4bit_quant_storage']=torch.uint8
    return dict(local_files_only=True,torch_dtype=torch.bfloat16,attn_implementation='sdpa',
        device_map={'':'cuda:0'},quantization_config=BitsAndBytesConfig(**q))


def inventory(model):
    import torch
    from bitsandbytes.nn import Linear4bit
    modules=[];quant_states=[]
    for name,module in model.named_modules():
        if isinstance(module,Linear4bit):
            if name.startswith('model.visual') or name=='lm_head' or not name.startswith('model.language_model.'):
                raise ValueError('unexpected 4bit replacement: '+name)
            state=module.weight.quant_state
            if (module.compute_dtype!=torch.bfloat16 or module.weight.dtype!=torch.uint8 or module.weight.quant_type!='nf4' or
                state is None or not state.nested):
                raise ValueError('actual NF4 double quant BF16 configuration differs')
            for state_name,qs in [('primary',state),('nested',state.state2)]:
                for key in ('absmax','code','offset'):
                    tensor=getattr(qs,key,None)
                    if tensor is not None:
                        if str(tensor.device)!='cuda:0':
                            raise ValueError('quantization state offload forbidden: '+name)
                        quant_states.append(dict(module=name,state=state_name,key=key,dtype=str(tensor.dtype),device=str(tensor.device),shape=list(tensor.shape)))
            modules.append(name)
        elif isinstance(module,torch.nn.Linear) and name.startswith('model.language_model.'):
            raise ValueError('language Linear escaped NF4 conversion: '+name)
    expected=model.config.text_config.num_hidden_layers*7
    if len(modules)!=expected:
        raise ValueError('actual language Linear4bit replacement count differs')
    params=[]
    for name,p in model.named_parameters():
        if str(p.device)!='cuda:0':
            raise ValueError('CPU/disk/meta/offload parameter forbidden: '+name)
        if (name.startswith('model.visual.') or name.startswith('lm_head.')) and p.dtype!=torch.bfloat16:
            raise ValueError('vision/output parameters must remain BF16')
        if p.is_floating_point() and p.dtype!=torch.bfloat16:
            raise ValueError('nonquantized floating parameters must remain BF16: '+name)
        params.append(dict(name=name,shape=list(p.shape),dtype=str(p.dtype),device=str(p.device)))
    buffers=[]
    for name,b in model.named_buffers():
        if str(b.device)!='cuda:0':
            raise ValueError('non-CUDA buffer forbidden: '+name)
        buffers.append(dict(name=name,shape=list(b.shape),dtype=str(b.dtype),device=str(b.device)))
    if any(str(v) not in ('0','cuda:0') for v in model.hf_device_map.values()):
        raise ValueError('device map offload forbidden')
    return dict(quantized_modules=modules,quantization_states=quant_states,parameters=params,buffers=buffers,device_map=model.hf_device_map)


def failure_record(exc,stage,stage_started,timings,start,folder,torch_ref=None,cuda_started=False):
    """Report only already-available CUDA measurements; preflight never initializes CUDA."""
    timing=dict(timings)
    timing[stage+'_elapsed_seconds']=time.perf_counter()-stage_started
    memory=None
    if cuda_started and torch_ref is not None:
        try:
            memory=dict(allocated_bytes=torch_ref.cuda.memory_allocated(),reserved_bytes=torch_ref.cuda.memory_reserved(),
                peak_allocated_bytes=torch_ref.cuda.max_memory_allocated(),peak_reserved_bytes=torch_ref.cuda.max_memory_reserved())
        except Exception as memory_error:
            memory=dict(measurement_error=repr(memory_error))
    return dict(status='failed',stage=stage,error=repr(exc),error_type=type(exc).__name__,
        oom=('out of memory' in str(exc).lower() or 'outofmemory' in type(exc).__name__.lower()),
        traceback=traceback.format_exc(),timing=timing,gpu_memory=memory,
        elapsed_seconds=time.perf_counter()-start,generated_tokens_saved=(folder/'generated_token_ids.npy').exists(),automatic_retry=False)


def execute(condition,attempt,lock_fd):
    config=dict(condition_id=condition,settings=SETTINGS)
    start=time.perf_counter()
    job=verify_lease(config,attempt,lock_fd)
    validation_seconds=time.perf_counter()-start
    started_utc=datetime.now(timezone.utc).isoformat()
    folder=output_path(condition,attempt)
    folder.mkdir(parents=True,exist_ok=False)
    timings=dict(initial_validation_seconds=validation_seconds)
    stage='preflight';stage_started=time.perf_counter();torch_ref=None;cuda_started=False
    try:
        gate=resources()
        atomic_json(folder/'lease.json',dict(attempt=attempt,run_id=job['run_id'],task_id=job['task_id'],dispatch_id=job['dispatch_id'],code_sha=job['code_sha'],source_hash=job['source_hash'],input_hash=job['input_hash'],config_hash=job['config_hash'],preload_resource=gate))
        d=manifest();row=next(r for r in d['conditions'] if r['condition_id']==condition)
        os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
        import torch
        torch_ref=torch
        import numpy as np
        from transformers import AutoProcessor,BitsAndBytesConfig,GenerationConfig,Qwen3VLForConditionalGeneration
        from mvp.method import QwenAnalyzer
        from vlm_batch.common import parse_pair
        torch.manual_seed(0)
        # CPU input preparation and all parity checks finish before weight construction.
        stage='prepare';stage_started=time.perf_counter()
        t=time.perf_counter()
        rgb,source=decode(row)
        holder=object.__new__(QwenAnalyzer)
        holder.phase='full'
        holder.processor=AutoProcessor.from_pretrained(MODEL,local_files_only=True)
        inputs,info,frames=holder.prepare(rgb,source,row['window_id'],row['roi'])
        expanded=holder.processor.tokenizer.decode(inputs.input_ids[0],skip_special_tokens=False)
        parity=validate_prepared(row,info,frames,expanded)
        np.save(folder/'processor_rgb.npy',frames,allow_pickle=False)
        from batch02_vlm.evidence import save_sheet
        save_sheet(frames,info['source_pts'],folder/'evidence-sheet.jpg')
        np.save(folder/'input_token_ids.npy',inputs.input_ids.numpy(),allow_pickle=False)
        (folder/'expanded_prompt.txt').write_text(expanded)
        atomic_json(folder/'input.json',dict(metadata=info,parity=parity,source_frame_sha256=row['source_frame_sha256'],processor_frame_sha256=[hashlib.sha256(f.tobytes()).hexdigest() for f in frames],processor_payload_sha256=hashlib.sha256(frames.tobytes()).hexdigest()))
        prepare_seconds=time.perf_counter()-t
        timings['prepare_seconds']=prepare_seconds
        stage='preload_validation';stage_started=time.perf_counter()
        # Fresh authority/input and unchanged 6144 gate immediately before model load.
        verify_lease(config,attempt,lock_fd)
        gate=resources();torch.cuda.reset_peak_memory_stats();cuda_started=True
        timings['preload_validation_seconds']=time.perf_counter()-stage_started
        stage='load';stage_started=time.perf_counter()
        t=time.perf_counter()
        model=Qwen3VLForConditionalGeneration.from_pretrained(MODEL,**load_kwargs(torch,BitsAndBytesConfig)).eval()
        torch.cuda.synchronize();load_seconds=time.perf_counter()-t
        timings['load_seconds']=load_seconds
        stage='inventory';stage_started=time.perf_counter()
        atomic_json(folder/'module-inventory.json',inventory(model))
        load_memory=dict(peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved())
        context=model.config.text_config.max_position_embeddings
        if info['input_tokens']+384>context:
            raise ValueError('effective context insufficient')
        # Preserve official BOS/EOS/pad IDs; explicitly neutralize its sampling defaults.
        generation=GenerationConfig.from_pretrained(MODEL,local_files_only=True)
        generation.do_sample=False;generation.max_new_tokens=384;generation.repetition_penalty=1.0
        generation.temperature=1.0;generation.top_p=1.0;generation.top_k=50
        atomic_json(folder/'generation-config.json',dict(effective=generation.to_dict(),model_card_defaults=json.loads((MODEL/'generation_config.json').read_text()),override='greedy seed0 max_new384 repeat1.0; sampling defaults replaced'))
        stage='input_transfer';stage_started=time.perf_counter()
        t=time.perf_counter()
        inputs=inputs.to('cuda:0');torch.cuda.synchronize()
        transfer_seconds=time.perf_counter()-t
        timings['input_transfer_seconds']=transfer_seconds
        torch.cuda.reset_peak_memory_stats()
        t=time.perf_counter()
        stage='generation';stage_started=time.perf_counter()
        with torch.inference_mode():
            generated=model.generate(**inputs,generation_config=generation)
        torch.cuda.synchronize();seconds=time.perf_counter()-t
        timings['generation_seconds']=seconds
        stage='decode_persist';stage_started=time.perf_counter()
        tokens=generated[:,inputs.input_ids.shape[1]:].detach().cpu().numpy()
        np.save(folder/'generated_token_ids.npy',tokens,allow_pickle=False)
        # Persist tokens before decoding: decode/write failure must not trigger regeneration.
        raw=holder.processor.batch_decode(tokens,skip_special_tokens=True,clean_up_tokenization_spaces=False)[0]
        (folder/'raw_response.txt').write_text(raw)
        parsed=parse_pair(raw)
        record=dict(status='succeeded',condition_id=condition,started_utc=started_utc,
            output_utc=datetime.now(timezone.utc).isoformat(),raw_response=raw,parse=parsed,
            parsed=parsed['postprocessed_parsed'],input_metadata=info,parity=parity,
            effective_context_tokens=context,input_text_tokens=info['input_tokens']-info['visual_tokens'],
            output_tokens=int(tokens.shape[1]),hit_token_limit=bool(tokens.shape[1]>=384),
            timing=dict(**timings,
                child_total_seconds=time.perf_counter()-start,queue_wait_seconds=job['attempt_started_at']-job['created_at']),
            gpu_memory=dict(peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved()),
            load_gpu_memory=load_memory,preload_resource=gate,cost=dict(external_paid_api_cost=0,currency='USD',electricity_cost=None),
            artifacts={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file()})
        atomic_json(folder/'result.json',record)
        atomic_json(folder/'summary.json',dict(status='succeeded',condition_id=condition,result_sha256=hashlib.sha256((folder/'result.json').read_bytes()).hexdigest()))
    except Exception as exc:
        atomic_json(folder/'failure.json',failure_record(exc,stage,stage_started,timings,start,folder,torch_ref,cuda_started))
        raise


def main():
    p=argparse.ArgumentParser();p.add_argument('--condition',required=True);p.add_argument('--attempt',required=True);p.add_argument('--lock-fd',required=True,type=int)
    a=p.parse_args();execute(a.condition,a.attempt,a.lock_fd)


if __name__=='__main__':
    main()
