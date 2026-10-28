"""Compare the local pre-setup inventory and package freezes without modification."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def verify(root, snapshot):
    before = json.loads(snapshot.read_text(encoding="utf-8"))
    errors = []
    for name in (".venv", ".venv-vlm"):
        actual = subprocess.check_output(["uv", "pip", "freeze", "--python", str(root / name / "bin/python")], text=True)
        if actual != before[name]:
            errors.append(name + ": package freeze changed")
    for rel, expected in before["files"].items():
        path = root / rel
        if not path.is_file():
            errors.append(rel + ": missing"); continue
        stat = path.stat()
        if stat.st_size != expected["size"] or stat.st_mtime_ns != expected["mtime_ns"]:
            errors.append(rel + ": size/mtime changed")
        if "sha256" in expected and hashlib.sha256(path.read_bytes()).hexdigest() != expected["sha256"]:
            errors.append(rel + ": content changed")
    return {"passed": not errors, "inventoried_files": len(before["files"]),
            "hashed_files": sum("sha256" in item for item in before["files"].values()),
            "environment_freezes": 2, "errors": errors,
            "scope": "all inventoried files size/mtime; selected small metadata/code/report JSON SHA256; not full media hashing"}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--before", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args(); result = verify(args.source, args.before)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result)); raise SystemExit(0 if result["passed"] else 1)
