"""Synthetic CPU adapter contract tests: no real ReID or original CCTV used."""
import tempfile
import unittest
from pathlib import Path

import numpy as np


from sceneguard import run_exp0031_quality as runner


class RunnerAdapterContract(unittest.TestCase):
    runner = runner

    def test_reuse_only_does_not_create_model_or_crop_directory(self):
        row=dict(frame_index=0,cache_index=0,bbox=[0.1,0.1,0.2,0.3])
        selected={'t1':{'head':[row],'tail':[row]}}
        old={(0,0):np.eye(512)[0]}
        def fail(*args):raise AssertionError('Unnecessary decoder/encoder used')
        with tempfile.TemporaryDirectory() as t:
            feats,stats=self.runner.encode_alternatives('video',[dict(source_size=[20,20])],selected,old,
                     weights='unused',interval=.1,review_dir=Path(t)/'crops',
                     encoder_factory=fail,decoder=fail)
            self.assertEqual(feats['t1']['head'],feats['t1']['tail'])
            self.assertEqual(stats['distinct_new_crops'],0)
            self.assertEqual(stats['encoder_calls'],0)
            self.assertFalse((Path(t)/'crops').exists())

    def test_new_crop_decoded_once_and_encoded_only_if_needed(self):
        row=dict(frame_index=0,cache_index=1,bbox=[.1,.1,.7,.9])
        selected={'t1':{'head':[row],'tail':[row]}}
        source=[dict(source_size=[32,32])]
        calls=[]
        class Fake:
            def __call__(self,bgr,xywh):
                calls.append(xywh.copy())
                self_test.assertEqual(xywh.shape,(1,4))
                return [np.ones(512)]
        self_test=self
        def encoder(*args):return Fake()
        def decode(*args):return [(0,np.full((32,32,3),128,np.uint8))]
        with tempfile.TemporaryDirectory() as t:
            feats,stats=self.runner.encode_alternatives('video',source,selected,{},
                weights='unused',interval=.1,review_dir=Path(t)/'crops',
                encoder_factory=encoder,decoder=decode)
            self.assertEqual(stats['distinct_new_crops'],1)
            self.assertEqual(stats['encoder_calls'],1)
            self.assertEqual(len(calls),1)
            self.assertAlmostEqual(np.linalg.norm(feats['t1']['head'][0]),1)
            self.assertEqual(len(list((Path(t)/'crops').glob('*.jpg'))),1)

    def test_missing_decode_must_fail_not_silently_fallback(self):
        row=dict(frame_index=5,cache_index=1,bbox=[.1,.1,.7,.9])
        selected={'t1':{'head':[row],'tail':[row]}}
        class Fake:
            def __call__(self,*args):return [np.ones(512)]
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaisesRegex(ValueError,'Not all required'):
                self.runner.encode_alternatives('video',[dict(source_size=[32,32])],selected,{},
                    weights='unused',interval=.1,review_dir=Path(t)/'crops',
                    encoder_factory=lambda *args: Fake(),decoder=lambda *args: [])

    def test_q_comparison_keeps_original_gates_without_accepted_claim(self):
        segs=[dict(id=i,raw_id=n,end=2,start=0) for i,n in
              [('t0001',1),('t0007',9),('t0008',11),('t0002',2),('t0004',4)]]
        for s in segs:
            if s['id'] not in ('t0001','t0002'):
                s['start']=3
        feats={s['id']:{'head':[[1,0]],'tail':[[1,0]]} for s in segs}
        old=dict(links=[dict(before='t0001',after='t0007',status='rejected')])
        new=dict(links=[dict(before='t0001',after='t0007',status='accepted')])
        audit=self.runner.question_comparison('030',segs,feats,feats,old,new)
        self.assertEqual(audit[0]['baseline_status'],'rejected')
        self.assertEqual(audit[0]['alternate_status'],'accepted')
        self.assertFalse(audit[0]['adopted'])
        self.assertFalse(audit[0]['identity_verified'])

if __name__=='__main__':unittest.main()
