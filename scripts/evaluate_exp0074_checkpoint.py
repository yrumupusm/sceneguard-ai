"""Evaluate a future B/C epoch on the frozen development split; never trains.

Requires an actual-training checkpoint receipt and its exact manifest binding.
The A development subset can be exported without rerunning baseline inference.
"""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.evaluate_person_detector_pair import sha,validate_predictions
from scripts.evaluate_exp0074_baseline import summarize,write


def development_subset(manifest, predictions):
    frames=[f for f in manifest['frames'] if f['split']=='development']
    ids={f['frame_id'] for f in frames}
    chosen=[p for p in predictions if p['frame_id'] in ids]
    validate_predictions(chosen,frames)
    return chosen


def verify_receipt(receipt,checkpoint,manifest_path):
    if (receipt['evidence_kind']!='actual_training_checkpoint'
            or receipt['checkpoint']!={'path':str(checkpoint.resolve()),'sha256':sha(checkpoint)}
            or receipt['provenance']['manifest']!={'path':str(manifest_path.resolve()),'sha256':sha(manifest_path)}
            or receipt['provenance']['variant'] not in ('B','C')
            or receipt['epoch'] not in range(1,6)):
        raise ValueError('Exact real epoch checkpoint and frozen manifest required')


def summarize_epoch(frames,predictions):
    result=summarize(frames,predictions)
    result['condition_missed_gt_rows']=result.pop('recovery_denominator')
    result.pop('future_recovered')
    result.pop('future_new_misses')
    result['reference_A_required_for_recovery']=True
    for person in result['people']:
        person['detected']=person.pop('baseline_detected')
    return result


def evaluate(checkpoint,receipt_path,manifest_path,output):
    if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise ValueError('CPU-only evaluation required')
    receipt=json.loads(receipt_path.read_text());verify_receipt(receipt,checkpoint,manifest_path)
    manifest=json.loads(manifest_path.read_text())
    frames=[f for f in manifest['frames'] if f['split']=='development']
    if not frames or not all(f['person_completeness_verified'] for f in frames):
        raise ValueError('Full-person reviewed development frames required')
    for f in frames:
        for k in ('image','label'):
            if sha(manifest_path.parent/f[k])!=f[k+'_sha256']:raise ValueError('Input changed')
    output.mkdir(parents=True,exist_ok=False)
    from scripts.exp0066_yolo import configure_offline
    configure_offline(output)
    import numpy as np
    import torch
    import ultralytics
    from scripts.train_person_detector import image_tensor,raw_forward
    from scripts.diagnose_person_overfit import state_hash,CHECKPOINTS,PRIOR
    from scripts.prepare_person_bn_comparison import state_hashes,digest,bn_snapshot,assert_bn_fixed
    if ultralytics.__version__!='8.4.192' or torch.cuda.is_initialized():raise ValueError('Pinned CPU environment required')
    torch.set_num_threads(4);torch.manual_seed(68);torch.use_deterministic_algorithms(True)
    torch.backends.mkldnn.deterministic=True
    saved=torch.load(checkpoint,map_location='cpu',weights_only=False)
    model=saved['model'].float().cpu().eval().requires_grad_(False)
    if (saved['provenance']!=receipt['provenance'] or saved['epoch']!=receipt['epoch']
            or saved['optimizer_steps']!=receipt['optimizer_steps']
            or saved['evidence_kind']!='actual_training_checkpoint'
            or any(not torch.equal(v,saved['state_dict'][k]) for k,v in model.state_dict().items())
            or digest(state_hashes(model))!=receipt['state_sha256']):raise ValueError('Checkpoint receipt/state mismatch')
    if receipt['provenance']['variant']=='C':
        initial=PRIOR/'initial.pt'
        if sha(initial)!=CHECKPOINTS['initial']:raise ValueError('Initial checkpoint changed')
        original=torch.load(initial,map_location='cpu',weights_only=False)['model'].float().cpu()
        assert_bn_fixed(model,bn_snapshot(original));del original
    before=state_hash(model);predictions=[];anchors={}
    with torch.inference_mode():
        for f in frames:
            tensor,g=image_tensor(f,manifest_path.parent,'cpu')
            decoded=model.model[-1]._inference(raw_forward(model,tensor)['one2one'])[0].T
            boxes,scores=decoded[:,:4].clone(),decoded[:,4]
            for dims,offset,bound in (([0,2],g['left'],g['width']),([1,3],g['top'],g['height'])):
                boxes[:,dims]=((boxes[:,dims]-offset)/g['ratio']).clamp(0,bound)
            arr=torch.cat([boxes,scores[:,None]],dim=1).numpy().copy()
            if arr.shape!=(8400,5) or not np.isfinite(arr).all():raise ValueError('Invalid anchors')
            anchors[f['frame_id']]=arr
            selected=torch.topk(scores,300,sorted=True).indices
            selected=selected[(scores[selected]>=.05)&(boxes[selected,2]>boxes[selected,0])&(boxes[selected,3]>boxes[selected,1])]
            predictions.append(dict(frame_id=f['frame_id'],image_sha256=f['image_sha256'],source_pts=f['source_pts'],
                boxes=boxes[selected].tolist(),person_scores=scores[selected].tolist()))
    if state_hash(model)!=before or torch.cuda.is_initialized():raise ValueError('Inference changed model or initialized CUDA')
    with (output/'predictions.jsonl').open('x') as stream:
        for r in predictions:stream.write(json.dumps(r)+'\n')
    np.savez_compressed(output/'all-anchors.npz',**anchors)
    result=summarize_epoch(frames,predictions)
    result.update(checkpoint=receipt['checkpoint'],epoch=receipt['epoch'],variant=receipt['provenance']['variant'],
        manifest_sha256=sha(manifest_path),receipt_sha256=sha(receipt_path),model_state_unchanged=True,
        device='cpu',inference_source_sha256=sha(__file__),summarizer_sha256=sha(ROOT/'scripts/evaluate_exp0074_baseline.py'))
    write(output/'evaluation.json',result)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='command',required=True)
    e=s.add_parser('evaluate')
    for k in ('checkpoint','receipt','manifest','output'):e.add_argument('--'+k,type=Path,required=True)
    e=s.add_parser('extract-development')
    for k in ('manifest','predictions','output'):e.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args()
    if a.command=='evaluate':evaluate(a.checkpoint.resolve(),a.receipt.resolve(),a.manifest.resolve(),a.output.resolve())
    else:
        rows=development_subset(json.loads(a.manifest.read_text()),[json.loads(l) for l in a.predictions.read_text().splitlines()])
        with a.output.open('x') as stream:
            for r in rows:stream.write(json.dumps(r)+'\n')
