"""Fixed BATCH-0002 CV queue entrypoint; no direct model execution route."""
import argparse
import json
from orchestration.batch02_cv_command import (LOCAL, RUNTIME, SETTINGS, STAGES,
    input_contract, validate_assignment)
from orchestration.queue import Queue


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    enqueue = sub.add_parser('enqueue')
    enqueue.add_argument('--stage', choices=STAGES, required=True)
    sub.add_parser('run-once')
    sub.add_parser('status')
    args = parser.parse_args()
    queue = Queue(RUNTIME)
    if args.action == 'enqueue':
        authorization = json.loads((LOCAL / 'execution-authorization.json').read_text())
        run, task, dispatch = [authorization[k] for k in ('run_id', 'task_id', 'dispatch_id')]
        validate_assignment(run, task, dispatch)
        result = queue.enqueue(job_key='batch0002-exp0019-cv-' + args.stage,
            run_id=run, task_id=task, dispatch_id=dispatch, owner='BATCH-0002-CV', command='batch02-cv',
            config=dict(stage=args.stage, settings=SETTINGS), input_value=input_contract(args.stage), timeout=900)
    else:
        result = queue.run_once() if args.action == 'run-once' else queue.status()
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
