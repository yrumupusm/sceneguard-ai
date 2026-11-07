"""CPU-only preparation of explicit model specs and the nonfused InternVideo import compatibility copy."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'runtime/model-comparison/exp0066'
ENV_CODE='''import importlib.metadata as m,importlib.util,json,sys
names=('torch','torchvision','numpy','av','cv2','timm','einops','transformers','safetensors')
print(json.dumps({'python':sys.version,'packages':sorted((d.metadata['Name'].lower(),d.version) for d in m.distributions()),'imports':{n:(importlib.util.find_spec(n).origin if importlib.util.find_spec(n) else None) for n in names}},sort_keys=True))'''


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def snapshot_environment(interpreter):
    return json.loads(subprocess.check_output([str(interpreter),'-I','-c',ENV_CODE],text=True))


def internvideo_compat(source,dest):
    """Change optional dependency imports only; official nonfused numerical branches stay intact."""
    dest.mkdir(parents=True,exist_ok=False)
    for p in source.glob('*.py'):shutil.copyfile(p,dest/p.name)
    (dest/'__init__.py').write_text('')
    p=dest/'modeling_internvideo_next.py';original=p.read_text();text=original
    replacements={
        'from flash_attn.flash_attn_interface import flash_attn_varlen_qkvpacked_func\nfrom flash_attn.bert_padding import unpad_input, pad_input':
        'try:\n    from flash_attn.flash_attn_interface import flash_attn_varlen_qkvpacked_func\n    from flash_attn.bert_padding import unpad_input, pad_input\nexcept ImportError:\n    flash_attn_varlen_qkvpacked_func = unpad_input = pad_input = None',
        'from flash_attn.modules.mlp import FusedMLP\nfrom flash_attn.ops.rms_norm import DropoutAddRMSNorm':
        'try:\n    from flash_attn.modules.mlp import FusedMLP\n    from flash_attn.ops.rms_norm import DropoutAddRMSNorm\nexcept ImportError:\n    FusedMLP = DropoutAddRMSNorm = None'}
    for old,new in replacements.items():
        if text.count(old)!=1:raise ValueError('Official import layout differs; adaptation refused')
        text=text.replace(old,new)
    p.write_text(text)
    receipt=dict(source_file=str(source/p.name),source_sha256=hashlib.sha256(original.encode()).hexdigest(),
                 adapted_file=str(p),adapted_sha256=sha(p),
                 change='guard_optional_flash_imports_only; explicitly select existing nonfused model branches',
                 numerical_branch_modified=False,weights_modified=False)
    (dest/'compatibility.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


def prepare():
    source=RUNTIME/'encoders/encoder-source-contract-v2.json';contract=json.loads(source.read_text())
    out=RUNTIME/'model-specs-v1';out.mkdir(exist_ok=False)
    compat=RUNTIME/'internvideo-nonfused-v1'
    internvideo_compat(RUNTIME/'encoders/vendor/internvideo-next-hf',compat)
    for m in contract['models']:
        model_id=m['id'];r3d=model_id=='r3d18_exp0064'
        checkpoint=Path(m['checkpoint']['path']);checkpoint=checkpoint if checkpoint.is_absolute() else ROOT/checkpoint
        spec=dict(model_id=model_id,checkpoint_path=str(checkpoint),resolution=m['resolution'],
                  source_contract=dict(path=str(source),sha256=sha(source)),
                  bindings={str(checkpoint):sha(checkpoint),str(source):sha(source)},
                  temporal_condition='16 samples at4/30seconds centerindex8; actual repeated/nativePTS explicit')
        if spec['bindings'][str(checkpoint)]!=m['checkpoint']['sha256']:raise ValueError('Official checkpoint changed')
        if not r3d:
            vendor=compat if model_id=='internvideo_next_s2_l' else RUNTIME/'encoders'/m['vendor']
            spec.update(vendor_path=str(vendor),constructor_kwargs=m['kwargs'],state_prefix=m['state_prefix'],state_container=m['state_container'])
            if model_id=='internvideo_next_s2_l':
                spec['constructor_kwargs'].update(use_flash_attn=False,use_fused_mlp=False,use_fused_rmsnorm=False)
                spec['compatibility']='explicit official nonfused branches; optional imports guarded; no numerical branch edits'
                spec['bindings'][str(vendor/'compatibility.json')]=sha(vendor/'compatibility.json')
            spec['bindings'].update({str(p):sha(p) for p in vendor.rglob('*.py') if '.git' not in p.parts})
        interpreter=ROOT/('.venv-cv-batch02' if r3d else '.venv-exp0066-encoders')/'bin/python'
        environment=out/(model_id+'-environment.json')
        environment.write_text(json.dumps(snapshot_environment(interpreter),sort_keys=True,indent=2)+'\n')
        spec['environment_path']=str(environment);spec['bindings'][str(environment)]=sha(environment)
        (out/(model_id+'.json')).write_text(json.dumps(spec,sort_keys=True,indent=2)+'\n')
    print(out)


if __name__=='__main__':prepare()
