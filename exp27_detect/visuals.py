# SPDX-License-Identifier: AGPL-3.0-only
"""Full-native local triptychs with every returned box and score retained."""
from orchestration.exp27_detect_command import ROOT
from orchestration.vlm_command import file_hash
from exp27_detect.api import score_bin,BINS
COLORS=((0,165,255),(0,255,255),(0,220,0))  # BGR orange/yellow/green


def panel(rgb,record,label):
    import cv2
    import numpy as np
    image=cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR)
    if record is not None:
        for i,row in enumerate(record['persons']):
            x1,y1,x2,y2=map(round,row['xyxy']);color=COLORS[BINS.index(score_bin(row['confidence']))]
            cv2.rectangle(image,(x1,y1),(x2,y2),color,2)
            cv2.putText(image,f"{i+1}: {row['confidence']:.4f}",(x1,max(16,y1-5)),cv2.FONT_HERSHEY_SIMPLEX,.5,color,1)
    banner=np.zeros((60,image.shape[1],3),dtype=np.uint8)
    cv2.putText(banner,label,(15,23),cv2.FONT_HERSHEY_SIMPLEX,.65,(255,255,255),1)
    cv2.putText(banner,'orange [.05,.10) | yellow [.10,.25) | green [.25,1] | human review pending',(15,48),cv2.FONT_HERSHEY_SIMPLEX,.55,(255,255,255),1)
    return np.concatenate((banner,image),axis=0)


def triptych(rgb,before,after,folder,frame_id):
    import cv2
    import numpy as np
    images=[panel(rgb,None,frame_id+' ORIGINAL'),panel(rgb,before,'pretrained Detection conf .05'),panel(rgb,after,'fine-tuned Detection conf .05')]
    paths={}
    for label,im in zip(('original','pretrained','fine_tuned','triptych'),images+[np.concatenate(images,axis=1)]):
        path=folder/(frame_id+'-'+label+'.png')
        if path.exists():raise ValueError('never overwrite local image output')
        if not cv2.imwrite(str(path),im):raise ValueError('PNG save failed')
        paths[label]=dict(path=str(path.relative_to(ROOT)),sha256=file_hash(path),shape=list(im.shape))
    return paths
