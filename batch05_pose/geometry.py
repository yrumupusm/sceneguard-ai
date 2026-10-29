# SPDX-License-Identifier: AGPL-3.0-only
"""Fixed background ROI, with one explicit native-local to source translation."""
from copy import deepcopy
import math
from batch04_pose.api import result_rows

ROI = [.28, .20, .75, .80]
PIXELS = (537, 216, 1440, 864)


def bounds(shape, roi):
    h, w = shape[:2]
    if len(roi) != 4 or not all(math.isfinite(v) and 0 <= v <= 1 for v in roi):
        raise ValueError('finite normalized ROI required')
    x1,y1,x2,y2 = roi
    if x1 >= x2 or y1 >= y2:
        raise ValueError('positive ROI required')
    return math.floor(x1*w),math.floor(y1*h),math.ceil(x2*w),math.ceil(y2*h)


def crop(rgb):
    import numpy as np
    if not isinstance(rgb,np.ndarray) or rgb.dtype != np.uint8 or rgb.shape != (1080,1920,3):
        raise ValueError('exact original RGB required')
    x1,y1,x2,y2 = bounds(rgb.shape,ROI)
    if (x1,y1,x2,y2) != PIXELS:
        raise ValueError('fixed C6 geometry differs')
    return np.ascontiguousarray(rgb[y1:y2,x1:x2])


def rows(result, shape, view):
    if view not in ('full','C6'):
        raise ValueError('fixed view required')
    local = result_rows(result,shape)
    original = deepcopy(local)
    if view == 'C6':
        if tuple(shape) != (648,903,3):
            raise ValueError('exact C6 crop shape required')
        # Retention is decided in local coordinates before offset. Never reparse shifted rows.
        for p in original:
            x1,y1,x2,y2 = p['xyxy']
            p['xyxy'] = [x1+537,y1+216,x2+537,y2+216]
            for k in p['keypoints']:
                x,y = k['raw_xy']
                k['raw_xy'] = [x+537,y+216]
                if k['observed_xy'] is not None:
                    x,y = k['observed_xy']
                    k['observed_xy'] = [x+537,y+216]
    elif tuple(shape) != (1080,1920,3):
        raise ValueError('exact full shape required')
    return dict(local_persons=local,persons=original,offset_applications=1 if view=='C6' else 0,
        local_coordinate_space='crop RGB' if view=='C6' else 'source RGB',
        output_coordinate_space='source RGB; unknown sentinel status preserved from local coordinates')
