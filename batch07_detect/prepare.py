# SPDX-License-Identifier: AGPL-3.0-only
"""CPU-only byte copies; loaders can never write caches into historical draft."""
import json
from pathlib import Path
import shutil
from orchestration.mock_job import atomic_json
from orchestration.vlm_command import file_hash
from orchestration.batch07_detect_command import ROOT,LOCAL,DATA,dataset_files

TREE=LOCAL/'train-data'


def prepare_tree():
    if TREE.exists():raise ValueError('isolated data already exists; never overwrite')
    before=dataset_files()
    summary=json.loads((DATA/'summary.json').read_text())
    if summary['usable_for_training'] is not False or summary['D0_passed'] is not False:
        raise ValueError('historical pending metadata required')
    records={}
    for split,count in [('train',210),('valid',20)]:
        images=sorted((DATA/split/'images').glob('*'))
        labels=sorted((DATA/split/'labels').glob('*.txt'))
        if len(images)!=count or len(labels)!=count:raise ValueError('fixed split count differs')
        for source in images+labels:
            rel=source.relative_to(DATA);target=TREE/rel
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source,target)
            if file_hash(source)!=file_hash(target):raise ValueError('bytecopy differs')
            records[str(rel)]=file_hash(target)
    # Intentionally no test key, path or files: validation uses only fixed valid20.
    yaml='path: '+str(TREE)+'\ntrain: train/images\nval: valid/images\nnc: 1\nnames: [person]\n'
    (TREE/'data.yaml').write_text(yaml)
    records['data.yaml']=file_hash(TREE/'data.yaml')
    atomic_json(LOCAL/'dataset-freeze.local.json',before)
    atomic_json(LOCAL/'train-data-manifest.local.json',dict(files=records,train=210,valid=20,test_used=0,
        method='independent bytecopy; historical source bytes preserved; loader caches local to copy'))
    if dataset_files()!=before:raise ValueError('historical dataset changed')
    return verify_tree()


def verify_tree():
    d=json.loads((LOCAL/'train-data-manifest.local.json').read_text())
    if (d['train'],d['valid'],d['test_used'])!=(210,20,0):raise ValueError('split contract differs')
    for name,expected in d['files'].items():
        p=TREE/name
        if name.startswith('test/') or not p.resolve().is_relative_to(TREE.resolve()) or p.is_symlink() or file_hash(p)!=expected:
            raise ValueError('isolated train data differs')
        if name!='data.yaml':
            original=DATA/name
            if file_hash(original)!=expected or p.stat().st_ino==original.stat().st_ino:
                raise ValueError('independent identical data copy required')
    actual={str(p.relative_to(TREE)) for p in TREE.rglob('*') if p.is_file() and p.suffix!='.cache'}
    if actual!=set(d['files']) or (TREE/'test').exists():raise ValueError('unexpected data/test files')
    yaml=(TREE/'data.yaml').read_text()
    if yaml!='path: '+str(TREE)+'\ntrain: train/images\nval: valid/images\nnc: 1\nnames: [person]\n':
        raise ValueError('isolated YAML contract differs')
    return d


if __name__=='__main__':
    print(json.dumps(prepare_tree(),sort_keys=True))
