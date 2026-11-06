"""EXP-0063 one-configuration training through the existing canonical GPU queue.

This module does not initialize/migrate the real queue or execute a GPU job on import.
Authorization is a local reviewed snapshot; Orca is queried again at execution time.
"""
import argparse
import ast
import copy
import datetime as dt
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import subprocess

from orchestration.queue import digest, process_state

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = Path('/home/jhc7484/dev/sceneguard-orca-lab/runtime/orca-lab/gpu-queue')
INTERPRETER = ROOT / '.venv-cv-batch02/bin/python'
OUTPUT = ROOT / 'outputs/action-recognition/exp0063/queued-training'
FROZEN_SEQUENTIAL_SHA = '080bf01a7cd5c686e73cdd744b2087f46c3631ae73df9371e67b501f2c07633c'
FROZEN_SPLIT_SHA = 'bfb0f9fcd570794036cc6d2eaad46f988679b612996e21282a34821203ad5499'
EXECUTION_REVISION = 'amp-overflow-v2'
RECOVERY_ATTEMPT = '058639f80f394a71b345eb4eae5ceacb'
OPTIMIZER_HELPERS = {'install_actual_step_counter','amp_optimizer_update','ensure_finite_training_state'}
PRODUCER_COMMIT = '99d18b3e1e899ef17380ca3f7e87de290f1e3859'
PRODUCER_TRAINER_SHA = '2a0d01de3ec9b872c99761472b0626ba1e5f41a5b9f2c9be4eef4fe5626ff350'
FILE_KEYS = {'manifest', 'baseline_lock', 'split_manifest', 'config', 'prepared', 'review_release', 'weights'}


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def trainer():
    spec = importlib.util.spec_from_file_location('exp0063_trainer', ROOT/'scripts/train_action_recognizer.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sources(config=None):
    paths = ('orchestration/queue.py', 'orchestration/mock_job.py',
             'orchestration/action_training_command.py', 'scripts/train_action_recognizer.py',
             'tests/test_action_recognizer.py', 'tests_orca/test_action_training.py',
             'scripts/prepare_action_pixels_parallel.py', 'tests_orca/test_action_training_provenance.py')
    return {name:file_hash(ROOT/name) for name in paths}


def checked_file(entry):
    path = Path(entry['path'])
    if not path.is_absolute() or path.is_symlink() or file_hash(path) != entry['sha256']:
        raise ValueError('Immutable absolute local input required: '+str(path))
    return path


def input_contract(config):
    """Verify selected real sources/pixels without reading test pixels during smoke."""
    expected = FILE_KEYS | ({'preparation_evidence'} if config['stage'] == 'train' else set())
    if config['stage'] not in ('smoke','train') or set(config['files']) != expected:
        raise ValueError('Exact stage-specific action training file bindings required')
    paths = {k:checked_file(v) for k,v in config['files'].items()}
    if config['files']['weights']['sha256'] != 'b3b3357ead25631ec9c57362ff2128a92d0427e01e2cd184951a44380c3f2e9d':
        raise ValueError('Exact official R3D-18 pretrained weight hash required')
    if file_hash(paths['split_manifest']) != FROZEN_SPLIT_SHA:
        raise ValueError('Frozen source/group/split v3 required')
    module = trainer()
    settings = read(paths['config'])
    module.validate_config(settings)
    manifest, baseline, split = (read(paths[k]) for k in ('manifest','baseline_lock','split_manifest'))
    if (len(baseline.get('regression_only_videos', [])) != 45
            or len({r['sha256'] for r in baseline['regression_only_videos']}) != 45):
        raise ValueError('All45 regression hashes must remain forbidden')
    if manifest.get('config_sha256') != config['files']['config']['sha256']:
        raise ValueError('Manifest preprocessing config binding differs')
    if manifest.get('baseline_lock_sha256') != config['files']['baseline_lock']['sha256']:
        raise ValueError('Manifest baseline binding differs')
    if manifest.get('source_split_sha256') != FROZEN_SPLIT_SHA:
        raise ValueError('Manifest split binding differs')
    counts = module.validate_manifest(manifest, baseline, settings['frames'], split)
    release = module.validate_release(paths['manifest'], paths['split_manifest'], paths['review_release'],
                                      config['files']['review_release']['sha256'])
    selected = module.partition_rows(manifest, config['stage'])
    provenance = None
    original_sources = {}
    if config['stage'] == 'train':
        original_sources, provenance = preparation_evidence(config, paths, manifest, counts, release)
    annotation_hashes = {}
    for row in selected:
        path = row['source_path']
        if config['stage'] == 'smoke' and path not in original_sources:
            original_sources[path] = file_hash(path)
        if original_sources[path] != row['source_sha256']:
            raise ValueError('Source video changed')
        if not row.get('label_path') or not row.get('label_sha256'):
            raise ValueError('Official annotation path/hash required')
        label_path = row['label_path']
        if label_path not in annotation_hashes:
            annotation_hashes[label_path] = file_hash(label_path)
        if annotation_hashes[label_path] != row['label_sha256']:
            raise ValueError('Official annotation changed')
        original_sources[label_path] = annotation_hashes[label_path]
    arrays = module.prepared_entries(paths['prepared'].parent, paths['manifest'], paths['config'], selected)
    prepared = read(paths['prepared'])
    result = dict(files={k:v['sha256'] for k,v in config['files'].items()}, sources=original_sources,
                  pixels={key:prepared['clips'][key]['sha256'] for key in arrays},
                  review_snapshot_sha256=release['review_snapshot']['sha256'])
    if provenance is not None:
        result['preparation_provenance'] = provenance
    if 'execution_revision' in config:
        if config['execution_revision'] != EXECUTION_REVISION:
            raise ValueError('Only the explicitly reviewed numerical recovery revision is allowed')
        result['execution_revision'] = config['execution_revision']
    return result


def evidence_binding(entry):
    if (not isinstance(entry, dict) or set(entry) != {'path','sha256'}
            or not isinstance(entry['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', entry['sha256'])):
        raise ValueError('Exact preparation artifact path/hash binding required')
    return checked_file(entry)


def preprocessing_compatibility(producer_sha):
    """Prove immutable old pixels are compatible with an optimization-only core revision."""
    if producer_sha != PRODUCER_TRAINER_SHA:
        raise ValueError('Pinned historical producer trainer required')
    old = subprocess.check_output(['git','show',PRODUCER_COMMIT+':scripts/train_action_recognizer.py'],cwd=ROOT)
    if hashlib.sha256(old).hexdigest() != PRODUCER_TRAINER_SHA:
        raise ValueError('Historical Git trainer anchor differs')
    current = (ROOT/'scripts/train_action_recognizer.py').read_bytes()
    proof = compare_preprocessing_sources(old.decode('utf-8'),current.decode('utf-8'))
    return dict(producer_commit=PRODUCER_COMMIT,producer_trainer_sha256=producer_sha,
                execution_trainer_sha256=hashlib.sha256(current).hexdigest(),**proof)


def compare_preprocessing_sources(old, current):
    """Pure source comparison, never execute historical code or load a model."""
    left,right = ast.parse(old),ast.parse(current)
    def functions(tree):
        rows = [n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
        result = {n.name:n for n in rows}
        if len(rows) != len(result):
            raise ValueError('Duplicate/shadowed trainer helper definitions')
        return result
    before,after = functions(left),functions(right)
    if 'main' not in before or not set(before).issubset(after):
        raise ValueError('Missing historical preprocessing helper')
    checked = {}
    for name,node in before.items():
        if name == 'main':continue
        old_text,new_text = ast.get_source_segment(old,node),ast.get_source_segment(current,after[name])
        if old_text != new_text or ast.dump(node,include_attributes=False) != ast.dump(after[name],include_attributes=False):
            raise ValueError('Preprocessing/helper source changed: '+name)
        checked[name] = hashlib.sha256(old_text.encode()).hexdigest()
    added = set(after)-set(before)
    if not added.issubset(OPTIMIZER_HELPERS):
        raise ValueError('Unreviewed/shadowing optimization helper name')
    for name in added:
        node = after[name]
        defaults = [*node.args.defaults,*[n for n in node.args.kw_defaults if n is not None]]
        args = [*node.args.posonlyargs,*node.args.args,*node.args.kwonlyargs]
        if node.args.vararg:args.append(node.args.vararg)
        if node.args.kwarg:args.append(node.args.kwarg)
        annotations = [a.annotation for a in args if a.annotation is not None]
        if node.returns is not None:annotations.append(node.returns)
        if (node.decorator_list or getattr(node,'type_params',[]) or any(not isinstance(n,ast.Constant) for n in defaults)
                or any(not isinstance(n,(ast.Name,ast.Constant)) for n in annotations)):
            raise ValueError('New optimization helper has executable definition side effects')
    def globals_ast(tree):
        return [n for n in tree.body if not isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))
                and not (isinstance(n,ast.Expr) and isinstance(n.value,ast.Constant) and isinstance(n.value.value,str))]
    old_globals,new_globals = globals_ast(left),globals_ast(right)
    globals_text = ast.dump(ast.Module(body=old_globals,type_ignores=[]),include_attributes=False)
    if globals_text != ast.dump(ast.Module(body=new_globals,type_ignores=[]),include_attributes=False):
        raise ValueError('Preprocessing imports/globals/dependencies changed')
    def prefix(node):
        for index,statement in enumerate(node.body):
            if isinstance(statement,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='optimizer' for t in statement.targets):
                return ast.dump(ast.Module(body=node.body[:index+1],type_ignores=[]),include_attributes=False)
        raise ValueError('Protected model/preprocessing optimizer boundary is missing')
    def definition_metadata(node):
        clone = copy.copy(node)
        clone.body = []
        return ast.dump(clone,include_attributes=False)
    if definition_metadata(before['main']) != definition_metadata(after['main']):
        raise ValueError('Main preprocessing entrypoint definition metadata changed')
    old_prefix,new_prefix = prefix(before['main']),prefix(after['main'])
    if old_prefix != new_prefix:
        raise ValueError('Model/preprocessing/normalization prelude changed')
    return dict(checked_helpers_sha256=checked,imports_globals_ast_sha256=hashlib.sha256(globals_text.encode()).hexdigest(),
                main_prefix_through_optimizer_ast_sha256=hashlib.sha256(old_prefix.encode()).hexdigest(),
                compatibility='unchanged_pixel_preprocessing_and_model_prelude_optimization_loop_revision_only')


def validate_recovery_parent(config):
    """Observe the fixed failed parent; never retry, mutate, or reuse its output."""
    with sqlite3.connect('file:'+str(RUNTIME/'queue.sqlite3')+'?mode=ro',uri=True) as db:
        db.row_factory = sqlite3.Row
        row = db.execute('SELECT j.*,a.status AS attempt_status,a.exit_code,a.result_manifest '
                         'FROM jobs j JOIN attempts a USING(job_id) WHERE a.attempt_id=?',(RECOVERY_ATTEMPT,)).fetchone()
        attempts = db.execute('SELECT COUNT(*) FROM attempts WHERE job_id=?',(row['job_id'],)).fetchone()[0] if row else 0
    if (row is None or row['command']!='action-train' or row['status']!='failed'
            or row['attempt_status']!='failed' or row['exit_code']!=1 or attempts!=1
            or row['code_sha']!=PRODUCER_COMMIT):
        raise ValueError('Exact preserved failed numerical parent attempt required')
    parent = json.loads(row['config_json']);old_inputs = json.loads(row['input_json'])
    keys = ['manifest','baseline_lock','split_manifest','config','review_release','weights']
    if config['stage']=='train':keys += ['prepared','preparation_evidence']
    if (parent.get('stage')!='train' or parent.get('execution_revision') is not None
            or row['job_key'] != job_key(parent) or digest(parent)!=row['config_hash'] or digest(old_inputs)!=row['input_hash']
            or any(parent['files'][key]!=config['files'][key] for key in keys)):
        raise ValueError('Recovery must preserve the failed parent data/config/pixel bindings')
    receipt_path = RUNTIME/'attempts'/RECOVERY_ATTEMPT/'manifest.json'
    if row['result_manifest']!=str(receipt_path):
        raise ValueError('Failed parent receipt path differs')
    receipt = read(receipt_path)
    if (receipt.get('synthetic') is not False or receipt.get('execution_status')!='failed'
            or receipt.get('attempt_id')!=RECOVERY_ATTEMPT
            or receipt.get('result_path')!=str(output_path('train',RECOVERY_ATTEMPT))
            or receipt.get('registration')!={key:row[key] for key in
                 ('command','job_id','run_id','task_id','dispatch_id','owner','code_sha','source_hash','input_hash','config_hash')}):
        raise ValueError('Canonical failed parent receipt differs')
    return dict(attempt_id=RECOVERY_ATTEMPT,receipt_sha256=file_hash(receipt_path),input_hash=row['input_hash'],
                status='failed_exit1_preserved_no_retry',execution_revision=EXECUTION_REVISION)


def preparation_evidence(config, paths, manifest, counts, release):
    """Authenticate completed pixels' historical provenance; never open original video."""
    evidence_binding(config['files']['preparation_evidence'])
    evidence = read(paths['preparation_evidence'])
    if (set(evidence) != {'schema_version','kind','scope','prepared','producer_contract',
                          'successful_result','source_gate_receipt','equivalence'}
            or type(evidence['schema_version']) is not int or evidence['schema_version'] != 1
            or evidence['kind'] != 'completed_action_preparation_v1' or evidence['scope'] != 'full_corpus'
            or set(evidence['equivalence']) != {'report','sequential_snapshot'}):
        raise ValueError('Exact full completed-preparation evidence schema required')
    if evidence['prepared'] != config['files']['prepared']:
        raise ValueError('Preparation evidence prepared binding differs')
    artifact = {key:evidence_binding(evidence[key]) for key in
                ('prepared','producer_contract','successful_result','source_gate_receipt')}
    equivalence = {key:evidence_binding(value) for key,value in evidence['equivalence'].items()}
    folder = paths['prepared'].parent
    for key,name in (('producer_contract','contract.json'),('successful_result','result.json'),
                     ('source_gate_receipt','verified-source-hashes.json')):
        if artifact[key] != folder/name:
            raise ValueError('Preparation artifacts must belong to the same producer output')
    if (paths['prepared'] != folder/'prepared.json' or equivalence['report'] != folder/'sequential-equivalence.json'
            or (folder/'failure.json').exists()):
        raise ValueError('Failed or noncanonical completed preparation')
    prepared, producer, success, gate = [read(artifact[key]) for key in
                                       ('prepared','producer_contract','successful_result','source_gate_receipt')]
    snapshot = read(equivalence['sequential_snapshot']); report = read(equivalence['report'])
    rows = manifest['clips']; by_id = {row['clip_id']:row for row in rows}
    if (not rows or len(by_id) != len(rows) or set(prepared['clips']) != set(by_id)
            or success.get('status') != 'prepared' or success.get('clips') != len(rows)
            or success.get('workers') != 4 or success.get('prepared_sha256') != config['files']['prepared']['sha256']
            or producer.get('mode') != 'prepare' or producer.get('workers') != 4
            or producer.get('expected_clips') != len(rows) or producer.get('counts') != counts):
        raise ValueError('Successful full preparation with exact clip inventory required')
    prep = prepared.get('preparation', {})
    driver_sha = file_hash(ROOT/'scripts/prepare_action_pixels_parallel.py')
    if (prep.get('contract') != evidence['producer_contract'] or prep.get('workers') != 4
            or prep.get('trainer_sha256') != producer.get('trainer_sha256')
            or prep.get('driver_sha256') != driver_sha or producer.get('driver_sha256') != driver_sha):
        raise ValueError('Reviewed producer contract/trainer/driver binding differs')
    compatibility = preprocessing_compatibility(producer.get('trainer_sha256'))
    if (compatibility['producer_trainer_sha256'] != compatibility['execution_trainer_sha256']
            and config.get('execution_revision') != EXECUTION_REVISION):
        raise ValueError('Explicit recovery revision required for historical prepared pixels')
    for key in ('manifest','baseline_lock','split_manifest','config','review_release'):
        if (producer.get('paths',{}).get(key) != str(paths[key])
                or producer.get('hashes',{}).get(key) != config['files'][key]['sha256']):
            raise ValueError('Producer input contract differs: '+key)
    for key in ('review_snapshot','interpretation_policy'):
        if (producer.get('paths',{}).get(key) != release[key]['path']
                or producer.get('hashes',{}).get(key) != release[key]['sha256']):
            raise ValueError('Producer review contract differs: '+key)
    if (evidence['equivalence']['sequential_snapshot']['sha256'] != FROZEN_SEQUENTIAL_SHA
            or producer.get('paths',{}).get('sequential_snapshot') != str(equivalence['sequential_snapshot'])
            or producer.get('hashes',{}).get('sequential_snapshot') != evidence['equivalence']['sequential_snapshot']['sha256']
            or snapshot.get('manifest_sha256') != config['files']['manifest']['sha256']):
        raise ValueError('Sequential snapshot producer binding differs')
    prior = snapshot.get('clips', {})
    if (not prior or not set(prior).issubset(by_id) or report.get('compared') != len(prior)
            or any(report.get(key) is not True for key in
                   ('npy_sha256_equal','arrays_equal','dtype_equal','shape_equal'))
            or any(prior[key]['sha256'] != prepared['clips'][key]['sha256'] for key in prior)):
        raise ValueError('Exact nonempty sequential pixel equivalence required')
    npy_paths = set()
    for entry in prepared['clips'].values():
        path = Path(entry['path'])
        if (not path.is_absolute() or path.parent != folder or path.suffix != '.npy'
                or path.is_symlink() or str(path) in npy_paths
                or not re.fullmatch('[0-9a-f]{64}',entry['sha256'])):
            raise ValueError('Unique producer-local NPY bindings required')
        npy_paths.add(str(path))
    expected = {}
    for row in rows:
        for path_key,hash_key in (('source_path','source_sha256'),('label_path','label_sha256')):
            path, value = row[path_key],row[hash_key]
            if path in expected and expected[path] != value:
                raise ValueError('Conflicting source gate hashes')
            expected[path] = value
    actual = {}
    if gate.get('status') != 'passed' or not isinstance(gate.get('files'),list):
        raise ValueError('Successful complete source gate receipt required')
    for entry in gate['files']:
        if (set(entry) != {'path','sha256'} or not Path(entry['path']).is_absolute()
                or entry['path'] in actual or not re.fullmatch('[0-9a-f]{64}',entry['sha256'])):
            raise ValueError('Unique exact source gate rows required')
        actual[entry['path']] = entry['sha256']
    if actual != expected:
        raise ValueError('Source gate receipt differs from complete frozen manifest')
    return actual, dict(mode='verified_during_completed_preparation_not_current_raw_revalidation',
                        evidence_sha256=config['files']['preparation_evidence']['sha256'],
                        producer_contract_sha256=evidence['producer_contract']['sha256'],
                        source_gate_receipt_sha256=evidence['source_gate_receipt']['sha256'],
                        successful_result_sha256=evidence['successful_result']['sha256'],
                        equivalence_sha256=evidence['equivalence']['report']['sha256'],
                        preprocessing_compatibility=compatibility)


def validate_smoke_numerics(result_path):
    result = read(result_path)
    if (type(result.get('optimizer_steps')) is not int or type(result.get('optimizer_step_attempts')) is not int or type(result.get('amp_skipped_steps')) is not int
            or result['optimizer_step_attempts'] != 2 or result['amp_skipped_steps'] != 0
            or result['optimizer_step_attempts'] != result['optimizer_steps'] + result['amp_skipped_steps']):
        raise ValueError('Smoke needs two actual updates with exact attempted/skipped accounting')
    scale = result.get('amp_scale')
    finite = result.get('finite_state',{})
    if (type(scale) not in (int,float) or not math.isfinite(scale) or scale <= 0
            or finite.get('model_parameters_and_buffers_finite') is not True
            or finite.get('optimizer_state_finite') is not True
            or any(type(finite.get('checked_tensors',{}).get(key)) is not int
                   or finite['checked_tensors'][key] <= 0 for key in ('model_tensors','optimizer_tensors'))):
        raise ValueError('Finite smoke scale/model/optimizer telemetry required')
    path = result_path.parent/'amp-updates.jsonl'
    if not re.fullmatch('[0-9a-f]{64}',result.get('amp_updates_sha256','')) or file_hash(path) != result['amp_updates_sha256']:
        raise ValueError('Actual AMP update telemetry binding differs')
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if len(rows) != 2:
        raise ValueError('Exact two actual smoke update records required')
    previous = None
    for index,row in enumerate(rows,1):
        before,after = row.get('scale_before'),row.get('scale_after')
        if (any(type(row.get(k)) is not int for k in ('optimizer_step_attempts','optimizer_steps','amp_skipped_steps'))
                or row.get('optimizer_step_attempts') != index or row.get('optimizer_steps') != index
                or row.get('amp_skipped_steps') != 0 or row.get('step_applied') is not True
                or row.get('overflow_skipped') is not False or row.get('epoch') != 1
                or row.get('microbatch_end') != 4*index or row.get('effective_batch_samples') != 16
                or any(type(x) not in (int,float) or not math.isfinite(x) or x <= 0 for x in (before,after))
                or after < before or (previous is not None and before != previous)):
            raise ValueError('Smoke actual-step/scaler telemetry is inconsistent')
        previous = after
    history = read(result_path.parent/'history.json')
    if (previous != scale or len(history) != 1 or history[0].get('epoch') != 1
            or history[0].get('optimizer_steps') != 2 or history[0].get('optimizer_step_attempts') != 2
            or history[0].get('amp_skipped_steps') != 0 or history[0].get('amp_scale') != scale
            or history[0].get('finite_state') != finite):
        raise ValueError('Smoke result/history/actual updates differ')
    return dict(actual_updates=2,attempted_updates=2,skipped_updates=0,amp_scale=scale,
                updates_sha256=result['amp_updates_sha256'],history_sha256=file_hash(result_path.parent/'history.json'),
                finite_state=finite)


def validate_canonical_smoke(binding, config, inputs):
    """Past succeeded canonical smoke must have consumed the same 36 pixel hashes."""
    validate_smoke(binding, config)
    result_path = checked_file(binding); attempt = result_path.parent.name
    result = read(result_path)
    if result.get('optimizer_steps') != 2 or result.get('training_complete') is not False:
        raise ValueError('Exact two-step smoke-only execution required')
    if (not re.fullmatch('[0-9a-f]{32}',attempt)
            or result_path != output_path('smoke',attempt)/'result.json'):
        raise ValueError('Canonical successful smoke result path required')
    with sqlite3.connect('file:'+str(RUNTIME/'queue.sqlite3')+'?mode=ro',uri=True) as db:
        db.row_factory = sqlite3.Row
        row = db.execute('SELECT j.*,a.status AS attempt_status,a.result_manifest FROM jobs j '
                         'JOIN attempts a USING(job_id) WHERE a.attempt_id=?',(attempt,)).fetchone()
    if (row is None or row['command'] != 'action-train' or row['status'] != 'succeeded'
            or row['attempt_status'] != 'succeeded'):
        raise ValueError('Actually succeeded canonical smoke queue attempt required')
    directory = RUNTIME/'attempts'/attempt
    if row['result_manifest'] != str(directory/'manifest.json'):
        raise ValueError('Canonical smoke queue receipt path differs')
    receipt = read(directory/'manifest.json'); saved = json.loads(row['config_json'])
    snapshot = read(directory/'action-training-config.json'); original = json.loads(row['input_json'])
    expected_registration = {key:row[key] for key in ('command','job_id','run_id','task_id','dispatch_id',
                              'owner','code_sha','source_hash','input_hash','config_hash')}
    if (receipt.get('synthetic') is not False or receipt.get('execution_status') != 'succeeded'
            or receipt.get('attempt_id') != attempt or receipt.get('result_path') != str(result_path.parent)
            or receipt.get('registration') != expected_registration or saved != snapshot
            or saved.get('stage') != 'smoke' or set(saved.get('files',{})) != FILE_KEYS
            or row['job_key'] != job_key(saved)
            or row['input_hash'] != digest(original) or row['config_hash'] != digest(saved)
            or saved.get('context') != {key:row[key] for key in ('run_id','task_id','dispatch_id','owner')}):
        raise ValueError('Canonical succeeded smoke registration/input/config proof differs')
    authorization = read(checked_file(saved['authorization']))
    if (authorization.get('stage') != 'smoke' or authorization.get('context') != saved['context']
            or authorization.get('input_hash') != row['input_hash'] or authorization.get('code_sha') != row['code_sha']
            or not authorization.get('sources') or digest(authorization['sources']) != row['source_hash']
            or any(authorization.get(key) is not True for key in
                   ('confirmed','training_authorized','independent_review_passed','explicit_gpu_go'))):
        raise ValueError('Reviewed historical smoke authorization differs')
    if authorization['sources'].get('scripts/train_action_recognizer.py') != file_hash(ROOT/'scripts/train_action_recognizer.py'):
        raise ValueError('Historical smoke training-core source differs from current frozen trainer')
    numerics = validate_smoke_numerics(result_path)
    for name, expected in authorization['sources'].items():
        committed = subprocess.check_output(['git','show',row['code_sha']+':'+name],cwd=ROOT)
        if hashlib.sha256(committed).hexdigest() != expected:
            raise ValueError('Historical smoke committed source differs')
    for key in ('manifest','baseline_lock','split_manifest','config','review_release','weights'):
        if saved['files'][key] != config['files'][key]:
            raise ValueError('Smoke/training input binding differs: '+key)
    if (saved.get('execution_revision') != config.get('execution_revision')
            or original.get('execution_revision') != saved.get('execution_revision')):
        raise ValueError('Canonical smoke and train execution revisions differ')
    if (original.get('files') != {key:value['sha256'] for key,value in saved['files'].items()}
            or original.get('review_snapshot_sha256') != inputs['review_snapshot_sha256']):
        raise ValueError('Smoke queued file/review bindings differ')
    manifest = read(config['files']['manifest']['path']); selected = trainer().partition_rows(manifest,'smoke')
    ids = {row['clip_id'] for row in selected}
    expected_sources = {row[path_key]:row[hash_key] for row in selected for path_key,hash_key in
                        (('source_path','source_sha256'),('label_path','label_sha256'))}
    pixels = original.get('pixels',{})
    if (len(ids) != 36 or set(pixels) != ids or original.get('sources') != expected_sources
            or any(pixels[key] != inputs['pixels'].get(key) for key in ids)):
        raise ValueError('Canonical smoke36/full preparation pixel/source equality required')
    old_prepared = read(checked_file(saved['files']['prepared']))
    if (old_prepared.get('manifest_sha256') != saved['files']['manifest']['sha256']
            or old_prepared.get('config_sha256') != saved['files']['config']['sha256']
            or any(old_prepared['clips'][key]['sha256'] != pixels[key] for key in ids)):
        raise ValueError('Canonical smoke pixel provenance differs')
    return dict(attempt_id=attempt,receipt_sha256=file_hash(directory/'manifest.json'),
                input_hash=row['input_hash'],matching_pixels=36,numerics=numerics)


def validate_assignment(context):
    if set(context) != {'run_id','task_id','dispatch_id','owner'} or context['run_id'] != 'run_3d23462a014a':
        raise ValueError('Existing canonical Orca assignment required')
    cli = os.environ.get('ORCA_CLI_COMMAND', 'orca-ide')
    data = json.loads(subprocess.check_output([cli,'orchestration','worker-show','--dispatch',
                      context['dispatch_id'],'--json'], text=True, timeout=25))
    if not data.get('ok'):
        raise ValueError('Live Orca assignment unavailable')
    dispatch = data['result']['dispatch']
    if (dispatch.get('runId') != context['run_id'] or dispatch.get('taskId') != context['task_id']
            or dispatch.get('assigneeHandle') != context['owner'] or dispatch.get('status') != 'dispatched'
            or dispatch.get('capabilityRevokedAt') is not None):
        raise ValueError('Current live Run/Task/Dispatch/owner required')
    live = data['result'].get('projection', {}).get('liveness', {})
    observation = data['result'].get('observation', {})
    if live.get('verdict') != 'live' or observation.get('status') != 'live' or observation.get('exactWorker') is not True:
        raise ValueError('Exact Orca worker liveness is not established')
    return dict(dispatch=dispatch, liveness=live, observation=observation,
                observed_utc=dt.datetime.now(dt.timezone.utc).isoformat())


def validate(config, inputs, runtime):
    if (set(config) != {'stage','context','files','authorization','execution_revision'}
            or config['execution_revision'] != EXECUTION_REVISION or config['stage'] not in ('smoke','train')
            or Path(runtime).resolve() != RUNTIME or not INTERPRETER.is_file()):
        raise ValueError('Canonical runtime, existing interpreter and smoke/train stage required')
    actual = input_contract(config)
    if inputs != actual:
        raise ValueError('Action training input contract changed')
    authorization = read(checked_file(config['authorization']))
    if (authorization.get('context') != config['context'] or authorization.get('stage') != config['stage']
            or authorization.get('input_hash') != digest(inputs) or authorization.get('sources') != sources()
            or authorization.get('execution_revision') != EXECUTION_REVISION
            or authorization.get('recovery_from_attempt') != RECOVERY_ATTEMPT
            or any(authorization.get(k) is not True for k in
                   ('confirmed','training_authorized','independent_review_passed','explicit_gpu_go'))):
        raise ValueError('Reviewed exact source/input assignment and explicit GPU GO required')
    head = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if authorization.get('code_sha') != head:
        raise ValueError('Reviewed committed code SHA differs')
    for name, expected in authorization['sources'].items():
        committed = subprocess.check_output(['git','show',head+':'+name],cwd=ROOT)
        if hashlib.sha256(committed).hexdigest() != expected:
            raise ValueError('Reviewed sources must be committed: '+name)
    recovery = validate_recovery_parent(config)
    smoke_proof = None
    if config['stage'] == 'train':
        smoke_proof = validate_canonical_smoke(authorization.get('smoke_result'),config,inputs)
    live_assignment = validate_assignment(config['context'])
    result = dict(authorization=authorization, live_assignment=live_assignment,recovery=recovery)
    if smoke_proof is not None:
        result['canonical_smoke'] = smoke_proof
    return result


def validate_smoke(binding, config):
    if not binding:
        raise ValueError('A successful actual smoke result is required before training')
    result = read(checked_file(binding))
    batch_size = read(config['files']['config']['path'])['batch_size']
    if (result.get('status') != 'smoke_passed' or result.get('test_accessed') is not False
            or result.get('manifest_sha256') != config['files']['manifest']['sha256']
            or result.get('config_sha256') != config['files']['config']['sha256']
            or result.get('real_train_clips') != 32 or result.get('real_validation_clips') != 4
            or result.get('actual_microbatch_sizes') != [batch_size]*(32//batch_size)
            or result.get('accumulation') != 4 or result.get('optimizer_steps',0) < 2):
        raise ValueError('Actual smoke does not validate the requested manifest/config/batch/accumulation')


def job_key(config):
    key = 'exp0063-action-'+config['stage']+'-'+config['files']['manifest']['sha256']
    if 'execution_revision' in config:
        if config['execution_revision'] != EXECUTION_REVISION:
            raise ValueError('Unreviewed execution revision')
        key += '-'+config['execution_revision']
    return key


def output_path(stage, attempt):
    if stage not in ('smoke','train') or not re.fullmatch('[0-9a-f]{32}', attempt):
        raise ValueError('Exact action stage/attempt required')
    return OUTPUT/stage/attempt


def resources():
    value = subprocess.check_output(['nvidia-smi','--id=0','--query-gpu=memory.free',
                                     '--format=csv,noheader,nounits'],text=True,timeout=15)
    free = int(value.strip())
    if free < 6144:
        raise ValueError('Action training requires at least 6144MiB free')
    return {'device':0,'free_mib':free}


def command(config, inputs, runtime, attempt, lock_fd):
    provenance = validate(config, inputs, runtime)
    os.fstat(lock_fd)
    resources()
    directory = Path(runtime)/'attempts'/attempt
    directory.mkdir(parents=True, exist_ok=True)
    snapshot = directory/'action-training-config.json'
    if snapshot.exists():
        raise ValueError('Action queue config snapshot already exists')
    snapshot.write_text(json.dumps(config,sort_keys=True,indent=2)+'\n')
    (directory/'action-live-assignment.json').write_text(json.dumps(provenance,sort_keys=True,indent=2)+'\n')
    files = config['files']
    argv = [str(INTERPRETER),'-I',str(ROOT/'scripts/train_action_recognizer.py'),
            '--mode',config['stage'],'--output',str(output_path(config['stage'],attempt)),
            '--queue-config',str(snapshot),'--queue-config-sha256',file_hash(snapshot),
            '--queue-attempt',attempt,'--review-release-sha256',files['review_release']['sha256'],
            '--weights-sha256',files['weights']['sha256']]
    for name in ('manifest','baseline_lock','split_manifest','config','review_release','weights'):
        argv += ['--'+name.replace('_','-'),files[name]['path']]
    return argv+['--prepared',str(Path(files['prepared']['path']).parent)]


def runner_guard(args):
    """Child must inherit the actual running queue attempt and its held lock."""
    from orchestration.queue import Queue, source_hash
    fd = int(os.environ['SCENEGUARD_GPU_LOCK_FD'])
    actual, held = (RUNTIME/'gpu.lock').stat(), os.fstat(fd)
    if (actual.st_dev, actual.st_ino) != (held.st_dev, held.st_ino):
        raise ValueError('Wrong canonical GPU reservation FD')
    # A separate open must fail: simply acquiring a supplied unheld FD is insufficient.
    with (RUNTIME/'gpu.lock').open('a+') as probe:
        try:
            fcntl.flock(probe, fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            pass
        else:
            raise ValueError('Canonical GPU reservation is not held')
    fcntl.flock(fd, fcntl.LOCK_EX|fcntl.LOCK_NB)
    if not args.queue_config or file_hash(args.queue_config) != args.queue_config_sha256:
        raise ValueError('Queue config snapshot differs')
    config = read(args.queue_config)
    expected = output_path(config['stage'],args.queue_attempt)
    if (args.mode != config['stage'] or args.output.resolve() != expected
            or args.prepared.resolve() != Path(config['files']['prepared']['path']).parent.resolve()):
        raise ValueError('Runner mode/output/prepared differ from queue registration')
    for name in ('manifest','baseline_lock','split_manifest','config','review_release','weights'):
        if getattr(args,name).resolve() != Path(config['files'][name]['path']).resolve():
            raise ValueError('Runner input path differs: '+name)
    if (args.weights_sha256 != config['files']['weights']['sha256']
            or args.review_release_sha256 != config['files']['review_release']['sha256']):
        raise ValueError('Runner input hash differs')
    q = Queue(RUNTIME)
    with q.connection() as db:
        row = db.execute('SELECT j.*,a.status AS attempt_status,a.supervisor_pid,a.supervisor_identity '
                         'FROM jobs j JOIN attempts a USING(job_id) WHERE a.attempt_id=?',
                         (args.queue_attempt,)).fetchone()
    if row is None:
        raise ValueError('Actual running canonical queue attempt required')
    inputs = json.loads(row['input_json'])
    validate(config, inputs, RUNTIME)
    if (row['command'] != 'action-train' or row['status'] != 'running'
            or row['attempt_status'] != 'running' or json.loads(row['config_json']) != config
            or row['input_hash'] != digest(inputs) or row['source_hash'] != source_hash('action-train',config)
            or any(row[k] != v for k,v in config['context'].items())
            or process_state(row['supervisor_pid'],row['supervisor_identity']) != 'live'):
        raise ValueError('Actual running canonical queue attempt required')
    if os.environ.get('CUDA_VISIBLE_DEVICES') != '0':
        raise ValueError('Canonical GPU0 device binding required')
    resources()


def retry_guard(db, job):
    raise ValueError('Action training retries require a separately reviewed execution plan')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--queue-config', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(input_contract(read(args.queue_config)),sort_keys=True,indent=2))


if __name__ == '__main__':
    main()
