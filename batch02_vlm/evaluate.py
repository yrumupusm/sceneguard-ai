"""Frozen CPU evaluation; labels and old answers never enter the inference module."""
import json
from pathlib import Path
from vlm_batch.common import parse_pair

NEGATIVES=('q01','q02','q03','q05','q06','v02','v04')
CANDIDATES=frozenset(('climbing_attempt_or_in_progress','stepping_over_boundary'))
RUBRIC=dict(candidate='any climbing_attempt_or_in_progress or stepping_over_boundary action',
    indeterminate='indeterminate action, separately from parse failure',
    other='valid parsed response without candidate/indeterminate',
    completion='crossing_completion observed reported separately; q04 observed is unsupported',
    raw_schema='strict original JSON schema independently of common outer-fence removal',
    common_fence_removal='existing vlm_batch.common.parse_pair; no semantic repair',
    evidence_consistency='manual local review of saved exact input required; unreviewed is null',
    cost='load/prepare/generate/queue/output tokens/memory separately; no speed or cost invented',
    reference_views='retain original references and separate new sampled-input review; v03 boundary truth unestablished')


def classify(raw):
    pair=parse_pair(raw)
    parsed=pair['postprocessed_parsed']
    if parsed is None:
        return dict(candidate=None,indeterminate=None,other=None,completion=None,
            strict_schema=pair['strict_parsed'] is not None,common_schema=False,
            postprocessing=pair['postprocessing'],evidence_consistency=None,parse_failure=True)
    actions=set(parsed['observed_actions'])
    candidate=bool(actions&CANDIDATES);indeterminate='indeterminate' in actions
    return dict(candidate=candidate,indeterminate=indeterminate,other=not(candidate or indeterminate),
        completion=parsed['crossing_completion'],strict_schema=pair['strict_parsed'] is not None,
        common_schema=True,postprocessing=pair['postprocessing'],evidence_consistency=None,parse_failure=False)


def reference(review):
    if review=='q04':
        return dict(prior='attempt_progress; completion not observed',sampled_input='holding gate / foot raising; B/C individually unconfirmed',boundary_candidate_reference=True,completion_support=False)
    if review=='v01':
        return dict(prior='attempt_progress; completion previously unassessed',sampled_input='rope/line crossed then standing opposite; not exhaustive per person',boundary_candidate_reference=True,completion_support='visible reviewed action only')
    if review=='v03':
        return dict(prior='adjacent-gap attempt_progress; boundary relation ambiguous; completion unassessed',sampled_input='rock ascent beside gate; boundary crossing not established',boundary_candidate_reference=None,completion_support=None,candidate_absence_definitive_boundary_miss=False)
    return dict(prior='no attempt_progress / approach only or no person',sampled_input='no new positive review',boundary_candidate_reference=False,completion_support=False)


def compare(root,manifest,actual):
    rows=[]
    for condition in manifest['conditions']:
        identity=condition['condition_id'];review=identity.split('_')[0]
        baseline=json.loads((root/condition['baseline_result']).read_text())
        new=actual.get(identity)
        old=classify(baseline['raw_response'])
        candidate=classify(new['raw_response']) if new else None
        rows.append(dict(condition_id=identity,reference=reference(review),baseline=old,candidate=candidate,
            baseline_result_sha256=condition['files'][condition['baseline_result']],
            baseline_timing=baseline.get('timing'),baseline_output_tokens=baseline.get('output_tokens'),
            baseline_gpu_memory=baseline.get('gpu_memory'),
            negative_false_candidate_baseline=old['candidate'] if review in NEGATIVES else None,
            negative_false_candidate_4b=candidate['candidate'] if candidate and review in NEGATIVES else None,
            q04_candidate_retained=(candidate['candidate'] if candidate else None) if review=='q04' else None,
            timing=new.get('timing') if new else None,output_tokens=new.get('output_tokens') if new else None,
            gpu_memory=new.get('gpu_memory') if new else None,
            evidence_consistency_review='pending local human review',cost=new.get('cost') if new else None))
    return dict(schema_version=1,experiment='EXP-0020',rubric=RUBRIC,
        planned_conditions=16,completed_conditions=len(actual),results=rows,
        status='awaiting_execution' if not actual else 'partial' if len(actual)<16 else 'executed_review_pending',
        final_metrics=dict(accuracy=None,precision=None,recall=None,F1=None,FPR=None),
        adoption='hold; bounded development comparison and independent review required',
        limitations=['capacity and quantization changed together','historical q processor RGB/expanded prompt unavailable','q04 B/C visibility unconfirmed','v03 rock ascent does not establish boundary crossing','seven negative windows are diagnostic; no final accuracy/F1/FPR'])
