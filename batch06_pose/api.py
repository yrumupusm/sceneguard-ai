# SPDX-License-Identifier: AGPL-3.0-only
"""CPU audit of the one-axis public kwargs and real installed preprocessing."""
import inspect
from batch04_pose.api import official_audit as historical_audit
from orchestration.batch06_pose_command import PREDICT_KWARGS,BASE_KWARGS


def official_audit():
    import numpy as np
    import torch
    from types import SimpleNamespace
    from ultralytics.engine.model import Model
    from ultralytics.engine.predictor import BasePredictor
    from ultralytics.cfg import get_cfg,DEFAULT_CFG_DICT
    a=historical_audit()
    if set(PREDICT_KWARGS)!=set(BASE_KWARGS) or [k for k in BASE_KWARGS if BASE_KWARGS[k]!=PREDICT_KWARGS[k]]!=['imgsz']:
        raise ValueError('one axis required')
    inspect.signature(Model.predict).bind(None,source=object(),**PREDICT_KWARGS)
    call={k:v for k,v in PREDICT_KWARGS.items() if k!='stream'}
    if not set(call)<=set(DEFAULT_CFG_DICT):raise ValueError('unsupported public kwargs')
    cfg=get_cfg(overrides=call)
    if any(getattr(cfg,k)!=v for k,v in call.items()):raise ValueError('public config changed')
    # No model instance or CUDA: exercise official letterbox/preprocess with a CPU descriptor.
    descriptor=SimpleNamespace(args=cfg,imgsz=[960,960],scale_fill=False,device=torch.device('cpu'),
        model=SimpleNamespace(fp16=False,stride=32,pt=True,dynamic=False,imx=False))
    descriptor.pre_transform=lambda images:BasePredictor.pre_transform(descriptor,images)
    tensor=BasePredictor.preprocess(descriptor,[np.zeros((648,903,3),np.uint8)])
    if list(tensor.shape)!=[1,3,960,960] or tensor.dtype!=torch.float32:raise ValueError('960 preprocess shape differs')
    if torch.cuda.is_initialized():raise ValueError('CPU audit initialized CUDA')
    return dict(a,kwargs=PREDICT_KWARGS,changed_keys=['imgsz'],expected_gpu_shape=[1,3,960,960],
        synthetic_cpu_shape=list(tensor.shape),cpu_dtype=str(tensor.dtype),model_constructions=0,cuda_initialized=False)
