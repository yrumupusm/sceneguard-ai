# SPDX-License-Identifier: AGPL-3.0-only
"""EXP-0027 bounded low-confidence diagnosis; canonical queue and frozen authority."""
from copy import deepcopy
import json
from pathlib import Path
import re
import subprocess
from orchestration.batch07_detect_command import (ROOT, RUNTIME, INTERPRETER, EVAL,
    PREDICT_KWARGS as EXP26_KWARGS, checked, validate_eval, dataset_files)
from orchestration.queue import digest
from orchestration.vlm_command import file_hash

LOCAL = ROOT / 'runtime/EXP-0027'
MANIFEST = ROOT / 'configs/exp0027_detection_manifest.json'
EVAL_SHA = 'd5f55a213f002a335da610cafdd42803fc9b1f96dc205bc47e0de980451187cf'
OLD_SUMMARY = ROOT / 'outputs/batch0007/EXP-0026/train_compare/616f05a480c7434f82253e90ae7a096e/summary.json'
OLD_SUMMARY_SHA = 'ba1fdb049f2c030576817b7d781ff6180e9337a077ffd148679ee1ddd044cc99'
MODELS = {
    'pretrained': dict(path='weights/yolo26m.pt', sha256='401cea9ab23ad19246ff7744859816bc599f350e93c9dd30367b6f0a0745d0b7', nc=80, cached_phase='baseline'),
    'fine_tuned': dict(path='outputs/batch0007/EXP-0026/train_compare/616f05a480c7434f82253e90ae7a096e/training/weights/best.pt', sha256='1b120a24c8983507e137304ec3ef814a2415d97c866113df80a6cb61c260dd4f', nc=1, cached_phase='after')}
FRAMES = ('030_084','030_090','030_094','030_050','030_055','007_047p5','007_052p5')
IDENTITY = ('run_3d23462a014a','task_e36f02bf0722','ctx_75d3dc7cb54f')
STAGES = ('diagnose',)
PREDICT_KWARGS = deepcopy(EXP26_KWARGS)
PREDICT_KWARGS['conf'] = .05
SETTINGS = dict(api='YOLO.predict',ultralytics='8.4.192',predict_kwargs=PREDICT_KWARGS,
    minimum_gpu_free_mib=6144,maximum_sample_calls=14,maximum_queue_seconds=900,
    automatic_retry=False,execution_error_retries_max=0,training=False,
    visual_quality='unreviewed',behavior='unmeasured',default_application=False)


def evaluation():
    checked(EVAL,EVAL_SHA)
    d=validate_eval(json.loads(EVAL.read_text()))
    if tuple(f['frame_id'] for f in d['frames'])!=FRAMES:
        raise ValueError('exact seven frame order required')
    return d


def historical_outputs():
    checked(OLD_SUMMARY,OLD_SUMMARY_SHA)
    d=json.loads(OLD_SUMMARY.read_text())
    for model in MODELS.values():
        records=d[model['cached_phase']]
        if tuple(r['frame_id'] for r in records)!=FRAMES:
            raise ValueError('fixed historical output order required')
        for record in records:
            ref=record['native_result'];checked(ref['path'],ref['sha256'])
    return d


def input_contract(stage='diagnose'):
    job_key(stage)
    public=json.loads(MANIFEST.read_text())
    if public!=dict(schema_version=1,experiment_id='EXP-0027',settings=SETTINGS,
            models=MODELS,frames=list(FRAMES),evaluation_manifest_sha256=EVAL_SHA,
            historical_summary_sha256=OLD_SUMMARY_SHA):
        raise ValueError('fixed EXP27 public manifest differs')
    for spec in MODELS.values():checked(spec['path'],spec['sha256'])
    evaluation();old=historical_outputs()
    env=json.loads(EVAL.read_text())['historical_environment_pins']
    for n,h in env['files'].items():checked(n,h)
    for n,h in json.loads((ROOT/env['file_index']).read_text()).items():
        if not n.startswith('.venv-pose-batch03/'):raise ValueError('fixed environment prefix required')
        checked(n,h)
    freeze=ROOT/'runtime/BATCH-0007/training/dataset-freeze.local.json'
    if dataset_files()!=json.loads(freeze.read_text()):raise ValueError('historical dataset bytes differ')
    return dict(manifest_sha256=file_hash(MANIFEST),evaluation_manifest_sha256=EVAL_SHA,
        models=MODELS,historical_summary_sha256=OLD_SUMMARY_SHA,
        historical_results={r['native_result']['path']:r['native_result']['sha256'] for phase in ('baseline','after') for r in old[phase]},
        dataset_snapshot_sha256=file_hash(freeze),environment_files=env['files'],
        environment_index_sha256=file_hash(ROOT/env['file_index']),
        camera_config_sha256=file_hash(ROOT/'configs/mvp0001_cameras.json'))


def sources(config=None):
    from orchestration.batch07_detect_command import sources as old_sources
    names=set(old_sources())
    names.update(['orchestration/exp27_detect_command.py','configs/exp0027_detection_manifest.json','tests_orca/test_exp27_detect.py'])
    names.update(str(p.relative_to(ROOT)) for p in (ROOT/'exp27_detect').glob('*.py'))
    return {n:file_hash(ROOT/n) for n in sorted(names)}


def validate_assignment(run,task,dispatch):
    a=json.loads((LOCAL/'execution-authorization.json').read_text())
    if (run,task,dispatch)!=IDENTITY or tuple(a[k] for k in ('run_id','task_id','dispatch_id'))!=IDENTITY:
        raise ValueError('current coordinator-confirmed EXP27 identity required')
    if any(a.get(k) is not True for k in ('confirmed','inference_authorized','independent_review_passed')):
        raise ValueError('explicit reviewed inference authorization required')
    if a.get('maximum_sample_calls')!=14 or a.get('allowed_stages')!=list(STAGES):
        raise ValueError('bounded fourteen-call diagnosis authorization required')
    if a.get('sources')!=sources() or a.get('input_contract_sha256')!=digest(input_contract()):
        raise ValueError('exact reviewed source/input authorization required')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if a.get('code_sha')!=head:raise ValueError('current Git freeze differs')
    return a


def job_key(stage='diagnose'):
    if stage not in STAGES:raise ValueError('fixed EXP27 diagnose stage required')
    return 'exp0027-detect-low-confidence'


def output_path(stage,attempt):
    job_key(stage)
    if not re.fullmatch('[0-9a-f]{32}',attempt):raise ValueError('invalid attempt')
    return ROOT/'outputs/exp0027/EXP-0027'/stage/attempt


def validate(config,inputs,runtime):
    if config!=dict(stage='diagnose',settings=SETTINGS) or Path(runtime).resolve()!=RUNTIME or not INTERPRETER.is_file():
        raise ValueError('fixed EXP27 settings/canonical queue/interpreter required')
    if inputs!=input_contract():raise ValueError('fixed input contract differs')
    validate_assignment(*IDENTITY)
    return 'diagnose'


def execution_guard(db,job,attempt):
    rows=db.execute("SELECT j.job_key,j.run_id,j.task_id,j.dispatch_id,a.attempt_id,a.attempt_no FROM jobs j LEFT JOIN attempts a USING(job_id) WHERE j.command='exp27-detect'").fetchall()
    if len(rows)!=1 or tuple(rows[0])!=(job_key(),*IDENTITY,attempt,1) or job['job_key']!=job_key():
        raise ValueError('one initial EXP27 attempt required; no retries')


def retry_guard(db,job):
    raise ValueError('no automatic retry or explicit rerun in EXP27')


def command(config,inputs,runtime,attempt,lock_fd):
    stage=validate(config,inputs,runtime);output_path(stage,attempt)
    return [str(INTERPRETER),'-I',str(ROOT/'exp27_detect/runner.py'),'--stage',stage,'--attempt',attempt,'--lock-fd',str(lock_fd)]
