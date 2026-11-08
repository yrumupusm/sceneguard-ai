"""Explain fixed-threshold misses from saved anchors; never rerun or retune a model."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.evaluate_person_detector_pair import MANIFEST_SHA, iou, sha


def diagnose(manifest_path, result_dir, evaluation_path, output):
    import numpy as np
    assert sha(manifest_path) == MANIFEST_SHA
    manifest = json.loads(manifest_path.read_text())
    result = json.loads((result_dir / 'result.json').read_text())
    evaluation = json.loads(evaluation_path.read_text())
    assert evaluation['person_threshold'] == evaluation['iou_threshold'] == .5
    name = 'after-all-anchors.npz'
    assert sha(result_dir / name) == result['artifacts'][name]
    frames = {f['frame_id']: f for f in manifest['frames'] if f['split'] == 'validation'}
    rows, counts = [], Counter()
    with np.load(result_dir / name) as archive:
        assert set(archive.files) == set(frames)
        for evaluated in evaluation['frames']:
            frame = frames[evaluated['frame_id']]
            anchors = archive[frame['frame_id']]
            assert anchors.shape == (8400, 5) and np.isfinite(anchors).all()
            for g in evaluated['after']['unmatched_gt_indices']:
                gt = frame['confirmed_person_boxes'][g]['xyxy']
                overlap = np.array([iou(gt, b[:4]) for b in anchors])
                compatible = overlap >= .5
                best = float(anchors[compatible, 4].max()) if compatible.any() else None
                cause = ('no_iou_compatible_raw_anchor' if best is None else
                         'compatible_anchor_below_fixed_score' if best < .5 else
                         'selection_or_one_to_one_competition')
                counts[cause] += 1
                rows.append(dict(frame_id=frame['frame_id'], source_pts=frame['source_pts'],
                                 gt_index=g, cause=cause,
                                 max_score_at_iou_ge_05=best,
                                 max_raw_iou=float(overlap.max())))
    assert len(rows) == evaluation['metrics']['after']['fn']
    scores = [r['max_score_at_iou_ge_05'] for r in rows if r['max_score_at_iou_ge_05'] is not None]
    report = dict(schema_version=1, missed_gt_rows=len(rows), causes=dict(counts),
                  compatible_anchor_score_range=[min(scores), max(scores)] if scores else None,
                  rows=rows, input_sha256=dict(manifest=sha(manifest_path), result=sha(result_dir/'result.json'),
                       evaluation=sha(evaluation_path), raw_anchors=sha(result_dir/name)),
                  script_sha256=sha(__file__), new_inference=False, threshold_changed=False,
                  limitation='Output symptom only; does not establish why training changed scores.')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'rows'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('manifest', 'result-dir', 'evaluation', 'output'):
        parser.add_argument('--'+key, type=Path, required=True)
    args = parser.parse_args()
    diagnose(args.manifest, args.result_dir, args.evaluation, args.output)
