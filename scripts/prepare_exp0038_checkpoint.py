"""Download only the approved immutable EXP-0038 checkpoint; no model load."""
from pathlib import Path
import hashlib
import json
import time

from huggingface_hub import HfApi, snapshot_download

ROOT = Path(__file__).resolve().parents[1]
MODEL = 'Qwen/Qwen3-VL-8B-Instruct'
REVISION = '0c351dd01ed87e9c1b53cbc748cba10e6187ff3b'


def digest(path, algorithm='sha256', git_blob=False):
    h = hashlib.new(algorithm)
    if git_blob:
        h.update(f'blob {path.stat().st_size}\0'.encode())
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    runtime = ROOT / 'runtime/EXP-0038'
    runtime.mkdir(parents=True, exist_ok=True)
    destination = ROOT / 'weights/Qwen3-VL-8B-Instruct'
    start = time.perf_counter()
    info = HfApi().model_info(MODEL, revision=REVISION, files_metadata=True)
    if info.sha != REVISION or info.id != MODEL:
        raise ValueError('Official revision differs')
    rows = [vars(row) for row in info.siblings if row.rfilename != '.gitattributes']
    metadata = dict(model_id=MODEL, revision=info.sha,
                    license=info.card_data.to_dict().get('license'), files=rows)
    (runtime / 'download-official-metadata.json').write_text(
        json.dumps(metadata, default=vars, indent=2) + '\n')
    fetched = time.perf_counter()
    snapshot_download(MODEL, revision=REVISION, local_dir=destination,
                      allow_patterns=[row['rfilename'] for row in rows], max_workers=2)
    downloaded = time.perf_counter()
    records = {}
    for row in rows:
        path = destination / row['rfilename']
        if path.is_symlink() or path.stat().st_size != row['size']:
            raise ValueError('Expected exact materialized file: ' + row['rfilename'])
        sha = digest(path)
        if row['lfs']:
            if sha != row['lfs'].sha256:
                raise ValueError('Official LFS SHA mismatch')
        elif digest(path, 'sha1', git_blob=True) != row['blob_id']:
            raise ValueError('Official Git blob mismatch')
        records[row['rfilename']] = dict(bytes=path.stat().st_size, sha256=sha)
    receipt = dict(model_id=MODEL, revision=REVISION, files=records)
    (runtime / 'checkpoint.json').write_text(json.dumps(receipt, indent=2) + '\n')
    timing = dict(metadata_seconds=fetched-start, download_seconds=downloaded-fetched,
                  official_verification_seconds=time.perf_counter()-downloaded,
                  bytes=sum(x['bytes'] for x in records.values()), files=len(records),
                  official_hashes_verified=True, model_loads=0, gpu_inference=0)
    (runtime / 'checkpoint-preparation.json').write_text(json.dumps(timing, indent=2) + '\n')
    print(json.dumps(timing))


if __name__ == '__main__':
    main()
