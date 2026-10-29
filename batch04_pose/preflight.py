# SPDX-License-Identifier: AGPL-3.0-only
"""CPU-only frozen API/readiness receipt; no weights are deserialized."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from orchestration.batch04_pose_command import ROOT, LOCAL, RUNTIME, manifest, sources, input_contract
from orchestration.mock_job import atomic_json
from orchestration.vlm_command import file_hash
from batch04_pose.api import official_audit


def main():
    if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
        raise ValueError('CUDA must be hidden for CPU preflight')
    if Path(sys.executable).absolute() != ROOT / '.venv-pose-batch03/bin/python':
        raise ValueError('reuse pinned isolated interpreter')
    d = manifest()
    audit = official_audit()
    inputs = input_contract('smoke')
    atomic_json(LOCAL / 'official-api-audit.json', audit)
    # Snapshot every existing native row before additive migration/registration.
    before = LOCAL / 'queue-before.local.json'
    with sqlite3.connect(f'file:{RUNTIME / "queue.sqlite3"}?mode=ro',uri=True) as db:
        db.row_factory = sqlite3.Row
        rows = {t:[dict(r) for r in db.execute('SELECT * FROM '+t+' ORDER BY '+k)]
            for t,k in [('jobs','job_id'),('attempts','attempt_id')]}
    if not before.exists():
        atomic_json(before, rows)
    else:
        frozen = json.loads(before.read_text())
        for t,k in [('jobs','job_id'),('attempts','attempt_id')]:
            current = {r[k]:r for r in rows[t]}
            if any(current.get(r[k]) != r for r in frozen[t]):
                raise ValueError('historical native queue row changed')
    receipt = dict(status='CPU preflight passed; GPU/model construction not authorized by this receipt',
        frames=len(d['frames']), smoke=inputs['frames'], remaining=265,
        input_contract_sha256=__import__('orchestration.queue',fromlist=['digest']).digest(inputs),
        manifest_sha256=file_hash(ROOT/'configs/batch0004_pose_manifest.json'),
        audit_sha256=file_hash(LOCAL/'official-api-audit.json'), sources=sources(),
        model_constructions=0, sample_predictions=0, cuda_initialized=False,
        test_log='runtime/BATCH-0004/cpu-tests.log',test_log_sha256=file_hash(LOCAL/'cpu-tests.log'),
        required_gate='coordinator source commit + independent reviewer + execution-authorization.json allowing smoke only')
    atomic_json(LOCAL/'readiness.json',receipt)
    print(json.dumps({k:receipt[k] for k in ('status','frames','smoke','remaining','manifest_sha256','audit_sha256','model_constructions','sample_predictions','cuda_initialized')},sort_keys=True))


if __name__ == '__main__':
    main()
