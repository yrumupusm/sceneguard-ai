"""EXP-0064 advisory action adapter, pending root canonical queue registration.

Import/contract generation do not load torch, mutate the queue, or start inference.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess

from orchestration.queue import digest, process_state
from orchestration.action_training_command import validate_assignment, resources, file_hash, read, checked_file, trainer

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=Path('/home/jhc7484/dev/sceneguard-orca-lab/runtime/orca-lab/gpu-queue')
INTERPRETER=ROOT/'.venv-cv-batch02/bin/python'
OUTPUT=ROOT/'outputs/action-recognition/exp0064/queued-inference'
INTEGRATION_PLAN=ROOT/'docs/experiments/EXP-0063-integration-plan.md'
INTEGRATION_PLAN_SHA='25e9a1d0c839c45a29f658fb247ee2658738f378f921c62bba0a6ab0896c3868'
FILE_KEYS={'manifest','baseline_lock','checkpoint','training_result','training_history',
           'test_scores','training_config','training_manifest','training_receipt','training_queue_config'}


def planner():
    spec=importlib.util.spec_from_file_location('action_regression_plan',ROOT/'scripts/prepare_action_regression.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def sources(config=None):
    names=('orchestration/queue.py','orchestration/mock_job.py','orchestration/action_training_command.py',
           'orchestration/action_inference_command.py','docs/experiments/EXP-0063-integration-plan.md','scripts/prepare_action_regression.py',
           'scripts/infer_action_regression.py','scripts/train_action_recognizer.py',
           'scripts/build_action_training_clips.py','tests/test_action_regression.py','tests_orca/test_action_inference.py')
    return {p:file_hash(ROOT/p) for p in names}


def standalone_contract(paths, config):
    result=read(paths['training_result']);history=read(paths['training_history'])
    settings=read(paths['training_config']);receipt=read(paths['training_receipt'])
    module=planner();training=trainer();training.validate_config(settings)
    if any(settings.get(k)!=module.POLICY[k] for k in
           ('frames','sample_fps','threshold','image_size','batch_size','precision')):
        raise ValueError('Frozen training preprocessing differs')
    if (settings.get('model')!='torchvision.models.video.r3d_18' or settings.get('epochs')!=10
            or settings.get('selection')!='minimum_validation_cross_entropy'):
        raise ValueError('Fixed first model and validation selection required')
    train_dir=paths['training_result'].parent
    if (not re.fullmatch('[0-9a-f]{32}',train_dir.name)
            or train_dir.parent!=ROOT/'outputs/action-recognition/exp0063/queued-training/train'
            or any(paths[k]!=train_dir/name for k,name in
                   (('checkpoint','best.pt'),('training_history','history.json'),('test_scores','test-scores.json')))):
        raise ValueError('Exact standalone queued training final outputs required')
    if (result.get('status')!='trained' or not result.get('test')
            or result.get('weights_sha256')!=config['files']['checkpoint']['sha256']
            or len(history)!=10 or [r.get('epoch') for r in history]!=list(range(1,11))):
        raise ValueError('Completed standalone training and test evaluation required')
    import math
    if any(not math.isfinite(r['validation_loss']) for r in history):
        raise ValueError('Finite standalone validation history required')
    selected=min(history,key=lambda r:r['validation_loss'])['epoch']
    if result.get('best_epoch')!=selected:
        raise ValueError('Validation-selected final checkpoint required')
    scores=read(paths['test_scores'])
    if not scores: raise ValueError('Completed standalone test scores required')
    if (paths['training_receipt']!=RUNTIME/'attempts'/train_dir.name/'manifest.json'
            or receipt.get('execution_status')!='succeeded' or receipt.get('synthetic') is not False
            or receipt.get('registration',{}).get('command')!='action-train'
            or receipt.get('attempt_id')!=train_dir.name or receipt.get('result_path')!=str(train_dir)):
        raise ValueError('Successful canonical standalone training receipt required')
    snapshot_path=RUNTIME/'attempts'/train_dir.name/'action-training-config.json'
    if paths['training_queue_config']!=snapshot_path:
        raise ValueError('Adjacent same-attempt training contract required')
    snapshot=read(snapshot_path)
    if (snapshot.get('stage')!='train' or receipt['registration'].get('config_hash')!=digest(snapshot)
            or any(snapshot.get('files',{}).get(key)!=config['files'][name] for key,name in
                   (('manifest','training_manifest'),('config','training_config'),('baseline_lock','baseline_lock')))):
        raise ValueError('Adjacent training manifest/config/baseline contract differs')
    training_manifest=read(paths['training_manifest'])
    if (training_manifest.get('baseline_lock_sha256')!=module.LOCK_SHA
            or training_manifest.get('config_sha256')!=config['files']['training_config']['sha256']):
        raise ValueError('Standalone training all45 exclusion baseline/config differs')
    test_rows=[r for r in training_manifest['clips'] if r['split']=='test']
    test_by_id={r['clip_id']:r for r in test_rows}
    if (not test_rows or len(test_by_id)!=len(test_rows) or len(scores)!=len(test_rows)
            or {s['clip_id'] for s in scores}!=set(test_by_id)
            or any(s['label']!=test_by_id[s['clip_id']]['label']
                   or not math.isfinite(s['score']) or not 0<=s['score']<=1 for s in scores)):
        raise ValueError('Complete exact standalone test score inventory required')
    if result['test']!=training.evaluation_report(scores,test_rows,set(training_manifest.get('held_out_test_locations',[]))):
        raise ValueError('Standalone test evaluation report differs from actual scores')
    return dict(selected_epoch=selected,training_manifest_sha256=config['files']['training_manifest']['sha256'])


def input_contract(config):
    if set(config['files'])!=FILE_KEYS: raise ValueError('Exact inference input bindings required')
    paths={k:checked_file(v) for k,v in config['files'].items()}
    module=planner()
    checked_file(dict(path=str(INTEGRATION_PLAN),sha256=INTEGRATION_PLAN_SHA))
    if paths['manifest']!=module.OUTPUT/'manifest.json' or paths['baseline_lock']!=module.LOCK:
        raise ValueError('Canonical regression plan and frozen baseline required')
    if config['files']['baseline_lock']['sha256']!=module.LOCK_SHA:
        raise ValueError('EXP0062 attempt-002 baseline lock changed')
    manifest=read(paths['manifest'])
    if (manifest.get('policy')!=module.POLICY or manifest.get('ground_truth_used') is not False
            or manifest.get('baseline_lock')!={'path':str(module.LOCK),'sha256':module.LOCK_SHA}
            or manifest.get('status')!='cpu_plan_only_no_inference'):
        raise ValueError('Immutable advisory integration policy required')
    entries=manifest['videos']
    if len(entries)!=45 or {e['video_id'] for e in entries}!={f'E01_{i:03d}' for i in range(1,46)}:
        raise ValueError('Exact all45 inference required')
    lock=read(paths['baseline_lock']); originals={e['video_id']:e for e in lock['regression_only_videos']}
    selected={};plans={};baseline={}
    for entry in entries:
        path=checked_file({k:entry[k] for k in ('path','sha256')})
        if path!=module.OUTPUT/(entry['video_id']+'.json'):
            raise ValueError('Canonical source plan required')
        row=read(path)
        # Recompute CPU plan from locked source data: a forged eligible window cannot enter execution.
        expected=module.source_plan(originals[entry['video_id']],lock)
        if row!=expected: raise ValueError('Source window/coverage plan changed')
        plans[str(path)]=entry['sha256']
        for p,h in {**row['input_hashes'],**row['baseline_hashes']}.items():
            if p in selected and selected[p]!=h: raise ValueError('Conflicting source binding')
            selected[p]=h
        baseline.update(row['baseline_hashes'])
    # Verify actual selected originals here, once per unique source, not the huge historical lock inventory.
    for p,h in selected.items(): checked_file(dict(path=p,sha256=h))
    standalone=standalone_contract(paths,config)
    return dict(files={k:v['sha256'] for k,v in config['files'].items()},plans=plans,
                selected_sources=selected,baseline_outputs=baseline,standalone=standalone,
                integration_plan=dict(path=str(INTEGRATION_PLAN),sha256=INTEGRATION_PLAN_SHA))


def validate(config, inputs, runtime):
    if (set(config)!={'stage','context','files','authorization'} or config['stage']!='all45'
            or Path(runtime).resolve()!=RUNTIME or not INTERPRETER.is_file()):
        raise ValueError('Canonical runtime/interpreter/all45 stage required')
    actual=input_contract(config)
    if inputs!=actual: raise ValueError('Inference input contract changed')
    authorization=read(checked_file(config['authorization']))
    if (authorization.get('context')!=config['context'] or authorization.get('stage')!='all45'
            or authorization.get('input_hash')!=digest(inputs) or authorization.get('sources')!=sources()
            or any(authorization.get(k) is not True for k in ('confirmed','inference_authorized',
                'standalone_evaluation_complete','independent_review_passed','root_go','explicit_gpu_go'))):
        raise ValueError('Independent review, completed standalone evaluation and explicit root GPU GO required')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if authorization.get('code_sha')!=head: raise ValueError('Reviewed committed source HEAD differs')
    for name,h in authorization['sources'].items():
        if hashlib.sha256(subprocess.check_output(['git','show',head+':'+name],cwd=ROOT)).hexdigest()!=h:
            raise ValueError('Reviewed source must be committed: '+name)
    return dict(authorization=authorization,live_assignment=validate_assignment(config['context']))


def job_key(config):
    return 'exp0064-action-all45-'+config['files']['manifest']['sha256']+'-'+config['files']['checkpoint']['sha256']


def output_path(stage, attempt):
    if stage!='all45' or not re.fullmatch('[0-9a-f]{32}',attempt): raise ValueError('Exact all45 attempt required')
    return OUTPUT/stage/attempt


def command(config, inputs, runtime, attempt, lock_fd):
    provenance=validate(config,inputs,runtime);os.fstat(lock_fd);resources()
    directory=Path(runtime)/'attempts'/attempt;directory.mkdir(parents=True,exist_ok=True)
    snapshot=directory/'action-inference-config.json'
    with snapshot.open('x') as stream: json.dump(config,stream,sort_keys=True,indent=2)
    (directory/'action-inference-live-assignment.json').write_text(json.dumps(provenance,sort_keys=True,indent=2)+'\n')
    return [str(INTERPRETER),'-I',str(ROOT/'scripts/infer_action_regression.py'),
            '--queue-config',str(snapshot),'--queue-config-sha256',file_hash(snapshot),
            '--queue-attempt',attempt,'--output',str(output_path(config['stage'],attempt))]


def runner_guard(args):
    """No standalone bypass: inherited held FD + actual running row + live reviewed assignment."""
    from orchestration.queue import source_hash
    fd=int(os.environ['SCENEGUARD_GPU_LOCK_FD'])
    actual,held=(RUNTIME/'gpu.lock').stat(),os.fstat(fd)
    if (actual.st_dev,actual.st_ino)!=(held.st_dev,held.st_ino): raise ValueError('Wrong canonical GPU reservation FD')
    with (RUNTIME/'gpu.lock').open('a+') as probe:
        try: fcntl.flock(probe,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: pass
        else: raise ValueError('Canonical GPU reservation is not held')
    fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    snapshot=Path(args.queue_config)
    if snapshot!=RUNTIME/'attempts'/args.queue_attempt/'action-inference-config.json':
        raise ValueError('Canonical attempt snapshot required')
    if file_hash(snapshot)!=args.queue_config_sha256: raise ValueError('Queue snapshot changed')
    config=read(snapshot)
    if args.output.resolve()!=output_path(config['stage'],args.queue_attempt): raise ValueError('Runner output differs')
    with sqlite3.connect('file:'+str(RUNTIME/'queue.sqlite3')+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        row=db.execute('SELECT j.*,a.status AS attempt_status,a.supervisor_pid,a.supervisor_identity '
                       'FROM jobs j JOIN attempts a USING(job_id) WHERE a.attempt_id=?',(args.queue_attempt,)).fetchone()
    if row is None: raise ValueError('Actual running canonical queue attempt required')
    inputs=json.loads(row['input_json']);provenance=validate(config,inputs,RUNTIME)
    if (row['command']!='action-infer' or row['status']!='running' or row['attempt_status']!='running'
            or json.loads(row['config_json'])!=config or row['config_hash']!=digest(config)
            or row['input_hash']!=digest(inputs) or row['source_hash']!=source_hash('action-infer',config)
            or row['source_hash']!=digest(sources(config)) or row['job_key']!=job_key(config)
            or row['code_sha']!=provenance['authorization']['code_sha']
            or any(row[k]!=v for k,v in config['context'].items())
            or process_state(row['supervisor_pid'],row['supervisor_identity'])!='live'):
        raise ValueError('Actual running canonical queue attempt required')
    if os.environ.get('CUDA_VISIBLE_DEVICES')!='0': raise ValueError('Canonical GPU0 required')
    resources()
    return config,inputs


def retry_guard(db,job):
    raise ValueError('Action inference retries require a separately reviewed execution plan')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Read-only exact inference input contract; no execution')
    parser.add_argument('--queue-config',type=Path,required=True);args=parser.parse_args()
    print(json.dumps(input_contract(read(args.queue_config)),sort_keys=True,indent=2))
