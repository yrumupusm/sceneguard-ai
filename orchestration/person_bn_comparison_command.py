"""Future EXP74 B/C canonical-queue contract; prepare never submits work."""
import argparse
import os
from pathlib import Path
import re

from scripts import prepare_person_bn_comparison as preparation
from orchestration.action_training_command import resources, validate_assignment

ROOT = preparation.ROOT
RUNTIME = preparation.QUEUE
OUTPUT = preparation.FUTURE_OUTPUT
file_hash = preparation.sha


def interpreter(config=None):
    return ROOT / '.venv-pose-batch03/bin/python'


def sources(config=None):
    return preparation.source_bindings()


def input_contract(config):
    if (config.get('experiment_id') != 'EXP-0074' or config.get('model_id') != 'yolo26m'
            or config.get('stage') not in ('B', 'C') or config.get('variant') != config.get('stage')):
        raise ValueError('Exact EXP74 YOLO26m B/C stage required')
    plan_binding = config['plan']
    preparation.bound(plan_binding['path'], plan_binding['sha256'])
    plan = preparation.read(plan_binding['path'])
    if plan != preparation.make_plan(plan['dataset']['manifest']['path'], plan['initialization']['path']):
        raise ValueError('Exact current plan, dataset, pretrained weights and source bytes required')
    return plan


def validate(config, inputs, runtime):
    if (set(config) != {'experiment_id', 'model_id', 'stage', 'variant', 'context',
                        'execution_revision', 'plan', 'authorization'}
            or Path(runtime).resolve() != RUNTIME
            or config['execution_revision'] != 'person-bn-comparison-v1'
            or set(config['context']) != {'run_id', 'task_id', 'dispatch_id', 'owner'}
            or not all(isinstance(v, str) and v for v in config['context'].values())
            or not interpreter().is_file()):
        raise ValueError('Exact future EXP74 assignment/config/runtime required')
    if input_contract(config) != inputs:
        raise ValueError('Training plan/inputs differ')
    authorization = preparation.validate_release(config, inputs)
    from orchestration.model_comparison_command import environment_contract
    spec = preparation.read(inputs['model_specification']['path'])
    environment_contract({'model_id': 'yolo26m'}, spec)
    assignment = validate_assignment(config['context'])
    return dict(authorization=authorization, live_assignment=assignment)


def job_key(config):
    return 'exp0074-person-bn-' + config['variant'] + '-' + config['plan']['sha256']


def output_path(stage, attempt):
    if stage not in ('B', 'C') or not re.fullmatch('[0-9a-f]{32}', attempt):
        raise ValueError('Exact B/C stage and canonical attempt required')
    return OUTPUT / stage / attempt


def command(config, inputs, runtime, attempt, lock_fd):
    proof = validate(config, inputs, runtime)
    os.fstat(lock_fd)
    resources()
    directory = Path(runtime) / 'attempts' / attempt
    snapshot = directory / 'person-bn-comparison-config.json'
    preparation.write_json(snapshot, config)
    preparation.write_json(directory / 'person-bn-comparison-assignment.json', proof)
    return [str(interpreter()), '-I', str(ROOT / 'scripts/prepare_person_bn_comparison.py'),
            'future-train', '--queue-config', str(snapshot),
            '--queue-config-sha256', file_hash(snapshot), '--queue-attempt', attempt,
            '--output', str(output_path(config['stage'], attempt))]


def runner_guard(args):
    return preparation.future_runner_guard(args)


def retry_guard(db, job):
    raise ValueError('Automatic EXP74 training retry is forbidden; preserve the first failure')


def verify_result(config, path):
    """Queue success requires all five real epoch checkpoint receipts and bytes."""
    path = Path(path)
    result = preparation.read(path)
    plan = input_contract(config)
    if (result.get('status') != 'actual_exp0074_training_complete'
            or result.get('variant') != config['variant']
            or result.get('optimizer_steps') != plan['expected_optimizer_steps']
            or len(result.get('epochs', [])) != 5):
        raise ValueError('Complete actual B/C five-epoch result required')
    steps = 0
    for epoch, receipt in enumerate(result['epochs'], 1):
        steps += len(plan['epoch_orders'][epoch - 1]['batches'])
        checkpoint = path.parent / ('epoch-%02d.pt' % epoch)
        if (receipt.get('evidence_kind') != 'actual_training_checkpoint'
                or receipt.get('epoch') != epoch or receipt.get('optimizer_steps') != steps
                or receipt.get('checkpoint') != preparation.bound(checkpoint)
                or receipt.get('provenance', {}).get('plan') != config['plan']
                or preparation.read(str(checkpoint) + '.json') != receipt):
            raise ValueError('Missing, changed, synthetic or mismatched epoch checkpoint')
    if result.get('selected_checkpoint') != result['epochs'][-1]['checkpoint']:
        raise ValueError('Fixed last epoch5 checkpoint selection required')
    return result


def prepare(plan_path, variant, context, authorization, revision='person-bn-comparison-v1'):
    """Create a reviewable enqueue envelope only; missing release is intentionally allowed here."""
    config = dict(experiment_id='EXP-0074', model_id='yolo26m', stage=variant, variant=variant,
                  context=context, execution_revision=revision,
                  plan=preparation.bound(plan_path), authorization=authorization)
    inputs = input_contract(config)
    from orchestration.queue import digest
    return dict(status='prepared_not_submitted', command='person-bn-comparison-train',
                job_key=job_key(config), config=config, input_value=inputs,
                expected_input_hash=digest(inputs), expected_config_hash=digest(config),
                source_hash=digest(sources()), queue_runtime=str(RUNTIME),
                execution_authorized=False, queue_mutated=False,
                release_requirement='validate() requires reviewed committed sources, new grant and live assignment')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--variant', choices=('B', 'C'), required=True)
    parser.add_argument('--context', type=Path, required=True,
                        help='JSON with actual future run_id/task_id/dispatch_id/owner')
    parser.add_argument('--authorization', type=Path,
                        help='Optional existing release; never created by preparation')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    auth = preparation.bound(args.authorization) if args.authorization else None
    result = prepare(args.plan, args.variant, preparation.read(args.context), auth)
    preparation.write_json(args.output, result)
    print('Prepared future queue envelope; not submitted: ' + str(args.output))


if __name__ == '__main__':
    main()
