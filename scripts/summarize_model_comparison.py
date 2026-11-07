"""Summarize saved model outputs without treating boxes or temporal overlap as success."""
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
if __package__:
    from .comparison_saved_evidence import checked_rows, result_provenance
else:
    from comparison_saved_evidence import checked_rows, result_provenance

ROOT = Path(__file__).resolve().parents[1]
MODELS = ('evad_vitb_vmaev2', 'evad_vitl', 'stmixer_vitb_vmaev2',
          'internvideo_next_s2_l', 'vjepa2_l', 'vjepa2_1_l', 'videomaev2_b', 'r3d18_exp0064')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def read(path): return json.loads(Path(path).read_text())


def summarize(paths, cohort_path):
    cohort = read(cohort_path); cohort_sha = sha(cohort_path)
    expected = {}; cameras = {}
    for video in cohort['videos']:
        if sha(video['plan']['path']) != video['plan']['sha256']:
            raise ValueError('Window plan changed')
        plan = read(video['plan']['path']); cameras[video['video_id']] = video['camera_id']
        for role, windows in (('regular', plan['windows']), ('diagnostic', plan['supplemental_windows'])):
            for window in windows:
                key = window['window_id']
                if key in expected: raise ValueError('Duplicate planned window')
                expected[key] = dict(role=role,window=window,video_id=video['video_id'],source_sha256=video['source_sha256'])
    models = {}
    for path in paths:
        result, provenance = result_provenance(path,cohort_sha); model = result['model_id']
        if model not in MODELS or model in models: raise ValueError('Unknown or duplicate model')
        if result['cohort_sha256'] != cohort_sha: raise ValueError('Cohort differs')
        if result['status'] not in ('smoke_passed', 'inference_complete'):
            raise ValueError('A successful result is required')
        windows_path = Path(path).parent / 'windows.jsonl'
        if sha(windows_path) != result['windows_sha256']: raise ValueError('Outputs changed')
        seen = set(); groups = defaultdict(lambda: dict(windows=0, windows_with_person_queries=0,
              person_query_rows=0, climbing_candidates=0, climbing_scored_windows=0))
        timing = defaultdict(float)
        for row in checked_rows(windows_path,result,expected):
            key = row['window']['window_id']
            if key in seen or key not in expected: raise ValueError('Unexpected or duplicate output')
            seen.add(key); role, window = expected[key]['role'],expected[key]['window']
            if row['window'] != window: raise ValueError('Output input window differs')
            out = row['output']; group = groups[(role, cameras[row['video_id']])]
            group['windows'] += 1
            threshold = {'evad_vitb_vmaev2': .7, 'evad_vitl': .7, 'stmixer_vitb_vmaev2': .6}.get(model)
            if threshold is not None:
                scores = out['person_scores']; valid = out['valid_boxes']
                if not len(scores) == len(valid) == len(out['boxes']): raise ValueError('Query lengths differ')
                count = sum(bool(v) and s >= threshold for s, v in zip(scores, valid))
                group['person_query_rows'] += count
                group['windows_with_person_queries'] += bool(count)
            score = out.get('climbing_score')
            if score is not None:
                if not math.isfinite(score) or not 0 <= score <= 1: raise ValueError('Invalid climb score')
                if model != 'r3d18_exp0064' or out['threshold'] != .5:
                    raise ValueError('Unexpected raw climbing head or threshold')
                group['climbing_scored_windows'] += 1
                group['climbing_candidates'] += score >= .5
            for name, value in out['timing_seconds'].items():
                if not math.isfinite(value) or value < 0: raise ValueError('Invalid timing')
                timing[name] += value
        if len(seen) != result['scored_windows']: raise ValueError('Output count differs')
        if result['status'] == 'inference_complete' and seen != set(expected):
            raise ValueError('Full-video pass is incomplete')
        for group in groups.values():
            if group['climbing_scored_windows']==0:group['climbing_candidates']=None
            if model not in ('evad_vitb_vmaev2','evad_vitl','stmixer_vitb_vmaev2'):
                group['person_query_rows']=None;group['windows_with_person_queries']=None
        models[model] = dict(status=result['status'], provenance=provenance,
            source_hash=result['source_hash'], model_spec_sha256=result['model_spec_sha256'],
            windows=len(seen), decoded_native_frames=result['decoded_native_frames'],
            elapsed_seconds=result['elapsed_seconds'], load_seconds=result['load_seconds'],
            peak_gpu_allocated_bytes=result['peak_gpu_allocated_bytes'],
            peak_gpu_reserved_bytes=result['peak_gpu_reserved_bytes'], adapter_timing_seconds=dict(timing),
            groups=[dict(role=k[0], camera_id=k[1], **v) for k, v in sorted(groups.items())],
            person_recall=None, climbing_precision=None, climbing_recall=None, intrusion_improvement=None)
    return dict(experiment_id='EXP-0066', cohort_sha256=cohort_sha,summarizer_sha256=sha(__file__),
        evidence_verifier_sha256=sha(Path(__file__).with_name('comparison_saved_evidence.py')),
        models={m: models.get(m, dict(status='no_completed_result_supplied')) for m in MODELS},
        all_eight_full_passes_complete=len(models)==8 and all(x['status']=='inference_complete' for x in models.values()),
        semantic_evaluation_complete=False,
        limitations=['Person-query rows are not unique people or recovered misses.',
                    'AVA climb is not a task-specific CCTV wall-crossing probability.',
                    'Regular and extra diagnostic windows are reported separately.',
                    'No actor correspondence, event success, or intrusion completion is inferred.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result', type=Path, action='append', required=True)
    parser.add_argument('--cohort', type=Path, default=ROOT/'outputs/model-comparison/exp0066/cohort-v1/manifest.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); summary = summarize(args.result, args.cohort)
    with args.output.open('x') as stream: json.dump(summary, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({'output': str(args.output), 'all_eight_full_passes_complete': summary['all_eight_full_passes_complete']}))
