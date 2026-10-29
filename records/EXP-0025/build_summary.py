# SPDX-License-Identifier: AGPL-3.0-only
"""CPU-only public aggregates from saved Results; outside frozen GPU sources."""
import hashlib
import json
from pathlib import Path
import sqlite3
from orchestration.batch06_pose_command import (ROOT,RUNTIME,LOCAL,MANIFEST,WEIGHT_SHA,CONDITIONS,
    sources,input_contract,cached_records,OLD_SUMMARY_SHA)
from orchestration.queue import digest


def main():
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    matches=list((ROOT/'outputs/batch0006/EXP-0025/comparison').glob('*/summary.json'))
    if len(matches)!=1:raise ValueError('one saved comparison run required')
    path=matches[0];s=json.loads(path.read_text())
    if s['status']!='succeeded' or not s['technical_pass']:raise ValueError('successful exact run required')
    if [r['condition_id'] for r in s['results']]!=list(CONDITIONS):raise ValueError('exact three ordered results required')
    assert s['public_predict_calls']==s['successful_results']==s['sample_model_forward_count']==3
    assert s['sample_model_forward_attempts']==3 and s['warmup_model_forward_count']==s['warmup_model_forward_attempts']==1 and s['model_constructions']==1
    assert digest(sources())==s['registration']['source_hash']
    input_contract();old=cached_records()
    for r in s['results']:
        assert r['input_tensor']['shape']==[1,3,960,960] and r['offset_applications']==1
        for a in r['artifacts'].values():assert sha(ROOT/a['path'])==a['sha256']
    for a in s['comparisons'].values():assert sha(ROOT/a['path'])==a['sha256']
    with sqlite3.connect(f'file:{RUNTIME/"queue.sqlite3"}?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row;before=json.loads((LOCAL/'queue-before.local.json').read_text());preserved={}
        for table,key in [('jobs','job_id'),('attempts','attempt_id')]:
            current={r[key]:dict(r) for r in db.execute('SELECT * FROM '+table)}
            assert all(current.get(r[key])==r for r in before[table]);preserved[table]=len(before[table])
        runs=[dict(r) for r in db.execute("SELECT a.*,j.status AS job_status FROM attempts a JOIN jobs j USING(job_id) WHERE j.command='batch06-pose'")]
        assert len(runs)==1 and runs[0]['attempt_id']==s['attempt_id'] and runs[0]['status']==runs[0]['job_status']=='succeeded'
        queue_wall=runs[0]['finished_at']-runs[0]['started_at']
    folder=ROOT/'records/EXP-0025'
    write=lambda p,d:p.write_text(json.dumps(d,indent=2,sort_keys=True,allow_nan=False)+'\n')
    formal={k:None for k in ('accuracy','precision','recall','f1','false_positive_rate')}
    facts={84:'User: three persons/poses generally good; qualitative, no precise joint GT',90:'User: only rightmost of three detected; its joints misaligned; other two missed',94:'User: one person atop gate and one beyond visible, both missed; no general completion/legal claim'}
    user_review=json.loads((LOCAL/'user-review.local.json').read_text())
    rows=[]
    def aggregate(r):
        return dict(person_rows=r['person_count'],retained_joint_estimates=sum(p['retained_joint_count'] for p in r['persons']),
            unknown_joint_estimates=sum(k['observed_xy'] is None for p in r['persons'] for k in p['keypoints']),
            technical_status='normal_pose_results' if r['person_count'] else 'normal_empty_results',
            actual_input_tensor={k:r['input_tensor'][k] for k in ('shape','dtype','device','sha256')},
            architecture=r['architecture'],artifact_sha256={k:a['sha256'] for k,a in r['artifacts'].items()})
    for r in sorted(s['results'],key=lambda r:r['pts_seconds']):
        prior=old[r['frame_id']]
        rows.append(dict(pts_seconds=r['pts_seconds'],native_pts=r['native_pts'],time_base=r['time_base'],
            cached640=aggregate(prior),new960=aggregate(r),baseline_user_review=facts[int(r['pts_seconds'])],
            new960_user_review=user_review['facts'][str(int(r['pts_seconds']))],
            new960_person_correspondence={84:'user qualitative good; exact row/person correspondence not annotated',90:'normal empty; no useful pose evidence',94:'user: gate-top person detected; already-across person missed'}[int(r['pts_seconds'])],
            new960_joint_correspondence={84:'user qualitative good; individual wrist/hip/knee/ankle GT unavailable',90:'no output joints; quality remains insufficient',94:'user qualitative good for gate-top person; individual joint GT unavailable'}[int(r['pts_seconds'])],
            count_change_is_quality_improvement=False))
    comparison=dict(schema_version=1,experiment_id='EXP-0025',batch='BATCH-0006',execution_status='succeeded',adoption='adopt_on_hold',
        code_sha=s['registration']['code_sha'],source_sha256=s['registration']['source_hash'],manifest_sha256=sha(MANIFEST),checkpoint_sha256=WEIGHT_SHA,
        stage_summary_sha256=sha(path),cached_summary_sha256=OLD_SUMMARY_SHA,attempt_id=s['attempt_id'],job_id=s['registration']['job_id'],
        public_predict_calls=3,new_native_results=3,cached_native_results=3,baseline_new_predict_calls=0,model_constructions=1,
        sample_model_forward_attempts=3,sample_model_forward_returns=3,warmup_model_forward_attempts=1,warmup_model_forward_returns=1,
        errors=0,retries=0,new_checkpoints=0,new_environments=0,training=False,changed_predict_kwargs=['imgsz'],frames=rows,
        behavioral_validation='unmeasured',formal_behavior_metrics=formal,rule_status='not_run',tracker_status='not_run',
        person_joint_quality='User qualitative good84 and gate-top94; no useful90 pose and already-across94 missed. No precise person/joint GT; no overall success/adoption claim',
        user_review_source=user_review['source'],user_review_summary_sha256=sha(LOCAL/'user-review.local.json'),
        original_native_rows_preserved=preserved,comparison_image_sha256={k:a['sha256'] for k,a in s['comparisons'].items()},
        scope='Three fixed paired native PTS of one development scene. Three cached640 Results, no640 rerun, three new960 calls. No precise GT or adoption/behavior performance claim.')
    write(folder/'comparison.json',comparison)
    scope=('Three-call instrumented diagnostic, not throughput. First960 call is90s and contains setup/fuse/warmup; cached640 90s was first in a five-call prior run, 84/94 later. '
        'Historical640 costs belong to EXP-0023, zero new640 GPU inference. Whole960 three-call and historical640 five-call run totals have different scopes; do not directly benchmark them or derive FPS. '
        'Constructor excludes predictor setup/fuse/CUDA transfer. Official setup/warmup/network timings overlap and cannot be summed. Warmup includes one model forward plus synthetic random-box NMS, separate from sample predictions. '
        'Results.speed and public wall include profiler/synchronization/tensor capture overhead in different scopes. Frame wall also includes RGB verification/native serialization. '
        'Run-entry includes lease/input validation and image creation, excludes interpreter startup/final summary save; queue wall includes supervisor validation/startup. Allocator reset after imports; device-wide samples include other processes.')
    def cost(r):
        return dict(pts_seconds=r['pts_seconds'],input_read_convert_verify_seconds=r['input_read_convert_verify_seconds'],tensor_capture_save_seconds=r['input_tensor']['capture_save_seconds'],
            results_speed_ms=r['results_speed_ms'],official_events=r['official_events'],public_predict_wall_seconds=r['public_predict_wall_seconds'],frame_wall_seconds=r.get('frame_wall_seconds'))
    samples=[[float(x.strip()) for x in v['values'].split(',')] for v in s['device_samples']]
    costs=dict(experiment_id='EXP-0025',constructor_checkpoint_cpu_seconds=s['model_construction_load_seconds'],
        official_setup_model_seconds=sum(e['seconds'] for r in s['results'] for e in r['official_events'] if e['stage']=='setup_model'),
        official_warmup_seconds=sum(e['seconds'] for r in s['results'] for e in r['official_events'] if e['stage']=='warmup'),
        official_warmup_model_forward_seconds=sum(e['seconds'] for r in s['results'] for e in r['official_events'] if e['stage']=='network_predict' and e['warmup']),
        run_entry_wall_seconds=s['run_entry_wall_seconds'],queue_attempt_wall_seconds=queue_wall,
        allocator_peak_allocated_bytes=s['allocator_peak_allocated_bytes'],allocator_peak_reserved_bytes=s['allocator_peak_reserved_bytes'],free_vram_before_load_mib=s['resource_gate']['free_mib'],
        new960_predictions=[cost(r) for r in s['results']],
        cached640_predictions=[dict(cost(old[r['frame_id']]),new_predict_calls=0,new_gpu_inference_seconds=0,charged_to='EXP-0023 historical only') for r in s['results']],
        device_wide_sample_count=len(samples),device_wide_max_sampled_used_mib=max(v[0] for v in samples) if samples else None,
        device_wide_min_sampled_free_mib=min(v[1] for v in samples) if samples else None,device_sampler_errors=len(s['device_sample_errors']),inference_fps=None,scope=scope)
    write(folder/'costs.json',costs)
    metrics=[]
    def add(label,value,unit,source,pointer,n=1,context=None):
        metrics.append(dict(label=label,value=value,unit=unit,sample_n=n,source='records/EXP-0025/'+source,source_pointer=pointer,source_sha256=sha(folder/source),scope=context or scope,verification='saved_native_results_and_exact_queue_receipt'))
    for key,unit,n in [('public_predict_calls','calls',3),('new_native_results','results',3),('cached_native_results','results',3),('baseline_new_predict_calls','calls',3),('model_constructions','loads',1),('sample_model_forward_returns','forwards',3),('warmup_model_forward_returns','forwards',1)]:add(key,comparison[key],unit,'comparison.json',[key],n)
    for key,unit in [('constructor_checkpoint_cpu_seconds','seconds'),('official_setup_model_seconds','seconds'),('official_warmup_seconds','seconds'),('run_entry_wall_seconds','seconds'),('queue_attempt_wall_seconds','seconds'),('allocator_peak_allocated_bytes','bytes'),('allocator_peak_reserved_bytes','bytes'),('free_vram_before_load_mib','MiB')]:add(key,costs[key],unit,'costs.json',[key])
    for i,r in enumerate(rows):
        for resolution in ('cached640','new960'):
            for key,unit in [('person_rows','rows'),('retained_joint_estimates','estimated joints'),('unknown_joint_estimates','estimated joints')]:add(str(r['pts_seconds'])+' '+resolution+' '+key,r[resolution][key],unit,'comparison.json',['frames',i,resolution,key],1,'Model output counts, not precise person/joint GT; user qualitative appraisal recorded separately')
    for i,r in enumerate(costs['new960_predictions']):
        for phase in ('preprocess','inference','postprocess'):add(str(r['pts_seconds'])+' new960 '+phase,r['results_speed_ms'][phase],'ms','costs.json',['new960_predictions',i,'results_speed_ms',phase])
    for key in formal:add(key,None,'unmeasured','comparison.json',['formal_behavior_metrics',key],0,'No precise person/joint/action GT; behavior unmeasured')
    write(folder/'metrics.json',dict(schema_version=1,experiment_id='EXP-0025',comparison_group='EXP-0025',comparison_source='records/EXP-0025/comparison.json',comparison_sha256=sha(folder/'comparison.json'),
        execution_status='succeeded',adoption='adopt_on_hold',behavioral_validation='unmeasured',cross_experiment_comparable=False,formal_behavior_metrics=formal,scope=comparison['scope'],metrics=metrics,
        source_bindings=dict(execution_commits=[s['registration']['code_sha']],stage_summary_sha256=[sha(path)],manifest_sha256=sha(MANIFEST),checkpoint_sha256=WEIGHT_SHA,report_builder_sha256=sha(Path(__file__)))))
    write(LOCAL/'preservation-final.json',dict(original_native_rows_preserved=preserved,source_unchanged=True,all_frozen_inputs_environment_checked=True,artifact_hashes_verified=True))
    print(json.dumps(dict(status='public aggregates built',new_predictions=3,cached_results=3,metrics=len(metrics),source_unchanged=True),sort_keys=True))


if __name__=='__main__':main()
