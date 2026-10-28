"""CPU-only environment inventory and manifest freeze; never constructs a model."""
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from pathlib import Path

from batch02_cv.prepare import ROOT, sha
from orchestration.batch02_cv_command import SETTINGS


def freeze():
    env = ROOT / '.venv-cv-batch02'
    if Path(sys.executable).absolute() != env / 'bin/python':
        raise ValueError('only the new isolated environment may be frozen')
    inventory = {d.metadata['Name']: d.version for d in importlib.metadata.distributions()}
    for name, version in {'torch': '2.5.1+cu124', 'torchvision': '0.20.1+cu124',
                          'rfdetr': '1.11.2', 'transformers': '5.1.0',
                          'supervision': '0.29.0', 'av': '16.0.1'}.items():
        if importlib.metadata.version(name) != version:
            raise ValueError('fixed package version differs: ' + name)
    lock = ROOT / 'requirements-cv-batch02-lock.txt'
    lock.write_text('# Isolated Python3.10 Linux inventory, torch/vision from official cu124 index.\n'
        '# No training/export extras; freeze includes packaging tools.\n'
        + ''.join(f'{n}=={v}\n' for n, v in sorted(inventory.items(), key=lambda x: x[0].lower())))
    local = ROOT / 'runtime/BATCH-0002/cv'
    evidence = dict(python=sys.version, executable=str(sys.executable), platform=platform.platform(),
        packages=inventory, pip_check=subprocess.check_output([sys.executable, '-m', 'pip', 'check'], text=True))
    (local / 'environment-inventory.json').write_text(json.dumps(evidence, indent=2)+'\n')
    files = {'requirements-cv-batch02-lock.txt': sha(lock),
             'runtime/BATCH-0002/cv/environment-inventory.json': sha(local / 'environment-inventory.json'),
             '.venv-cv-batch02/pyvenv.cfg': sha(env / 'pyvenv.cfg'),
             '.venv-cv-batch02/bin/python': sha(env / 'bin/python')}
    for name in ('cpu-import-check.json', 'official-source-parity.json', 'checkpoint-verification.json'):
        path = local / name
        files[str(path.relative_to(ROOT))] = sha(path)
    installed_files = {}
    # Pin installed code and native libraries, not merely the package version labels.
    for dist in importlib.metadata.distributions():
        for relative in dist.files or []:
            path = Path(dist.locate_file(relative)).resolve()
            if path.is_file() and path.is_relative_to(env) and '__pycache__' not in path.parts and path.suffix != '.pyc':
                installed_files[str(path.relative_to(ROOT))] = sha(path)
    file_index = local / 'environment-files.local.json'
    file_index.write_text(json.dumps(installed_files, indent=2, sort_keys=True)+'\n')
    files[str(file_index.relative_to(ROOT))] = sha(file_index)
    binding = json.loads((local / 'frame-binding.json').read_text())
    checkpoint = json.loads((local / 'checkpoint-verification.json').read_text())
    d = dict(schema_version=1, batch='BATCH-0002', experiment='EXP-0019',
        model=dict(name='RF-DETR Medium', release='1.11.2',
            tag_commit='7433d5919d0f7e72cc6cb78663e0a731afd499e0',
            url='https://storage.googleapis.com/rfdetr/medium_coco/checkpoint_best_regular.pth',
            license='Apache-2.0', **checkpoint), settings=SETTINGS,
        frames=binding['frames'], historical_pins=binding['historical_pins'],
        environment=dict(packages=inventory, files=files, file_index=str(file_index.relative_to(ROOT))),
        native_review_gate='prior user03084 approaching3 and03090 climbing3; exact native PTS bound; no bbox GT',
        sampled_vlm_input_gate='separate human review record; no CV output establishes sampled-input sufficiency',
        excluded='v native pose exact-frame unreviewed; no automatic FCOS rerun; no tracker/ROI/event/PoC changes')
    (ROOT / 'configs/batch0002_cv_manifest.json').write_text(json.dumps(d, indent=2, sort_keys=True)+'\n')
    print('Frozen packages', len(inventory), 'environment files', len(installed_files), 'native frames', len(d['frames']))


if __name__ == '__main__':
    freeze()
