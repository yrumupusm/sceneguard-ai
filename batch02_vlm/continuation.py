"""One exact EXP-0020 metadata correction, preserving the original 33 settled rows."""
import json
import sqlite3
from pathlib import Path

ORIGINAL_COMMIT='952c52fdb3786ab0ae306562d3dfbeaca4e5d7bd'
ORIGINAL_SOURCE='76c9322a6c8ff5e208b209e757f517fda385e6bb84aed35bbaab6b4cc85f35a7'
HISTORY_SHA='a1ffae8a95be5dee1a7628837a8cfe351a41f6f0a70892cf6aac7edcd5c25f32'
FAILED_JOB='0b9a0a852237499f8846aa3563f0e10f'
FAILED_ATTEMPT='c3ae75c0bcdc4ce0af2cfb4a694edd1b'
CONDITION='v01_full_frame'
RETRY_KEY='batch0002-exp0020-vlm-v01_full_frame-retry1'
Q=tuple(f'q{i:02}_{view}' for i in range(1,7) for view in ('B','C'))


def state(command,db=None):
    if db is None:
        with sqlite3.connect(f'file:{command.RUNTIME/"queue.sqlite3"}?mode=ro',uri=True) as connection:
            return state(command,connection)
    db.row_factory=sqlite3.Row
    return dict(jobs=[dict(r) for r in db.execute('SELECT * FROM jobs')],
                attempts=[dict(r) for r in db.execute('SELECT * FROM attempts')])


def verify_history(history,current):
    for table,key in (('jobs','job_id'),('attempts','attempt_id')):
        actual={r[key]:r for r in current[table]}
        for old in history[table]:
            if actual.get(old[key])!=old:
                raise ValueError('immutable prior '+table+' row differs')


def load(command):
    path=command.ROOT/'configs/batch0002_vlm_continuation.json'
    if not path.exists():return None
    d=json.loads(path.read_text())
    expected=dict(schema_version=1,experiment='EXP-0020',reason='v-only historical RGB metadata compatibility',
        original_commit=ORIGINAL_COMMIT,original_source_hash=ORIGINAL_SOURCE,
        history_snapshot_sha256=HISTORY_SHA,failed_job_id=FAILED_JOB,failed_attempt_id=FAILED_ATTEMPT,
        correction_condition=CONDITION,correction_job_key=RETRY_KEY,maximum_logical_attempts=2)
    if not command.same({k:d.get(k) for k in expected},expected) or set(d)!=set(expected)|{'receipt_sha256'}:
        raise ValueError('only the exact EXP0020 metadata continuation is registered')
    receipt_path=command.LOCAL/'continuation-receipt.json';history_path=command.LOCAL/'before-metadata-correction-queue.json'
    if command.file_hash(receipt_path)!=d['receipt_sha256'] or command.file_hash(history_path)!=HISTORY_SHA:
        raise ValueError('pinned continuation receipt/history hash differs')
    receipt=json.loads(receipt_path.read_text());history=json.loads(history_path.read_text())
    if len(history['jobs'])!=33 or len(history['attempts'])!=33 or set(receipt['retained'])!=set(Q):
        raise ValueError('exact33 prior rows and12 retained q successes required')
    current=state(command);verify_history(history,current)
    jobs={j['job_id']:j for j in history['jobs']};attempts={a['attempt_id']:a for a in history['attempts']}
    for condition,entry in receipt['retained'].items():
        j=jobs[entry['job_id']];a=attempts[entry['attempt_id']]
        if (a['job_id']!=j['job_id'] or a['status']!='succeeded' or j['status']!='succeeded' or
            j['command']!='vlm-batch02' or json.loads(j['config_json'])!=dict(condition_id=condition,settings=command.SETTINGS) or
            j['source_hash']!=ORIGINAL_SOURCE or j['code_sha']!=ORIGINAL_COMMIT):
            raise ValueError('retained success source/lineage/settings differ')
        folder=command.output_path(condition,a['attempt_id'])
        summary=json.loads((folder/'summary.json').read_text());result=json.loads((folder/'result.json').read_text())
        if (command.file_hash(folder/'summary.json')!=entry['summary_sha256'] or
            command.file_hash(folder/'result.json')!=entry['result_sha256'] or
            summary['result_sha256']!=entry['result_sha256'] or result['artifacts']!=entry['artifacts'] or
            result['condition_id']!=condition or result['status']!='succeeded' or
            command.file_hash(command.RUNTIME/'attempts'/a['attempt_id']/'manifest.json')!=entry['queue_manifest_sha256']):
            raise ValueError('retained success output/queue receipt differs')
        for name,sha in entry['artifacts'].items():
            if Path(name).name!=name or command.file_hash(folder/name)!=sha:
                raise ValueError('retained success artifact differs')
    failed=receipt['failed'];j=jobs[FAILED_JOB];a=attempts[FAILED_ATTEMPT]
    if (failed['job_id']!=FAILED_JOB or failed['attempt_id']!=FAILED_ATTEMPT or
        a['job_id']!=FAILED_JOB or a['status']!='failed' or j['status']!='failed' or
        j['source_hash']!=ORIGINAL_SOURCE or j['code_sha']!=ORIGINAL_COMMIT or
        json.loads(j['config_json'])!=dict(condition_id=CONDITION,settings=command.SETTINGS)):
        raise ValueError('exact original failed v01 lineage required')
    folder=command.output_path(CONDITION,FAILED_ATTEMPT)
    for name,sha in failed['artifacts'].items():
        if Path(name).name!=name or command.file_hash(folder/name)!=sha:
            raise ValueError('original failed artifact differs')
    if (command.file_hash(command.RUNTIME/'attempts'/FAILED_ATTEMPT/'manifest.json')!=failed['queue_manifest_sha256'] or
        (folder/'generated_token_ids.npy').exists()):
        raise ValueError('original failed v01 receipt/tokens differ')
    return d,receipt,history,current


def budget(command,binding):
    d,receipt,history,current=binding
    linked=[j for j in current['jobs'] if j['command']=='vlm-batch02' and json.loads(j['config_json']).get('condition_id')==CONDITION]
    if any(j['job_id']!=FAILED_JOB and j['job_key']!=RETRY_KEY for j in linked) or len(linked)>2:
        raise ValueError('unregistered v01 correction lineage')
    identities={j['job_id'] for j in linked};attempts=[a for a in current['attempts'] if a['job_id'] in identities]
    reserved=len(attempts)+sum(j['status']=='queued' for j in linked)
    if len(attempts)>2 or reserved>2:
        raise ValueError('v01 maximum two logical attempts including queued work')
    for j in linked:
        if j['job_id']!=FAILED_JOB:
            if j['source_hash']!=command.source_hash() or j['code_sha']!=json.loads((command.LOCAL/'execution-authorization.json').read_text())['source_commit']:
                raise ValueError('correction requires exact current frozen source')
            if j['status'] not in ('queued','running','succeeded'):
                raise ValueError('v01 correction exhausted its single logical retry')



def retry_guard(command,db,row):
    """Called under Queue.retry's existing transaction; never change a row here."""
    binding=load(command)
    if binding is None:return
    verify_history(binding[2],state(command,db))
    condition=json.loads(row['config_json']).get('condition_id')
    if condition==CONDITION or row['job_id']==FAILED_JOB or row['job_key']==RETRY_KEY:
        raise ValueError('EXP0020 v01 correction is its sole logical retry; old/correction jobs cannot retry')
    if command.prior_generated_tokens(condition):
        raise ValueError('saved generated tokens require CPU recovery; no retry generation')
