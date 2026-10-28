"""CPU-only acquisition of the sole approved official checkpoint; no model imports."""
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'ebb281ec70b05090aa6165b016eac8ec08e71b17'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8*1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    evidence = ROOT / 'runtime/BATCH-0002/vlm-readiness'
    api = json.loads((evidence / 'hf-model-api.json').read_text())
    if api['sha'] != REVISION or api['id'] != 'Qwen/Qwen3-VL-4B-Instruct':
        raise ValueError('official pinned API metadata differs')
    target = ROOT / 'weights/Qwen3-VL-4B-Instruct'
    target.mkdir(exist_ok=True, parents=True)
    records = {}
    for row in api['siblings']:
        name = row['rfilename']
        if name in ('.gitattributes', 'README.md'):
            continue
        path = target / name
        if not path.exists():
            cached = evidence / ('model-' + name)
            old = ROOT / 'weights/Qwen3-VL-2B-Instruct' / name
            part = path.with_suffix(path.suffix + '.partial')
            if part.exists():
                raise ValueError('partial download exists; preserve for explicit assessment')
            if cached.is_file():
                shutil.copyfile(cached, part)
            elif old.is_file() and hashlib.sha1(b'blob '+str(old.stat().st_size).encode()+b'\0'+old.read_bytes()).hexdigest() == row['blobId']:
                shutil.copyfile(old, part)
            else:
                url = f'https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct/resolve/{REVISION}/{name}'
                with urllib.request.urlopen(url, timeout=180) as source, part.open('xb') as out:
                    shutil.copyfileobj(source, out, 8*1024*1024)
            if part.stat().st_size != row['size']:
                raise ValueError('official size mismatch: ' + name)
            actual = sha(part)
            if 'lfs' in row:
                if actual != row['lfs']['sha256']:
                    raise ValueError('full official shard SHA differs: ' + name)
            elif hashlib.sha1(b'blob '+str(row['size']).encode()+b'\0'+part.read_bytes()).hexdigest() != row['blobId']:
                raise ValueError('official Git blob differs: ' + name)
            part.rename(path)
        actual = sha(path)
        if path.stat().st_size != row['size'] or ('lfs' in row and actual != row['lfs']['sha256']):
            raise ValueError('existing file differs: ' + name)
        if 'lfs' not in row and hashlib.sha1(b'blob '+str(row['size']).encode()+b'\0'+path.read_bytes()).hexdigest() != row['blobId']:
            raise ValueError('existing official Git blob differs: ' + name)
        records[name] = dict(bytes=path.stat().st_size, sha256=actual, official_git_blob=row['blobId'])
        print(name, actual, flush=True)
    (ROOT / 'runtime/BATCH-0002/vlm/model-download.json').write_text(json.dumps(dict(model_id=api['id'],revision=REVISION,files=records),indent=2)+'\n')


if __name__ == '__main__':
    main()
