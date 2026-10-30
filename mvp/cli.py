"""MVP frontend to the existing canonical queue; no direct model execution."""

import argparse
import json
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True,
                        help="existing absolute canonical GPU queue (no new runtime)")
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("status", help="read queue state without inference")
    enqueue = actions.add_parser("enqueue", help="register a frozen MVP job, without running it")
    from orchestration.mvp_command import PHASES
    enqueue.add_argument("--phase", choices=PHASES, required=True)
    enqueue.add_argument("--view", choices=["full_frame", "fixed_roi"], required=True)
    for field in ("job-key", "run-id", "task-id", "dispatch-id", "owner"):
        enqueue.add_argument("--" + field, required=True)
    run_once = actions.add_parser("run-once", help="supervise at most one queued job under the existing lock")
    run_once.add_argument('--job-id', help='claim only this exact queued job')
    args = parser.parse_args(argv)
    # Lazy imports keep --help CPU-only and usable before registry integration.
    from orchestration import mvp_command as registered
    from orchestration.queue import Queue

    if not args.runtime.is_absolute() or args.runtime.resolve() != registered.RUNTIME.resolve():
        parser.error("MVP execution requires the existing canonical queue")
    queue = Queue(args.runtime)
    if args.action == "enqueue":
        if args.phase == "dev" and args.view != "fixed_roi":
            parser.error("development comparison registers only the frozen fixed_roi condition")
        registered.validate_run(args.phase, args.run_id)
        _, _, frozen = registered.load_configs()
        if args.phase == 'appearance-8b':
            from mvp.exp0038 import validate_authorization
            authorization = validate_authorization()
            if tuple(authorization[k] for k in ('run_id', 'task_id', 'dispatch_id')) != (
                    args.run_id, args.task_id, args.dispatch_id):
                parser.error('EXP-0038 requires the current authorized Run/Task/Dispatch')
        config = {"phase": args.phase, "view": args.view,
                  "settings": registered.settings_for_phase(args.phase).copy()}
        inputs = registered.input_contract(args.phase)
        registered.validate(config, inputs, args.runtime)
        result = queue.enqueue(job_key=args.job_key, run_id=args.run_id, task_id=args.task_id,
                               dispatch_id=args.dispatch_id, owner=args.owner,
                               command="mvp-0001", input_value=inputs, config=config,
                               timeout=frozen['full_timeout_seconds' if args.phase not in ('dev', 'full')
                                              else f"{args.phase}_timeout_seconds"])
    elif args.action == "run-once":
        result = queue.run_once(args.job_id) if args.job_id else queue.run_once()
    else:
        result = queue.status()
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
