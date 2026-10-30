"""EXP-0034 visible-clothing comparison. No face identity or intrusion verdict.

Existing local Qwen processor/model is supplied by the canonical GPU runner.
CPU parser/fusion tests never instantiate or download a model.
"""
import json
import re

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


def compare_images(analyzer, before, after):
    """2–6 separate RGB images; no bbox half-splitting, no inferences about hidden parts.

    Call ONLY inside the existing, properly registered canonical MVP queue job.
    The caller decodes native source frames and extracts target crops with provenance.
    """
    from mvp.runner import verify_environment_lease
    verify_environment_lease()  # Before GPU use, even if a caller passes a model.
    import numpy as np
    import torch
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
    processor=analyzer.processor
    text=processor.apply_chat_template([{'role':'user','content':content}],tokenize=False,add_generation_prompt=True)
    # Fixed bounded image-token budget. Do not mutate the shared processor settings.
    inputs=processor(text=[text],images=images,return_tensors='pt',
                     images_kwargs={'min_pixels':64*32*32,'max_pixels':256*32*32})
    inputs=inputs.to(analyzer.settings['device'])
    with torch.inference_mode():
        generated=analyzer.model.generate(**inputs,do_sample=False,max_new_tokens=192)
    output=generated[:,inputs['input_ids'].shape[1]:]
    raw=processor.batch_decode(output,skip_special_tokens=True,clean_up_tokenization_spaces=False)[0]
    return {'raw_response':raw,'parsed':parse_comparison(raw),'images':len(images),
            'frame_groups':[len(before),len(after)],'intrusion_verdict':None,
            'source':'existing_local_vlm_multi_image','automatic_identity_confirmation':False}


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
        row['link_status']='review_link_proposed' if src==dst==1 else 'ambiguous_not_linked'
    return rows
