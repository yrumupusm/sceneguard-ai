"""Frozen EXP74 person-detection baseline; CPU inference only, no fitting.

The initial EXP68 checkpoint is an exact person-row slice of official YOLO26m,
saved before optimizer steps. This keeps A and future B/C on the same head.
"""
import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.evaluate_person_detector_pair import match, sha, validate_predictions
from scripts.diagnose_person_overfit import state_hash, CHECKPOINTS, PRIOR


def write(path, data):
    with path.open('x', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def summarize(frames, predictions, evaluation_split='development'):
    rows = validate_predictions(predictions, frames)
    detail, people = [], []
    for f in frames:
        p = rows[f['frame_id']]
        r = match([b['xyxy'] for b in f['confirmed_person_boxes']], p['boxes'], p['person_scores'])
        detail.append(dict(frame_id=f['frame_id'], split=f['split'], event_group=f['event_group'],
                           capture_reservation=f['capture_reservation'], source_pts=f['source_pts'], **r))
        matched = {m['gt_index'] for m in r['matches']}
        for i, b in enumerate(f['confirmed_person_boxes']):
            x1, y1, x2, y2 = b['xyxy']
            scale = 640 / max(f['source_size'])
            area = (x2-x1)*(y2-y1)*scale*scale
            size = 'small' if area < 32**2 else 'medium' if area < 96**2 else 'large'
            people.append(dict(frame_id=f['frame_id'], gt_id=b['id'], gt_index=i,
                event_group=f['event_group'], split=f['split'], baseline_detected=i in matched,
                size_at_640=size, native_height=y2-y1, input_height=(y2-y1)*scale,
                occlusion_level=None, posture_label=None))
    groups = {}
    for key in sorted({r['split'] for r in detail} | {'event:'+r['event_group'] for r in detail}):
        rr = [r for r in detail if r['split']==key or 'event:'+r['event_group']==key]
        count = {k:sum(r[k] for r in rr) for k in ('tp','fp','fn')}
        tp, fp, fn = (count[k] for k in ('tp','fp','fn'))
        groups[key] = dict(**count, frames=len(rr), precision=tp/(tp+fp) if tp+fp else None,
            recall=tp/(tp+fn) if tp+fn else None, f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None)
    conditions = {}
    for split in sorted({f['split'] for f in frames}):
        conditions[split] = {}
        for size in ('small','medium','large'):
            pp = [p for p in people if p['split']==split and p['size_at_640']==size]
            conditions[split][size] = dict(gt_rows=len(pp), detected=sum(p['baseline_detected'] for p in pp),
                                            missed=sum(not p['baseline_detected'] for p in pp))
        empties = {f['frame_id'] for f in frames if f['split']==split and not f['confirmed_person_boxes']}
        conditions[split]['explicit_empty'] = dict(frames=len(empties),
            false_positive_boxes=sum(r['fp'] for r in detail if r['frame_id'] in empties),
            false_positive_frames=sum(r['fp']>0 for r in detail if r['frame_id'] in empties))
    return dict(groups=groups, conditions=conditions, frames=detail, people=people,
        confidence=.5, iou_threshold=.5, recovery_denominator=sum(r['fn'] for r in detail if r['split']==evaluation_split),
        future_recovered=None, future_new_misses=None, independent_test=False,
        size_definition='sqrt native bbox area after 640-square letterbox scale: <32/<96/otherwise; not COCO native-area AP',
        temporal_person_identity_known=False, event_counts_are_frame_box_rows=True)


def execute(manifest_path, output, evaluation_split='development'):
    if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
        raise ValueError('CPU-only: set CUDA_VISIBLE_DEVICES empty before launch')
    manifest = json.loads(manifest_path.read_text())
    frames = manifest['frames']
    if not frames or not all(f['person_completeness_verified'] for f in frames):
        raise ValueError('Only full-person reviewed frames allowed')
    for f in frames:
        for kind in ('image','label'):
            if sha(manifest_path.parent/f[kind]) != f[kind+'_sha256']:
                raise ValueError('Input changed: '+f['frame_id']+' '+kind)
    checkpoint = PRIOR/'initial.pt'
    if sha(checkpoint) != CHECKPOINTS['initial']:
        raise ValueError('Pretrained initial checkpoint changed')
    output.mkdir(parents=True, exist_ok=False)
    from scripts.exp0066_yolo import configure_offline
    configure_offline(output)
    import numpy as np
    import torch
    import ultralytics
    from scripts.train_person_detector import image_tensor, raw_forward
    if ultralytics.__version__ != '8.4.192' or torch.cuda.is_initialized():
        raise ValueError('Pinned CPU environment required')
    torch.set_num_threads(4)
    torch.manual_seed(68)
    torch.use_deterministic_algorithms(True)
    torch.backends.mkldnn.deterministic = True
    saved = torch.load(checkpoint, map_location='cpu', weights_only=False)
    if saved['epoch'] != 0 or saved['optimizer_steps'] != 0:
        raise ValueError('A must be saved before training')
    model = saved['model'].float().cpu().eval().requires_grad_(False)
    if any(not torch.equal(v, saved['state_dict'][k]) for k,v in model.state_dict().items()):
        raise ValueError('Saved state/model disagree')
    before = state_hash(model)
    write(output/'invocation.json', dict(argv=sys.argv, manifest_sha256=sha(manifest_path),
        initial_checkpoint_sha256=sha(checkpoint), initial_epoch=0, initial_steps=0,
        source_sha256={p:sha(ROOT/p) for p in ('scripts/evaluate_exp0074_baseline.py',
            'scripts/train_person_detector.py','scripts/evaluate_person_detector_pair.py')},
        device='cpu', torch_version=torch.__version__, ultralytics_version=ultralytics.__version__,
        image_size=640, dtype='float32', square_letterbox=True, extra_nms=False,
        native_one2one_topk=300, save_confidence=.05, eval_confidence=.5, eval_iou=.5,
        dataset_frozen_before_forward=True, no_training=True, evaluation_split=evaluation_split))
    predictions, raw = [], {}
    start = time.monotonic()
    with torch.inference_mode():
        for index, f in enumerate(frames):
            tensor, g = image_tensor(f, manifest_path.parent, 'cpu')
            decoded = model.model[-1]._inference(raw_forward(model,tensor)['one2one'])[0].T
            boxes, scores = decoded[:,:4].clone(), decoded[:,4]
            for dims, offset, bound in (([0,2],g['left'],g['width']),([1,3],g['top'],g['height'])):
                boxes[:,dims] = ((boxes[:,dims]-offset)/g['ratio']).clamp(0,bound)
            arr = torch.cat([boxes,scores[:,None]],dim=1).numpy().copy()
            if arr.shape != (8400,5) or not np.isfinite(arr).all():
                raise ValueError('Invalid anchors')
            raw[f['frame_id']] = arr
            selected = torch.topk(scores,300,sorted=True).indices
            selected = selected[(scores[selected]>=.05)&(boxes[selected,2]>boxes[selected,0])&(boxes[selected,3]>boxes[selected,1])]
            predictions.append(dict(frame_id=f['frame_id'], image_sha256=f['image_sha256'],
                source_pts=f['source_pts'],boxes=boxes[selected].tolist(),person_scores=scores[selected].tolist()))
            if (index+1)%25==0:
                print(json.dumps(dict(frames=index+1,seconds=time.monotonic()-start)),flush=True)
    if state_hash(model)!=before or torch.cuda.is_initialized():
        raise ValueError('Inference mutated model or initialized GPU')
    with (output/'A-predictions.jsonl').open('x') as stream:
        for row in predictions: stream.write(json.dumps(row)+'\n')
    np.savez_compressed(output/'A-all-anchors.npz',**raw)
    results = summarize(frames,predictions,evaluation_split=evaluation_split)
    results.update(manifest_sha256=sha(manifest_path), initial_checkpoint_sha256=sha(checkpoint),
                   model_state_preserved=True, model_state_sha256=before, seconds=time.monotonic()-start)
    write(output/'A-evaluation.json',results)
    print(json.dumps(results['groups'],ensure_ascii=False),flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    execute(args.manifest.resolve(),args.output.resolve())
