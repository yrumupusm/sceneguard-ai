"""CPU-only immutable specs for the YOLO26 pretrained baseline. No model import or GPU access."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.prepare_model_comparison import sha, snapshot_environment
from scripts.exp0066_yolo import WEIGHTS, PREDICT, validate_spec


def prepare(output):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    interpreter = ROOT/'.venv-pose-batch03/bin/python'
    vendor = Path(subprocess.check_output([str(interpreter),'-I','-c',
        'import importlib.util; print(importlib.util.find_spec("ultralytics").origin)'], text=True).strip()).parent
    env = output/'environment.json'
    env.write_text(json.dumps(snapshot_environment(interpreter), sort_keys=True, indent=2)+'\n')
    dependencies = {str(p):sha(p) for p in sorted(vendor.rglob('*'))
                    if p.is_file() and p.suffix in ('.py','.yaml','.yml','.json')}
    dependencies[str(env)] = sha(env)
    specs = {}
    for model_id, expected in WEIGHTS.items():
        checkpoint = (ROOT/'weights/yolo26m.pt' if model_id == 'yolo26m' else
                      ROOT/'runtime/model-comparison/exp0066/yolo26-preparation-v1'/(model_id+'.pt'))
        if sha(checkpoint) != expected:
            raise ValueError('Pinned official checkpoint differs: '+model_id)
        spec = dict(model_id=model_id, checkpoint_path=str(checkpoint), vendor_path=str(vendor),
            environment_path=str(env), bindings={**dependencies,str(checkpoint):expected},
            ultralytics_version='8.4.192', resolution=640, predict_kwargs=PREDICT,
            input_frame_index=8, report_person_threshold=.5,
            temporal_condition='Single actual native frame at slot8 of unchanged cohort windows; not16-frame inference',
            runtime_settings_directory=str(output/'offline-settings'/model_id))
        validate_spec(spec)
        path=output/(model_id+'.json')
        path.write_text(json.dumps(spec, sort_keys=True, indent=2)+'\n')
        specs[model_id]=dict(path=str(path),sha256=sha(path))
    (output/'manifest.json').write_text(json.dumps(dict(specs=specs,new_inference=0),indent=2)+'\n')
    print(json.dumps(specs))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    prepare(parser.parse_args().output)
