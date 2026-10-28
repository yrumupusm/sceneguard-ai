#!/usr/bin/env python3
"""Read-only, stdlib-only evaluation of the frozen EXP-0016 jobs as EXP-0017.

No model, decoder, processor or queue imports. Only the unchanged pure parser
and MVP action classification are imported. Local paths/text stay in runtime;
the comparison is built from an explicit allowlist of metadata and claims.
"""
import argparse
import ast
from collections import Counter
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mvp.events import classify
from vlm_batch.common import parse_pair

GROUPS = {'q_full_frame': ('prompt-regression', 'full_frame', 6),
          'q_fixed_roi': ('prompt-regression', 'fixed_roi', 6),
          'v_original': ('independent-original', 'full_frame', 4),
          'v_revised': ('independent-revised', 'full_frame', 4)}
BASE_ATTEMPTS = {'B': '49cad0749df04995bb55727d57946fec',
                 'C': 'a546b67626e54ef79cdf9bee1c70b3bf'}
Q = [('q01', 's007_early', 'E01_007', 'w000001', 0, 5),
     ('q02', 's007_preevent', 'E01_007', 'w000020', 47.5, 52.5),
     ('q03', 'd007_boxchange', 'E01_007', 'w000022', 52.5, 57.5),
     ('q04', 'd007_official', 'E01_007', 'w000026', 62.5, 67.5),
     ('q05', 's030_time', 'E01_030', 'w000021', 50, 55),
     ('q06', 'd030_eof', 'E01_030', 'w000063', 155, 160)]
PINS = {'records/EXP-0015/window_reviews.json': 'b82267a2c8a457a2dd505183c61fb0cffde886776970322e66176e69493de0d0',
        'configs/mvp_exp0016_independent_evaluation.json': 'e7e59c8ae807ffcea5a606ad4d6618360be43dc62afa83e4abaec88ddd363a0d',
        'configs/mvp_exp0016_independent_manifest.json': '68b07ef836422cd9043e4fcb88b40b0f70e256d0024a2bd57ce29a12e08aa765',
        'configs/mvp_exp0016_manifest.json': 'e1a00ce51d35e6dea61ade0869db3379cc447a30f6988e5296c7cb0cf6c688b6',
        'configs/mvp0001_settings.json': '4250fb34b68725a08a832bfb247a7b7d08450f5b4837daa136262aac3710fa21'}
MODEL_SHA = '7de1838c87a5349b016c26a1c3f7d2bc400a3d485f95ef39a7059ffd734977a0'
PROMPTS = {'original': '049ec4a6274443fcf8e3069914e53b2913aefa6f4a13ca049cc4001fa8def7a6',
           'revised': 'ffc12cd2f9af707e9654acd3eed0449009576e81803206573b17445cde8cf92b'}
STATES = ('candidate', 'indeterminate', 'other', 'parse_failed', 'missing')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)+'\n').encode()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def strict_json(raw):
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            require(key not in obj, 'duplicate JSON key')
            obj[key] = value
        return obj
    def bad_constant(value):
        raise ValueError('nonfinite JSON constant')
    return json.loads(raw, object_pairs_hook=unique, parse_constant=bad_constant)


class Reader:
    def __init__(self):
        self.files = {}

    def read(self, path, expected=None):
        path = Path(path).resolve()
        raw = path.read_bytes()
        digest = sha(raw)
        require(expected is None or digest == expected, 'artifact hash mismatch: '+path.name)
        require(path not in self.files or self.files[path] == digest, 'input changed during evaluation')
        self.files[path] = digest
        return raw

    def json(self, path, expected=None):
        return strict_json(self.read(path, expected))

    def verify(self):
        require(all(sha(p.read_bytes()) == h for p, h in self.files.items()), 'input changed during evaluation')


def outcome(result):
    """Parser claims only: a candidate plus indeterminate remains a candidate."""
    if result is None:
        return {'status': 'missing', 'strict_json_valid': False, 'common_parse_valid': False,
                'actions': [], 'completion_claim': None, 'claims_are_truth': False}
    raw = result.get('raw_response')
    pair = parse_pair(raw) if isinstance(raw, str) else None
    parsed = pair['postprocessed_parsed'] if pair else None
    states = classify({'parsed': parsed})
    names = [state for state, _ in states]
    status = ('candidate' if 'candidate' in names else 'parse_failed' if 'parse_failed' in names
              else 'indeterminate' if 'indeterminate' in names else 'other')
    if result.get('execution_error') or result.get('skipped'):
        status = 'missing'
    if isinstance(raw, str):
        require(result.get('parsed') == parsed and result.get('parse') == pair,
                'stored parser differs from unchanged reparse')
    actions = parsed['observed_actions'] if parsed else []
    return {'status': status, 'strict_json_valid': bool(pair and pair['strict_parsed']),
            'common_parse_valid': parsed is not None,
            'common_postprocessing': pair['postprocessing'] if pair else 'unavailable',
            'runtime_states': [list(s) for s in states], 'actions': actions,
            'completion_claim': parsed['crossing_completion'] if parsed else None,
            'candidate_with_indeterminate_action': status == 'candidate' and 'indeterminate' in actions,
            'uncertainty_text_present': bool(parsed and parsed['uncertainties'].strip()),
            'claims_are_truth': False}


def costs(result):
    if result is None:
        return {'prepare_seconds': None, 'generation_seconds': None, 'output_token_count': None,
                'input_token_count': None, 'visual_token_count': None,
                'peak_allocated_bytes': None, 'peak_reserved_bytes': None, 'hit_token_limit': None}
    info = result.get('input_metadata') or {}
    timing, memory = result.get('timing') or {}, result.get('gpu_memory') or {}
    out = {k: timing.get(k) for k in ('prepare_seconds', 'generation_seconds')}
    out.update(output_token_count=result.get('output_tokens'), input_token_count=info.get('input_tokens'),
               visual_token_count=info.get('visual_tokens'), hit_token_limit=result.get('hit_token_limit'))
    out.update({k: memory.get(k) for k in ('peak_allocated_bytes', 'peak_reserved_bytes')})
    require(out['hit_token_limit'] is None or type(out['hit_token_limit']) is bool, 'invalid token-limit flag')
    for k, value in out.items():
        if value is not None and k != 'hit_token_limit':
            require(type(value) in (int, float) and math.isfinite(value) and value >= 0, 'invalid cost measurement')
    return out


def npy_binding(path, reader):
    """Hash uint8 RGB payload without importing numpy or interpreting images."""
    raw = reader.read(path)
    require(raw[:6] == b'\x93NUMPY', 'invalid processor RGB NPY')
    version = raw[6:8]
    require(version in (b'\x01\x00', b'\x02\x00'), 'unsupported NPY version')
    width = 2 if version[0] == 1 else 4
    size = struct.unpack('<H' if width == 2 else '<I', raw[8:8+width])[0]
    end = 8+width+size
    header = ast.literal_eval(raw[8+width:end].decode('latin1'))
    shape = header['shape']
    require(header['descr'] == '|u1' and header['fortran_order'] is False
            and len(shape) == 4 and shape[-1] == 3 and all(type(x) is int and x > 0 for x in shape),
            'uint8 C-order processor RGB required')
    require(len(raw)-end == math.prod(shape), 'processor RGB payload length mismatch')
    return {'shape': list(shape), 'payload_sha256': sha(raw[end:]), 'file_sha256': sha(raw)}


def verify_input(source, info, expected):
    """Exact source/timing/RGB binding is required; a window name is insufficient."""
    for key in ('source_sha256', 'window_start', 'window_end', 'pts_seconds', 'native_pts', 'time_base'):
        require(source.get(key) == expected[key] and source.get(key) is not None, 'input mismatch: '+key)
    rgb_key = 'rgb_sha256' if 'rgb_sha256' in expected else 'frame_sha256'
    require(source.get(rgb_key) == expected[rgb_key], 'input RGB hash mismatch')
    pts, native, bases = source['pts_seconds'], source['native_pts'], source['time_base']
    bases = bases if isinstance(bases, list) else [bases]*len(pts)
    require(len(pts) == len(native) == len(bases) == 10, 'ten real frames required')
    require(all(abs(float(Fraction(b)*p)-s) < 1e-6 for b,p,s in zip(bases,native,pts)), 'native PTS inconsistent')
    require(all(source['window_start'] <= p < source['window_end'] for p in pts)
            and all(a < b for a,b in zip(pts,pts[1:])), 'unordered/outside PTS')
    for key, source_key in [('source_pts', 'pts_seconds'), ('native_pts', 'native_pts'),
                            ('time_base', 'time_base'), ('roi', 'roi'), ('source_size', 'source_size'),
                            ('relative_indices', 'relative_indices'), ('source_fps', 'fps'),
                            ('window_start', 'window_start'), ('window_end', 'window_end')]:
        require(info.get(key) == source.get(source_key) and key in info, 'processor input binding: '+key)
    require(info.get('observed_frames') == 10 and info.get('processor_frames') == 10
            and info.get('extra_sampling') is False and info.get('temporal_padding_frames') == 0,
            'processor frame sampling differs')
    require(info.get('processor_size') == {'shortest_edge':16384,'longest_edge':3584000},
            'processor pixel budget differs')
    require(info.get('processor_timestamp_coordinates') == [(p-source['window_start'])*source['fps'] for p in pts],
            'processor timestamp mismatch')


def compare_processor(old, new):
    # Input text tokens change with prompt; every other recorded visual setting must match.
    a, b = [{k:v for k,v in info.items() if k != 'input_tokens'} for info in (old, new)]
    require(a == b and bool(a), 'processor metadata mismatch')
    return 'all_recorded_visual_metadata_equal_excluding_text_token_count'


def verify_prompt_pair(original, revised, window_id, old_prompt, new_prompt):
    old = 'Clip ID: '+window_id+'\n'+old_prompt.strip()
    new = 'Clip ID: '+window_id+'\n'+new_prompt.strip()
    require(old != new and original.count(old) == 1 and revised.count(new) == 1,
            'expanded prompt missing or ambiguous')
    require(original.replace(old, new, 1) == revised, 'expanded prompt has a nonprompt difference')


def load_group(folder, name, reader, settings, expected_attempt=None):
    phase, view, count = GROUPS[name]
    summary = reader.json(folder/'summary.json')
    require(summary.get('status') == 'succeeded', 'group not successful: '+name)
    require(isinstance(summary.get('attempt_id'),str) and re.fullmatch(r'[0-9a-f]{32}',summary['attempt_id']),
            'invalid attempt identifier')
    require(summary.get('config') == {'phase':phase, 'view':view, 'settings':settings['generation']},
            'group config mismatch: '+name)
    require(summary.get('pipeline_settings') == settings, 'pipeline settings mismatch')
    require(expected_attempt is None or summary.get('attempt_id') == expected_attempt, 'attempt mismatch')
    require(summary.get('config_hash') == sha(canonical(summary['config'])), 'config hash mismatch')
    binding = summary.get('bindings', {}).get('inputs', {})
    require(summary.get('input_hash') == sha(canonical(binding)), 'input binding hash mismatch')
    require(binding.get('model_files', {}).get('model.safetensors') == MODEL_SHA, 'model binding mismatch')
    expected_prompt = PROMPTS['original' if name == 'v_original' else 'revised']
    require((binding.get('prompt_sha256') if name.startswith('q_') else
             binding.get('prompt_hashes', {}).get(phase)) == expected_prompt, 'prompt binding mismatch')
    return summary


def index_paths(index):
    require(index.get('experiment') == 'EXP-0017' and len(index.get('jobs', [])) == 4,
            'four-job EXP-0017 index required')
    require(index.get('state') == 'completed', 'run index not finalized successfully')
    paths, attempts = {}, {}
    for job in index['jobs']:
        matches = [k for k,(p,v,n) in GROUPS.items() if (p,v) == (job.get('phase'),job.get('view'))]
        require(len(matches) == 1 and matches[0] not in paths, 'duplicate/unknown job group')
        key = matches[0]
        require(job.get('state') == 'succeeded', 'run index not finalized successfully')
        successful = [a for a in job.get('attempts', []) if a.get('status') == 'succeeded']
        require(len(successful) == 1, 'exact successful attempt required')
        require(job.get('expected_records') == GROUPS[key][2], 'record count contract mismatch')
        paths[key], attempts[key] = Path(job['output_path']), successful[0]['attempt_id']
    require(len(set(p.resolve() for p in paths.values())) == 4, 'output roots must be distinct')
    return paths, attempts


def q_assessment(rows):
    """Falsifiable regression guards, never a performance/adoption verdict."""
    result = {}
    for view in ('full_frame', 'fixed_roi'):
        group = [r for r in rows if r['view'] == view]
        by_id = {r['review_clip_id']:r for r in group}
        require(len(group) == 6 and set(by_id) == {q[0] for q in Q}, 'missing/duplicate q assessment rows')
        old_count = sum(r['old']['status'] == 'candidate' for r in group)
        new_count = sum(r['new']['status'] == 'candidate' for r in group)
        q04 = by_id['q04']['new']['status']
        no_attempt = [r for r in group if r['review_clip_id'] != 'q04']
        unresolved = any(r['new']['status'] in ('missing', 'parse_failed', 'indeterminate') for r in group)
        guards = all(by_id[q]['new']['status'] == 'other' for q in ('q01','q06'))
        target_reduced = sum(by_id[q]['new']['status'] == 'candidate' for q in ('q02','q03','q05')) < sum(
            by_id[q]['old']['status'] == 'candidate' for q in ('q02','q03','q05'))
        status = ('not_improvement_q04_candidate_missing' if q04 != 'candidate'
                  else 'unresolved_outputs_prevent_improvement_claim' if unresolved
                  else 'descriptive_regression_targets_met' if target_reduced and guards
                  else 'regression_targets_not_met')
        result[view] = {'old_candidate_count':old_count, 'new_candidate_count':new_count,
                        'reviewed_no_attempt_new_candidate_count':sum(r['new']['status']=='candidate' for r in no_attempt),
                        'q04_old_status':by_id['q04']['old']['status'], 'q04_new_status':q04,
                        'q04_candidate_preserved':by_id['q04']['old']['status']=='candidate' and q04=='candidate',
                        'q04_candidate_present':q04=='candidate', 'status':status,
                        'candidate_reduction_alone_is_success':False, 'adoption_decision':'not_made'}
    return result


def evaluate(root=ROOT, paths=None, index_path=None, baseline_paths=None):
    root, reader = Path(root), Reader()
    pinned = {p:reader.json(root/p,h) for p,h in PINS.items()}
    baseline = pinned['records/EXP-0015/window_reviews.json']
    manifest = pinned['configs/mvp_exp0016_independent_manifest.json']
    labels = pinned['configs/mvp_exp0016_independent_evaluation.json']['labels']
    settings = pinned['configs/mvp0001_settings.json']
    prompts = {k:reader.read(root/'configs'/file, PROMPTS[k]).decode() for k,file in
               [('original','vlm_batch01_prompt.txt'), ('revised','mvp_exp0016_prompt.txt')]}
    attempts, index_hash = {}, None
    if paths is None:
        chosen_index = index_path or root/'runtime/EXP-0017/run-index.json'
        index = reader.json(chosen_index)
        index_hash = sha(reader.read(chosen_index))
        paths, attempts = index_paths(index)
    require(set(paths) == set(GROUPS), 'all four explicit groups required')
    paths = {k:Path(v) for k,v in paths.items()}
    summaries = {k:load_group(p,k,reader,settings,attempts.get(k)) for k,p in paths.items()}
    first = summaries['q_full_frame']['bindings']['inputs']['model_files']
    require(all(s['bindings']['inputs']['model_files'] == first for s in summaries.values()), 'model/processor files differ')
    baseline_paths = baseline_paths or {m:root/'outputs/mvp0001/EXP-0012'/a for m,a in BASE_ATTEMPTS.items()}
    q_rows, historical_load = [], {}
    for view,method in [('full_frame','B'), ('fixed_roi','C')]:
        group = 'q_'+view
        meta = reader.json(Path(baseline_paths[method])/'loading.json')
        historical_load[view] = {key:meta.get(key) for key in (
            'load_seconds','load_peak_allocated_bytes','load_peak_reserved_bytes')}
        for qid,cid,sid,wid,start,end in Q:
            parents = [r for r in baseline if r['method']==method and r['case_id']==cid]
            require(len(parents)==1, 'missing/duplicate EXP-0015 row')
            parent = parents[0]
            label = parent['user_label_revision']['user_label']
            require((label['review_clip_id'],label['source_id'],label['window_id'],label['interval_seconds']) ==
                    (qid,sid,wid,[start,end]), 'q label mapping differs')
            require(parent['paired_trace_valid'], 'invalid baseline trace')
            require(sha(canonical(meta['config']['settings'])) == sha(canonical(settings['generation'])), 'baseline generation differs')
            require(reader.files[ (Path(baseline_paths[method])/'loading.json').resolve() ] == parent['provenance']['loading_metadata_sha256'], 'baseline loading hash differs')
            expected = dict(source_sha256=parent['source_sha256'], window_start=start, window_end=end,
                            pts_seconds=parent['actual_sampled_pts_seconds'], native_pts=parent['actual_native_pts'],
                            time_base=parent['actual_time_base'], rgb_sha256=parent['decoded_source_rgb_sha256'])
            old_dir = Path(baseline_paths[method])/sid/'windows'/wid
            new_dir = paths[group]/sid/'windows'/wid
            old_input = reader.json(old_dir/'input.json',parent['provenance']['input_file_sha256'])
            old_result = reader.json(old_dir/'result.json',parent['provenance']['result_file_sha256'])
            new_input, new_result = reader.json(new_dir/'input.json'), reader.json(new_dir/'result.json')
            # Historical input.json lacks source hash/ROI: pinned run metadata supplies them.
            old_run = reader.json(Path(baseline_paths[method])/sid/'run.json', parent['provenance']['source_run_metadata_sha256'])
            require(old_run['source']['sha256'] == expected['source_sha256'], 'baseline source binding differs')
            verify_input({**old_input,'source_sha256':old_run['source']['sha256'],
                          'roi':old_run['camera']['roi']},old_result['input_metadata'],expected)
            verify_input(new_input,new_result['input_metadata'],expected)
            require(summaries[group]['bindings']['inputs']['videos'].get(sid) == expected['source_sha256'], 'q source contract differs')
            compare_processor(old_result['input_metadata'],new_result['input_metadata'])
            require(new_result['input_metadata']['processor_size'] == settings['processor_size'], 'processor size differs')
            new_rgb = npy_binding(new_dir/'processor_rgb.npy',reader)
            require(new_rgb['shape'] == [new_result['input_metadata']['resized_shape'][i] for i in (0,2,3,1)], 'processor artifact shape differs')
            expanded = reader.read(new_dir/'expanded_prompt.txt').decode()
            require(expanded.count('Clip ID: '+wid+'\n'+prompts['revised'].strip())==1, 'q expanded prompt mismatch')
            old, new = outcome(old_result), outcome(new_result)
            require((old['status']=='candidate') == (parent['counted_output_presence']=='candidate'), 'baseline status differs')
            row = {'review_clip_id':qid, 'case_id':cid, 'source_id':sid, 'window_id':wid, 'view':view,
                   'evaluation_role':parent['evaluation_role'], 'interval_seconds':[start,end],
                   'user_reference':label['reference_label'], 'completion_reference':label['completion_reference'],
                   'old':old, 'new':new, 'old_cost':costs(old_result), 'new_cost':costs(new_result),
                   'pairing':{'source_native_pts_rgb_equal':True, 'recorded_processor_metadata_equal':True,
                              'historical_processor_pixels_equal':'not_established_no_saved_historical_processor_RGB',
                              'historical_expanded_prompt_equal':'not_established_no_saved_historical_expanded_prompt'},
                   'provenance':{'old_input_sha256':sha(reader.read(old_dir/'input.json')),
                                 'new_input_sha256':sha(reader.read(new_dir/'input.json')),
                                 'old_result_sha256':sha(reader.read(old_dir/'result.json')),
                                 'new_result_sha256':sha(reader.read(new_dir/'result.json')),
                                 'source_sha256':expected['source_sha256'], 'source_rgb_sha256':expected['rgb_sha256'],
                                 'new_processor_RGB':new_rgb},
                   'semantic_review':'draft_against_existing_user_observation_no_new_media_adjudication',
                   'model_candidate_conflicts_with_no_attempt_reference':new['status']=='candidate' and qid!='q04',
                   'completion_claim_conflicts_with_clip_end_reference':qid=='q04' and new['completion_claim']=='observed'}
            q_rows.append(row)
        for sid in ('E01_007','E01_030'):
            summary = reader.json(paths[group]/sid/'summary.json')
            expected_ids = {q[3] for q in Q if q[2]==sid}
            require(set(summary.get('completed_windows',[]))==expected_ids and len(summary['completed_windows'])==len(expected_ids)
                    and summary.get('decode',{}).get('eof_reached') is True, 'q completion coverage differs')
    v_rows = []
    require(len(labels)==4 and {x['review_clip_id'] for x in labels}=={'v01','v02','v03','v04'}, 'v label coverage differs')
    for label in labels:
        wid, qid = label['window_id'], label['review_clip_id']
        frozen = next(r for r in manifest['windows'] if r['window_id']==wid)
        sid = frozen['source_id']
        expected = {**frozen['timing'], 'source_sha256':manifest['sources'][sid]['sha256'], 'frame_sha256':frozen['frame_sha256']}
        pair = []
        for group in ('v_original','v_revised'):
            directory = paths[group]/'windows'/wid
            source, result = reader.json(directory/'input.json'), reader.json(directory/'result.json')
            require(all(source.get(k)==v for k,v in frozen['timing'].items()), 'v frozen timing differs')
            verify_input(source,result['input_metadata'],expected)
            require(source.get('roi')==[0,0,1,1] and source.get('prompt_sha256')==PROMPTS['original' if group=='v_original' else 'revised'], 'v input prompt/ROI differs')
            rgb = npy_binding(directory/'processor_rgb.npy',reader)
            expanded = reader.read(directory/'expanded_prompt.txt').decode()
            pair.append((source,result,rgb,expanded))
        a,b = pair
        require({k:v for k,v in a[0].items() if k!='prompt_sha256'} == {k:v for k,v in b[0].items() if k!='prompt_sha256'}, 'v input has nonprompt difference')
        compare_processor(a[1]['input_metadata'],b[1]['input_metadata'])
        require(a[2] == b[2], 'v processor RGB differs')
        verify_prompt_pair(a[3],b[3],wid,prompts['original'],prompts['revised'])
        old,new = outcome(a[1]),outcome(b[1])
        v_rows.append({'review_clip_id':qid,'window_id':wid,'source_id':sid,'source_group':sid,
                       'interval_seconds':[frozen['start'],frozen['end']], 'user_reference':label['label'],
                       'completion_reference':label.get('completion','not_assessed'), 'completion_evaluation':'not_assessed',
                       'location_reference':label.get('location'), 'boundary_relation_reference':label.get('boundary_relation'),
                       'old':old,'new':new,'old_cost':costs(a[1]),'new_cost':costs(b[1]),
                       'pairing':{'identical_frame_hashes_native_pts_and_processor_RGB':True,'expanded_text_difference_only_prompt':True},
                       'semantic_review':'draft_against_existing_user_observation_no_new_media_adjudication',
                       'model_candidate_conflicts_with_non_event_reference':new['status']=='candidate' and label['label']=='non_event',
                       'provenance':{'old_input_sha256':sha(reader.read(paths['v_original']/'windows'/wid/'input.json')),
                                     'new_input_sha256':sha(reader.read(paths['v_revised']/'windows'/wid/'input.json')),
                                     'old_result_sha256':sha(reader.read(paths['v_original']/'windows'/wid/'result.json')),
                                     'new_result_sha256':sha(reader.read(paths['v_revised']/'windows'/wid/'result.json')),
                                     'processor_RGB':a[2], 'source_sha256':expected['source_sha256'],
                                     'source_frame_hashes_sha256':sha(canonical(expected['frame_sha256']))}})
    sa,sb = summaries['v_original'],summaries['v_revised']
    for key in ('pipeline_settings','packages','torch_version','cuda_version','model_parameter_devices'):
        require(sa.get(key)==sb.get(key) and key in sa, 'v environment/config differs: '+key)
    require(sa['bindings']==sb['bindings'], 'v model/processor/code/source bindings differ')
    for group in ('v_original','v_revised'):
        require(sorted(summaries[group]['results'])==sorted(r['window_id'] for r in manifest['windows']), 'v job result coverage differs')
        for sid in manifest['sources']:
            summary = reader.json(paths[group]/(sid+'_summary.json'))
            ids = [r['window_id'] for r in manifest['windows'] if r['source_id']==sid]
            require(sorted(summary.get('completed_windows',[]))==sorted(ids)
                    and summary.get('decode',{}).get('eof_reached') is True, 'v completion coverage differs')
    tables, timing_tables = [], []
    for name, rows in [('q_full_frame',[r for r in q_rows if r['view']=='full_frame']),
                       ('q_fixed_roi',[r for r in q_rows if r['view']=='fixed_roi']), ('v_full_frame',v_rows)]:
        for condition in ('old','new'):
            counts = Counter(r[condition]['status'] for r in rows)
            tables.append({'group':name,'condition':condition,'denominator':len(rows),**{k:counts[k] for k in STATES},
                           'strict_json_valid':sum(r[condition]['strict_json_valid'] for r in rows),
                           'common_parse_valid':sum(r[condition]['common_parse_valid'] for r in rows)})
            measurements = [r[condition+'_cost'] for r in rows]
            totals = {}
            for key in ('prepare_seconds','generation_seconds','output_token_count'):
                values = [m[key] for m in measurements]
                totals['total_'+key] = sum(values) if all(v is not None for v in values) else None
            for key in ('peak_allocated_bytes','peak_reserved_bytes'):
                values = [m[key] for m in measurements]
                totals['maximum_'+key] = max(values) if all(v is not None for v in values) else None
            timing_tables.append({'group':name,'condition':condition,'matched_window_count':len(rows),**totals})
    result = {'schema_version':1,'experiment_id':'EXP-0017','frozen_spec':'EXP-0016',
              'scope':'CPU local saved-output evaluation; selected development windows; candidate counts are descriptive',
              'model_claims_are_ground_truth':False, 'performance_metrics':{k:None for k in ('accuracy','precision','recall','f1','fpr','hourly_false_alarms')},
              'q':q_rows,'v':v_rows,'output_status_tables':tables,'q_regression_assessment':q_assessment(q_rows),
              'matched_window_measurements':timing_tables,'historical_q_job_loading':historical_load,
              'v_grouping':{'window_count':4,'source_group_count':2,'groups':{'E01_004':['v01','v02'],'E01_021':['v03','v04']},
                            'camera_site_independent_blind_test':False,'completion_v01_v03':'not_assessed'},
              'job_measurements':{name:{'attempt_id':s['attempt_id'],'load_seconds':s.get('load_seconds'),
                                       'load_peak_allocated_bytes':s.get('load_peak_allocated_bytes'),
                                       'load_peak_reserved_bytes':s.get('load_peak_reserved_bytes'),
                                       'generation_retries':s.get('generation_retries'),
                                       'summary_sha256':sha(reader.read(paths[name]/'summary.json'))} for name,s in summaries.items()},
              'provenance':{'implementation_sha256':sha(reader.read(Path(__file__))), 'frozen_inputs_sha256':PINS,
                            'run_index_sha256':index_hash,
                            'model_weight_hash_recorded_by_runner':MODEL_SHA, 'prompt_sha256':PROMPTS,
                            'weights_reopened_by_evaluator':False,'source_files_redecoded_by_evaluator':False},
              'limitations':['Parsed actions and completion are model claims, not truth.',
                             'No accuracy/F1/FPR, generalization, real-time suitability or adoption conclusion.',
                             'q original source/native PTS/RGB and recorded visual processor metadata match; historical processor pixel tensors and expanded prompts are not saved and equality cannot be established.',
                             'v saved processor RGB bytes, native frames, environment and settings match; expanded text differs only by prompt. Hidden processor tensors were not saved or recomputed.',
                             'Semantic conflict flags are draft comparisons to existing user observations, not new visual review.',
                             'Generation/preparation totals cover only matching selected windows; model loading is separate. Decoder and queue overhead are not measured here. Background GPU load is uncontrolled, so timing differences do not establish a causal speed improvement.',
                             'v03 attempt is beside the gate in a gap; exact boundary association remains ambiguous. v01/v03 completion not assessed.']}
    reader.verify()
    return result,reader


def write_once(path, raw):
    path = Path(path)
    require(not path.is_symlink() and (not path.exists() or path.stat().st_nlink==1), 'unsafe output')
    if path.exists():
        require(path.read_bytes()==raw, 'refusing to overwrite differing output')
        return
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--run-index',type=Path)
    for name in GROUPS:
        parser.add_argument('--'+name.replace('_','-'),dest=name,type=Path)
    parser.add_argument('--baseline-b',type=Path)
    parser.add_argument('--baseline-c',type=Path)
    args = parser.parse_args(argv)
    explicit = {k:getattr(args,k) for k in GROUPS if getattr(args,k) is not None}
    require(not explicit or len(explicit)==4, 'supply all four output paths or a run index')
    require(not explicit or args.run_index is None, 'choose explicit paths or index')
    require((args.baseline_b is None)==(args.baseline_c is None), 'both baseline roots required')
    baseline = {'B':args.baseline_b,'C':args.baseline_c} if args.baseline_b else None
    result,reader = evaluate(args.root, explicit or None, args.run_index, baseline)
    output = args.root/'records/EXP-0017/comparison.json'
    local = args.root/'runtime/EXP-0017/evaluation-input-index.json'
    # Recheck before any writes; paths and raw response text never enter comparison.
    reader.verify()
    write_once(output,encoded(result))
    write_once(local,encoded({'comparison_sha256':sha(encoded(result)),
                             'files':[{'path':str(p),'sha256':h} for p,h in sorted(reader.files.items())]}))
    print(json.dumps({'comparison_sha256':sha(encoded(result)), 'input_files':len(reader.files)}))


if __name__ == '__main__':
    main()
