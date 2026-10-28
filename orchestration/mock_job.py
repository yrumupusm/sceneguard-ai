"""Registered CPU-only sleep job. No media, model, network, or GPU access."""

import argparse
import json
import os
from pathlib import Path
import time


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", required=True, type=float)
    parser.add_argument("--exit-code", required=True, type=int)
    parser.add_argument("--result", required=True)
    parser.add_argument("--lock-fd", required=True, type=int)
    args = parser.parse_args()
    # Keep the inherited flock open until process exit, even if supervisor dies.
    os.fstat(args.lock_fd)
    started = time.time()
    atomic_json(Path(args.result).with_name("mock-start.json"), {
        "pid": os.getpid(), "started_at": started, "synthetic": True,
    })
    time.sleep(args.seconds)
    atomic_json(args.result, {
        "schema_version": 1, "synthetic": True, "workload": "cpu-sleep",
        "pid": os.getpid(), "started_at": started, "finished_at": time.time(),
        "requested_exit_code": args.exit_code, "gpu_measurements": None,
    })
    return args.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
