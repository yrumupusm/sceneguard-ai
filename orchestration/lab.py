"""Start/stop only this lab's read-only server and Orca projection reader."""
from __future__ import annotations
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.request


def identity(pid):
    try:
        stat = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        if stat[0] == "Z":
            return None
        return {"pid": pid, "start_ticks": stat[19],
                "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip()}
    except (FileNotFoundError, ProcessLookupError):
        return None


def matches(saved):
    return saved is not None and identity(saved["pid"]) == saved


def run(config_path: Path, action: str):
    config_path = config_path.resolve(strict=True)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    root, runtime = Path(config["repo_root"]), Path(config["runtime_dir"])
    runtime.mkdir(parents=True, exist_ok=True)
    state_file = runtime / "services.json"
    url = f"http://127.0.0.1:{int(config.get('port', 8765))}"
    with (runtime / "services.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = json.loads(state_file.read_text()) if state_file.exists() else {}
        def save():
            temp = state_file.with_suffix(".tmp")
            temp.write_text(json.dumps(state, indent=2), encoding="utf-8"); temp.replace(state_file)
        if action == "status":
            return {"url": url, "services": {k: {"identity_matches": matches(v), "pid": v["pid"]} for k, v in state.items()}}
        if action == "stop":
            for name, saved in list(state.items()):
                if matches(saved):
                    # Bind the signal to this exact Linux process, not a reused PID.
                    descriptor = os.pidfd_open(saved["pid"])
                    try:
                        if not matches(saved):
                            raise RuntimeError(f"{name}: identity changed before signal")
                        signal.pidfd_send_signal(descriptor, signal.SIGTERM)
                    finally:
                        os.close(descriptor)
                    deadline = time.monotonic() + 12
                    while matches(saved) and time.monotonic() < deadline:
                        time.sleep(.1)
                    if matches(saved):
                        raise RuntimeError(f"{name} still alive; preserved state, no unrelated process killed")
                elif identity(saved["pid"]) is not None:
                    raise RuntimeError(f"{name}: PID identity changed; refusing signal")
                state.pop(name); save()
            return {"stopped": True, "note": "GPU queue and Orca agents are independent; not stopped"}
        if any(matches(v) for v in state.values()):
            raise RuntimeError("A lab service is already live; use status/stop, never duplicate it")
        with socket.socket() as sock:
            # A stopped server may leave TIME_WAIT connections. This still
            # rejects an active listener; it does not enable SO_REUSEPORT.
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", int(config.get("port", 8765))))
        env = os.environ.copy(); env["SCENEGUARD_LAB_CONFIG"] = str(config_path)
        argv = {
            "web": [sys.executable, "-m", "uvicorn", "webapp.app:app", "--host", "127.0.0.1",
                    "--port", str(config.get("port", 8765)), "--no-access-log"],
            "projection": [sys.executable, "-m", "orchestration.orca_adapter", "--cli", config.get("orca_cli", "orca-ide"),
                           "--run", config["orca_run_id"], "--output", str(runtime / "orca_projection.json"), "--watch"],
        }
        for name, command in argv.items():
            with (runtime / f"{name}.log").open("ab") as log:
                proc = subprocess.Popen(command, cwd=root, env=env, stdout=log, stderr=log,
                                        stdin=subprocess.DEVNULL, start_new_session=True)
            state[name] = identity(proc.pid)
            if state[name] is None:
                raise RuntimeError(f"{name} exited immediately; see local log")
            save()
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if not matches(state["web"]):
                raise RuntimeError("Web startup failed; inspect log and run stop to clean up projection")
            try:
                with urllib.request.urlopen(url + "/api/catalog", timeout=1) as response:
                    if response.status == 200:
                        return {"url": url, "started": list(state), "bind": "loopback only"}
            except OSError:
                time.sleep(.2)
        raise RuntimeError("Web readiness timed out; inspect local logs; no second instance started")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("action", choices=["start", "stop", "status"])
    a = p.parse_args()
    print(json.dumps(run(a.config, a.action), ensure_ascii=False, indent=2))
