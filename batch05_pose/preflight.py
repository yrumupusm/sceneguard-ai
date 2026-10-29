# SPDX-License-Identifier: AGPL-3.0-only
"""CPU source/input/cache/API receipt; does not authorize execution."""
import json
import os
import sqlite3
from orchestration.batch05_pose_command import ROOT,LOCAL,RUNTIME,MANIFEST,sources,input_contract,CONDITIONS
from orchestration.queue import digest
from orchestration.mock_job import atomic_json
from orchestration.vlm_command import file_hash
from batch04_pose.api import official_audit


def main():
    if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise ValueError('hide CUDA for CPU preflight')
    audit=official_audit();inputs=input_contract()
    atomic_json(LOCAL/'official-api-audit.json',audit)
    with sqlite3.connect(f'file:{RUNTIME/"queue.sqlite3"}?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        rows={t:[dict(r) for r in db.execute('SELECT * FROM '+t+' ORDER BY '+k)] for t,k in [('jobs','job_id'),('attempts','attempt_id')]}
    before=LOCAL/'queue-before.local.json'
    if not before.exists():atomic_json(before,rows)
    else:
        old=json.loads(before.read_text())
        for t,k in [('jobs','job_id'),('attempts','attempt_id')]:
            current={r[k]:r for r in rows[t]}
            if any(current.get(r[k])!=r for r in old[t]):raise ValueError('historical native rows changed')
    receipt=dict(status='CPU ready; no GPU/model permission',sources=sources(),source_digest=digest(sources()),
        input_contract_sha256=digest(inputs),manifest_sha256=file_hash(MANIFEST),conditions=list(CONDITIONS),
        test_log_sha256=file_hash(LOCAL/'cpu-tests.log'),audit_sha256=file_hash(LOCAL/'official-api-audit.json'),
        model_constructions=0,new_predictions=0,cuda_initialized=False)
    atomic_json(LOCAL/'readiness.json',receipt)
    print(json.dumps({k:receipt[k] for k in ('status','source_digest','input_contract_sha256','manifest_sha256','test_log_sha256')},sort_keys=True))


if __name__=='__main__':main()
