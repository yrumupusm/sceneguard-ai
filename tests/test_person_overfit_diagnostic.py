import copy
import unittest
import torch
from scripts.diagnose_person_overfit import swap_bn_statistics, state_hash, summarize


class OverfitDiagnosticTests(unittest.TestCase):
    def test_statistics_swap_preserves_affine_and_other_weights_and_donor(self):
        target=torch.nn.Sequential(torch.nn.Conv2d(3,4,1),torch.nn.BatchNorm2d(4))
        donor=copy.deepcopy(target)
        with torch.no_grad():
            donor[0].weight.fill_(17)
            donor[1].weight.fill_(9)
            donor[1].bias.fill_(7)
            donor[1].running_mean.fill_(4)
            donor[1].running_var.fill_(3)
            donor[1].num_batches_tracked.fill_(125)
        old=copy.deepcopy(target.state_dict()); donor_hash=state_hash(donor)
        keys=swap_bn_statistics(target,donor)
        self.assertEqual(len(keys),3)
        self.assertTrue(torch.equal(target[0].weight,old['0.weight']))
        self.assertTrue(torch.equal(target[1].weight,old['1.weight']))
        self.assertTrue(torch.equal(target[1].bias,old['1.bias']))
        self.assertTrue(torch.equal(target[1].running_var,donor[1].running_var))
        self.assertEqual(state_hash(donor),donor_hash)
        target[1].running_var.zero_()
        self.assertTrue((donor[1].running_var==3).all())

    def test_train_and_validation_metrics_are_separate(self):
        frames=[];predictions=[]
        for n,split in [(1,'train'),(3,'train'),(5,'validation')]:
            frames.append(dict(frame_id=str(n),case_number=n,split=split,event_group=str(n),
                source_pts=0.,image_sha256=str(n),source_size=[100,100],
                confirmed_person_boxes=[dict(xyxy=[0,0,10,10])]))
            predictions.append(dict(frame_id=str(n),source_pts=0.,image_sha256=str(n),
                boxes=[[0,0,10,10]],person_scores=[.9 if split=='train' else .1]))
        result=summarize(frames,predictions)
        self.assertEqual(result['groups']['train']['tp'],2)
        self.assertEqual(result['groups']['train']['events'],2)
        self.assertEqual(result['groups']['validation']['fn'],1)
        self.assertEqual(result['groups']['validation']['recall'],0)


if __name__=='__main__':
    unittest.main()
