"""Fixed offline six-clip runner. Actual model loading requires a live queue lease."""
import argparse
import fcntl
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import time
import traceback

# Script invoked with -I: only this repository is added to the import path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from orchestration.mock_job import atomic_json
from orchestration.vlm_command import ASSETS, ROOT, RUNTIME, CLIPS, MODELS, SETTINGS, output_path
from vlm_batch.common import parse_pair


def verify_lease(adapter, attempt, lock_fd):
    """Fail before importing torch/model code unless the canonical supervisor owns us."""
    stat = os.fstat(lock_fd)
    actual = (RUNTIME / 'gpu.lock').stat()
    if (stat.st_dev, stat.st_ino) != (actual.st_dev, actual.st_ino):
        raise ValueError('canonical inherited lock required')
    with (RUNTIME / 'gpu.lock').open('a+') as other:
        try:
            fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            pass
        else:
            raise ValueError('queue reservation is not held')
    db = sqlite3.connect(f'file:{RUNTIME / "queue.sqlite3"}?mode=ro', uri=True)
    try:
        row = db.execute('SELECT a.status,a.supervisor_pid,j.command,j.config_json '
                         'FROM attempts a JOIN jobs j USING(job_id) WHERE attempt_id=?',
                         (attempt,)).fetchone()
    finally:
        db.close()
    if not row or row[:3] != ('running', os.getppid(), 'vlm-batch01'):
        raise ValueError('live native queue attempt required')
    if json.loads(row[3]) != {'adapter': adapter, 'settings': SETTINGS}:
        raise ValueError('adapter differs from registered attempt')


class MemoryMonitor:
    def __init__(self):
        self.stop_event = threading.Event()
        self.samples = []
        self.errors = []

    def poll(self):
        while not self.stop_event.is_set():
            try:
                raw = subprocess.check_output(['nvidia-smi', '-i', '0',
                    '--query-gpu=memory.used,memory.free', '--format=csv,noheader,nounits'],
                    text=True, timeout=3).strip()
                used, free = map(float, raw.split(','))
                self.samples.append(dict(monotonic=time.perf_counter(), used_mib=used, free_mib=free))
            except Exception as exc:
                self.errors.append(type(exc).__name__)
            self.stop_event.wait(0.5)

    def start(self):
        self.thread = threading.Thread(target=self.poll, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=4)


def save_frames(target, frames, source, clip_id):
    import numpy as np
    from PIL import Image, ImageDraw
    np.save(target / 'processor_resized_rgb.npy', frames)
    if frames.ndim != 4 or frames.shape[0] != 10 or frames.shape[-1] != 3:
        raise ValueError('adapter must return actual ten-frame RGB for review')
    h, w = frames.shape[1:3]
    sheet = Image.new('RGB', (2 * w, 5 * (h + 30)))
    for i, frame in enumerate(frames):
        x, y = i % 2 * w, i // 2 * (h + 30)
        sheet.paste(Image.fromarray(frame.astype('uint8')), (x, y + 30))
        ImageDraw.Draw(sheet).text((x + 4, y + 8),
                                  f"{clip_id} PTS {source['frames'][i]['pts']:.6f}", fill='white')
    sheet.save(target / 'actual_input_review.jpg', quality=95)


def run(adapter_name, attempt, lock_fd):
    verify_lease(adapter_name, attempt, lock_fd)
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
    import numpy as np
    import torch
    folder = output_path(adapter_name, attempt)
    folder.mkdir(parents=True, exist_ok=False)
    metadata = dict(adapter=adapter_name, attempt_id=attempt, settings=SETTINGS,
                    status='loading', original_decode_seconds=None,
                    python_version=sys.version,
                    packages={d.metadata['Name']: d.version for d in importlib.metadata.distributions()},
                    original_decode_reason='existing EXP7 RGB cache reused')
    monitor = MemoryMonitor()
    monitor.start()
    try:
        torch.manual_seed(0)
        if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
            raise ValueError('CUDA BF16 required')
        torch.cuda.reset_peak_memory_stats()
        started = time.perf_counter()
        adapter = importlib.import_module('vlm_batch.' + adapter_name).Adapter(
            ASSETS / 'weights' / MODELS[adapter_name][2], SETTINGS)
        torch.cuda.synchronize()
        metadata.update(load_seconds=time.perf_counter() - started,
                        model_parameter_devices=sorted({str(p.device) for p in adapter.model.parameters()}),
                        device=torch.cuda.get_device_name(0), torch_version=torch.__version__,
                        cuda_version=torch.version.cuda, numpy_version=np.__version__,
                        load_peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                        load_peak_reserved_bytes=torch.cuda.max_memory_reserved())
        import transformers
        metadata['transformers_version'] = transformers.__version__
        if metadata['model_parameter_devices'] != ['cuda:0']:
            raise ValueError('all model parameters must be on CUDA0')
        atomic_json(folder / 'loading.json', metadata)
        prompt = (ROOT / 'configs/vlm_batch01_prompt.txt').read_text(encoding='utf-8').strip()
        for clip in CLIPS:
            target = folder / clip
            target.mkdir()
            record = dict(clip_id=clip, status='preparing')
            try:
                torch.cuda.reset_peak_memory_stats()
                t = time.perf_counter()
                rgb = np.load(ASSETS / 'outputs/vlm_exp0007' / clip / 'rgb.npy', allow_pickle=False)
                record['npy_load_seconds'] = time.perf_counter() - t
                source = json.loads((ASSETS / 'outputs/vlm_exp0007' / clip / 'input.json').read_text())
                if rgb.shape != (10, 1080, 1920, 3) or rgb.dtype != np.uint8:
                    raise ValueError('fixed ten full-screen uint8 frames required')
                t = time.perf_counter()
                inputs, info, actual = adapter.prepare(rgb, source, prompt, clip)
                inputs = inputs.to('cuda:0')
                torch.cuda.synchronize()
                record.update(info)
                record.update(prepare_seconds=time.perf_counter() - t,
                              source_pts=[r['pts'] for r in source['frames']],
                              native_pts=[r['native_pts'] for r in source['frames']],
                              time_base=source['frames'][0]['time_base'],
                              relative_indices=source['relative_indices'], source_fps=source['fps'])
                (target / 'expanded_prompt.txt').write_text(
                    adapter.processor.tokenizer.decode(inputs['input_ids'][0], skip_special_tokens=False),
                    encoding='utf-8')
                save_frames(target, actual, source, clip)
                started = time.perf_counter()
                with torch.inference_mode():
                    result = adapter.model.generate(**inputs, do_sample=False, max_new_tokens=384,
                                                    repetition_penalty=1.0)
                torch.cuda.synchronize()
                record['generation_seconds'] = time.perf_counter() - started
                output = result[:, inputs['input_ids'].shape[1]:]
                np.save(target / 'generated_token_ids.npy', output.detach().cpu().numpy())
                record.update(output_tokens=int(output.shape[1]),
                              hit_token_limit=bool(output.shape[1] >= 384),
                              peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                              peak_reserved_bytes=torch.cuda.max_memory_reserved())
                raw = adapter.processor.batch_decode(output, skip_special_tokens=True,
                                                     clean_up_tokenization_spaces=False)[0]
                (target / 'raw_response.txt').write_text(raw, encoding='utf-8')
                record.update(parse_pair(raw))
                record['status'] = 'generated'
                del inputs, result, output, rgb, actual
                print(clip, 'generated', record['generation_seconds'], flush=True)
            except Exception as exc:
                record.update(status='failed', error=repr(exc), traceback=traceback.format_exc(),
                              oom=isinstance(exc, torch.cuda.OutOfMemoryError))
                atomic_json(target / 'result.json', record)
                raise
            atomic_json(target / 'result.json', record)
        metadata['status'] = 'succeeded'
    except Exception as exc:
        metadata.update(status='failed', error=repr(exc), traceback=traceback.format_exc())
        raise
    finally:
        monitor.stop()
        atomic_json(folder / 'gpu_memory_samples.json', {'samples': monitor.samples, 'errors': monitor.errors})
        atomic_json(folder / 'summary.json', metadata)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adapter', choices=tuple(MODELS), required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--lock-fd', required=True, type=int)
    args = parser.parse_args()
    run(args.adapter, args.attempt, args.lock_fd)
