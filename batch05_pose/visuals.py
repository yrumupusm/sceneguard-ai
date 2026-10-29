# SPDX-License-Identifier: AGPL-3.0-only
"""Local native-resolution triptychs; never opens or uploads CCTV media."""
import hashlib
from orchestration.batch05_pose_command import ROOT,cached_record
from batch04_pose.api import bgr_source


def comparison_images(manifest,records,folder):
    import cv2
    import numpy as np
    cached=cached_record(manifest)
    lookup={r['condition_id']:r for r in records}
    lookup['030_090_full']=dict(cached,cached=True)
    edges=((5,6),(5,7),(7,9),(6,8),(8,10),(5,11),(6,12),(11,12),(11,13),(13,15),(12,14),(14,16))
    artifacts={}
    for f in manifest['frames']:
        frame=f['frame_id'];original=bgr_source(np.load(ROOT/f['rgb_path'],allow_pickle=False))
        panels=[]
        for view in ('original','full','C6'):
            panel=original.copy()
            r=None if view=='original' else lookup[frame+'_'+view]
            if r:
                for p in r['persons']:
                    a,b,c,d=map(round,p['xyxy']);color=(60,230,80)
                    cv2.rectangle(panel,(a,b),(c,d),color,2)
                    cv2.putText(panel,'row '+str(p['output_index']),(a,max(20,b-5)),cv2.FONT_HERSHEY_SIMPLEX,.6,color,2)
                    xy=[k['observed_xy'] for k in p['keypoints']]
                    for i,j in edges:
                        if xy[i] is not None and xy[j] is not None:
                            cv2.line(panel,tuple(map(round,xy[i])),tuple(map(round,xy[j])),color,2)
                    for k in xy:
                        if k is not None:cv2.circle(panel,tuple(map(round,k)),4,(0,0,255),-1)
            cv2.rectangle(panel,(537,216),(1439,863),(255,150,0),2)
            banner=np.zeros((65,1920,3),dtype=np.uint8)
            label=f'{frame} native PTS {f["pts_seconds"]}s | {view}'
            if r:label+=f' | rows {r["person_count"]} | '+('CACHED EXP-0022; no new prediction' if r.get('cached') else 'NEW EXP-0023')
            cv2.putText(banner,label,(12,25),cv2.FONT_HERSHEY_SIMPLEX,.7,(255,255,255),1)
            cv2.putText(banner,'Blue rectangle: fixed C6. Pose estimates >=0.5; correspondence pending human review.',(12,52),cv2.FONT_HERSHEY_SIMPLEX,.65,(255,255,255),1)
            image=np.concatenate((banner,panel),axis=0)
            path=folder/(frame+'-'+view+'.png')
            if not cv2.imwrite(str(path),image):raise ValueError('local PNG save failed')
            artifacts[frame+'_'+view]=dict(path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            panels.append(image)
        path=folder/(frame+'-comparison.png')
        if not cv2.imwrite(str(path),np.concatenate(panels,axis=1)):raise ValueError('triptych save failed')
        artifacts[frame]=dict(path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    return artifacts
