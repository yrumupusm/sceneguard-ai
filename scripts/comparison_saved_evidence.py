"""Read-only verification of saved comparison provenance; no model imports."""
import hashlib
import json
import math
from itertools import zip_longest
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
QUEUE = Path('/home/jhc7484/dev/sceneguard-orca-lab/runtime/orca-lab/gpu-queue')
MODELS = {'evad_vitb_vmaev2', 'evad_vitl', 'stmixer_vitb_vmaev2',
          'internvideo_next_s2_l', 'vjepa2_l', 'vjepa2_1_l', 'videomaev2_b', 'r3d18_exp0064'}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))


def result_provenance(path, cohort_sha, queue=QUEUE):
    path = Path(path).resolve(); result = read(path)
    if result['model_id'] not in MODELS or result['cohort_sha256'] != cohort_sha:
        raise ValueError('Unexpected model/cohort')
    if result['status'] not in ('smoke_passed', 'inference_complete'):
        raise ValueError('Successful saved result required')
    attempt = result['queue_attempt']
    if len(attempt) != 32 or any(c not in '0123456789abcdef' for c in attempt):
        raise ValueError('Invalid attempt identifier')
    receipt_path = queue/'attempts'/attempt/'manifest.json'; receipt = read(receipt_path)
    if (receipt['attempt_id'] != attempt or receipt['execution_status'] != 'succeeded'
            or receipt['result_sha256'] != sha(path) or Path(receipt['result_path']).resolve() != path.parent
            or receipt.get('synthetic') is not False):
        raise ValueError('Canonical result receipt differs')
    with sqlite3.connect('file:'+str(queue/'queue.sqlite3')+'?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        row = db.execute('SELECT j.*,a.status AS attempt_status,a.result_manifest FROM jobs j '
                         'JOIN attempts a USING(job_id) WHERE a.attempt_id=?', (attempt,)).fetchone()
    keys = ('command','job_id','run_id','task_id','dispatch_id','owner','code_sha','source_hash','input_hash','config_hash')
    if (row is None or row['command'] != 'model-compare' or row['status'] != 'succeeded'
            or row['attempt_status'] != 'succeeded' or row['result_manifest'] != str(receipt_path)
            or any(receipt['registration'].get(k) != row[k] for k in keys)
            or any(result[k] != row[k] for k in ('source_hash','input_hash','code_sha'))):
        raise ValueError('Canonical successful queue rows differ')
    config = json.loads(row['config_json'])
    if (config['model_id'] != result['model_id'] or config['stage'] != result['stage']
            or config['files']['model_spec']['sha256'] != result['model_spec_sha256']):
        raise ValueError('Executed model specification differs')
    spec_entry = config['files']['model_spec']
    if sha(spec_entry['path']) != spec_entry['sha256']: raise ValueError('Model specification changed')
    if sha(path.parent/'windows.jsonl') != result['windows_sha256']: raise ValueError('Saved windows changed')
    return result, dict(result_path=str(path), result_sha256=sha(path), receipt_path=str(receipt_path),
                       receipt_sha256=sha(receipt_path), model_spec=spec_entry, queue_attempt=attempt)


def checked_rows(path, result, expected):
    """Stream all rows for integrity, permitting callers to retain only diagnostics."""
    seen = set()
    with Path(path).open(encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line); key = row['window']['window_id']
            if key in seen or key not in expected: raise ValueError('Unexpected or duplicate output window')
            seen.add(key); planned = expected[key]
            if (row['window'] != planned['window'] or row['video_id'] != planned['video_id']
                    or row['source_sha256'] != planned['source_sha256']):
                raise ValueError('Output source/window correspondence differs')
            if result['model_id'].startswith('evad'):
                out = row['output']
                if out.get('box_coordinate_verification') != 'native_original_person_equals_normalized_action_times_original_size':
                    raise ValueError('EVAD output predates the native coordinate correction')
            yield row
    if len(seen) != result['scored_windows']: raise ValueError('Scored window count differs')
    if result['status'] == 'inference_complete' and seen != set(expected):
        raise ValueError('Incomplete full-video output')


def checked_head_scores(path, raw_result, raw_provenance, expected):
    """Bind CPU advisory scores to their successful trained head and exact raw pass."""
    if __package__:
        from .score_model_comparison_heads import checked_head
    else:
        from score_model_comparison_heads import checked_head
    path = Path(path).resolve(); report = read(path)
    if (report['status'] != 'frozen_head_scored_saved_school_outputs'
            or report['model_id'] != raw_result['model_id']
            or report['raw_provenance'] != raw_provenance
            or report['windows'] != len(expected)
            or report['new_encoder_or_detector_forwards'] != 0
            or report['school_data_used_for_training_or_threshold_selection'] is not False
            or report['semantic_evaluation_complete'] is not False):
        raise ValueError('Frozen CPU scoring provenance differs')
    head_path = Path(report['head_result_path'])
    head, receipt_path, config = checked_head(head_path, raw_result)
    if (sha(head_path) != report['head_result_sha256']
            or sha(receipt_path) != report['head_receipt_sha256']
            or head['head_sha256'] != report['head_sha256']
            or head['selection'] != report['head_selection']):
        raise ValueError('Frozen scoring head differs')
    scores_path = path.parent/'scores.jsonl'
    if sha(scores_path) != report['scores_sha256']: raise ValueError('Saved CPU scores changed')
    raw_path = Path(raw_provenance['result_path'])
    required = {p.resolve() for p in (raw_path, raw_path.parent/'windows.jsonl', head_path, head_path.parent/'head.pt',
                ROOT/'scripts/score_model_comparison_heads.py', ROOT/'scripts/train_comparison_heads.py', Path(__file__))}
    bindings = {Path(p).resolve(): h for p, h in report['bindings'].items()}
    if set(bindings) != required or any(sha(p) != h for p, h in bindings.items()):
        raise ValueError('CPU scoring source/input binding changed')
    seen = set(); selected = {}; threshold = head['selection']['threshold']
    joint = raw_result['model_id'] in {'evad_vitb_vmaev2', 'evad_vitl', 'stmixer_vitb_vmaev2'}
    person_threshold = {'evad_vitb_vmaev2': .7, 'evad_vitl': .7, 'stmixer_vitb_vmaev2': .6}.get(raw_result['model_id'])
    with scores_path.open(encoding='utf-8') as stream:
        for line, native in zip_longest(stream, checked_rows(raw_path.parent/'windows.jsonl', raw_result, expected)):
            if line is None or native is None: raise ValueError('Raw/scored coverage differs')
            row = json.loads(line); wid = row['window']['window_id']
            if wid in seen or wid not in expected: raise ValueError('Duplicate or unknown scored window')
            seen.add(wid); want = expected[wid]
            if (row['window'] != want['window'] or row['video_id'] != want['video_id']
                    or native['window']['window_id'] != wid or row['model_id'] != raw_result['model_id']
                    or row['boxes'] != native['output']['boxes'] or row['person_scores'] != native['output']['person_scores']
                    or row['source_sha256'] != want['source_sha256']
                    or row['head_threshold'] != threshold or row['person_threshold'] != person_threshold
                    or row['intrusion_completed'] is not None or row['intrusion_state_changed'] is not False
                    or row['same_person_verified'] is not False):
                raise ValueError('Scored input or advisory semantics differ')
            scores = row['scores']
            if len(scores) != (100 if joint else 1): raise ValueError('Scored query count differs')
            for i, item in enumerate(scores):
                value = item['climbing_action_score']
                if (not math.isfinite(value) or not 0 <= value <= 1
                        or item['query_index'] != (i if joint else None)
                        or item['climbing_action_candidate'] != (value >= threshold)
                        or item['intrusion_completed'] is not None or item['intrusion_state_changed'] is not False
                        or item['threshold_status'] != 'provisional_official_reference_not_human_calibrated'
                        or item['matched_false_positive_operating_point_verified'] is not False):
                    raise ValueError('Invalid advisory head score')
                combined = (bool(native['output']['valid_boxes'][i]) and row['person_scores'][i] >= person_threshold
                            and value >= threshold) if joint else None
                if item['person_and_action_candidate'] != combined: raise ValueError('Combined person/action candidate differs')
            if want['role'] == 'diagnostic': selected[wid] = row
    if seen != set(expected): raise ValueError('Incomplete frozen CPU scores')
    return report, selected, dict(path=str(path), sha256=sha(path), scores_sha256=report['scores_sha256'])
