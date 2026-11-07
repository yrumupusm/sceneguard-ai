"""Explicit encoder/classifier adapters. No GPU or model imports on module import."""
from pathlib import Path
import time


def letterbox(frames,size):
    import cv2
    import numpy as np
    if frames.ndim!=4 or frames.shape[-1]!=3 or frames.dtype!=np.uint8:
        raise ValueError('RGB uint8 THWC frames required')
    h,w=frames.shape[1:3];scale=size/max(h,w)
    nh,nw=max(1,round(h*scale)),max(1,round(w*scale))
    top,left=(size-nh)//2,(size-nw)//2
    canvas=np.zeros((len(frames),size,size,3),dtype=np.uint8)
    for i,f in enumerate(frames):canvas[i,top:top+nh,left:left+nw]=cv2.resize(f,(nw,nh))
    return canvas,dict(source_size=[w,h],input_size=[size,size],resized_size=[nw,nh],
                       padding_xy=[left,top],scale_xy=[nw/w,nh/h],crop_xyxy=[0,0,w,h])


def load_model(spec,device):
    import importlib
    import importlib.util
    import sys
    import numpy as np
    import torch
    model_id=spec['model_id']
    if model_id=='r3d18_exp0064':
        from torchvision.models.video import r3d_18
        model=r3d_18(weights=None)
        model.fc=torch.nn.Linear(model.fc.in_features,2)
        with torch.serialization.safe_globals([np._core.multiarray._reconstruct,np.ndarray,np.dtype,
                                                type(np.dtype('uint32'))]):
            checkpoint=torch.load(spec['checkpoint_path'],map_location='cpu',weights_only=True,mmap=True)
        model.load_state_dict(checkpoint['model'],strict=True)
        if checkpoint['epoch']!=6:raise ValueError('EXP0064 epoch6 required')
        return model.eval().to(device)
    sys.path.insert(0,spec['vendor_path'])
    if model_id=='vjepa2_l':
        factory=importlib.import_module('src.models.vision_transformer').vit_large
    elif model_id=='vjepa2_1_l':
        factory=importlib.import_module('app.vjepa_2_1.models.vision_transformer').vit_large
    elif model_id=='videomaev2_b':
        factory=importlib.import_module('models.modeling_finetune').vit_base_patch16_224
    elif model_id=='internvideo_next_s2_l':
        package=Path(spec['vendor_path'])
        package_spec=importlib.util.spec_from_file_location('exp0066_ivnext',package/'__init__.py',
                                                          submodule_search_locations=[str(package)])
        module=importlib.util.module_from_spec(package_spec);sys.modules['exp0066_ivnext']=module
        package_spec.loader.exec_module(module)
        factory=importlib.import_module('exp0066_ivnext.modeling_internvideo_next').InternVideoNextBackbone
        if any(spec['constructor_kwargs'].get(k) is not False for k in
               ('use_flash_attn','use_fused_mlp','use_fused_rmsnorm')):
            raise ValueError('Explicit audited nonfused InternVideo condition required')
    else:raise ValueError('Unknown encoder: '+model_id)
    model=factory(**spec['constructor_kwargs'])
    if model_id=='internvideo_next_s2_l':
        from safetensors.torch import load_file
        state=load_file(spec['checkpoint_path'],device='cpu')
    else:
        state=torch.load(spec['checkpoint_path'],map_location='cpu',weights_only=True,mmap=True)[spec['state_container']]
    prefix=spec['state_prefix']
    if any(not k.startswith(prefix) for k in state):raise ValueError('Unexpected checkpoint key prefix')
    model.load_state_dict({k[len(prefix):]:v for k,v in state.items()},strict=True)
    return model.eval().to(device)


def infer_clip(model,frames_rgb,spec):
    import numpy as np
    import torch
    model_id=spec['model_id']
    start=time.perf_counter()
    if len(frames_rgb)!=16:raise ValueError('Declared16-frame comparison input required')
    pixels,geometry=letterbox(frames_rgb,112 if model_id=='r3d18_exp0064' else spec['resolution'])
    x=torch.from_numpy(pixels.astype(np.float32)/255).permute(3,0,1,2)
    mean=torch.tensor([0.43216,0.394666,0.37645] if model_id=='r3d18_exp0064' else [.485,.456,.406])[:,None,None,None]
    std=torch.tensor([0.22803,0.22145,0.216989] if model_id=='r3d18_exp0064' else [.229,.224,.225])[:,None,None,None]
    x=((x-mean)/std).unsqueeze(0).to(next(model.parameters()).device)
    torch.cuda.synchronize();preprocess=time.perf_counter()-start
    start=time.perf_counter()
    with torch.inference_mode(),torch.autocast('cuda',dtype=torch.float16):
        if model_id=='r3d18_exp0064':
            logits=model(x);score=float(torch.softmax(logits.float(),dim=1)[0,1].cpu())
        else:
            if model_id=='videomaev2_b':features=model.forward_features(x)
            elif model_id=='vjepa2_1_l':features=model(x,training=False)
            elif model_id=='internvideo_next_s2_l':features=model(x,projected=False)
            else:features=model(x)
            shape=list(features.shape)
            if features.ndim==3:features=features.float().mean(dim=1)
            pooled=features.float().cpu()
    torch.cuda.synchronize();infer=time.perf_counter()-start
    if model_id!='r3d18_exp0064':
        if pooled.ndim!=2 or pooled.shape[0]!=1 or not torch.isfinite(pooled).all():
            raise ValueError('Invalid pooled encoder features')
        return dict(boxes=[],person_scores=[],action_scores=[],action_label_names=[],
                    pooled_features=pooled[0].tolist(),native_feature_shape=shape,
                    climbing_score=None,output_semantics='encoder_features_without_climbing_head',
                    geometry=geometry,timing_seconds=dict(preprocess=preprocess,inference=infer,postprocess=0.0),
                    intrusion_completed=False,person_identity_verified=False)
    if not np.isfinite(score):raise ValueError('Nonfinite action output')
    return dict(boxes=[],person_scores=[],action_scores=[],action_label_names=[],
                climbing_score=score,threshold=0.5,climbing_candidate=score>=0.5,
                output_semantics='trained_actor_crop_classifier_under_new_wholeframe_16frame_condition',
                geometry=geometry,timing_seconds=dict(preprocess=preprocess,inference=infer,postprocess=0.0),
                intrusion_completed=False,person_identity_verified=False)
