"""YOLO26 pretrained person baseline; model imports occur only after queue lease validation."""
import os
from pathlib import Path

WEIGHTS = {
    'yolo26m': '401cea9ab23ad19246ff7744859816bc599f350e93c9dd30367b6f0a0745d0b7',
    'yolo26l': '9fe3c544f2b19bebad7ea41e76d7ad3d88b7c2f10d11d24430c5311f6b32db26',
    'yolo26x': '9fdd44a31c504547ffb81d2c6d9e6dac3493c8eaa8b0398d3f43bae6c7003e92',
}
PREDICT = dict(imgsz=640, rect=False, batch=1, conf=.05, device='cuda:0',
    quantize=None, nms=False, max_det=300, iou=.7, agnostic_nms=False,
    classes=[0], augment=False, compile=False, channels_last=False,
    save=False, save_txt=False, save_crop=False, show=False, verbose=False,
    stream=False, visualize=False, embed=None)


def validate_spec(spec):
    if (spec.get('model_id') not in WEIGHTS or spec.get('predict_kwargs') != PREDICT
            or spec.get('input_frame_index') != 8 or spec.get('resolution') != 640
            or spec.get('report_person_threshold') != .5
            or spec.get('ultralytics_version') != '8.4.192'
            or spec.get('bindings', {}).get(spec.get('checkpoint_path')) != WEIGHTS[spec['model_id']]):
        raise ValueError('Frozen pretrained YOLO26 weights, center frame and prediction contract required')


def configure_offline(directory):
    import socket
    def denied(*args, **kwargs):
        raise RuntimeError('Network access is disabled for local comparison inference')
    os.environ.update(YOLO_AUTOINSTALL='false', YOLO_OFFLINE='true', ULTRALYTICS_OFFLINE='true',
        YOLO_CONFIG_DIR=str(directory/'settings'), MPLCONFIGDIR=str(directory/'matplotlib'),
        HF_HUB_OFFLINE='1', WANDB_DISABLED='true', NO_ALBUMENTATIONS_UPDATE='1')
    os.environ.pop('ULTRALYTICS_API_KEY', None)
    socket.socket.connect = socket.socket.connect_ex = socket.socket.sendto = denied
    socket.create_connection = socket.getaddrinfo = denied


def load_model(spec, device):
    validate_spec(spec)
    if device not in ('cuda', 'cuda:0'):
        raise ValueError('Fixed canonical CUDA0 inference required')
    configure_offline(Path(spec['runtime_settings_directory']))
    import ultralytics
    from ultralytics import YOLO
    from ultralytics.utils import SETTINGS
    if (ultralytics.__version__ != spec['ultralytics_version']
            or Path(ultralytics.__file__).resolve().parent != Path(spec['vendor_path']).resolve()):
        raise ValueError('Pinned Ultralytics version/import origin required')
    SETTINGS.update({k:False for k in ('sync','clearml','comet','dvc','mlflow','raytune','tensorboard','wandb')})
    model = YOLO(spec['checkpoint_path'], task='detect')
    validate_loaded_model(model)
    return model


def validate_loaded_model(model):
    # 8.4.192 selects end2end from predict(nms=False) before official fusion.
    # Older official weights retain both heads but no _end2end mode flag at load.
    head=model.model.model[-1]
    if (model.task != 'detect' or model.names.get(0) != 'person'
            or getattr(head,'one2one_cv2',None) is None
            or getattr(head,'one2one_cv3',None) is None):
        raise ValueError('COCO person detector with native one-to-one heads required')
    model.model.end2end=True
    if not model.model.end2end:
        raise ValueError('Official native head selection did not take effect')


def result_rows(result, height, width):
    """Public Results.xyxy is already in original pixels; never rescale it twice."""
    import numpy as np
    if tuple(result.orig_shape) != (height, width):
        raise ValueError('Prediction source geometry differs')
    boxes = result.boxes.xyxy.detach().float().cpu().numpy()
    scores = result.boxes.conf.detach().float().cpu().numpy()
    labels = result.boxes.cls.detach().float().cpu().numpy()
    if (boxes.shape != (len(scores), 4) or labels.shape != scores.shape
            or not np.isfinite(boxes).all() or not np.isfinite(scores).all()
            or not np.isfinite(labels).all() or (labels != 0).any()
            or (scores < .05).any() or (scores > 1).any()
            or (boxes[:, [0, 2]] < 0).any() or (boxes[:, [0, 2]] > width).any()
            or (boxes[:, [1, 3]] < 0).any() or (boxes[:, [1, 3]] > height).any()):
        raise ValueError('Finite original-pixel person boxes and probabilities required')
    valid = ((boxes[:, 2] > boxes[:, 0]) & (boxes[:, 3] > boxes[:, 1])).tolist()
    return dict(boxes=boxes.tolist(), box_format='xyxy_original_input_pixels', valid_boxes=valid,
                person_scores=scores.tolist(), native_class_ids=labels.astype(int).tolist())


def infer_clip(model, frames, spec):
    import numpy as np
    validate_spec(spec)
    if frames.ndim != 4 or frames.shape[0] != 16 or frames.shape[-1] != 3 or frames.dtype != np.uint8:
        raise ValueError('Sixteen RGB uint8 cohort slots required; only slot8 is detector input')
    frame = np.ascontiguousarray(frames[8, :, :, ::-1])
    results = model.predict(source=frame, **spec['predict_kwargs'])
    if len(results) != 1 or not model.predictor.model.end2end:
        raise ValueError('Exactly one native end-to-end detector result required')
    if model.predictor.model.fp16:
        raise ValueError('FP32 detector contract required')
    result = result_rows(results[0], *frame.shape[:2])
    result.update(input_frame_index=8, actual_input_frames=1, input_color='BGR',
        input_resolution=[640,640], full_frame=True, person_threshold=.5,
        retained_person_threshold=.05, score_semantics='COCO person probability; not action probability',
        action_scores=None, climbing_score=None, external_person_proposals=False, fcos_gating=False,
        native_end2end=True, additional_nms=False, native_speed_ms=results[0].speed)
    return result
