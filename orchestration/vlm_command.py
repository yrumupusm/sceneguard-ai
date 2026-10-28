"""The sole registered, offline BATCH-0001 command. No user-selected paths."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
ASSETS = Path('/home/jhc7484/dev/sceneguard-ai')
RUNTIME = Path('/home/jhc7484/dev/sceneguard-orca-lab/runtime/orca-lab/gpu-queue')
CLIPS = tuple(f'clip{i:02}' for i in range(1, 7))
SETTINGS = dict(seed=0, do_sample=False, max_new_tokens=384, repetition_penalty=1.0,
                dtype='bfloat16', attention='sdpa', device='cuda:0', batch_size=1)
MODELS = {
    'qwen': ('EXP-0008', '.venv-vlm/bin/python', 'Qwen3-VL-2B-Instruct'),
    'smol': ('EXP-0009', '.venv-vlm-batch01/bin/python', 'SmolVLM2-2.2B-Instruct'),
    'qwen_high_pixels': ('EXP-0010', '.venv-vlm/bin/python', 'Qwen3-VL-2B-Instruct'),
}


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def sources(adapter):
    paths = (
        ROOT / 'orchestration/queue.py', ROOT / 'orchestration/mock_job.py',
        ROOT / 'orchestration/vlm_command.py', ROOT / 'vlm_batch/__init__.py',
        ROOT / 'vlm_batch/run.py', ROOT / 'vlm_batch/common.py',
        ROOT / f'vlm_batch/{adapter}.py', ROOT / 'configs/vlm_batch01_prompt.txt')
    if adapter == 'qwen_high_pixels':
        paths += (ROOT / 'vlm_batch/qwen.py',)
    return {str(p.relative_to(ROOT)): file_hash(p) for p in paths}


def input_contract(adapter):
    if not isinstance(adapter, str) or adapter not in MODELS:
        raise ValueError('unregistered adapter')
    model = ASSETS / 'weights' / MODELS[adapter][2]
    files = sorted(p for p in model.rglob('*') if p.is_file()
                   and not any(x.startswith('.') for x in p.relative_to(model).parts))
    if not files or not any(p.suffix == '.safetensors' for p in files):
        raise ValueError('fixed local model is incomplete')
    return {'clips': {clip: {name: file_hash(ASSETS / 'outputs/vlm_exp0007' / clip / name)
                            for name in ('rgb.npy', 'input.json')} for clip in CLIPS},
            'model_files': {str(p.relative_to(model)): file_hash(p) for p in files}}


def validate(config, inputs, runtime):
    if not isinstance(config, dict) or set(config) != {'adapter', 'settings'}:
        raise ValueError('fixed adapter/settings config required')
    adapter = config['adapter']
    if (not isinstance(adapter, str) or adapter not in MODELS or
            json.dumps(config['settings'], sort_keys=True) != json.dumps(SETTINGS, sort_keys=True)):
        raise ValueError('unregistered model or generation settings')
    if Path(runtime).resolve() != RUNTIME:
        raise ValueError('actual VLM requires the existing canonical queue')
    interpreter = ASSETS / MODELS[adapter][1]
    if not interpreter.is_file():
        raise ValueError('fixed interpreter unavailable')
    if inputs != input_contract(adapter):
        raise ValueError('fixed asset hashes differ')
    return adapter


def command(config, inputs, runtime, attempt, lock_fd):
    adapter = validate(config, inputs, runtime)
    if not re.fullmatch('[0-9a-f]{32}', attempt):
        raise ValueError('invalid queue attempt')
    # run.py is a fixed script and explicitly adds only this trusted repository.
    return [str(ASSETS / MODELS[adapter][1]), '-I', str(ROOT / 'vlm_batch/run.py'),
            '--adapter', adapter, '--attempt', attempt, '--lock-fd', str(lock_fd)]


def output_path(adapter, attempt):
    return ASSETS / 'outputs/vlm_batch01' / MODELS[adapter][0] / attempt
