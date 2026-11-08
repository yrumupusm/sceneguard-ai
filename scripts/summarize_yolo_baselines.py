"""Summarize three completed fixed YOLO baselines; never infer target recall from box counts."""
import argparse
from collections import defaultdict
import json
from pathlib import Path

if __package__:
    from .render_yolo_baseline_panels import YOLO, load_completed, read, sha
else:
    from render_yolo_baseline_panels import YOLO, load_completed, read, sha


def summarize(cohort_path, completions):
    cohort = read(cohort_path); cohort_sha = sha(cohort_path); expected = {}
    for video in cohort['videos']:
        plan_path = Path(video['plan']['path'])
        if sha(plan_path) != video['plan']['sha256']: raise ValueError('Window plan changed')
        plan = read(plan_path)
        for window in plan['windows'] + plan['supplemental_windows']:
            key = window['window_id']
            if key in expected: raise ValueError('Duplicate planned input')
            expected[key] = (video['video_id'], video['source_sha256'], window)
    models = {}
    for path in completions:
        model, rows, binding = load_completed(path, cohort_sha)
        binding['path'] = str(Path(binding['path']).relative_to(Path(__file__).resolve().parents[1]))
        if model in models or set(rows) != set(expected): raise ValueError('Duplicate model or incomplete inputs')
        result_path = Path(read(path)['result']['path']); result = read(result_path)
        groups = defaultdict(lambda: dict(inputs=0, inputs_with_person_boxes=0, person_box_rows=0))
        for key, row in rows.items():
            video_id, source_sha, window = expected[key]
            if row['video_id'] != video_id or row['source_sha256'] != source_sha or row['window'] != window:
                raise ValueError('Actual source and planned input differ')
            if row['box_pts'] != window['sample_pts'][8] or row['box_frame_index'] != window['sample_frame_indices'][8]:
                raise ValueError('Detection frame differs')
            out = row['output']
            if out['person_threshold'] != .5 or out['climbing_score'] is not None or out['actual_input_frames'] != 1:
                raise ValueError('Frozen detector semantics changed')
            if not len(out['valid_boxes']) == len(out['person_scores']) == len(out['boxes']):
                raise ValueError('Box and score lengths differ')
            count = sum(bool(v) and s >= .5 for v,s in zip(out['valid_boxes'],out['person_scores']))
            group = groups[window['role']]
            group['inputs'] += 1; group['inputs_with_person_boxes'] += bool(count); group['person_box_rows'] += count
        models[model] = dict(completion=binding, result_sha256=sha(result_path), queue_attempt=result['queue_attempt'],
            code_sha=result['code_sha'], model_spec_sha256=result['model_spec_sha256'],
            scored_inputs=result['scored_windows'], decoded_native_frames=result['decoded_native_frames'],
            elapsed_seconds=result['elapsed_seconds'], peak_torch_allocated_bytes=result['peak_gpu_allocated_bytes'],
            peak_torch_reserved_bytes=result['peak_gpu_reserved_bytes'], person_threshold=.5, groups=dict(groups),
            person_recall=None, false_positive_rate=None, finetuning_effect=None)
    if set(models) != set(YOLO): raise ValueError('All three baselines must be complete')
    return dict(experiment_id='EXP-0066', status='three_pretrained_detector_baselines_complete',
        cohort_sha256=cohort_sha, summarizer_sha256=sha(__file__),
        verifier_sha256=sha(Path(__file__).with_name('render_yolo_baseline_panels.py')),
        models={m:models[m] for m in YOLO}, new_detector_finetuning_runs=0, semantic_evaluation_complete=False,
        limitations=['Fixed native slot8 from 6219 planned inputs, not inference on every decoded frame.',
                    'Regular and supplemental diagnostic inputs have separate denominators.',
                    'Box rows and inputs containing a box are not unique people, target recall or event success.',
                    'Same score threshold does not establish equal false-positive operating points.',
                    'Elapsed includes loading, official warmup, decoding and integrity checks; total forward calls unmeasured.',
                    'Torch memory peaks are not total GPU memory usage.',
                    'School45 remains protected from training and threshold selection.'])


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort',type=Path,required=True)
    parser.add_argument('--completion',type=Path,action='append',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); data=summarize(args.cohort,args.completion)
    with args.output.open('x') as stream:json.dump(data,stream,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps(dict(output=str(args.output),models=list(data['models']))))
