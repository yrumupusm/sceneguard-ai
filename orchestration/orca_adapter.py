"""Read-only Orca projection. Orca owns Task/Dispatch state; this is a cache.

Never writes to Orca, invokes a model, reads provider transcripts or polls by LLM.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import time


def snapshot(cli: str, run: str, output: Path):
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    workers = []
    cursor = None
    try:
        while True:
            argv = [cli, "orchestration", "worker-list", "--run", run, "--include-remote", "--json"]
            if cursor:
                argv += ["--cursor", cursor]
            result = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", timeout=25, check=True)
            data = json.loads(result.stdout)
            if not data.get("ok"):
                raise RuntimeError(data.get("error", {}).get("code", "Orca error"))
            body = data["result"]
            for row in body.get("workers", []):
                projection = row.get("projection", {})
                workers.append({"dispatch_id": projection.get("dispatchId", row.get("dispatchId")),
                                "task_id": projection.get("taskId", row.get("taskId")),
                                "stage": projection.get("stage"), "liveness": projection.get("liveness"),
                                "resource": projection.get("resource"), "outcome": projection.get("outcome")})
            if not body.get("page", {}).get("hasMore"):
                break
            cursor = body["page"]["nextCursor"]
        record = {"observed_at": now, "connected": True, "run_id": run, "workers": workers,
                  "authority": "Orca native Run/Task/Dispatch", "stale_after_seconds": 45}
    except (subprocess.SubprocessError, ValueError, OSError, RuntimeError) as error:
        record = {"observed_at": now, "connected": False, "run_id": run, "workers": [],
                  "error": type(error).__name__, "stale_after_seconds": 45,
                  "note": "contact loss is not worker exit; no lifecycle mutation performed"}
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    temp.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(output)
    return record


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cli", default=os.environ.get("ORCA_CLI_COMMAND", "orca-ide"))
    p.add_argument("--run", required=True)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--watch", action="store_true")
    a = p.parse_args()
    while True:
        snapshot(a.cli, a.run, a.output)
        if not a.watch:
            break
        time.sleep(15)
