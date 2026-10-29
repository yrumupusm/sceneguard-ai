# SPDX-License-Identifier: AGPL-3.0-only
"""CPU-only, post-run evidence builder for the exhausted two-attempt smoke failure.

This file is outside the inference source allowlist and never constructs a model.
Run from repository root with Python3; raw summaries remain ignored/local.
"""
import hashlib
import json
from pathlib import Path
import sqlite3
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'records/EXP-0021'
LOCAL=ROOT/'runtime/BATCH-0003'
ATTEMPTS=('152d45f0113f4c94b44c69961a677023','070b7d4885154095bb84299b8f5916b8')
QUEUE=Path('/home/jhc7484/dev/sceneguard-orca-lab/runtime/orca-lab/gpu-queue')


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def write(name,data):
    (OUT/name).write_text(json.dumps(data,indent=2,sort_keys=True,allow_nan=False)+'\n')


def build():
    manifest=ROOT/'configs/batch0003_pose_manifest.json';d=json.loads(manifest.read_text());summaries=[];rows=[]
    with sqlite3.connect(f'file:{QUEUE}/queue.sqlite3?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        for attempt in ATTEMPTS:
            path=ROOT/'outputs/batch0003/EXP-0021/smoke'/attempt/'summary.json';s=json.loads(path.read_text())
            assert s['status']=='failed' and s['results']==[] and s['forward_count']==0
            native=db.execute('SELECT a.*,j.job_key FROM attempts a JOIN jobs j USING(job_id) WHERE a.attempt_id=?',(attempt,)).fetchone()
            assert native['status']=='failed' and native['finished_at'] is not None
            marker=path.parent/'inference-started.json';attempted=json.loads(marker.read_text())['frame_id'] if marker.exists() else None
            rows.append(dict(attempt_id=attempt,job_key=native['job_key'],status=s['status'],error_type=s['error_type'],error=s['error'],
                code_sha=s['registration']['code_sha'],source_sha256=s['registration']['source_hash'],summary_sha256=sha(path),
                completed_forward_returns=0,completed_frames=0,first_attempted_frame=attempted,
                load_seconds=s['model_construction_load_seconds'],initial_validation_seconds=s['initial_validation_seconds'],
                run_entry_wall_seconds=s['run_entry_wall_seconds'],queue_attempt_wall_seconds=native['finished_at']-native['started_at'],
                load_peak_allocated_bytes=s['load_peak_allocated_bytes'],load_peak_reserved_bytes=s['load_peak_reserved_bytes'],
                free_vram_before_load_mib=s['resource_gate']['free_mib'],warmup_frames=s['warmup_frames'],
                architecture_initial=s.get('architecture_initial'),architecture_selected=s.get('architecture_selected')))
            summaries.append((path,s))
        pose_jobs=[dict(r) for r in db.execute("SELECT job_key,status FROM jobs WHERE command='batch03-pose'")]
        assert len(pose_jobs)==2 and all(j['status']=='failed' for j in pose_jobs)
    previous=json.loads((LOCAL/'initial-failure-freeze/queue-rows.json').read_text())
    with sqlite3.connect(f'file:{QUEUE}/queue.sqlite3?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        for table,key in [('jobs','job_id'),('attempts','attempt_id')]:
            now={r[key]:dict(r) for r in db.execute('SELECT * FROM '+table)}
            assert all(now[r[key]]==r for r in previous[table]),'original queue rows changed'
    comparison=dict(experiment_id='EXP-0021',execution_status='failed',adoption='adopt_on_hold',
        scope='Smoke technical integration only; two failed smoke attempts with completed model loads, zero successful prediction results; no pose/person/behavior performance measured',
        planned_unique_frames=len(d['frames']),planned_smoke_frames=['030_090','007_064'],completed_unique_frames=0,
        attempted_outer_model_calls=1,completed_forward_returns=0,remaining_stage='not_enqueued_or_executed',
        attempts=rows,logical_smoke_attempts=2,logical_retry_consumed=True,original_queue_rows_preserved={'jobs':len(previous['jobs']),'attempts':len(previous['attempts'])},
        windows=[dict(alias=w['alias'],planned_frames=len(w['frames']),completed_frames=0,bbox_count=None,retained_joint_count=None,visual_correspondence=None) for w in d['windows']],
        diagnostic_frames_planned=11,diagnostic_frames_completed=0,person_joint_quality='unmeasured',temporal_correspondence='unmeasured',
        rule_status='skipped: no pose evidence; existing fence-top/far-side geometry unvalidated',tracker='not_run',
        original_pose_comparison='unavailable: no pose output; never substitute original footage or blank skeleton for a successful model comparison',
        technical_limitation='forward_count records completed returns only; correction attempted the outer model call once, failing keyword binding before BaseModel.predict body/_predict_once',
        formal_behavior_metrics={k:None for k in ('accuracy','precision','recall','f1','false_positive_rate')},
        inference_fps=None,actual_input_tensor_artifact='unavailable: capture/save occurred only after successful inference; second path reached shape/dtype assertion but tensor not persisted',
        manifest_sha256=sha(manifest),checkpoint_sha256=d['model']['sha256'],environment_file_index_sha256=d['environment']['files'][d['environment']['file_index']])
    write('comparison.json',comparison)
    costs=dict(attempts=rows,successful_prediction_frames=0,inference_seconds=None,preprocess_seconds=None,postprocess_seconds=None,save_seconds=None,inference_fps=None,frame_wall_fps=None,
        model_load_total_seconds=sum(r['load_seconds'] for r in rows),run_entry_total_seconds=sum(r['run_entry_wall_seconds'] for r in rows),
        queue_attempt_total_seconds=sum(r['queue_attempt_wall_seconds'] for r in rows),
        preparation=json.loads((LOCAL/'frame-binding.json').read_text())['decode'],
        scopes='model load includes checkpoint/FP32/CUDA transfer and synchronization; run-entry starts before lease/input validation but excludes Python/module startup and final summary write; queue attempt includes parent validation/child startup; preparation includes CPU decode/RGB/save/hash; failed frame phase durations were not persisted and remain null; allocator peaks are load-only, not full device total')
    write('costs.json',costs)
    metrics=[]
    for i,r in enumerate(rows):
        for key,unit in [('completed_frames','frames'),('load_seconds','seconds'),('initial_validation_seconds','seconds'),('run_entry_wall_seconds','seconds'),('queue_attempt_wall_seconds','seconds'),('load_peak_allocated_bytes','bytes'),('load_peak_reserved_bytes','bytes'),('free_vram_before_load_mib','MiB')]:
            metrics.append(dict(label=f'Attempt{i+1} {key}',value=r[key],unit=unit,sample_n=1,scope='One failed canonical smoke attempt; no prediction quality or throughput measurement. '+costs['scopes'],source='records/EXP-0021/comparison.json',source_sha256=sha(OUT/'comparison.json'),source_pointer=['attempts',i,key],verification='saved_failure_summary_and_exact_queue_receipt'))
    for name in ('inference_fps','accuracy','precision','recall','f1','false_positive_rate'):
        metrics.append(dict(label=name,value=None,unit='unmeasured',sample_n=0,scope='No pose outputs or joint/person/action GT; never interpret missing inference as normal/empty detections',source='records/EXP-0021/comparison.json',source_sha256=sha(OUT/'comparison.json'),verification='unavailable'))
    write('metrics.json',dict(schema_version=1,experiment_id='EXP-0021',execution_status='failed',behavioral_validation='unmeasured',adoption='adopt_on_hold',comparison_group='EXP-0021',cross_experiment_comparable=False,scope=comparison['scope'],formal_behavior_metrics=comparison['formal_behavior_metrics'],metrics=metrics,comparison_source='records/EXP-0021/comparison.json',comparison_sha256=sha(OUT/'comparison.json'),source_bindings=dict(manifest_sha256=sha(manifest),checkpoint_sha256=d['model']['sha256'],execution_commits=[r['code_sha'] for r in rows],stage_summary_sha256=[sha(p) for p,_ in summaries],failure_builder_sha256=sha(Path(__file__)))))
    print(json.dumps(dict(attempts=rows,model_load_total_seconds=costs['model_load_total_seconds'],queue_attempt_total_seconds=costs['queue_attempt_total_seconds']),indent=2))

if __name__=='__main__':build()
