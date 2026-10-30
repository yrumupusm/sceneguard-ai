"""Fixed offline MVP-0001 registration, reusing the existing canonical queue."""
import json
from pathlib import Path
import re

from orchestration.vlm_command import ASSETS, RUNTIME, SETTINGS, file_hash
from mvp.independent import PHASES as INDEPENDENT_PHASES

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ASSETS / 'weights/Qwen3-VL-2B-Instruct'
INTERPRETER = ASSETS / '.venv-vlm/bin/python'
PINNED_MODEL_SHA256 = '7de1838c87a5349b016c26a1c3f7d2bc400a3d485f95ef39a7059ffd734977a0'
CONFIG_NAMES = ('mvp0001_sources.json', 'mvp0001_cameras.json', 'mvp0001_settings.json')
PHASES = ('dev', 'full', 'prompt-regression', 'candidate-vlm', 'appearance-compare', 'appearance-8b') + INDEPENDENT_PHASES
REGRESSION_RUN = 'run_3d23462a014a'
REGRESSION_MANIFEST = 'mvp_exp0016_manifest.json'
REGRESSION_PROMPT = 'mvp_exp0016_prompt.txt'
REGRESSION_WINDOWS = (('E01_007', 'C3', 'w000001', 0.0, 5.0),
    ('E01_007', 'C3', 'w000020', 47.5, 52.5),
    ('E01_007', 'C3', 'w000022', 52.5, 57.5),
    ('E01_007', 'C3', 'w000026', 62.5, 67.5),
    ('E01_030', 'C6', 'w000021', 50.0, 55.0),
    ('E01_030', 'C6', 'w000063', 155.0, 160.0))
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


def load_regression_manifest():
    manifest = json.loads((ROOT / 'configs' / REGRESSION_MANIFEST).read_text())
    source, cameras, _ = load_configs()
    expected = dict(schema_version=1, experiment='EXP-0016', phase='prompt-regression',
        run_id=REGRESSION_RUN, views=['full_frame', 'fixed_roi'], prompt='configs/' + REGRESSION_PROMPT,
        window_seconds=5.0, stride_seconds=2.5, sampling_fps=2.0,
        windows=[dict(source_id=s, camera_id=c, window_id=w, start=a, end=b)
                 for s, c, w, a, b in REGRESSION_WINDOWS],
        sources={r['source_id']: r['sha256'] for r in source['continuous_sources']
                 if r['source_id'] in ('E01_007', 'E01_030')},
        rois={c: cameras['cameras'][c]['roi'] for c in ('C3', 'C6')})
    if not same(manifest, expected):
        raise ValueError('EXP-0016 frozen six-window manifest differs')
    return manifest


def validate_run(phase, run_id):
    if phase == 'appearance-8b':
        from mvp.exp0038 import validate_authorization
        if validate_authorization()['run_id'] != run_id:
            raise ValueError('EXP-0038 requires its current authorized Orca run')
    if phase == 'appearance-compare':
        from mvp.exp0034_appearance import IDENTITY, validate_authorization
        if run_id != IDENTITY[0]:
            raise ValueError('EXP-0034 requires the existing Orca run')
        validate_authorization()
    if phase in ('prompt-regression', *INDEPENDENT_PHASES) and run_id != REGRESSION_RUN:
        raise ValueError('EXP-0016 requires the existing Orca run')


def sources(config=None):
    names = ['orchestration/queue.py', 'orchestration/mock_job.py', 'orchestration/mvp_command.py',
             'orchestration/vlm_command.py', 'vlm_batch/common.py', 'vlm_batch/qwen.py',
             'vlm_batch/run.py', 'configs/vlm_batch01_prompt.txt']
    names += ['mvp/' + name + '.py' for name in
              ('method', 'compare', 'runner', 'windows', 'events', 'evidence', 'pipeline', 'cli', 'independent')]
    names += ['configs/' + name for name in CONFIG_NAMES]
    if config and config.get('phase') == 'appearance-compare':
        names += ['mvp/exp0034_appearance.py', 'sceneguard/appearance_support.py',
                  'tests_mvp/test_exp0034_appearance.py']
    if config and config.get('phase') == 'appearance-8b':
        names += ['mvp/exp0038.py', 'mvp/exp0034_appearance.py',
                  'sceneguard/appearance_support.py', 'batch02_vlm/__init__.py',
                  'batch02_vlm/runner.py', 'orchestration/batch02_vlm_command.py',
                  'requirements-vlm-batch02-lock.txt', 'tests_mvp/test_exp0038.py',
                  'tests_mvp/test_exp0038_queue.py']
    if config and config.get('phase') == 'candidate-vlm':
        names += ['mvp/candidate_vlm.py', 'configs/exp0033_cv_vlm_manifest.json',
                  'configs/exp0033_cv_vlm_prompt.txt']
    if config and config.get('phase') == 'prompt-regression':
        names += ['configs/' + REGRESSION_MANIFEST, 'configs/' + REGRESSION_PROMPT]
    if config and config.get('phase') in INDEPENDENT_PHASES:
        from mvp.independent import MANIFEST
        names += [MANIFEST, 'configs/' + REGRESSION_PROMPT]
    return {name: file_hash(ROOT / name) for name in names}


def input_contract(phase):
    if phase not in PHASES:
        raise ValueError('registered MVP phase required')
    if phase == 'appearance-8b':
        from mvp.exp0038 import input_contract as bind_8b
        return bind_8b()
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
    if phase == 'appearance-compare':
        from mvp.exp0034_appearance import bind_inputs
        inputs.update(bind_inputs())
        return inputs
    if phase in INDEPENDENT_PHASES:
        from mvp.independent import bind_inputs
        inputs.update(bind_inputs())
        return inputs
    if phase == 'candidate-vlm':
        # The evaluation reference file is intentionally excluded from the model contract.
        from mvp.candidate_vlm import frozen_manifest, verify_candidate_events
        pilot = frozen_manifest()
        original_events = verify_candidate_events(pilot)
        inputs['videos'] = {r['source_id']: file_hash(ASSETS / r['path'])
                            for r in pilot['videos']}
        if inputs['videos'] != {r['source_id']: r['source_sha256'] for r in pilot['videos']}:
            raise ValueError('Original CCTV source differs from the fixed pilot manifest')
        inputs['pilot_event_hashes'] = {k: v['sha256'] for k, v in original_events.items()}
        inputs['pilot_manifest_sha256'] = file_hash(ROOT / 'configs/exp0033_cv_vlm_manifest.json')
        inputs['pilot_prompt_sha256'] = file_hash(ROOT / 'configs/exp0033_cv_vlm_prompt.txt')
        return inputs
    if phase == 'dev':
        inputs['clips'] = {r['clip_id']: {name: file_hash(ASSETS / r['cache_dir'] / name)
                                        for name in ('rgb.npy', 'input.json')}
                           for r in source['development_clips']}
        # Pin successful historical baseline receipts and all reusable output bytes.
        from mvp.compare import baseline_paths
        inputs['baseline'] = {str(p.relative_to(ASSETS)): file_hash(p) for p in baseline_paths()}
    else:
        manifest = load_regression_manifest() if phase == 'prompt-regression' else None
        inputs['videos'] = {r['source_id']: file_hash(ASSETS / r['relative_video_path'])
                            for r in source['continuous_sources']
                            if manifest is None or r['source_id'] in manifest['sources']}
        if any(inputs['videos'][r['source_id']] != r['sha256'] for r in source['continuous_sources']
               if r['source_id'] in inputs['videos']):
            raise ValueError('original full video differs from frozen source hash')
        if manifest is not None:
            inputs['prompt_sha256'] = file_hash(ROOT / 'configs' / REGRESSION_PROMPT)
            inputs['window_manifest_sha256'] = file_hash(ROOT / 'configs' / REGRESSION_MANIFEST)
    return inputs


def validate(config, inputs, runtime):
    if not isinstance(config, dict) or set(config) != {'phase', 'view', 'settings'}:
        raise ValueError('fixed phase/view/settings config required')
    if config['phase'] not in PHASES or config['view'] not in ('fixed_roi', 'full_frame'):
        raise ValueError('unregistered phase/view')
    if config['phase'] == 'candidate-vlm' and config['view'] != 'fixed_roi':
        raise ValueError('EXP-0033 uses the existing fixed camera ROI only')
    if config['phase'] == 'appearance-compare' and config['view'] != 'full_frame':
        raise ValueError('EXP-0034 uses exact stored native target crops only')
    if config['phase'] == 'appearance-8b' and config['view'] != 'full_frame':
        raise ValueError('EXP-0038 uses exact stored native target crops only')
    if config['phase'] == 'dev' and config['view'] != 'fixed_roi':
        raise ValueError('development B outputs must be reused, not rerun')
    if config['phase'] in INDEPENDENT_PHASES and config['view'] != 'full_frame':
        raise ValueError('independent comparison permits full_frame only; no frozen camera ROI')
    if not same(config['settings'], settings_for_phase(config['phase'])):
        raise ValueError('baseline generation settings required')
    if Path(runtime).resolve() != RUNTIME:
        raise ValueError('existing canonical GPU queue required')
    if not interpreter_for_phase(config['phase']).is_file():
        raise ValueError('existing offline VLM interpreter unavailable')
    if inputs != input_contract(config['phase']):
        raise ValueError('registered model/input/config hashes differ')
    if config['phase'] in INDEPENDENT_PHASES:
        from mvp.independent import load_manifest, validate_decoder
        validate_decoder(load_manifest())
    return config['phase'], config['view']


def command(config, inputs, runtime, attempt, lock_fd):
    phase, view = validate(config, inputs, runtime)
    if not isinstance(attempt, str) or not re.fullmatch('[0-9a-f]{32}', attempt):
        raise ValueError('invalid queue attempt')
    return [str(interpreter_for_phase(phase)), '-I', str(ROOT / 'mvp/runner.py'), '--phase', phase,
            '--view', view, '--attempt', attempt, '--lock-fd', str(lock_fd)]


def output_path(phase, attempt):
    if phase not in PHASES or not isinstance(attempt, str) or not re.fullmatch('[0-9a-f]{32}', attempt):
        raise ValueError('invalid phase or queue attempt')
    if phase in INDEPENDENT_PHASES:
        path = ASSETS / 'outputs/mvp0001/EXP-0016/independent' / phase / attempt
    else:
        experiment = {'dev': 'EXP-0011', 'full': 'EXP-0012', 'prompt-regression': 'EXP-0016',
                      'candidate-vlm': 'EXP-0033', 'appearance-compare': 'EXP-0034',
                      'appearance-8b': 'EXP-0038'}[phase]
        path = ASSETS / 'outputs/mvp0001' / experiment / attempt
    if phase in ('prompt-regression', 'candidate-vlm', 'appearance-compare', 'appearance-8b', *INDEPENDENT_PHASES) and path.resolve() != path:
        raise ValueError('EXP-0016 output must be a new local attempt without symlink redirection')
    return path


def settings_for_phase(phase):
    if phase == 'appearance-8b':
        from mvp.exp0038 import SETTINGS as settings
        return settings
    return SETTINGS


def interpreter_for_phase(phase):
    if phase == 'appearance-8b':
        from mvp.exp0038 import INTERPRETER as interpreter
        return interpreter
    return INTERPRETER
