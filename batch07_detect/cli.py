# SPDX-License-Identifier: AGPL-3.0-only
"""Single canonical queue entrypoint, no standalone model operation."""
import argparse
import json
from orchestration.batch07_detect_command import LOCAL,RUNTIME,SETTINGS,IDENTITY,input_contract,validate_assignment,job_key
from orchestration.queue import Queue


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('enqueue','run-once','status'))
    a=p.parse_args();q=Queue(RUNTIME)
    if a.action=='enqueue':
        validate_assignment(*IDENTITY)
        out=q.enqueue(job_key=job_key(),run_id=IDENTITY[0],task_id=IDENTITY[1],dispatch_id=IDENTITY[2],
            owner='BATCH-0007-DETECT',command='batch07-detect',input_value=input_contract(),
            config=dict(stage='train_compare',settings=SETTINGS),timeout=3600)
    else:out=q.supervise_once() if a.action=='run-once' else q.status()
    print(json.dumps(out,sort_keys=True))


if __name__=='__main__':main()
