"""Leakage, label-boundary and real PTS preprocessing checks, without GPU."""
import copy
import importlib.util
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
                temporal_alignment='reviewed',box_alignment='reviewed'))
    return dict(review_status='approved',review_evidence='fixture-only',
                label_policy='explicit_actor_action_intervals',clips=rows,
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
        source_split={'assignments':[dict(source_id=r['source_id'],source_sha256=r['source_sha256'],
            group_id=r['event_group'],split=r['split'],excluded=False) for r in data['clips']]}
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


if __name__=='__main__':unittest.main()
