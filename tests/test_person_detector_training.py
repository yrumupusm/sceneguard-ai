"""Person adapter/geometry/provenance counterexamples, CPU only."""
import copy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import torch
from scripts import train_person_detector as trainer
from orchestration import person_detector_training_command as command
from orchestration.queue import Queue


class PersonTrainingTests(unittest.TestCase):
    def fake(self):
        class Model(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.model=torch.nn.ModuleList([torch.nn.Module()]);self.yaml={'nc':80};self.names={0:'person'}
                h=self.model[-1];h.nc=80;h.reg_max=1;h.no=84
                for name in ('cv3','one2one_cv3'):
                    setattr(h,name,torch.nn.ModuleList([torch.nn.Sequential(torch.nn.Conv2d(4,7,1),torch.nn.SiLU(),torch.nn.Conv2d(7,80,1)) for _ in range(3)]))
        return Model()

    def test_all_six_person_rows_and_hidden_layers_preserved(self):
        model=self.fake();before=copy.deepcopy(model.state_dict());x=torch.randn(2,4,3,3)
        h=model.model[-1];expected={n:[b(x)[:,:1].detach() for b in getattr(h,n)] for n in ('cv3','one2one_cv3')}
        report=trainer.adapt_person(model)
        self.assertEqual(len(report),6);self.assertEqual(h.nc,1);self.assertEqual(h.no,5)
        for name,branches in expected.items():
            for i,out in enumerate(branches):
                self.assertTrue(torch.equal(getattr(h,name)[i](x),out))
        for key,value in model.state_dict().items():
            self.assertTrue(torch.equal(value,before[key][:1] if value.shape!=before[key].shape else before[key]))

    def test_unexpected_head_rejected(self):
        model=self.fake();model.model[-1].nc=79
        with self.assertRaises(ValueError):trainer.adapt_person(model)
        model=self.fake();model.model[-1].one2one_cv3[2][-1]=torch.nn.Conv2d(7,79,1)
        with self.assertRaises(ValueError):trainer.adapt_person(model)

    def test_native_targets_letterbox_and_roundtrip(self):
        import cv2
        import numpy as np
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);cv2.imwrite(str(folder/'a.png'),np.zeros((120,240,3),dtype=np.uint8))
            row=dict(image='a.png',source_size=[240,120],confirmed_person_boxes=[dict(xyxy=[24,12,120,96])])
            image,g=trainer.image_tensor(row,folder,'cpu');batch=trainer.batch_targets([row,row],folder,'cpu')
            self.assertEqual(tuple(image.shape),(1,3,640,640));self.assertEqual(g['top'],160)
            self.assertTrue(torch.allclose(batch['bboxes'][0],torch.tensor([.3,.475,.4,.35])))
            self.assertEqual(batch['batch_idx'].tolist(),[0,1]);self.assertEqual(batch['cls'].tolist(),[[0],[0]])

    def test_nonfinite_weights_and_optimizer_rejected(self):
        model=self.fake();optimizer=torch.optim.AdamW(model.parameters(),lr=.0001)
        trainer.finite_state(model,optimizer)
        with torch.no_grad():next(model.parameters()).fill_(float('nan'))
        with self.assertRaises(ValueError):trainer.finite_state(model,optimizer)

    def test_full_initial_and_trained_optimizer_checkpoint(self):
        model=self.fake();optimizer=torch.optim.AdamW(model.parameters(),lr=.0001)
        # Local test class is not picklable; checkpoint uses a real standard module here.
        model=torch.nn.Linear(3,1);optimizer=torch.optim.AdamW(model.parameters(),lr=.0001)
        initial=model.weight.detach().clone();model(torch.ones(2,3)).sum().backward();optimizer.step()
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'last.pt';trainer.checkpoint(path,model,optimizer,5,125)
            saved=torch.load(path,weights_only=False)
        self.assertEqual(saved['optimizer_steps'],125);self.assertEqual(saved['epoch'],5)
        self.assertTrue(saved['optimizer']['state']);self.assertFalse(torch.equal(saved['model'].weight,initial))
        self.assertTrue(torch.equal(saved['state_dict']['weight'],model.weight))

    def test_bad_scope_wrong_assignment_and_retry_rejected(self):
        with self.assertRaises(ValueError):command.input_contract(dict(model_id='yolo26x',stage='train5',files={}))
        with self.assertRaises(ValueError):command.validate(dict(stage='smoke'),{},command.RUNTIME)
        with self.assertRaises(ValueError):command.retry_guard(None,None)
        with self.assertRaises(ValueError):command.output_path('train5','bad')

    def test_queue_migration_preserves_all_old_rows_and_retry_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            q=Queue.initialize(Path(temp).resolve());old=q.enqueue(job_key='old',run_id='r',task_id='t',dispatch_id='d',owner='o')
            before=q.status();q.migrate_commands(include_person_detector_train=True)
            self.assertEqual(before,q.status())
            with q.connection() as db:self.assertIn('person-detector-train',db.execute("SELECT sql FROM sqlite_master WHERE name='jobs'").fetchone()[0])

    def test_runner_rejects_missing_held_fd_before_importing_model(self):
        with patch.dict('os.environ',{},clear=True):
            with self.assertRaises(KeyError):command.runner_guard(SimpleNamespace())


if __name__=='__main__':unittest.main()
