"""Fixed condition registration and one canonical queue step; no direct model API."""
import argparse
import json
from orchestration.batch02_vlm_command import CONDITIONS,RUNTIME,SETTINGS,input_contract,job_key,validate_assignment
from orchestration.queue import Queue


def main():
    p=argparse.ArgumentParser();p.add_argument('--runtime',default=str(RUNTIME))
    s=p.add_subparsers(dest='action',required=True)
    e=s.add_parser('enqueue');e.add_argument('--condition',choices=CONDITIONS,required=True)
    for key in ('run-id','task-id','dispatch-id','owner'):
        e.add_argument('--'+key,required=True)
    s.add_parser('run-once');s.add_parser('status')
    a=p.parse_args()
    if a.runtime!=str(RUNTIME):
        raise ValueError('only canonical queue permitted')
    q=Queue(RUNTIME)
    if a.action=='enqueue':
        validate_assignment(a.run_id,a.task_id,a.dispatch_id)
        result=q.enqueue(command='vlm-batch02',job_key=job_key(a.condition),run_id=a.run_id,
            task_id=a.task_id,dispatch_id=a.dispatch_id,owner=a.owner,
            config=dict(condition_id=a.condition,settings=SETTINGS),input_value=input_contract(a.condition),timeout=1800)
    elif a.action=='run-once':
        result=q.run_once()
    else:
        result=q.status()
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
