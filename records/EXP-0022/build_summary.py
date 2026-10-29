# SPDX-License-Identifier: AGPL-3.0-only
"""CPU-only report extraction from the one observed smoke; no model/media viewing."""
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
from orchestration.batch04_pose_command import ROOT, RUNTIME, LOCAL, MANIFEST, WEIGHT_SHA, sources, input_contract
from orchestration.queue import digest

ATTEMPT='6509c805b40e4d7a8137f770cfa04a05'
base=ROOT/'outputs/batch0004/EXP-0022/smoke'/ATTEMPT
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
s=json.loads((base/'summary.json').read_text())
assert s['status']=='succeeded' and s['technical_pass'] is True
assert [r['frame_id'] for r in s['results']]==['030_090','007_064']
assert s['public_predict_calls']==s['successful_results']==2
assert s['sample_model_forward_count']==2 and s['warmup_model_forward_count']==1
assert digest(sources())==s['registration']['source_hash']
input_contract('smoke')  # Complete historical RGB/source/checkpoint/environment parity, no model.
with sqlite3.connect(f'file:{RUNTIME/"queue.sqlite3"}?mode=ro',uri=True) as db:
 db.row_factory=sqlite3.Row
 old=json.loads((LOCAL/'queue-before.local.json').read_text())
 preservation={}
 for table,key in [('jobs','job_id'),('attempts','attempt_id')]:
  current={r[key]:dict(r) for r in db.execute('SELECT * FROM '+table)}
  assert all(current.get(r[key])==r for r in old[table])
  preservation[table]=len(old[table])
 row=db.execute('SELECT * FROM attempts WHERE attempt_id=?',(ATTEMPT,)).fetchone()
 queue_wall=row['finished_at']-row['started_at']
 all_new=[dict(r) for r in db.execute("SELECT job_key,status FROM jobs WHERE command='batch04-pose'")]
 assert len(all_new)==1 and all_new[0]['status']=='succeeded'
# Original source/report/config/records bytes remain equal to the pre-BATCH4 tree.
code=s['registration']['code_sha']
pre=subprocess.check_output(['git','rev-parse',code+'^'],cwd=ROOT,text=True).strip()
legacy=subprocess.check_output(['git','ls-tree','-r','--name-only',pre],cwd=ROOT,text=True).splitlines()
legacy=[n for n in legacy if n.startswith(('batch03_pose/','records/EXP-00','docs/experiments/EXP-00')) or n in ('configs/batch0003_pose_manifest.json','requirements-pose-batch03-lock.txt','orchestration/batch03_pose_command.py','docs/decisions/ADR-0020-yolo26m-pose.md')]
for name in legacy:
 assert (ROOT/name).read_bytes()==subprocess.check_output(['git','show',pre+':'+name],cwd=ROOT)
artifacts={}
for r in s['results']:
 for label,a in r['artifacts'].items():
  assert sha(ROOT/a['path'])==a['sha256']
 artifacts[r['frame_id']]={k:v['sha256'] for k,v in r['artifacts'].items()}
write=lambda p,d:p.write_text(json.dumps(d,indent=2,sort_keys=True,allow_nan=False)+'\n')
write(LOCAL/'preservation-final.json',dict(original_native_rows=preservation,legacy_public_files=len(legacy),legacy_bytes_unchanged=True,
 source_digest=digest(sources()),source_unchanged=True,all_frozen_inputs_environment_checked=True,new_jobs=all_new,artifact_hashes_verified=True))
formal={k:None for k in ('accuracy','precision','recall','f1','false_positive_rate')}
frames=[]
for r in s['results']:
 frames.append(dict(frame_id=r['frame_id'],source_id=r['source_id'],native_pts=r['native_pts'],time_base=r['time_base'],pts_seconds=r['pts_seconds'],
  person_rows=r['person_count'],retained_joint_estimates=sum(p['retained_joint_count'] for p in r['persons']),
  technical_status='normal_empty_results' if not r['person_count'] else 'normal_pose_results',
  actual_input_tensor={k:r['input_tensor'][k] for k in ('shape','dtype','device','sha256')},
  architecture=r['architecture'],visual_correspondence='unreviewed',original_overlay_hash_equal=r['artifacts']['original']['sha256']==r['artifacts']['overlay']['sha256'],
  artifacts_sha256=artifacts[r['frame_id']]))
scopes=('One instrumented two-frame diagnostic, not throughput/quality benchmark. CPU YOLO checkpoint constructor+sync excludes first predictor deepcopy/fuse/CUDA setup. '
 'Official stage observations use Python profiler and CUDA synchronization; setup/warmup return None by contract, not failures. '
 'Warmup includes one actual-input model forward and synthetic random-box NMS, excluded from sample predictions and Results.speed. '
 'Results.speed preprocess includes observer tensor copy/save and synchronization; inference/postprocess retain profiler overhead. '
 'Public predict wall includes setup/first warmup/metadata save; frame wall also source read/verification/native Results and PNG/JSON save. '
 'Run-entry includes lease/input validation but excludes interpreter startup/final summary save; queue attempt includes parent validation/child startup. '
 'Allocator reset after imports before constructor through final frame; device-wide samples include other processes and are sampled, not exact peaks. '
 'Nested network/warmup/inference observations overlap; never sum them as disjoint wall.')
comparison=dict(schema_version=1,experiment_id='EXP-0022',batch='BATCH-0004',execution_status='succeeded',adoption='adopt_on_hold',
 code_sha=code,source_sha256=s['registration']['source_hash'],manifest_sha256=sha(MANIFEST),checkpoint_sha256=WEIGHT_SHA,
 stage_summary_sha256=sha(base/'summary.json'),attempt_id=ATTEMPT,job_id=s['registration']['job_id'],
 planned_unique_frames=267,completed_unique_frames=2,remaining_frames=265,remaining_status='held_not_enqueued;030_090 has no pose despite prior user-confirmed people/climbing;007_064 correspondence unreviewed',
 public_predict_calls=2,sample_model_forward_attempts=s['sample_model_forward_attempts'],sample_model_forward_returns=2,
 warmup_model_forward_attempts=s['warmup_model_forward_attempts'],warmup_model_forward_returns=1,logical_smoke_attempts=1,logical_retry_consumed=False,
 model_constructions=1,new_checkpoints=0,new_environments=0,training=False,frames=frames,
 person_joint_quality='030_090 no pose evidence despite prior user-confirmed people/climbing;007_064 unreviewed; counts/confidence do not establish human correspondence',behavioral_validation='unmeasured',
 rule_status='not_run',tracker_status='not_run',formal_behavior_metrics=formal,
 original_queue_rows_preserved=preservation,legacy_public_files_preserved=len(legacy),
 scope='Technical public API smoke only; normal zero-person output at030_090 and two pose rows at007_064 are not person recovery/behavior accuracy',timing_scope=scopes)
folder=ROOT/'records/EXP-0022';folder.mkdir(exist_ok=True)
write(folder/'comparison.json',comparison)
frame_costs=[]
for r in s['results']:
 frame_costs.append(dict(frame_id=r['frame_id'],input_read_convert_verify_seconds=r['input_read_convert_verify_seconds'],
  tensor_capture_save_seconds=r['input_tensor']['capture_save_seconds'],results_speed_ms=r['results_speed_ms'],
  official_events=r['official_events'],public_predict_wall_seconds=r['public_predict_wall_seconds'],frame_wall_seconds=r['frame_wall_seconds']))
values=[]
for sample in s['device_samples']:
 vals=[float(x.strip()) for x in sample['values'].split(',')]
 values.append(vals)
costs=dict(experiment_id='EXP-0022',constructor_checkpoint_cpu_seconds=s['model_construction_load_seconds'],
 initial_validation_seconds=s['initial_validation_seconds'],run_entry_wall_seconds=s['run_entry_wall_seconds'],queue_attempt_wall_seconds=queue_wall,
 allocator_peak_allocated_bytes=s['allocator_peak_allocated_bytes'],allocator_peak_reserved_bytes=s['allocator_peak_reserved_bytes'],
 free_vram_before_load_mib=s['resource_gate']['free_mib'],frames=frame_costs,
 official_setup_model_seconds=sum(e['seconds'] for r in s['results'] for e in r['official_events'] if e['stage']=='setup_model'),
 official_warmup_seconds=sum(e['seconds'] for r in s['results'] for e in r['official_events'] if e['stage']=='warmup'),
 official_warmup_model_forward_seconds=sum(e['seconds'] for r in s['results'] for e in r['official_events'] if e['stage']=='network_predict' and e['warmup']),
 device_wide_sample_count=len(values),device_wide_max_sampled_used_mib=max(v[0] for v in values) if values else None,
 device_wide_min_sampled_free_mib=min(v[1] for v in values) if values else None,device_sampler_errors=len(s['device_sample_errors']),
 inference_fps=None,scope=scopes)
write(folder/'costs.json',costs)
metrics=[]
def add(label,value,unit,source,pointer,n=1,scope=None):
 metrics.append(dict(label=label,value=value,unit=unit,sample_n=n,source='records/EXP-0022/'+source,
  source_pointer=pointer,source_sha256=sha(folder/source),scope=scope or scopes,verification='saved_native_results_summary_and_exact_queue_receipt'))
for key,unit in [('completed_unique_frames','frames'),('public_predict_calls','calls'),('sample_model_forward_returns','forwards'),('warmup_model_forward_returns','forwards')]:
 add(key,comparison[key],unit,'comparison.json',[key],1 if key=='warmup_model_forward_returns' else 2)
for key,unit in [('constructor_checkpoint_cpu_seconds','seconds'),('official_setup_model_seconds','seconds'),('official_warmup_seconds','seconds'),('run_entry_wall_seconds','seconds'),('queue_attempt_wall_seconds','seconds'),('allocator_peak_allocated_bytes','bytes'),('allocator_peak_reserved_bytes','bytes'),('free_vram_before_load_mib','MiB')]:
 add(key,costs[key],unit,'costs.json',[key])
for i,r in enumerate(frames):
 for key,unit in [('person_rows','rows'),('retained_joint_estimates','estimated joints')]:
  add(r['frame_id']+' '+key,r[key],unit,'comparison.json',['frames',i,key],1,'Model output only; unreviewed person/joint correspondence, not GT or accuracy')
 for phase in ('preprocess','inference','postprocess'):
  add(r['frame_id']+' '+phase,frame_costs[i]['results_speed_ms'][phase],'ms','costs.json',['frames',i,'results_speed_ms',phase])
for key in formal:
 add(key,None,'unmeasured','comparison.json',['formal_behavior_metrics',key],0,'No person/joint/action GT; no formal performance metric')
write(folder/'metrics.json',dict(schema_version=1,experiment_id='EXP-0022',comparison_group='EXP-0022',comparison_source='records/EXP-0022/comparison.json',
 comparison_sha256=sha(folder/'comparison.json'),execution_status='succeeded',adoption='adopt_on_hold',behavioral_validation='unmeasured',
 cross_experiment_comparable=False,formal_behavior_metrics=formal,scope=comparison['scope'],metrics=metrics,
 source_bindings=dict(execution_commits=[code],stage_summary_sha256=[comparison['stage_summary_sha256']],manifest_sha256=comparison['manifest_sha256'],
 checkpoint_sha256=WEIGHT_SHA,report_builder_sha256=sha(Path(__file__)))))
print(json.dumps(dict(status='public aggregate built',historical_native_rows_preserved=preservation,legacy_public_files_preserved=len(legacy),
 source_unchanged=True,metrics=len(metrics),comparison_sha256=sha(folder/'comparison.json'),costs_sha256=sha(folder/'costs.json'),metrics_sha256=sha(folder/'metrics.json')),sort_keys=True))
