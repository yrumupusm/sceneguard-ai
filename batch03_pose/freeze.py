# SPDX-License-Identifier: AGPL-3.0-only
"""CPU-only package/source/environment freeze. Never import or construct a model."""
import importlib.metadata
import json
import platform
import subprocess
import sys
from pathlib import Path
from batch03_pose.prepare import ROOT,sha
from orchestration.batch03_pose_command import SETTINGS,COCO17


def freeze():
    env=ROOT/'.venv-pose-batch03';local=ROOT/'runtime/BATCH-0003'
    if Path(sys.executable).absolute()!=env/'bin/python':raise ValueError('isolated interpreter required')
    for name,version in {'ultralytics':'8.4.192','torch':'2.5.1+cu124','torchvision':'0.20.1+cu124','av':'16.0.1','numpy':'2.2.6','opencv-python':'4.12.0.88'}.items():
        if importlib.metadata.version(name)!=version:raise ValueError('fixed version differs '+name)
    packages={d.metadata['Name']:d.version for d in importlib.metadata.distributions()}
    lock=ROOT/'requirements-pose-batch03-lock.txt'
    lock.write_text('# Isolated Python3.10 Linux; torch/torchvision official cu124 wheels; no extras.\n'+''.join(f'{n}=={v}\n' for n,v in sorted(packages.items(),key=lambda kv:kv[0].lower())))
    inventory=local/'environment-inventory.json'
    inventory.write_text(json.dumps(dict(python=sys.version,platform=platform.platform(),executable=str(sys.executable),packages=packages,
        pip_check=subprocess.check_output([sys.executable,'-m','pip','check'],text=True)),indent=2)+'\n')
    files={str(p.relative_to(ROOT)):sha(p) for p in [lock,inventory,env/'pyvenv.cfg',env/'bin/python',local/'cpu-import-check.json',local/'official-source-parity.json',local/'official/checkpoint-verification.json',local/'preservation-before.json',local/'frame-binding.json']}
    installed={}
    for d in importlib.metadata.distributions():
        for rel in d.files or []:
            p=Path(d.locate_file(rel)).resolve()
            if p.is_file() and p.is_relative_to(env) and '__pycache__' not in p.parts and p.suffix!='.pyc':installed[str(p.relative_to(ROOT))]=sha(p)
    index=local/'environment-files.local.json';index.write_text(json.dumps(installed,indent=2,sort_keys=True)+'\n');files[str(index.relative_to(ROOT))]=sha(index)
    binding=json.loads((local/'frame-binding.json').read_text());checkpoint=json.loads((local/'official/checkpoint-verification.json').read_text())
    d=dict(schema_version=1,batch='BATCH-0003',experiment='EXP-0021',settings=SETTINGS,coco17=list(COCO17),
        model=dict(name='YOLO26m-Pose',package='ultralytics',version='8.4.192',tag='v8.4.192',source_commit='922563eab42b778445e55a2edbabb6974eed8e4b',license='AGPL-3.0; local research evaluation only; integration/public deployment requires separate license review',**checkpoint),
        frames=binding['frames'],windows=binding['windows'],sampling=binding['sampling'],historical_pins=binding['historical_pins'],
        environment=dict(packages=packages,files=files,file_index=str(index.relative_to(ROOT))),
        boundary_scope='existing camera lines pinned only; not fence-top/other-side calibration; no crop/track/rule inference',
        review_gate='retained estimates are not visible-joint GT; require independent local human correspondence review before any rule',
        limits=dict(max_unique_frames=300,max_window_fps=10,new_checkpoints=1,training=False,rule=False,tracking=False,external_media=False))
    (ROOT/'configs/batch0003_pose_manifest.json').write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
    print('Frozen packages',len(packages),'installed files',len(installed),'frames',len(d['frames']))

if __name__=='__main__':freeze()
