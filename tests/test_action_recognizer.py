"""Leakage, label-boundary and real PTS preprocessing checks, without GPU."""
import copy
import importlib.util
import json
from unittest.mock import patch
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('trainer', Path(__file__).parents[1]/'scripts/train_action_recognizer.py')
trainer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(trainer)


def fixture():
    rows=[]
    for split in ['train','validation','test']:
        for label in [0,1]:
            key=f'{split}-{label}'
            rows.append(dict(clip_id=key, source_id=key, source_path=f'/tmp/{key}.mp4',
                source_sha256=key, event_group=key, split=split, label=label,
                actor_id=0, location='place-'+split, sample_pts=[i/3 for i in range(16)],
                roi_xyxy=[0,0,32,24], verified_action_interval=[0,5],
                label_evidence='fixture-only', negative_basis='explicit_action_annotation',
                temporal_alignment='annotation_interior_both_origins',box_alignment='official_annotations_sampled_alignment_review'))
    return dict(review_status='sampled_alignment_review_complete',review_evidence='fixture-only',
                label_policy='official_actor_action_intervals_sampled_alignment_review',clips=rows,
                held_out_test_locations=['place-test'])


BASELINE=dict(status='verified',baseline_experiment='EXP-0062',regression_only_videos=[dict(path='/tmp/regression.mp4',sha256='forbidden')])


class ActionContracts(unittest.TestCase):
    def test_good_fixture(self):
        self.assertEqual(len(trainer.validate_manifest(fixture(),BASELINE)),6)
        data=fixture()
        for row in data['clips']:row['sample_pts']=row['sample_pts'][:8]
        self.assertEqual(len(trainer.validate_manifest(data,BASELINE,frames=8)),6)

    def test_cross_camera_event_leakage(self):
        data=fixture();data['clips'][2]['event_group']=data['clips'][0]['event_group']
        with self.assertRaisesRegex(ValueError,'leakage'):trainer.validate_manifest(data,BASELINE)

    def test_frozen_split_cannot_be_reassigned(self):
        data=fixture()
        source_split={'held_out_test_locations':data['held_out_test_locations'],'assignments':[dict(source_id=r['source_id'],source_sha256=r['source_sha256'],
            group_id=r['event_group'],split=r['split'],location=r['location'],excluded=False) for r in data['clips']]}
        trainer.validate_manifest(data,BASELINE,source_split=source_split)
        source_split['assignments'][0]['split']='test'
        with self.assertRaisesRegex(ValueError,'frozen'):trainer.validate_manifest(data,BASELINE,source_split=source_split)

    def test_duplicate_content_under_new_name(self):
        data=fixture();data['clips'][2]['source_sha256']=data['clips'][0]['source_sha256']
        with self.assertRaisesRegex(ValueError,'leakage'):trainer.validate_manifest(data,BASELINE)

    def test_regression_renamed(self):
        data=fixture();data['clips'][0]['source_sha256']='forbidden'
        with self.assertRaisesRegex(ValueError,'Regression'):trainer.validate_manifest(data,BASELINE)

    def test_unlabeled_region_is_not_negative(self):
        data=fixture();data['clips'][0]['negative_basis']='no_annotation'
        with self.assertRaisesRegex(ValueError,'negative'):trainer.validate_manifest(data,BASELINE)

    def test_no_whole_video_positive(self):
        data=fixture();data['clips'][1]['verified_action_interval']=[2,4]
        with self.assertRaisesRegex(ValueError,'beyond'):trainer.validate_manifest(data,BASELINE)

    def test_invalid_action_intervals(self):
        for interval in [[float('nan'),float('nan')],[0,float('inf')],[5,1],[-1,5]]:
            data=fixture();data['clips'][1]['verified_action_interval']=interval
            with self.assertRaisesRegex(ValueError,'interval'):trainer.validate_manifest(data,BASELINE)

    def test_conflicting_path_hash_does_not_evade_verification(self):
        data=fixture();data['clips'][2]['source_path']=data['clips'][0]['source_path']
        with self.assertRaisesRegex(ValueError,'Contradictory'):trainer.validate_manifest(data,BASELINE)

    def test_no_padding(self):
        data=fixture();data['clips'][1]['sample_pts']=[0.]*16
        with self.assertRaisesRegex(ValueError,'consecutive'):trainer.validate_manifest(data,BASELINE)

    def test_missing_review(self):
        data=fixture();data['review_status']='pending'
        with self.assertRaisesRegex(ValueError,'review'):trainer.validate_manifest(data,BASELINE)

    def test_missing_negative_in_validation(self):
        data=fixture();data['clips']=[r for r in data['clips'] if not (r['split']=='validation' and r['label']==0)]
        with self.assertRaisesRegex(ValueError,'both'):trainer.validate_manifest(data,BASELINE)

    def test_exclusions_and_places(self):
        for number in [19,35,69,70]:
            data=fixture();data['clips'][0].update(scenario_family=4,scenario_number=number)
            with self.assertRaisesRegex(ValueError,'excluded'):trainer.validate_manifest(data,BASELINE)
        data=fixture();data['clips'][0]['location']='place-test'
        with self.assertRaisesRegex(ValueError,'location'):trainer.validate_manifest(data,BASELINE)

    def test_positive_only_precision_unmeasured(self):
        result=trainer.metrics([dict(label=1,score=.9),dict(label=1,score=.1)])
        self.assertIsNone(result['precision']); self.assertIsNone(result['f1'])
        self.assertEqual(result['recall'],.5)

    def test_nonfinite_score_cannot_silently_disappear_from_confusion_counts(self):
        with self.assertRaisesRegex(ValueError,'Nonfinite'):trainer.metrics([dict(label=1,score=float('nan'))])

    def test_native_video_decode_and_pts_failure(self):
        import av
        import numpy as np
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'fixture.mp4'
            with av.open(str(path),'w') as container:
                stream=container.add_stream('libx264',rate=3)
                stream.width=32;stream.height=24;stream.pix_fmt='yuv420p'
                for i in range(18):
                    frame=av.VideoFrame.from_ndarray(np.full((24,32,3),i*10,dtype=np.uint8),format='rgb24')
                    for packet in stream.encode(frame):container.mux(packet)
                for packet in stream.encode():container.mux(packet)
            row=copy.deepcopy(fixture()['clips'][0]);row['source_path']=str(path)
            arr=trainer.decode_clip(row,112)
            self.assertEqual(arr.shape,(16,112,112,3))
            self.assertGreater(arr[-1].mean(),arr[0].mean())
            row['sample_pts'][0]=.01
            with self.assertRaisesRegex(ValueError,'PTS'):trainer.decode_clip(row,112)



class ReleaseAndSmokeTests(unittest.TestCase):
    def release_fixture(self, folder):
        manifest, split, snapshot, release, policy = [Path(folder)/name for name in ('manifest.json','split.json','answers.json','release.json','policy.md')]
        manifest.write_text('{}');split.write_text('{}');policy.write_text('official reference; sampled human alignment only')
        requests = [dict(id='request-'+str(i),version=4,answer_version=1,experiment_id='EXP-0063',
                         answer='small difference',source_binding_sha256='binding-'+str(i)) for i in range(8)]
        trainer.save(snapshot,dict(requests=requests))
        data=dict(schema_version=1,experiment_id='EXP-0063',manifest_sha256=trainer.sha(manifest),
                  split_manifest_sha256=trainer.sha(split),review_snapshot=dict(path=str(snapshot),sha256=trainer.sha(snapshot)),
                  interpretation_policy=dict(path=str(policy),sha256=trainer.sha(policy)),
                  reviews=[dict(request_id=r['id'],version=r['version'],answer_version=r['answer_version']) for r in requests])
        trainer.save(manifest,dict(review_evidence=dict(review_snapshot=data['review_snapshot'],
            review_policy=data['interpretation_policy'],reviews=data['reviews'])))
        data['manifest_sha256']=trainer.sha(manifest)
        trainer.save(release,data)
        return manifest,split,snapshot,release,data

    def test_release_rejects_wrong_hash_or_manifest_or_split(self):
        with tempfile.TemporaryDirectory() as t:
            manifest,split,snapshot,release,data=self.release_fixture(t)
            trainer.validate_release(manifest,split,release,trainer.sha(release))
            with self.assertRaisesRegex(ValueError,'hash'):
                trainer.validate_release(manifest,split,release,'0'*64)
            manifest.write_text('{"changed":true}')
            with self.assertRaisesRegex(ValueError,'binding'):
                trainer.validate_release(manifest,split,release,trainer.sha(release))

    def test_release_requires_all_exact_versions_and_immutable_answers(self):
        with tempfile.TemporaryDirectory() as t:
            manifest,split,snapshot,release,data=self.release_fixture(t)
            data['reviews'][0]['version']=2;trainer.save(release,data)
            with self.assertRaisesRegex(ValueError,'provenance|exact'):
                trainer.validate_release(manifest,split,release,trainer.sha(release))
            snapshot.write_text('{}')
            with self.assertRaisesRegex(ValueError,'snapshot'):
                trainer.validate_release(manifest,split,release,trainer.sha(release))

    def test_truthy_review_evidence_cannot_replace_alignment_policy(self):
        data=fixture();data['review_status']='approved';data['review_evidence']='yes'
        with self.assertRaisesRegex(ValueError,'review'):trainer.validate_manifest(data,BASELINE)

    def test_smoke_only_selects_real_train_val_and_never_opens_test_array(self):
        data=fixture()
        originals=list(data['clips'])
        for row in originals:
            if row['split'] in ('train','validation'):
                for i in range(15 if row['split']=='train' else 1):
                    added=copy.deepcopy(row);added['clip_id']+='-'+str(i);data['clips'].append(added)
        selected=trainer.partition_rows(data,'smoke')
        self.assertEqual({r['split'] for r in selected},{'train','validation'})
        with tempfile.TemporaryDirectory() as t:
            folder=Path(t);manifest=folder/'manifest.json';config=folder/'config.json'
            trainer.save(manifest,data);trainer.save(config,{})
            entries={}
            for row in data['clips']:
                path=folder/(row['clip_id']+'.npy')
                if row['split']!='test':path.write_bytes(b'pixels')
                entries[row['clip_id']]=dict(path=str(path),sha256=trainer.sha(path) if path.exists() else 'missing-test')
            trainer.save(folder/'prepared.json',dict(manifest_sha256=trainer.sha(manifest),config_sha256=trainer.sha(config),clips=entries))
            self.assertEqual(len(trainer.prepared_entries(folder,manifest,config,selected)),36)
            self.assertEqual(sum(r['split']=='train' for r in selected),32)
            with self.assertRaises(FileNotFoundError):trainer.prepared_entries(folder,manifest,config,data['clips'])

    def test_smoke_rejects_too_few_real_clips_for_full_batch(self):
        with self.assertRaisesRegex(ValueError,'Insufficient'):trainer.partition_rows(fixture(),'smoke')

    def test_place_cohorts_are_separate_and_human_metrics_remain_null(self):
        data=fixture();rows=[r for r in data['clips'] if r['split']=='test']
        rows[0]['location']='seen';rows[1]['location']='heldout'
        scores=[dict(clip_id=r['clip_id'],label=r['label'],score=.9) for r in rows]
        result=trainer.evaluation_report(scores,rows,{'heldout'})
        self.assertEqual(result['same_place']['clips'],1);self.assertEqual(result['heldout_place']['clips'],1)
        self.assertIsNone(result['heldout_place']['annotation_reference']['precision'])
        self.assertIsNone(result['same_place']['annotation_reference']['human_precision'])

    def test_negative_subtype_rates_are_annotation_reference_only(self):
        rows=[dict(clip_id='a',action_class='stand',location='seen',source_id='s1',event_group='g1'),
              dict(clip_id='b',action_class='stand',location='seen',source_id='s2',event_group='g2'),
              dict(clip_id='c',action_class='wall_over',location='held',source_id='s3',event_group='g3')]
        scores=[dict(clip_id='a',label=0,score=.9),dict(clip_id='b',label=0,score=.1),dict(clip_id='c',label=1,score=.9)]
        result=trainer.evaluation_report(scores,rows,{'held'})
        stand=result['same_place']['by_action_class']['stand']
        self.assertEqual((stand['fp'],stand['tn'],stand['false_positive_rate']),(1,1,.5))
        self.assertIsNone(stand['human_precision'])
        self.assertEqual(result['heldout_place']['by_action_class']['wall_over']['recall'],1)

    def test_fixed_first_config_rejects_model_epochs_gate_and_threshold_changes(self):
        config=json.loads((Path(__file__).parents[1]/'configs/exp0063_action_training.json').read_text())
        trainer.validate_config(config)
        for key,value in [('epochs',9),('minimum_gpu_free_mib',6143),('threshold',.6),('frames',16),('batch_size',8)]:
            with self.assertRaises(ValueError):trainer.validate_config({**config,key:value})


class AmpUpdateTests(unittest.TestCase):
    def setup_training(self, growth_interval=100):
        import torch
        model = torch.nn.Linear(2, 1, bias=False)
        with torch.no_grad():
            model.weight.fill_(1.)
        optimizer = torch.optim.AdamW(model.parameters(), lr=.0001, weight_decay=.0001)
        scaler = torch.amp.GradScaler('cpu', init_scale=8., growth_interval=growth_interval)
        counts, handle = trainer.install_actual_step_counter(optimizer)
        self.assertTrue(scaler.is_enabled())
        return model, optimizer, scaler, counts, handle

    def backward(self, model, optimizer, scaler, poison=None):
        import torch
        optimizer.zero_grad(set_to_none=True)
        loss = model(torch.ones(1, 2)).square().sum()
        self.assertTrue(bool(torch.isfinite(loss)))
        scaler.scale(loss).backward()
        if poison is not None:
            model.weight.grad.fill_(poison)
        return loss

    def test_real_cpu_amp_overflow_skips_backoffs_then_updates_twice(self):
        import torch
        model, optimizer, scaler, counts, handle = self.setup_training()
        initial = model.weight.detach().clone()
        self.backward(model, optimizer, scaler, float('inf'))
        skipped = trainer.amp_optimizer_update(optimizer, scaler, counts)
        self.assertFalse(skipped['step_applied'])
        self.assertTrue(skipped['overflow_skipped'])
        self.assertEqual((skipped['scale_before'], skipped['scale_after']), (8., 4.))
        self.assertTrue(torch.equal(initial, model.weight))
        self.assertEqual(len(optimizer.state), 0)
        for _ in range(2):
            self.backward(model, optimizer, scaler)
            applied = trainer.amp_optimizer_update(optimizer, scaler, counts)
            self.assertTrue(applied['step_applied'])
        self.assertEqual(counts, dict(attempted=3, actual=2, skipped=1))
        self.assertEqual(float(optimizer.state[model.weight]['step']), 2.)
        self.assertFalse(torch.equal(initial, model.weight))
        self.assertTrue(trainer.ensure_finite_training_state(model, optimizer)['optimizer_state_finite'])

    def test_nan_skip_preserves_existing_adam_moments_and_checkpoint_counters(self):
        import torch
        model, optimizer, scaler, counts, handle = self.setup_training()
        self.backward(model, optimizer, scaler)
        trainer.amp_optimizer_update(optimizer, scaler, counts)
        old_parameter = model.weight.detach().clone()
        old_state = {k: v.clone() for k, v in optimizer.state[model.weight].items()}
        self.backward(model, optimizer, scaler, float('nan'))
        event = trainer.amp_optimizer_update(optimizer, scaler, counts)
        self.assertTrue(event['overflow_skipped'])
        self.assertTrue(torch.equal(old_parameter, model.weight))
        for key, value in old_state.items():
            self.assertTrue(torch.equal(value, optimizer.state[model.weight][key]))
        self.backward(model, optimizer, scaler)
        trainer.amp_optimizer_update(optimizer, scaler, counts)
        with tempfile.TemporaryDirectory() as folder:
            checkpoint = Path(folder)/'state.pt'
            torch.save(dict(optimizer=optimizer.state_dict(), scaler=scaler.state_dict(), counts=counts), checkpoint)
            saved = torch.load(checkpoint, map_location='cpu', weights_only=False)
        self.assertEqual(saved['counts'], dict(attempted=3, actual=2, skipped=1))
        self.assertEqual({float(s['step']) for s in saved['optimizer']['state'].values()}, {2.})
        self.assertEqual(saved['scaler']['scale'], 4.)

    def test_actual_update_count_survives_scale_growth_and_none_step_return(self):
        model, optimizer, scaler, counts, handle = self.setup_training(growth_interval=1)
        self.backward(model, optimizer, scaler)
        event = trainer.amp_optimizer_update(optimizer, scaler, counts)
        self.assertTrue(event['step_applied'])
        self.assertEqual((event['scale_before'], event['scale_after']), (8., 16.))
        self.assertEqual(counts, dict(attempted=1, actual=1, skipped=0))

    def test_finite_elements_with_overflowing_norm_are_not_corrupted_by_infinite_clip(self):
        import torch
        model, optimizer, scaler, counts, handle = self.setup_training()
        self.backward(model, optimizer, scaler, 8.*3.e19)
        self.assertTrue(bool(torch.isfinite(model.weight.grad).all()))
        unsafe = torch.nn.Parameter(torch.ones(2))
        unsafe.grad = torch.full_like(unsafe, 3.e19)
        self.assertFalse(bool(torch.isfinite(unsafe.grad.norm())))
        torch.nn.utils.clip_grad_norm_([unsafe], float('inf'), error_if_nonfinite=False)
        self.assertTrue(bool(torch.isnan(unsafe.grad).all()))
        event = trainer.amp_optimizer_update(optimizer, scaler, counts)
        self.assertTrue(event['step_applied'])
        self.assertTrue(bool(torch.isfinite(model.weight.grad).all()))
        trainer.ensure_finite_training_state(model, optimizer)

    def test_nonfinite_model_parameters_buffers_and_optimizer_state_reject(self):
        import torch
        for target in ['parameter', 'buffer', 'moment', 'step']:
            with self.subTest(target=target):
                model, optimizer, scaler, counts, handle = self.setup_training()
                self.backward(model, optimizer, scaler)
                trainer.amp_optimizer_update(optimizer, scaler, counts)
                model.register_buffer('audit_buffer', torch.zeros(1))
                with torch.no_grad():
                    if target == 'parameter':
                        model.weight.fill_(float('nan'))
                    elif target == 'buffer':
                        model.audit_buffer.fill_(float('inf'))
                    elif target == 'moment':
                        optimizer.state[model.weight]['exp_avg_sq'].fill_(float('nan'))
                    else:
                        optimizer.state[model.weight]['step'].fill_(float('inf'))
                with self.assertRaisesRegex(ValueError, 'Nonfinite training state'):
                    trainer.ensure_finite_training_state(model, optimizer)

    def test_invalid_scale_and_fused_counter_are_rejected_without_updates(self):
        import torch
        model, optimizer, scaler, counts, handle = self.setup_training()
        self.backward(model, optimizer, scaler)
        before = model.weight.detach().clone()
        with patch.object(scaler, 'get_scale', return_value=0.):
            with self.assertRaisesRegex(ValueError, 'Invalid AMP scale'):
                trainer.amp_optimizer_update(optimizer, scaler, counts)
        self.assertEqual(counts, dict(attempted=0, actual=0, skipped=0))
        self.assertTrue(torch.equal(before, model.weight))
        optimizer.defaults['fused'] = True
        with self.assertRaisesRegex(ValueError, 'non-fused'):
            trainer.install_actual_step_counter(optimizer)

    def test_amp_counterexamples_use_no_cuda_context(self):
        import torch
        initialized_before = torch.cuda.is_initialized()
        model, optimizer, scaler, counts, handle = self.setup_training()
        self.backward(model, optimizer, scaler)
        trainer.amp_optimizer_update(optimizer, scaler, counts)
        self.assertEqual(torch.cuda.is_initialized(), initialized_before)
        self.assertEqual(model.weight.device.type, 'cpu')


if __name__=='__main__':unittest.main()
