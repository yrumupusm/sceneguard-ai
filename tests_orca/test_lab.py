import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
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

    def test_projection_exit_before_web_readiness_preserves_ownership(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); config = root / 'config.json'
            config.write_text(json.dumps({'repo_root': directory, 'runtime_dir': directory, 'port': 0, 'orca_run_id': 'fixture'}))
            def process_identity(pid):
                return {'pid': pid, 'start_ticks': 'fixture', 'boot_id': 'fixture'}
            with patch('orchestration.lab.subprocess.Popen', side_effect=[SimpleNamespace(pid=11), SimpleNamespace(pid=22)]), \
                 patch('orchestration.lab.identity', side_effect=process_identity), \
                 patch('orchestration.lab.matches', side_effect=lambda saved: saved['pid'] == 11), \
                 patch('orchestration.lab.urllib.request.urlopen') as http:
                with self.assertRaisesRegex(RuntimeError, 'Partial startup: projection exited'):
                    run(config, 'start')
                http.assert_not_called()
            self.assertEqual(set(json.loads((root / 'services.json').read_text())), {'web', 'projection'})

    def test_only_current_projection_receipt_can_report_degraded_start(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); config = root / 'config.json'
            config.write_text(json.dumps({'repo_root': directory, 'runtime_dir': directory, 'port': 0, 'orca_run_id': 'fixture'}))
            projection = root / 'orca_projection.json'
            projection.write_text(json.dumps({'launch_id': 'old-launch', 'connected': True}))
            calls = []
            def sleep(_):
                calls.append('waited for current receipt')
                projection.write_text(json.dumps({'launch_id': 'current-launch', 'connected': False}))
            with patch('orchestration.lab.subprocess.Popen', side_effect=[SimpleNamespace(pid=11), SimpleNamespace(pid=22)]), \
                 patch('orchestration.lab.identity', side_effect=lambda pid: {'pid': pid}), \
                 patch('orchestration.lab.matches', return_value=True), \
                 patch('orchestration.lab.uuid.uuid4', return_value=SimpleNamespace(hex='current-launch')), \
                 patch('orchestration.lab.time.sleep', side_effect=sleep), \
                 patch('orchestration.lab.urllib.request.urlopen') as http:
                http.return_value.__enter__.return_value.status = 200
                result = run(config, 'start')
            self.assertEqual(len(calls), 1)
            self.assertEqual(result['state'], 'degraded')
            self.assertEqual(result['projection_state'], 'disconnected')
            self.assertEqual(result['projection_launch_id'], 'current-launch')


if __name__ == "__main__":
    unittest.main()
