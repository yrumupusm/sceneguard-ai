# SPDX-License-Identifier: AGPL-3.0-only
"""Local diagnostic box images; no uploads or accuracy claims."""
from pathlib import Path
from orchestration.batch07_detect_command import ROOT
from orchestration.vlm_command import file_hash


def draw(rgb,record,path):
    import cv2
    bgr=cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR)
    for i,row in enumerate(record['persons']):
        x1,y1,x2,y2=[round(v) for v in row['xyxy']]
        cv2.rectangle(bgr,(x1,y1),(x2,y2),(0,255,0),2)
        cv2.putText(bgr,f"{i+1} person {row['confidence']:.3f}",(x1,max(22,y1-5)),cv2.FONT_HERSHEY_SIMPLEX,.65,(0,255,0),2)
    x1,y1,x2,y2=record['crop_xyxy'];cv2.rectangle(bgr,(x1,y1),(x2,y2),(255,190,0),1)
    cv2.putText(bgr,f"{record['phase']} | {record['frame_id']} | boxes {record['person_count']} | unreviewed",(20,35),cv2.FONT_HERSHEY_SIMPLEX,.85,(0,255,255),2)
    if not cv2.imwrite(str(path),bgr):raise ValueError('local overlay save failed')


def compare(frames,before,after,folder):
    import cv2
    import numpy as np
    out={}
    for frame in frames:
        fid=frame['frame_id']
        a=cv2.imread(str(folder/('baseline-'+fid+'-overlay.png')))
        b=cv2.imread(str(folder/('after-'+fid+'-overlay.png')))
        p=folder/(fid+'-baseline-after.png')
        if a is None or b is None or a.shape!=b.shape:raise ValueError('matching local comparison images required')
        if not cv2.imwrite(str(p),np.concatenate([a,b],axis=1)):raise ValueError('comparison save failed')
        out[fid]=dict(path=str(p.relative_to(ROOT)),sha256=file_hash(p),shape=list(a.shape[:1])+[a.shape[1]*2,3])
    return out
