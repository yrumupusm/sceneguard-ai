# SPDX-License-Identifier: AGPL-3.0-only
"""All-row native triptychs created locally; no viewing, resizing, or upload."""
import hashlib
from orchestration.batch06_pose_command import ROOT,cached_records
from batch04_pose.api import bgr_source


def comparison_images(manifest,records,folder):
    import cv2
    import numpy as np
    cached=cached_records(manifest)
    lookup={r['frame_id']:r for r in records}
    edges=((5,6),(5,7),(7,9),(6,8),(8,10),(5,11),(6,12),(11,12),(11,13),(13,15),(12,14),(14,16))
    artifacts={}
    for f in manifest['frames']:
        frame=f['frame_id'];original=bgr_source(np.load(ROOT/f['rgb_path'],allow_pickle=False));panels=[]
        for view in ('original','640 cached EXP-0023','960 new EXP-0025'):
            panel=original.copy();r=None if view=='original' else cached[frame] if view.startswith('640') else lookup[frame]
            labels=[]
            if r is not None:
                for p in r['persons']:
                    a,b,c,d=map(round,p['xyxy']);color=((80+71*p['output_index'])%255,230,80)
                    cv2.rectangle(panel,(a,b),(c,d),color,2)
                    label=f'row {p["output_index"]} score {p["confidence"]:.3f} retained {p["retained_joint_count"]}/17'
                    labels.append(label)
                    cv2.putText(panel,label,(a,max(20,b-5)),cv2.FONT_HERSHEY_SIMPLEX,.55,color,2)
                    xy=[k['observed_xy'] for k in p['keypoints']]
                    for i,j in edges:
                        if xy[i] is not None and xy[j] is not None:cv2.line(panel,tuple(map(round,xy[i])),tuple(map(round,xy[j])),color,2)
                    for k in xy:
                        if k is not None:cv2.circle(panel,tuple(map(round,k)),4,(0,0,255),-1)
            cv2.rectangle(panel,(537,216),(1439,863),(255,150,0),2)
            # Variable header keeps every row's score visible even if labels overlap on people.
            header=np.zeros((180+28*max(len(cached[frame]['persons']),len(lookup[frame]['persons'])),1920,3),dtype=np.uint8)
            text=[f'{frame} native PTS {f["native_pts"]} x {f["time_base"]} = {f["pts_seconds"]}s | {view}',
                'Cyan rectangle: fixed ROI | Green/varied: all person boxes + skeleton | Red: retained joints',
                'Unknown joints omitted; rows are not person IDs; actual body/joint correspondence needs human review']
            if r is not None:text.append(f'Normal Results: {r["person_count"]} rows; '+('no new prediction' if view.startswith('640') else 'one new 960 prediction'))
            for i,line in enumerate(text+labels):cv2.putText(header,line,(12,27+28*i),cv2.FONT_HERSHEY_SIMPLEX,.67,(255,255,255),1)
            panels.append(np.concatenate((header,panel),axis=0))
        path=folder/(frame+'-comparison.png')
        if not cv2.imwrite(str(path),np.concatenate(panels,axis=1)):raise ValueError('local PNG write failed')
        artifacts[frame]=dict(path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    return artifacts
