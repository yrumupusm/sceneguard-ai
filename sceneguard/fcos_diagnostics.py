"""Read-only shadow of TorchVision 0.20 FCOS postprocessing, never returned as predictions."""
import json
import types
from pathlib import Path

STAGES = {0: 'internal_score', 1: 'level_topk', 2: 'nms',
          3: 'global_cap', 4: 'returned_below_0.5', 5: 'final_person'}


class FCOSDiagnostics:
    def __init__(self, model, output, threshold):
        self.model, self.output, self.threshold = model, Path(output), threshold
        self.pts = None
        self.selected = {84., 88., 90., 92., 94., 96.}
        self.records = []
        self.original = model.postprocess_detections
        def wrapped(_model, heads, anchors, shapes):
            result = self.original(heads, anchors, shapes)
            if self.pts is not None:
                self.capture(heads, anchors, shapes, result)
            return result  # Unmodified upstream result, not shadow predictions.
        model.postprocess_detections = types.MethodType(wrapped, model)

    def capture(self, heads, anchors, shapes, actual):
        import numpy as np
        import torch
        from torchvision.ops import boxes as ops
        m = self.model
        assert len(shapes) == 1, 'Diagnostic supports batch=1'
        person_boxes, person_scores, probabilities, centers, stages = [], [], [], [], []
        all_boxes, all_scores, all_labels, all_ids = [], [], [], []
        level_counts = []
        offset = 0
        for level, (logits, regression, ctr, anchor) in enumerate(zip(
                heads['cls_logits'], heads['bbox_regression'], heads['bbox_ctrness'], anchors[0])):
            logits, regression, ctr = logits[0], regression[0], ctr[0]
            nc = logits.shape[-1]
            probs, cp = logits.sigmoid(), ctr.sigmoid()
            scores = torch.sqrt(probs * cp)
            ps = scores[:, 1]
            flat = scores.flatten()
            eligible = torch.where(flat > m.score_thresh)[0]
            values, rank = flat[eligible].topk(min(len(eligible), m.topk_candidates))
            chosen = eligible[rank]
            ai, labels = torch.div(chosen, nc, rounding_mode='floor'), chosen % nc
            boxes = ops.clip_boxes_to_image(m.box_coder.decode(regression[ai], anchor[ai]), shapes[0])
            all_boxes.append(boxes); all_scores.append(values); all_labels.append(labels)
            all_ids.append(ai + offset)
            # Decode every person anchor, even below internal threshold, for offline localization only.
            person_boxes.append(ops.clip_boxes_to_image(m.box_coder.decode(regression, anchor), shapes[0]))
            person_scores.append(ps); probabilities.append(probs[:, 1]); centers.append(cp[:, 0])
            stage = torch.zeros(len(ps), device=ps.device, dtype=torch.int64)
            stage[ps > m.score_thresh] = 1
            stage[ai[labels == 1]] = 2
            stages.append(stage)
            level_counts.append(dict(level=level, anchors=len(ps),
                person_internal=int((ps > m.score_thresh).sum()),
                all_class_eligible=len(eligible), all_class_topk=len(chosen),
                person_topk=int((labels == 1).sum())))
            offset += len(ps)
        boxes, scores, labels, ids = [torch.cat(x) for x in (all_boxes, all_scores, all_labels, all_ids)]
        keep = ops.batched_nms(boxes, scores, labels, m.nms_thresh)
        retained = keep[:m.detections_per_img]
        for key, value in [('boxes', boxes[retained]), ('scores', scores[retained]), ('labels', labels[retained])]:
            if not torch.equal(value, actual[0][key]):
                raise AssertionError('Shadow differs from upstream: '+key)
        stage = torch.cat(stages)
        stage[ids[keep[labels[keep] == 1]]] = 3
        person_retained = retained[labels[retained] == 1]
        stage[ids[person_retained]] = 4
        stage[ids[person_retained[scores[person_retained] >= self.threshold]]] = 5
        record = dict(pts=self.pts, shadow_exact=True, levels=level_counts,
                      stage_counts={STAGES[k]:int((stage == k).sum()) for k in STAGES},
                      all_class_after_nms=len(keep), all_class_returned=len(retained))
        if self.pts in self.selected:
            # Suppressor is the first earlier NMS survivor of the SAME class exceeding IoU.
            # Keep all survivors before the global cap; capped survivors can still suppress.
            suppressions = []
            survived = set(keep.cpu().tolist())
            for j in torch.where(labels == 1)[0].cpu().tolist():
                if j in survived: continue
                possible = keep[(labels[keep] == 1) & (scores[keep] >= scores[j])]
                overlap = ops.box_iou(boxes[j:j+1], boxes[possible])[0]
                match = torch.where(overlap > m.nms_thresh)[0]
                if not len(match):
                    raise AssertionError('No NMS suppressor found')
                k = int(possible[match[0]])
                suppressions.append(dict(candidate_id=int(ids[j]), suppressor_id=int(ids[k]),
                    candidate_score=float(scores[j]), suppressor_score=float(scores[k]),
                    iou=float(overlap[match[0]]), suppressor_stage=STAGES[int(stage[ids[k]])]))
            record['suppressions'] = suppressions
            h,w = shapes[0]
            norm = torch.tensor([w,h,w,h],device=boxes.device)
            np.savez_compressed(self.output/f'candidates_{self.pts:.6f}.npz',
                boxes=(torch.cat(person_boxes)/norm).cpu().numpy(),
                scores=torch.cat(person_scores).cpu().numpy(),
                class_probability=torch.cat(probabilities).cpu().numpy(),
                centerness=torch.cat(centers).cpu().numpy(), stage=stage.cpu().numpy(),
                level_sizes=np.array([x['anchors'] for x in level_counts]))
        self.records.append(record)
        with (self.output/'diagnostic_stages.jsonl').open('a') as f:
            f.write(json.dumps(record)+'\n')

    def finish(self):
        import inspect
        import hashlib
        from torchvision.models.detection.fcos import FCOS
        source=inspect.getsource(FCOS.postprocess_detections)
        (self.output/'diagnostic_config.json').write_text(json.dumps(dict(
            internal_score=self.model.score_thresh, nms_iou=self.model.nms_thresh,
            topk_per_level=self.model.topk_candidates, detections_per_image=self.model.detections_per_img,
            final_person_score=self.threshold, selected_pts=sorted(self.selected), stages=STAGES,
            postprocess_source_sha256=hashlib.sha256(source.encode()).hexdigest(),
            frames_verified=len(self.records), timing_comparable=False),indent=2))
