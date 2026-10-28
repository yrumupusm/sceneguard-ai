"""Local Qwen fixed-camera input adapter; CPU preparation never loads weights."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time

from orchestration.vlm_command import SETTINGS
from vlm_batch.common import parse_pair

ROOT = Path(__file__).resolve().parents[1]
PROCESSOR_SIZE = {'shortest_edge': 16384, 'longest_edge': 3584000}


def analyzer_prompt(window_id, phase='full'):
    """Text accepts only an anonymous ID and registered phase, never metadata."""
    from orchestration.mvp_command import PHASES, REGRESSION_PROMPT
    if phase not in PHASES:
        raise ValueError('unregistered prompt phase')
    from mvp.independent import PHASES as INDEPENDENT_PHASES, prompt
    if phase in INDEPENDENT_PHASES:
        return prompt(window_id, phase)
    pattern = r'w\d{6,12}' if phase == 'prompt-regression' else r'(?:w\d{6,12}|clip0[1-6])'
    if not isinstance(window_id, str) or not re.fullmatch(pattern, window_id):
        raise ValueError('anonymous window ID required')
    name = REGRESSION_PROMPT if phase == 'prompt-regression' else 'vlm_batch01_prompt.txt'
    return f'Clip ID: {window_id}\n' + (ROOT / 'configs' / name).read_text(encoding='utf-8').strip()


def crop_frames(rgb, roi):
    """Crop one fixed normalized rectangle, using floor/ceil outward bounds."""
    import numpy as np
    if not isinstance(rgb, np.ndarray) or rgb.dtype != np.uint8 or rgb.ndim != 4 or rgb.shape[-1] != 3:
        raise ValueError('original uint8 RGB [N,H,W,3] required')
    if min(rgb.shape[1:3]) < 32:
        raise ValueError('original frames of at least 32 pixels required')
    if not isinstance(roi, (list, tuple)) or len(roi) != 4 or any(
            type(x) not in (int, float) or not math.isfinite(x) for x in roi):
        raise ValueError('finite normalized fixed rectangle required')
    x0, y0, x1, y1 = roi
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise ValueError('rectangle must lie within original frame')
    h, w = rgb.shape[1:3]
    bounds = [math.floor(x0*w), math.floor(y0*h), math.ceil(x1*w), math.ceil(y1*h)]
    a, b, c, d = bounds
    if min(c-a, d-b) < 32:
        raise ValueError('fixed rectangle is too small for official video processor')
    return np.ascontiguousarray(rgb[:, b:d, a:c]), bounds


def validate_source(rgb, source, window_id):
    from fractions import Fraction
    if not isinstance(window_id, str) or not re.fullmatch(r'(?:w\d{6,12}|clip0[1-6])', window_id):
        raise ValueError('anonymous full-window or original development clip ID required')
    required = {'fps', 'pts_seconds', 'native_pts', 'time_base', 'relative_indices',
                'source_size', 'window_start', 'window_end', 'last_decoded_pts'}
    if not isinstance(source, dict) or not required <= source.keys():
        raise ValueError('source timing contract is incomplete')
    n = len(rgb)
    if any(len(source[k]) != n for k in ('pts_seconds', 'native_pts', 'relative_indices')):
        raise ValueError('one timing record per observed frame required')
    if source['source_size'] != [rgb.shape[2], rgb.shape[1]]:
        raise ValueError('source_size must describe original RGB dimensions')
    values = [source[k] for k in ('fps', 'window_start', 'window_end', 'last_decoded_pts')]
    values += list(source['pts_seconds'])
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in values):
        raise ValueError('finite numeric source timing required')
    start, end = source['window_start'], source['window_end']
    pts = source['pts_seconds']
    if source['fps'] <= 0 or start >= end or any(not start <= p < end for p in pts):
        raise ValueError('observations must lie inside their half-open window')
    if any(a >= b for a, b in zip(pts, pts[1:])) or (pts and pts[-1] > source['last_decoded_pts']):
        raise ValueError('ordered PTS and observed last decoded PTS required')
    indices = source['relative_indices']
    if any(type(i) is not int or i < 0 for i in indices) or any(a >= b for a, b in zip(indices, indices[1:])):
        raise ValueError('ordered original relative frame indices required')
    bases = source['time_base'] if isinstance(source['time_base'], list) else [source['time_base']]*n
    if len(bases) != n or any(type(p) is not int for p in source['native_pts']):
        raise ValueError('one native integer PTS and rational time base per observation required')
    try:
        if any(abs(float(Fraction(b)*p)-s) > 1e-6 for b, p, s in zip(bases, source['native_pts'], pts)):
            raise ValueError('native PTS/time base differs from observed seconds')
    except (TypeError, ZeroDivisionError) as exc:
        raise ValueError('valid native time bases required') from exc
    if 'decoded_indices' in source and (len(source['decoded_indices']) != n or
            (n and [i-source['decoded_indices'][0] for i in source['decoded_indices']] != indices)):
        raise ValueError('relative indices must be actual decoded ordinals')


class QwenAnalyzer:
    """Weights can only be constructed under the inherited canonical MVP lease."""
    def __init__(self, model_dir, settings):
        from mvp.runner import verify_environment_lease
        job = verify_environment_lease()
        self.phase = json.loads(job['config_json'])['phase']
        from orchestration.mvp_command import MODEL_DIR
        if Path(model_dir).resolve() != MODEL_DIR.resolve() or json.dumps(settings, sort_keys=True) != json.dumps(SETTINGS, sort_keys=True):
            raise ValueError('fixed local Qwen model and baseline generation settings required')
        os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
        import torch
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
        torch.manual_seed(0)
        self.settings = dict(settings)
        self.processor = AutoProcessor.from_pretrained(model_dir, local_files_only=True)
        self.model = Qwen3VLForConditionalGeneration.from_pretrained(
            model_dir, local_files_only=True, torch_dtype=torch.bfloat16,
            attn_implementation=settings['attention']).to(settings['device']).eval()

    def prepare(self, rgb, source, window_id, roi):
        """CPU official processor path, separately usable without a model instance."""
        from transformers.video_utils import VideoMetadata
        cropped, bounds = crop_frames(rgb, roi)
        validate_source(rgb, source, window_id)
        if len(rgb) < 2:
            raise ValueError('insufficient_frames: official resize requires at least two observations')
        prompt = analyzer_prompt(window_id, getattr(self, 'phase', 'full'))
        messages = [{'role': 'user', 'content': [{'type': 'video'},
                    {'type': 'text', 'text': prompt}]}]
        processor = self.processor
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        duration = source['window_end'] - source['window_start']
        timestamp_coordinates = [(p-source['window_start'])*source['fps'] for p in source['pts_seconds']]
        metadata = VideoMetadata(total_num_frames=round(duration * source['fps']), fps=source['fps'],
                                 width=cropped.shape[2], height=cropped.shape[1], duration=duration,
                                 frames_indices=timestamp_coordinates.copy(), video_backend='pyav_preselected')
        captured = []
        original = processor.video_processor.resize

        def resize(images, **kwargs):
            result = original(images, **kwargs)
            captured.append(result.detach().cpu().clone())
            return result

        processor.video_processor.resize = resize
        try:
            inputs = processor(text=[text], videos=[cropped], video_metadata=[metadata],
                               do_sample_frames=False, size=PROCESSOR_SIZE.copy(), return_tensors='pt')
        finally:
            processor.video_processor.resize = original
        grid = inputs['video_grid_thw'].tolist()
        n = len(rgb)
        padded = grid[0][0] * processor.video_processor.temporal_patch_size
        if len(captured) != 1 or captured[0].shape[0] != n or padded != n + n % 2:
            raise ValueError('official processor changed observed frame count unexpectedly')
        frames = captured[0].permute(0, 2, 3, 1).numpy().astype('uint8')
        video_token_id = processor.tokenizer.convert_tokens_to_ids(processor.video_token)
        info = dict(observed_frames=n, processor_frames=padded,
                    source_pts=list(source['pts_seconds']), native_pts=list(source['native_pts']),
                    time_base=source['time_base'], relative_indices=list(source['relative_indices']),
                    source_fps=source['fps'], source_size=source['source_size'],
                    window_start=source['window_start'], window_end=source['window_end'],
                    last_decoded_pts=source['last_decoded_pts'], last_observed_pts=source['pts_seconds'][-1],
                    roi=list(roi), crop_bounds_xyxy=bounds, cropped_shape=list(cropped.shape),
                    crop_sha256=hashlib.sha256(cropped.tobytes()).hexdigest(),
                    video_grid_thw=grid, resized_shape=list(captured[0].shape), resize_calls=len(captured),
                    extra_sampling=False, temporal_padding_frames=padded-n,
                    temporal_padding_source_pts=source['pts_seconds'][-1] if padded > n else None,
                    temporal_padding_is_observation=False,
                    processor_timestamp_coordinates=timestamp_coordinates,
                    processor_timestamp_basis='(actual PTS-window_start)*fps time coordinates, not decoded indices',
                    processor_timestamp_quantization='official pair averaging then captions rounded to 0.1 seconds',
                    visual_tokens=int((inputs.input_ids == video_token_id).sum()),
                    input_tokens=int(inputs.input_ids.shape[1]), processor_size=PROCESSOR_SIZE.copy(),
                    processor_do_pad=getattr(processor.video_processor, 'do_pad', None),
                    frame_order='original observed frame order')
        return inputs, info, frames

    def analyze(self, rgb, source, window_id, roi):
        self.last_generated_token_ids = []
        self.last_processor_frames = None
        self.last_expanded_prompt = None
        self.last_input_metadata = None
        crop_frames(rgb, roi)
        validate_source(rgb, source, window_id)
        if len(rgb) < 2:
            return dict(raw_response='', parsed=None, parse={'status': 'insufficient_frames',
                        'reason': 'fewer than two real observations; no generation'},
                        timing={'prepare_seconds': None, 'generation_seconds': None},
                        input_metadata={'observed_frames': len(rgb), 'last_observed_pts': source['pts_seconds'][-1] if len(rgb) else None,
                                        'temporal_padding_frames': 0}, output_tokens=0,
                        newly_generated_tokens=0, gpu_memory=None)
        import torch
        torch.cuda.reset_peak_memory_stats()
        t = time.perf_counter()
        inputs, info, self.last_processor_frames = self.prepare(rgb, source, window_id, roi)
        self.last_input_metadata = info
        inputs = inputs.to(self.settings['device'])
        torch.cuda.synchronize()
        prepare_seconds = time.perf_counter() - t
        self.last_expanded_prompt = self.processor.tokenizer.decode(inputs['input_ids'][0], skip_special_tokens=False)
        t = time.perf_counter()
        with torch.inference_mode():
            result = self.model.generate(**inputs, do_sample=False, max_new_tokens=384, repetition_penalty=1.0)
        torch.cuda.synchronize()
        generation_seconds = time.perf_counter() - t
        output = result[:, inputs['input_ids'].shape[1]:]
        # Retain original token IDs before text decode, including decode failures.
        self.last_generated_token_ids = output.detach().cpu().tolist()
        # A queue runner may attach its fixed local artifact root. Save IDs
        # before decode so a tokenizer failure cannot erase generated evidence.
        if getattr(self, 'artifact_root', None) is not None:
            import numpy as np
            target = Path(self.artifact_root) / window_id
            target.mkdir(parents=True, exist_ok=True)
            np.save(target / 'generated_token_ids.npy', output.detach().cpu().numpy())
        raw = self.processor.batch_decode(output, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]
        parsed = parse_pair(raw)
        return dict(raw_response=raw, parsed=parsed['postprocessed_parsed'], parse=parsed,
                    timing={'prepare_seconds': prepare_seconds, 'generation_seconds': generation_seconds},
                    input_metadata=info, output_tokens=int(output.shape[1]),
                    newly_generated_tokens=int(output.shape[1]), reused=False,
                    hit_token_limit=bool(output.shape[1] >= 384),
                    generated_token_ids=self.last_generated_token_ids,
                    gpu_memory={'peak_allocated_bytes': torch.cuda.max_memory_allocated(),
                                'peak_reserved_bytes': torch.cuda.max_memory_reserved()})
