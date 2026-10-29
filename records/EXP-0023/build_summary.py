# SPDX-License-Identifier: AGPL-3.0-only
"""CPU extraction of the sole saved run; outside frozen inference sources."""
import hashlib
import json
from pathlib import Path
import sqlite3
from orchestration.batch05_pose_command import (ROOT,RUNTIME,LOCAL,MANIFEST,WEIGHT_SHA,CONDITIONS,
    sources,input_contract,cached_record)
from orchestration.queue import digest


def main():
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    matches=list((ROOT/'outputs/batch0005/EXP-0023/comparison').glob('*/summary.json'))
    if len(matches)!=1:raise ValueError('one saved comparison run required')
    path=matches[0];s=json.loads(path.read_text())
    if s['status']!='succeeded' or not s['technical_pass']:raise ValueError('successful exact run required')
    if [r['condition_id'] for r in s['results']]!=list(CONDITIONS):raise ValueError('exact five ordered results required')
    assert s['public_predict_calls']==s['successful_results']==s['sample_model_forward_count']==5
    assert s['warmup_model_forward_count']==1 and s['model_constructions']==1
    assert digest(sources())==s['registration']['source_hash']
    input_contract()
    old=cached_record()
    for r in s['results']:
        for a in r['artifacts'].values():assert sha(ROOT/a['path'])==a['sha256']
    for a in s['comparisons'].values():assert sha(ROOT/a['path'])==a['sha256']
    with sqlite3.connect(f'file:{RUNTIME/"queue.sqlite3"}?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        before=json.loads((LOCAL/'queue-before.local.json').read_text())
        preserved={}
        for table,key in [('jobs','job_id'),('attempts','attempt_id')]:
            current={r[key]:dict(r) for r in db.execute('SELECT * FROM '+table)}
            assert all(current.get(r[key])==r for r in before[table]);preserved[table]=len(before[table])
        runs=[dict(r) for r in db.execute("SELECT a.*,j.status AS job_status FROM attempts a JOIN jobs j USING(job_id) WHERE j.command='batch05-pose'")]
        assert len(runs)==1 and runs[0]['attempt_id']==s['attempt_id'] and runs[0]['status']==runs[0]['job_status']=='succeeded'
        queue_wall=runs[0]['finished_at']-runs[0]['started_at']
    write=lambda p,d:p.write_text(json.dumps(d,indent=2,sort_keys=True,allow_nan=False)+'\n')
    folder=ROOT/'records/EXP-0023'
    formal={k:None for k in ('accuracy','precision','recall','f1','false_positive_rate')}
    rows=[]
    for r in s['results']+[dict(old,condition_id='030_090_full',view='full',cached=True)]:
        rows.append(dict(condition_id=r['condition_id'],frame_id=r['frame_id'],view=r['view'],native_pts=r['native_pts'],time_base=r['time_base'],pts_seconds=r['pts_seconds'],
            provenance='EXP-0022 cached; zero new prediction cost' if r.get('cached') else 'EXP-0023 new prediction',
            person_rows=r['person_count'],retained_joint_estimates=sum(p['retained_joint_count'] for p in r['persons']),
            unknown_joint_estimates=sum(k['observed_xy'] is None for p in r['persons'] for k in p['keypoints']),
            technical_status='normal_pose_results' if r['person_count'] else 'normal_empty_results',
            actual_input_tensor={k:r['input_tensor'][k] for k in ('shape','dtype','device','sha256')},architecture=r['architecture'],
            visual_correspondence='unreviewed; counts are not people/joint GT',
            artifact_sha256={k:a['sha256'] for k,a in r['artifacts'].items()}))
    rows.sort(key=lambda r:(r['pts_seconds'],r['view']!='full'))
    comparison=dict(schema_version=1,experiment_id='EXP-0023',batch='BATCH-0005',execution_status='succeeded',adoption='adopt_on_hold',
        code_sha=s['registration']['code_sha'],source_sha256=s['registration']['source_hash'],manifest_sha256=sha(MANIFEST),checkpoint_sha256=WEIGHT_SHA,
        stage_summary_sha256=sha(path),attempt_id=s['attempt_id'],job_id=s['registration']['job_id'],
        public_predict_calls=5,new_native_results=5,cached_native_results=1,model_constructions=1,
        sample_model_forward_attempts=s['sample_model_forward_attempts'],sample_model_forward_returns=s['sample_model_forward_count'],
        warmup_model_forward_attempts=s['warmup_model_forward_attempts'],warmup_model_forward_returns=s['warmup_model_forward_count'],
        errors=0,retries=0,new_checkpoints=0,new_environments=0,training=False,frames=rows,
        behavioral_validation='unmeasured',formal_behavior_metrics=formal,rule_status='not_run',tracker_status='not_run',
        person_joint_quality='unreviewed; fixed ROI output counts do not confirm actual body/joint correspondence',
        original_native_rows_preserved=preserved,comparison_image_sha256={k:a['sha256'] for k,a in s['comparisons'].items()},
        scope='Three fixed native times full/C6 diagnostic. Five new calls and one historical cached empty Results. No GT, behavior accuracy, calibrated fence, or adoption claim.')
    write(folder/'comparison.json',comparison)
    scope=('One instrumented five-call diagnostic, not throughput benchmark. Constructor excludes first predictor setup/fuse/CUDA preparation. '
        'Setup/warmup/network events overlap and must not be summed. Warmup contains actual-input model forward plus synthetic random-box NMS, excluded from five predictions and Results.speed. '
        'Results.speed preprocess includes profiler/synchronization and tensor CPU capture/save; public predict wall includes first setup/warmup/observer saves; frame wall includes RGB validation and native Results serialization. '
        'Run-entry includes lease/input validation and final comparison PNG creation, excludes interpreter startup/final summary save; queue wall includes supervisor validation/startup. '
        'Allocator reset after imports before constructor; device-wide samples include other processes. Cached full90 historical costs are not new cost. No general FPS or real-time claim.')
    def cost(r):
        return dict(condition_id=r['condition_id'],input_read_convert_verify_seconds=r['input_read_convert_verify_seconds'],
            tensor_capture_save_seconds=r['input_tensor']['capture_save_seconds'],results_speed_ms=r['results_speed_ms'],official_events=r['official_events'],
            public_predict_wall_seconds=r['public_predict_wall_seconds'],frame_wall_seconds=r.get('frame_wall_seconds'))
    samples=[[float(x.strip()) for x in v['values'].split(',')] for v in s['device_samples']]
    costs=dict(experiment_id='EXP-0023',constructor_checkpoint_cpu_seconds=s['model_construction_load_seconds'],
        official_setup_model_seconds=sum(e['seconds'] for r in s['results'] for e in r['official_events'] if e['stage']=='setup_model'),
        official_warmup_seconds=sum(e['seconds'] for r in s['results'] for e in r['official_events'] if e['stage']=='warmup'),
        official_warmup_model_forward_seconds=sum(e['seconds'] for r in s['results'] for e in r['official_events'] if e['stage']=='network_predict' and e['warmup']),
        run_entry_wall_seconds=s['run_entry_wall_seconds'],queue_attempt_wall_seconds=queue_wall,
        allocator_peak_allocated_bytes=s['allocator_peak_allocated_bytes'],allocator_peak_reserved_bytes=s['allocator_peak_reserved_bytes'],
        free_vram_before_load_mib=s['resource_gate']['free_mib'],new_predictions=[cost(r) for r in s['results']],
        cached_prediction=dict(condition_id='030_090_full',new_predict_calls=0,new_gpu_inference_seconds=0,
            historical_results_speed_ms=old['results_speed_ms'],historical_public_predict_wall_seconds=old['public_predict_wall_seconds'],charged_to='EXP-0022 only'),
        device_wide_sample_count=len(samples),device_wide_max_sampled_used_mib=max(v[0] for v in samples) if samples else None,
        device_wide_min_sampled_free_mib=min(v[1] for v in samples) if samples else None,device_sampler_errors=len(s['device_sample_errors']),
        inference_fps=None,scope=scope)
    write(folder/'costs.json',costs)
    metrics=[]
    def add(label,value,unit,source,pointer,n=1,context=None):
        metrics.append(dict(label=label,value=value,unit=unit,sample_n=n,source='records/EXP-0023/'+source,source_pointer=pointer,
            source_sha256=sha(folder/source),scope=context or scope,verification='saved_native_results_and_exact_queue_receipt'))
    for key,unit,n in [('public_predict_calls','calls',5),('new_native_results','results',5),('cached_native_results','results',1),('model_constructions','loads',1),('sample_model_forward_returns','forwards',5),('warmup_model_forward_returns','forwards',1)]:
        add(key,comparison[key],unit,'comparison.json',[key],n)
    for key,unit in [('constructor_checkpoint_cpu_seconds','seconds'),('official_setup_model_seconds','seconds'),('official_warmup_seconds','seconds'),('run_entry_wall_seconds','seconds'),('queue_attempt_wall_seconds','seconds'),('allocator_peak_allocated_bytes','bytes'),('allocator_peak_reserved_bytes','bytes'),('free_vram_before_load_mib','MiB')]:
        add(key,costs[key],unit,'costs.json',[key])
    for i,r in enumerate(rows):
        for key,unit in [('person_rows','rows'),('retained_joint_estimates','estimated joints'),('unknown_joint_estimates','estimated joints')]:
            add(r['condition_id']+' '+key,r[key],unit,'comparison.json',['frames',i,key],1,'Model output diagnostic; actual human/joint correspondence unreviewed; not GT')
    for i,r in enumerate(costs['new_predictions']):
        for phase in ('preprocess','inference','postprocess'):
            add(r['condition_id']+' '+phase,r['results_speed_ms'][phase],'ms','costs.json',['new_predictions',i,'results_speed_ms',phase])
    for key in formal:add(key,None,'unmeasured','comparison.json',['formal_behavior_metrics',key],0,'No person/joint/action GT; behavior performance unmeasured')
    write(folder/'metrics.json',dict(schema_version=1,experiment_id='EXP-0023',comparison_group='EXP-0023',comparison_source='records/EXP-0023/comparison.json',
        comparison_sha256=sha(folder/'comparison.json'),execution_status='succeeded',adoption='adopt_on_hold',behavioral_validation='unmeasured',cross_experiment_comparable=False,
        formal_behavior_metrics=formal,scope=comparison['scope'],metrics=metrics,
        source_bindings=dict(execution_commits=[s['registration']['code_sha']],stage_summary_sha256=[sha(path)],manifest_sha256=sha(MANIFEST),checkpoint_sha256=WEIGHT_SHA,report_builder_sha256=sha(Path(__file__)))))
    write(LOCAL/'preservation-final.json',dict(original_native_rows_preserved=preserved,source_unchanged=True,all_frozen_inputs_environment_checked=True,artifact_hashes_verified=True))
    print(json.dumps(dict(status='public aggregates built',new_predictions=5,cached_results=1,metrics=len(metrics),source_unchanged=True),sort_keys=True))


if __name__=='__main__':main()
