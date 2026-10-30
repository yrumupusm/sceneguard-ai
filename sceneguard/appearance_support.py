"""EXP-0034 visible-clothing comparison. No face identity or intrusion verdict.

Existing local Qwen processor/model is supplied by the canonical GPU runner.
CPU parser/fusion tests never instantiate or download a model.
"""
import json
import re
import hashlib
import time

IMAGE_BUDGET = {'min_pixels':64*32*32,'max_pixels':256*32*32}

PROMPT = '''A와 B는 서로 다른 시점의 대상 이미지 묶음이다. 이름이나 얼굴 신원은 판단하지 말고 보이는 의복과 가방만 비교해.
상의는 상의끼리, 하의는 하의끼리, 가방은 가방끼리 비교해. 어느 한쪽에서 가려지거나 안 보이면 unavailable이다. 안 보이는 부분을 다르다고 판단하거나 복원하지 마. 비슷한 색 하나만으로 같은 대상이라고 확정하지 마. 두 사람이 섞이거나 대상을 구분하기 어렵다면 decision은 unknown이다.
침입 여부, 위치, 이동 방향은 판단하지 마. JSON 한 개만 답해:
{"upper":"match|different|unavailable","lower":"match|different|unavailable","bag":"match|different|unavailable","decision":"compatible|different|unknown"}
compatible은 외형상 연결 가능한 후보라는 뜻이며 동일인 확정이 아니다. 공통으로 보이는 비교 근거가 없으면 unknown이다.'''


def parse_comparison(raw):
    """Reject invalid/mutually inconsistent responses; do not repair their meaning."""
    def unique(pairs):
        obj={}
        for k,v in pairs:
            if k in obj:
                raise ValueError('Duplicate key')
            obj[k]=v
        return obj
    text=raw.strip()
    match=re.fullmatch(r'```(?:json)?\s*\n([\s\S]*?)\n```',text)
    if match:
        text=match[1]
    try:
        obj=json.loads(text,object_pairs_hook=unique)
        if not isinstance(obj,dict) or set(obj)!={'upper','lower','bag','decision'}:
            raise ValueError('Wrong keys')
        vals=[obj[k] for k in ('upper','lower','bag')]
        if any(v not in ('match','different','unavailable') for v in vals) or obj['decision'] not in ('compatible','different','unknown'):
            raise ValueError('Wrong enums')
        if obj['decision']=='compatible' and ('match' not in vals or 'different' in vals):
            raise ValueError('Unsupported compatibility claim')
        if obj['decision']=='different' and 'different' not in vals:
            raise ValueError('Unavailable is not different')
        return {'valid':True,'comparison':obj,'identity_verified':False}
    except (ValueError,TypeError):
        return {'valid':False,'comparison':{'upper':'unavailable','lower':'unavailable',
                                           'bag':'unavailable','decision':'unknown'},
                'identity_verified':False,'reason':'invalid_or_contradictory_model_output'}


def prepare_images(processor, before, after):
    """CPU-only pinned processor preparation, recording its actual ordered images."""
    import numpy as np
    from PIL import Image
    if not (1<=len(before)<=3 and 1<=len(after)<=3):
        raise ValueError('Use one to three actual target crops per side')
    images=[]
    content=[]
    for label, group in (('A',before),('B',after)):
        content.append({'type':'text','text':f'{label}의 이미지:'})
        for image in group:
            if not isinstance(image,np.ndarray) or image.dtype!=np.uint8 or image.ndim!=3 or image.shape[2]!=3 or min(image.shape[:2])<16:
                raise ValueError('Actual nonempty RGB uint8 crops required')
            images.append(Image.fromarray(image))
            content.append({'type':'image'})
    content.append({'type':'text','text':PROMPT})
    text=processor.apply_chat_template([{'role':'user','content':content}],tokenize=False,add_generation_prompt=True)
    captured={}
    original=processor.image_processor.resize
    def resize(image, **kwargs):
        result=original(image,**kwargs)
        key=tuple(image.shape[-2:])
        if key in captured:
            raise ValueError('Unexpected repeated image resize group')
        captured[key]=result.detach().cpu().clone()
        return result
    processor.image_processor.resize=resize
    try:
        inputs=processor(text=[text],images=images,return_tensors='pt',
                         images_kwargs=IMAGE_BUDGET.copy())
    finally:
        processor.image_processor.resize=original
    offsets={}
    actual=[]
    for img in images:
        key=(img.height,img.width)
        index=offsets.get(key,0)
        if key not in captured or index>=len(captured[key]):
            raise ValueError('Processor image ordering/capture mismatch')
        actual.append(captured[key][index].permute(1,2,0).numpy().astype('uint8'))
        offsets[key]=index+1
    if sum(len(x) for x in captured.values())!=len(images):
        raise ValueError('Processor added or removed images')
    grid=inputs['image_grid_thw'].tolist()
    if len(grid)!=len(images) or any(g[0]!=1 for g in grid):
        raise ValueError('One static image grid per native crop required')
    metadata=dict(image_budget=IMAGE_BUDGET.copy(),image_grid_thw=grid,
        input_tokens=int(inputs['input_ids'].shape[1]),
        input_shapes=[list(x.shape) for x in (*before,*after)],
        processor_shapes=[list(x.shape) for x in actual],
        processor_rgb_sha256=[hashlib.sha256(x.tobytes()).hexdigest() for x in actual],
        tensor_shapes={k:list(v.shape) for k,v in inputs.items()},
        extra_sampling=False,explicit_padding=False,
        static_image_temporal_patch_repeats=processor.image_processor.temporal_patch_size-1,
        static_repeats_are_new_observations=False,
        frame_groups=[len(before),len(after)])
    expanded=processor.tokenizer.decode(inputs['input_ids'][0],skip_special_tokens=False)
    return inputs,metadata,actual,expanded


def compare_images(analyzer, before, after):
    """One greedy generation inside the existing canonical MVP lease; no retry."""
    from mvp.runner import verify_environment_lease
    verify_environment_lease()
    import torch
    for key,value in [('last_generated_token_ids',[]),('last_processor_images',None),
                      ('last_expanded_prompt',None),('last_input_metadata',None)]:
        setattr(analyzer,key,value)
    torch.cuda.reset_peak_memory_stats()
    t=time.perf_counter()
    inputs,info,actual,expanded=prepare_images(analyzer.processor,before,after)
    analyzer.last_processor_images=actual
    analyzer.last_expanded_prompt=expanded
    analyzer.last_input_metadata=info
    inputs=inputs.to(analyzer.settings['device'])
    torch.cuda.synchronize()
    prepare_seconds=time.perf_counter()-t
    # Save processor diagnostics before generation, including a failed generation.
    callback=getattr(analyzer,'appearance_diagnostics',None)
    if callback:
        callback()
    t=time.perf_counter()
    with torch.inference_mode():
        generated=analyzer.model.generate(**inputs,do_sample=False,max_new_tokens=192)
    torch.cuda.synchronize()
    generation_seconds=time.perf_counter()-t
    output=generated[:,inputs['input_ids'].shape[1]:]
    analyzer.last_generated_token_ids=output.detach().cpu().tolist()
    if callback:
        callback()
    raw=analyzer.processor.batch_decode(output,skip_special_tokens=True,clean_up_tokenization_spaces=False)[0]
    return {'raw_response':raw,'parsed':parse_comparison(raw),'images':len(actual),
            'frame_groups':[len(before),len(after)],'intrusion_verdict':None,
            'source':'existing_local_vlm_multi_image','automatic_identity_confirmation':False,
            'timing':{'prepare_seconds':prepare_seconds,'generation_seconds':generation_seconds},
            'input_metadata':info,'output_tokens':int(output.shape[1]),
            'generation_settings':{'do_sample':False,'max_new_tokens':192},
            'hit_token_limit':bool(output.shape[1]>=192),'generation_retries':0,
            'gpu_memory':{'peak_allocated_bytes':torch.cuda.max_memory_allocated(),
                          'peak_reserved_bytes':torch.cuda.max_memory_reserved()}}


def link_proposals(pairs, responses):
    """Mutual-unique compatibility is only a proposal; +/-90 never accepts a link.

    Ambiguous targets/sources stay unresolved; no raw ID or historical alarm changes.
    """
    known={p['pair_id']:p for p in pairs}
    if len(known)!=len(pairs) or any(k not in known for k in responses):
        raise ValueError('Response pair IDs must be unique exported candidates')
    eligible=[]
    rows=[]
    for pair in pairs:
        result=responses.get(pair['pair_id'])
        parsed=parse_comparison(result) if isinstance(result,str) else None
        decision=parsed['comparison']['decision'] if parsed else 'unknown'
        row=dict(pair,appearance_decision=decision,link_status='unresolved',identity_verified=False)
        rows.append(row)
        if decision=='compatible':
            eligible.append(row)
    for row in eligible:
        src=sum(p['before']==row['before'] for p in eligible)
        dst=sum(p['after']==row['after'] for p in eligible)
        competitors=[p for p in rows if p['pair_id']!=row['pair_id'] and
                     (p['before']==row['before'] or p['after']==row['after'])]
        incomplete=any(p['appearance_decision']=='unknown' for p in competitors)
        row['link_status']=('ambiguous_not_linked' if src!=1 or dst!=1 else
                            'unresolved_competitor_coverage' if incomplete else 'review_link_proposed')
    return rows
