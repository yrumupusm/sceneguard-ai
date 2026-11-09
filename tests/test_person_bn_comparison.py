"""CPU preparation tests. No optimizer is instantiated and no optimizer step runs."""
import copy
import json
from pathlib import Path
import tempfile
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import torch

from scripts import prepare_person_bn_comparison as prep
from orchestration import person_bn_comparison_command as command


class PersonBNComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)

    def model(self):
        torch.manual_seed(68)
        return torch.nn.Sequential(torch.nn.Conv2d(3, 4, 1), torch.nn.BatchNorm2d(4),
                                   torch.nn.SiLU(), torch.nn.Conv2d(4, 2, 1))

    def manifest(self, directory):
        import cv2
        import numpy as np
        frames = []
        for i, split in enumerate(('train', 'train', 'development')):
            image = directory / ('%s.png' % i)
            cv2.imwrite(str(image), np.full((12, 16, 3), i * 30, dtype=np.uint8))
            frames.append(dict(frame_id='frame-%s' % i, split=split, image=image.name,
                               image_sha256=prep.sha(image), source_size=[16, 12], source_pts=i / 30,
                               source_sha256=prep.digest(split), person_completeness_verified=True,
                               confirmed_person_boxes=[dict(id='person-0', xyxy=[1, 1, 10, 11])],
                               event_group=split + '-event', capture_reservation=split + '-capture'))
        value = dict(person_boxes_human_verified=True, protected_school_or_test_used=False, frames=frames)
        path = directory / 'manifest.json'
        path.write_text(json.dumps(value), encoding='utf-8')
        return path, value

    def rewrite(self, path, value):
        path.write_text(json.dumps(value), encoding='utf-8')

    def test_C_freezes_only_BN_buffers_after_repeated_train_resets_and_affine_has_gradients(self):
        model = self.model()
        baseline = prep.bn_snapshot(model)
        original = copy.deepcopy(model.state_dict())
        for i in range(3):
            model.train()
            self.assertTrue(model[1].training)
            self.assertEqual(prep.set_training_mode(model, 'C'), 1)
            self.assertFalse(model[1].training)
            self.assertTrue(model[0].training)
            output = model(torch.full((2, 3, 8, 8), float(i + 1)))
            output.square().mean().backward()
            prep.assert_bn_fixed(model, baseline)
        self.assertIsNotNone(model[1].weight.grad)
        self.assertIsNotNone(model[1].bias.grad)
        self.assertGreater(model[1].weight.grad.abs().sum().item(), 0)
        self.assertGreater(model[1].bias.grad.abs().sum().item(), 0)
        self.assertTrue(all(p.requires_grad for p in model.parameters()))
        self.assertTrue(all(torch.equal(value, model.state_dict()[key]) for key, value in original.items()))

    def test_B_updates_running_statistics_and_counters_without_changing_weights(self):
        model = self.model()
        before = prep.bn_snapshot(model)
        weights = {k: v.detach().clone() for k, v in model.named_parameters()}
        for _ in range(3):
            prep.set_training_mode(model, 'B')
            with torch.no_grad():
                model(torch.ones(2, 3, 8, 8))
        after = prep.bn_snapshot(model)
        self.assertEqual(after['1.num_batches_tracked'].item(), 3)
        self.assertFalse(torch.equal(before['1.running_mean'], after['1.running_mean']))
        self.assertFalse(torch.equal(before['1.running_var'], after['1.running_var']))
        self.assertTrue(all(torch.equal(value, dict(model.named_parameters())[key]) for key, value in weights.items()))

    def test_B_and_C_initial_state_and_trainable_parameter_set_identical(self):
        a = self.model()
        b, c = copy.deepcopy(a), copy.deepcopy(a)
        prep.set_training_mode(b, 'B')
        prep.set_training_mode(c, 'C')
        self.assertEqual(prep.state_hashes(b), prep.state_hashes(c))
        self.assertEqual([n for n, p in b.named_parameters() if p.requires_grad],
                         [n for n, p in c.named_parameters() if p.requires_grad])

    def test_buffer_drift_untracked_BN_and_invalid_variant_rejected(self):
        model = self.model()
        before = prep.bn_snapshot(model)
        model[1].num_batches_tracked.add_(1)
        with self.assertRaises(ValueError):
            prep.assert_bn_fixed(model, before)
        with self.assertRaises(ValueError):
            prep.set_training_mode(model, 'A')
        with self.assertRaises(ValueError):
            prep.set_training_mode(torch.nn.BatchNorm2d(3, track_running_stats=False), 'C')

    def test_orders_use_every_frame_and_partial_batch_reproducibly(self):
        ids = ['f%s' % i for i in range(123)]
        orders = prep.epoch_orders(ids)
        self.assertEqual(orders, prep.epoch_orders(ids))
        self.assertEqual(len(orders), 5)
        for order in orders:
            self.assertEqual(sorted(order['frame_ids']), sorted(ids))
            self.assertEqual(sum(order['batches'], []), order['frame_ids'])
            self.assertEqual(len(order['batches']), 62)
            self.assertEqual(len(order['batches'][-1]), 1)
        self.assertNotEqual(orders[0]['frame_ids'], orders[1]['frame_ids'])

    def test_gain_schedule_matches_pinned_historical_criterion_update(self):
        from ultralytics.utils.loss import E2ELoss
        class FakeLoss:
            def __init__(self, model, **kwargs):
                self.hyp = SimpleNamespace(epochs=5)
        criterion = E2ELoss(None, loss_fn=FakeLoss)
        for i, order in enumerate(prep.epoch_orders(['a', 'b'])):
            self.assertAlmostEqual(order['o2m_gain'], criterion.o2m)
            if i < 4:
                criterion.update()
        self.assertEqual(criterion.updates, 4)
        self.assertAlmostEqual(criterion.o2m, .1)

    def test_dataset_contract_supports_revisions_and_relative_or_absolute_images(self):
        with tempfile.TemporaryDirectory() as temp:
            path, value = self.manifest(Path(temp))
            value['frames'][0]['image'] = str(Path(temp) / value['frames'][0]['image'])
            self.rewrite(path, value)
            result = prep.dataset_contract(path)
            self.assertEqual(result['counts'], dict(train=2, development=1))
            self.assertEqual(result['box_counts'], dict(train=2, development=1))
            self.assertEqual(result['manifest']['sha256'], prep.sha(path))
            with self.assertRaises(ValueError):
                prep.dataset_contract(path, dict(train=122, development=75))

    def test_dataset_rejects_pixel_hash_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            path, value = self.manifest(Path(temp))
            (path.parent / value['frames'][0]['image']).write_bytes(b'changed')
            with self.assertRaises(ValueError):
                prep.dataset_contract(path)

    def test_dataset_rejects_missing_false_completeness_and_missing_invalid_source_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            path, baseline = self.manifest(Path(temp))
            for key, replacement in (('person_completeness_verified', None),
                                     ('person_completeness_verified', False),
                                     ('source_sha256', None), ('source_sha256', ''),
                                     ('source_sha256', 'invalid'), ('source_sha256', 123)):
                value = copy.deepcopy(baseline)
                if replacement is None:
                    value['frames'][0].pop(key)
                else:
                    value['frames'][0][key] = replacement
                self.rewrite(path, value)
                with self.assertRaises(ValueError, msg=str((key, replacement))):
                    prep.dataset_contract(path)

    def test_dataset_rejects_shared_source_even_with_distinct_event_and_capture_labels(self):
        with tempfile.TemporaryDirectory() as temp:
            path, value = self.manifest(Path(temp))
            value['frames'][2]['source_sha256'] = value['frames'][0]['source_sha256']
            self.rewrite(path, value)
            with self.assertRaisesRegex(ValueError, 'Source/event/capture'):
                prep.dataset_contract(path)

    def test_dataset_rejects_cross_split_event_capture_and_duplicate_pixels(self):
        with tempfile.TemporaryDirectory() as temp:
            path, baseline = self.manifest(Path(temp))
            for key in ('event_group', 'capture_reservation', 'pixels'):
                value = copy.deepcopy(baseline)
                if key == 'pixels':
                    for name in ('image', 'image_sha256'):
                        value['frames'][2][name] = value['frames'][0][name]
                else:
                    value['frames'][2][key] = value['frames'][0][key]
                self.rewrite(path, value)
                with self.assertRaises(ValueError, msg=key):
                    prep.dataset_contract(path)

    def test_dataset_rejects_duplicate_frame_GT_invalid_boxes_and_unconfirmed_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            path, baseline = self.manifest(Path(temp))
            cases = []
            value = copy.deepcopy(baseline)
            value['frames'][1]['frame_id'] = value['frames'][0]['frame_id']
            cases.append(value)
            value = copy.deepcopy(baseline)
            value['frames'][0]['confirmed_person_boxes'] *= 2
            cases.append(value)
            for box in ([0, 0, float('nan'), 2], [0, 0, 17, 12], [2, 2, 1, 1]):
                value = copy.deepcopy(baseline)
                value['frames'][0]['confirmed_person_boxes'][0]['xyxy'] = box
                cases.append(value)
            value = copy.deepcopy(baseline)
            value['protected_school_or_test_used'] = True
            cases.append(value)
            value = copy.deepcopy(baseline)
            value['person_boxes_human_verified'] = False
            cases.append(value)
            for value in cases:
                self.rewrite(path, value)
                with self.assertRaises(ValueError):
                    prep.dataset_contract(path)

    def test_plan_binds_same_initialization_orders_settings_and_all_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            path, _ = self.manifest(Path(temp))
            plan = prep.make_plan(path)
            self.assertEqual(plan['initialization']['sha256'], prep.INITIAL_SHA)
            self.assertEqual(plan['expected_optimizer_steps'], 5)
            self.assertEqual(plan['settings_sha256'], prep.digest(prep.SETTINGS))
            self.assertFalse(plan['execution_authorized'])
            self.assertEqual(plan['optimizer_steps_executed'], 0)
            self.assertEqual(plan['dataset']['counts'], dict(train=2, development=1))
            self.assertEqual(plan['variants']['C']['bn_affine'], 'trainable')
            last = path.parent / 'last.pt'
            last.write_bytes(b'not allowed')
            with self.assertRaises(ValueError):
                prep.make_plan(path, last)

    def test_five_atomic_checkpoint_simulations_are_explicitly_untrained_and_reloadable(self):
        model = self.model()
        initial = prep.state_hashes(model)
        provenance = dict(manifest_sha256='synthetic-manifest', settings_sha256=prep.digest(prep.SETTINGS),
                          evidence='synthetic fixture; no training')
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            for epoch in range(1, 6):
                path = folder / ('epoch-%02d.pt' % epoch)
                receipt = prep.save_epoch_checkpoint(path, model, dict(state={}, param_groups=[]),
                                                     epoch, 0, provenance, synthetic=True)
                value = torch.load(path, map_location='cpu', weights_only=False)
                self.assertEqual(value['evidence_kind'], 'synthetic_checkpoint_simulation')
                self.assertEqual(value['optimizer_steps'], 0)
                self.assertEqual(value['tensor_sha256'], initial)
                self.assertEqual(value['provenance'], provenance)
                self.assertEqual(receipt['checkpoint']['sha256'], prep.sha(path))
                self.assertEqual(prep.read(str(path) + '.json'), receipt)
            self.assertEqual(len(list(folder.glob('*.pt'))), 5)
            self.assertFalse(list(folder.glob('*.tmp')))
            with self.assertRaises(FileExistsError):
                prep.save_epoch_checkpoint(path, model, {}, 5, 0, provenance, synthetic=True)

    def test_atomic_writer_failure_never_publishes_partial_file(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'checkpoint.pt'
            def fail(stream):
                stream.write(b'partial')
                raise RuntimeError('simulated interruption')
            with self.assertRaises(RuntimeError):
                prep.atomic_write(path, fail)
            self.assertEqual(list(path.parent.iterdir()), [])

    def test_nonfinite_checkpoint_rejected(self):
        model = self.model()
        with torch.no_grad():
            model[1].running_var.fill_(float('inf'))
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                prep.save_epoch_checkpoint(Path(temp) / 'epoch.pt', model, {}, 1, 0, {}, synthetic=True)

    def test_pairing_stable_GT_recovery_new_miss_and_FP_by_event(self):
        frame = dict(frame_id='dev', split='development', source_pts=1., source_size=[100, 100],
                     image_sha256='pixels', event_group='event', confirmed_person_boxes=[
                         dict(id='one', xyxy=[0, 0, 20, 20]), dict(id='two', xyxy=[30, 0, 50, 20])])
        def prediction(boxes):
            return [dict(frame_id='dev', source_pts=1., image_sha256='pixels',
                         boxes=boxes, person_scores=[.9] * len(boxes))]
        predictions = dict(A=prediction([[0, 0, 20, 20]]),
                           B=prediction([[30, 0, 50, 20], [70, 70, 90, 90]]),
                           C=prediction([[0, 0, 20, 20], [30, 0, 50, 20]]))
        result = prep.compare_predictions(dict(frames=[frame]), predictions)
        self.assertEqual(result['paired_gt_counts']['B'], dict(new_miss=1, recovered=1))
        self.assertEqual(result['paired_gt_counts']['C'], dict(retained=1, recovered=1))
        self.assertEqual(result['event_counts']['event']['B']['fp'], 1)
        self.assertEqual(result['frames'][0]['paired_gt'][0]['gt_id'], 'one')
        predictions['C'][0]['image_sha256'] = 'different'
        with self.assertRaises(ValueError):
            prep.compare_predictions(dict(frames=[frame]), predictions)

    def test_queue_prepare_is_read_only_and_release_missing_fails_before_optimizer(self):
        with tempfile.TemporaryDirectory() as temp:
            path, _ = self.manifest(Path(temp))
            plan_path = Path(temp) / 'plan.json'
            prep.write_json(plan_path, prep.make_plan(path))
            context = dict(run_id='future-run', task_id='future-task', dispatch_id='future-dispatch', owner='future-terminal')
            with patch('orchestration.queue.Queue.enqueue', side_effect=AssertionError('must not enqueue')):
                envelope = command.prepare(plan_path, 'B', context, None)
            self.assertEqual(envelope['status'], 'prepared_not_submitted')
            self.assertFalse(envelope['queue_mutated'])
            with patch('torch.optim.AdamW', side_effect=AssertionError('must not instantiate optimizer')):
                with self.assertRaises((ValueError, TypeError)):
                    command.validate(envelope['config'], envelope['input_value'], command.RUNTIME)
                with self.assertRaises(ValueError):
                    prep.execute_future(SimpleNamespace(queue_attempt='invalid', queue_config='missing',
                                                         queue_config_sha256='missing', output=Path(temp) / 'train'))
            self.assertFalse((Path(temp) / 'train').exists())

    def test_queue_contract_rejects_wrong_stage_runtime_scope_and_retry(self):
        with self.assertRaises(ValueError):
            command.input_contract(dict(experiment_id='EXP-0068', model_id='yolo26m', stage='B', variant='B'))
        with self.assertRaises(ValueError):
            command.output_path('A', 'a' * 32)
        with self.assertRaises(ValueError):
            command.output_path('B', 'bad')
        with self.assertRaises(ValueError):
            command.retry_guard(None, None)
        self.assertEqual(command.output_path('C', 'a' * 32), command.OUTPUT / 'C' / ('a' * 32))

    def test_temp_queue_migration_preserves_old_rows_and_all_existing_command_names(self):
        from orchestration.queue import Queue
        with tempfile.TemporaryDirectory() as temp:
            queue = Queue.initialize(Path(temp).resolve())
            queue.enqueue(job_key='old-mock', run_id='r', task_id='t', dispatch_id='d', owner='o')
            queue.migrate_commands(include_person_detector_train=True)
            before = queue.status()
            with queue.connection() as db:
                old_sql = db.execute("SELECT sql FROM sqlite_master WHERE name='jobs'").fetchone()[0]
            queue.migrate_commands(include_person_bn_comparison_train=True)
            self.assertEqual(before, queue.status())
            with queue.connection() as db:
                sql = db.execute("SELECT sql FROM sqlite_master WHERE name='jobs'").fetchone()[0]
                self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
            import re
            self.assertEqual(set(re.findall("'([^']+)'", sql)),
                             set(re.findall("'([^']+)'", old_sql)) | {'person-bn-comparison-train'})
            backups = list(Path(temp).glob('queue-before-person-bn-comparison-train-*.sqlite3'))
            self.assertEqual(len(backups), 1)
            queue.migrate_commands(include_person_bn_comparison_train=True)
            self.assertEqual(len(list(Path(temp).glob('queue-before-person-bn-comparison-train-*.sqlite3'))), 1)

    def test_temp_queue_routes_new_command_child_without_training_and_missing_result_fails(self):
        from orchestration.queue import Queue, digest, source_hash
        with tempfile.TemporaryDirectory() as temp:
            queue = Queue.initialize(Path(temp).resolve())
            context = dict(run_id='r', task_id='t', dispatch_id='d', owner='o')
            config = dict(stage='B', variant='B', context=context, plan=dict(sha256='synthetic-plan'))
            # Only a throwaway queue and inert exit-zero child exercise dispatch/finish.
            with patch.object(command, 'validate', return_value={}):
                job = queue.enqueue(job_key=command.job_key(config), command='person-bn-comparison-train',
                                    input_value=dict(synthetic=True), config=config, **context)
            self.assertEqual(source_hash('person-bn-comparison-train', config), digest(command.sources()))
            with patch.object(command, 'command', return_value=[sys.executable, '-I', '-c', 'raise SystemExit(0)']), \
                    patch.object(command, 'OUTPUT', Path(temp) / 'outputs'):
                result = queue.supervise_once(job['job_id'])
            self.assertEqual(result['status'], 'failed')
            attempt = queue.status()['attempts'][0]
            self.assertIn('Invalid BN comparison result', attempt['reason'])
            with self.assertRaisesRegex(ValueError, 'retry is forbidden'):
                queue.retry(job['job_id'])

    def test_new_command_unreleased_enqueue_does_not_migrate_or_change_temp_queue(self):
        from orchestration.queue import Queue
        with tempfile.TemporaryDirectory() as temp:
            queue = Queue.initialize(Path(temp).resolve())
            before = queue.status()
            with self.assertRaises(ValueError):
                queue.enqueue(job_key='unreleased', command='person-bn-comparison-train',
                              config={}, input_value={}, run_id='r', task_id='t', dispatch_id='d', owner='o')
            self.assertEqual(before, queue.status())
            with queue.connection() as db:
                self.assertNotIn('person-bn-comparison-train', db.execute(
                    "SELECT sql FROM sqlite_master WHERE name='jobs'").fetchone()[0])

    def test_result_validator_rejects_synthetic_checkpoint_receipts(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'result.json'
            result = dict(status='actual_exp0074_training_complete', variant='B', optimizer_steps=5,
                          epochs=[dict(evidence_kind='synthetic_checkpoint_simulation')] * 5)
            prep.write_json(path, result)
            with patch.object(command, 'input_contract', return_value=dict(expected_optimizer_steps=5,
                    epoch_orders=[dict(batches=[['f']])] * 5)):
                with self.assertRaisesRegex(ValueError, 'synthetic'):
                    command.verify_result(dict(variant='B'), path)


if __name__ == '__main__':
    unittest.main()
