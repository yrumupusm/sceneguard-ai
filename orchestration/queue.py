"""Linux local allowlisted queue with a shared, inherited GPU reservation lock."""

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import sqlite3
import subprocess
import sys
import time
import uuid

from orchestration.mock_job import atomic_json


ROOT = Path(__file__).resolve().parent.parent
MOCK = Path(__file__).resolve().with_name("mock_job.py")
RETRYABLE = {"failed", "cancelled", "interrupted"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def source_hash(command="cpu-mock", config=None):
    if command == 'batch06-pose':
        from orchestration.batch06_pose_command import sources
        return digest(sources(config))
    if command == 'batch05-pose':
        from orchestration.batch05_pose_command import sources
        return digest(sources(config))
    if command == 'batch04-pose':
        from orchestration.batch04_pose_command import sources
        return digest(sources(config))
    if command == 'batch03-pose':
        from orchestration.batch03_pose_command import sources
        return digest(sources(config))
    if command == 'vlm-batch02':
        from orchestration.batch02_vlm_command import sources
        return digest(sources(config))
    if command == 'batch02-cv':
        from orchestration.batch02_cv_command import sources
        return digest(sources(config))
    if command == 'mvp-0001':
        from orchestration.mvp_command import sources
        return digest(sources(config))
    if command == 'vlm-batch01':
        from orchestration.vlm_command import sources
        return digest(sources(config['adapter']))
    return digest({p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in (Path(__file__), MOCK)})


def process_identity(pid):
    """Return boot ID + /proc start ticks; None means proven absent/zombie.

    Permission and parse errors deliberately propagate: absence is not assumed.
    """
    try:
        stat = Path(f"/proc/{int(pid)}/stat").read_text()
    except FileNotFoundError:
        return None
    fields = stat[stat.rindex(")") + 2:].split()
    if fields[0] in {"Z", "X"}:
        return None
    boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    return f"{boot}:{fields[19]}"


def process_state(pid, expected):
    if not pid or not expected:
        return "unknown"
    try:
        actual = process_identity(pid)
    except (OSError, ValueError, IndexError):
        return "unknown"
    if actual is None:
        return "exited"
    return "live" if actual == expected else "unknown"


class Queue:
    def __init__(self, runtime):
        supplied = Path(runtime).expanduser()
        if not supplied.is_absolute():
            raise ValueError("--runtime must be an explicit absolute shared path")
        self.runtime = supplied.resolve()
        marker = self.runtime / "queue-runtime.json"
        if not marker.is_file():
            raise ValueError("runtime is not initialized; use init first")
        if json.loads(marker.read_text())["canonical_runtime"] != str(self.runtime):
            raise ValueError("runtime was moved/copied; canonical path differs")
        self.db = self.runtime / "queue.sqlite3"

    @classmethod
    def initialize(cls, runtime):
        path = Path(runtime).expanduser()
        if not path.is_absolute():
            raise ValueError("--runtime must be an explicit absolute shared path")
        path = path.resolve()
        path.mkdir(parents=True, exist_ok=True)
        # Serialize first-time initialization across worktrees, without truncation.
        with (path / "init.lock").open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            marker = path / "queue-runtime.json"
            if not marker.exists():
                atomic_json(marker, {"schema_version": 1, "canonical_runtime": str(path)})
            queue = cls(path)
            with queue.connection() as db:
                db.executescript("""
                    CREATE TABLE IF NOT EXISTS jobs (
                        job_id TEXT PRIMARY KEY, job_key TEXT NOT NULL UNIQUE,
                        run_id TEXT NOT NULL, task_id TEXT NOT NULL, dispatch_id TEXT NOT NULL,
                        owner TEXT NOT NULL, command TEXT NOT NULL CHECK(command IN ('cpu-mock','vlm-batch01')),
                        input_json TEXT NOT NULL, config_json TEXT NOT NULL,
                        input_hash TEXT NOT NULL, config_hash TEXT NOT NULL,
                        source_hash TEXT NOT NULL, code_sha TEXT NOT NULL,
                        timeout REAL NOT NULL, status TEXT NOT NULL,
                        created_at REAL NOT NULL, cancel_requested INTEGER NOT NULL DEFAULT 0
                    );
                    CREATE TABLE IF NOT EXISTS attempts (
                        attempt_id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(job_id),
                        attempt_no INTEGER NOT NULL CHECK(attempt_no BETWEEN 1 AND 2),
                        owner TEXT NOT NULL, status TEXT NOT NULL,
                        supervisor_pid INTEGER, supervisor_identity TEXT,
                        child_pid INTEGER, child_identity TEXT,
                        started_at REAL NOT NULL, finished_at REAL, exit_code INTEGER,
                        heartbeat REAL NOT NULL, timeout REAL NOT NULL,
                        result_manifest TEXT, reason TEXT,
                        UNIQUE(job_id, attempt_no)
                    );
                """)
            queue.migrate_commands()
        return queue

    def migrate_commands(self, include_mvp=False, include_cv=False, include_vlm_batch02=False, include_pose=False, include_public_pose=False, include_roi_pose=False, include_resolution_pose=False):
        """Backup then atomically rebuild only the old command CHECK; keep every row."""
        if include_mvp or include_cv or include_vlm_batch02 or include_pose or include_public_pose or include_roi_pose or include_resolution_pose:
            target = "'batch06-pose'" if include_resolution_pose else "'batch05-pose'" if include_roi_pose else "'batch04-pose'" if include_public_pose else "'batch03-pose'" if include_pose else "'vlm-batch02'" if include_vlm_batch02 else ("'batch02-cv'" if include_cv else "'mvp-0001'")
            with self.connection() as db:
                sql = db.execute("SELECT sql FROM sqlite_master WHERE name='jobs'").fetchone()[0]
                if target in sql:
                    return  # Already migrated: enqueue may proceed while GPU is busy.
        with self.gpu_lock(blocking=False) as lock:
            if lock is None:
                raise ValueError('cannot migrate while a queue reservation is held')
            with self.connection() as db:
                sql = db.execute("SELECT sql FROM sqlite_master WHERE name='jobs'").fetchone()[0]
                if include_resolution_pose:
                    if "'batch06-pose'" in sql:
                        return
                    old_check = "CHECK(command IN ('cpu-mock','vlm-batch01','mvp-0001','batch02-cv','vlm-batch02','batch03-pose','batch04-pose','batch05-pose'))"
                    if old_check not in sql:
                        raise ValueError('resolution pose registration requires preserved batch05 queue schema')
                    new_check = old_check[:-2] + ",'batch06-pose'))"
                elif include_roi_pose:
                    if "'batch05-pose'" in sql:
                        return
                    old_check = "CHECK(command IN ('cpu-mock','vlm-batch01','mvp-0001','batch02-cv','vlm-batch02','batch03-pose','batch04-pose'))"
                    if old_check not in sql:
                        raise ValueError('ROI pose registration requires preserved batch04 queue schema')
                    new_check = old_check[:-2] + ",'batch05-pose'))"
                elif include_public_pose:
                    if "'batch04-pose'" in sql:
                        return
                    old_check = "CHECK(command IN ('cpu-mock','vlm-batch01','mvp-0001','batch02-cv','vlm-batch02','batch03-pose'))"
                    if old_check not in sql:
                        raise ValueError('public pose registration requires preserved batch03 queue schema')
                    new_check = "CHECK(command IN ('cpu-mock','vlm-batch01','mvp-0001','batch02-cv','vlm-batch02','batch03-pose','batch04-pose'))"
                elif include_pose:
                    if "'batch03-pose'" in sql:
                        return
                    old_check = "CHECK(command IN ('cpu-mock','vlm-batch01','mvp-0001','batch02-cv','vlm-batch02'))"
                    if old_check not in sql:
                        raise ValueError('pose registration requires preserved batch02 queue schema')
                    new_check = "CHECK(command IN ('cpu-mock','vlm-batch01','mvp-0001','batch02-cv','vlm-batch02','batch03-pose'))"
                elif include_vlm_batch02:
                    if "'vlm-batch02'" in sql:
                        return
                    allowed = ("CHECK(command='cpu-mock')",
                        "CHECK(command IN ('cpu-mock','vlm-batch01'))",
                        "CHECK(command IN ('cpu-mock','vlm-batch01','mvp-0001'))",
                        "CHECK(command IN ('cpu-mock','vlm-batch01','mvp-0001','batch02-cv'))")
                    old_check = next((v for v in allowed if v in sql), None)
                    if old_check is None:
                        raise ValueError('unrecognized queue schema')
                    new_check = "CHECK(command IN ('cpu-mock','vlm-batch01','mvp-0001','batch02-cv','vlm-batch02'))"
                elif include_cv:
                    if "'batch02-cv'" in sql:
                        return
                    allowed = ("CHECK(command='cpu-mock')",
                        "CHECK(command IN ('cpu-mock','vlm-batch01'))",
                        "CHECK(command IN ('cpu-mock','vlm-batch01','mvp-0001'))")
                    old_check = next((v for v in allowed if v in sql), None)
                    if old_check is None:
                        raise ValueError('unrecognized queue schema')
                    new_check = "CHECK(command IN ('cpu-mock','vlm-batch01','mvp-0001','batch02-cv'))"
                elif include_mvp:
                    if "'mvp-0001'" in sql:
                        return
                    if "CHECK(command='cpu-mock')" in sql:
                        old_check = "CHECK(command='cpu-mock')"
                    elif "CHECK(command IN ('cpu-mock','vlm-batch01'))" in sql:
                        old_check = "CHECK(command IN ('cpu-mock','vlm-batch01'))"
                    else:
                        raise ValueError('unrecognized queue schema')
                    new_check = "CHECK(command IN ('cpu-mock','vlm-batch01','mvp-0001'))"
                elif "CHECK(command='cpu-mock')" not in sql:
                    if "'vlm-batch01'" not in sql:
                        raise ValueError('unrecognized queue schema')
                    return
                else:
                    old_check = "CHECK(command='cpu-mock')"
                    new_check = "CHECK(command IN ('cpu-mock','vlm-batch01'))"
                db.execute('PRAGMA foreign_keys=OFF')
                db.execute('BEGIN IMMEDIATE')
                if db.execute("SELECT 1 FROM jobs WHERE status IN ('running','unknown')").fetchone():
                    raise ValueError('unresolved queue prevents schema migration')
                migration = 'batch06-pose' if include_resolution_pose else 'batch05-pose' if include_roi_pose else 'batch04-pose' if include_public_pose else 'batch03-pose' if include_pose else 'batch02-vlm' if include_vlm_batch02 else ('batch02-cv' if include_cv else ('mvp' if include_mvp else 'vlm'))
                backup = self.runtime / f'queue-before-{migration}-{uuid.uuid4().hex}.sqlite3'
                # Separate reader copies committed state while this write lock
                # prevents enqueues. Backup precedes the first schema mutation.
                with sqlite3.connect(self.db) as reader, sqlite3.connect(backup) as dest:
                    reader.backup(dest)
                with backup.open('rb') as stream:
                    os.fsync(stream.fileno())
                parent_fd = os.open(self.runtime, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(parent_fd)
                finally:
                    os.close(parent_fd)
                jobs = [tuple(r) for r in db.execute('SELECT * FROM jobs ORDER BY job_id')]
                attempts = [tuple(r) for r in db.execute('SELECT * FROM attempts ORDER BY attempt_id')]
                extras = [r[0] for r in db.execute("SELECT sql FROM sqlite_master WHERE tbl_name='jobs' "
                                                  "AND type IN ('index','trigger') AND sql IS NOT NULL")]
                new_sql = re.sub(r'CREATE TABLE (?:"jobs"|jobs)(?=\s|\()', 'CREATE TABLE jobs_vlm', sql, count=1).replace(
                    old_check, new_check)
                db.execute(new_sql)
                db.execute('INSERT INTO jobs_vlm SELECT * FROM jobs')
                db.execute('DROP TABLE jobs')
                db.execute('ALTER TABLE jobs_vlm RENAME TO jobs')
                for statement in extras:
                    db.execute(statement)
                if jobs != [tuple(r) for r in db.execute('SELECT * FROM jobs ORDER BY job_id')] or attempts != [
                        tuple(r) for r in db.execute('SELECT * FROM attempts ORDER BY attempt_id')]:
                    raise ValueError('migration preservation mismatch')
                if db.execute('PRAGMA foreign_key_check').fetchall():
                    raise ValueError('migration foreign key mismatch')
                db.commit()
                db.execute('PRAGMA foreign_keys=ON')

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.db, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        try:
            yield db
        finally:
            if db.in_transaction:
                db.rollback()
            db.close()

    @contextmanager
    def gpu_lock(self, blocking=True):
        # NEVER unlink, truncate, or LOCK_UN: child shares this open description.
        lock = (self.runtime / "gpu.lock").open("a+")
        try:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
            except BlockingIOError:
                yield None
            else:
                yield lock
        finally:
            lock.close()

    def enqueue(self, *, job_key, run_id, task_id, dispatch_id, owner,
                command="cpu-mock", input_value=None, config=None, timeout=10,
                expected_input_hash=None, expected_config_hash=None):
        if command not in {"cpu-mock", "vlm-batch01", "mvp-0001", "batch02-cv", "vlm-batch02", "batch03-pose", "batch04-pose", "batch05-pose", "batch06-pose"}:
            raise ValueError("only registered cpu-mock/vlm-batch01/mvp-0001/batch02-cv/vlm-batch02/batch03-pose/batch04-pose commands are permitted")
        if any(not isinstance(x, str) or not x.strip() for x in
               (job_key, run_id, task_id, dispatch_id, owner)):
            raise ValueError("job key, run/task/dispatch and owner are required")
        if command == 'cpu-mock':
            config = {"seconds": 0.1, "exit_code": 0} if config is None else config
            if not isinstance(config, dict) or set(config) != {"seconds", "exit_code"}:
                raise ValueError("mock config must contain only seconds and exit_code")
            seconds, code = config["seconds"], config["exit_code"]
            if (type(seconds) not in (int, float) or not math.isfinite(seconds)
                    or not 0 <= seconds <= 3600 or type(code) is not int or not 0 <= code <= 125):
                raise ValueError("seconds must be 0..3600; exit_code must be integer 0..125")
        elif command == 'batch06-pose':
            from orchestration.batch06_pose_command import validate, validate_assignment, job_key as pose_job_key
            validate(config, input_value, self.runtime)
            a = validate_assignment(run_id, task_id, dispatch_id)
            if job_key != pose_job_key(config['stage']):
                raise ValueError('one fixed public pose job key per stage required')
            current_sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
            if a['code_sha'] != current_sha:
                raise ValueError('coordinator source commit differs')
        elif command == 'batch05-pose':
            from orchestration.batch05_pose_command import validate, validate_assignment, job_key as pose_job_key
            validate(config, input_value, self.runtime)
            a = validate_assignment(run_id, task_id, dispatch_id)
            if job_key != pose_job_key(config['stage']):
                raise ValueError('one fixed public pose job key per stage required')
            current_sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
            if a['code_sha'] != current_sha:
                raise ValueError('coordinator source commit differs')
        elif command == 'batch04-pose':
            from orchestration.batch04_pose_command import validate, validate_assignment, job_key as pose_job_key
            validate(config, input_value, self.runtime)
            a = validate_assignment(run_id, task_id, dispatch_id)
            if job_key != pose_job_key(config['stage']):
                raise ValueError('one fixed public pose job key per stage required')
            current_sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
            if a['code_sha'] != current_sha:
                raise ValueError('coordinator source commit differs')
        elif command == 'batch03-pose':
            from orchestration.batch03_pose_command import validate, validate_assignment, job_key as pose_job_key
            validate(config, input_value, self.runtime)
            validate_assignment(run_id, task_id, dispatch_id)
            if job_key != pose_job_key(config['stage']):
                raise ValueError('one fixed pose job key per stage required')
        elif command == 'vlm-batch02':
            from orchestration.batch02_vlm_command import validate, validate_assignment, job_key as vlm_job_key
            validate(config, input_value, self.runtime)
            validate_assignment(run_id, task_id, dispatch_id)
            if job_key != vlm_job_key(config['condition_id']):
                raise ValueError('one fixed VLM job key per condition required')
        elif command == 'batch02-cv':
            from orchestration.batch02_cv_command import validate, validate_assignment
            validate(config, input_value, self.runtime)
            validate_assignment(run_id, task_id, dispatch_id)
            if job_key != 'batch0002-exp0019-cv-' + config['stage']:
                raise ValueError('one fixed CV job key per stage required')
        elif command == 'vlm-batch01':
            from orchestration.vlm_command import validate
            validate(config, input_value, self.runtime)
        else:
            from orchestration.mvp_command import validate, validate_run
            validate(config, input_value, self.runtime)
            validate_run(config['phase'], run_id)
        limit = 900 if command == 'vlm-batch01' else 3600
        if command == 'vlm-batch02':
            limit = 1800
        if command == 'mvp-0001':
            limit = 900 if config['phase'] == 'dev' else 1800
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= limit:
            raise ValueError(f"timeout must be finite and 0 < timeout <= {limit}")
        input_value = {"synthetic": True} if input_value is None else input_value
        ih, ch = digest(input_value), digest(config)
        if expected_input_hash not in (None, ih) or expected_config_hash not in (None, ch):
            raise ValueError("expected input/config hash mismatch")
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
                             capture_output=True, check=True).stdout.strip()
        values = dict(job_key=job_key, run_id=run_id, task_id=task_id,
                      dispatch_id=dispatch_id, owner=owner, command=command,
                      input_json=json.dumps(input_value, sort_keys=True),
                      config_json=json.dumps(config, sort_keys=True),
                      input_hash=ih, config_hash=ch, source_hash=source_hash(command, config),
                      code_sha=sha, timeout=timeout)
        if command == 'batch06-pose':
            self.migrate_commands(include_resolution_pose=True)
        if command == 'batch05-pose':
            self.migrate_commands(include_roi_pose=True)
        if command == 'batch04-pose':
            self.migrate_commands(include_public_pose=True)
        if command == 'batch03-pose':
            self.migrate_commands(include_pose=True)
        if command == 'vlm-batch02':
            self.migrate_commands(include_vlm_batch02=True)
        if command == 'batch02-cv':
            self.migrate_commands(include_cv=True)
        if command == 'mvp-0001':
            self.migrate_commands(include_mvp=True)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("SELECT * FROM jobs WHERE job_key=?", (job_key,)).fetchone()
            if previous:
                if any(previous[k] != v for k, v in values.items()):
                    raise ValueError("job key already exists with a different contract")
                db.commit()
                return dict(previous)
            values.update(job_id=uuid.uuid4().hex, status="queued", created_at=time.time())
            columns = ",".join(values)
            db.execute(f"INSERT INTO jobs ({columns}) VALUES ({','.join('?' for _ in values)})",
                       tuple(values.values()))
            db.commit()
        return values

    def status(self):
        with self.connection() as db:
            jobs = [dict(r) for r in db.execute("SELECT * FROM jobs ORDER BY created_at")]
            return {"canonical_runtime": str(self.runtime), "synthetic": all(j['command'] == 'cpu-mock' for j in jobs),
                    "jobs": jobs,
                    "attempts": [dict(r) for r in db.execute("SELECT * FROM attempts ORDER BY started_at")]}

    def _claim(self):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            # Unresolved identity is a queue-wide fail-closed condition.
            if db.execute("SELECT 1 FROM jobs WHERE status IN ('running','unknown')").fetchone():
                db.commit()
                return None
            row = db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
            if row is None:
                db.commit()
                return None
            job = dict(row)
            number = db.execute("SELECT COUNT(*) FROM attempts WHERE job_id=?", (job["job_id"],)).fetchone()[0] + 1
            now, attempt = time.time(), uuid.uuid4().hex
            db.execute("INSERT INTO attempts (attempt_id,job_id,attempt_no,owner,status,"
                       "supervisor_pid,supervisor_identity,started_at,heartbeat,timeout) "
                       "VALUES (?,?,?,?,'running',?,?,?,?,?)",
                       (attempt, job["job_id"], number, job["owner"], os.getpid(),
                        process_identity(os.getpid()), now, now, job["timeout"]))
            db.execute("UPDATE jobs SET status='running' WHERE job_id=?", (job["job_id"],))
            db.commit()
            return job, attempt

    def _finish(self, attempt, status, exit_code, reason):
        with self.connection() as db:
            row = dict(db.execute("SELECT * FROM attempts WHERE attempt_id=?", (attempt,)).fetchone())
            job = dict(db.execute("SELECT * FROM jobs WHERE job_id=?", (row["job_id"],)).fetchone())
            manifest = self.runtime / "attempts" / attempt / "manifest.json"
            manifest.parent.mkdir(parents=True, exist_ok=True)
            finished = time.time()
            real = job['command'] == 'vlm-batch01'
            mvp = job['command'] == 'mvp-0001'
            cv = job['command'] == 'batch02-cv'
            vlm02 = job['command'] == 'vlm-batch02'
            pose06 = job['command'] == 'batch06-pose'
            pose05 = job['command'] == 'batch05-pose'
            pose04 = job['command'] == 'batch04-pose'
            pose = job['command'] in ('batch03-pose', 'batch04-pose', 'batch05-pose', 'batch06-pose')
            if pose:
                if pose06:
                    from orchestration.batch06_pose_command import INTERPRETER as POSE_PYTHON, output_path as pose_output_path
                elif pose05:
                    from orchestration.batch05_pose_command import INTERPRETER as POSE_PYTHON, output_path as pose_output_path
                elif pose04:
                    from orchestration.batch04_pose_command import INTERPRETER as POSE_PYTHON, output_path as pose_output_path
                else:
                    from orchestration.batch03_pose_command import INTERPRETER as POSE_PYTHON, output_path as pose_output_path
                pose_config = json.loads(job['config_json'])
            if vlm02:
                from orchestration.batch02_vlm_command import INTERPRETER as VLM02_PYTHON, output_path as vlm02_output_path
                vlm02_config = json.loads(job['config_json'])
            if cv:
                from orchestration.batch02_cv_command import INTERPRETER as CV_PYTHON, output_path as cv_output_path
                cv_config = json.loads(job['config_json'])
            if real:
                from orchestration.vlm_command import ASSETS, MODELS, output_path
                adapter = json.loads(job['config_json'])['adapter']
            if mvp:
                from orchestration.mvp_command import INTERPRETER, output_path as mvp_output_path
                mvp_config = json.loads(job['config_json'])
            atomic_json(manifest, {"schema_version": 1, "synthetic": not (real or mvp or cv or vlm02 or pose),
                        "execution_status": status,
                        "registration": {"command": job['command'],
                                         "script": str(ROOT / 'batch06_pose/runner.py') if pose06 else str(ROOT / 'batch05_pose/runner.py') if pose05 else str(ROOT / 'batch04_pose/runner.py') if pose04 else str(ROOT / 'batch03_pose/runner.py') if pose else str(ROOT / 'batch02_vlm/runner.py') if vlm02 else str(ROOT / 'batch02_cv/runner.py') if cv else str(ROOT / 'mvp/runner.py') if mvp else (str(ROOT / 'vlm_batch/run.py') if real else str(MOCK)),
                                         "cwd": str(ROOT), "interpreter": str(POSE_PYTHON) if pose else str(VLM02_PYTHON) if vlm02 else str(CV_PYTHON) if cv else str(INTERPRETER) if mvp else (str(ASSETS / MODELS[adapter][1]) if real else sys.executable)},
                        "job": {**job, "status": status}, "attempt": {**row, "status": status,
                        "exit_code": exit_code, "finished_at": finished, "reason": reason},
                        "result": str(pose_output_path(pose_config['stage'], attempt)) if pose else str(vlm02_output_path(vlm02_config['condition_id'], attempt)) if vlm02 else str(cv_output_path(cv_config['stage'], attempt)) if cv else str(mvp_output_path(mvp_config['phase'], attempt)) if mvp else (str(output_path(adapter, attempt)) if real else str(manifest.with_name("mock-result.json"))),
                        "mock_result": None if real or mvp or cv or vlm02 or pose else str(manifest.with_name("mock-result.json")),
                        "limitations": ["Queue exit alone does not establish model quality"] if real or mvp or cv or vlm02 or pose else
                                        ["CPU mock timing only; no GPU/model performance measured"]})
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE attempts SET status=?,exit_code=?,finished_at=?,heartbeat=?,"
                       "result_manifest=?,reason=? WHERE attempt_id=?",
                       (status, exit_code, finished, finished, str(manifest), reason, attempt))
            db.execute("UPDATE jobs SET status=? WHERE job_id=?", (status, row["job_id"]))
            db.commit()

    def _recover_locked(self):
        with self.connection() as db:
            rows = db.execute("SELECT * FROM attempts WHERE status IN ('running','unknown')").fetchall()
        results = []
        for row in rows:
            states = [process_state(row["supervisor_pid"], row["supervisor_identity"])]
            if row["child_pid"] is not None:
                states.append(process_state(row["child_pid"], row["child_identity"]))
            if "unknown" in states:
                state = "unknown"
            elif "live" in states:
                state = "running"
            else:
                state = "interrupted"
            if state != "running":
                self._finish(row["attempt_id"], state, None,
                             "process identity unverifiable" if state == "unknown"
                             else "supervisor and recorded child exited without final receipt")
            results.append({"attempt_id": row["attempt_id"], "status": state})
        return results

    def recover(self):
        with self.gpu_lock(blocking=False) as lock:
            if lock is None:
                return {"status": "busy", "reason": "reservation held; no mutation or signal sent"}
            return {"status": "checked", "attempts": self._recover_locked()}

    def retry(self, job_id):
        with self.gpu_lock(blocking=False) as lock:
            if lock is None:
                raise ValueError("reservation is held; retry refused")
            self._recover_locked()
            with self.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
                count = db.execute("SELECT COUNT(*) FROM attempts WHERE job_id=?", (job_id,)).fetchone()[0]
                if row is None or row["status"] not in RETRYABLE or count != 1:
                    raise ValueError("one explicit retry allowed only after a known failed/cancelled/interrupted attempt")
                if row['command']=='batch06-pose':
                    from orchestration.batch06_pose_command import retry_guard
                    retry_guard(db,dict(row))
                if row['command']=='batch05-pose':
                    from orchestration.batch05_pose_command import retry_guard
                    retry_guard(db,dict(row))
                if row['command']=='batch04-pose':
                    from orchestration.batch04_pose_command import retry_guard
                    retry_guard(db,dict(row))
                if row['command']=='batch03-pose':
                    from orchestration.batch03_pose_command import retry_guard
                    retry_guard(db,dict(row))
                if row['command']=='vlm-batch02':
                    from orchestration.batch02_vlm_command import retry_guard
                    retry_guard(db,dict(row))
                db.execute("UPDATE jobs SET status='queued',cancel_requested=0 WHERE job_id=?", (job_id,))
                db.commit()
        return {"job_id": job_id, "status": "queued", "explicit_retry": True}

    def cancel(self, job_id):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT status FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None or row[0] not in {"queued", "running"}:
                raise ValueError("only queued/running jobs can be cancelled")
            db.execute("UPDATE jobs SET cancel_requested=1,status=? WHERE job_id=?",
                       ("cancelled" if row[0] == "queued" else "running", job_id))
            db.commit()
        return {"job_id": job_id, "cancel_requested": True}

    def supervise_once(self):
        # Fail before claiming if this Linux runtime cannot bind signals to PIDs.
        if not callable(getattr(signal, "pidfd_send_signal", None)):
            raise ValueError("this runtime requires signal.pidfd_send_signal")
        probe = os.pidfd_open(os.getpid())
        os.close(probe)
        # The supervisor owns this lock before claim and throughout child lifetime.
        with self.gpu_lock() as lock:
            self._recover_locked()
            claimed = self._claim()
            if claimed is None:
                return {"status": "idle_or_unresolved"}
            job, attempt = claimed
            directory = self.runtime / "attempts" / attempt
            directory.mkdir(parents=True)
            child = None
            deadline = time.monotonic() + job['timeout']
            try:
                config = json.loads(job['config_json'])
                if job["source_hash"] != source_hash(job['command'], config):
                    raise ValueError("registered source changed since enqueue")
                if digest(json.loads(job["input_json"])) != job["input_hash"] or digest(json.loads(job["config_json"])) != job["config_hash"]:
                    raise ValueError("stored input/config hash mismatch")
                config = json.loads(job["config_json"])
                if job['command'] == 'batch06-pose':
                    from orchestration.batch06_pose_command import command
                    argv = command(config, json.loads(job['input_json']), self.runtime, attempt, lock.fileno())
                elif job['command'] == 'batch05-pose':
                    from orchestration.batch05_pose_command import command
                    argv = command(config, json.loads(job['input_json']), self.runtime, attempt, lock.fileno())
                elif job['command'] == 'batch04-pose':
                    from orchestration.batch04_pose_command import command
                    argv = command(config, json.loads(job['input_json']), self.runtime, attempt, lock.fileno())
                elif job['command'] == 'batch03-pose':
                    from orchestration.batch03_pose_command import command
                    argv = command(config, json.loads(job['input_json']), self.runtime, attempt, lock.fileno())
                elif job['command'] == 'vlm-batch02':
                    from orchestration.batch02_vlm_command import command
                    argv = command(config, json.loads(job['input_json']), self.runtime, attempt, lock.fileno())
                elif job['command'] == 'batch02-cv':
                    from orchestration.batch02_cv_command import command
                    argv = command(config, json.loads(job['input_json']), self.runtime, attempt, lock.fileno())
                elif job['command'] == 'mvp-0001':
                    from orchestration.mvp_command import command
                    argv = command(config, json.loads(job['input_json']), self.runtime, attempt, lock.fileno())
                elif job['command'] == 'vlm-batch01':
                    from orchestration.vlm_command import command
                    argv = command(config, json.loads(job['input_json']), self.runtime, attempt, lock.fileno())
                elif job['command'] == 'cpu-mock':
                    argv = [sys.executable, "-I", str(MOCK), "--seconds", str(config["seconds"]),
                            "--exit-code", str(config["exit_code"]), "--result",
                            str(directory / "mock-result.json"), "--lock-fd", str(lock.fileno())]
                else:
                    raise ValueError('unregistered command in stored job')
                with (directory / "child.log").open("ab") as output:
                    child = subprocess.Popen(argv, cwd=ROOT, stdin=subprocess.DEVNULL,
                                             stdout=output, stderr=subprocess.STDOUT,
                                             pass_fds=(lock.fileno(),), start_new_session=True)
                identity = process_identity(child.pid)
                with self.connection() as db:
                    db.execute("UPDATE attempts SET child_pid=?,child_identity=? WHERE attempt_id=?",
                               (child.pid, identity, attempt))
                # pidfd binds timeout/cancel signals to this exact process incarnation.
                pidfd = os.pidfd_open(child.pid)
                try:
                    status, reason = None, None
                    while child.poll() is None:
                        with self.connection() as db:
                            cancelled = db.execute("SELECT cancel_requested FROM jobs WHERE job_id=?", (job["job_id"],)).fetchone()[0]
                            db.execute("UPDATE attempts SET heartbeat=? WHERE attempt_id=?", (time.time(), attempt))
                        if cancelled or time.monotonic() >= deadline:
                            status, reason = ("cancelled", "explicit cancellation") if cancelled else ("failed", "timeout")
                            try:
                                signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                            except ProcessLookupError:
                                pass  # Exact child exited between poll and signal.
                            break
                        time.sleep(0.05)
                    code = child.wait()
                    status = status or ("succeeded" if code == 0 else "failed")
                    self._finish(attempt, status, code, reason or "child exit observed")
                finally:
                    os.close(pidfd)
            except Exception as error:
                # If a child exists, retain its inherited lock and wait before release.
                # Do not guess a PID or send a signal without a verified pidfd.
                if child is not None:
                    child.wait()
                self._finish(attempt, "failed", child.returncode if child else None,
                             f"{type(error).__name__}: {error}")
            return {"job_id": job["job_id"], "attempt_id": attempt,
                    "status": next(j["status"] for j in self.status()["jobs"] if j["job_id"] == job["job_id"])}

    def run_once(self):
        # Detached supervisor survives loss of this caller; it claims its own job.
        argv = [sys.executable, "-m", "orchestration.queue", "--runtime", str(self.runtime), "_supervise"]
        with (self.runtime / "supervisor.log").open("ab") as output:
            process = subprocess.Popen(argv, cwd=ROOT, stdin=subprocess.DEVNULL,
                                       stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        return {"supervisor_pid": process.pid, "supervisor_exit_code": process.wait()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", required=True, help="absolute canonical runtime shared by ALL worktrees")
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("init", help="initialize the shared runtime")
    enqueue = commands.add_parser("enqueue", help="register one allowlisted job (idempotent job key)")
    for field in ("job-key", "run-id", "task-id", "dispatch-id", "owner"):
        enqueue.add_argument("--" + field, required=True)
    enqueue.add_argument("--command", choices=["cpu-mock", "vlm-batch01", "mvp-0001", "batch02-cv", "vlm-batch02", "batch03-pose"], default="cpu-mock")
    enqueue.add_argument("--input-json", type=json.loads, default={"synthetic": True})
    enqueue.add_argument("--config-json", type=json.loads, default={"seconds": 0.1, "exit_code": 0})
    enqueue.add_argument("--expected-input-hash")
    enqueue.add_argument("--expected-config-hash")
    enqueue.add_argument("--timeout", type=float, default=10)
    commands.add_parser("run-once", help="wait for reservation and supervise at most one queued job")
    commands.add_parser("status", help="JSON jobs and attempts, without recovery or execution")
    commands.add_parser("recover", help="verify process identities; never signal or auto-retry")
    for action in ("retry", "cancel"):
        item = commands.add_parser(action, help="explicit " + action)
        item.add_argument("job_id")
    commands.add_parser("_supervise", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        queue = Queue.initialize(args.runtime) if args.action == "init" else Queue(args.runtime)
        if args.action == "enqueue":
            result = queue.enqueue(job_key=args.job_key, run_id=args.run_id, task_id=args.task_id,
                                   dispatch_id=args.dispatch_id, owner=args.owner, command=args.command,
                                   input_value=args.input_json, config=args.config_json, timeout=args.timeout,
                                   expected_input_hash=args.expected_input_hash,
                                   expected_config_hash=args.expected_config_hash)
        elif args.action in {"retry", "cancel"}:
            result = getattr(queue, args.action)(args.job_id)
        elif args.action == "init":
            result = {"canonical_runtime": str(queue.runtime), "status": "initialized", "synthetic": True}
        else:
            method = {"run-once": "run_once", "_supervise": "supervise_once"}.get(args.action, args.action)
            result = getattr(queue, method)()
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, OSError, sqlite3.Error, subprocess.SubprocessError) as error:
        parser.exit(2, f"queue: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
