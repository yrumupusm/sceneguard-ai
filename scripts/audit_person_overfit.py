"""Recompute EXP69 counts with subset-DP and reconstruct all four state hashes on CPU."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main(folder):
    if os.environ.get('CUDA_VISIBLE_DEVICES')!='':
        raise ValueError('CPU only')
    from scripts.exp0066_yolo import configure_offline
    configure_offline(folder/'audit-settings')
    import numpy as np
    import torch
    torch.set_num_threads(2)
    read=lambda p:json.loads(Path(p).read_text())
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    result=read(folder/'result.json')
    manifest_path=ROOT/'outputs/model-comparison/exp0067/confirmed-person-v1/manifest.json'
    assert sha(manifest_path)==result['manifest_sha256']
    frames={f['frame_id']:f for f in read(manifest_path)['frames']}
    prior=ROOT/'outputs/model-comparison/exp0068/queued/train5/47adf16ca4fa4145b50e0ee150106c38'
    snapshots={}
    for name,h in result['checkpoint_sha256'].items():
        assert sha(prior/(name+'.pt'))==h
        snapshots[name]=torch.load(prior/(name+'.pt'),map_location='cpu',weights_only=False)['state_dict']
    for name,h in result['artifacts'].items():
        assert sha(folder/name)==h,name
    audit={}
    for condition,proof in result['state_preservation'].items():
        weight=snapshots[proof['weights']];bn=snapshots[proof['bn_statistics']]
        digest=hashlib.sha256();bn_count=0
        for key,value in weight.items():
            if key.endswith(('.running_mean','.running_var','.num_batches_tracked')):
                value=bn[key];bn_count+=1
            digest.update(key.encode());digest.update(str(value.dtype).encode())
            digest.update(str(tuple(value.shape)).encode());digest.update(value.contiguous().numpy().tobytes())
        assert digest.hexdigest()==proof['state_sha256']
        assert proof['unchanged_after_forward'] and bn_count==proof['bn_buffer_count']==372
        rows=[json.loads(l) for l in (folder/(condition+'-predictions.jsonl')).read_text().splitlines()]
        assert len(rows)==75 and {r['frame_id'] for r in rows}==set(frames)
        ev={r['frame_id']:r for r in read(folder/(condition+'-evaluation.json'))['frames']}
        counts={s:dict(tp=0,fp=0,fn=0) for s in ('train','validation')}
        with np.load(folder/(condition+'-all-anchors.npz')) as raw:
            for row in rows:
                fid=row['frame_id'];frame=frames[fid];a=raw[fid]
                assert a.shape==(8400,5) and np.isfinite(a).all()
                assert row['image_sha256']==frame['image_sha256'] and row['source_pts']==frame['source_pts']
                selected=a[np.argsort(-a[:,4],kind='stable')[:300]]
                selected=selected[(selected[:,4]>=.05)&(selected[:,2]>selected[:,0])&(selected[:,3]>selected[:,1])]
                logged=np.array([b+[s] for b,s in zip(row['boxes'],row['person_scores'])],dtype=np.float32).reshape(-1,5)
                assert sorted(map(tuple,selected.tolist()))==sorted(map(tuple,logged.tolist()))
                gt=np.array([b['xyxy'] for b in frame['confirmed_person_boxes']],dtype=np.float64)
                masks={0};predicted=0
                for b in selected[selected[:,4]>=.5,:4].astype(np.float64):
                    predicted+=1
                    inter=np.maximum(0,np.minimum(gt[:,2:],b[2:])-np.maximum(gt[:,:2],b[:2])).prod(axis=1)
                    union=(gt[:,2:]-gt[:,:2]).prod(axis=1)+(b[2:]-b[:2]).prod()-inter
                    edges=np.flatnonzero(inter/union>=.5).tolist()
                    masks=masks|{m|(1<<g) for m in masks for g in edges if not m&(1<<g)}
                tp=max(m.bit_count() for m in masks)
                actual=dict(tp=tp,fp=predicted-tp,fn=len(gt)-tp)
                assert all(actual[k]==ev[fid][k] for k in actual)
                for k,v in actual.items():counts[frame['split']][k]+=v
        assert all(counts[s][k]==result['groups'][condition][s][k] for s in counts for k in counts[s])
        audit[condition]=dict(counts=counts,state_reconstructed=True,exact_raw_to_json=True,frames=75)
    proof=dict(status='passed',scope='same-author secondary arithmetic and state audit; not independent human review',
               algorithm='subset_DP independent of evaluator augmenting paths',conditions=audit,
               result_sha256=sha(folder/'result.json'),audit_script_sha256=sha(__file__),cuda_initialized=torch.cuda.is_initialized())
    with (folder/'audit.json').open('x') as stream:json.dump(proof,stream,indent=2);stream.write('\n')
    print(json.dumps(proof))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--folder',type=Path,required=True)
    main(p.parse_args().folder)
