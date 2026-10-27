import unittest
from sceneguard.detectors import SPECS, build_detector


class DetectorTests(unittest.TestCase):
    def test_specs_preserve_baseline_and_new_size(self):
        self.assertEqual(SPECS['ssdlite320']['input'],[320,320])
        self.assertEqual(SPECS['fcos800']['input'],{'min_size':800,'max_size':1333})

    def test_fcos_pretrained_architecture_without_download(self):
        import torch
        from torchvision.ops.misc import FrozenBatchNorm2d
        model=build_detector('fcos800')
        self.assertFalse(model.training)
        self.assertFalse(any(isinstance(m,torch.nn.BatchNorm2d) for m in model.modules()))
        self.assertEqual(sum(isinstance(m,FrozenBatchNorm2d) for m in model.modules()),53)
        self.assertEqual(model.transform.min_size,(800,))
        self.assertEqual(model.transform.max_size,1333)
        self.assertEqual(sum(p.numel() for p in model.parameters()),32269600)


if __name__=='__main__':unittest.main()
