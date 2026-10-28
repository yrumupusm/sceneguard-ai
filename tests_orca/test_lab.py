import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from orchestration.lab import identity, matches, run


class ServiceOwnership(unittest.TestCase):
    def test_identity_and_exit(self):
        process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(5)"])
        try:
            saved = identity(process.pid)
            self.assertTrue(matches(saved))
            self.assertFalse(matches({**saved, "start_ticks": "invalid"}))
        finally:
            process.terminate(); process.wait(3)
        self.assertIsNone(identity(process.pid))

    def test_pid_reuse_never_signalled(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config.json"
            config.write_text(json.dumps({"repo_root": directory, "runtime_dir": directory}))
            saved = {"pid": os.getpid(), "start_ticks": "wrong", "boot_id": "wrong"}
            (root / "services.json").write_text(json.dumps({"web": saved}))
            with patch("signal.pidfd_send_signal") as send:
                with self.assertRaisesRegex(RuntimeError, "PID identity changed"):
                    run(config, "stop")
                send.assert_not_called()

    def test_occupied_port_refuses_start_without_spawning(self):
        with tempfile.TemporaryDirectory() as directory, socket.socket() as listener:
            listener.bind(("127.0.0.1", 0)); listener.listen()
            root = Path(directory); config = root / "config.json"
            config.write_text(json.dumps({"repo_root": directory, "runtime_dir": directory,
                                          "port": listener.getsockname()[1]}))
            with patch("subprocess.Popen") as spawn:
                with self.assertRaises(OSError):
                    run(config, "start")
                spawn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
