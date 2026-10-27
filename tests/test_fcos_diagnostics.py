import json
import tempfile
import unittest
from pathlib import Path

class DiagnosticsTests(unittest.TestCase):
    def test_read_only_stage_attribution(self):
        import numpy as np
        import torch
        from sceneguard.detectors import build_detector
        from sceneguard.fcos_diagnostics import FCOSDiagnostics
        model=build_detector('fcos800')
        logits=torch.full((1,4,91),-20.)
        for i,s in enumerate([.8,.7,.4,.1]):
            logits[0,i,1]=torch.logit(torch.tensor(s*s/.9))
        heads={'cls_logits':[logits],'bbox_ctrness':[torch.full((1,4,1),torch.logit(torch.tensor(.9)))],
               'bbox_regression':[torch.ones(1,4,4)]}
        anchors=[[torch.tensor([[0.,0.,8.,8.],[0.,0.,8.,8.],[30.,0.,38.,8.],[60.,0.,68.,8.]])]]
        with tempfile.TemporaryDirectory() as tmp:
            expected=model.postprocess_detections(heads,anchors,[(100,100)])
            recorder=FCOSDiagnostics(model,tmp,.5);recorder.pts=84.
            actual=model.postprocess_detections(heads,anchors,[(100,100)])
            for k in expected[0]:self.assertTrue(torch.equal(expected[0][k],actual[0][k]))
            data=np.load(Path(tmp)/'candidates_84.000000.npz')
            self.assertEqual(data['stage'].tolist(),[5,2,4,0])
            record=json.loads((Path(tmp)/'diagnostic_stages.jsonl').read_text())
            self.assertEqual(record['suppressions'][0]['candidate_id'],1)
            self.assertEqual(record['suppressions'][0]['suppressor_id'],0)
            self.assertAlmostEqual(record['suppressions'][0]['iou'],1.)
            # Synthetic cap/top-k branch tests, never used by the real experiment.
            model.detections_per_img=1
            recorder.pts=88.
            model.postprocess_detections(heads,anchors,[(100,100)])
            self.assertEqual(np.load(Path(tmp)/'candidates_88.000000.npz')['stage'].tolist(),[5,2,3,0])
            model.topk_candidates=1
            recorder.pts=90.
            model.postprocess_detections(heads,anchors,[(100,100)])
            self.assertEqual(np.load(Path(tmp)/'candidates_90.000000.npz')['stage'].tolist(),[5,1,1,0])
