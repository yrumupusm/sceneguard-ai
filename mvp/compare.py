"""Explicit successful-baseline reuse and input fingerprints, never pseudo-GT."""
import copy
import ast
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sqlite3
import subprocess
import time

from orchestration.vlm_command import ASSETS, RUNTIME, SETTINGS, file_hash
from orchestration.queue import digest
from vlm_batch.common import parse_pair

ROOT = Path(__file__).resolve().parents[1]
BASELINE_ATTEMPT = '8b93c06304724009b8ca5a0d15a28288'
BASELINE = ASSETS / 'outputs/vlm_batch01/EXP-0008' / BASELINE_ATTEMPT


def same_qwen_budget_refactor(old, current):
    """Recognize only EXP10's extraction of two identical budget dict literals."""
    from mvp.method import PROCESSOR_SIZE
    if (hashlib.sha256(old).hexdigest() != '56388dfc25fbe926372f1782b689cb440ec182be8073c9a2a39a9111e4447b4f'
            or hashlib.sha256(current).hexdigest() != '94d0c64f1355a7f0a3c13b9836d7a0159345fea441464d050fa2c8c998fc237b'):
        return False
    tree = ast.parse(current)
    changes = []

    class RestoreLiteral(ast.NodeTransformer):
        def visit_ClassDef(self, node):
            if node.name == 'Adapter':
                retained = []
                for statement in node.body:
                    if (isinstance(statement, ast.Assign) and len(statement.targets) == 1
                            and isinstance(statement.targets[0], ast.Name)
                            and statement.targets[0].id == 'PROCESSOR_SIZE'
                            and ast.literal_eval(statement.value) == PROCESSOR_SIZE):
                        changes.append('constant')
                    else:
                        retained.append(statement)
                node.body = retained
            return self.generic_visit(node)

        def visit_Call(self, node):
            if (isinstance(node.func, ast.Attribute) and node.func.attr == 'copy'
                    and isinstance(node.func.value, ast.Attribute)
                    and node.func.value.attr == 'PROCESSOR_SIZE'
                    and isinstance(node.func.value.value, ast.Name)
                    and node.func.value.value.id == 'self' and not node.args and not node.keywords):
                changes.append('literal')
                return ast.parse(repr(PROCESSOR_SIZE), mode='eval').body
            return self.generic_visit(node)

    restored = RestoreLiteral().visit(tree)
    return (changes.count('constant') == 1 and changes.count('literal') == 2 and
            ast.dump(restored, include_attributes=False) == ast.dump(ast.parse(old), include_attributes=False))


def baseline_paths():
    return [BASELINE / 'summary.json'] + [BASELINE / f'clip{i:02}' / name
        for i in range(1, 7) for name in ('result.json', 'raw_response.txt', 'expanded_prompt.txt',
                                         'generated_token_ids.npy', 'processor_resized_rgb.npy')]


def successful_baseline(attempt, phase=None, view=None):
    """Accept only native successful attempts, never a caller-supplied output file."""
    with sqlite3.connect(f'file:{RUNTIME / "queue.sqlite3"}?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        row = db.execute('SELECT a.attempt_id,a.status AS attempt_status,a.exit_code,j.* FROM attempts a '
                         'JOIN jobs j USING(job_id) WHERE a.attempt_id=?', (attempt,)).fetchone()
    if row is None or row['attempt_status'] != 'succeeded' or row['exit_code'] != 0 or row['status'] != 'succeeded':
        raise ValueError('successful native baseline attempt required for reuse')
    row = dict(row)
    config = json.loads(row['config_json'])
    expected = {'adapter': 'qwen', 'settings': SETTINGS} if phase is None else {
        'phase': phase, 'view': view, 'settings': SETTINGS}
    if row['command'] != ('vlm-batch01' if phase is None else 'mvp-0001') or config != expected:
        raise ValueError('successful attempt is not the requested fixed baseline')
    return row


def semantic_digest(rgb, source, window_id, roi, model_digest, settings_digest):
    """Timing, observed pixels, exact prompt ID, and all semantic dependencies."""
    from mvp.method import PROCESSOR_SIZE, crop_frames
    cropped, bounds = crop_frames(rgb, roi)
    timing = {k: source[k] for k in ('fps', 'pts_seconds', 'native_pts', 'time_base',
             'relative_indices', 'source_size', 'window_start', 'window_end', 'last_decoded_pts')}
    return digest(dict(pixels=hashlib.sha256(cropped.tobytes()).hexdigest(), shape=list(cropped.shape),
        timing=timing, window_id=window_id, bounds=bounds, model_digest=model_digest,
        settings_digest=settings_digest, processor_size=PROCESSOR_SIZE,
        prompt_sha256=file_hash(ROOT / 'configs/vlm_batch01_prompt.txt'),
        code={name: file_hash(ROOT / name) for name in
              ('mvp/method.py', 'vlm_batch/common.py', 'vlm_batch/qwen.py', 'vlm_batch/run.py')},
        packages={name: importlib.metadata.version(name) for name in
                  ('torch', 'torchvision', 'transformers', 'tokenizers', 'numpy')}))


def read_baseline_results(source_dir):
    """Read once and pin the exact successful B result bytes for later reuse."""
    records = {}
    for path in sorted((Path(source_dir) / 'windows').glob('*/result.json')):
        raw = path.read_bytes()
        result = json.loads(raw)
        result['_reuse_binding'] = {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest()}
        records[path.parent.name] = result
    if not records:
        raise ValueError('successful baseline has no persisted window results')
    return records


def reuse_development(analyzer, rgb, source, clip_id, roi, model_files):
    """C1 fallback reuses EXP8 only after exact current processor equivalence."""
    import numpy as np
    from mvp.method import PROCESSOR_SIZE
    analyzer.last_generated_token_ids = []
    analyzer.last_processor_frames = None
    analyzer.last_expanded_prompt = None
    analyzer.last_input_metadata = None
    if clip_id != 'clip05' or list(roi) != [0, 0, 1, 1]:
        raise ValueError('only unchanged C1 full-frame fallback may reuse EXP8')
    t = time.perf_counter()
    job = successful_baseline(BASELINE_ATTEMPT)
    historical_inputs = json.loads(job['input_json'])
    if historical_inputs['model_files'] != model_files:
        raise ValueError('baseline and current local model hashes differ')
    for name in ('rgb.npy', 'input.json'):
        if historical_inputs['clips'][clip_id][name] != file_hash(ASSETS / 'outputs/vlm_exp0007' / clip_id / name):
            raise ValueError('baseline original input differs')
    summary = json.loads((BASELINE / 'summary.json').read_text())
    if summary['status'] != 'succeeded' or summary['settings'] != SETTINGS:
        raise ValueError('historical baseline summary/settings differ')
    for name in ('torch', 'torchvision', 'transformers', 'tokenizers', 'numpy'):
        if importlib.metadata.version(name) != summary['packages'][name]:
            raise ValueError('semantic processor/model package version differs')
    historical_code = {}
    code_equivalence = {}
    for name in ('vlm_batch/qwen.py', 'vlm_batch/run.py', 'vlm_batch/common.py', 'configs/vlm_batch01_prompt.txt'):
        old = subprocess.check_output(['git', 'show', f"{job['code_sha']}:{name}"], cwd=ROOT)
        historical_code[name] = hashlib.sha256(old).hexdigest()
        if historical_code[name] != file_hash(ROOT / name):
            if name != 'vlm_batch/qwen.py' or not same_qwen_budget_refactor(old, (ROOT / name).read_bytes()):
                raise ValueError('historical processor/generation/parser/prompt code differs')
            code_equivalence[name] = {'historical_sha256': historical_code[name],
                'current_sha256': file_hash(ROOT / name),
                'proof': 'AST identical after restoring exactly two unchanged processor budget literals'}
    inputs, info, frames = analyzer.prepare(rgb, source, clip_id, roi)
    # The only permitted historical code difference is the pinned constant
    # extraction above. Check every actual processor tensor against that
    # equivalent original full-frame path, without constructing any model.
    import torch
    from types import SimpleNamespace
    from vlm_batch.qwen import Adapter
    equivalent = object.__new__(Adapter)
    equivalent.processor = analyzer.processor
    equivalent.model = SimpleNamespace(config=SimpleNamespace(video_token_id=
        analyzer.processor.tokenizer.convert_tokens_to_ids(analyzer.processor.video_token)))
    original_inputs, _, _ = equivalent.prepare(rgb, source,
        (ROOT / 'configs/vlm_batch01_prompt.txt').read_text().strip(), clip_id)
    if set(inputs) != set(original_inputs) or any(not torch.equal(inputs[k], original_inputs[k]) for k in inputs):
        raise ValueError('current fallback tensors differ from equivalent historical adapter')
    tensor_hashes = {k: hashlib.sha256(v.detach().cpu().contiguous().numpy().tobytes()).hexdigest()
                     for k, v in inputs.items()}
    target = BASELINE / clip_id
    previous_bytes = (target / 'result.json').read_bytes()
    previous = json.loads(previous_bytes)
    expected = dict(source_pts=source['pts_seconds'], native_pts=source['native_pts'],
                    relative_indices=source['relative_indices'], source_fps=source['fps'],
                    time_base=source['time_base'], processor_size=PROCESSOR_SIZE,
                    resized_shape=info['resized_shape'], video_grid_thw=info['video_grid_thw'],
                    visual_tokens=info['visual_tokens'], input_tokens=info['input_tokens'])
    if previous['status'] != 'generated' or any(previous[k] != v for k, v in expected.items()):
        raise ValueError('historical native timing/processor inputs differ')
    expanded = analyzer.processor.tokenizer.decode(inputs['input_ids'][0], skip_special_tokens=False)
    if expanded != (target / 'expanded_prompt.txt').read_text() or not np.array_equal(
            frames, np.load(target / 'processor_resized_rgb.npy', allow_pickle=False)):
        raise ValueError('historical expanded prompt/actual processor pixels differ')
    raw_bytes = (target / 'raw_response.txt').read_bytes()
    raw = raw_bytes.decode('utf-8')
    parsed = parse_pair(raw)
    analyzer.last_processor_frames = frames
    analyzer.last_expanded_prompt = expanded
    analyzer.last_input_metadata = info
    analyzer.last_generated_token_ids = []
    return dict(raw_response=raw, parsed=parsed['postprocessed_parsed'], parse=parsed,
        input_metadata=info, output_tokens=previous['output_tokens'], newly_generated_tokens=0,
        gpu_memory=None, reused=True,
        timing={'prepare_seconds': None, 'generation_seconds': None,
                'reuse_validation_seconds': time.perf_counter()-t},
        reuse_provenance={'experiment_id': 'EXP-0008', 'attempt_id': BASELINE_ATTEMPT,
            'clip_id': clip_id, 'result_sha256': hashlib.sha256(previous_bytes).hexdigest(),
            'raw_sha256': hashlib.sha256(raw_bytes).hexdigest(), 'baseline_code': historical_code,
            'code_equivalence': code_equivalence,
            'equivalent_historical_adapter_tensors_sha256': tensor_hashes,
            'current_method_sha256': file_hash(ROOT / 'mvp/method.py'),
            'historical_output_tokens': previous['output_tokens'],
            'historical_timing': {key: previous[key] for key in ('prepare_seconds', 'generation_seconds')},
            'exact_pixels_prompt_native_timing_model_settings_verified': True})


class ExactReuseAnalyzer:
    """Reuse a proven successful full baseline only for identical full-frame ROI."""
    def __init__(self, analyzer, records, baseline_attempt, model_digest, settings_digest):
        self.analyzer = analyzer
        successful_baseline(baseline_attempt, 'full', 'full_frame')
        self.records = records
        self.baseline_attempt = baseline_attempt
        self.model_digest, self.settings_digest = model_digest, settings_digest

    def __getattr__(self, name):
        return getattr(self.analyzer, name)

    def analyze(self, rgb, source, window_id, roi):
        started = time.perf_counter()
        underlying = self.analyzer
        seen = set()
        while id(underlying) not in seen:
            seen.add(id(underlying))
            child = getattr(underlying, '__dict__', {}).get('analyzer')
            if child is None:
                break
            underlying = child
        underlying.last_generated_token_ids = []
        underlying.last_processor_frames = None
        underlying.last_expanded_prompt = None
        underlying.last_input_metadata = None
        if list(roi) != [0, 0, 1, 1] or len(rgb) < 2:
            return self.analyzer.analyze(rgb, source, window_id, roi)
        key = semantic_digest(rgb, source, window_id, roi, self.model_digest, self.settings_digest)
        previous = self.records.get(window_id)
        if previous is None or previous.get('semantic_input_sha256') != key:
            raise ValueError('full-frame fallback semantic input differs; no silent rerun')
        binding = previous.get('_reuse_binding')
        if not binding:
            raise ValueError('exact successful baseline result-byte binding required')
        actual = Path(binding['path']).read_bytes()
        if hashlib.sha256(actual).hexdigest() != binding['sha256']:
            raise ValueError('pinned baseline result bytes changed before reuse')
        original = json.loads(actual)
        if original != {k: v for k, v in previous.items() if k != '_reuse_binding'}:
            raise ValueError('baseline in-memory response differs from pinned result bytes')
        result = copy.deepcopy(previous)
        result.pop('_reuse_binding')
        result.update(reused=True, newly_generated_tokens=0, gpu_memory=None, generated_token_ids=[],
            timing={'prepare_seconds': None, 'generation_seconds': None,
                    'reuse_validation_seconds': time.perf_counter()-started},
            reuse_provenance={'baseline_attempt': self.baseline_attempt,
                             'semantic_input_sha256': key, 'baseline_window_id': window_id,
                             'historical_timing': copy.deepcopy(previous.get('timing')),
                             'historical_output_tokens': previous.get('output_tokens'),
                             'baseline_result_sha256': binding['sha256'],
                             'baseline_raw_response_sha256': hashlib.sha256(
                                 str(original.get('raw_response', '')).encode('utf-8')).hexdigest()})
        return result


class FingerprintedAnalyzer:
    """Attach semantic provenance to each generated or insufficient result."""
    def __init__(self, analyzer, model_digest, settings_digest):
        self.analyzer, self.model_digest, self.settings_digest = analyzer, model_digest, settings_digest

    def __getattr__(self, name):
        return getattr(self.analyzer, name)

    def analyze(self, rgb, source, window_id, roi):
        result = self.analyzer.analyze(rgb, source, window_id, roi)
        result['semantic_input_sha256'] = semantic_digest(rgb, source, window_id, roi,
                                                        self.model_digest, self.settings_digest)
        return result
