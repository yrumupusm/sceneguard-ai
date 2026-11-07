"""Summarize frozen advisory heads; candidate counts are not person/event success."""
import argparse
from collections import defaultdict
import json
from pathlib import Path

if __package__:
    from .comparison_saved_evidence import ROOT, MODELS, read, sha, result_provenance, checked_head_scores
else:
    from comparison_saved_evidence import ROOT, MODELS, read, sha, result_provenance, checked_head_scores


def verified_raw_models(summary,cohort_sha):
    if (summary['cohort_sha256']!=cohort_sha or summary['all_eight_full_passes_complete'] is not True
            or set(summary['models'])!=MODELS):raise ValueError('Exact eight-model raw summary required')
    actual={}
    for model in sorted(MODELS):
        item=summary['models'][model]
        result,proof=result_provenance(item['provenance']['result_path'],cohort_sha)
        if (result['model_id']!=model or result['status']!='inference_complete' or result['scored_windows']!=6219
                or result['decoded_native_frames']!=184300 or len(result['videos'])!=45
                or item['status']!=result['status'] or item['windows']!=result['scored_windows']
                or item['decoded_native_frames']!=result['decoded_native_frames'] or item['provenance']!=proof):
            raise ValueError('Actual completed raw model differs')
        actual[model]=(result,proof)
    return actual


def summarize(raw_summary_path, score_paths):
    cohort_path=ROOT/'outputs/model-comparison/exp0066/cohort-v1/manifest.json'
    cohort=read(cohort_path);raw_summary=read(raw_summary_path)
    raw_models=verified_raw_models(raw_summary,sha(cohort_path))
    expected={};cameras={}
    for video in cohort['videos']:
        if sha(video['plan']['path'])!=video['plan']['sha256']:raise ValueError('Input plan changed')
        cameras[video['video_id']]=video['camera_id'];plan=read(video['plan']['path'])
        for role,windows in [('regular',plan['windows']),('diagnostic',plan['supplemental_windows'])]:
            for window in windows:
                key=window['window_id']
                if key in expected:raise ValueError('Duplicate plan window')
                expected[key]=dict(role=role,window=window,video_id=video['video_id'],source_sha256=video['source_sha256'])
    models={}
    for path in score_paths:
        model=read(path)['model_id']
        if model in models or model=='r3d18_exp0064':raise ValueError('Duplicate model or forbidden R3D retraining')
        result,proof=raw_models[model]
        scored,diagnostics,binding=checked_head_scores(path,result,proof,expected)
        head=read(scored['head_result_path']);groups=defaultdict(lambda:dict(windows=0,action_score_rows=0,
            action_positive_rows=0,action_positive_windows=0,person_and_action_positive_rows=0,person_and_action_positive_windows=0))
        joint=model in {'evad_vitb_vmaev2','evad_vitl','stmixer_vitb_vmaev2'}
        with (path.parent/'scores.jsonl').open(encoding='utf-8') as stream:
            for line in stream:
                row=json.loads(line);key=row['window']['window_id'];group=groups[(expected[key]['role'],cameras[row['video_id']])]
                positive=sum(s['climbing_action_candidate'] for s in row['scores'])
                combined=sum(s['person_and_action_candidate'] is True for s in row['scores'])
                group['windows']+=1;group['action_score_rows']+=len(row['scores'])
                group['action_positive_rows']+=positive;group['action_positive_windows']+=positive>0
                group['person_and_action_positive_rows']+=combined;group['person_and_action_positive_windows']+=combined>0
        if not joint:
            for group in groups.values():
                group['person_and_action_positive_rows']=None;group['person_and_action_positive_windows']=None
        models[model]=dict(status='frozen_head_scoring_complete',score_provenance=binding,head_sha256=scored['head_sha256'],
            selected_epoch=head['selected_epoch'],selection=head['selection'],sample_count=head['sample_count'],
            feature_dimension=head['feature_dimension'],coverage_by_split=head['coverage_by_split'],
            validation_metric_scope=head['validation_metric_scope'],validation_normal_subtypes=head['validation_normal_subtypes'],
            official_reference_only=True,human_calibration_complete=False,
            groups=[dict(role=k[0],camera_id=k[1],**v) for k,v in sorted(groups.items())],
            cpu_head_scoring_seconds=scored['cpu_head_scoring_seconds'],scoring_elapsed_seconds=scored['elapsed_seconds'],
            timing_scope=scored['timing_scope'],person_recall=None,climbing_precision=None,climbing_recall=None,intrusion_improvement=None)
    expected_models=MODELS-{'r3d18_exp0064'}
    if set(models)!=expected_models:raise ValueError('All seven actual frozen head results required')
    return dict(status='seven_head_outputs_summarized_not_semantic_evaluation',raw_summary=dict(path=str(raw_summary_path.resolve()),sha256=sha(raw_summary_path)),
        summarizer_sha256=sha(__file__),models=models,all_seven_heads_scored=True,semantic_evaluation_complete=False,
        baseline='EXP0062 AFTER37/52 preserved; no new intrusion decisions',r3d_threshold=.5,
        limitations=['Joint action-only counts include low-person-score queries; combined counts apply native person thresholds.',
                     'Counts refer to windows or frame-local queries, not unique people, events or recovered misses.',
                     'Encoder scores have no actor localization.',
                     'Weak-reference validation has sitting-only negatives; equal human-verified FPR is not established.',
                     'School45 and EXP0064 test were excluded from fitting and threshold selection.'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-summary',type=Path,required=True)
    parser.add_argument('--score',type=Path,action='append',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=summarize(args.raw_summary,args.score)
    with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2,ensure_ascii=False,allow_nan=False)
    print(json.dumps({'output':str(args.output),'heads':len(result['models']),'semantic_evaluation_complete':False}))
