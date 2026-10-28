"""One offline Qwen3-VL model, independent anonymous full-screen video conversations."""
import os
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import threading
import time
import traceback
import numpy as np
import torch
from PIL import Image, ImageDraw
from transformers import Qwen3VLForConditionalGeneration, AutoProcessor
from transformers.video_utils import VideoMetadata
ROOT = Path('outputs/vlm_exp0007')
MODEL = Path('weights/Qwen3-VL-2B-Instruct')

class MemoryMonitor:

    def __init__(self):
        self.stop_event = threading.Event()
        self.samples = []

    def poll(self):
        while not self.stop_event.is_set():
            try:
                value = subprocess.check_output(['nvidia-smi', '--query-gpu=memory.used,memory.free', '--format=csv,noheader,nounits'], text=True).strip()
                self.samples.append(dict(monotonic=time.perf_counter(), used_free_mib=value))
            except Exception:
                pass
            self.stop_event.wait(0.5)

    def start(self):
        self.thread = threading.Thread(target=self.poll, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.thread.join()

def parse_response(raw):
    obj = json.loads(raw)
    expected = {'관찰 행동', '화면에서 확인되는 근거', '넘기 완료', '불확실한 부분'}
    if set(obj) != expected or not isinstance(obj['관찰 행동'], list) or (not all((isinstance(a, str) for a in obj['관찰 행동']))):
        raise ValueError('Invalid response keys/actions')
    if not all((isinstance(obj[k], str) for k in expected - {'관찰 행동'})):
        raise ValueError('Expected strings')
    if obj['넘기 완료'] not in ['관찰됨', '확인되지 않음', '판단 불가']:
        raise ValueError('Invalid completion')
    return obj

def run(name):
    folder = ROOT / name
    folder.mkdir(exist_ok=False)
    frozen = json.loads((ROOT / 'preregistered.json').read_text(encoding='utf-8'))
    for (path, h) in frozen['hashes'].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == h
    prompt = Path('configs/vlm_exp0007_prompt.txt').read_text(encoding='utf-8').strip()
    torch.manual_seed(0)
    assert torch.cuda.is_available()
    monitor = MemoryMonitor()
    monitor.start()
    metadata = dict(device=torch.cuda.get_device_name(0), bf16_supported=torch.cuda.is_bf16_supported(), cuda_version=torch.version.cuda, precision='bfloat16', quantization=False, attention='sdpa', generation=dict(do_sample=False, max_new_tokens=384, repetition_penalty=1.0), code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    try:
        t = time.perf_counter()
        processor = AutoProcessor.from_pretrained(MODEL, local_files_only=True)
        model = Qwen3VLForConditionalGeneration.from_pretrained(MODEL, local_files_only=True, torch_dtype=torch.bfloat16, attn_implementation='sdpa').to('cuda:0').eval()
        torch.cuda.synchronize()
        metadata['load_seconds'] = time.perf_counter() - t
        metadata['model_parameter_devices'] = sorted({str(p.device) for p in model.parameters()})
        metadata['loaded_allocated_bytes'] = torch.cuda.memory_allocated()
        metadata['loaded_reserved_bytes'] = torch.cuda.memory_reserved()
        (folder / 'loading.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
        print('loaded', metadata, flush=True)
        original_resize = processor.video_processor.resize
        captured = []

        def capture_resize(images, **kwargs):
            result = original_resize(images, **kwargs)
            captured.append(result.detach().cpu().clone())
            return result
        processor.video_processor.resize = capture_resize
        for clip_id in [f'clip{i:02}' for i in range(1, 7)]:
            target = folder / clip_id
            target.mkdir()
            record = dict(clip_id=clip_id)
            try:
                captured.clear()
                torch.cuda.reset_peak_memory_stats()
                t = time.perf_counter()
                rgb = np.load(ROOT / clip_id / 'rgb.npy')
                source = json.loads((ROOT / clip_id / 'input.json').read_text(encoding='utf-8'))
                assert rgb.shape == (10, 1080, 1920, 3)
                messages = [{'role': 'user', 'content': [{'type': 'video'}, {'type': 'text', 'text': f'클립 ID: {clip_id}\n' + prompt}]}]
                text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                vm = VideoMetadata(total_num_frames=round(5 * source['fps']), fps=source['fps'], width=1920, height=1080, duration=5.0, frames_indices=source['relative_indices'], video_backend='pyav_preselected')
                inputs = processor(text=[text], videos=[rgb], video_metadata=[vm], do_sample_frames=False, size={'shortest_edge': 16384, 'longest_edge': 3584000}, return_tensors='pt')
                grid = inputs['video_grid_thw'].tolist()
                assert grid[0][0] * 2 == 10 and len(captured) == 1 and (captured[0].shape[0] == 10)
                record.update(source_pts=[r['pts'] for r in source['frames']], native_pts=[r['native_pts'] for r in source['frames']], time_base=source['frames'][0]['time_base'], fps=source['fps'], relative_indices=source['relative_indices'], video_grid_thw=grid, resized_shape=list(captured[0].shape), resize_calls=len(captured), extra_sampling=False, temporal_padding_frames=0, visual_tokens=int((inputs.input_ids == model.config.video_token_id).sum()), input_tokens=inputs.input_ids.shape[1])
                (target / 'expanded_prompt.txt').write_text(processor.tokenizer.decode(inputs.input_ids[0], skip_special_tokens=False), encoding='utf-8')
                inputs = inputs.to('cuda:0')
                torch.cuda.synchronize()
                record['preprocess_seconds'] = time.perf_counter() - t
                started = time.perf_counter()
                with torch.inference_mode():
                    result = model.generate(**inputs, do_sample=False, max_new_tokens=384, repetition_penalty=1.0)
                torch.cuda.synchronize()
                record['generation_seconds'] = time.perf_counter() - started
                output = result[:, inputs.input_ids.shape[1]:]
                raw = processor.batch_decode(output, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]
                np.save(target / 'generated_token_ids.npy', output.detach().cpu().numpy())
                (target / 'raw_response.txt').write_text(raw, encoding='utf-8')
                record.update(output_tokens=int(output.shape[1]), hit_token_limit=output.shape[1] >= 384, peak_allocated_bytes=torch.cuda.max_memory_allocated(), peak_reserved_bytes=torch.cuda.max_memory_reserved(), status='generated')
                try:
                    record['parsed'] = parse_response(raw)
                    record['parse_error'] = None
                except Exception as exc:
                    record['parsed'] = None
                    record['parse_error'] = str(exc)
                frames = captured[0].permute(0, 2, 3, 1).numpy()
                (h, w) = frames.shape[1:3]
                np.save(target / 'processor_resized_rgb.npy', frames)
                sheet = Image.new('RGB', (2 * w, 5 * (h + 30)))
                for (i, a) in enumerate(frames):
                    x = i % 2 * w
                    y = i // 2 * (h + 30)
                    sheet.paste(Image.fromarray(a.astype('uint8')), (x, y + 30))
                    ImageDraw.Draw(sheet).text((x + 4, y + 8), f"{clip_id} PTS {record['source_pts'][i]:.6f}", fill='white')
                sheet.save(target / 'actual_input_review.jpg', quality=95)
                del inputs, result, output
                print(clip_id, record['status'], record['generation_seconds'], record.get('parsed'), flush=True)
            except Exception as exc:
                record.update(status='failed', error=repr(exc), traceback=traceback.format_exc(), oom=isinstance(exc, torch.cuda.OutOfMemoryError))
                (target / 'result.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
                raise
            (target / 'result.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    finally:
        monitor.stop()
        (folder / 'gpu_memory_samples.json').write_text(json.dumps(monitor.samples, indent=2), encoding='utf-8')
if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--run', default='run01')
    run(p.parse_args().run)
