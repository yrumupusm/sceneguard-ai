"""CPU-only integration tests. Timing intervals are synthetic, never GPU metrics."""

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from orchestration.queue import Queue, ROOT, digest, process_identity, process_state


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="sceneguard-queue-")
        self.addCleanup(self.temporary.cleanup)
        self.queue = Queue.initialize(self.temporary.name)
        self.workers = []
        self.addCleanup(self.cleanup_workers)

    def cleanup_workers(self):
        # Tests only wait for their own bounded mock jobs, never unrelated PIDs.
        for process in self.workers:
            try:
                process.communicate(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=2)
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            with self.queue.gpu_lock(blocking=False) as lock:
                if lock is not None:
                    return
            time.sleep(0.02)
        self.fail("test mock still owns reservation during cleanup")

    def enqueue(self, key="job", seconds=0.1, exit_code=0, timeout=5, **kwargs):
        return self.queue.enqueue(job_key=key, run_id="test-run", task_id="test-task",
                                  dispatch_id="test-dispatch", owner="test-owner",
                                  config={"seconds": seconds, "exit_code": exit_code},
                                  timeout=timeout, **kwargs)

    def worker(self):
        process = subprocess.Popen([sys.executable, "-m", "orchestration.queue",
                                    "--runtime", str(self.queue.runtime), "run-once"],
                                   cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True)
        self.workers.append(process)
        return process

    def wait_until(self, predicate, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = predicate()
            if result:
                return result
            time.sleep(0.01)
        self.fail("condition not reached within test deadline")

    def started(self, job_id):
        for attempt in self.queue.status()["attempts"]:
            if attempt["job_id"] == job_id and attempt["child_pid"]:
                marker = self.queue.runtime / "attempts" / attempt["attempt_id"] / "mock-start.json"
                if marker.exists():
                    return attempt
        return None

    def wait_worker(self, process):
        stdout, stderr = process.communicate(timeout=8)
        self.assertEqual(process.returncode, 0, stderr)
        self.assertEqual(json.loads(stdout)["supervisor_exit_code"], 0, stderr)

    def result(self, attempt):
        return json.loads((self.queue.runtime / "attempts" / attempt["attempt_id"] /
                           "mock-result.json").read_text())

    def test_two_concurrent_workers_serialize_intervals(self):
        self.enqueue("a", seconds=0.25)
        self.enqueue("b", seconds=0.25)
        workers = [self.worker(), self.worker()]
        for worker in workers:
            self.wait_worker(worker)
        status = self.queue.status()
        self.assertEqual([j["status"] for j in status["jobs"]], ["succeeded", "succeeded"])
        self.assertEqual(len(status["attempts"]), 2)
        first, second = map(self.result, status["attempts"])
        self.assertLessEqual(first["finished_at"], second["started_at"])
        self.assertIsNone(first["gpu_measurements"])

    def test_failure_releases_and_next_runs(self):
        self.enqueue("failure", exit_code=7)
        self.enqueue("next")
        self.wait_worker(self.worker())
        self.wait_worker(self.worker())
        attempts = self.queue.status()["attempts"]
        self.assertEqual([a["status"] for a in attempts], ["failed", "succeeded"])
        self.assertEqual([a["exit_code"] for a in attempts], [7, 0])
        self.assertTrue(all(Path(a["result_manifest"]).is_file() for a in attempts))

    def test_restart_and_duplicate_enqueue_never_repeat_completed_job(self):
        original = self.enqueue()
        self.assertEqual(self.enqueue()["job_id"], original["job_id"])
        self.wait_worker(self.worker())
        restarted = Queue(self.queue.runtime)
        self.assertEqual(restarted.recover()["status"], "checked")
        self.wait_worker(self.worker())
        self.assertEqual(len(restarted.status()["attempts"]), 1)
        with self.assertRaises(ValueError):
            restarted.retry(original["job_id"])

    def test_concurrent_enqueue_has_unique_job_key(self):
        argv = [sys.executable, "-m", "orchestration.queue", "--runtime", str(self.queue.runtime),
                "enqueue", "--job-key", "same", "--run-id", "r", "--task-id", "t",
                "--dispatch-id", "d", "--owner", "o"]
        processes = [subprocess.Popen(argv, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE) for _ in range(2)]
        self.workers.extend(processes)
        ids = []
        for process in processes:
            out, err = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 0, err)
            ids.append(json.loads(out)["job_id"])
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(len(self.queue.status()["jobs"]), 1)

    def test_worker_death_keeps_supervisor_and_lock(self):
        first = self.enqueue("orphan", seconds=0.8)
        self.enqueue("next", seconds=0.1)
        worker = self.worker()
        attempt = self.wait_until(lambda: self.started(first["job_id"]))
        worker.kill()
        worker.communicate(timeout=2)
        self.assertEqual(process_state(attempt["supervisor_pid"], attempt["supervisor_identity"]), "live")
        self.assertEqual(self.queue.recover()["status"], "busy")
        self.wait_worker(self.worker())
        attempts = self.queue.status()["attempts"]
        self.assertEqual(len(attempts), 2)
        self.assertEqual([a["status"] for a in attempts], ["succeeded", "succeeded"])
        self.assertLessEqual(self.result(attempts[0])["finished_at"], self.result(attempts[1])["started_at"])

    def test_supervisor_death_child_inherits_lock_and_no_silent_retry(self):
        first = self.enqueue("orphan-child", seconds=0.6)
        self.enqueue("next")
        worker = self.worker()
        attempt = self.wait_until(lambda: self.started(first["job_id"]))
        fd = os.pidfd_open(attempt["supervisor_pid"])
        try:
            self.assertEqual(process_state(attempt["supervisor_pid"], attempt["supervisor_identity"]), "live")
            signal.pidfd_send_signal(fd, signal.SIGKILL)
        finally:
            os.close(fd)
        worker.communicate(timeout=2)
        self.assertEqual(self.queue.recover()["status"], "busy")
        with self.queue.gpu_lock(blocking=False) as lock:
            self.assertIsNone(lock)
        self.wait_worker(self.worker())
        attempts = self.queue.status()["attempts"]
        self.assertEqual([a["status"] for a in attempts], ["interrupted", "succeeded"])
        self.assertIsNone(attempts[0]["exit_code"])
        self.assertLessEqual(self.result(attempts[0])["finished_at"], self.result(attempts[1])["started_at"])
        self.assertEqual(sum(a["job_id"] == first["job_id"] for a in attempts), 1)

    def test_timeout_kills_only_registered_child_and_releases(self):
        self.enqueue("timeout", seconds=2, timeout=0.1)
        self.enqueue("next")
        self.wait_worker(self.worker())
        self.wait_worker(self.worker())
        first, second = self.queue.status()["attempts"]
        self.assertEqual((first["status"], first["reason"], first["exit_code"]), ("failed", "timeout", -9))
        self.assertEqual(process_state(first["child_pid"], first["child_identity"]), "exited")
        self.assertEqual(second["status"], "succeeded")

    def test_cancel_running_and_queued(self):
        job = self.enqueue("cancel-running", seconds=2)
        queued = self.enqueue("cancel-queued")
        self.queue.cancel(queued["job_id"])
        worker = self.worker()
        self.wait_until(lambda: self.started(job["job_id"]))
        self.queue.cancel(job["job_id"])
        self.wait_worker(worker)
        self.assertEqual([j["status"] for j in self.queue.status()["jobs"]], ["cancelled", "cancelled"])
        self.assertEqual(len(self.queue.status()["attempts"]), 1)
        self.assertEqual(self.queue.status()["attempts"][0]["reason"], "explicit cancellation")

    def test_single_explicit_retry_with_immutable_attempt_history(self):
        job = self.enqueue(exit_code=4)
        self.wait_worker(self.worker())
        self.wait_worker(self.worker())
        self.assertEqual(len(self.queue.status()["attempts"]), 1)
        self.queue.retry(job["job_id"])
        self.wait_worker(self.worker())
        attempts = self.queue.status()["attempts"]
        self.assertEqual([a["attempt_no"] for a in attempts], [1, 2])
        self.assertNotEqual(attempts[0]["attempt_id"], attempts[1]["attempt_id"])
        with self.assertRaises(ValueError):
            self.queue.retry(job["job_id"])

    def test_pid_reuse_unknown_is_not_killed_or_retried_and_blocks_claim(self):
        job = self.enqueue("uncertain")
        self.wait_worker(self.worker())
        self.enqueue("next")
        with self.queue.connection() as db:
            db.execute("UPDATE jobs SET status='running' WHERE job_id=?", (job["job_id"],))
            db.execute("UPDATE attempts SET status='running',supervisor_pid=?,"
                       "supervisor_identity='wrong-incarnation',child_pid=NULL,child_identity=NULL",
                       (os.getpid(),))
        with mock.patch("os.kill") as kill, mock.patch("signal.pidfd_send_signal") as send:
            outcome = self.queue.recover()
            self.assertEqual(outcome["attempts"][0]["status"], "unknown")
            kill.assert_not_called()
            send.assert_not_called()
        with self.assertRaises(ValueError):
            self.queue.retry(job["job_id"])
        self.wait_worker(self.worker())
        self.assertEqual(len(self.queue.status()["attempts"]), 1)
        self.assertEqual(self.queue.status()["jobs"][1]["status"], "queued")
        self.assertEqual(process_state(os.getpid(), process_identity(os.getpid())), "live")

    def test_unreadable_process_identity_is_unknown(self):
        with mock.patch("orchestration.queue.process_identity", side_effect=PermissionError):
            self.assertEqual(process_state(123, "identity"), "unknown")
        self.assertEqual(process_state(None, None), "unknown")

    def test_shared_canonical_path_and_cli_required_runtime(self):
        alias = self.queue.runtime / "runtime-alias"
        alias.symlink_to(self.queue.runtime, target_is_directory=True)
        self.assertEqual(Queue(alias).runtime, self.queue.runtime)
        with self.assertRaises(ValueError):
            Queue("relative/path")
        result = subprocess.run([sys.executable, "-m", "orchestration.queue", "status"],
                                cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("--runtime", result.stderr)

    def test_registration_contract_and_expected_hash_validation(self):
        with self.assertRaises(ValueError):
            self.enqueue(command="sh")
        with self.assertRaises(ValueError):
            self.enqueue(expected_input_hash="incorrect")
        with self.assertRaises(ValueError):
            self.enqueue(seconds=float("nan"))
        original = self.enqueue(expected_config_hash=digest({"seconds": 0.1, "exit_code": 0}))
        with self.assertRaises(ValueError):
            self.enqueue(seconds=0.2)
        self.assertEqual(len(original["input_hash"]), 64)
        self.assertEqual(len(original["code_sha"]), 40)

    def test_hash_tamper_fails_without_starting_child(self):
        self.enqueue()
        with self.queue.connection() as db:
            db.execute("UPDATE jobs SET config_json=?", ('{"seconds":1,"exit_code":0}',))
        self.wait_worker(self.worker())
        attempt = self.queue.status()["attempts"][0]
        self.assertEqual(attempt["status"], "failed")
        self.assertIsNone(attempt["child_pid"])
        self.assertIn("hash mismatch", attempt["reason"])


if __name__ == "__main__":
    unittest.main()
