"""Fixed offline MVP-0001 registration, reusing the existing canonical queue."""
import json
from pathlib import Path
import re

from orchestration.vlm_command import ASSETS, RUNTIME, SETTINGS, file_hash

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ASSETS / 'weights/Qwen3-VL-2B-Instruct'
INTERPRETER = ASSETS / '.venv-vlm/bin/python'
PINNED_MODEL_SHA256 = '7de1838c87a5349b016c26a1c3f7d2bc400a3d485f95ef39a7059ffd734977a0'
CONFIG_NAMES = ('mvp0001_sources.json', 'mvp0001_cameras.json', 'mvp0001_settings.json')
DEVELOPMENT = (('clip01', 'E01_007', 'C3'), ('clip02', 'E01_030', 'C6'),
               ('clip03', 'E01_006', 'C3'), ('clip04', 'E01_007', 'C3'),
               ('clip05', 'E01_001', 'C1'), ('clip06', 'E01_031', 'C7'))
CONTINUOUS = (('E01_007', 'C3'), ('E01_030', 'C6'), ('E01_013', 'C4'))
EXPECTED_SETTINGS = dict(schema_version=1, generation=SETTINGS,
    processor_size={'shortest_edge': 16384, 'longest_edge': 3584000},
    window_seconds=5.0, stride_seconds=2.5, sampling_fps=2.0, minimum_real_frames=2,
    merge_rule='same source/camera/action and overlapping source intervals; retain all constituent windows',
    merge_gap_seconds=0.0, evidence_pre_seconds=2.0, evidence_post_seconds=2.0,
    dev_timeout_seconds=900, full_timeout_seconds=1800, minimum_gpu_free_mib=6144,
    execution_error_retries_max=1)


def same(a, b):
    return json.dumps(a, sort_keys=True, allow_nan=False) == json.dumps(b, sort_keys=True, allow_nan=False)


def load_configs():
    source, camera, settings = [json.loads((ROOT / 'configs' / name).read_text()) for name in CONFIG_NAMES]
    if not same(settings, EXPECTED_SETTINGS):
        raise ValueError('MVP pipeline settings differ from frozen baseline')
    if [(r['clip_id'], r['source_id'], r['camera_id']) for r in source['development_clips']] != list(DEVELOPMENT):
        raise ValueError('fixed six development clips required')
    if [(r['source_id'], r['camera_id']) for r in source['continuous_sources']] != list(CONTINUOUS):
        raise ValueError('fixed full source list 007/030/013 required')
    if any(r['cache_dir'] != f"outputs/vlm_exp0007/{r['clip_id']}" for r in source['development_clips']):
        raise ValueError('fixed existing RGB cache paths required')
    if any(r['relative_video_path'] != f"data/TS_침입/{r['source_id']}.mp4" for r in source['continuous_sources']):
        raise ValueError('fixed original video paths required')
    for key in ('window_seconds', 'stride_seconds', 'sampling_fps'):
        if source[key] != settings[key]:
            raise ValueError('source window settings differ')
    rois = {'C3': [0.6, 0, 0.9, 0.6], 'C6': [0.28, 0.2, 0.75, 0.8],
            'C7': [0.43, 0, 0.78, 1], 'C1': [0, 0, 1, 1], 'C4': [0, 0, 1, 1]}
    for name, roi in rois.items():
        if camera['cameras'][name]['roi'] != roi:
            raise ValueError('camera ROI differs from original static background/fallback')
    return source, camera, settings


def sources():
    names = ['orchestration/queue.py', 'orchestration/mock_job.py', 'orchestration/mvp_command.py',
             'orchestration/vlm_command.py', 'vlm_batch/common.py', 'vlm_batch/qwen.py',
             'vlm_batch/run.py', 'configs/vlm_batch01_prompt.txt']
    names += ['mvp/' + name + '.py' for name in
              ('method', 'compare', 'runner', 'windows', 'events', 'evidence', 'pipeline', 'cli')]
    names += ['configs/' + name for name in CONFIG_NAMES]
    return {name: file_hash(ROOT / name) for name in names}


def input_contract(phase):
    if phase not in ('dev', 'full'):
        raise ValueError('fixed dev/full phase required')
    source, _, _ = load_configs()
    files = sorted(p for p in MODEL_DIR.rglob('*') if p.is_file()
                   and not any(s.startswith('.') for s in p.relative_to(MODEL_DIR).parts))
    if not files or not (MODEL_DIR / 'model.safetensors').is_file():
        raise ValueError('existing pinned Qwen model incomplete')
    model = {str(p.relative_to(MODEL_DIR)): file_hash(p) for p in files}
    if model['model.safetensors'] != PINNED_MODEL_SHA256:
        raise ValueError('local Qwen weights differ from pinned revision')
    inputs = {'model_files': model,
              'configs': {name: file_hash(ROOT / 'configs' / name) for name in CONFIG_NAMES}}
    if phase == 'dev':
        inputs['clips'] = {r['clip_id']: {name: file_hash(ASSETS / r['cache_dir'] / name)
                                        for name in ('rgb.npy', 'input.json')}
                           for r in source['development_clips']}
        # Pin successful historical baseline receipts and all reusable output bytes.
        from mvp.compare import baseline_paths
        inputs['baseline'] = {str(p.relative_to(ASSETS)): file_hash(p) for p in baseline_paths()}
    else:
        inputs['videos'] = {r['source_id']: file_hash(ASSETS / r['relative_video_path'])
                            for r in source['continuous_sources']}
        if any(inputs['videos'][r['source_id']] != r['sha256'] for r in source['continuous_sources']):
            raise ValueError('original full video differs from frozen source hash')
    return inputs


def validate(config, inputs, runtime):
    if not isinstance(config, dict) or set(config) != {'phase', 'view', 'settings'}:
        raise ValueError('fixed phase/view/settings config required')
    if config['phase'] not in ('dev', 'full') or config['view'] not in ('fixed_roi', 'full_frame'):
        raise ValueError('unregistered phase/view')
    if config['phase'] == 'dev' and config['view'] != 'fixed_roi':
        raise ValueError('development B outputs must be reused, not rerun')
    if not same(config['settings'], SETTINGS):
        raise ValueError('baseline generation settings required')
    if Path(runtime).resolve() != RUNTIME:
        raise ValueError('existing canonical GPU queue required')
    if not INTERPRETER.is_file():
        raise ValueError('existing offline VLM interpreter unavailable')
    if inputs != input_contract(config['phase']):
        raise ValueError('registered model/input/config hashes differ')
    return config['phase'], config['view']


def command(config, inputs, runtime, attempt, lock_fd):
    phase, view = validate(config, inputs, runtime)
    if not isinstance(attempt, str) or not re.fullmatch('[0-9a-f]{32}', attempt):
        raise ValueError('invalid queue attempt')
    return [str(INTERPRETER), '-I', str(ROOT / 'mvp/runner.py'), '--phase', phase,
            '--view', view, '--attempt', attempt, '--lock-fd', str(lock_fd)]


def output_path(phase, attempt):
    if phase not in ('dev', 'full') or not re.fullmatch('[0-9a-f]{32}', attempt):
        raise ValueError('invalid phase or queue attempt')
    return ASSETS / 'outputs/mvp0001' / ('EXP-0011' if phase == 'dev' else 'EXP-0012') / attempt
