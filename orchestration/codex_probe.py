"""Read the installed, authenticated Codex catalog using its stdio protocol.

No credentials are opened, no model invocation or account change is made here.
Catalog visibility alone is not invocation verification.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import selectors
import subprocess
import time


def probe(output: Path, workspaces=()):
    output.mkdir(parents=True, exist_ok=True)
    with (output / "catalog-stderr.log").open("w", encoding="utf-8") as stderr:
        proc = subprocess.Popen(["codex", "app-server", "--stdio"], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=stderr, text=True, encoding="utf-8", bufsize=1)
        def rpc(number, method, params):
            proc.stdin.write(json.dumps({"id": number, "method": method, "params": params}) + "\n")
            proc.stdin.flush()
            deadline = time.monotonic() + 40
            with selectors.DefaultSelector() as selector:
                selector.register(proc.stdout, selectors.EVENT_READ)
                while time.monotonic() < deadline:
                    if not selector.select(1):
                        continue
                    line = proc.stdout.readline()
                    if not line:
                        raise RuntimeError("Codex app-server exited before response")
                    response = json.loads(line)
                    if response.get("id") == number:
                        if "error" in response:
                            raise RuntimeError(response["error"])
                        return response["result"]
            raise TimeoutError(method)
        try:
            rpc(1, "initialize", {"clientInfo": {"name": "sceneguard_setup", "version": "1"},
                                  "capabilities": {"experimentalApi": True}})
            proc.stdin.write('{"method":"initialized"}\n'); proc.stdin.flush()
            models = []; cursor = None; request = 2
            while True:
                result = rpc(request, "model/list", {"limit": 100, "includeHidden": True, "cursor": cursor})
                models.extend({k: m.get(k) for k in ("id", "model", "displayName", "hidden",
                              "supportedReasoningEfforts", "defaultReasoningEffort")} for m in result["data"])
                cursor = result.get("nextCursor"); request += 1
                if cursor is None:
                    break
            current = None
            if os.environ.get("CODEX_THREAD_ID"):
                thread = rpc(request, "thread/read", {"threadId": os.environ["CODEX_THREAD_ID"], "includeTurns": False})["thread"]
                current = {k: thread.get(k) for k in ("model", "reasoningEffort", "modelProvider", "cliVersion", "originator")}
                request += 1
            sessions = []
            for workspace in workspaces:
                result = rpc(request, "thread/list", {"cwd": str(Path(workspace).resolve()), "limit": 10})
                request += 1
                for thread in result["data"]:
                    sessions.append({k: thread.get(k) for k in ("id", "cwd", "model", "reasoningEffort",
                                     "modelProvider", "cliVersion", "createdAt", "updatedAt")})
            evidence = {"checked_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                        "method": "installed schema model/list and metadata-only thread/read",
                        "models": models, "current_session": current,
                        "workspace_sessions": sessions,
                        "catalog_is_invocation_proof": False}
            (output / "codex-capabilities.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
            return evidence
        finally:
            proc.terminate()
            try:
                proc.wait(10)
            except subprocess.TimeoutExpired:
                proc.kill(); proc.wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--workspace", action="append", default=[])
    args = parser.parse_args()
    result = probe(args.output, args.workspace)
    print(json.dumps({"current_session": result["current_session"], "models": [m["id"] for m in result["models"]],
                      "workspace_sessions": result["workspace_sessions"]}))
