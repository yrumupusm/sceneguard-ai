"""Pinned detector specifications; no implicit backbone downloads."""
SPECS = {
    'ssdlite320': {
        'name': 'ssdlite320_mobilenet_v3_large.COCO_V1',
        'filename': 'ssdlite320_mobilenet_v3_large_coco-a79551df.pth',
        'hash_prefix': 'a79551df', 'input': [320, 320],
    },
    'fcos800': {
        'name': 'fcos_resnet50_fpn.COCO_V1',
        'filename': 'fcos_resnet50_fpn_coco-99b0c9b7.pth',
        'hash_prefix': '99b0c9b7', 'input': {'min_size': 800, 'max_size': 1333},
    },
}


def build_detector(name):
    from torch import nn
    from torchvision.models.detection import ssdlite320_mobilenet_v3_large, fcos_resnet50_fpn
    from torchvision.ops.misc import FrozenBatchNorm2d
    if name == 'ssdlite320':
        return ssdlite320_mobilenet_v3_large(weights=None, weights_backbone=None).eval()
    if name != 'fcos800':
        raise ValueError('Unknown detector')
    model = fcos_resnet50_fpn(weights=None, weights_backbone=None, min_size=800, max_size=1333)
    # TorchVision 0.20.1 uses FrozenBN when pretrained weights are requested.
    # Match that architecture without an implicit download or unsafe pickle loader.
    def freeze_bn(module):
        for child_name, child in list(module.named_children()):
            if isinstance(child, nn.BatchNorm2d):
                setattr(module, child_name, FrozenBatchNorm2d(child.num_features, eps=child.eps))
            else:
                freeze_bn(child)
    freeze_bn(model)
    return model.eval()
