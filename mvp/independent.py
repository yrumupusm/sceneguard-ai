"""Hash-bound EXP-0016 prompt-only comparison; no evaluation labels are loaded."""
import hashlib
import json
from pathlib import Path
import re

from orchestration.vlm_command import ASSETS, file_hash

ROOT = Path(__file__).resolve().parents[1]
PHASES = ('independent-original', 'independent-revised')
MANIFEST = 'configs/mvp_exp0016_independent_manifest.json'
MANIFEST_SHA256 = '68b07ef836422cd9043e4fcb88b40b0f70e256d0024a2bd57ce29a12e08aa765'


def load_manifest():
    path = ROOT / MANIFEST
    if file_hash(path) != MANIFEST_SHA256:
        raise ValueError('independent four-window manifest hash differs')
    manifest = json.loads(path.read_text(encoding='utf-8'))
    for prompt in manifest['prompts'].values():
        if file_hash(ROOT / prompt['path']) != prompt['sha256']:
            raise ValueError('independent prompt hash differs')
    return manifest


def prompt(window_id, phase):
    if phase not in PHASES or not isinstance(window_id, str) or not re.fullmatch(r'w00000[1-4]', window_id):
        raise ValueError('independent phase and anonymous four-window ID required')
    selected = load_manifest()['prompts'][phase]
    return f'Clip ID: {window_id}\n' + (ROOT / selected['path']).read_text(encoding='utf-8').strip()


def bind_inputs():
    manifest = load_manifest()
    videos = {sid: file_hash(ASSETS / source['relative_video_path'])
              for sid, source in manifest['sources'].items()}
    if videos != {sid: source['sha256'] for sid, source in manifest['sources'].items()}:
        raise ValueError('independent original source video hash differs')
    return {'videos': videos, 'window_manifest_sha256': MANIFEST_SHA256,
            'prompt_hashes': {phase: p['sha256'] for phase, p in manifest['prompts'].items()}}


def validate_decoder(manifest):
    import av
    actual = {'pyav': av.__version__, 'libraries': {k: list(v) for k, v in av.library_versions.items()}}
    if actual != manifest['decoder']:
        raise ValueError('independent frozen decoder differs')


def validate_window(window, frozen, rgb):
    if window.start != frozen['start'] or window.end != frozen['end'] or window.source() != frozen['timing']:
        raise ValueError('independent exact frame indices/PTS/timing differ')
    if [hashlib.sha256(frame.tobytes()).hexdigest() for frame in rgb] != frozen['frame_sha256']:
        raise ValueError('independent decoded RGB frame hashes differ')


def run_comparison(analyzer, folder, context):
    """Use the existing decoder/sampler and full-frame processor without labels."""
    import numpy as np
    from mvp.windows import iter_windows
    from mvp.pipeline import _clear_diagnostics, _failure_diagnostics
    from orchestration.mock_job import atomic_json

    manifest = load_manifest()
    if (context.get('phase') not in PHASES or context.get('view') != 'full_frame'
            or context.get('run_id') != manifest['run_id']):
        raise ValueError('independent full-frame phase requires the existing Run')
    validate_decoder(manifest)
    bindings = bind_inputs()  # Recheck sources before decoding or any analyzer call.
    results = []
    for sid, item in manifest['sources'].items():
        selected = {row['start']: row for row in manifest['windows'] if row['source_id'] == sid}
        stats, completed = {}, []
        try:
            for window in iter_windows(ASSETS / item['relative_video_path'], stats=stats):
                frozen = selected.get(window.start)
                if frozen is None:
                    continue
                rgb = window.rgb
                validate_window(window, frozen, rgb)
                wid = frozen['window_id']
                target = folder / 'windows' / wid
                target.mkdir(parents=True, exist_ok=False)
                analyzer.artifact_root = folder / 'windows'
                # Only original measured timing, RGB and anonymous ID reach inference.
                source = window.source()
                atomic_json(target / 'input.json', {**source, 'source_sha256': bindings['videos'][sid],
                    'roi': manifest['roi'], 'frame_sha256': frozen['frame_sha256'],
                    'prompt_sha256': bindings['prompt_hashes'][context['phase']]})
                _clear_diagnostics(analyzer)
                try:
                    record = analyzer.analyze(rgb, source, wid, list(manifest['roi']))
                except Exception:
                    atomic_json(target / 'failure.json', _failure_diagnostics(analyzer))
                    raise
                atomic_json(target / 'result.json', record)
                (target / 'raw_response.txt').write_text(record['raw_response'], encoding='utf-8')
                (target / 'expanded_prompt.txt').write_text(analyzer.last_expanded_prompt, encoding='utf-8')
                np.save(target / 'generated_token_ids.npy', np.array(analyzer.last_generated_token_ids, dtype='int64'))
                np.save(target / 'processor_rgb.npy', analyzer.last_processor_frames, allow_pickle=False)
                completed.append(wid)
            if set(completed) != {row['window_id'] for row in selected.values()} or not stats.get('eof_reached'):
                raise ValueError('independent four windows must decode from original sources through EOF')
        finally:
            atomic_json(folder / (sid + '_summary.json'),
                        {'decode': stats, 'completed_windows': completed, 'run_context': context})
        results.extend(completed)
    return results
