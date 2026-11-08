"""EXP69 CPU-only 2x2 checkpoint/BN-statistic diagnostic on reviewed train/val."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.evaluate_person_detector_pair import MANIFEST_SHA, match, sha, validate_predictions

DATA = ROOT/'outputs/model-comparison/exp0067/confirmed-person-v1/manifest.json'
PRIOR = ROOT/'outputs/model-comparison/exp0068/queued/train5/47adf16ca4fa4145b50e0ee150106c38'
CHECKPOINTS = {'initial': '436426a56cb2699c7be3391b3dc1e4c06b268b357b330e3b1cf13409ee01ef53',
               'last': '42c348982b4788c23fe731ede7117a40098b2fb3c995d6f4faee3687fc5544b9'}
CONDITIONS = {'A_initial': ('initial', 'initial'), 'B_trained': ('last', 'last'),
              'C_trained_initial_bn': ('last', 'initial'), 'D_initial_trained_bn': ('initial', 'last')}


def write(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def state_hash(model):
    digest = hashlib.sha256()
    for key, value in model.state_dict().items():
        digest.update(key.encode())
        digest.update(str(value.dtype).encode())
        digest.update(str(tuple(value.shape)).encode())
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def swap_bn_statistics(target, donor):
    import torch
    target_modules, donor_modules = dict(target.named_modules()), dict(donor.named_modules())
    before = {k: v.clone() for k, v in target.state_dict().items()}
    keys = []
    with torch.no_grad():
        for name, module in target_modules.items():
            if not isinstance(module, torch.nn.modules.batchnorm._BatchNorm):
                continue
            source = donor_modules[name]
            if not isinstance(source, type(module)) or not module.track_running_stats:
                raise ValueError('Matching tracked BN modules required')
            for field in ('running_mean', 'running_var', 'num_batches_tracked'):
                getattr(module, field).copy_(getattr(source, field))
                keys.append((name+'.' if name else '')+field)
    after, reference = target.state_dict(), donor.state_dict()
    for key in before:
        expected = reference[key] if key in keys else before[key]
        if not torch.equal(after[key], expected):
            raise ValueError('BN transplant changed unexpected state '+key)
    return keys


def summarize(frames, predictions):
    rows = validate_predictions(predictions, frames)
    records = []
    for frame in frames:
        pred = rows[frame['frame_id']]
        r = match([b['xyxy'] for b in frame['confirmed_person_boxes']], pred['boxes'], pred['person_scores'])
        records.append(dict(frame_id=frame['frame_id'], split=frame['split'], case_number=frame['case_number'],
                            event_group=frame['event_group'], source_pts=frame['source_pts'], **r))
    groups = {}
    for group in ('train', 'validation', 'case-1', 'case-3', 'case-5'):
        selected = [r for r in records if r['split']==group or 'case-'+str(r['case_number'])==group]
        counts = {k: sum(r[k] for r in selected) for k in ('tp', 'fp', 'fn')}
        tp, fp, fn = (counts[k] for k in ('tp', 'fp', 'fn'))
        groups[group] = dict(**counts, frames=len(selected), gt_rows=tp+fn,
            events=len({r['event_group'] for r in selected}),
            precision=tp/(tp+fp) if tp+fp else None, recall=tp/(tp+fn) if tp+fn else None,
            f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None)
    return dict(groups=groups, frames=records)


def execute(output):
    if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
        raise ValueError('Set CUDA_VISIBLE_DEVICES to empty; this diagnostic is CPU-only')
    if output.exists():
        raise ValueError('Use a fresh output directory')
    if sha(DATA) != MANIFEST_SHA:
        raise ValueError('Fixed reviewed dataset changed')
    manifest = json.loads(DATA.read_text())
    # Read-only live answers before any model operation.
    from orchestration.person_detector_training_command import current_review_contract
    reviews = current_review_contract(manifest)
    frames = manifest['frames']
    if manifest['frame_counts'] != {'train': 50, 'validation': 25}:
        raise ValueError('Fixed train50/validation25 required')
    for f in frames:
        if sha(DATA.parent/f['image']) != f['image_sha256'] or sha(DATA.parent/f['label']) != f['label_sha256']:
            raise ValueError('Changed image/label '+f['frame_id'])
    for name, expected in CHECKPOINTS.items():
        if sha(PRIOR/(name+'.pt')) != expected:
            raise ValueError('Changed checkpoint '+name)
    output.mkdir(parents=True)
    start = time.monotonic()
    from scripts.exp0066_yolo import configure_offline
    configure_offline(output)
    import numpy as np
    import torch
    import ultralytics
    from scripts.train_person_detector import image_tensor, raw_forward
    if ultralytics.__version__ != '8.4.192' or torch.cuda.is_initialized():
        raise ValueError('Pinned environment and no CUDA initialization required')
    torch.set_num_threads(4)
    torch.manual_seed(69)
    torch.use_deterministic_algorithms(True)
    torch.backends.mkldnn.deterministic = True
    saved = {k: torch.load(PRIOR/(k+'.pt'), map_location='cpu', weights_only=False) for k in CHECKPOINTS}
    for cp in saved.values():
        if any(not torch.equal(v, cp['state_dict'][k]) for k, v in cp['model'].state_dict().items()):
            raise ValueError('Saved model/state mismatch')
    sources = {p: sha(ROOT/p) for p in ('scripts/diagnose_person_overfit.py', 'scripts/train_person_detector.py',
               'scripts/evaluate_person_detector_pair.py', 'docs/experiments/EXP-0069-protocol.md')}
    write(output/'invocation.json', dict(argv=sys.argv, device='cpu', cuda_visible_devices='', threads=4,
        torch_version=torch.__version__, ultralytics_version=ultralytics.__version__, source_sha256=sources,
        checkpoint_sha256=CHECKPOINTS, manifest_sha256=MANIFEST_SHA, current_reviews=reviews,
        conditions=CONDITIONS, confidence=.5, iou=.5, new_training=False))
    results, preservation, parity = {}, {}, {}
    for name, (weight_source, statistic_source) in CONDITIONS.items():
        model = copy.deepcopy(saved[weight_source]['model']).float().cpu()
        keys = swap_bn_statistics(model, saved[statistic_source]['model'])
        model.eval().requires_grad_(False)
        before_state = state_hash(model)
        predictions, raw, gt_diagnostics = [], {}, []
        with torch.inference_mode():
            for index, frame in enumerate(frames):
                image, g = image_tensor(frame, DATA.parent, 'cpu')
                heads = raw_forward(model, image)
                decoded = model.model[-1]._inference(heads['one2one'])[0].T
                boxes, scores = decoded[:, :4].clone(), decoded[:, 4]
                for dims, offset, bound in (([0,2], g['left'], g['width']), ([1,3], g['top'], g['height'])):
                    boxes[:, dims] = ((boxes[:, dims]-offset)/g['ratio']).clamp(0, bound)
                arr = torch.cat([boxes, scores[:, None]], dim=1).numpy().copy()
                if arr.shape != (8400,5) or not np.isfinite(arr).all():
                    raise ValueError('Invalid raw anchors')
                raw[frame['frame_id']] = arr
                selected = torch.topk(scores, 300, sorted=True).indices
                selected = selected[(scores[selected]>=.05) & (boxes[selected,2]>boxes[selected,0]) & (boxes[selected,3]>boxes[selected,1])]
                predictions.append(dict(frame_id=frame['frame_id'], image_sha256=frame['image_sha256'],
                    source_pts=frame['source_pts'], boxes=boxes[selected].tolist(), person_scores=scores[selected].tolist()))
                for gt_index, gt in enumerate(frame['confirmed_person_boxes']):
                    b = np.asarray(gt['xyxy'], dtype=np.float64)
                    intersection = np.maximum(0, np.minimum(arr[:,2],b[2])-np.maximum(arr[:,0],b[0])) * np.maximum(0, np.minimum(arr[:,3],b[3])-np.maximum(arr[:,1],b[1]))
                    union = (arr[:,2]-arr[:,0])*(arr[:,3]-arr[:,1])+(b[2]-b[0])*(b[3]-b[1])-intersection
                    overlap = np.divide(intersection, union, out=np.zeros_like(intersection), where=union>0)
                    eligible = overlap>=.5
                    gt_diagnostics.append(dict(frame_id=frame['frame_id'], split=frame['split'], gt_index=gt_index,
                        max_score_at_iou_ge_05=float(arr[eligible,4].max()) if eligible.any() else None))
                if (index+1)%25==0:
                    print(json.dumps(dict(condition=name, frames=index+1, seconds=time.monotonic()-start)), flush=True)
        after_state = state_hash(model)
        if after_state != before_state:
            raise ValueError('Evaluation mutated model state')
        preservation[name] = dict(state_sha256=before_state, unchanged_after_forward=True, bn_buffer_count=len(keys),
                                  weights=weight_source, bn_statistics=statistic_source)
        with (output/(name+'-predictions.jsonl')).open('x') as stream:
            for r in predictions:
                stream.write(json.dumps(r)+'\n')
        np.savez_compressed(output/(name+'-all-anchors.npz'), **raw)
        write(output/(name+'-gt-scores.json'), gt_diagnostics)
        results[name] = summarize(frames, predictions)
        write(output/(name+'-evaluation.json'), results[name])
        if name in ('A_initial','B_trained'):
            prior_name = 'before' if name=='A_initial' else 'after'
            old = [json.loads(l) for l in (PRIOR/(prior_name+'-predictions.jsonl')).read_text().splitlines()]
            val = [f for f in frames if f['split']=='validation']
            old_summary = summarize(val, old)
            current_val = [r for r in results[name]['frames'] if r['split']=='validation']
            if any(any(a[k]!=b[k] for k in ('frame_id','tp','fp','fn')) for a,b in zip(old_summary['frames'],current_val)):
                raise ValueError('CPU/GPU validation matching counts differ')
            with np.load(PRIOR/(prior_name+'-all-anchors.npz')) as prior_raw:
                deltas = [np.abs(raw[f['frame_id']]-prior_raw[f['frame_id']]) for f in val]
            parity[name] = dict(all25_frame_counts_equal=True,
                max_box_pixel_delta=float(max(x[:,:4].max() for x in deltas)),
                max_score_delta=float(max(x[:,4].max() for x in deltas)))
        del model
    if torch.cuda.is_initialized():
        raise ValueError('Unexpected CUDA use')
    # Checkpoints and source images/labels are read-only and hash-verified again.
    for k,h in CHECKPOINTS.items():
        if sha(PRIOR/(k+'.pt')) != h:
            raise ValueError('Checkpoint changed during diagnostic')
    for f in frames:
        if sha(DATA.parent/f['image'])!=f['image_sha256'] or sha(DATA.parent/f['label'])!=f['label_sha256']:
            raise ValueError('Dataset changed during diagnostic')
    write(output/'result.json', dict(status='completed_cpu_diagnostic', schema_version=1,
        experiment_id='EXP-0069', groups={k:v['groups'] for k,v in results.items()},
        state_preservation=preservation, gpu_reproduction=parity, elapsed_seconds=time.monotonic()-start,
        manifest_sha256=MANIFEST_SHA, checkpoint_sha256=CHECKPOINTS, source_sha256=sources,
        device='cpu', cuda_initialized=False, new_training=False, threshold_changed=False,
        school_or_protected_test_used=False, independent_generalization=False,
        artifacts={p.name:sha(p) for p in output.iterdir() if p.is_file()}))
    print(json.dumps(dict(status='completed', groups={k:v['groups'] for k,v in results.items()})), flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    execute(parser.parse_args().output)
