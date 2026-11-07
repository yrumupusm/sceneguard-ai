"""Apply already frozen CPU heads to saved school outputs; never select thresholds here."""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.comparison_saved_evidence import QUEUE,checked_rows,read,result_provenance,sha
from orchestration.queue import digest


def checked_head(path,raw_result):
    result=read(path);attempt=result['queue_attempt'];directory=path.parent
    if (result['status']!='head_trained' or result['queue_command']!='comparison-head'
            or result['stage']!='train' or result['model_id']!=raw_result['model_id']
            or result['model_spec_sha256']!=raw_result['model_spec_sha256']):
        raise ValueError('Matching completed task head required')
    if len(attempt)!=32 or any(c not in '0123456789abcdef' for c in attempt):raise ValueError('Invalid head attempt')
    receipt_path=QUEUE/'attempts'/attempt/'manifest.json';receipt=read(receipt_path)
    if (receipt['attempt_id']!=attempt or receipt['execution_status']!='succeeded'
            or receipt['result_sha256']!=sha(path) or Path(receipt['result_path']).resolve()!=directory.resolve()
            or receipt.get('synthetic') is not False):raise ValueError('Actual head receipt differs')
    with sqlite3.connect('file:'+str(QUEUE/'queue.sqlite3')+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        row=db.execute('SELECT j.*,a.status AS attempt_status,a.result_manifest FROM jobs j JOIN attempts a USING(job_id) WHERE a.attempt_id=?',(attempt,)).fetchone()
    if (row is None or row['command']!='comparison-head' or row['status']!='succeeded' or row['attempt_status']!='succeeded'
            or row['result_manifest']!=str(receipt_path)
            or any(row[k]!=result[k] for k in ('source_hash','input_hash','code_sha'))
            or any(receipt['registration'].get(k)!=row[k] for k in ('job_id','run_id','task_id','dispatch_id','owner','source_hash','input_hash','code_sha','config_hash'))):
        raise ValueError('Actual successful head queue record required')
    config=json.loads(row['config_json']);inputs=json.loads(row['input_json'])
    if (digest(config)!=row['config_hash'] or digest(inputs)!=row['input_hash']
            or config['stage']!='train' or config['model_id']!=result['model_id']
            or config['files']['plan']['sha256']!=result['plan_sha256']
            or config['files']['model_spec']['sha256']!=result['model_spec_sha256']):
        raise ValueError('Executed head configuration differs')
    for name in ('plan','release','model_spec'):
        entry=config['files'][name]
        if sha(entry['path'])!=entry['sha256']:raise ValueError('Frozen head input changed: '+name)
    release=read(config['files']['release']['path'])
    if release['plan']!=config['files']['plan'] or release['preparation']!=config['files']['preparation']:
        raise ValueError('Training release selected different inputs')
    for name in ('head','history','selection'):
        if sha(directory/(name+('.pt' if name=='head' else '.json')))!=result[name+'_sha256']:
            raise ValueError('Frozen head artifact changed')
    return result,receipt_path,config


def score(raw_path,head_path,output):
    started=time.perf_counter()
    if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise ValueError('Explicit CUDA-hidden CPU scoring required')
    import torch
    from scripts.train_comparison_heads import score_features
    torch.set_num_threads(2)
    cohort_path=ROOT/'outputs/model-comparison/exp0066/cohort-v1/manifest.json';cohort=read(cohort_path)
    result,provenance=result_provenance(raw_path,sha(cohort_path))
    if result['status']!='inference_complete':raise ValueError('Complete school full-video outputs required')
    head_result,receipt_path,head_config=checked_head(head_path,result)
    head=torch.load(head_path.parent/'head.pt',map_location='cpu',weights_only=True)
    if (head['model_id']!=result['model_id'] or head['selection']!=head_result['selection']
            or head['plan']!=head_config['files']['plan'] or head['feature_source']!=head_config['files']['features']
            or head['input_hash']!=head_result['input_hash'] or head['source_hash']!=head_result['source_hash']):
        raise ValueError('Head selection/model differs')
    if head['selection']['threshold_status']!='provisional_official_reference_not_human_calibrated':
        raise ValueError('Calibration limitation must be preserved')
    expected={}
    for video in cohort['videos']:
        if sha(video['plan']['path'])!=video['plan']['sha256']:raise ValueError('Frozen window plan changed')
        plan=read(video['plan']['path'])
        for w in plan['windows']+plan['supplemental_windows']:
            if w['window_id'] in expected:raise ValueError('Duplicate input window')
            expected[w['window_id']]=dict(window=w,video_id=video['video_id'],source_sha256=video['source_sha256'])
    output.mkdir(parents=True,exist_ok=False);count=0;scoring_seconds=0.;head_inputs=0
    joint=result['model_id'] in ('evad_vitb_vmaev2','evad_vitl','stmixer_vitb_vmaev2')
    person_threshold={'evad_vitb_vmaev2':.7,'evad_vitl':.7,'stmixer_vitb_vmaev2':.6}.get(result['model_id'])
    bindings={str(p):sha(p) for p in (raw_path,raw_path.parent/'windows.jsonl',head_path,head_path.parent/'head.pt',Path(__file__),ROOT/'scripts/train_comparison_heads.py',ROOT/'scripts/comparison_saved_evidence.py')}
    with (output/'scores.jsonl').open('x',encoding='utf-8') as stream:
        for row in checked_rows(raw_path.parent/'windows.jsonl',result,expected):
            native=row['output'];features=native['raw_action_logits'] if joint else [native['pooled_features']]
            before=time.perf_counter();scores=score_features(head,features)
            head_seconds=time.perf_counter()-before;scoring_seconds+=head_seconds;head_inputs+=len(features)
            for i,item in enumerate(scores):
                item['query_index']=i if joint else None
                item['person_and_action_candidate']=(bool(native['valid_boxes'][i]) and native['person_scores'][i]>=person_threshold and item['climbing_action_candidate']) if joint else None
            item=dict(video_id=row['video_id'],source_sha256=row['source_sha256'],window=row['window'],
                      model_id=result['model_id'],scores=scores,boxes=native['boxes'],person_scores=native['person_scores'],
                      person_threshold=person_threshold,head_threshold=head['selection']['threshold'],
                      scope='automatic_query_action_scores' if joint else 'weakly_supervised_scene_action_score_no_actor_localization',
                      cpu_head_seconds=head_seconds,
                      same_person_verified=False,intrusion_completed=None,intrusion_state_changed=False)
            stream.write(json.dumps(item,sort_keys=True,allow_nan=False)+'\n');count+=1
    if count!=6219 or torch.cuda.is_initialized():raise ValueError('Incomplete scoring or unexpected CUDA use')
    if any(sha(p)!=h for p,h in bindings.items()):raise ValueError('Scoring source or input changed')
    report=dict(status='frozen_head_scored_saved_school_outputs',model_id=result['model_id'],windows=count,
                raw_provenance=provenance,head_result_path=str(head_path),head_result_sha256=sha(head_path),
                head_receipt_path=str(receipt_path),head_receipt_sha256=sha(receipt_path),
                head_sha256=head_result['head_sha256'],head_selection=head['selection'],bindings=bindings,
                scores_sha256=sha(output/'scores.jsonl'),new_encoder_or_detector_forwards=0,
                elapsed_seconds=time.perf_counter()-started,cpu_head_scoring_seconds=scoring_seconds,
                scored_feature_vectors=head_inputs,
                timing_scope='CPU head construction/load/normalization/linear/sigmoid/threshold per window; total also includes provenance checks and input/output IO, not live streaming latency',
                school_data_used_for_training_or_threshold_selection=False,semantic_evaluation_complete=False,
                person_recall=None,climbing_precision=None,climbing_recall=None,intrusion_improvement=None)
    with (output/'result.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2,allow_nan=False)
    print(json.dumps({'status':report['status'],'model':result['model_id'],'windows':count}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('raw-result','head-result','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();score(args.raw_result,args.head_result,args.output)
