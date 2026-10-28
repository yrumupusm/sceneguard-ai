"""Download only BATCH-0001's selected, pinned Smol model and verify provenance.

No model construction, inference, credential use, or media access occurs here.
The provenance JSON is a local artifact, not a publication-ready result.
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import struct

from huggingface_hub import HfApi, snapshot_download

MODEL = "HuggingFaceTB/SmolVLM2-2.2B-Instruct"
REVISION = "482adb537c021c86670beed01cd58990d01e72e4"
WEIGHTS = {
    "model-00001-of-00002.safetensors": (
        4959390584, "7c88a90e78f567460b2369a0369cc4dafbfda5607c9cb090b30fa4437b0282f2"),
    "model-00002-of-00002.safetensors": (
        4027833472, "cf3d0958a8240f71054a6812038f2a6bfbe2e5124573a3b363f6b120c9a52657"),
}
SUPPORT_FILES = (
    "README.md", "added_tokens.json", "chat_template.json", "config.json",
    "generation_config.json", "merges.txt", "model.safetensors.index.json",
    "preprocessor_config.json", "processor_config.json", "special_tokens_map.json",
    "tokenizer.json", "tokenizer_config.json", "vocab.json",
)


def hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def header_summary(path):
    """Inspect safetensors headers only; never materialize or load tensors."""
    with path.open("rb") as stream:
        header_size = struct.unpack("<Q", stream.read(8))[0]
        if header_size > 32 * 1024 * 1024:
            raise ValueError("unexpectedly large safetensors header")
        header = json.loads(stream.read(header_size))
    tensors = [value for key, value in header.items() if key != "__metadata__"]
    return {"storage_dtypes": sorted({value["dtype"] for value in tensors}),
            "tensor_count": len(tensors),
            "parameter_count": sum(math.prod(value["shape"]) for value in tensors)}


def download(model_dir, provenance_path):
    if model_dir.name != "SmolVLM2-2.2B-Instruct" or model_dir.is_symlink():
        raise ValueError("expected a regular selected-model directory")
    info = HfApi(token=False).model_info(MODEL, revision=REVISION, files_metadata=True)
    if info.sha != REVISION or info.card_data.get("license") != "apache-2.0":
        raise ValueError("official revision or license differs from frozen contract")
    if info.card_data.get("language") != ["en"]:
        raise ValueError("official language differs from frozen contract")
    official = {item.rfilename: item for item in info.siblings}
    for name, (size, digest) in WEIGHTS.items():
        item = official[name]
        if (item.size, item.lfs.size, item.lfs.sha256) != (size, size, digest):
            raise ValueError("official shard metadata differs from frozen contract")
    selected = list(SUPPORT_FILES) + list(WEIGHTS)
    if not all(name in official for name in selected):
        raise ValueError("missing official processor or tokenizer file")
    provenance_path.parent.mkdir(parents=True, exist_ok=True)
    provenance = {
        "model": MODEL, "revision": REVISION, "license": "apache-2.0",
        "language": ["en"], "source": f"https://huggingface.co/{MODEL}/tree/{REVISION}",
        "metadata_url": f"https://huggingface.co/api/models/{MODEL}/revision/{REVISION}?blobs=true",
        "metadata_verified_at": datetime.now(timezone.utc).isoformat(),
        "official_files": {name: {"bytes": official[name].size,
                                   "lfs": asdict(official[name].lfs) if official[name].lfs else None}
                           for name in selected},
        "verification": "metadata_verified_download_not_completed", "files": {},
    }
    provenance_path.write_text(json.dumps(provenance, indent=2) + "\n")
    snapshot_download(MODEL, revision=REVISION, local_dir=model_dir, token=False,
                      allow_patterns=selected, max_workers=2)
    for name in selected:
        path = model_dir / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("downloaded file must be a regular file")
        size, digest = path.stat().st_size, hash_file(path)
        if size != official[name].size or (name in WEIGHTS and (size, digest) != WEIGHTS[name]):
            raise ValueError("downloaded size or shard SHA256 mismatch")
        provenance["files"][name] = {"bytes": size, "sha256": digest}
        if name in WEIGHTS:
            provenance["files"][name].update(header_summary(path))
    index = json.loads((model_dir / "model.safetensors.index.json").read_text())
    if set(index["weight_map"].values()) != set(WEIGHTS):
        raise ValueError("weight index references an unexpected shard")
    provenance["verification"] = "official_metadata_and_all_local_hashes_verified"
    provenance["verified_at"] = datetime.now(timezone.utc).isoformat()
    provenance_path.write_text(json.dumps(provenance, indent=2) + "\n")
    return provenance


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    args = parser.parse_args()
    result = download(args.model_dir, args.provenance)
    print(json.dumps({"model": MODEL, "revision": REVISION,
                      "verification": result["verification"], "files": len(result["files"])}))
