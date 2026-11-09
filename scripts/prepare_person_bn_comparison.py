"""EXP-0074 preparation and separately guarded future B/C trainer.

The prepare/verify commands never instantiate an optimizer or use CUDA.  Future
training requires a new reviewed release and a live canonical queue attempt;
this module does not register, enqueue, migrate, or otherwise mutate that queue.
"""
import argparse
from collections import Counter
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import sqlite3
import sys
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DATASET = ROOT / 'outputs/model-comparison/exp0074/person-data-v1/manifest.json'
EVIDENCE = ROOT / 'runtime/model-comparison/exp0074/bc-preparation-v1'
OFFICIAL = ROOT / 'weights/yolo26m.pt'
OFFICIAL_SHA = '401cea9ab23ad19246ff7744859816bc599f350e93c9dd30367b6f0a0745d0b7'
INITIAL = ROOT / 'outputs/model-comparison/exp0068/queued/train5/47adf16ca4fa4145b50e0ee150106c38/initial.pt'
INITIAL_SHA = '436426a56cb2699c7be3391b3dc1e4c06b268b357b330e3b1cf13409ee01ef53'
QUEUE = Path('/home/jhc7484/dev/sceneguard-orca-lab/runtime/orca-lab/gpu-queue')
FUTURE_OUTPUT = ROOT / 'outputs/model-comparison/exp0074/queued'
SETTINGS = dict(epochs=5, batch=2, imgsz=640, seed=68, optimizer='AdamW', lr=1e-4,
                weight_decay=.0005, betas=[.9, .999], eps=1e-8, workers=0,
                amp=False, augmentation=False, ema=False, dtype='float32',
                accumulation=1, warmup_steps=0, loss_box=7.5, loss_cls=.5,
                loss_dfl=1.5, gradient_clip_norm=10.0, full_fine_tune=True,
                checkpoint_selection='last_epoch5', o2m_initial=.8, o2m_final=.1,
                criterion_update='after_epochs_1_2_3_4', shuffle='random.Random(68+epoch)')
SOURCE_NAMES = ('scripts/prepare_person_bn_comparison.py', 'scripts/train_person_detector.py',
                'scripts/exp0066_yolo.py', 'scripts/evaluate_person_detector_pair.py',
                'orchestration/person_bn_comparison_command.py', 'orchestration/queue.py',
                'orchestration/action_training_command.py', 'orchestration/model_comparison_command.py',
                'scripts/prepare_model_comparison.py')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def bound(path, expected=None):
    path = Path(path).resolve(strict=True)
    actual = sha(path)
    if expected is not None and actual != expected:
        raise ValueError('File bytes changed: ' + str(path))
    return dict(path=str(path), sha256=actual)


def atomic_write(path, writer):
    """Publish a complete fsynced file without replacing an earlier artifact."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            writer(stream)
            stream.flush()
            os.fsync(stream.fileno())
        # Same-filesystem hard link atomically publishes and refuses overwrite.
        os.link(name, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        Path(name).unlink(missing_ok=True)


def write_json(path, value):
    payload = (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False,
                          allow_nan=False) + '\n').encode()
    atomic_write(path, lambda stream: stream.write(payload))


def source_bindings():
    return {name: sha(ROOT / name) for name in SOURCE_NAMES}


def gt_id(frame, index):
    box = frame['confirmed_person_boxes'][index]
    # Content-derived fallback remains auditable, and does not claim identity tracking.
    return str(box.get('id', box.get('box_id', 'xyxy-' + digest(box['xyxy'])[:20])))


def dataset_contract(path, expected_counts=None):
    path = Path(path).resolve(strict=True)
    manifest = read(path)
    if (manifest.get('person_boxes_human_verified') is not True
            or manifest.get('protected_school_or_test_used') is not False):
        raise ValueError('Explicit confirmed-person and protected-data exclusion declarations required')
    frames = manifest['frames']
    seen, pixels, groups, reservations, sources = set(), {}, {}, {}, {}
    counts, boxes = Counter(), Counter()
    records = []
    for row in frames:
        fid, split = row['frame_id'], row['split']
        if not isinstance(fid, str) or not fid or fid in seen or split not in ('train', 'development'):
            raise ValueError('Unique stable frame_id and train/development split required')
        seen.add(fid)
        if (row.get('person_completeness_verified') is not True
                or not isinstance(row.get('source_sha256'), str)
                or not re.fullmatch('[0-9a-f]{64}', row['source_sha256'])):
            raise ValueError('Per-frame confirmed person completeness and valid source SHA-256 required')
        sources.setdefault(row['source_sha256'], set()).add(split)
        if not row.get('event_group') or not row.get('capture_reservation'):
            raise ValueError('Explicit event group and capture reservation required')
        for key, table in (('event_group', groups), ('capture_reservation', reservations)):
            table.setdefault(digest(row[key]), set()).add(split)
        width, height = row['source_size']
        if (type(width) is not int or type(height) is not int or min(width, height) <= 0
                or type(row['source_pts']) not in (int, float) or not math.isfinite(row['source_pts'])):
            raise ValueError('Finite source PTS and positive integer source dimensions required')
        image = Path(row['image'])
        if not image.is_absolute():
            image = path.parent / image
        binding = bound(image, row['image_sha256'])
        # Duplicate pixels cannot silently cross the train/development boundary.
        previous = pixels.setdefault(binding['sha256'], split)
        if previous != split:
            raise ValueError('Image pixels cross train/development split')
        ids = set()
        for i, box in enumerate(row['confirmed_person_boxes']):
            xyxy = box['xyxy']
            if (len(xyxy) != 4 or any(type(x) not in (int, float) or not math.isfinite(x) for x in xyxy)
                    or not (0 <= xyxy[0] < xyxy[2] <= width and 0 <= xyxy[1] < xyxy[3] <= height)):
                raise ValueError('Confirmed boxes must be finite original-pixel xyxy within source')
            identity = gt_id(row, i)
            if identity in ids:
                raise ValueError('Duplicate per-frame GT id')
            ids.add(identity)
        counts[split] += 1
        boxes[split] += len(row['confirmed_person_boxes'])
        records.append(dict(frame_id=fid, split=split, image=binding, source_size=[width, height],
                            source_sha256=row['source_sha256'], person_completeness_verified=True,
                            source_pts=row['source_pts'], event_group=row['event_group'],
                            capture_reservation=row['capture_reservation'],
                            gt=[dict(gt_id=gt_id(row, i), xyxy=b['xyxy'])
                                for i, b in enumerate(row['confirmed_person_boxes'])]))
    if any(len(splits) > 1 for splits in list(groups.values()) + list(reservations.values()) + list(sources.values())):
        raise ValueError('Source/event/capture reservation crosses train/development split')
    if set(counts) != {'train', 'development'}:
        raise ValueError('Nonempty train and development splits required')
    if expected_counts is not None and dict(counts) != expected_counts:
        raise ValueError('Exact frozen frame counts required: ' + str(expected_counts))
    return dict(manifest=bound(path), counts=dict(counts), box_counts=dict(boxes), frames=records,
                records_sha256=digest(records), action_ground_truth_used=False,
                independent_generalization=False)


def epoch_orders(frame_ids, epochs=5):
    orders = []
    for epoch in range(1, epochs + 1):
        order = list(frame_ids)
        random.Random(68 + epoch).shuffle(order)
        orders.append(dict(epoch=epoch, frame_ids=order, order_sha256=digest(order),
                           batches=[order[i:i + 2] for i in range(0, len(order), 2)],
                           o2m_gain=max(1 - (epoch - 1) / 4, 0) * .7 + .1))
    return orders


def make_plan(manifest=DATASET, initialization=INITIAL):
    contract = dataset_contract(manifest)
    initialization = Path(initialization).resolve(strict=True)
    if initialization == INITIAL.resolve():
        initial = bound(initialization, INITIAL_SHA)
        initial['kind'] = 'exp0068_epoch0_exact_person_slice'
    elif initialization == OFFICIAL.resolve():
        initial = bound(initialization, OFFICIAL_SHA)
        initial['kind'] = 'official80_exact_person_slice_at_load'
    else:
        raise ValueError('Only pinned EXP68 initial.pt or official YOLO26m is allowed; never trained last')
    orders = epoch_orders([r['frame_id'] for r in contract['frames'] if r['split'] == 'train'])
    spec_path = ROOT / 'runtime/model-comparison/exp0066/yolo26-specs-v1/yolo26m.json'
    spec = read(spec_path)
    if spec['bindings'].get(str(OFFICIAL)) != OFFICIAL_SHA or spec['ultralytics_version'] != '8.4.192':
        raise ValueError('Pinned official model/environment specification required')
    for filename, expected in spec['bindings'].items():
        bound(filename, expected)
    return dict(schema_version=1, experiment_id='EXP-0074', status='preparation_only_no_training',
                dataset=contract, initialization=initial, official_baseline=bound(OFFICIAL, OFFICIAL_SHA),
                model_specification=bound(spec_path), environment=bound(spec['environment_path']),
                settings=copy.deepcopy(SETTINGS), settings_sha256=digest(SETTINGS),
                epoch_orders=orders, expected_optimizer_steps=sum(len(e['batches']) for e in orders),
                variants=dict(A=dict(kind='exact_official_person_slice_no_fitting', training=False),
                              B=dict(kind='full_fine_tune', bn_running_stats='updated', bn_affine='trainable'),
                              C=dict(kind='full_fine_tune', bn_running_stats='fixed', bn_affine='trainable')),
                sources=source_bindings(), evaluation=dict(person_confidence=.5, iou=.5,
                    retained_confidence=.05, max_det=300, nms=False, split='development',
                    gt_key=['frame_id', 'gt_id'], event_key='event_group', selection='fixed_epoch5'),
                execution_authorized=False, gpu_used=False, optimizer_steps_executed=0,
                gaps=['New independent execution release is required before any queue submission',
                      'Preparation does not produce predictions; B/C predictions, optimizer updates and real epoch checkpoints remain unmeasured',
                      'Protected-set membership relies on coordinator dataset provenance; declarations alone do not prove it'])


def bn_snapshot(model):
    import torch
    return {name + '.' + key: getattr(module, key).detach().cpu().clone()
            for name, module in model.named_modules()
            if isinstance(module, torch.nn.modules.batchnorm._BatchNorm)
            for key in ('running_mean', 'running_var', 'num_batches_tracked')
            if getattr(module, key) is not None}


def set_training_mode(model, variant):
    """Reapply after EVERY model.train(): freeze C buffers, retain all affine gradients."""
    import torch
    if variant not in ('B', 'C'):
        raise ValueError('Only B/C are trainable variants')
    model.train()
    for parameter in model.parameters():
        parameter.requires_grad_(True)
    count = 0
    for module in model.modules():
        if isinstance(module, torch.nn.modules.batchnorm._BatchNorm):
            if not module.track_running_stats or module.running_mean is None:
                raise ValueError('Tracked BN running buffers required')
            module.train(variant == 'B')
            count += 1
    if not count:
        raise ValueError('Expected BatchNorm modules')
    return count


def assert_bn_fixed(model, initial):
    import torch
    actual = bn_snapshot(model)
    if set(actual) != set(initial) or any(not torch.equal(value, actual[key]) for key, value in initial.items()):
        raise ValueError('C BatchNorm running buffers changed')


def state_hashes(model):
    result = {}
    for key, tensor in model.state_dict().items():
        tensor = tensor.detach().cpu().contiguous()
        result[key] = digest(dict(dtype=str(tensor.dtype), shape=list(tensor.shape),
                                 bytes_sha256=hashlib.sha256(tensor.numpy().tobytes()).hexdigest()))
    return result


def load_initial(initialization, official_path=OFFICIAL):
    """Load local trusted bytes only and prove EXP68 epoch0 equals official exact slice."""
    import torch
    from scripts.train_person_detector import adapt_person
    from ultralytics import YOLO
    bound(official_path, OFFICIAL_SHA)
    official = YOLO(str(official_path), task='detect').model.cpu().float()
    official.end2end = True
    adapt_person(official)
    path = Path(initialization).resolve()
    if path == OFFICIAL.resolve():
        return official, dict(exact_official_person_state=True, initialization_sha256=OFFICIAL_SHA)
    if path != INITIAL.resolve():
        raise ValueError('Unapproved initialization path')
    bound(path, INITIAL_SHA)
    checkpoint = torch.load(path, map_location='cpu', weights_only=False)
    if checkpoint['epoch'] != 0 or checkpoint['optimizer_steps'] != 0 or checkpoint['optimizer']['state']:
        raise ValueError('Untrained epoch0 initialization required')
    model = checkpoint['model'].cpu().float()
    expected, actual = official.state_dict(), model.state_dict()
    if (set(expected) != set(actual) or set(actual) != set(checkpoint['state_dict'])
            or any(not torch.equal(actual[k], expected[k])
                   or not torch.equal(actual[k], checkpoint['state_dict'][k]) for k in actual)):
        raise ValueError('EXP68 initial state is not the exact official person slice')
    model.end2end = True
    return model, dict(exact_official_person_state=True, initialization_sha256=INITIAL_SHA,
                       state_sha256=digest(state_hashes(model)))


def verify_yolo_cpu(directory, initialization=INITIAL):
    """Forward-only real architecture check; synthetic inputs, no loss/backward/optimizer."""
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    from scripts.exp0066_yolo import configure_offline
    configure_offline(Path(directory))
    import torch
    import ultralytics
    if ultralytics.__version__ != '8.4.192':
        raise ValueError('Pinned Ultralytics 8.4.192 required')
    torch.set_num_threads(4)
    torch.manual_seed(68)
    model, initialization_report = load_initial(initialization)
    input_tensor = torch.linspace(0, 1, 2 * 3 * 640 * 640).reshape(2, 3, 640, 640)
    initial_state = copy.deepcopy(model.state_dict())
    reports = {}
    for variant in ('B', 'C'):
        model.load_state_dict(initial_state)
        before = bn_snapshot(model)
        for _ in range(2):
            # Exercise an outer train() reset before reapplying the BN policy.
            model.train()
            count = set_training_mode(model, variant)
            with torch.no_grad():
                output = model(input_tensor)
            if not isinstance(output, dict) or set(output) != {'one2many', 'one2one'}:
                raise ValueError('Native unfused training dual-head output required')
            if variant == 'C':
                assert_bn_fixed(model, before)
        after = bn_snapshot(model)
        changed = [key for key in before if not torch.equal(before[key], after[key])]
        parameters_equal = all(torch.equal(parameter, initial_state[key]) for key, parameter in model.named_parameters())
        if not parameters_equal or not all(p.requires_grad for p in model.parameters()):
            raise ValueError('Forward-only verification must preserve all trainable weights')
        if variant == 'B' and not changed:
            raise ValueError('B must update BN running statistics')
        reports[variant] = dict(bn_modules=count, changed_bn_buffers=changed,
                               before_bn_sha256=digest({k: hashlib.sha256(v.numpy().tobytes()).hexdigest()
                                                        for k, v in before.items()}),
                               after_bn_sha256=digest({k: hashlib.sha256(v.numpy().tobytes()).hexdigest()
                                                       for k, v in after.items()}),
                               trainable_parameter_tensors=sum(1 for _ in model.parameters()),
                               weights_unchanged=True, all_parameters_trainable=True,
                               forward_passes=2, repeated_train_reset=True)
    return dict(status='actual_yolo26m_cpu_forward_only_verified', input='synthetic_linspace_batch2_640',
                initialization=initialization_report, variants=reports, torch=torch.__version__,
                ultralytics=ultralytics.__version__, device='cpu', optimizer_steps=0,
                sources=source_bindings(),
                backward_calls=0, trained_checkpoints_produced=0,
                limitation='Verifies BN state behavior; does not measure detection performance or training convergence')


def save_epoch_checkpoint(path, model, optimizer_state, epoch, steps, provenance, *, synthetic=False):
    """Epoch artifacts are atomic, immutable, and carry exact data/config/weight hashes."""
    import torch
    # The future caller checks the optimizer too; this check covers model buffers.
    if any(not torch.isfinite(value).all() for value in model.state_dict().values()):
        raise ValueError('Nonfinite checkpoint state')
    weights = state_hashes(model)
    payload = dict(model=copy.deepcopy(model).cpu(),
                   state_dict={k: v.detach().cpu().clone() for k, v in model.state_dict().items()},
                   optimizer=copy.deepcopy(optimizer_state), epoch=epoch, optimizer_steps=steps,
                   settings=SETTINGS, provenance=copy.deepcopy(provenance),
                   tensor_sha256=weights, state_sha256=digest(weights),
                   evidence_kind='synthetic_checkpoint_simulation' if synthetic else 'actual_training_checkpoint',
                   ema=None)
    atomic_write(path, lambda stream: torch.save(payload, stream))
    receipt = dict(checkpoint=bound(path), epoch=epoch, optimizer_steps=steps,
                   state_sha256=payload['state_sha256'], provenance=provenance,
                   evidence_kind=payload['evidence_kind'])
    write_json(str(path) + '.json', receipt)
    return receipt


def compare_predictions(manifest, predictions):
    """Stable development per-GT transitions and per-frame/event FP counts for A/B/C."""
    from scripts.evaluate_person_detector_pair import match, validate_predictions
    frames = [f for f in manifest['frames'] if f['split'] == 'development']
    if set(predictions) != {'A', 'B', 'C'} or not frames:
        raise ValueError('Complete A/B/C development predictions required')
    indexed = {variant: validate_predictions(rows, frames) for variant, rows in predictions.items()}
    records, groups = [], {}
    totals = {variant: Counter() for variant in predictions}
    transitions = {variant: Counter() for variant in ('B', 'C')}
    for frame in frames:
        fid = frame['frame_id']
        gt = [b['xyxy'] for b in frame['confirmed_person_boxes']]
        results = {v: match(gt, rows[fid]['boxes'], rows[fid]['person_scores']) for v, rows in indexed.items()}
        hits = {v: {m['gt_index'] for m in r['matches']} for v, r in results.items()}
        paired = []
        group = str(frame['event_group'])
        groups.setdefault(group, {v: Counter() for v in predictions})
        for variant, result in results.items():
            counts = {k: result[k] for k in ('tp', 'fp', 'fn')}
            totals[variant].update(counts)
            groups[group][variant].update(counts)
        for i in range(len(gt)):
            states = {}
            for variant in ('B', 'C'):
                state = ('retained' if i in hits[variant] else 'new_miss') if i in hits['A'] else (
                    'recovered' if i in hits[variant] else 'persistent_miss')
                transitions[variant][state] += 1
                states[variant] = state
            paired.append(dict(gt_id=gt_id(frame, i), gt_index=i, against_A=states,
                               detected={v: i in h for v, h in hits.items()}))
        records.append(dict(frame_id=fid, image_sha256=frame['image_sha256'], source_pts=frame['source_pts'],
                            event_group=frame['event_group'], variants=results, paired_gt=paired))
    return dict(frames=records, totals=totals, event_counts=groups, paired_gt_counts=transitions,
                confidence=.5, iou=.5, matching='deterministic_maximum_cardinality_per_frame',
                fp_semantics='unmatched predictions counted per frame/event; no invented cross-model FP identity',
                action_metrics=None, independent_generalization=False)


def validate_release(config, plan):
    """Shared enqueue/runner release validation; read-only and CPU dependency-free."""
    if not isinstance(config.get('authorization'), dict):
        raise ValueError('Preparation does not provide an execution authorization')
    authorization = read(bound(config['authorization']['path'], config['authorization']['sha256'])['path'])
    required = ('training_authorized', 'independent_review_passed', 'root_go', 'explicit_gpu_go')
    if (any(authorization.get(key) is not True for key in required)
            or authorization.get('status') != 'authorized_exp0074_bn_comparison_training'
            or authorization.get('plan') != config['plan']
            or authorization.get('context') != config['context']
            or authorization.get('variant') != config['variant']
            or authorization.get('sources') != source_bindings()
            or not str(authorization.get('root_go_message', '')).startswith('msg_')):
        raise ValueError('New independent release and explicit coordinator GPU GO required')
    # The release and grant must bind the exact candidate; old EXP68 grants fail.
    review_binding, grant_binding = authorization['independent_review'], authorization['root_grant']
    review = read(bound(review_binding['path'], review_binding['sha256'])['path'])
    grant = read(bound(grant_binding['path'], grant_binding['sha256'])['path'])
    for document, status in ((review, 'accepted_exp0074_bn_training_release'),
                             (grant, 'root_authorized_exp0074_bn_training')):
        if document.get('status') != status or any(document.get(k) != authorization.get(k)
                for k in ('plan', 'context', 'variant', 'sources', 'code_sha')):
            raise ValueError('Independent review/root grant differs from execution release')
    if grant.get('independent_review') != review_binding or grant.get('root_go_message') != authorization['root_go_message']:
        raise ValueError('Actual release/grant binding required')
    import subprocess
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if authorization['code_sha'] != head:
        raise ValueError('Reviewed committed HEAD changed')
    for name, expected in source_bindings().items():
        if hashlib.sha256(subprocess.check_output(['git', 'show', head + ':' + name], cwd=ROOT)).hexdigest() != expected:
            raise ValueError('Training source is not the reviewed committed byte version')
    return authorization


def future_runner_guard(args):
    """Fail closed before model/CUDA imports; requires future reviewed queue integration."""
    import fcntl
    from orchestration.queue import digest as queue_digest, process_state
    from orchestration.action_training_command import resources, validate_assignment
    # No preparation CLI can grant execution.
    config_path = QUEUE / 'attempts' / args.queue_attempt / 'person-bn-comparison-config.json'
    if (not re.fullmatch('[0-9a-f]{32}', args.queue_attempt)
            or Path(args.queue_config) != config_path or sha(config_path) != args.queue_config_sha256):
        raise ValueError('Exact canonical attempt snapshot required')
    config = read(config_path)
    from orchestration import person_bn_comparison_command as command
    if config['variant'] not in ('B', 'C') or config['experiment_id'] != 'EXP-0074':
        raise ValueError('Exact EXP74 B/C variant required')
    plan_path = Path(config['plan']['path'])
    bound(plan_path, config['plan']['sha256'])
    plan = read(plan_path)
    if plan != make_plan(plan['dataset']['manifest']['path'], plan['initialization']['path']):
        raise ValueError('Plan, inputs, settings or source hashes changed')
    authorization = command.validate(config, plan, QUEUE)['authorization']
    head = authorization['code_sha']
    fd = int(os.environ['SCENEGUARD_GPU_LOCK_FD'])
    actual, held = (QUEUE / 'gpu.lock').stat(), os.fstat(fd)
    if (actual.st_dev, actual.st_ino) != (held.st_dev, held.st_ino):
        raise ValueError('Wrong canonical reservation FD')
    with (QUEUE / 'gpu.lock').open('r+') as probe:
        try:
            fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            pass
        else:
            raise ValueError('Canonical GPU reservation is not held')
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    with sqlite3.connect('file:' + str(QUEUE / 'queue.sqlite3') + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        row = db.execute('SELECT j.*, a.status AS attempt_status,a.supervisor_pid,a.supervisor_identity '
                         'FROM jobs j JOIN attempts a USING(job_id) WHERE a.attempt_id=?',
                         (args.queue_attempt,)).fetchone()
    if (row is None or row['command'] != 'person-bn-comparison-train'
            or row['status'] != 'running' or row['attempt_status'] != 'running'
            or json.loads(row['config_json']) != config or row['config_hash'] != queue_digest(config)
            or json.loads(row['input_json']) != plan or row['input_hash'] != queue_digest(plan)
            or row['source_hash'] != queue_digest(source_bindings()) or row['code_sha'] != head
            or row['job_key'] != command.job_key(config)
            or any(row[k] != v for k, v in config['context'].items())
            or process_state(row['supervisor_pid'], row['supervisor_identity']) != 'live'
            or os.environ.get('CUDA_VISIBLE_DEVICES') != '0'
            or args.output.resolve() != FUTURE_OUTPUT / config['variant'] / args.queue_attempt):
        raise ValueError('Live canonical EXP74 queue attempt required')
    validate_assignment(config['context'])
    resources()
    return config, plan


def execute_future(args):
    """Executable future loop.  Never called by preparation or verification."""
    config, plan = future_runner_guard(args)
    directory = args.output
    directory.mkdir(parents=True, exist_ok=False)
    from scripts.exp0066_yolo import configure_offline
    configure_offline(directory)
    os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'
    import numpy as np
    import torch
    import ultralytics
    from scripts.train_person_detector import batch_targets, finite_state, loss_items
    if ultralytics.__version__ != '8.4.192':
        raise ValueError('Pinned Ultralytics required')
    torch.set_num_threads(4)
    random.seed(68)
    np.random.seed(68)
    torch.manual_seed(68)
    torch.cuda.manual_seed_all(68)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    model, initialization = load_initial(plan['initialization']['path'])
    model = model.to('cuda:0').float()
    model.args = SimpleNamespace(box=7.5, cls=.5, dfl=1.5, epochs=5)
    # Never inherit a criterion/optimizer schedule from another experiment.
    model.criterion = model.init_criterion()
    fixed = bn_snapshot(model)
    set_training_mode(model, config['variant'])
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, betas=(.9, .999), eps=1e-8, weight_decay=.0005)
    rows = read(plan['dataset']['manifest']['path'])['frames']
    by_id = {r['frame_id']: r for r in rows if r['split'] == 'train'}
    folder = Path(plan['dataset']['manifest']['path']).parent
    provenance = dict(plan=config['plan'], manifest=plan['dataset']['manifest'],
                      initialization=plan['initialization'], initialization_verification=initialization,
                      settings_sha256=plan['settings_sha256'], sources=plan['sources'],
                      variant=config['variant'], context=config['context'])
    write_json(directory / 'run-config.json', dict(plan=plan, config=config, provenance=provenance))
    steps, epochs = 0, []
    with (directory / 'optimizer-steps.jsonl').open('x', encoding='utf-8') as log:
        for order in plan['epoch_orders']:
            set_training_mode(model, config['variant'])
            if not math.isclose(model.criterion.o2m, order['o2m_gain'], abs_tol=1e-12):
                raise ValueError('Historical criterion.update schedule differs')
            seen = []
            for frame_ids in order['batches']:
                selected = [by_id[fid] for fid in frame_ids]
                batch = batch_targets(selected, folder, 'cuda:0')
                optimizer.zero_grad(set_to_none=True)
                loss, items = model(batch)
                scalar = loss.sum()
                if not torch.isfinite(scalar):
                    raise ValueError('Nonfinite loss')
                scalar.backward()
                gradients = [p.grad for p in model.parameters() if p.grad is not None]
                if not gradients or any(not torch.isfinite(g).all() for g in gradients):
                    raise ValueError('Missing/nonfinite gradients')
                norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 10., error_if_nonfinite=True)
                optimizer.step()
                steps += 1
                seen.extend(frame_ids)
                if config['variant'] == 'C':
                    assert_bn_fixed(model, fixed)
                log.write(json.dumps(dict(epoch=order['epoch'], step=steps, frame_ids=frame_ids,
                    loss=scalar.item(), native_loss_items=loss_items(items), grad_norm_before_clip=float(norm))) + '\n')
                log.flush()
            if seen != order['frame_ids']:
                raise ValueError('Epoch coverage/order differs')
            finite_state(model, optimizer)
            epoch = order['epoch']
            # Save the next-epoch criterion state; log the gains actually used separately.
            gains = dict(o2m=model.criterion.o2m, o2o=model.criterion.o2o)
            if epoch < 5:
                model.criterion.update()
            receipt = save_epoch_checkpoint(directory / ('epoch-%02d.pt' % epoch), model,
                optimizer.state_dict(), epoch, steps, dict(provenance, order_sha256=order['order_sha256'],
                                                          loss_gains_used=gains))
            epochs.append(receipt)
    if steps != plan['expected_optimizer_steps']:
        raise ValueError('Optimizer step coverage differs')
    if plan != make_plan(plan['dataset']['manifest']['path'], plan['initialization']['path']):
        raise ValueError('Inputs changed during execution')
    result = dict(status='actual_exp0074_training_complete', variant=config['variant'], epochs=epochs,
                  optimizer_steps=steps, selected_checkpoint=epochs[-1]['checkpoint'],
                  provenance=provenance, predictions_pending=True)
    write_json(directory / 'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prepare = sub.add_parser('prepare')
    prepare.add_argument('--manifest', type=Path, default=DATASET)
    prepare.add_argument('--initialization', type=Path, default=INITIAL)
    prepare.add_argument('--output', type=Path, default=EVIDENCE / 'plan.json')
    verify = sub.add_parser('verify-yolo-cpu')
    verify.add_argument('--initialization', type=Path, default=INITIAL)
    verify.add_argument('--output', type=Path, default=EVIDENCE / 'yolo-cpu-verification.json')
    train = sub.add_parser('future-train')
    train.add_argument('--queue-config', required=True)
    train.add_argument('--queue-config-sha256', required=True)
    train.add_argument('--queue-attempt', required=True)
    train.add_argument('--output', type=Path, required=True)
    compare = sub.add_parser('compare')
    compare.add_argument('--manifest', type=Path, required=True)
    for variant in ('A', 'B', 'C'):
        compare.add_argument('--' + variant, type=Path, required=True)
    compare.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        result = make_plan(args.manifest, args.initialization)
    elif args.command == 'verify-yolo-cpu':
        result = verify_yolo_cpu(args.output.parent, args.initialization)
    elif args.command == 'compare':
        dataset_contract(args.manifest)
        result = compare_predictions(read(args.manifest), {v: [json.loads(line) for line in getattr(args, v).read_text().splitlines()]
                                                           for v in ('A', 'B', 'C')})
        result['inputs'] = {name: bound(getattr(args, name)) for name in ('manifest', 'A', 'B', 'C')}
    else:
        execute_future(args)
        return
    write_json(args.output, result)
    print(json.dumps(dict(status=result.get('status', 'comparison_complete'), output=str(args.output))))


if __name__ == '__main__':
    main()
