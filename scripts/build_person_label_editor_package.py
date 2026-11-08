"""Bind an immutable editor package to actual prepared frames and detector drafts."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def execution_binding(preparation, proposals, result_path, receipt_path):
    from orchestration.person_label_repair_command import RUNTIME, MODEL_SPEC_SHA, output_path
    from orchestration.queue import digest
    result = json.loads(result_path.read_text())
    receipt = json.loads(receipt_path.read_text())
    attempt = result['queue_attempt']
    directory = output_path('draft75', attempt)
    if (result_path.resolve() != directory/'result.json' or proposals.resolve() != directory/'proposals.jsonl'
            or receipt_path.resolve() != RUNTIME/'attempts'/attempt/'manifest.json'):
        raise ValueError('Canonical output and receipt paths required')
    with sqlite3.connect('file:'+str(RUNTIME/'queue.sqlite3')+'?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        row = db.execute('SELECT j.*, a.status AS attempt_status, a.result_manifest FROM jobs j JOIN attempts a USING(job_id) WHERE a.attempt_id=?', (attempt,)).fetchone()
    if row is None or row['command'] != 'person-label-repair' or row['status'] != 'succeeded' or row['attempt_status'] != 'succeeded':
        raise ValueError('Successful canonical draft inference required')
    config = json.loads(row['config_json'])
    if (row['config_hash'] != digest(config) or row['input_hash'] != digest(json.loads(row['input_json']))
            or row['result_manifest'] != str(receipt_path.resolve())
            or receipt['execution_status'] != 'succeeded' or receipt['attempt_id'] != attempt
            or receipt['result_sha256'] != sha(result_path) or receipt['result_path'] != str(directory)
            or result['status'] != 'draft_proposals_complete' or result['model_id'] != 'yolo26x'
            or result['frames_scored'] != 75 or result['proposals_sha256'] != sha(proposals)
            or result['preparation_sha256'] != sha(preparation)
            or result['model_spec_sha256'] != MODEL_SPEC_SHA
            or config['files']['preparation'] != {'path':str(preparation.resolve()), 'sha256':sha(preparation)}
            or result['training_release'] is not False or result['human_verified'] is not False):
        raise ValueError('Executed result/input/receipt binding differs')
    for key in ('command','job_id','run_id','task_id','dispatch_id','owner','code_sha','source_hash','input_hash','config_hash'):
        if receipt['registration'][key] != row[key]:
            raise ValueError('Receipt registration differs')
    for key in ('code_sha','source_hash','input_hash'):
        if result[key] != row[key]:
            raise ValueError('Result provenance differs')
    spec_file = config['files']['model_spec']
    if sha(spec_file['path']) != MODEL_SPEC_SHA or spec_file['sha256'] != MODEL_SPEC_SHA:
        raise ValueError('Pinned model specification changed')
    spec = json.loads(Path(spec_file['path']).read_text())
    expected = dict(queue_command='person-label-repair', queue_attempt=attempt, code_sha=row['code_sha'],
                    source_hash=row['source_hash'], input_hash=row['input_hash'], model_spec_sha256=MODEL_SPEC_SHA,
                    checkpoint_sha256=spec['bindings'][spec['checkpoint_path']])
    return dict(result_sha256=sha(result_path), receipt_sha256=sha(receipt_path), **expected)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(preparation, proposals, result_path, receipt_path, output):
    from scripts.infer_person_label_repair import proposal_rows
    binding = execution_binding(preparation, proposals, result_path, receipt_path)
    prepared = json.loads(preparation.read_text())
    rows = [json.loads(line) for line in proposals.read_text().splitlines()]
    predictions = {row['frame_id']: row for row in rows}
    if (len(predictions) != len(rows) or set(predictions) != {f['frame_id'] for f in prepared['frames']}
            or prepared['training_release'] is not False or prepared['protected_school_or_test_used'] is not False):
        raise ValueError('Exact held preparation frames and draft-only status required')
    frames = []
    for frame in prepared['frames']:
        pred = predictions[frame['frame_id']]
        expected = {k:v for k,v in binding.items() if k not in ('result_sha256','receipt_sha256')}
        if (pred['model_provenance'] != expected or pred['proposals'] != proposal_rows(frame, pred['detector_output'], binding['model_spec_sha256'])
                or pred['training_release'] is not False or pred['detector_proposals_are_ground_truth'] is not False):
            raise ValueError('Model row provenance or native proposals differ')
        for key in ('frame_id', 'case_number', 'split', 'frame_index', 'source_pts', 'native_pts_tick', 'source_rgb_sha256', 'image', 'original_annotations', 'original_boxes_by_origin'):
            if pred[key] != frame[key]:
                raise ValueError('Prediction frame/source differs: ' + key)
        if sha(frame['image']['path']) != frame['image']['sha256']:
            raise ValueError('Prepared image changed')
        candidates = [dict(id=f'original-{i}', kind='original', label=f'기존 {i+1}',
                           xyxy=box['xyxy'], score=None, annotation=box)
                      for i, box in enumerate(frame['original_boxes_by_origin']['1'])]
        for i, proposal in enumerate(pred['proposals']):
            if proposal['human_verified'] is not False or proposal['training_eligible'] is not False:
                raise ValueError('Detector proposal cannot carry human approval')
            if not proposal['valid_box']:
                continue
            candidates.append(dict(id=proposal['proposal_id'], kind='model', label=f'초안 {i+1}',
                                   xyxy=proposal['xyxy'], score=proposal['person_score'],
                                   proposal_provenance=proposal))
        frames.append(dict(frame_id=frame['frame_id'], case_number=frame['case_number'], split=frame['split'],
            event_group=frame['event_group'], source_sha256=frame['source_sha256'], source_size=frame['source_size'],
            source_pts=frame['source_pts'], native_pts_tick=frame['native_pts_tick'], frame_index=frame['frame_index'],
            source_rgb_sha256=frame['source_rgb_sha256'], image_path=frame['image']['path'], image_sha256=frame['image']['sha256'],
            original_boxes_by_origin=frame['original_boxes_by_origin'], frame_origin_certified=False,
            original_label_hashes=sorted(frame['label_file_bindings'].values()),
            completeness_answer_version=frame['answer_version'], candidates=candidates))
    result = dict(schema_version=1, experiment_id='EXP-0067', training_release=False,
                  preparation_sha256=sha(preparation), proposals_sha256=sha(proposals), execution_binding=binding, frames=frames)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(frames=len(frames), package_sha256=sha(output), training_release=False)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('preparation', 'proposals', 'result', 'receipt', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    build(args.preparation, args.proposals, args.result, args.receipt, args.output)
