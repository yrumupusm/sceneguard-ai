"""Create a local-only canonical viewer config; never copy experiment assets."""
import argparse
import json
import os
from pathlib import Path


def make_config(repo: Path, source: Path, runtime: Path, run_id: str, port=8765):
    repo = repo.resolve(strict=True); source = source.resolve(strict=True); runtime = runtime.resolve()
    if not (repo / "records/catalog.json").is_file():
        raise ValueError("Export historical records before initialization")
    if not (source / "outputs").is_dir():
        raise ValueError("Existing local outputs directory is required")
    config_file = runtime / "local_config.json"
    if config_file.exists():
        raise FileExistsError("Preserve existing config; inspect it instead of overwriting")
    artifacts = {}
    for experiment, directory, prefix, filename in [
        (5, "cv_phase2f", "", "raw_B_C_normal_then_quarter.mp4"),
        (6, "cv_phase2g", "video", "raw_C_review_normal_then_quarter.mp4"),
    ]:
        for video in ("007", "030"):
            artifacts[f"exp{experiment}-{video}"] = {
                "path": str(source / "outputs" / directory / (prefix + video) / filename), "kind": "video"}
    for i in range(1, 7):
        artifacts[f"exp7-clip{i:02d}"] = {
            "path": str(source / "outputs/vlm_exp0007/run02" / f"clip{i:02d}" / "actual_input_review.jpg"), "kind": "image"}
    runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
    config = {"repo_root": str(repo), "runtime_dir": str(runtime), "artifact_allow_root": str(source / "outputs"),
              "artifacts": artifacts, "port": port, "orca_run_id": run_id,
              "orca_cli": os.environ.get("ORCA_CLI_COMMAND", "orca-ide")}
    with config_file.open("x", encoding="utf-8") as stream:
        json.dump(config, stream, ensure_ascii=False, indent=2)
    config_file.chmod(0o600)
    return config_file


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, default=Path.cwd())
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--runtime", type=Path, required=True)
    p.add_argument("--run", required=True)
    p.add_argument("--port", type=int, default=8765)
    a = p.parse_args()
    print(make_config(a.repo, a.source, a.runtime, a.run, a.port))
