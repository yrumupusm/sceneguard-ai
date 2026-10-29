# SPDX-License-Identifier: AGPL-3.0-only
"""Detection-only native Results validation; keep local coordinates and one offset."""
import math


def result_rows(result,shape,offset):
    if result.keypoints is not None or tuple(result.orig_shape)!=tuple(shape[:2]) or result.boxes is None:
        raise ValueError('native Detection Results and exact original shape required')
    array=result.boxes.data.detach().cpu().numpy()
    if len(array.shape)!=2 or array.shape[1]!=6:raise ValueError('Nx6 Detection boxes required')
    local=[];full=[]
    for row in array.tolist():
        x1,y1,x2,y2,score,cls=row
        if not all(math.isfinite(x) for x in row) or cls!=0 or not .25<=score<=1 or x2<=x1 or y2<=y1:
            raise ValueError('finite person0 boxes/confidence required')
        if not 0<=x1<=x2<=shape[1] or not 0<=y1<=y2<=shape[0]:raise ValueError('native boxes outside crop')
        local.append(dict(xyxy=[x1,y1,x2,y2],confidence=score,class_id=0))
        full.append(dict(xyxy=[x1+offset[0],y1+offset[1],x2+offset[0],y2+offset[1]],confidence=score,class_id=0))
    return dict(person_count=len(local),local_persons=local,persons=full,offset_applications=1,
        accuracy=None,visual_quality='unreviewed',behavior='unmeasured')
