"""CPU-only local panels and diagnostic summaries; no semantic ground truth."""
import json
from pathlib import Path
from orchestration.mock_job import atomic_json
from orchestration.batch02_cv_command import ROOT, manifest, output_path


def iou(a, b):
    overlap = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    union = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - overlap
    return overlap/union if union > 0 else 0


def fcos_boxes(item):
    rows = [json.loads(line) for line in (ROOT / item['cache_path']).read_text().splitlines()]
    rows = [r for r in rows if r['native_pts'] == item['native_pts'] and r['time_base'] == item['time_base']]
    if len(rows) != 1 or rows[0]['pts'] != item['pts_seconds']:
        raise ValueError('exact FCOS cache row differs')
    row = rows[0]
    return [dict(xyxy=b, score=s) for b, s in zip(row['boxes'], row['scores']) if s >= .5]


def generate(smoke_attempt, remaining_attempt):
    import numpy as np
    from PIL import Image, ImageDraw
    d = manifest()
    summaries = [json.loads((output_path(stage, attempt) / 'summary.json').read_text())
                 for stage, attempt in [('smoke', smoke_attempt), ('remaining', remaining_attempt)]]
    if any(s['status'] != 'succeeded' for s in summaries):
        raise ValueError('both stages must have succeeded')
    records = [r for s in summaries for r in s['results']]
    if len(records) != 11 or {r['frame_id'] for r in records} != {r['frame_id'] for r in d['frames']}:
        raise ValueError('exactly eleven unique diagnostic results required')
    target = ROOT / 'outputs/batch0002/cv/comparison'
    target.mkdir(parents=True, exist_ok=False)
    regions = json.loads((ROOT / 'outputs/cv_phase2c/review_locations.json').read_text())
    public, overlaps = [], []
    for item in d['frames']:
        result = next(r for r in records if r['frame_id'] == item['frame_id'])
        baseline = fcos_boxes(item)
        image = Image.fromarray(np.load(ROOT / item['rgb_path'], allow_pickle=False))
        panels = []
        for title, boxes, color in [('Original full RGB', [], 'white'),
            ('Historical FCOS person >=0.5', baseline, 'lime'),
            ('RF-DETR Medium person >0.5', result['persons'], 'orange')]:
            panel = image.copy()
            draw = ImageDraw.Draw(panel)
            for box in boxes:
                draw.rectangle(box['xyxy'], outline=color, width=3)
                draw.text((box['xyxy'][0], box['xyxy'][1]), f"{box['score']:.3f}", fill=color)
            panel = panel.resize((960, 540))
            draw = ImageDraw.Draw(panel)
            draw.rectangle((0, 0, 960, 25), fill='black')
            draw.text((8, 6), title + ' | DIAGNOSTIC ONLY; exact visual review pending', fill='white')
            panels.append(panel)
        canvas = Image.new('RGB', (2880, 540))
        for index, panel in enumerate(panels):
            canvas.paste(panel, (index*960, 0))
        canvas.save(target / (item['frame_id'] + '.png'))
        public.append(dict(frame_alias=item['frame_id'], fcos_person_count=len(baseline),
            rfdetr_person_count=len(result['persons']), predict_seconds=result['predict_seconds'],
            timing_label=result['timing_label'], visual_person_recovery=None, duplicates=None,
            background_false_positive=None, full_body_quality=None))
        if item['source_id'] == 'E01_030' and str(item['requested_seconds']) in regions:
            for name, rect in regions[str(item['requested_seconds'])].items():
                original = [float(v)*2 for v in rect]
                overlaps.append(dict(frame_id=item['frame_id'], region=name,
                    meaning='pre-existing Codex approximate review region only; not GT; overlapping regions may share boxes',
                    fcos_max_iou=max((iou(b['xyxy'], original) for b in baseline), default=0),
                    rfdetr_max_iou=max((iou(b['xyxy'], original) for b in result['persons']), default=0)))
    atomic_json(target / 'tentative-overlaps.local.json', dict(diagnostic_only=True, rows=overlaps))
    atomic_json(target / 'public-summary.json', dict(experiment='EXP-0019', adoption='adopt_on_hold',
        rows=public, precision=None, recall=None, f1=None,
        visual_review='unknown; only prior human03084 approach3 and03090 climbing3 observations are established',
        sampled_vlm_input_sufficiency='separate human bundle reviewed; q04 B/C individual adequacy and v03 boundary crossing remain uncertain; CV does not resolve these',
        excluded='v native pose unreviewed; no tracker/ROI/event/PoC changes',
        timing='single-pass instrumented eager FP32; first frame per stage cold; FCOS historical not controlled',
        model_load_seconds=[s['model_construction_load_seconds'] for s in summaries],
        load_peak_allocated_bytes=[s['load_peak_allocated_bytes'] for s in summaries],
        load_peak_reserved_bytes=[s['load_peak_reserved_bytes'] for s in summaries]))
    return target


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke-attempt', required=True)
    parser.add_argument('--remaining-attempt', required=True)
    args = parser.parse_args()
    print(generate(args.smoke_attempt, args.remaining_attempt))
