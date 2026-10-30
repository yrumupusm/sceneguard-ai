"""EXP-0038 support: one pinned 8B NF4 load, six preserved appearance pairs.

The local coordinator must wire this into a NEW phase of the existing canonical
mvp-0001 queue. No standalone inference CLI or fallback/offload path is provided.
Only stdlib is imported until load_analyzer() verifies the existing queue lease.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import time
from types import SimpleNamespace

MODEL_ID = 'Qwen/Qwen3-VL-8B-Instruct'
REVISION = '0c351dd01ed87e9c1b53cbc748cba10e6187ff3b'
PHASE = 'appearance-8b'
BASELINE_MANIFEST_SHA256 = '996ecdb638b624d69c54a70ff0e44027c95a3d2dd04a78efa00a69856af3ec90'
PAIR_IMAGE_COUNTS = [5, 5, 5, 4, 4, 4]
MIN_FREE_MIB = 8192
ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / 'runtime/EXP-0038'
MODEL_DIR = ROOT / 'weights/Qwen3-VL-8B-Instruct'
CHECKPOINT = LOCAL / 'checkpoint.json'
AUTHORIZATION = LOCAL / 'appearance-execution-authorization.json'
INTERPRETER = ROOT / '.venv-vlm-batch02/bin/python'
ENVIRONMENT = ROOT / 'runtime/BATCH-0002/vlm/environment.json'
BASELINE_OUTPUT = ROOT / 'outputs/mvp0001/EXP-0034/565b65a15fee492a8aea0e29bde1cb4e/appearance_results.json'
QUANTIZATION = dict(load_in_4bit=True, bnb_4bit_quant_type='nf4',
    bnb_4bit_compute_dtype='bfloat16', bnb_4bit_quant_storage='uint8',
    bnb_4bit_use_double_quant=True, llm_int8_skip_modules=['model.visual', 'lm_head'],
    llm_int8_enable_fp32_cpu_offload=False)
SETTINGS = dict(seed=0, batch_size=1, do_sample=False, max_new_tokens=192,
    repetition_penalty=1.0, attention='sdpa', device='cuda:0', dtype='bfloat16',
    quantization=QUANTIZATION, minimum_gpu_free_mib=MIN_FREE_MIB,
    execution_error_retries_max=0, model_loads=1, maximum_generate_calls=6,
    warmup_generations=0)
REQUIRED_FILES = {
    'config.json', 'generation_config.json', 'preprocessor_config.json',
    'tokenizer.json', 'tokenizer_config.json', 'chat_template.json',
    'model.safetensors.index.json',
    *(f'model-{i:05d}-of-00004.safetensors' for i in range(1, 5)),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def verify_checkpoint(directory: Path, receipt: dict) -> dict:
    """CPU preparation receipt pins files from the official immutable revision.

    The preparation step must first check official Hub LFS hashes. This function
    checks the downloaded bytes AGAIN; it is not proof of receipt authenticity.
    """
    directory = Path(directory)
    if receipt.get('model_id') != MODEL_ID or receipt.get('revision') != REVISION:
        raise ValueError('Use the pinned official 8B-Instruct checkpoint')
    files = receipt.get('files', {})
    if not isinstance(files, dict) or not REQUIRED_FILES.issubset(files):
        raise ValueError('Incomplete local checkpoint inventory')
    verified = {}
    for name, record in files.items():
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts or not relative.parts:
            raise ValueError('Invalid checkpoint inventory path')
        path = directory / relative
        # Hugging Face cache symlinks are not assumed safe; use a materialized local copy.
        if path.is_symlink() or any(p.is_symlink() for p in path.parents) or not path.is_file():
            raise ValueError('Expected materialized local checkpoint file')
        expected = record.get('sha256')
        size = record.get('bytes')
        if (not isinstance(expected, str) or len(expected) != 64
                or any(c not in '0123456789abcdef' for c in expected)
                or type(size) is not int or size < 0
                or path.stat().st_size != size or sha256(path) != expected):
            raise ValueError('Checkpoint file bytes/hash mismatch: ' + name)
        verified[name] = expected
    index = json.loads((directory / 'model.safetensors.index.json').read_text())
    shards = set(index.get('weight_map', {}).values())
    expected_shards = {n for n in REQUIRED_FILES if n.endswith('.safetensors')}
    if shards != expected_shards:
        raise ValueError('Expected all four official 8B shards')
    config = json.loads((directory / 'config.json').read_text())
    text = config.get('text_config', {})
    if (config.get('model_type') != 'qwen3_vl'
            or config.get('architectures') != ['Qwen3VLForConditionalGeneration']
            or text.get('hidden_size') != 4096 or text.get('num_hidden_layers') != 36
            or config.get('tie_word_embeddings') is not False):
        raise ValueError('Checkpoint is not the pinned 8B architecture')
    return verified


def require_phase(context: dict) -> None:
    config = json.loads(context['config_json'])
    if context.get('command') != 'mvp-0001' or config.get('phase') != PHASE:
        raise ValueError('A new canonical appearance-8b phase is required')


def environment_binding() -> dict:
    """Verify the preserved installed environment before loading, never per pair."""
    env = json.loads(ENVIRONMENT.read_text())
    if sha256(INTERPRETER) != env['interpreter_sha256'] or not env.get('files'):
        raise ValueError('Preserved batch02 Python environment required')
    for name, expected in env['files'].items():
        path = ROOT / name
        if not path.is_relative_to(ROOT) or '..' in Path(name).parts or sha256(path) != expected:
            raise ValueError('Preserved batch02 environment changed: ' + name)
    return dict(receipt_sha256=sha256(ENVIRONMENT),
                interpreter_sha256=sha256(INTERPRETER), versions=env['versions'],
                files=env['files'])


def input_contract() -> dict:
    from mvp.exp0034_appearance import load_manifest, MANIFEST, bind_inputs
    manifest = load_manifest()
    verify_pair_manifest(manifest, MANIFEST)
    receipt = json.loads(CHECKPOINT.read_text())
    checked = verify_checkpoint(MODEL_DIR, receipt)
    return dict(bind_inputs(), model_files=checked, model_id=MODEL_ID, revision=REVISION,
        checkpoint_receipt_sha256=sha256(CHECKPOINT),
        checkpoint_receipt_path=str(CHECKPOINT.relative_to(ROOT)),
        model_directory=str(MODEL_DIR.relative_to(ROOT)),
        environment=environment_binding(), quantization=QUANTIZATION)


def validate_authorization(job=None) -> dict:
    """Current dispatch GO; cheap frozen bindings on repeated generation leases."""
    from orchestration.mvp_command import sources
    from orchestration.queue import digest
    authorization = json.loads(AUTHORIZATION.read_text())
    identity = tuple(authorization.get(k) for k in ('run_id', 'task_id', 'dispatch_id'))
    from mvp.exp0034_appearance import IDENTITY as old_identity
    if (any(not isinstance(v, str) or not v for v in identity)
            or identity[1] == old_identity[1] or identity[2] == old_identity[2]):
        raise ValueError('A new live EXP-0038 Task/Dispatch is required')
    if any(authorization.get(k) is not True for k in
           ('confirmed', 'inference_authorized', 'independent_review_passed')):
        raise ValueError('Explicit coordinator GO and independent preflight required')
    if (authorization.get('maximum_generate_calls') != 6
            or authorization.get('model_loads') != 1
            or authorization.get('warmup_generations') != 0):
        raise ValueError('One load, six generations, no warmup required')
    if (authorization.get('sources') != sources({'phase': PHASE})
            or authorization.get('checkpoint_receipt_sha256') != sha256(CHECKPOINT)
            or authorization.get('code_sha') != subprocess.check_output(
                ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()):
        raise ValueError('Reviewed source/checkpoint/HEAD freeze differs')
    if job is None:
        expected_input = digest(input_contract())
    else:
        require_phase(job)
        if tuple(job[k] for k in ('run_id', 'task_id', 'dispatch_id')) != identity:
            raise ValueError('Current authorized queue Task/Dispatch required')
        expected_input = job['input_hash']
        if digest(json.loads(job['input_json'])) != expected_input:
            raise ValueError('Queue input hash differs')
    if authorization.get('input_contract_sha256') != expected_input:
        raise ValueError('Reviewed input contract differs')
    return authorization


def verify_live_dispatch(job, attempt, previous) -> None:
    """Repeated cheap lease checks exclude old authorization and phase retries."""
    validate_authorization(job)
    cursor, matches = None, []
    while True:
        argv = ['orca-ide', 'orchestration', 'worker-list', '--run', job['run_id'], '--json']
        if cursor:
            argv += ['--cursor', cursor]
        snapshot = json.loads(subprocess.check_output(argv, text=True, timeout=25))
        if not snapshot.get('ok'):
            raise ValueError('EXP-0038 native dispatch lookup failed')
        result = snapshot.get('result', {})
        matches += [w for w in result.get('workers', [])
            if w.get('taskId') == job['task_id'] and w.get('dispatchId') == job['dispatch_id']
            and w.get('dispatchStatus') == 'dispatched'
            and w.get('projection', {}).get('liveness', {}).get('verdict') == 'live']
        page = result.get('page', {})
        if not page.get('hasMore'):
            break
        next_cursor = page.get('nextCursor')
        if not next_cursor or next_cursor == cursor:
            raise ValueError('EXP-0038 native dispatch pagination failed')
        cursor = next_cursor
    if len(matches) != 1:
        raise ValueError('EXP-0038 native dispatch must be live')
    selected = [r for r in previous if json.loads(r[2]).get('phase') == PHASE]
    if len(selected) != 1 or tuple(selected[0][:2]) != (job['job_id'], attempt):
        raise ValueError('Only one EXP-0038 job/attempt; automatic retry forbidden')


def load_kwargs(torch, bitsandbytes_config) -> dict:
    """Same NF4 route as EXP-0020; language only, no CPU/disk offload."""
    values = dict(QUANTIZATION, bnb_4bit_compute_dtype=torch.bfloat16,
                  bnb_4bit_quant_storage=torch.uint8)
    q = bitsandbytes_config(**values)
    return dict(local_files_only=True, trust_remote_code=False,
                torch_dtype=torch.bfloat16, attn_implementation='sdpa',
                device_map={'': 'cuda:0'}, quantization_config=q)


def load_analyzer(directory: Path, receipt: dict):
    """Called once by the NEW queue phase, never by the 2B constructor.

    Returns (analyzer, load_metrics). Existing prepare_images/compare_images and
    run_appearance consume this analyzer without changing input or parser rules.
    Queue source/input bindings must include this module, receipt and all model
    files; see CODEX_EXP0038.md for the required local integration.
    """
    from mvp.runner import verify_environment_lease, check_resources
    context = verify_environment_lease()
    require_phase(context)
    validation_started = time.perf_counter()
    if Path(directory) != MODEL_DIR or receipt != json.loads(CHECKPOINT.read_text()):
        raise ValueError('Use the bound EXP-0038 checkpoint receipt and model directory')
    checked = verify_checkpoint(Path(directory), receipt)
    if checked != json.loads(context['input_json'])['model_files']:
        raise ValueError('Loaded checkpoint differs from registered 8B input')
    checkpoint_validation_seconds = time.perf_counter() - validation_started
    gate = check_resources({'minimum_gpu_free_mib': MIN_FREE_MIB})

    import torch
    from transformers import AutoProcessor, BitsAndBytesConfig, Qwen3VLForConditionalGeneration
    # This existing inventory function checks actual Linear4bit modules, BF16
    # vision/output weights, and that all parameters/quant states are on CUDA0.
    from batch02_vlm.runner import inventory

    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise ValueError('CUDA0 BF16 required')
    torch.manual_seed(0)
    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    processor = AutoProcessor.from_pretrained(str(directory), local_files_only=True,
                                              trust_remote_code=False)
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        str(directory), **load_kwargs(torch, BitsAndBytesConfig))
    model.eval()
    # Match greedy baseline behavior instead of inheriting card sampling defaults.
    gen = model.generation_config
    gen.do_sample = False
    gen.num_beams = 1
    gen.repetition_penalty = 1.0
    gen.temperature = None
    gen.top_p = None
    gen.top_k = None
    torch.cuda.synchronize()
    load_seconds = time.perf_counter() - started
    placement = inventory(model)
    if (model.config.tie_word_embeddings is not False
            or model.get_input_embeddings().weight is model.get_output_embeddings().weight):
        raise ValueError('Preserve the official 8B untied BF16 output head')
    footprint = dict(peak_allocated_bytes=int(torch.cuda.max_memory_allocated()),
                     peak_reserved_bytes=int(torch.cuda.max_memory_reserved()),
                     resident_allocated_bytes=int(torch.cuda.memory_allocated()),
                     resident_reserved_bytes=int(torch.cuda.memory_reserved()))
    analyzer = SimpleNamespace(model=model, processor=processor,
        settings={'device': 'cuda:0'}, phase=PHASE,
        last_processor_images=None, last_expanded_prompt=None,
        last_input_metadata=None, last_generated_token_ids=[])
    return analyzer, dict(model_id=MODEL_ID, revision=REVISION,
        model_files_sha256=checked, loading_and_quantization_seconds=load_seconds,
        checkpoint_validation_seconds=checkpoint_validation_seconds,
        load_memory=footprint, inventory=placement, resource_gate=gate,
        whole_device_after_load=check_resources({'minimum_gpu_free_mib': 0}),
        offload=False, model_loads=1, warmup_generations=0)


def verify_pair_manifest(manifest: dict, manifest_path: Path) -> None:
    if sha256(Path(manifest_path)) != BASELINE_MANIFEST_SHA256:
        raise ValueError('Use the exact preserved EXP-0034 six-pair manifest')
    counts = [len(p['before_images']) + len(p['after_images']) for p in manifest['pairs']]
    if counts != PAIR_IMAGE_COUNTS or len({p['pair_id'] for p in manifest['pairs']}) != 6:
        raise ValueError('Six original pairs / 27 ordered image slots are required')


def _seconds(value, name):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError('Invalid seconds: ' + name)
    return float(value)


def summarize_rows(rows: list[dict]) -> dict:
    """Timing/format statistics only. Unknown AFTER parsing failure is not abstention."""
    if len(rows) != 6 or len({r['pair_id'] for r in rows}) != 6:
        raise ValueError('Need six unique, complete comparisons')
    if [r['images'] for r in rows] != PAIR_IMAGE_COUNTS:
        raise ValueError('Changed input count/order')
    generation = [_seconds(r['timing']['generation_seconds'], 'generation') for r in rows]
    preparation = [_seconds(r['timing']['prepare_seconds'], 'preparation') for r in rows]
    valid = [r for r in rows if r['parsed']['valid']]
    decisions = Counter(r['parsed']['comparison']['decision'] for r in valid)
    return dict(
        pairs=6, image_slots=27, generation_calls=6,
        valid_response_rows=len(valid), invalid_response_rows=6-len(valid),
        valid_decisions=dict(decisions),
        explicit_valid_unknown=decisions.get('unknown', 0),
        unavailable_parts_in_valid_rows=sum(
            r['parsed']['comparison'][part] == 'unavailable'
            for r in valid for part in ('upper', 'lower', 'bag')),
        generation_seconds_sum=sum(generation),
        generation_seconds_median=statistics.median(generation),
        generation_seconds_min=min(generation), generation_seconds_max=max(generation),
        first_pair_generation_seconds=generation[0],
        remaining_pairs_generation_seconds_median=statistics.median(generation[1:]),
        prepare_seconds_sum=sum(preparation),
        output_tokens=sum(r['output_tokens'] for r in rows),
        token_limit_rows=sum(bool(r.get('hit_token_limit')) for r in rows),
        generation_peak_allocated_bytes=max(r['gpu_memory']['peak_allocated_bytes'] for r in rows),
        generation_peak_reserved_bytes=max(r['gpu_memory']['peak_reserved_bytes'] for r in rows),
        caveats=['Different pairs/output lengths, not repeated steady-state latency',
                 'First pair includes cold execution effects; no extra warmup call',
                 'Torch allocator peaks are not whole-device memory',
                 'Valid format/unknown counts do not establish correct visual reasoning'],
        semantic_accuracy=None, identity_accuracy=None, automatic_adoption=False)


def compare_saved_rows(baseline: list[dict], candidate: list[dict]) -> list[dict]:
    """Post-generation inspection. Never pass baseline answers into the model."""
    summarize_rows(baseline)
    summarize_rows(candidate)
    old = {r['pair_id']: r for r in baseline}
    if set(old) != {r['pair_id'] for r in candidate}:
        raise ValueError('Baseline/candidate pairs differ')
    comparisons = []
    for row in candidate:
        previous = old[row['pair_id']]
        if (previous['images'] != row['images'] or previous['frame_groups'] != row['frame_groups']):
            raise ValueError('Baseline image groups changed')
        keys = ('processor_rgb_sha256', 'image_grid_thw', 'image_budget')
        parity = all(k in previous['input_metadata'] and k in row['input_metadata'] and
                     previous['input_metadata'][k] == row['input_metadata'][k] for k in keys)
        comparisons.append(dict(pair_id=row['pair_id'],
            baseline=previous['parsed'], candidate=row['parsed'],
            processor_image_parity=parity,
            baseline_generation_seconds=previous['timing']['generation_seconds'],
            candidate_generation_seconds=row['timing']['generation_seconds'],
            baseline_output_tokens=previous['output_tokens'], candidate_output_tokens=row['output_tokens'],
            human_review='pending', semantic_improvement=None,
            note='2B BF16 vs 8B NF4: capacity, vision encoder and quantization differ'))
    return comparisons


def run_six_pairs(directory: Path, receipt: dict, folder: Path, context: dict,
                  baseline_output: Path) -> dict:
    """New queue-phase entrypoint. Coordinator binds all arguments before enqueue.

    Uses the original six-pair loop, not six independent model loads. Historical
    answers are opened only AFTER all new generations, solely for comparison.
    """
    from mvp.exp0034_appearance import (load_manifest, MANIFEST, bind_inputs,
                                       verify_native_crops, run_appearance)
    from orchestration.mock_job import atomic_json
    folder = Path(folder)
    root = ROOT
    if (not folder.resolve().is_relative_to(root/'outputs/mvp0001/EXP-0038')
            or folder.is_symlink() or any(p.is_symlink() for p in folder.parents)
            or (folder/'appearance_results.json').exists()):
        raise ValueError('Use a fresh EXP-0038 canonical queue output directory')
    folder.mkdir(parents=True, exist_ok=True)
    baseline_output = Path(baseline_output)
    begun = time.perf_counter()
    load = None
    stage = 'cpu_input_validation'
    try:
        manifest = load_manifest()
        verify_pair_manifest(manifest, MANIFEST)
        bound = bind_inputs()
        native = verify_native_crops()
        if native['native_crops_checked'] != 27:
            raise ValueError('Incomplete original crop verification')
        atomic_json(folder/'input_binding.json', dict(
            source_inputs=bound,
            native_validation=native, semantic_labels_supplied=False))
        validation_seconds = time.perf_counter() - begun
        stage = 'model_loading'
        analyzer, load = load_analyzer(directory, receipt)
        atomic_json(folder/'model_load.json', load)
        stage = 'six_pairs'
        measured = time.perf_counter()
        # Existing loop stores raw outputs, exact processor images and tokens.
        rows = run_appearance(analyzer, folder, context)
        six_pair_wall = time.perf_counter() - measured
        stats = summarize_rows(rows)
        stage = 'post_generation_comparison'
        # Do not even open historical response bytes until every generation ends.
        baseline_sha = sha256(baseline_output)
        previous = json.loads(baseline_output.read_text(encoding='utf-8'))
        if previous.get('partial') is not False:
            raise ValueError('Historical six-pair run is incomplete')
        comparison = compare_saved_rows(previous['completed'], rows)
        atomic_json(folder/'baseline_comparison.json', comparison)
        result = dict(experiment='EXP-0038', status='completed_pending_visual_review',
            model_id=MODEL_ID, revision=REVISION, statistics=stats,
            cpu_input_validation_seconds=validation_seconds,
            checkpoint_validation_seconds=load['checkpoint_validation_seconds'],
            loading_and_quantization_seconds=load['loading_and_quantization_seconds'],
            six_pair_wall_including_artifact_writes_seconds=six_pair_wall,
            total_function_wall_seconds=time.perf_counter()-begun,
            model_loads=1, warmup_generations=0, new_detector_calls=0,
            new_tracker_calls=0, training_steps=0, external_image_uploads=0,
            baseline_output_sha256=baseline_sha, automatic_adoption=False,
            intrusion_verdict=None, identity_merged=False)
        atomic_json(folder/'exp0038_summary.json', result)
        return result
    except Exception as exc:
        memory = None
        # Failure reporting must not initialize CUDA after a CPU validation error.
        import sys
        torch_ref = sys.modules.get('torch')
        if torch_ref is not None and torch_ref.cuda.is_initialized():
            try:
                memory = dict(allocated_bytes=torch_ref.cuda.memory_allocated(),
                    reserved_bytes=torch_ref.cuda.memory_reserved(),
                    peak_allocated_bytes=torch_ref.cuda.max_memory_allocated(),
                    peak_reserved_bytes=torch_ref.cuda.max_memory_reserved())
            except Exception as memory_error:
                memory = dict(error=repr(memory_error))
        atomic_json(folder/'exp0038_failure.json', dict(
            experiment='EXP-0038', status='failed', stage=stage,
            error_type=type(exc).__name__, error=str(exc),
            elapsed_seconds=time.perf_counter()-begun,
            gpu_memory=memory,
            model_load_recorded=load is not None, automatic_retry=False,
            automatic_offload_fallback=False, actual_pairs='see appearance_results.json if present'))
        raise
