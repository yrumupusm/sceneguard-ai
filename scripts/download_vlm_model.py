"""Download only the pinned official model; verify the published weight hash."""
import hashlib,json
from pathlib import Path
from huggingface_hub import snapshot_download
MODEL='Qwen/Qwen3-VL-2B-Instruct'
REVISION='89644892e4d85e24eaac8bacfd4f463576704203'
WEIGHT_SHA='7de1838c87a5349b016c26a1c3f7d2bc400a3d485f95ef39a7059ffd734977a0'


def verify():
    root=Path('weights/Qwen3-VL-2B-Instruct')
    hashes={}
    for p in root.iterdir():
        if not p.is_file():continue
        h=hashlib.sha256()
        with p.open('rb') as f:
            for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
        hashes[p.name]=dict(bytes=p.stat().st_size,sha256=h.hexdigest())
    assert hashes['model.safetensors']['sha256']==WEIGHT_SHA
    dest=Path('outputs/vlm_exp0007');dest.mkdir(parents=True,exist_ok=True)
    (dest/'weight_provenance.json').write_text(json.dumps(dict(model=MODEL,revision=REVISION,files=hashes),indent=2))
    return hashes


if __name__=='__main__':
    snapshot_download(MODEL,revision=REVISION,local_dir='weights/Qwen3-VL-2B-Instruct',allow_patterns=['*.json','*.txt','*.safetensors','README.md'],max_workers=2)
    print(verify())
