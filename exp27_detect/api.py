# SPDX-License-Identifier: AGPL-3.0-only
"""Native Detection rows and ordered CPU diagnostics, without any model calls."""
import math

BINS = ('[0.05,0.10)','[0.10,0.25)','[0.25,1]')
POSITION_ATOL = .001
SCORE_ATOL = .000001


def score_bin(score):
    if not math.isfinite(score) or not .05<=score<=1:
        raise ValueError('finite confidence in [0.05,1] required')
    return BINS[0] if score<.10 else BINS[1] if score<.25 else BINS[2]


def result_rows(result,shape,offset,minimum=.05):
    if result.keypoints is not None or tuple(result.orig_shape)!=tuple(shape[:2]) or result.boxes is None:
        raise ValueError('native Detection Results and exact original shape required')
    array=result.boxes.data.detach().cpu().numpy()
    if len(array.shape)!=2 or array.shape[1]!=6:raise ValueError('Nx6 Detection boxes required')
    local=[];full=[]
    for row in array.tolist():
        x1,y1,x2,y2,score,cls=row
        if not all(math.isfinite(x) for x in row) or cls!=0 or not minimum<=score<=1:
            raise ValueError('finite person0 boxes/confidence required')
        if not 0<=x1<x2<=shape[1] or not 0<=y1<y2<=shape[0]:raise ValueError('native boxes outside crop')
        local.append(dict(xyxy=[x1,y1,x2,y2],confidence=score,class_id=0))
        full.append(dict(xyxy=[x1+offset[0],y1+offset[1],x2+offset[0],y2+offset[1]],confidence=score,class_id=0))
    counts={b:0 for b in BINS}
    for r in local:counts[score_bin(r['confidence'])]+=1
    return dict(person_count=len(local),local_persons=local,persons=full,offset_applications=1,
        confidence_bins=counts,top_scores=sorted((r['confidence'] for r in local),reverse=True)[:10],
        accuracy=None,visual_quality='unreviewed',behavior='unmeasured')


def compare_cached(low,old):
    """Compare in returned order, never rematch/reorder boxes or coerce equality."""
    high=[r for r in low if r['confidence']>=.25]
    deltas=[]
    for i,(a,b) in enumerate(zip(high,old)):
        deltas.append(dict(index=i,xyxy_delta=[x-y for x,y in zip(a['xyxy'],b['xyxy'])],
            confidence_delta=a['confidence']-b['confidence'],class_equal=a['class_id']==b['class_id']))
    same_count=len(high)==len(old)
    ordered_tolerance=same_count and all(d['class_equal'] and abs(d['confidence_delta'])<=SCORE_ATOL
        and all(abs(x)<=POSITION_ATOL for x in d['xyxy_delta']) for d in deltas)
    return dict(cpu_filter='confidence >= 0.25; official EXP26 final filter was > 0.25',
        filtered_count=len(high),cached_count=len(old),exact_ordered_equal=high==old,
        tolerance_ordered_equal=ordered_tolerance,position_atol_pixels=POSITION_ATOL,score_atol=SCORE_ATOL,
        boundary_exact_025_count=sum(r['confidence']==.25 for r in high),paired_deltas=deltas,
        count_delta=len(high)-len(old),max_abs_position_delta=max((abs(x) for d in deltas for x in d['xyxy_delta']),default=0),
        max_abs_confidence_delta=max((abs(d['confidence_delta']) for d in deltas),default=0),
        interpretation='numeric/order diagnosis only; no person correspondence or accuracy claim')


def official_audit():
    """Inspect installed primary source and signatures, without constructing a model."""
    import hashlib
    import inspect
    import importlib.metadata
    from pathlib import Path
    import torch
    from ultralytics.engine.model import Model
    from ultralytics.models.yolo.detect.predict import DetectionPredictor
    from ultralytics.nn.modules.head import Detect
    from ultralytics.utils.nms import non_max_suppression
    from ultralytics.cfg import get_cfg
    from orchestration.exp27_detect_command import PREDICT_KWARGS
    if importlib.metadata.version('ultralytics')!='8.4.192':raise ValueError('fixed Ultralytics required')
    inspect.signature(Model.predict).bind(None,source=object(),**PREDICT_KWARGS)
    get_cfg(overrides={k:v for k,v in PREDICT_KWARGS.items() if k!='stream'})
    methods=[Model.predict,DetectionPredictor.postprocess,DetectionPredictor.construct_result,
        Detect.postprocess,Detect.get_topk_index,non_max_suppression]
    source={m.__qualname__:inspect.getsource(m) for m in methods}
    if 'mask = pred[:, 4] > conf_thres' not in source[non_max_suppression.__qualname__]:
        raise ValueError('strict confidence filter pathway differs')
    if 'scores.flatten(1)' not in source[Detect.get_topk_index.__qualname__] or 'self.max_det' not in source[Detect.postprocess.__qualname__]:
        raise ValueError('head top-k pathway differs')
    return dict(version='8.4.192',model_constructions=0,
        signatures={m.__qualname__:str(inspect.signature(m)) for m in methods},
        installed_sources={str(Path(inspect.getsourcefile(m))):hashlib.sha256(Path(inspect.getsourcefile(m)).read_bytes()).hexdigest() for m in methods},
        source_bodies=source,
        order='end2end head: top-k anchors by maximum class score then top-k flattened class scores; predictor: score > conf AND class0, then [:max_det]; native scale_boxes once upstream',
        head_class_difference='pretrained80 vs fine-tuned1 affects head top-k competition before person0 filtering',
        comparison_boundary='CPU >=0.25 intentionally includes exact 0.25; official final filter uses >0.25',
        limitation='conf0.05 final Results expose only retained head/top-k/class/threshold rows; empty does not establish absence of internal candidates')
