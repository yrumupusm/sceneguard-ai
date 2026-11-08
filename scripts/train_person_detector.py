"""EXP68 bounded person-only fitting. CUDA imports/forward follow the canonical guard."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
SETTINGS=dict(epochs=5,batch=2,imgsz=640,seed=68,lr=1e-4,weight_decay=.0005,
              betas=[.9,.999],eps=1e-8,workers=0,amp=False,augmentation=False,
              accumulation=1,warmup_steps=0,loss_box=7.5,loss_cls=.5,loss_dfl=1.5,
              checkpoint_selection='last_epoch5',o2m_initial=.8,o2m_final=.1)


def write(path,value):
    with Path(path).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')


def adapt_person(model):
    """Keep official hidden widths/weights; slice only the six final COCO classifiers."""
    import torch
    head=model.model[-1]
    if head.nc!=80 or head.reg_max!=1:raise ValueError('Official YOLO26 COCO head required')
    evidence=[]
    for name in ('cv3','one2one_cv3'):
        branches=getattr(head,name)
        if len(branches)!=3:raise ValueError('All three detector scales required')
        for index,branch in enumerate(branches):
            old=branch[-1]
            if not isinstance(old,torch.nn.Conv2d) or old.out_channels!=80 or old.kernel_size!=(1,1):
                raise ValueError('Unexpected official final classifier')
            # Deep copy avoids consuming RNG or randomly reinitializing anything.
            new=copy.deepcopy(old);new.out_channels=1
            new.weight=torch.nn.Parameter(old.weight[:1].detach().clone())
            new.bias=torch.nn.Parameter(old.bias[:1].detach().clone())
            branch[-1]=new
            if not torch.equal(new.weight,old.weight[:1]) or not torch.equal(new.bias,old.bias[:1]):
                raise ValueError('Person row transplant failed')
            evidence.append(dict(branch=name,scale=index,input_channels=old.in_channels,
                weight_sha256=hashlib.sha256(new.weight.detach().cpu().numpy().tobytes()).hexdigest(),
                bias_sha256=hashlib.sha256(new.bias.detach().cpu().numpy().tobytes()).hexdigest()))
    head.nc=1;head.no=4*head.reg_max+1;model.names={0:'person'};model.yaml['nc']=1
    model.end2end=True
    return evidence


def image_tensor(row,folder,device):
    import cv2
    import numpy as np
    import torch
    image=cv2.imread(str(folder/row['image']))
    if image is None:raise ValueError('Missing local image')
    h,w=image.shape[:2]
    if [w,h]!=row['source_size']:raise ValueError('Source dimensions differ')
    ratio=640/max(h,w);nw,nh=round(w*ratio),round(h*ratio)
    left=round((640-nw)/2-.1);top=round((640-nh)/2-.1)
    image=cv2.resize(image,(nw,nh),interpolation=cv2.INTER_LINEAR)
    image=cv2.copyMakeBorder(image,top,640-nh-top,left,640-nw-left,cv2.BORDER_CONSTANT,value=(114,114,114))
    rgb=np.ascontiguousarray(image[:,:,::-1].transpose(2,0,1))
    tensor=torch.from_numpy(rgb).to(device=device,dtype=torch.float32).div_(255).unsqueeze(0)
    return tensor,dict(ratio=ratio,left=left,top=top,width=w,height=h,resized_width=nw,resized_height=nh)


def batch_targets(rows,folder,device):
    import torch
    images=[];boxes=[];indices=[]
    for i,row in enumerate(rows):
        image,g=image_tensor(row,folder,device);images.append(image)
        for item in row['confirmed_person_boxes']:
            x1,y1,x2,y2=item['xyxy'];r=g['ratio'];left,top=g['left'],g['top']
            boxes.append([((x1+x2)*r/2+left)/640,((y1+y2)*r/2+top)/640,(x2-x1)*r/640,(y2-y1)*r/640]);indices.append(i)
    return dict(img=torch.cat(images),batch_idx=torch.tensor(indices,device=device,dtype=torch.float32),
        cls=torch.zeros((len(boxes),1),device=device),bboxes=torch.tensor(boxes,device=device,dtype=torch.float32).reshape(-1,4))


def raw_forward(model,image):
    output=model(image)
    if not isinstance(output,tuple) or 'one2one' not in output[1]:raise ValueError('Unfused dual-head output required')
    return output[1]


def predict_set(model,rows,folder,directory,prefix):
    import numpy as np
    import torch
    model.eval();logs=[];raw={}
    with torch.no_grad():
        for row in rows:
            image,g=image_tensor(row,folder,'cuda:0');heads=raw_forward(model,image)
            head=model.model[-1];decoded=head._inference(heads['one2one'])[0].T
            boxes=decoded[:,:4].clone();scores=decoded[:,4]
            boxes[:,[0,2]]=(boxes[:,[0,2]]-g['left'])/g['ratio'];boxes[:,[1,3]]=(boxes[:,[1,3]]-g['top'])/g['ratio']
            boxes[:,[0,2]]=boxes[:,[0,2]].clamp(0,g['width']);boxes[:,[1,3]]=boxes[:,[1,3]].clamp(0,g['height'])
            if not torch.isfinite(boxes).all() or not torch.isfinite(scores).all():raise ValueError('Nonfinite prediction')
            # Native end2end top300 (single class); never an added NMS.
            index=torch.topk(scores,min(300,len(scores)),sorted=True).indices
            index=index[scores[index]>=.05]
            index=index[(boxes[index,2]>boxes[index,0]) & (boxes[index,3]>boxes[index,1])]
            logs.append(dict(frame_id=row['frame_id'],image_sha256=row['image_sha256'],source_pts=row['source_pts'],
                boxes=boxes[index].cpu().tolist(),person_scores=scores[index].cpu().tolist(),
                box_format='xyxy_original_input_pixels',retained_threshold=.05,display_threshold=.5,
                native_class_ids=[0]*len(index),event_group=row['event_group']))
            # All8400 anchors, without confidence filtering or topk; invalid geometry remains explicit.
            raw[row['frame_id']]=torch.cat([boxes,scores[:,None]],dim=1).cpu().numpy()
    target=directory/(prefix+'-predictions.jsonl')
    with target.open('x',encoding='utf-8') as f:
        for row in logs:f.write(json.dumps(row,allow_nan=False)+'\n')
    np.savez_compressed(directory/(prefix+'-all-anchors.npz'),**raw)
    return logs


def loss_items(items):
    # Pinned8.4.192 returns named detached scalars, not the historical tensor vector.
    if not isinstance(items,dict) or not items:raise ValueError('Native named loss items required')
    return {key:float(value.detach().cpu()) for key,value in items.items()}


def finite_state(model,optimizer):
    import torch
    tensors=list(model.state_dict().values())
    for state in optimizer.state.values():tensors.extend(v for v in state.values() if torch.is_tensor(v))
    if any(not torch.isfinite(t).all() for t in tensors):raise ValueError('Nonfinite weights/optimizer state')


def checkpoint(path,model,optimizer,epoch,steps):
    import torch
    finite_state(model,optimizer)
    # Native model plus complete state allows exact direct and official loads; no stripping or EMA.
    torch.save(dict(model=copy.deepcopy(model).cpu(),state_dict={k:v.detach().cpu() for k,v in model.state_dict().items()},
        optimizer=optimizer.state_dict(),epoch=epoch,optimizer_steps=steps,settings=SETTINGS),path)


def execute(args):
    from orchestration import person_detector_training_command as command
    from orchestration.queue import digest
    config,inputs=command.runner_guard(args)  # Before importing CUDA/model dependencies.
    directory=args.output;directory.mkdir(parents=True,exist_ok=False)
    start=time.monotonic()
    from scripts.exp0066_yolo import configure_offline
    configure_offline(directory)
    os.environ['CUBLAS_WORKSPACE_CONFIG']=':4096:8'
    import numpy as np
    import torch
    import ultralytics
    from ultralytics import YOLO
    from ultralytics.utils import SETTINGS as ULTRA_SETTINGS
    from types import SimpleNamespace
    ULTRA_SETTINGS.update({k:False for k in ('sync','clearml','comet','dvc','mlflow','raytune','tensorboard','wandb')})
    if ultralytics.__version__!='8.4.192':raise ValueError('Pinned Ultralytics required')
    torch.set_num_threads(4);random.seed(68);np.random.seed(68);torch.manual_seed(68);torch.cuda.manual_seed_all(68)
    torch.use_deterministic_algorithms(True);torch.backends.cudnn.benchmark=False
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    torch.cuda.reset_peak_memory_stats()
    manifest=command.read(command.DATASET);rows=manifest['frames'];folder=command.DATASET.parent
    train=[r for r in rows if r['split']=='train'];val=[r for r in rows if r['split']=='validation']
    model=YOLO(config['checkpoint_path'],task='detect').model.float()
    model.end2end=True
    # All25 validation inputs, both raw heads: exact official-person parity before any optimizer step.
    official=model.to('cuda:0').eval();parity_reference={}
    with torch.no_grad():
        for row in val:
            image,_=image_tensor(row,folder,'cuda:0');heads=raw_forward(official,image)
            parity_reference[row['frame_id']]={name:dict(boxes=p['boxes'].cpu(),scores=p['scores'][:,:1].cpu()) for name,p in heads.items()}
    transplant=adapt_person(model)
    parity=[]
    with torch.no_grad():
        for row in val:
            image,_=image_tensor(row,folder,'cuda:0');heads=raw_forward(model,image)
            for name,p in heads.items():
                old=parity_reference[row['frame_id']][name]
                for key in ('boxes','scores'):
                    delta=(p[key].cpu()-old[key]).abs().max().item()
                    # CUDA final Conv shape may change kernel; accept FP32 roundoff only, report actual max.
                    if not torch.allclose(p[key].cpu(),old[key],atol=1e-5,rtol=1e-6):raise ValueError('Pretrained person parity failed')
                    parity.append(dict(frame_id=row['frame_id'],branch=name,tensor=key,max_abs_difference=delta))
    del parity_reference
    write(directory/'person-adaptation.json',dict(transplant=transplant,parity=parity,random_classifier=False,
        parity_tolerance=dict(atol=1e-5,rtol=1e-6),official80_to_person1=True))
    model.args=SimpleNamespace(box=7.5,cls=.5,dfl=1.5,epochs=5)
    for p in model.parameters():p.requires_grad_(True)
    optimizer=torch.optim.AdamW(model.parameters(),lr=1e-4,betas=(.9,.999),eps=1e-8,weight_decay=.0005)
    initial={k:p.detach().cpu().clone() for k,p in model.named_parameters()}
    checkpoint(directory/'initial.pt',model,optimizer,0,0)
    predict_set(model,val,folder,directory,'before')
    steps=0;epochs=[]
    log=(directory/'optimizer-steps.jsonl').open('x',encoding='utf-8')
    try:
        for epoch in range(1,6):
            model.train();order=list(range(len(train)));random.Random(68+epoch).shuffle(order);losses=[];seen=[]
            for offset in range(0,50,2):
                selected=[train[i] for i in order[offset:offset+2]];seen.extend(r['frame_id'] for r in selected)
                batch=batch_targets(selected,folder,'cuda:0');optimizer.zero_grad(set_to_none=True)
                loss,items=model(batch);scalar=loss.sum()
                if not torch.isfinite(scalar):raise ValueError('Nonfinite loss')
                scalar.backward()
                gradients=[p.grad for p in model.parameters() if p.grad is not None]
                if not gradients or any(not torch.isfinite(g).all() for g in gradients):raise ValueError('Missing/nonfinite gradients')
                grad_norm=torch.nn.utils.clip_grad_norm_(model.parameters(),10.0,error_if_nonfinite=True)
                optimizer.step();steps+=1
                event=dict(epoch=epoch,step=steps,frame_ids=[r['frame_id'] for r in selected],loss=scalar.item(),
                    native_loss_items=loss_items(items),grad_norm_before_clip=float(grad_norm),lr=1e-4)
                log.write(json.dumps(event,allow_nan=False)+'\n');log.flush();losses.append(scalar.item())
            finite_state(model,optimizer)
            epochs.append(dict(epoch=epoch,optimizer_steps=steps,frames=seen,mean_loss=sum(losses)/len(losses),
                o2m_gain=model.criterion.o2m,o2o_gain=model.criterion.o2o))
            if epoch<5:model.criterion.update()
            print(json.dumps(epochs[-1]),flush=True)
    finally:log.close()
    if steps!=125:raise ValueError('Exactly125 actual optimizer updates required')
    changed=[k for k,p in model.named_parameters() if not torch.equal(initial[k],p.detach().cpu())]
    head_prefix=f'model.{len(model.model)-1}.'
    groups={name:[k for k in changed if predicate(k)] for name,predicate in {
        'backbone':lambda k:k.startswith('model.0.'),
        'one2many_classifier':lambda k:k.startswith(head_prefix+'cv3.'),
        'one2one_classifier':lambda k:k.startswith(head_prefix+'one2one_cv3.'),
        'one2many_box':lambda k:k.startswith(head_prefix+'cv2.'),
        'one2one_box':lambda k:k.startswith(head_prefix+'one2one_cv2.')}.items()}
    if not changed or any(not v for v in groups.values()):raise ValueError('Backbone and both box/classifier heads must change')
    checkpoint(directory/'last.pt',model,optimizer,5,steps)
    predict_set(model,val,folder,directory,'after')
    write(directory/'epochs.json',epochs)
    # Reverify selected input/source bytes once after execution, no corpus-wide audit.
    if command.input_contract(config)!=inputs:raise ValueError('Training inputs changed')
    artifacts={p.name:command.file_hash(p) for p in directory.iterdir() if p.is_file()}
    result=dict(status='person_pilot_trained',queue_command='person-detector-train',queue_attempt=args.queue_attempt,
        code_sha=command.read(command.checked_file(config['authorization']))['code_sha'],source_hash=digest(command.sources()),
        input_hash=digest(inputs),manifest_sha256=command.DATASET_SHA,settings=SETTINGS,
        optimizer_steps=steps,epochs=5,frame_counts={'train':50,'validation':25},box_counts={'train':151,'validation':31},
        changed_parameter_groups=groups,changed_parameter_tensors=len(changed),changed_parameters=changed,finite_weights_and_optimizer=True,
        artifacts=artifacts,elapsed_seconds=time.monotonic()-start,gpu_peak_allocated=torch.cuda.max_memory_allocated(),
        gpu_peak_reserved=torch.cuda.max_memory_reserved(),validation_groups=1,validation_frames_correlated=True,
        school_inference=False,action_labels_used=False,other_models_trained=False,
        limitations=['Execution smoke/smallfit, not school improvement or independent generalization',
            '25validation frames from one event; explicit human labels derived from reviewed YOLO26x proposals'])
    write(directory/'result.json',result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--queue-config',required=True);p.add_argument('--queue-config-sha256',required=True)
    p.add_argument('--queue-attempt',required=True);p.add_argument('--output',type=Path,required=True)
    execute(p.parse_args())
