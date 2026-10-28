"""Fixed Qwen4B command contract; shared queue integration is coordinator-owned."""
import json
from pathlib import Path
import re
from orchestration.vlm_command import RUNTIME, file_hash

ROOT = Path('/home/jhc7484/dev/sceneguard-ai')
INTERPRETER = ROOT / '.venv-vlm-batch02/bin/python'
MANIFEST = ROOT / 'configs/batch0002_vlm_manifest.json'
LOCAL = ROOT / 'runtime/BATCH-0002/vlm'
MODEL = ROOT / 'weights/Qwen3-VL-4B-Instruct'
REVISION = 'ebb281ec70b05090aa6165b016eac8ec08e71b17'
SMOKE = ('q04_C', 'q05_B')
CONDITIONS = tuple(f'q{i:02}_{v}' for i in range(1,7) for v in ('B','C')) + tuple(f'v{i:02}_full_frame' for i in range(1,5))
SETTINGS = dict(seed=0, batch_size=1, do_sample=False, max_new_tokens=384,
    repetition_penalty=1.0, attention='sdpa', device='cuda:0', dtype='bfloat16',
    minimum_gpu_free_mib=6144, execution_error_retries_max=1)
QUANTIZATION = dict(load_in_4bit=True, bnb_4bit_quant_type='nf4',
    bnb_4bit_compute_dtype='bfloat16', bnb_4bit_quant_storage='uint8',
    bnb_4bit_use_double_quant=True, llm_int8_skip_modules=['model.visual','lm_head'],
    llm_int8_enable_fp32_cpu_offload=False)
SHARDS = {'model-00001-of-00002.safetensors': (4967229296, '30a01a0556622645a3cce87b655bbbbbc1f170c196099f1b666c93202c3339a9'),
          'model-00002-of-00002.safetensors': (3908490048, '046296a2a387efb43b0c997d5833c789604d168834f6e0d3064bf7bb13d002a6')}


def same(a,b):
    return json.dumps(a,sort_keys=True,allow_nan=False)==json.dumps(b,sort_keys=True,allow_nan=False)


def manifest():
    d = json.loads(MANIFEST.read_text())
    if (not same(d['settings'],SETTINGS) or not same(d['quantization'],QUANTIZATION) or
        d['model']['revision'] != REVISION or d['model']['id'] != 'Qwen/Qwen3-VL-4B-Instruct' or
        tuple(r['condition_id'] for r in d['conditions']) != CONDITIONS or d['smoke'] != list(SMOKE) or
        d['prompt_sha256'] != '049ec4a6274443fcf8e3069914e53b2913aefa6f4a13ca049cc4001fa8def7a6' or
        d['processor_size'] != dict(shortest_edge=16384,longest_edge=3584000)):
        raise ValueError('frozen VLM matrix/settings/model differ')
    for name,(size,sha) in SHARDS.items():
        if d['model']['files'][name]['bytes'] != size or d['model']['files'][name]['sha256'] != sha:
            raise ValueError('sole official shard differs')
    for row in d['conditions']:
        m = row['expected_metadata']
        if (m['observed_frames'] != 10 or m['processor_frames'] != 10 or m['temporal_padding_frames'] != 0 or
            m['source_pts'] != [m['window_start']+i/2 for i in range(10)] or
            m['window_end']-m['window_start'] != 5 or m['extra_sampling'] is not False):
            raise ValueError('frozen ten-frame baseline differs')
    return d


def sources(config=None):
    names = ['orchestration/__init__.py','mvp/__init__.py','vlm_batch/__init__.py','orchestration/queue.py','orchestration/mock_job.py','orchestration/vlm_command.py',
        'orchestration/batch02_vlm_command.py','orchestration/mvp_command.py','mvp/method.py',
        'mvp/independent.py','vlm_batch/common.py',
        'configs/vlm_batch01_prompt.txt','configs/batch0002_vlm_manifest.json',
        'requirements-vlm-batch02-lock.txt','tests_orca/test_batch02_vlm.py',
        'configs/batch0002_user_input_review.json','configs/batch0002_vlm_continuation.json']
    names += [str(p.relative_to(ROOT)) for p in sorted((ROOT/'batch02_vlm').glob('*.py'))]
    return {n:file_hash(ROOT/n) for n in names}


def source_hash(config=None):
    from orchestration.queue import digest
    return digest(sources(config))


def validate_assignment(run,task,dispatch):
    a=json.loads((LOCAL/'execution-authorization.json').read_text())
    if (run,task,dispatch) != tuple(a[k] for k in ('run_id','task_id','dispatch_id')) or a.get('confirmed') is not True:
        raise ValueError('coordinator-confirmed VLM execution assignment required')
    if a['sources'] != sources():
        raise ValueError('coordinator source/config freeze differs')
    return a


def safe_file(name):
    p=ROOT/name
    if p.resolve() != p or not p.is_relative_to(ROOT):
        raise ValueError('frozen local path required without symlink redirection')
    return p


def input_contract(condition):
    if condition not in CONDITIONS:
        raise ValueError('unknown condition')
    d=manifest()
    row=next(r for r in d['conditions'] if r['condition_id']==condition)
    if d['environment']['status']!='installed_verified' or not d['environment']['files']:
        raise ValueError('verified isolated environment required')
    if file_hash(INTERPRETER)!=d['environment']['interpreter_sha256']:
        raise ValueError('isolated Python binary differs')
    pins={**d['pins'],**d['environment']['files'],**row['files']}
    pins.update({str((MODEL/n).relative_to(ROOT)):r['sha256'] for n,r in d['model']['files'].items()})
    for name,expected in pins.items():
        if file_hash(safe_file(name)) != expected:
            raise ValueError('frozen input/environment/model differs: '+name)
    env=json.loads((LOCAL/'environment.json').read_text())
    for name,expected in env['files'].items():
        if file_hash(safe_file(name))!=expected:
            raise ValueError('installed environment file differs: '+name)
    for name,(size,_) in SHARDS.items():
        if (MODEL/name).stat().st_size != size:
            raise ValueError('official shard size differs')
    return dict(manifest_sha256=file_hash(MANIFEST),condition_id=condition,files=pins)


def continuation_binding():
    import sys
    from batch02_vlm.continuation import load
    return load(sys.modules[__name__])


def retry_guard(db,row):
    import sys
    from batch02_vlm.continuation import retry_guard as guard
    return guard(sys.modules[__name__],db,row)


def successful(condition):
    import sqlite3
    with sqlite3.connect(f'file:{RUNTIME/"queue.sqlite3"}?mode=ro',uri=True) as db:
        rows=db.execute("SELECT a.attempt_id,j.source_hash,j.input_json FROM attempts a JOIN jobs j USING(job_id) WHERE j.command='vlm-batch02' AND j.status='succeeded' AND a.status='succeeded' AND json_extract(j.config_json,'$.condition_id')=?",(condition,)).fetchall()
    binding=continuation_binding()
    retained=binding[1]['retained'].get(condition) if binding else None
    good=[]
    for attempt,stored,inputs in rows:
        path=output_path(condition,attempt)/'summary.json'
        expected_source=binding[0]['original_source_hash'] if retained else source_hash()
        if retained and attempt!=retained['attempt_id']:
            continue
        if stored==expected_source and json.loads(inputs)==input_contract(condition) and path.is_file():
            s=json.loads(path.read_text())
            result=path.with_name('result.json')
            if (s.get('status')=='succeeded' and s.get('condition_id')==condition and
                result.is_file() and file_hash(result)==s.get('result_sha256')):
                record=json.loads(result.read_text())
                if record.get('status')=='succeeded' and record.get('condition_id')==condition and all(
                    (path.parent/name).is_file() and file_hash(path.parent/name)==expected
                    for name,expected in record.get('artifacts',{}).items()):
                    good.append(attempt)
    return good


def prior_generated_tokens(condition):
    """A decode/persistence failure after generation cannot authorize another generation."""
    import sqlite3
    with sqlite3.connect(f'file:{RUNTIME/"queue.sqlite3"}?mode=ro',uri=True) as db:
        attempts=db.execute("SELECT a.attempt_id FROM attempts a JOIN jobs j USING(job_id) WHERE j.command='vlm-batch02' AND json_extract(j.config_json,'$.condition_id')=?",(condition,)).fetchall()
    return [attempt for (attempt,) in attempts if (output_path(condition,attempt)/'generated_token_ids.npy').is_file()]


def sequence_gate(condition):
    binding=continuation_binding()
    if binding and condition=='v01_full_frame':
        import sys
        from batch02_vlm.continuation import budget
        budget(sys.modules[__name__],binding)
    required=() if condition==SMOKE[0] else SMOKE[:1] if condition==SMOKE[1] else SMOKE
    if binding and condition in ('v02_full_frame','v03_full_frame','v04_full_frame'):
        required=SMOKE+('v01_full_frame',)
    for previous in required:
        if len(successful(previous)) != 1:
            raise ValueError('one exact successful smoke required: '+previous)
    if successful(condition):
        raise ValueError('successful condition must never regenerate')
    if prior_generated_tokens(condition):
        raise ValueError('existing generated tokens require CPU recovery; generation forbidden')


def validate(config,inputs,runtime):
    if (not isinstance(config,dict) or set(config)!={'condition_id','settings'} or
        config['condition_id'] not in CONDITIONS or not same(config['settings'],SETTINGS)):
        raise ValueError('fixed condition/settings required')
    if Path(runtime).resolve()!=RUNTIME or not INTERPRETER.is_file():
        raise ValueError('canonical queue and isolated VLM interpreter required')
    if inputs != input_contract(config['condition_id']):
        raise ValueError('registered VLM input contract differs')
    sequence_gate(config['condition_id'])
    return config['condition_id']


def job_key(condition):
    if condition not in CONDITIONS:
        raise ValueError('unknown condition')
    binding=continuation_binding()
    if binding and condition=='v01_full_frame':
        return binding[0]['correction_job_key']
    return 'batch0002-exp0020-vlm-'+condition


def command(config,inputs,runtime,attempt,lock_fd):
    condition=validate(config,inputs,runtime)
    output_path(condition,attempt)
    return [str(INTERPRETER),'-I',str(ROOT/'batch02_vlm/runner.py'),'--condition',condition,
        '--attempt',attempt,'--lock-fd',str(lock_fd)]


def output_path(condition,attempt):
    if condition not in CONDITIONS or not isinstance(attempt,str) or not re.fullmatch('[0-9a-f]{32}',attempt):
        raise ValueError('invalid VLM output identity')
    return safe_file('outputs/batch0002/vlm/EXP-0020/'+condition+'/'+attempt)
