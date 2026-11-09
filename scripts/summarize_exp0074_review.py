"""Join unchanged A197 predictions with the three new CPU predictions; no inference."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.evaluate_exp0074_baseline import summarize, write
from scripts.evaluate_person_detector_pair import sha
from scripts.prepare_person_bn_comparison import dataset_contract


def merge(manifest_path, old_path, new_path, output):
    manifest=json.loads(manifest_path.read_text());dataset_contract(manifest_path)
    old=json.loads((old_path/'A-evaluation.json').read_text())
    new=json.loads((new_path/'A-evaluation.json').read_text())
    if old['manifest_sha256']!=manifest['parent_manifest_sha256']:
        raise ValueError('Wrong parent baseline')
    subset=manifest_path.parent/'new-frames-only.json'
    if new['manifest_sha256']!=sha(subset):raise ValueError('Wrong new baseline')
    for key in ('initial_checkpoint_sha256','model_state_sha256','confidence','iou_threshold'):
        if old[key]!=new[key]:raise ValueError('Baseline conditions changed: '+key)
    predictions=[]
    for p in (old_path,new_path):
        predictions.extend(json.loads(l) for l in (p/'A-predictions.jsonl').read_text().splitlines())
    result=summarize(manifest['frames'],predictions)
    result.update(manifest_sha256=sha(manifest_path),initial_checkpoint_sha256=old['initial_checkpoint_sha256'],
        reused_frames=197,newly_inferred_frames=3,training_executed=False,
        parents={str(p/'A-evaluation.json'):sha(p/'A-evaluation.json') for p in (old_path,new_path)})
    output.mkdir(parents=True,exist_ok=False);write(output/'A-evaluation.json',result)
    dev={f['frame_id'] for f in manifest['frames'] if f['split']=='development'}
    for filename,rows in [('A-predictions.jsonl',predictions),('A-development-predictions.jsonl',[p for p in predictions if p['frame_id'] in dev])]:
        with (output/filename).open('x') as s:
            for row in rows:s.write(json.dumps(row)+'\n')
    print(json.dumps(result['groups'],ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('manifest','old','new','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();merge(a.manifest.resolve(),a.old.resolve(),a.new.resolve(),a.output.resolve())
