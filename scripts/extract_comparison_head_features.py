"""EXP0066 full-frame frozen representations; entry point is canonical comparison-head only."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import sys
import traceback

ROOT=Path(__file__).resolve().parents[1]


def iou(a,b):
    x=max(0,min(a[2],b[2])-max(a[0],b[0]));y=max(0,min(a[3],b[3])-max(a[1],b[1]))
    intersection=x*y;union=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-intersection
    return intersection/union if union>0 else 0


def valid_box(box,size):
    return (len(box)==4 and all(math.isfinite(v) for v in box)
            and 0<=box[0]<box[2]<=size[0] and 0<=box[1]<box[3]<=size[1])


def match_queries(output,targets,size):
    """Both-origin IoU .5; deterministic best query; a query has at most one weight.

    All qualifying targets participate in conflict detection, even if a different
    query is their best. Same-label collisions coalesce and retain every target
    binding; unmatched queries never become negative examples.
    """
    boxes=output['boxes'];valid=output['valid_boxes'];logits=output['raw_action_logits']
    persons=output['person_scores']
    if not boxes or len(boxes)!=len(valid) or len(boxes)!=len(logits):raise ValueError('Empty/inconsistent joint output')
    if len(persons)!=len(boxes) or any(not math.isfinite(v) or not 0<=v<=1 for v in persons):raise ValueError('Finite native person scores required')
    if any(len(v)!=80 or not all(math.isfinite(x) for x in v) for v in logits):raise ValueError('Finite80 AVA logits required')
    candidates=defaultdict(list);best=defaultdict(list);unique=[]
    for t in targets:
        # Provenance aliases do not create extra weights. They remain recorded.
        if t not in unique:unique.append(t)
    for t in unique:
        origins=[[*b[0],*b[1]] for b in t['anchor_boxes_origin0_origin1']]
        if len(origins)!=2 or not all(valid_box(b,size) for b in origins) or t['label'] not in (0,1):raise ValueError('Invalid target geometry/label')
        ranked=[]
        for q,box in enumerate(boxes):
            if type(valid[q]) is not bool:raise ValueError('Explicit query validity required')
            if not valid[q]:continue
            if not valid_box(box,size):raise ValueError('Invalid original-coordinate query box')
            overlap=min(iou(box,b) for b in origins)
            if overlap>=.5:
                candidates[q].append(t);ranked.append((overlap,q))
        if ranked:
            overlap,q=min(ranked,key=lambda item:(-item[0],item[1]));best[q].append((t,overlap))
    rows=[];conflicts=sorted(q for q,ts in candidates.items() if len({t['label'] for t in ts})!=1)
    ambiguous_targets={json.dumps(t,sort_keys=True) for q in conflicts for t in candidates[q]}
    for q,assignments in sorted(best.items()):
        if q in conflicts:continue
        rows.append(dict(query_index=q,label=assignments[0][0]['label'],feature=logits[q],query_box=boxes[q],
                         person_score=persons[q],person_score_policy='all_valid_queries_no_person_score_threshold',
                         min_iou=min(v for _,v in assignments),targets=[t for t,_ in assignments],
                         weight_count=1,semantic_ground_truth_verified=False))
    matched_targets={json.dumps(t,sort_keys=True) for r in rows for t in r['targets']}
    return rows,dict(query_count=len(boxes),matched_queries=len(rows),conflicting_queries=conflicts,
                     unknown_queries=len(boxes)-len(rows),target_count=len(unique),
                     ambiguous_targets=len(ambiguous_targets-matched_targets),
                     targets_with_conflicting_query=len(ambiguous_targets),conflicting_query_count=len(conflicts),
                     matched_targets=len(matched_targets),unmatched_targets=len(unique)-len(matched_targets),
                     same_actor_human_verified=False)


def representations(window,output,joint):
    if joint:return match_queries(output,window['targets'],window['source_size'])
    feature=output.get('pooled_features',[])
    if not feature or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in feature):raise ValueError('Empty/nonfinite pooled features')
    return [dict(query_index=None,label=window['label'],feature=feature,weight_count=1,
                 semantic_ground_truth_verified=False)],dict(scene_samples=1,unknown_queries=None)


def audit_native_outputs(native_path,feature_path,plan,joint):
    """Stream-recompute every matching decision from preserved complete native outputs."""
    from itertools import zip_longest
    windows={w['window_id']:w for w in plan['windows']};seen=set();coverage=defaultdict(Counter)
    def invalid(value):raise ValueError('Nonfinite JSON: '+value)
    with Path(native_path).open(encoding='utf-8') as native,Path(feature_path).open(encoding='utf-8') as features:
        for raw_line,feature_line in zip_longest(native,features):
            if raw_line is None or feature_line is None:raise ValueError('Native/feature coverage differs')
            raw=json.loads(raw_line,parse_constant=invalid);row=json.loads(feature_line,parse_constant=invalid);wid=row['window_id']
            if wid not in windows or wid in seen or raw['window_id']!=wid:raise ValueError('Native/feature window differs')
            seen.add(wid);window=windows[wid]
            native_hash=hashlib.sha256(json.dumps(raw['output'],sort_keys=True,allow_nan=False).encode()).hexdigest()
            if native_hash!=row['model_output_sha256']:raise ValueError('Native model output hash differs')
            samples,counts=representations(window,raw['output'],joint)
            if samples!=row['samples'] or counts!=row['coverage']:raise ValueError('Recomputed native matching/features differ')
            for k,v in counts.items():
                if type(v)==int:coverage[window['split']][k]+=v
    if seen!=set(windows):raise ValueError('Incomplete native output audit')
    return {s:dict(c) for s,c in coverage.items()}


def extract(config,output,attempt,inputs):
    import torch
    from orchestration.comparison_head_command import JOINT, file_hash, sources, input_contract, read
    from orchestration.queue import digest
    from scripts.prepare_comparison_head_data import window_pixels
    from scripts.run_model_comparison import load_adapter
    torch.set_num_threads(2);torch.manual_seed(66);torch.cuda.manual_seed_all(66)
    torch.backends.cudnn.benchmark=False
    plan=read(config['files']['plan']['path']);preparation=read(config['files']['preparation']['path'])
    windows=plan['windows']
    if config['stage']=='feature-smoke':windows=[w for w in windows if w['window_id'] in plan['smoke_window_ids']]
    grouped=defaultdict(list)
    for w in windows:grouped[w['source_sha256']].append(w)
    proofs={}
    for binding in preparation['sources']:
        proof=read(binding['path'])
        proofs.update({w['window_id']:w['rgb_slots_sha256'] for w in proof['windows']})
    spec=read(config['files']['model_spec']['path']);adapter=load_adapter(config['model_id'] in JOINT)
    snapshot=sources(config);model=adapter.load_model(spec,'cuda');dim=None;counts=Counter();seen=[]
    coverage_by_split=defaultdict(Counter)
    with (output/'features.jsonl').open('x',encoding='utf-8') as stream,(output/'native-outputs.jsonl').open('x',encoding='utf-8') as native:
        for rows in grouped.values():
            for window,clip in window_pixels(rows[0]['source_path'],rows):
                rgb_sha=hashlib.sha256(clip.tobytes()).hexdigest()
                if rgb_sha!=proofs.get(window['window_id']):raise ValueError('Actual selected RGB differs from CPU receipt')
                result=adapter.infer_clip(model,clip,spec)
                # Includes all model coordinates/scores, even for unmatched queries.
                result_hash=hashlib.sha256(json.dumps(result,sort_keys=True,allow_nan=False).encode()).hexdigest()
                native.write(json.dumps(dict(window_id=window['window_id'],output=result),sort_keys=True,allow_nan=False)+'\n');native.flush()
                samples,coverage=representations(window,result,config['model_id'] in JOINT)
                for key,value in coverage.items():
                    if type(value)==int:coverage_by_split[window['split']][key]+=value
                for sample in samples:
                    if dim is None:dim=len(sample['feature'])
                    if len(sample['feature'])!=dim:raise ValueError('Representation dimension changed')
                    counts[f"{window['split']}:{sample['label']}"]+=1
                record=dict(window_id=window['window_id'],split=window['split'],source_sha256=window['source_sha256'],
                            source_path=window['source_path'],source_size=window['source_size'],
                            sample_pts_ticks=window['sample_pts_ticks'],sample_pts=window['sample_pts'],
                            observed_unique_frames=7,available_after_pts=window['available_after_pts'],
                            rgb_slots_sha256=rgb_sha,model_output_sha256=result_hash,
                            samples=samples,coverage=coverage,
                            preprocessing_geometry=result['preprocessing_geometry'] if config['model_id'] in JOINT else result['geometry'])
                stream.write(json.dumps(record,sort_keys=True,allow_nan=False)+'\n');stream.flush();seen.append(window['window_id'])
    if set(seen)!={w['window_id'] for w in windows} or len(seen)!=len(windows) or not counts:raise ValueError('Incomplete/empty features')
    if sources(config)!=snapshot or input_contract(config)!=inputs:raise ValueError('Source/input changed during feature extraction')
    result=dict(status='feature_smoke_passed' if config['stage']=='feature-smoke' else 'features_complete',
                stage=config['stage'],model_id=config['model_id'],queue_command='comparison-head',queue_attempt=attempt,
                input_hash=digest(inputs),source_hash=digest(snapshot),code_sha=read(config['authorization']['path'])['code_sha'],
                features_sha256=file_hash(output/'features.jsonl'),feature_dimension=dim,counts=dict(counts),
                native_outputs_sha256=file_hash(output/'native-outputs.jsonl'),
                coverage_by_split={s:dict(c) for s,c in coverage_by_split.items()},
                representation_scope='conditional_on_matched_automatic_queries' if config['model_id'] in JOINT else 'weak_full_scene_not_actor_specific',
                person_score_policy='all_valid_queries_no_person_score_threshold' if config['model_id'] in JOINT else None,
                original_person_threshold=spec['output_postfilter']['original_person_threshold'] if config['model_id'] in JOINT else None,
                matched_native_person_operating_point_verified=False,
                window_ids=seen,windows=len(seen),model_spec_sha256=config['files']['model_spec']['sha256'],
                plan_sha256=config['files']['plan']['sha256'],semantic_ground_truth_verified=False,
                human_precision=None,human_recall=None,intrusion_completed=None,intrusion_state_changed=False)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('queue-config','queue-config-sha256','queue-attempt','output'):parser.add_argument('--'+name,required=True)
    args=parser.parse_args(argv);args.output=Path(args.output);sys.path.insert(0,str(ROOT))
    from orchestration.comparison_head_command import runner_guard
    config,inputs=runner_guard(args)
    args.output.mkdir(parents=True,exist_ok=False)
    status=args.output/'status.json';status.write_text(json.dumps(dict(status='running',stage=config['stage']))+'\n',encoding='utf-8')
    try:
        if config['stage']=='train':
            from scripts.train_comparison_heads import train
            result=train(config,args.output,args.queue_attempt,inputs)
        else:result=extract(config,args.output,args.queue_attempt,inputs)
        (args.output/'result.json').write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        status.write_text(json.dumps(dict(status='succeeded'))+'\n',encoding='utf-8')
    except BaseException:
        status.write_text(json.dumps(dict(status='failed',traceback=traceback.format_exc()))+'\n',encoding='utf-8');raise


if __name__=='__main__':main()
