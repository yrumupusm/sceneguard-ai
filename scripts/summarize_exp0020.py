#!/usr/bin/env python3
"""Rebuild EXP-0020 diagnostic metrics from hash-bound saved outputs, entirely on CPU.

No model/processor/Torch import, source decoding, queue mutation or inference.
The inference-time evaluation definitions remain in frozen batch02_vlm.evaluate.
Post-run text notes below paraphrase model claims against existing user references;
they are Codex drafts, never human visual adjudication or new ground truth.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ['CUDA_VISIBLE_DEVICES']=''
from orchestration import batch02_vlm_command as command
from orchestration.queue import digest
from batch02_vlm import continuation
from batch02_vlm.evaluate import compare,NEGATIVES

OUTPUT=ROOT/'records/EXP-0020/comparison.json'
REPORT=ROOT/'docs/experiments/EXP-0020-vlm-comparison.md'
METRICS=ROOT/'records/EXP-0020/metrics.json'
LOCAL=ROOT/'runtime/BATCH-0002/vlm'

# These notes add no scoring rule and never repair a schema-invalid output.
NOTES={
'q01_B': ('Describes a vehicle and a nearby person, with observed completion.',
          'Describes a passing vehicle and no people; leaves actions empty but still claims completion.',
          'No-attempt reference; the new response is unscorable. Its raw completion does not establish a human boundary crossing.'),
'q01_C': ('Describes a person near the gate, with no confirmed completion.',
          'Describes a static gate and no people, leaving actions empty.',
          'No-attempt reference; empty actions remain a schema failure, not a correct negative. Presence details are unverified.'),
'q02_B': ('Adds a stepping-over candidate to roadside walking and claims completion.',
          'Describes people approaching the gate without entering; no candidate or confirmed completion.',
          'The new action/completion description is compatible with the approach-only reference; detailed visual grounding remains unassessed.'),
'q02_C': ('Describes approach but claims observed completion without a candidate.',
          'Describes approach, with neither candidate nor confirmed completion.',
          'The new completion description better matches the approach-only reference; person details are unverified.'),
'q03_B': ('Describes approach/waiting without a candidate but claims completion.',
          'Describes walking and pausing, again without a candidate but with observed completion.',
          'The no-attempt reference and the response evidence do not support its completion claim; no candidate alone is insufficient.'),
'q03_C': ('Turns approach into a stepping-over candidate and claims completion.',
          'Describes approach, without a candidate or confirmed completion.',
          'This direction is compatible with the no-attempt reference; detailed person/bag descriptions were not visually checked.'),
'q04_B': ('Describes waiting at the gate, without an attempt candidate or confirmed completion.',
          'Describes waiting/preparation and denies active passing or climbing.',
          'Still no candidate despite the window-level foot-raise reference; B-specific visibility was not separately confirmed, so do not invent a definitive per-view boundary miss.'),
'q04_C': ('Retains an attempt candidate but assigns pushing/climbing roles to people; completion is indeterminate.',
          'Retains contact and climbing-attempt tags with pushing/climbing roles; completion is not confirmed.',
          'Broad contact/body-lift direction is compatible with the user review and avoids claiming completion. Per-person roles and C-specific visibility remain unconfirmed.'),
'q05_B': ('Describes approach as stepping over the gate and claims completion.',
          'Describes approach/stepping onto a crossing area, tags contact, and still claims completion without a candidate.',
          'Candidate removal does not fix unsupported completion under the approach-only reference. Contact and precise scene details remain unverified.'),
'q05_C': ('Describes approaching people as stepping over the lower gate and claims completion.',
          'Describes approach and gate contact, without a candidate or confirmed completion.',
          'No candidate is compatible with approach-only; the additional contact claim has not been visually adjudicated.'),
'q06_B': ('Describes a possible small animal, without a candidate or confirmed completion.',
          'Describes a static entrance and no people, leaving actions empty.',
          'No-person reference is specific to this 030 window. New no-person text is compatible, but its invalid schema remains unscorable; the animal claim was not adjudicated.'),
'q06_C': ('Describes a person behind the gate while also saying the person is not visible.',
          'Describes an empty/static gate, leaving actions empty.',
          'The baseline text is internally unclear and unsupported by the no-person reference. New text does not rescue its empty-action schema failure.'),
'v01_full_frame': ('Has a stepping-over candidate/completion claim, but its evidence describes object handling and road traffic rather than a rope crossing.',
                   'Describes people near vehicles and a wall, denies visible gates/fences/ropes, and leaves actions empty.',
                   'New boundary-visibility denial conflicts with the user sampled-input rope-crossing/opposite-side observation; no valid candidate judgment exists. Preserve the historical completion-unassessed reference alongside the newer limited completion observation.'),
'v02_full_frame': ('Describes a person waiting near a wall/vehicle, without a candidate or completion.',
                   'Tags contact while describing leaning on a wall, without a candidate or completion.',
                   'Both lack an attempt candidate under the non-event reference; wall-contact/person details remain unverified.'),
'v03_full_frame': ('Describes a person standing near the gate, without a candidate or completion.',
                   'Denies people or interaction and leaves actions empty.',
                   'The no-person text conflicts with the user rock-ascent observation. Retain the old adjacent-gap attempt reference and new rock-ascent reference separately; neither establishes boundary crossing, and candidate absence is not a definitive boundary miss.'),
'v04_full_frame': ('Turns ordinary crosswalk movement into a stepping-over candidate and claims completion.',
                   'Describes standing/walking, labels ground contact, and denies a boundary crossing.',
                   'Candidate removal is compatible with the non-event reference; ground-contact semantics and person details remain unverified.')}


def require(ok,message):
    if not ok:raise ValueError(message)


def encoded(value):
    return (json.dumps(value,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()


def stats(values,additive=True):
    values=[v for v in values if v is not None]
    if not values:return None
    result=dict(observations=len(values),minimum=min(values),mean=statistics.mean(values),median=statistics.median(values),maximum=max(values))
    if additive:result['sum']=sum(values)
    return result


def syntax_diagnostic(result):
    try:
        raw=json.loads(result['raw_response'])
        syntax=isinstance(raw,dict)
    except (ValueError,TypeError):raw={};syntax=False
    actions=raw.get('observed_actions') if isinstance(raw,dict) else None
    completion=raw.get('crossing_completion') if isinstance(raw,dict) else None
    return dict(json_object_syntax_valid=syntax,empty_action_list=actions==[],
        raw_action_count=len(actions) if isinstance(actions,list) else None,
        raw_completion_claim=completion if completion in ('observed','not_confirmed','indeterminate') else None,
        strict_error=result['parse']['strict_error'],common_error=result['parse']['postprocessed_error'])


def build():
    frozen=command.manifest();binding=continuation.load(command)
    require(binding is not None,'exact correction receipt required')
    queue=json.loads((LOCAL/'final-queue-state.json').read_text())
    continuation.verify_history(binding[2],queue)
    auth=json.loads((LOCAL/'execution-authorization.json').read_text())
    require(command.source_hash()==digest(auth['sources']),'inference source dependency bytes changed')
    current_source=command.source_hash()
    original_auth=json.loads((LOCAL/'execution-authorization-952c52f.json').read_text())
    require(original_auth['sources']['batch02_vlm/evaluate.py']==command.file_hash(ROOT/'batch02_vlm/evaluate.py'),'pre-generation evaluation definitions changed')
    require(auth['source_commit']=='78ba67df03f9a2f3307d85488d7f201eed119924','exact reviewed continuation commit required')
    jobs=[j for j in queue['jobs'] if j['command']=='vlm-batch02']
    identities={j['job_id'] for j in jobs};attempts=[a for a in queue['attempts'] if a['job_id'] in identities]
    require(len(jobs)==len(attempts)==17,'exact16 outputs plus one preserved pre-model failure required')
    successes=[j for j in jobs if j['status']=='succeeded'];failures=[j for j in jobs if j['status']=='failed']
    require(len(successes)==16 and len(failures)==1 and failures[0]['job_id']==continuation.FAILED_JOB,'unexpected execution outcome')
    require({json.loads(j['config_json'])['condition_id'] for j in successes}==set(command.CONDITIONS),'matrix differs')
    actual={};execution={};index=[];expected_manifest=command.file_hash(command.MANIFEST)
    for row in frozen['conditions']:
        cid=row['condition_id'];job=next(j for j in successes if json.loads(j['config_json'])['condition_id']==cid)
        selected=[a for a in attempts if a['job_id']==job['job_id']]
        require(len(selected)==1 and selected[0]['status']=='succeeded','one successful attempt per output required')
        a=selected[0];folder=command.output_path(cid,a['attempt_id'])
        expected_files={**frozen['pins'],**frozen['environment']['files'],**row['files']}
        expected_files.update({str((command.MODEL/name).relative_to(ROOT)):r['sha256'] for name,r in frozen['model']['files'].items()})
        expected_input=dict(manifest_sha256=expected_manifest,condition_id=cid,files=expected_files)
        require(json.loads(job['input_json'])==expected_input and job['input_hash']==digest(expected_input),'stored frozen input binding differs')
        require(json.loads(job['config_json'])==dict(condition_id=cid,settings=command.SETTINGS) and job['config_hash']==digest(json.loads(job['config_json'])),'stored settings binding differs')
        original=cid.startswith('q');expected_source=continuation.ORIGINAL_SOURCE if original else current_source
        expected_commit=continuation.ORIGINAL_COMMIT if original else auth['source_commit']
        require(job['source_hash']==expected_source and job['code_sha']==expected_commit,'condition source lineage differs')
        require(job['job_key']==('batch0002-exp0020-vlm-'+cid if cid!=continuation.CONDITION else continuation.RETRY_KEY),'fixed key differs')
        result=json.loads((folder/'result.json').read_text());summary=json.loads((folder/'summary.json').read_text())
        require(summary['status']=='succeeded' and summary['condition_id']==cid and summary['result_sha256']==command.file_hash(folder/'result.json'),'saved summary/result differs')
        require(result['condition_id']==cid and result['status']=='succeeded','saved result identity differs')
        from vlm_batch.common import parse_pair
        require((folder/'raw_response.txt').read_text()==result['raw_response'] and parse_pair(result['raw_response'])==result['parse'] and result['parsed']==result['parse']['postprocessed_parsed'],'saved raw/parser binding differs')
        require('raw_response.txt' in result['artifacts'] and 'generated_token_ids.npy' in result['artifacts'] and 'processor_rgb.npy' in result['artifacts'],'required raw/input/token artifacts absent')
        artifacts={}
        for name,sha in result['artifacts'].items():
            require(Path(name).name==name and command.file_hash(folder/name)==sha,'artifact hash differs: '+cid+'/'+name)
            artifacts[name]=dict(path=str((folder/name).relative_to(ROOT)),sha256=sha,bytes=(folder/name).stat().st_size)
        for name in ('result.json','summary.json'):
            artifacts[name]=dict(path=str((folder/name).relative_to(ROOT)),sha256=command.file_hash(folder/name),bytes=(folder/name).stat().st_size)
        require(command.file_hash(ROOT/row['baseline_result'])==row['files'][row['baseline_result']],'historical baseline differs')
        require(result['parity']['processor_RGB_matches_saved_EXP17'] and result['parity']['source_pts_rgb_crop_and_metadata'],'input parity failed')
        require(result['parity']['original_baseline_processor_RGB']==('unavailable_historical_q' if original else 'exact_saved_v'),'historical-pixel availability misrepresented')
        if not original:require(result['parity']['original_baseline_expanded_prompt']=='exact_saved_v','v expanded prompt mismatch')
        inventory=json.loads((folder/'module-inventory.json').read_text())
        require(len(inventory['quantized_modules'])==252 and all(n.startswith('model.language_model.') for n in inventory['quantized_modules']),'NF4 replacement inventory differs')
        require(all(p['device']=='cuda:0' and p['dtype'] in ('torch.bfloat16','torch.uint8') for p in inventory['parameters']),'parameter device/dtype differs')
        require(all(p['dtype']=='torch.bfloat16' for p in inventory['parameters'] if p['name'].startswith(('model.visual.','lm_head.'))),'vision/output BF16 inventory differs')
        require(all(p['device']=='cuda:0' for p in inventory['buffers']+inventory['quantization_states']),'buffer/quant-state offload differs')
        require(result['preload_resource']['free_mib']>=6144,'minimum resource gate differs')
        generation=json.loads((folder/'generation-config.json').read_text())['effective']
        require(generation['do_sample'] is False and generation['max_new_tokens']==384 and generation['repetition_penalty']==1.0,'generation settings differ')
        actual[cid]=result
        execution[cid]=dict(job_id=job['job_id'],attempt_id=a['attempt_id'],queue_attempt_number=a['attempt_no'],logical_condition_attempt=2 if cid==continuation.CONDITION else 1,
            source_commit=job['code_sha'],source_hash=job['source_hash'],input_hash=job['input_hash'],config_hash=job['config_hash'],result_sha256=summary['result_sha256'],
            queue_attempt_seconds=a['finished_at']-a['started_at'],created_at=job['created_at'],started_at=a['started_at'],finished_at=a['finished_at'])
        index.append(dict(condition_id=cid,**execution[cid],folder=str(folder.relative_to(ROOT)),artifacts=artifacts,
            queue_manifest=dict(path=str(command.RUNTIME/'attempts'/a['attempt_id']/'manifest.json'),sha256=command.file_hash(command.RUNTIME/'attempts'/a['attempt_id']/'manifest.json'))))
    comparison=compare(ROOT,frozen,actual)
    for row in comparison['results']:
        cid=row['condition_id'];r=actual[cid];metadata=r['input_metadata'];source=next(s for s in frozen['conditions'] if s['condition_id']==cid)
        row['execution']=execution[cid]
        row['format_diagnostics']=syntax_diagnostic(r)
        row['text_reference_review']=dict(kind='Codex text-vs-user-reference draft; no media viewing or human visual adjudication',
            baseline_paraphrase=NOTES[cid][0],candidate_paraphrase=NOTES[cid][1],assessment=NOTES[cid][2],visual_evidence_consistency=None)
        input_record=json.loads((command.output_path(cid,execution[cid]['attempt_id'])/'input.json').read_text())
        row['input_summary']=dict(observations=metadata['observed_frames'],source_wh=metadata['source_size'],crop_shape=metadata['cropped_shape'],processor_shape=metadata['resized_shape'],
            video_grid_thw=metadata['video_grid_thw'],visual_tokens=metadata['visual_tokens'],nonvisual_input_tokens=r['input_text_tokens'],input_tokens=metadata['input_tokens'],effective_context_tokens=r['effective_context_tokens'],
            crop_sha256=metadata['crop_sha256'],processor_payload_sha256=input_record['processor_payload_sha256'],expanded_prompt_sha256=r['artifacts']['expanded_prompt.txt'],parity=r['parity'])
        row['load_gpu_memory']=r['load_gpu_memory']
        row['hit_token_limit']=r['hit_token_limit']
        require(row['baseline']['evidence_consistency'] is None and row['candidate']['evidence_consistency'] is None,'unreviewed visual consistency must remain null')
    groups={}
    for group,ids in [('q_B',[f'q{i:02}_B' for i in (1,2,3,5,6)]),('q_C',[f'q{i:02}_C' for i in (1,2,3,5,6)]),('v_negative',['v02_full_frame','v04_full_frame'])]:
        selected=[r for r in comparison['results'] if r['condition_id'] in ids]
        groups[group]=dict(planned_negative_view_conditions=len(selected),baseline_false_candidates=sum(r['baseline']['candidate'] is True for r in selected),
            baseline_unscorable=sum(r['baseline']['parse_failure'] for r in selected),candidate_false_candidates=sum(r['candidate']['candidate'] is True for r in selected),
            candidate_valid_negative_view_responses=sum(not r['candidate']['parse_failure'] for r in selected),candidate_unscorable_negative_views=sum(r['candidate']['parse_failure'] for r in selected))
    parsing={}
    for which in ('baseline','candidate'):
        selected=[r[which] for r in comparison['results']]
        parsing[which]=dict(strict_schema_valid=sum(r['strict_schema'] for r in selected),common_schema_valid=sum(r['common_schema'] for r in selected),parse_failed=sum(r['parse_failure'] for r in selected),
            candidate_tag=sum(r['candidate'] is True for r in selected),indeterminate_tag=sum(r['indeterminate'] is True for r in selected),other_valid=sum(r['other'] is True for r in selected),
            completion_observed_valid=sum(r['completion']=='observed' for r in selected),completion_not_confirmed_valid=sum(r['completion']=='not_confirmed' for r in selected),completion_indeterminate_valid=sum(r['completion']=='indeterminate' for r in selected))
    failure_attempt=next(a for a in attempts if a['attempt_id']==continuation.FAILED_ATTEMPT)
    failed_path=command.output_path(continuation.CONDITION,continuation.FAILED_ATTEMPT);failure=json.loads((failed_path/'failure.json').read_text())
    failure_public={k:failure[k] for k in ('stage','error_type','error','oom','timing','gpu_memory','elapsed_seconds','generated_tokens_saved')}
    failure_public.update(job_id=continuation.FAILED_JOB,attempt_id=continuation.FAILED_ATTEMPT,source_commit=continuation.ORIGINAL_COMMIT,source_hash=continuation.ORIGINAL_SOURCE,
        queue_attempt_seconds=failure_attempt['finished_at']-failure_attempt['started_at'],logical_condition_attempt=1,model_construction=False,generation=False)
    timing_names=('prepare_seconds','input_transfer_seconds','initial_validation_seconds','preload_validation_seconds','load_seconds','generation_seconds','child_total_seconds','queue_wait_seconds')
    costs=dict(generated_outputs=16,output_tokens=sum(r['output_tokens'] for r in actual.values()),output_token_limit_hits=sum(r['hit_token_limit'] for r in actual.values()),
        candidate_timing={k:stats([r['timing'].get(k) for r in actual.values()]) for k in timing_names},
        baseline_timing={k:stats([r.get('baseline_timing',{}).get(k) for r in comparison['results']]) for k in ('prepare_seconds','generation_seconds')},
        baseline_output_tokens=sum(r['baseline_output_tokens'] for r in comparison['results']),
        baseline_analyze_peak_allocated_bytes=stats([r['baseline_gpu_memory']['peak_allocated_bytes'] for r in comparison['results']],False),
        baseline_analyze_peak_reserved_bytes=stats([r['baseline_gpu_memory']['peak_reserved_bytes'] for r in comparison['results']],False),
        generation_peak_allocated_bytes=stats([r['gpu_memory']['peak_allocated_bytes'] for r in actual.values()],False),generation_peak_reserved_bytes=stats([r['gpu_memory']['peak_reserved_bytes'] for r in actual.values()],False),
        load_peak_allocated_bytes=stats([r['load_gpu_memory']['peak_allocated_bytes'] for r in actual.values()],False),
        load_peak_reserved_bytes=stats([r['load_gpu_memory']['peak_reserved_bytes'] for r in actual.values()],False),
        pre_model_free_mib=stats([r['preload_resource']['free_mib'] for r in actual.values()],False),
        successful_queue_attempt_seconds=sum(r['queue_attempt_seconds'] for r in execution.values()),all17_queue_attempt_seconds=sum(a['finished_at']-a['started_at'] for a in attempts),
        first_job_created_to_last_attempt_finished_seconds=max(a['finished_at'] for a in attempts)-min(j['created_at'] for j in jobs),
        interval_scope='includes idle/review/metadata-repair pauses; not GPU busy time',
        validation_scope='initial lease/input/source checks plus preload revalidation/gate/CUDA initialization; not model inference',
        preparation_scope='source decode, official processor, saved evidence and input artifacts',
        baseline_cost_scope='stored per-window results; historical shared model loads not measured per condition; old preparation excludes source decode and current evidence writes, so preparation scopes differ',
        external_paid_api_cost=0,currency='USD',electricity_cost=None,
        baseline_memory_scope='old allocator reset before preparation/input transfer/generation; resident model included',
        candidate_memory_scope='generation allocator reset after input transfer; loading peak separately measured; not controlled overall memory reduction',device_memory_scope='PyTorch allocator peaks; pre-model nvidia-smi snapshots separately')
    environment=json.loads((LOCAL/'environment.json').read_text())
    comparison.update(schema_version=2,status='executed_behavior_insufficient_adoption_hold',
        denominators=dict(unique_windows=10,view_conditions=16,q_view_conditions=12,v_view_conditions=4,unique_sources=4,unique_negative_windows=7,negative_view_conditions=12,selected_development_diagnostic_only=True),
        execution_summary=dict(successful_generated_conditions=16,generations=16,queue_jobs=17,queue_attempts=17,preserved_pre_model_failures=1,logical_error_retries=1,oom=0,prior33_rows_unchanged=True,remaining_conditions=[],
            original_source_commit=continuation.ORIGINAL_COMMIT,original_source_hash=continuation.ORIGINAL_SOURCE,continuation_source_commit=auth['source_commit'],continuation_source_hash=current_source,failed_attempt=failure_public),
        summary=dict(parsing=parsing,negative_groups=groups,unscorable_conditions=[r['condition_id'] for r in comparison['results'] if r['candidate']['parse_failure']],
            valid_completion_observed_without_candidate=[r['condition_id'] for r in comparison['results'] if r['candidate']['completion']=='observed' and r['candidate']['candidate'] is False],
            candidate_json_object_syntax_valid=sum(r['format_diagnostics']['json_object_syntax_valid'] for r in comparison['results']),
            q04=dict(B_candidate=next(row['candidate']['candidate'] for row in comparison['results'] if row['condition_id']=='q04_B'),C_candidate=next(row['candidate']['candidate'] for row in comparison['results'] if row['condition_id']=='q04_C'),per_view_visibility='not independently confirmed'),
            v01_candidate=next(r['candidate']['candidate'] for r in comparison['results'] if r['condition_id']==continuation.CONDITION),v03_boundary_truth='unestablished; no definitive boundary-miss count'),
        costs=costs,model=dict(id=frozen['model']['id'],revision=frozen['model']['revision'],shards={name:row for name,row in frozen['model']['files'].items() if name.endswith('.safetensors')},
            quantization=frozen['quantization'],settings=frozen['settings'],actual_quantized_language_linear_modules_per_load=252,all_parameters_buffers_and_quant_states_cuda0=True,nonquantized_floating_parameters_bfloat16=True),
        provenance=dict(manifest_sha256=expected_manifest,prompt_sha256=frozen['prompt_sha256'],continuation_contract_sha256=command.file_hash(ROOT/'configs/batch0002_vlm_continuation.json'),
            continuation_receipt_sha256=command.file_hash(LOCAL/'continuation-receipt.json'),history_snapshot_sha256=continuation.HISTORY_SHA,
            frozen_evaluation_source_sha256=command.file_hash(ROOT/'batch02_vlm/evaluate.py'),hardware_receipt_sha256=command.file_hash(LOCAL/'hardware.txt'),
            final_queue_snapshot_sha256=command.file_hash(LOCAL/'final-queue-state.json'),environment_receipt_sha256=command.file_hash(LOCAL/'environment.json'),environment_frozen_file_count=len(environment['files']),
            package_versions={k:environment['versions'][k] for k in ('torch','transformers','bitsandbytes','accelerate','av','numpy','pillow')},
            validation_history_sha256=command.file_hash(LOCAL/'validation-history.json'),focused_test_log_sha256=command.file_hash(LOCAL/'continuation-tests.txt'),full_test_log_sha256=command.file_hash(LOCAL/'continuation-full-orca-tests.txt'),
            cpu_processor_validation_sha256=command.file_hash(LOCAL/'repair-cpu-processor-validation.json'),report_builder_sha256=command.file_hash(Path(__file__)),
            source_hash_verification='both execution freezes and all stored lease/input/config/output artifact bindings; no model load in this rebuild'),
        adoption='hold: schema-invalid positive/negative responses, v01 boundary denial, q04_B noncandidate and unsupported completion/grounding claims remain; no further inference authorized')
    receipts={name:dict(path=str((LOCAL/name).relative_to(ROOT)),sha256=command.file_hash(LOCAL/name),bytes=(LOCAL/name).stat().st_size) for name in ('hardware.txt','environment.json','pip-check.txt','pip-freeze.txt','model-download.json','validation-history.json','repair-cpu-processor-validation.json','continuation-readiness.json','continuation-receipt.json','before-metadata-correction-queue.json','final-queue-state.json','execution-authorization-952c52f.json','execution-authorization.json')}
    artifact_index=dict(schema_version=1,experiment='EXP-0020',receipts=receipts,successful_conditions=index,failed_attempt=dict(condition_id=continuation.CONDITION,path=str(failed_path.relative_to(ROOT)),
        artifacts={p.name:dict(sha256=command.file_hash(p),bytes=p.stat().st_size) for p in failed_path.iterdir() if p.is_file()},queue_manifest=dict(path=str(command.RUNTIME/'attempts'/continuation.FAILED_ATTEMPT/'manifest.json'),sha256=command.file_hash(command.RUNTIME/'attempts'/continuation.FAILED_ATTEMPT/'manifest.json'))),public_comparison_sha256=hashlib.sha256(encoded(comparison)).hexdigest())
    require('torch' not in sys.modules,'CPU report builder unexpectedly imported Torch')
    return comparison,artifact_index


def registration_metrics(r):
    source='records/EXP-0020/comparison.json';sha=hashlib.sha256(encoded(r)).hexdigest();rows=[]
    def add(label,pointer,unit,n,scope):
        value=r
        for part in pointer:value=value[part]
        require(value is None or type(value) in (int,float),'registration metric must be numeric or null')
        rows.append(dict(label=label,value=value,unit=unit,sample_n=n,scope=scope,source=source,source_pointer=pointer,source_sha256=sha,verification='hash_bound_saved_output_CPU_rebuild' if value is not None else 'not_measured'))
    output_scope='16 selected view conditions from10windows; interface/output diagnostic, not independent behavior accuracy.'
    for name in ('baseline','candidate'):
        model='2B' if name=='baseline' else '4B'
        for key,label in [('strict_schema_valid','strict schema valid'),('common_schema_valid','common schema valid'),('parse_failed','unscorable response schema')]:
            add(model+' '+label,['summary','parsing',name,key],'view conditions',16,output_scope)
    for group,g in r['summary']['negative_groups'].items():
        scope=f"{g['planned_negative_view_conditions']} planned negative view conditions; 4B has {g['candidate_valid_negative_view_responses']} valid and {g['candidate_unscorable_negative_views']} unavailable. Counts only; no FPR or correct-negative rate."
        for key,label in [('baseline_false_candidates','2B false candidates'),('candidate_false_candidates','4B false candidates among valid responses'),('candidate_unscorable_negative_views','4B unavailable negative views')]:
            add(group+' '+label,['summary','negative_groups',group,key],'view conditions',g['planned_negative_view_conditions'],scope)
    for key,label,n in [('successful_generated_conditions','Generated frozen conditions',16),('queue_attempts','Queue attempts including one pre-model failure',17),('logical_error_retries','Explicit v01 logical correction retries',1)]:
        add(label,['execution_summary',key],'count',n,'Execution accounting only;16unique outputs/17attempts, no behavior-performance claim.')
    for model,key in [('2B','baseline_timing'),('4B','candidate_timing')]:
        for statistic in ('mean','median','sum'):
            add(model+' generation '+statistic,['costs',key,'generation_seconds',statistic],'seconds',16,'Saved generate interval over16selected view conditions; excludes source decoding/loading; different capacity+quantization and output lengths, not a general throughput benchmark.')
    for key,label,scope in [('load_seconds','4B model loading total','Separate16fresh loads/quantization; no comparable per-condition historical load measurement.'),('initial_validation_seconds','4B initial validation total','Lease/source/input/weight/environment integrity before Torch import.'),('preload_validation_seconds','4B preload validation total','Repeated integrity/gate checks and device initialization, separate from generation.'),('prepare_seconds','4B preparation total','Includes source decode, official processor and evidence writes; scope differs from old analyze preparation.')]:
        add(label,['costs','candidate_timing',key,'sum'],'seconds',16,scope)
    for label,pointer,scope in [('2B analyze allocator allocated peak',['costs','baseline_analyze_peak_allocated_bytes','maximum'],r['costs']['baseline_memory_scope']),('4B generation allocator allocated peak',['costs','generation_peak_allocated_bytes','maximum'],r['costs']['candidate_memory_scope']),('4B loading allocator allocated peak',['costs','load_peak_allocated_bytes','maximum'],'Separate loading/quantization interval; allocator only, not device total.'),('4B generation allocator reserved peak',['costs','generation_peak_reserved_bytes','maximum'],r['costs']['candidate_memory_scope']),('Minimum free memory before model load',['costs','pre_model_free_mib','minimum'],'Fixed6144MiB gate; snapshot before each of16loads, unrelated processes not reserved.')]:
        add(label,pointer,'MiB' if pointer[-2]=='pre_model_free_mib' else 'bytes',16,scope)
    for key in ('accuracy','precision','recall','F1','FPR'):
        add('Final behavior '+key,['final_metrics',key],'not established',None,'Not measured; selected diagnostic windows and unresolved input/grounding boundaries do not support a final metric.')
    data=dict(schema_version=1,experiment_id='EXP-0020',comparison_group='EXP-0020',cross_experiment_comparable=False,comparison_source=source,comparison_sha256=sha,
        execution_status='succeeded',behavioral_validation='not_established',adoption='adoption_on_hold',denominators=r['denominators'],
        formal_behavior_metrics=dict(accuracy=None,precision=None,recall=None,f1=None,false_positive_rate=None),metrics=rows,
        source_bindings=dict(original_commit=r['execution_summary']['original_source_commit'],continuation_commit=r['execution_summary']['continuation_source_commit'],manifest_sha256=r['provenance']['manifest_sha256'],report_builder_sha256=r['provenance']['report_builder_sha256']))
    from orchestration.complete import metrics
    metrics(data,'EXP-0020')
    return data


def render_report(r):
    s=r['summary'];cost=r['costs'];execution=r['execution_summary'];provenance=r['provenance']
    def flag(value):return 'candidate' if value is True else 'none' if value is False else 'unscorable'
    def completion(value):return value or 'unscorable'
    neg='\n'.join(f"| {name} | {g['planned_negative_view_conditions']} | {g['baseline_false_candidates']} | {g['candidate_false_candidates']} | {g['candidate_valid_negative_view_responses']} | {g['candidate_unscorable_negative_views']} |" for name,g in s['negative_groups'].items())
    outcomes='\n'.join(f"| {row['condition_id']} | {flag(row['baseline']['candidate'])} → {flag(row['candidate']['candidate'])} | {completion(row['baseline']['completion'])} → {completion(row['candidate']['completion'])} |" for row in r['results'])
    notes='\n'.join(f"| {row['condition_id']} | {row['text_reference_review']['baseline_paraphrase']} | {row['text_reference_review']['candidate_paraphrase']} | {row['text_reference_review']['assessment']} |" for row in r['results'])
    timing_rows=[]
    for label,key in [('Generation','generation_seconds'),('Preparation','prepare_seconds')]:
        old=cost['baseline_timing'][key];new=cost['candidate_timing'][key]
        timing_rows.append(f"| {label} | {old['sum']:.3f} / {old['median']:.3f} | {new['sum']:.3f} / {new['median']:.3f} |")
    for label,key in [('Model loading/quantization','load_seconds'),('Initial lease/input/source validation','initial_validation_seconds'),('Preload revalidation/gate/CUDA initialization','preload_validation_seconds'),('Input transfer','input_transfer_seconds'),('Measured child total','child_total_seconds')]:
        new=cost['candidate_timing'][key];timing_rows.append(f"| {label} | unavailable per condition | {new['sum']:.3f} / {new['median']:.3f} |")
    times='\n'.join(timing_rows)
    shards='\n'.join(f"| {name} | {info['bytes']:,} | `{info['sha256']}` |" for name,info in r['model']['shards'].items())
    return f"""# EXP-0020 — Qwen4B comparison completed; adoption held

2026-10-29 KST. **The fixed 16-condition comparison completed, but the 4B configuration is not adopted.** It retains q04_C's attempt candidate and removes several old negative candidates, while six outputs fail the unchanged response schema, q04_B remains noncandidate, v01 denies the reviewed boundary cue, and unsupported completion claims remain. Candidate counts do not establish correct grounding or operational accuracy.

The [reproducible comparison](../../records/EXP-0020/comparison.json) and [registration metrics](../../records/EXP-0020/metrics.json) compare **16 view conditions across 10 unique five-second windows**, four sources and seven unique negative windows. q has six windows × B/C; v has four full-frame windows. These selected development/diagnostic conditions are not an independent camera/site test. Accuracy, precision, recall, F1 and FPR remain null.

## Execution and frozen configuration

One official Qwen3-VL-4B-Instruct checkpoint at revision `{r['model']['revision']}` was loaded with NF4 language weights, double quantization, uint8 storage, BF16 compute/nonquantized modules and explicit whole-model CUDA0 placement. Vision/mergers and tied embeddings/output remain BF16; all 16 loads verified **252 language Linear4bit modules**, all parameter/buffer/quantization-state devices on CUDA0 and no CPU/disk/meta offload. This compares old **2B BF16** with **4B NF4 language/BF16 vision and compute**; capacity and quantization effects cannot be separated. [ADR-0019](../decisions/ADR-0019-batch0002-vlm-candidate.md) and the [readiness report](BATCH-0002-vlm-readiness.md) retain the official-source/license evidence; the card declares Apache-2.0, and no separate checkpoint LICENSE file was downloaded.

The new isolated `.venv-vlm-batch02` retains Python 3.10.12, torch 2.5.1+cu124, Transformers 4.57.1 and Accelerate 1.11.0, adding only bitsandbytes 0.48.1 to the old pinned requirements. Pip check/freeze and **19,041 installed-file hashes** are bound by the environment receipt. Old environments, MVP defaults, labels, results and reports are preserved.

| Verified official shard | Bytes | SHA-256 |
| --- | ---: | --- |
{shards}

Batch 1, SDPA, seed 0, greedy generation, max-new-tokens 384 and repetition penalty 1.0 remained fixed. Model-card sampling defaults were explicitly neutralized and saved alongside effective settings, preserving official BOS/EOS/pad IDs. All outputs stayed below the token limit. No 2B model was rerun; its 12 q answers are EXP-0013 outputs under the historical EXP-0012 storage namespace, and its four v answers are EXP-0017 **independent-original** only. Revised EXP-0017 answers are excluded.

Smoke q04_C then q05_B each generated once and are members of the final 16. The disjoint remaining conditions followed serially through the existing canonical queue. No prompt, ROI, frames, dtype, quantization or resolution tuning occurred, and no extra model/condition/PoC was run.

## Response schema and behavior are separate

| Response measure | Stored 2B | New 4B |
| --- | ---: | ---: |
| Strict response schema valid | {s['parsing']['baseline']['strict_schema_valid']} | {s['parsing']['candidate']['strict_schema_valid']} |
| Valid after existing common outer-fence handling | {s['parsing']['baseline']['common_schema_valid']} | {s['parsing']['candidate']['common_schema_valid']} |
| Unscorable schema failures | {s['parsing']['baseline']['parse_failed']} | {s['parsing']['candidate']['parse_failed']} |
| Candidate tags in valid responses | {s['parsing']['baseline']['candidate_tag']} | {s['parsing']['candidate']['candidate_tag']} |
| Indeterminate action tags in valid responses | {s['parsing']['baseline']['indeterminate_tag']} | {s['parsing']['candidate']['indeterminate_tag']} |
| Other valid responses | {s['parsing']['baseline']['other_valid']} | {s['parsing']['candidate']['other_valid']} |

All 16 new responses have valid JSON-object syntax. **q01_B/C, q06_B/C, v01 and v03 have empty action lists**, rejected by the unchanged nonempty action schema; fence removal cannot repair them. Their candidate/indeterminate/completion judgments remain null, not correct negatives. Five old strict-schema rejections are recovered by existing outer-fence handling; all 16 old responses are common-schema valid. The same frozen parser/rubric is used for both models.

| Negative group | Planned negative view conditions | 2B false candidates | 4B false candidates among valid responses | 4B valid responses | 4B unscorable views |
| --- | ---: | ---: | ---: | ---: | ---: |
{neg}

The six valid q approach/no-attempt views q02/q03/q05 B/C all lack candidates. **Four other q negative views remain unresolved**, so this is not ten successful negative decisions. v02/v04 also lack candidates. Valid new q03_B and q05_B still claim observed completion without candidate tags or sufficient crossing evidence; no candidate alone is not correct grounding. Raw q01_B also claims completion inside a schema-invalid response and is not promoted to a valid completion judgment.

| Condition | 2B → 4B candidate judgment | 2B → 4B valid completion claim |
| --- | --- | --- |
{outcomes}

q04_C retains the candidate and changes completion indeterminate → not_confirmed; the old original-prompt baseline already did not confirm completion. q04_B still produces no candidate despite the window-level foot-raise reference, but B/C-specific visibility was not separately confirmed. v01 has no valid new candidate judgment and its raw boundary-visibility denial conflicts with the newer user review of rope crossing then standing opposite. The historical v01 completion-unassessed reference remains separately preserved.

v03's new no-person claim conflicts with the user's rock-ascent observation. **Rock ascent beside the gate does not establish a boundary crossing.** Its prior adjacent-gap attempt reference is retained separately; candidate absence is not counted as a definitive boundary miss, and candidate presence would not establish boundary truth either. q06's no-person reference applies only to source 030:155–160; nothing from source 031 is transferred.

## Action/evidence review draft against existing user references

These are **Codex paraphrases of saved model text compared with existing user references**, not new pixel observations or human visual validation. Extra person roles, objects, contact and scene details remain unverified. Machine `evidence_consistency` stays null for both models in every row. The local ten-observation sheets are available for separate human review; no media was viewed through cloud image tools.

| Condition | Stored 2B claim, paraphrased | New 4B claim, paraphrased | Text-vs-user-reference draft |
| --- | --- | --- | --- |
{notes}

## Input and historical parity limits

The [unchanged manifest](../../configs/batch0002_vlm_manifest.json) fixes ten actual observations at 2fps, original native PTS/order, source RGB hashes and floor/ceil fixed ROI crops. The original prompt SHA is `{provenance['prompt_sha256']}`; only the original anonymous window ID and frames enter model messages. Labels, prior answers, source paths, official annotations/captions and event timestamps do not enter model text. Ten unique windows provide 100 unique selected source observations; the 16 views contain 160 processed observations, including intentional paired q B/C reuse.

| Input view | Processor W×H | Visual / total input tokens |
| --- | --- | --- |
| q B, v full-frame | 768×448 | 1680 / 1947 |
| q C on 007 | 544×608 | 1615 / 1882 |
| q C on 030 | 704×480 | 1650 / 1917 |

All have 267 nonvisual input tokens, effective context limit 262,144, ten processor observations, one official resize, zero additional sampling and zero temporal padding. Expanded prompt, input/output IDs, source/crop/processor hashes and dimensions are saved. Actual decoder traversal ends at the last selected observation; the historical decoder's later traversal endpoint is recorded separately and is not an extra model observation.

All new q processor RGB matches EXP-0017's saved q RGB, but **the actual historical EXP-0013 q processor RGB and expanded prompts were not stored**. Source/PTS/RGB/crop and recorded visual-metadata parity do not establish missing historical processor-pixel/prompt byte identity. EXP-0017 revised q answers are never behavior baselines. All four new v inputs match the original saved processor RGB and expanded-prompt bytes exactly, both in authorized CPU preparation and during queue execution. Internal tensor identity is not claimed without saved tensors. [EXP-0018](EXP-0018-input-audit.md) and the [separate input review](../../configs/batch0002_user_input_review.json) retain the input-sufficiency boundaries.

## One pre-model adapter failure, one logical retry

The first v01 attempt failed in preparation with `KeyError('rgb_sha256')`: q metadata has that aggregate field, while historical v metadata stores ten per-frame hashes. It loaded no Qwen model, initialized no CUDA allocator for reporting and generated no tokens. Its failure/lease/queue receipts remain unchanged.

The bounded compatibility correction verifies all ten frozen per-frame hashes, accepts the historical v schema only for its registered full-frame inventory, and verifies aggregate RGB through the existing full-frame crop hash. Original metadata, the model manifest, images and model settings were not changed. All four actual v decodes and CPU AutoProcessor/RGB/expanded-prompt checks passed with CUDA hidden and uninitialized before retry.

The [frozen continuation contract](../../configs/batch0002_vlm_continuation.json) pins the exact 33-row history and 12 successful q artifact receipts. v01 uses one fixed `retry1` correction job linked to its immutable failed job/attempt: **logical attempt 2, first generation**, although its new queue job has attempt_no 1. A narrow registered-command `Queue.retry` hook rejects retrying either linked v01 job; fixed keys, source/input checks and prelaunch logical count also prevent duplicates/third attempts. No database triggers or recovery schema edits were installed. All 12 q outputs and all 33 pre-correction rows remained unchanged; v02–v04 each used a first attempt.

There are **16 generated outputs, 17 new jobs/attempts, one preserved preparation failure, one logical retry and zero OOMs**. The initial additive command-CHECK migration backed up and preserved the previous 20 settled jobs/attempts. The final canonical queue has 37 settled jobs/attempts, including the preserved failures. No more inference is authorized by this result.

## Measured cost, separated by scope

RTX 3080 10 GiB; every successful load passed the unchanged minimum free 6144 MiB gate, with recorded pre-model free memory {cost['pre_model_free_mib']['minimum']}–{cost['pre_model_free_mib']['maximum']} MiB. Actual device/module inventories are retained locally. PyTorch allocator peaks are not total device/process memory.

| Timing, seconds: total / median over 16 outputs | Stored 2B | New 4B |
| --- | ---: | ---: |
{times}

2B preparation excludes original source decoding and current evidence writes, while 4B preparation includes them; those preparation times are not equivalent performance measurements. Historical 2B shared model-load costs are unavailable per condition. Output tokens total {cost['baseline_output_tokens']} → {cost['output_tokens']}; generation timing is observed on these selected outputs, not a general throughput benchmark. The 4B change also changes quantization and execution/load structure.

Successful queue-attempt time totals {cost['successful_queue_attempt_seconds']:.3f}s; all 17 attempts including the preparation failure total {cost['all17_queue_attempt_seconds']:.3f}s. The first-job-created to last-attempt-finished interval is {cost['first_job_created_to_last_attempt_finished_seconds']:.3f}s, **including review/repair/idle gaps, not GPU busy time**. Validation/revalidation includes full input/environment/checkpoint integrity work and device initialization; it is reported separately from preparation, loading and generation. The failed attempt's own validation/prepare/elapsed values remain in the JSON; unavailable GPU measurements are null.

The old 2B allocator was reset before preparation/input transfer/generation, while the new generation interval is reset after input transfer and loading is measured separately. The old analyze allocation peak ({cost['baseline_analyze_peak_allocated_bytes']['maximum']/2**30:.3f} GiB) and new generation peak are different scopes; they do not establish a controlled overall memory reduction.

Maximum load allocator allocation/reservation: {cost['load_peak_allocated_bytes']['maximum']/2**30:.3f}/{cost['load_peak_reserved_bytes']['maximum']/2**30:.3f} GiB. Maximum generation allocator allocation/reservation: {cost['generation_peak_allocated_bytes']['maximum']/2**30:.3f}/{cost['generation_peak_reserved_bytes']['maximum']/2**30:.3f} GiB. External paid API cost is USD 0; electricity/host cost is unmeasured. No camera-independent accuracy, F1, FPR or operational readiness is inferred.

## Source, validation and CPU reproduction

- Original q generation / first failed v01 source: `{execution['original_source_commit']}`, digest `{execution['original_source_hash']}`.
- Reviewed v continuation source: `{execution['continuation_source_commit']}`, digest `{execution['continuation_source_hash']}`.
- Unchanged model/input manifest SHA: `{provenance['manifest_sha256']}`.
- Exact prior-history SHA: `{provenance['history_snapshot_sha256']}`; continuation receipt SHA: `{provenance['continuation_receipt_sha256']}`.
- Environment receipt SHA: `{provenance['environment_receipt_sha256']}`; post-run CPU report-builder SHA: `{provenance['report_builder_sha256']}`.

Initial validation: 22 focused tests passed; full Orca suite 109 run / 107 passed / 2 skipped. Reviewed correction: **28 focused passed; 115 full-suite run / 113 passed / 2 skipped**, plus actual four-v CPU decoder/processor parity. An interim full run had an existing supervisor-interruption test's reversed-order assertion; the test/generic behavior was not changed to hide it. A test-development fixture also initially violated a uniqueness constraint before its intended wrong-lineage assertion; that fixture was corrected. The separate local validation history preserves those facts and the available logs. CPU tests/recovery code review are not behavior-performance proof; the coordinator's final results review/delivery are separate.

The [CPU report builder](../../scripts/summarize_exp0020.py) reproduces this report, the public comparison and registration metrics and the ignored artifact index from saved, hash-bound outputs. It imports no Torch/model/processor, decodes no source media, mutates no queue and performs no inference:

```bash
python3 -B scripts/summarize_exp0020.py
python3 -B scripts/summarize_exp0020.py --check
```

The check verifies byte-identical outputs, frozen source/input/config/lineage bindings, saved parser/raw artifacts and local inventories. Local evidence index: `runtime/BATCH-0002/vlm/artifact-index.json`; raw responses, token IDs, RGB/sheets, checkpoints, environment and receipts stay ignored/local. Only safe code/config/report and deidentified diagnostic summaries are publication artifacts. Existing MVP/defaults/web features are unchanged. **Adoption remains held, and this bounded model comparison is closed without additional prompt/model/condition tuning or a PoC.**
"""


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true',help='verify byte-identical public comparison and local artifact index without writing')
    args=p.parse_args();comparison,index=build();public=encoded(comparison);metrics=encoded(registration_metrics(comparison));index['public_metrics_sha256']=hashlib.sha256(metrics).hexdigest();report=render_report(comparison).encode();index['public_report_sha256']=hashlib.sha256(report).hexdigest();private=encoded(index);index_path=LOCAL/'artifact-index.json'
    if args.check:
        require(OUTPUT.read_bytes()==public,'public comparison is not reproducible')
        require(index_path.read_bytes()==private,'local artifact index is not reproducible')
        require(REPORT.read_bytes()==report,'public report is not reproducible')
        require(METRICS.read_bytes()==metrics,'registration metrics are not reproducible')
    else:
        OUTPUT.write_bytes(public);index_path.write_bytes(private);REPORT.write_bytes(report);METRICS.write_bytes(metrics)
    print(json.dumps(dict(status='verified' if args.check else 'written',conditions=16,queue_attempts=17,logical_retry=1,strict_schema_valid=comparison['summary']['parsing']['candidate']['strict_schema_valid'],
        unscorable=comparison['summary']['unscorable_conditions'],comparison_sha256=hashlib.sha256(public).hexdigest(),artifact_index_sha256=hashlib.sha256(private).hexdigest(),report_sha256=hashlib.sha256(report).hexdigest(),metrics_sha256=hashlib.sha256(metrics).hexdigest(),torch_imported=False),sort_keys=True))


if __name__=='__main__':main()
