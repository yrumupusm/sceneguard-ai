"""Offline diagnostic rendering/association; never performs inference or creates ground truth."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw

STAGES=['internal_score','level_topk','nms','global_cap','returned_below_0.5','final_person']

def overlaps(boxes,ref):
    intersection=np.maximum(0,np.minimum(boxes[:,2:],ref[2:])-np.maximum(boxes[:,:2],ref[:2])).prod(1)
    union=(boxes[:,2:]-boxes[:,:2]).prod(1)+(ref[2:]-ref[:2]).prod()-intersection
    return intersection/np.maximum(union,1e-8)

def main(args):
    root=Path(__file__).resolve().parents[1]
    assert args.output.resolve().is_relative_to(root/'outputs')
    args.output.mkdir(parents=True,exist_ok=False)
    rows=[json.loads(x) for x in (args.run/'frames.jsonl').read_text().splitlines()]
    old=[json.loads(x) for x in (args.baseline/'frames.jsonl').read_text().splitlines()]
    assert rows == [r for r in old if rows[0]['pts']<=r['pts']<=rows[-1]['pts']]
    records={r['pts']:r for r in map(json.loads,(args.run/'diagnostic_stages.jsonl').read_text().splitlines())}
    regions=json.loads(args.locations.read_text())
    associations=[]
    for t in [84,88,90,92,94,96]:
        a=np.load(args.run/f'candidates_{t:.6f}.npz')
        boxes=a['boxes']*np.array([960,540,960,540])
        scores,stage=a['scores'],a['stage']
        suppression={r['candidate_id']:r for r in records[t]['suppressions']}
        selected=set()
        local=[]
        for name,ref in regions.get(str(t),{}).items():
            iou=overlaps(boxes,np.array(ref))
            eligible=np.where(iou>=.3)[0]
            for kind,indices in [('max_score',eligible),
                    ('internal_example',eligible[stage[eligible]==0]),
                    ('nms_example',eligible[stage[eligible]==2])]:
                if not len(indices):continue
                i=int(indices[np.argmax(scores[indices])]);selected.add(i)
                row=dict(pts=t,region=name,selection=kind,candidate_id=i,
                    score=float(scores[i]),class_probability=float(a['class_probability'][i]),
                    centerness=float(a['centerness'][i]),stage=STAGES[stage[i]],review_iou=float(iou[i]),
                    suppressor_id='',suppressor_score='',suppression_iou='')
                if i in suppression:
                    r=suppression[i];row.update(suppressor_id=r['suppressor_id'],
                        suppressor_score=r['suppressor_score'],suppression_iou=r['iou'])
                associations.append(row);local.append(row)
        if not selected:
            # Display selection only, no inference crop: top score per terminal stage near the gate.
            center=(boxes[:,:2]+boxes[:,2:])/2
            near=(center[:,0]>330)&(center[:,0]<650)&(center[:,1]>160)&(center[:,1]<400)
            for st in [0,2,3,4,5]:
                ii=np.where(near&(stage==st))[0]
                if len(ii):selected.add(int(ii[np.argmax(scores[ii])]))
        original=Image.open(args.previews/f'pair_{t:.6f}.jpg').crop((0,40,960,580))
        # Existing SSD preview in all these frames has zero boxes; verify externally below.
        final=original.copy();d=ImageDraw.Draw(final)
        current=next(r for r in rows if r['pts']==t)
        for det in current['detections']:
            b=np.array(det['bbox'])*[960,540,960,540];d.rectangle(b.tolist(),outline='lime',width=2)
            d.text((b[0],b[1]),f"{det['score']:.3f}",fill='lime')
        diag=original.copy();d=ImageDraw.Draw(diag)
        for name,b in regions.get(str(t),{}).items():
            d.rectangle(b,outline='cyan',width=1);d.text((b[0],b[1]-12),name,fill='cyan')
        colors=['gray','blue','red','magenta','orange','lime']
        for i in sorted(selected,key=lambda j:float(scores[j])):
            b=boxes[i];d.rectangle(b.tolist(),outline=colors[stage[i]],width=2)
            d.text((b[0],b[3]),f"#{i} {scores[i]:.3f} {STAGES[stage[i]]}",fill=colors[stage[i]])
        canvas=Image.new('RGB',(2880,850),'black');d=ImageDraw.Draw(canvas)
        for j,(im,label) in enumerate([(original,'Original existing preview'),(final,'FINAL person >=0.5 (unchanged)'),
                                       (diag,'DIAGNOSTIC ONLY: selected raw candidates, NOT detections')]):
            canvas.paste(im,(960*j,35));d.text((960*j+10,10),f'PTS {t} | {label}',fill='white')
        d.text((10,590),'Cyan: approximate review regions (not GT / not inference crops). Gray: <=0.2; red: NMS; magenta: global cap; orange: returned <0.5; green: final.',fill='white')
        for k,row in enumerate(local):
            d.text((10,615+22*k),f"{row['region']} {row['selection']} #{row['candidate_id']} score={row['score']:.6f} stage={row['stage']} reviewIoU={row['review_iou']:.3f} suppressor={row['suppressor_id']} IoU={row['suppression_iou']}",fill='white')
        canvas.save(args.output/f'diagnostic_{t}.jpg',quality=95)
        if local:
            # Post-inference zoom only; readable one-candidate cards and explicit suppressor.
            cards=Image.new('RGB',(1800,930),'black');cd=ImageDraw.Draw(cards)
            for k,row in enumerate(local):
                col,krow=divmod(k,3)
                i=row['candidate_id'];im=original.copy();draw=ImageDraw.Draw(im)
                draw.rectangle(boxes[i].tolist(),outline=colors[stage[i]],width=2)
                if row['suppressor_id'] != '':
                    draw.rectangle(boxes[row['suppressor_id']].tolist(),outline='lime',width=2)
                im=im.crop((350,170,650,300)).resize((600,260))
                x,y=col*600,krow*310
                cards.paste(im,(x,y+45))
                cd.text((x+5,y+4),f"PTS {t} {row['region']} #{i} {row['score']:.6f} {row['stage']}",fill='white')
                cd.text((x+5,y+21),f"DIAGNOSTIC zoom only | green suppressor #{row['suppressor_id']}",fill='white')
            cards.save(args.output/f'candidate_cards_{t}.jpg',quality=95)

    (args.output/'associations.json').write_text(json.dumps(associations,indent=2))
    with (args.output/'associations.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(associations[0]));writer.writeheader();writer.writerows(associations)
    print(json.dumps({'exact_final_frames':len(rows),'review_images':6,'associations':len(associations)}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['run','baseline','previews','locations','output']:p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args()
    # Ensure unannotated original panel is really available in the reused SSD previews.
    ssd=Path('outputs/cv_phase2a/smoke030/frames.jsonl')
    assert all(not r['detections'] for r in map(json.loads,ssd.read_text().splitlines()) if r['pts'] in [84,88,90,92,94,96])
    main(args)
