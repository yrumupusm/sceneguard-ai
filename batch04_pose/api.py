# SPDX-License-Identifier: AGPL-3.0-only
"""Public API/Results contract, importable without torch or model construction."""
import hashlib
import importlib.metadata
import inspect
from pathlib import Path
from orchestration.batch04_pose_command import PREDICT_KWARGS, COCO17


def bgr_source(rgb):
    import numpy as np
    if not isinstance(rgb, np.ndarray) or rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError('native RGB uint8 HxWx3 array required; external sources forbidden')
    return np.ascontiguousarray(rgb[..., ::-1])


def result_rows(result, shape):
    """Read native original-image coordinates once; output index is never person ID."""
    import numpy as np
    if tuple(result.orig_shape) != tuple(shape[:2]):
        raise ValueError('Results original shape mismatch')
    if result.boxes is None or result.keypoints is None:
        raise ValueError('explicit boxes and Nx17x3 keypoints required, including empty')
    boxes = result.boxes.data.detach().cpu().numpy()
    joints = result.keypoints.data.detach().cpu().numpy()
    n = len(boxes)
    if boxes.shape != (n, 6) or joints.shape != (n, 17, 3):
        raise ValueError('person row mismatch or Nx17x3 contract differs')
    if not np.isfinite(boxes).all() or not np.isfinite(joints).all():
        raise ValueError('nonfinite Results')
    h, w = shape[:2]
    persons = []
    for index, (box, kp) in enumerate(zip(boxes, joints)):
        x1, y1, x2, y2, score, cls = map(float, box)
        if not (cls == 0 and 0 <= x1 < x2 <= w and 0 <= y1 < y2 <= h and .25 < score <= 1):
            raise ValueError('original person box/class/confidence invalid')
        records = []
        for name, (x, y, c) in zip(COCO17, kp.tolist()):
            if not 0 <= c <= 1:
                raise ValueError('invalid joint confidence')
            retained = c >= .5 and 0 <= x <= w and 0 <= y <= h and (x, y) != (0., 0.)
            records.append(dict(name=name, raw_xy=[x, y], confidence=c,
                observed_xy=[x, y] if retained else None,
                status='retained_estimate' if retained else 'unknown'))
        persons.append(dict(output_index=index, xyxy=[x1,y1,x2,y2], confidence=score,
            class_id=0, keypoints=records, retained_joint_count=sum(k['observed_xy'] is not None for k in records),
            correspondence='unreviewed; output index is not track/person ID'))
    return persons


def official_audit():
    """CPU-only installed config and complete signature bindings; no YOLO instance."""
    import torch
    from ultralytics.engine.model import Model
    from ultralytics.engine.predictor import BasePredictor
    from ultralytics.cfg import get_cfg, DEFAULT_CFG_DICT
    from ultralytics.nn.autobackend import AutoBackend
    from ultralytics.nn.backends.pytorch import PyTorchBackend
    from ultralytics.nn.tasks import BaseModel
    from ultralytics.models.yolo.pose.predict import PosePredictor
    if importlib.metadata.version('ultralytics') != '8.4.192':
        raise ValueError('pinned Ultralytics required')
    call = dict(PREDICT_KWARGS)
    inspect.signature(Model.predict).bind(None, source=object(), **call)
    stream = call.pop('stream')
    if stream is not False or not set(call) <= set(DEFAULT_CFG_DICT):
        raise ValueError('unsupported public config key')
    cfg = get_cfg(overrides=call)
    for k,v in call.items():
        if getattr(cfg,k) != v:
            raise ValueError('public config value changed: ' + k)
    # Exact kwargs in the official predictor -> backend -> BaseModel path.
    inspect.signature(BasePredictor.inference).bind(None, object())
    inspect.signature(AutoBackend.forward).bind(None, object(), augment=False, embed=None)
    inspect.signature(PyTorchBackend.forward).bind(None, object(), augment=False, embed=None)
    inspect.signature(BaseModel.predict).bind(None, object(), augment=False, embed=None)
    try:
        inspect.signature(BaseModel.predict).bind(None, object(), augment=False, visualize=False, embed=None)
    except TypeError:
        regression = 'historical visualize keyword rejected before model construction'
    else:
        raise ValueError('historical regression no longer matches pinned signature')
    methods = [Model.predict, BasePredictor.preprocess, BasePredictor.inference, BasePredictor.setup_model,
        BasePredictor.stream_inference, AutoBackend.forward, AutoBackend.warmup,
        PyTorchBackend.load_model, PyTorchBackend.forward, BaseModel.predict, PosePredictor.construct_result]
    signatures = {f'{m.__qualname__}': str(inspect.signature(m)) for m in methods}
    files = {str(Path(inspect.getsourcefile(m)).relative_to(Path(torch.__file__).parents[1])):
        hashlib.sha256(Path(inspect.getsourcefile(m)).read_bytes()).hexdigest() for m in methods}
    # This checks installed routing source as well as binding, without invoking it.
    inference = inspect.getsource(BasePredictor.inference)
    setup = inspect.getsource(BasePredictor.setup_model)
    backend = inspect.getsource(PyTorchBackend.load_model)
    if 'augment=self.args.augment, embed=self.args.embed' not in inference or 'visualize=' in inference:
        raise ValueError('official inference keyword pathway changed')
    if 'fuse=True' not in setup or 'end2end=self.args.nms is False' not in setup:
        raise ValueError('official fuse/head selection pathway changed')
    if backend.index('model.end2end =') > backend.index('model.fuse('):
        raise ValueError('official head must be selected before fusion')
    if torch.cuda.is_initialized():
        raise ValueError('CPU audit must not initialize CUDA')
    return dict(package='ultralytics', version='8.4.192', kwargs=PREDICT_KWARGS,
        signatures=signatures, installed_files_sha256=files, regression=regression,
        cuda_initialized=False, model_constructions=0,
        pathway='YOLO.predict -> PosePredictor -> AutoBackend -> PyTorchBackend -> BaseModel.predict(augment,embed)',
        warmup='one CUDA PyTorch model forward on actual preprocessed input, plus synthetic random-box NMS; separate from sample predict',
        coordinates='Results already original-sized; no manual scaling')
