"""Pinned independent EVAD/STMixer adapters for the root's canonical runner.

Import and CLI preparation never perform a model forward. The root owns queue
authorization, native-PTS sampling, boundary accounting, timing and GPU GO.
"""
import argparse
from dataclasses import dataclass
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'runtime/model-comparison/exp0066/joint'
ENV = ROOT / '.venv-exp0066-joint'
LABELS = FOLDER / 'ava-label-map.json'
SEMANTICS = 'AVA_v2.2_atomic_action_scores_not_CCTV_fence_climbing_or_intrusion_probability'
MODELS = {
    'evad_vitb_vmaev2': dict(vendor='EVAD-exp0066', commit='0efdb7e1156d4b0b419cd240555f8bbca45e4bf6',
        config='projects/evad/configs/ViT_B_16x4_KTP.yaml', config_sha256='be1bc6980b32faebf10c2484c06960cc13fa8c274769e9e6b55c71779fab9cca',
        checkpoint='ava_evad_vitb_maev2_kpr0.7_ep10.pth', checkpoint_sha256='c58dbffc3137638230a8a67a5bac1e2c5a9186ba653fb516ff7931e45389d645',
        short_side=288, person_threshold_original=.7),
    'evad_vitl': dict(vendor='EVAD-exp0066', commit='0efdb7e1156d4b0b419cd240555f8bbca45e4bf6',
        config='projects/evad/configs/ViT_L_16x4_KTP.yaml', config_sha256='f4be68745121e2b462bea93b2af7213f9f25faf3306ad8d693f082594993b081',
        checkpoint='evad_vitl_official.pth', checkpoint_sha256='141d40fe36d9ccbe7792d62503358dc8b1eeaab3bf9006c2d94290744fb8ac93',
        short_side=288, person_threshold_original=.7),
    'stmixer_vitb_vmaev2': dict(vendor='STMixer-exp0066', commit='2c3cd1de2623fc47ad93cfda3a8fcb9713736a55',
        config='config_files/VMAEv2-ViTB-16x4.yaml', config_sha256='f13943d670be91d59c8be14cfec0f32f84ccbf1fe131a01df41483beefe45ac7',
        checkpoint='stmixer_vitb_vmaev2_official.pth', checkpoint_sha256='e9d6c69c47d7e13efc84d7147b3527c5cff9e21b148e18062cf66fec2101f6a1',
        short_side=256, person_threshold_original=.6),
}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(4 * 1024 * 1024), b''): h.update(b)
    return h.hexdigest()


def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, sort_keys=True, indent=2, allow_nan=False); f.write('\n')


def source_files(vendor):
    return sorted(p for p in vendor.rglob('*') if p.is_file() and p.suffix in {'.py', '.yaml', '.yml', '.cpp', '.cu', '.h'}
                  and not set(p.relative_to(vendor).parts) & {'.git', 'build', '__pycache__'})


def create_specs():
    """CPU metadata only; no checkpoint deserialize, construction or forward."""
    destination = FOLDER / 'specs-v2'; destination.mkdir(exist_ok=False)
    for name, info in MODELS.items():
        vendor = ROOT / 'runtime/vendor' / info['vendor']
        files = source_files(vendor)
        if name.startswith('evad'):
            files += source_files(ROOT / 'runtime/vendor/detectron2-exp0066-joint')
        files += [Path(__file__).resolve(), ROOT / 'tests/test_exp0066_joint_models.py',
                  LABELS, FOLDER / 'ava_action_list_v2.2.pbtxt', FOLDER / 'requirements-freeze.txt']
        # Bind installed native entry points used by these models, without
        # rewriting or copying the existing environments.
        site = ENV / 'lib/python3.10/site-packages'
        for package in ('timm', 'fvcore', 'iopath', 'yacs', 'torchvision'):
            files += source_files(site / package)
        if name.startswith('evad'): files += source_files(site / 'detectron2')
        files += list((site / 'cv2').glob('*.so'))
        files += list((site / 'torchvision').glob('_C*.so'))
        if name.startswith('evad'): files += list((site / 'detectron2').glob('_C*.so'))
        checkpoint = ROOT / 'weights/model-comparison/exp0066/joint' / info['checkpoint']
        receipt = read(FOLDER / (name + '-download.json'))
        if receipt['status'] != 'downloaded' or receipt['sha256'] != info['checkpoint_sha256'] or checkpoint.stat().st_size != receipt['bytes']:
            raise ValueError('Exact official download receipt required')
        spec = dict(schema_version=1, model_id=name, interpreter=str(ENV / 'bin/python'),
            vendor_path=str(vendor), vendor_commit=info['commit'],
            config_path=str(vendor / info['config']), config_sha256=info['config_sha256'],
            checkpoint_path=str(checkpoint), checkpoint_sha256=info['checkpoint_sha256'],
            checkpoint_bytes=receipt['bytes'], checkpoint_official_url=receipt['requested_url'],
            vendor_sources={str(p): sha(p) for p in files}, action_label_map_path=str(LABELS),
            action_label_map_sha256=sha(LABELS), frames=16, source_reference_fps=30,
            sample_interval_seconds=4 / 30, nominal_anchor_index=8,
            temporal_offsets_seconds=[(i - 8) * 4 / 30 for i in range(16)],
            temporal_sampling_owner='root_canonical_runner_native_pts_not_native_index_stride4_on3FPS',
            preprocessing=dict(short_side=info['short_side'], max_long_side=1333,
                full_field_of_view=True, crop=False, rgb=True, mean=[.45] * 3, std=[.225] * 3,
                size_divisibility=32, pad_alignment='right_bottom', normalized_pad_value=0.),
            output_postfilter=dict(original_person_threshold=info['person_threshold_original'],
                effective_person_threshold=0., all_learned_queries_returned=100,
                action_topk_disabled=True, no_external_proposals=True),
            precision='float32', torch_version='2.5.1+cu124', torchvision_version='0.20.1+cu124',
            score_semantics=SEMANTICS, task_specific_climbing_head=False,
            resource_status='CPU_preparation_only_GPU_peak_and_runtime_not_measured',
            model_forwards_executed=0)
        save(destination / (name + '.json'), spec)
    return destination


def validate_spec(spec):
    name = spec['model_id']; info = MODELS[name]
    vendor = ROOT / 'runtime/vendor' / info['vendor']
    if (Path(spec['vendor_path']).resolve() != vendor or spec['vendor_commit'] != info['commit']
            or Path(spec['config_path']).resolve() != vendor / info['config']
            or spec['config_sha256'] != info['config_sha256']
            or spec['checkpoint_sha256'] != info['checkpoint_sha256']
            or Path(spec['checkpoint_path']).resolve() != ROOT / 'weights/model-comparison/exp0066/joint' / info['checkpoint']):
        raise ValueError('Exact pinned joint model/config/checkpoint required')
    head = subprocess.check_output(['git', '-C', str(vendor), 'rev-parse', 'HEAD'], text=True).strip()
    if head != info['commit']: raise ValueError('Vendor commit differs')
    if sha(spec['config_path']) != info['config_sha256'] or sha(spec['checkpoint_path']) != info['checkpoint_sha256']:
        raise ValueError('Pinned config/checkpoint bytes differ')
    for path, h in spec['vendor_sources'].items():
        if sha(path) != h: raise ValueError('Source/dependency changed: ' + path)
    if spec.get('action_label_map_sha256') != sha(LABELS): raise ValueError('AVA label map differs')
    if spec.get('frames') != 16 or spec.get('sample_interval_seconds') != 4 / 30:
        raise ValueError('Native physical-time interpretation changed')
    if spec.get('score_semantics') != SEMANTICS or spec.get('task_specific_climbing_head') is not False:
        raise ValueError('AVA outputs cannot become task-specific climbing scores')
    if spec.get('precision') not in {'float32', 'amp_float16'}: raise ValueError('Explicit precision required')


def resize_geometry(height, width, model_id, short_side=None):
    if min(height, width) <= 0: raise ValueError('Positive input dimensions required')
    side = MODELS[model_id]['short_side'] if short_side is None else short_side
    if type(side) is not int or not 16 <= side <= 1333: raise ValueError('Explicit valid short side required')
    scale = side / min(height, width)
    rh, rw = height * scale, width * scale
    if model_id.startswith('evad') and max(rh, rw) > 1333:
        factor = 1333 / max(rh, rw); rh *= factor; rw *= factor
    rh, rw = int(rh + .5), int(rw + .5)
    # The official STM transform ignores its max_size argument after resizing.
    # Reject extreme aspect ratios instead of silently changing that pipeline.
    if not model_id.startswith('evad') and max(rh, rw) > 1333:
        raise ValueError('STM native resize exceeds1333; explicit new spatial control needed')
    return dict(original_height=height, original_width=width, resized_height=rh, resized_width=rw,
        padded_height=math.ceil(rh / 32) * 32, padded_width=math.ceil(rw / 32) * 32,
        scale_x=rw / width, scale_y=rh / height, pad_left=0, pad_top=0,
        field_of_view='entire_input_frame', crop=False)


def preprocess_clip(frames_rgb, spec):
    import cv2
    import numpy as np
    import torch
    if (not isinstance(frames_rgb, np.ndarray) or frames_rgb.dtype != np.uint8
            or frames_rgb.ndim != 4 or frames_rgb.shape[0] != 16 or frames_rgb.shape[-1] != 3):
        raise ValueError('Exactly16 uint8 RGB frames in THWC required; root owns temporal sampling')
    short = spec.get('spatial_control_short_side')
    if short is not None and not spec.get('spatial_control_label'):
        raise ValueError('A spatial override requires an explicit control label')
    geometry = resize_geometry(*frames_rgb.shape[1:3], spec['model_id'], short)
    rh, rw = geometry['resized_height'], geometry['resized_width']
    resized = np.stack([cv2.resize(a, (rw, rh), interpolation=cv2.INTER_LINEAR) for a in frames_rgb])
    tensor = torch.from_numpy(resized).permute(3, 0, 1, 2).float() / 255.
    tensor = (tensor - .45) / .225
    geometry.update(channel_order='RGB', mean=[.45] * 3, std=[.225] * 3,
        padding='vendor_ImageList_right_bottom' if spec['model_id'].startswith('evad') else 'adapter_native_collator_right_bottom',
        effective_short_side=short or MODELS[spec['model_id']]['short_side'], spatial_control_label=spec.get('spatial_control_label'))
    return tensor, geometry


def boxes_to_original(boxes, geometry, normalized=False):
    """Independent inverse geometry, retaining degenerate queries with flags."""
    import numpy as np
    b = np.asarray(boxes, dtype=np.float64)
    if b.ndim != 2 or b.shape[1] != 4 or not np.isfinite(b).all(): raise ValueError('Finite Nx4 boxes required')
    if normalized:
        b = b * ([geometry['original_width'], geometry['original_height']] * 2)
    else:
        b = b / ([geometry['scale_x'], geometry['scale_y']] * 2)
    b[:, [0, 2]] = b[:, [0, 2]].clip(0, geometry['original_width'])
    b[:, [1, 3]] = b[:, [1, 3]].clip(0, geometry['original_height'])
    valid = ((b[:, 2] > b[:, 0]) & (b[:, 3] > b[:, 1])).tolist()
    return b.tolist(), valid


def validate_scores(person_scores, action_scores):
    import numpy as np
    p, a = np.asarray(person_scores), np.asarray(action_scores)
    if (p.shape != (100,) or a.shape != (100, 80) or not np.isfinite(p).all()
            or not np.isfinite(a).all() or (p < 0).any() or (p > 1).any()
            or (a < 0).any() or (a > 1).any()):
        raise ValueError('All100 learned-query person probabilities and80native AVA probabilities required')


def evad_native_boxes(person_boxes, action_boxes, geometry):
    """EVAD returns original-pixel person boxes and normalized AVA action boxes.

    Its postprocessor mutates the det_head tensor in place. Never inverse-resize
    that hooked tensor again; verify the two native return paths agree instead.
    """
    import numpy as np
    original = np.asarray(person_boxes, dtype=np.float64)
    normalized = np.asarray(action_boxes, dtype=np.float64)
    if (original.ndim != 2 or original.shape[1] != 4 or normalized.shape != original.shape
            or not np.isfinite(original).all() or not np.isfinite(normalized).all()):
        raise ValueError('Aligned finite EVAD native person/action boxes required')
    scale = [geometry['original_width'], geometry['original_height']] * 2
    if not np.allclose(original, normalized * scale, rtol=1e-5, atol=1e-3):
        raise ValueError('EVAD native person/action coordinate correspondence differs')
    if (original < 0).any() or (original > np.asarray(scale) + 1e-3).any():
        raise ValueError('EVAD native original boxes out of bounds')
    valid = ((original[:, 2] > original[:, 0]) & (original[:, 3] > original[:, 1])).tolist()
    return original.tolist(), valid


@dataclass
class JointModel:
    native: object
    spec: dict
    captured: dict
    strict_load: dict


def load_model(spec: dict, device: str):
    """Called by the authorized root runner; CPU strict preparation is separate."""
    validate_spec(spec)
    if Path(sys.prefix).resolve() != ENV: raise ValueError('Use the isolated joint interpreter')
    import torch
    if torch.__version__ != spec['torch_version']: raise ValueError('Pinned torch version required')
    torch.set_num_threads(4)
    vendor = Path(spec['vendor_path']); sys.path.insert(0, str(vendor))
    name = spec['model_id']; captured = {}
    if name.startswith('evad'):
        from projects.evad.models import EVAD, add_evad_config
        from slowfast.config.defaults import get_cfg
        cfg = get_cfg(); add_evad_config(cfg); cfg.merge_from_file(spec['config_path'])
        cfg.NUM_GPUS = 0; cfg.MODEL.DEVICE = 'cpu'; cfg.TRAIN.ENABLE = False; cfg.TEST.ENABLE = True
        cfg.MODEL.SparseRCNN.PERSON_THRESHOLD = 0.; cfg.MODEL.SparseRCNN.NUM_EVAL_ACT_CLASSES = 0
        native = EVAD(cfg)
        def collect(module, args, result): captured.update(result)
        native.det_head.register_forward_hook(collect)
        state_key = 'model_state'
    else:
        from alphaction.config import cfg as default
        from alphaction.modeling.detector import build_detection_model
        cfg = default.clone(); cfg.merge_from_file(spec['config_path'])
        cfg.MODEL.STM.PERSON_THRESHOLD = 0.
        native = build_detection_model(cfg)
        def collect(module, args, result):
            captured.update(person_logits=result[0], action_logits=result[1])
        native.stm_head.decoder_stages[-1].register_forward_hook(collect)
        state_key = 'model'
    checkpoint = torch.load(spec['checkpoint_path'], map_location='cpu', weights_only=True, mmap=True)
    state = checkpoint[state_key]
    prefix = bool(state) and all(k.startswith('module.') for k in state)
    if prefix: state = {k[7:]: v for k, v in state.items()}
    native.load_state_dict(state, strict=True, assign=True)
    native.requires_grad_(False); native.eval(); native.to(device)
    for module in native.modules():
        if 'device' in module.__dict__: module.device = torch.device(device)
    return JointModel(native, dict(spec), captured, dict(strict=True, missing_keys=[], unexpected_keys=[],
        uniform_module_prefix_removed=prefix, checkpoint_container=state_key, state_keys=len(state),
        parameter_count=sum(p.numel() for p in native.parameters()), model_forward_count=0))


def infer_clip(model, frames_rgb, spec: dict):
    """One real forward, only after the root's canonical queue authorization."""
    import torch
    import numpy as np
    if spec['model_id'] != model.spec['model_id'] or spec['checkpoint_sha256'] != model.spec['checkpoint_sha256']:
        raise ValueError('Loaded model/spec mismatch')
    device = next(model.native.parameters()).device
    if device.type != 'cuda': raise ValueError('No CPU forward: root canonical GPU runner required')
    torch.cuda.synchronize(device)
    started = time.perf_counter()
    tensor, geometry = preprocess_clip(frames_rgb, spec)
    tensor = tensor.to(device); model.captured.clear()
    if spec['model_id'].startswith('evad'):
        arguments = ([[tensor]], [dict(ori_height=geometry['original_height'], ori_width=geometry['original_width'], metadata=[[0, 0]])])
    else:
        padded = tensor.new_zeros((1, 3, 16, geometry['padded_height'], geometry['padded_width']))
        padded[0, :, :, :tensor.shape[-2], :tensor.shape[-1]] = tensor
        whwh = tensor.new_tensor([[geometry['resized_width'], geometry['resized_height']] * 2])
        arguments = (padded, None, whwh, None, None)
    torch.cuda.synchronize(device)
    inference_started = time.perf_counter()
    with torch.no_grad(), torch.autocast('cuda', enabled=spec['precision'] == 'amp_float16', dtype=torch.float16):
        native_output = model.native(*arguments)
    torch.cuda.synchronize(device)
    postprocess_started = time.perf_counter()
    if spec['model_id'].startswith('evad'):
        actions, action_boxes, metadata, persons = native_output
        scores = persons['scores'][0]
        if action_boxes.shape != (100, 5) or not bool((action_boxes[:, 0] == 0).all()):
            raise ValueError('EVAD single-input native query alignment required')
        boxes, valid = evad_native_boxes(persons['boxes'][0].detach().float().cpu().numpy(),
            action_boxes[:, 1:].detach().float().cpu().numpy(), geometry)
        action_logits = model.captured['pred_actions'][0]
        person_logits = model.captured['pred_logits'][0]
        probabilities = actions
    else:
        actions, normalized_boxes = native_output
        person_logits = model.captured['person_logits'][0]
        action_logits = model.captured['action_logits'][0]
        scores = person_logits.softmax(-1)[:, 0]
        probabilities = actions[0]
        boxes, valid = boxes_to_original(normalized_boxes[0].detach().float().cpu().numpy(), geometry, normalized=True)
    def values(t):
        a = t.detach().float().cpu().numpy()
        if not np.isfinite(a).all(): raise ValueError('Nonfinite native output')
        return a.tolist()
    person_scores = values(scores); action_scores = values(probabilities)
    validate_scores(person_scores, action_scores)
    if len(boxes) != 100 or len(person_scores) != 100 or any(len(a) != 80 for a in action_scores) or len(action_scores) != 100:
        raise ValueError('All100 independent learned queries and80AVA classes required')
    labels = read(spec['action_label_map_path'])['labels']
    result = dict(boxes=boxes, box_format='xyxy_original_input_pixels', valid_boxes=valid,
        person_scores=person_scores, action_scores=action_scores,
        action_label_names=[labels[str(i)] for i in range(1, 81)], action_label_ids=list(range(1, 81)),
        raw_person_logits=values(person_logits), raw_action_logits=values(action_logits),
        preprocessing_geometry=geometry, score_semantics=SEMANTICS,
        external_person_proposals=False, fcos_gating=False, action_person_scores_multiplied=False,
        task_specific_climbing_probability=None, person_recovery_accuracy=None,
        model_id=spec['model_id'], precision=spec['precision'],
        output_postfilter=spec['output_postfilter'], checkpoint_sha256=spec['checkpoint_sha256'])
    if spec['model_id'].startswith('evad'):
        result['box_coordinate_verification'] = 'native_original_person_equals_normalized_action_times_original_size'
        result['box_coordinate_source'] = 'vendor_native_person_detector_original_pixels_no_second_resize'
        result['native_action_boxes_normalized'] = values(action_boxes[:, 1:])
    model.captured.clear()
    torch.cuda.synchronize(device)
    finished = time.perf_counter()
    result['timing_seconds'] = dict(preprocess=inference_started-started,
        inference=postprocess_started-inference_started, postprocess=finished-postprocess_started, total=finished-started)
    result['timing_scope'] = 'Preprocess includes CPU resize/normalization andGPU copy/pad; inference includes complete vendorforward/nativeheadpost; postprocess includes inverse geometry/CPUscore transfer/JSONlists; decode measured byroot'
    return result


def cpu_validate(spec, output):
    if os.environ.get('CUDA_VISIBLE_DEVICES') != '': raise ValueError('Explicit CUDA-hidden CPU preparation required')
    import torch
    model = load_model(spec, 'cpu')
    if torch.cuda.is_initialized(): raise ValueError('CUDA unexpectedly initialized')
    report = dict(model_id=spec['model_id'], status='strict_cpu_construction_load_passed_no_forward',
        strict_load=model.strict_load, checkpoint_sha256=spec['checkpoint_sha256'],
        parameters_bytes=sum(p.numel() * p.element_size() for p in model.native.parameters()),
        model_forwards=0, gpu_model_loads=0, cuda_initialized=False,
        adapter_sha256=sha(__file__), spec_digest=hashlib.sha256(json.dumps(spec, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
        note='CPU parameter bytes are not measured peak GPU memory or execution feasibility')
    save(output, report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-specs', action='store_true')
    parser.add_argument('--cpu-validate', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.write_specs: print(create_specs())
    elif args.cpu_validate and args.output:
        print(json.dumps(cpu_validate(read(args.cpu_validate), args.output), indent=2))
    else: parser.error('Preparation only: choose --write-specs or --cpu-validate SPEC --output REPORT; no inference CLI')
