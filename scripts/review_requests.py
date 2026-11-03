#!/usr/bin/env python3
"""Local explicit review-request lifecycle; does not run analysis or edit sources."""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from webapp.review_request_store import (  # noqa: E402
    RequestConflict, configured_store, experiment_entry,
)


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument('--config', help='lab JSON config (default: SCENEGUARD_LAB_CONFIG)')
    commands = root.add_subparsers(dest='command', required=True)
    create = commands.add_parser('create', help='create one explicit question from a JSON object')
    create.add_argument('--spec-file', required=True)
    pending = commands.add_parser('pending', help='read only: answers awaiting local acknowledgement')
    pending.add_argument('--experiment-id')
    pending.add_argument('--include-acknowledged', action='store_true', help='include answers read earlier but not resolved')
    acknowledge = commands.add_parser('acknowledge', help='acknowledge this exact answer revision')
    resolve = commands.add_parser('resolve', help='record application or deferral of an acknowledged answer')
    for command in (acknowledge, resolve):
        command.add_argument('id')
        command.add_argument('--expected-version', type=int, required=True)
        command.add_argument('--answer-version', type=int, required=True)
    acknowledge.add_argument('--note', default='')
    resolve.add_argument('--outcome', choices=('applied', 'deferred'), required=True)
    resolve.add_argument('--note', required=True)
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        config_path = args.config or os.environ.get('SCENEGUARD_LAB_CONFIG')
        if not config_path:
            raise ValueError('--config or SCENEGUARD_LAB_CONFIG is required')
        with open(config_path, encoding='utf-8') as source:
            config = json.load(source)
        db = configured_store(config)
        if args.command == 'create':
            with open(args.spec_file, encoding='utf-8') as source:
                result = {'request': db.create(config, json.load(source))}
        elif args.command == 'pending':
            if args.experiment_id:
                experiment_entry(config, args.experiment_id)
            rows = db.list(args.experiment_id)
            statuses = ('answered', 'acknowledged') if args.include_acknowledged else ('answered',)
            result = {'requests': [r for r in rows if r['status'] in statuses]}
        else:
            kwargs = dict(expected_version=args.expected_version, answer_version=args.answer_version, note=args.note)
            if args.command == 'resolve':
                kwargs['outcome'] = args.outcome
            result = {'request': getattr(db, args.command)(config, args.id, **kwargs)}
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except RequestConflict as exc:
        print(json.dumps({'error': str(exc), 'kind': 'conflict'}), file=sys.stderr)
        return 3
    except KeyError as exc:
        print(json.dumps({'error': str(exc), 'kind': 'missing'}), file=sys.stderr)
        return 4
    except (OSError, ValueError, TypeError, sqlite3.Error) as exc:
        print(json.dumps({'error': str(exc), 'kind': 'invalid_or_unavailable'}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
