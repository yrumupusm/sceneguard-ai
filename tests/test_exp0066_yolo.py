"""CPU-only contracts: native coordinates, RGB/BGR selection, empty/person-only outputs."""
import copy
from types import SimpleNamespace as NS
import unittest
import numpy as np
import torch
from scripts import exp0066_yolo as y
from orchestration import model_comparison_command as command


def spec():
    return dict(model_id='yolo26m',checkpoint_path='/weights/model.pt',
        bindings={'/weights/model.pt':y.WEIGHTS['yolo26m']},predict_kwargs=copy.deepcopy(y.PREDICT),
        resolution=640,input_frame_index=8,report_person_threshold=.5,ultralytics_version='8.4.192')


def result(boxes=((10,20,80,50),), scores=(.7,), labels=(0,)):
    return NS(orig_shape=(60,100),speed={'inference':1.0},boxes=NS(
        xyxy=torch.tensor(boxes,dtype=torch.float32).reshape(-1,4),
        conf=torch.tensor(scores,dtype=torch.float32),cls=torch.tensor(labels,dtype=torch.float32)))


class YoloTests(unittest.TestCase):
    def test_exact_center_frame_rgb_conversion_and_original_coordinates(self):
        frames=np.zeros((16,60,100,3),dtype=np.uint8)
        frames[8,...]=[12,34,56]
        calls=[]
        def predict(**kw):
            calls.append(kw)
            return [result()]
        model=NS(predict=predict,predictor=NS(model=NS(end2end=True,fp16=False)))
        row=y.infer_clip(model,frames,spec())
        np.testing.assert_array_equal(calls[0]['source'][0,0],[56,34,12])
        self.assertTrue(calls[0]['source'].flags.c_contiguous)
        self.assertEqual(row['boxes'],[[10,20,80,50]])
        self.assertEqual(row['actual_input_frames'],1)
        self.assertIsNone(row['action_scores'])
        self.assertFalse(row['fcos_gating'])

    def test_empty_is_valid_but_invalid_and_nonperson_rows_rejected(self):
        self.assertEqual(y.result_rows(result((),(),()),60,100)['boxes'],[])
        for r in [result(labels=(1,)),result(scores=(float('nan'),)),
                  result(boxes=((0,0,101,50),)),result(scores=(.01,))]:
            with self.assertRaises(ValueError):y.result_rows(r,60,100)
        r=result();r.orig_shape=(100,60)
        with self.assertRaises(ValueError):y.result_rows(r,60,100)

    def test_changed_threshold_time_weights_and_branch_rejected(self):
        original=spec();y.validate_spec(original)
        for k,v in [('input_frame_index',7),('report_person_threshold',.4),('model_id','yolo26n')]:
            with self.assertRaises(ValueError):y.validate_spec({**original,k:v})
        altered=copy.deepcopy(original);altered['predict_kwargs']['conf']=.01
        with self.assertRaises(ValueError):y.validate_spec(altered)
        altered=copy.deepcopy(original);altered['bindings']['/weights/model.pt']='x'*64
        with self.assertRaises(ValueError):y.validate_spec(altered)
        frames=np.zeros((16,60,100,3),dtype=np.uint8)
        model=NS(predict=lambda **kw:[result()],predictor=NS(model=NS(end2end=False,fp16=False)))
        with self.assertRaises(ValueError):y.infer_clip(model,frames,original)

    def test_only_new_models_use_existing_ultralytics_environment(self):
        for m in y.WEIGHTS:
            self.assertIn(m,command.MODEL_IDS)
            self.assertEqual(command.interpreter({'model_id':m}).parent.parent.name,'.venv-pose-batch03')
        self.assertEqual(command.interpreter({'model_id':'evad_vitl'}).parent.parent.name,'.venv-exp0066-joint')


if __name__=='__main__':unittest.main()
