"""Fixed EXP0066 CPU linear heads. Real-data fitting is canonical-queue-only."""
import copy
import hashlib
import json
import math
from pathlib import Path

PROTOCOL=dict(seed=66,epochs=100,batch_size=128,optimizer='Adam',learning_rate=.01,
              weight_decay=.0001,standardization='train_only_population_std_zero_to_one',
              training_loss='balanced_train_class_weighted_binary_cross_entropy',
              epoch_selection='minimum_unweighted_validation_cross_entropy_first_tie',
              threshold_selection='strict_validation_negative_quantile_fpr_at_most_0.05',max_reference_fpr=.05)


def strict_threshold(scores,labels):
    import numpy as np
    values=np.asarray(scores,dtype=np.float64);ys=np.asarray(labels)
    if values.ndim!=1 or ys.shape!=values.shape or not len(values) or not np.isfinite(values).all():raise ValueError('Empty/nonfinite validation scores')
    if set(ys.tolist())!={0,1}:raise ValueError('Both validation classes required')
    if ((values<0)|(values>1)).any():raise ValueError('Probabilities required')
    negatives=sorted(values[ys==0],reverse=True);allowed=len(negatives)//20
    boundary=float(negatives[allowed]);threshold=float(np.nextafter(boundary,np.inf))
    predicted=values>=threshold;fp=int(predicted[ys==0].sum())
    if fp>allowed:raise ValueError('Strict reference FPR bound failed')
    tp=int(predicted[ys==1].sum());fn=int((~predicted[ys==1]).sum());tn=len(negatives)-fp
    return dict(threshold=threshold,boundary_score=boundary,tie_policy='float64_nextafter_toward_positive_infinity',
                threshold_status='provisional_official_reference_not_human_calibrated',
                matched_false_positive_operating_point_verified=False,
                negative_count=len(negatives),allowed_false_positives=allowed,false_positives=fp,
                reference_fpr=fp/len(negatives),tp=tp,fp=fp,tn=tn,fn=fn,
                reference_precision=tp/(tp+fp) if tp+fp else None,reference_recall=tp/(tp+fn),
                human_precision=None,human_recall=None)


def feature_dataset(path,plan,joint,require_both=True):
    windows={w['window_id']:w for w in plan['windows']};seen=set();x=[];y=[];splits=[];keys=[];dim=None
    def invalid(value):raise ValueError('Nonfinite JSON constant: '+value)
    with Path(path).open(encoding='utf-8') as stream:
        for line in stream:
            row=json.loads(line,parse_constant=invalid);wid=row['window_id']
            if wid in seen or wid not in windows:raise ValueError('Duplicate/unselected feature window')
            seen.add(wid);w=windows[wid]
            if row['split']!=w['split'] or row['source_sha256']!=w['source_sha256']:raise ValueError('Feature split/source changed')
            queries=set()
            if not joint and len(row['samples'])!=1:raise ValueError('Exactly one encoder scene sample required')
            for sample in row['samples']:
                q=sample['query_index'];values=sample['feature'];label=sample['label']
                if q in queries or (joint and (type(q)!=int or q<0 or len(values)!=80)) or (not joint and q is not None):raise ValueError('Invalid/duplicate query weight')
                queries.add(q)
                if label not in (0,1) or label!=w['label'] or sample['weight_count']!=1:raise ValueError('Invalid reference label/weight')
                if not values or any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in values):raise ValueError('Empty/nonfinite features')
                if dim is None:dim=len(values)
                if dim!=len(values):raise ValueError('Feature dimension changed')
                x.append(values);y.append(label);splits.append(w['split']);keys.append([wid,q])
    if seen!=set(windows) or not x:raise ValueError('Incomplete/empty full feature dataset')
    if require_both:
        for split in ('train','validation'):
            if {label for label,s in zip(y,splits) if s==split}!={0,1}:raise ValueError('Actual matching must contain both classes in '+split)
    return x,y,splits,keys


def fit_linear(x,y,splits,history_sink=None):
    """Pure CPU implementation also exercised with synthetic counterexamples."""
    import torch
    torch.set_num_threads(2);torch.manual_seed(PROTOCOL['seed'])
    x=torch.tensor(x,dtype=torch.float32,device='cpu');y=torch.tensor(y,dtype=torch.float32,device='cpu')
    if x.ndim!=2 or not x.shape[0] or x.shape[0]!=len(y) or not torch.isfinite(x).all() or len(splits)!=len(y):raise ValueError('Empty/nonfinite fitting input')
    if any(s not in ('train','validation') for s in splits):raise ValueError('Protected/unknown fitting split')
    tr=torch.tensor([s=='train' for s in splits]);va=~tr
    for mask in (tr,va):
        if set(y[mask].tolist())!={0.,1.}:raise ValueError('Both classes required in actual train and validation')
    mean=x[tr].mean(0);std=x[tr].std(0,unbiased=False);std=torch.where(std==0,torch.ones_like(std),std)
    z=(x-mean)/std
    if not torch.isfinite(z).all():raise ValueError('Nonfinite standardized features')
    counts=torch.bincount(y[tr].long(),minlength=2);weights=tr.sum()/(2*counts.float())
    model=torch.nn.Linear(x.shape[1],1,device='cpu');optimizer=torch.optim.Adam(model.parameters(),lr=.01,weight_decay=.0001)
    train_indices=tr.nonzero().flatten();generator=torch.Generator(device='cpu').manual_seed(66)
    best_loss=math.inf;best=None;best_epoch=None;history=[]
    for epoch in range(1,101):
        model.train();loss_sum=0.;order=train_indices[torch.randperm(len(train_indices),generator=generator)]
        for batch in order.split(128):
            optimizer.zero_grad(set_to_none=True);logits=model(z[batch]).flatten()
            loss=(torch.nn.functional.binary_cross_entropy_with_logits(logits,y[batch],reduction='none')*weights[y[batch].long()]).mean()
            if not torch.isfinite(loss):raise ValueError('Nonfinite training loss')
            loss.backward();optimizer.step();loss_sum+=loss.item()*len(batch)
        model.eval()
        with torch.no_grad():val_loss=torch.nn.functional.binary_cross_entropy_with_logits(model(z[va]).flatten(),y[va]).item()
        if not math.isfinite(val_loss):raise ValueError('Nonfinite validation loss')
        history.append(dict(epoch=epoch,train_ce=loss_sum/len(train_indices),validation_ce=val_loss))
        if history_sink:history_sink(history[-1])
        if val_loss<best_loss:best_loss=val_loss;best=copy.deepcopy(model.state_dict());best_epoch=epoch
    model.load_state_dict(best)
    with torch.no_grad():scores=torch.sigmoid(model(z[va]).flatten()).double().tolist()
    selection=strict_threshold(scores,y[va].long().tolist())
    return dict(state_dict=best,mean=mean,std=std,feature_dimension=x.shape[1],selected_epoch=best_epoch,
                class_counts=counts.tolist(),class_weights=weights.tolist(),history=history,selection=selection,
                validation_scores=scores,validation_labels=y[va].long().tolist())


def score_features(head,features):
    """CPU advisory scoring; threshold frozen before any protected school output use."""
    import torch
    values=torch.as_tensor(features,dtype=torch.float32,device='cpu')
    if values.ndim!=2 or values.shape[1]!=head['feature_dimension'] or not len(values) or not torch.isfinite(values).all():raise ValueError('Invalid scoring features')
    if (head['mean'].shape!=(head['feature_dimension'],) or head['std'].shape!=(head['feature_dimension'],)
            or not torch.isfinite(head['mean']).all() or not torch.isfinite(head['std']).all()
            or not (head['std']>0).all() or not math.isfinite(head['selection']['threshold'])
            or any(not torch.isfinite(v).all() for v in head['state_dict'].values())):raise ValueError('Invalid frozen CPU head')
    model=torch.nn.Linear(head['feature_dimension'],1,device='cpu');model.load_state_dict(head['state_dict']);model.eval()
    with torch.no_grad():scores=torch.sigmoid(model((values-head['mean'])/head['std']).flatten()).double().tolist()
    if not all(math.isfinite(v) for v in scores):raise ValueError('Nonfinite head scores')
    return [dict(climbing_action_score=v,climbing_action_candidate=v>=head['selection']['threshold'],
                 threshold_status='provisional_official_reference_not_human_calibrated',
                 matched_false_positive_operating_point_verified=False,
                 intrusion_completed=None,intrusion_state_changed=False) for v in scores]


def train(config,output,attempt,inputs):
    import torch
    from orchestration.comparison_head_command import JOINT,file_hash,read,sources,input_contract
    from orchestration.queue import digest
    from scripts.extract_comparison_head_features import audit_native_outputs
    snapshot=sources(config);plan=read(config['files']['plan']['path'])
    native=Path(config['files']['features']['path']).parent/'native-outputs.jsonl'
    coverage=audit_native_outputs(native,config['files']['features']['path'],plan,config['model_id'] in JOINT)
    scope='conditional_on_matched_automatic_queries' if config['model_id'] in JOINT else 'weak_full_scene_not_actor_specific'
    x,y,splits,keys=feature_dataset(config['files']['features']['path'],plan,config['model_id'] in JOINT)
    with (output/'history.jsonl').open('x',encoding='utf-8') as history_stream:
        def history_sink(row):
            history_stream.write(json.dumps(row,sort_keys=True,allow_nan=False)+'\n');history_stream.flush()
        head=fit_linear(x,y,splits,history_sink)
    torch.save({**head, 'protocol':PROTOCOL,'model_id':config['model_id'],
                'feature_source':config['files']['features'],'plan':config['files']['plan'],
                'native_outputs':inputs['feature_native_output'],'coverage_by_split':coverage,'validation_metric_scope':scope,
                'feature_result':read(config['authorization']['path'])['feature_result'],
                'feature_receipt':read(config['authorization']['path'])['feature_receipt'],
                'input_hash':digest(inputs),'source_hash':digest(snapshot)},output/'head.pt')
    (output/'history.json').write_text(json.dumps(head['history'],sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    (output/'selection.json').write_text(json.dumps(dict(protocol=PROTOCOL,selected_epoch=head['selected_epoch'],
                selection=head['selection'],validation_scores=head['validation_scores'],validation_labels=head['validation_labels'],
                class_counts=head['class_counts'],class_weights=head['class_weights'],sample_keys=keys,
                validation_metric_scope=scope,coverage_by_split=coverage,
                native_outputs=inputs['feature_native_output']),sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    if sources(config)!=snapshot or input_contract(config)!=inputs:raise ValueError('Source/input changed during CPU fitting')
    return dict(status='head_trained',queue_command='comparison-head',queue_attempt=attempt,stage='train',
                model_id=config['model_id'],input_hash=digest(inputs),source_hash=digest(snapshot),
                code_sha=read(config['authorization']['path'])['code_sha'],plan_sha256=config['files']['plan']['sha256'],
                model_spec_sha256=config['files']['model_spec']['sha256'],head_sha256=file_hash(output/'head.pt'),
                history_sha256=file_hash(output/'history.json'),selection_sha256=file_hash(output/'selection.json'),
                history_stream_sha256=file_hash(output/'history.jsonl'),
                protocol_sha256=digest(PROTOCOL),selected_epoch=head['selected_epoch'],selection=head['selection'],
                sample_count=len(x),feature_dimension=head['feature_dimension'],
                native_outputs_sha256=file_hash(native),coverage_by_split=coverage,validation_metric_scope=scope,
                person_score_policy='all_valid_queries_no_person_score_threshold' if config['model_id'] in JOINT else None,
                original_person_threshold=read(config['files']['model_spec']['path'])['output_postfilter']['original_person_threshold'] if config['model_id'] in JOINT else None,
                matched_native_person_operating_point_verified=False,
                official_reference_only=True,semantic_ground_truth_verified=False,
                validation_normal_subtypes='sitting_only; walking/waiting/turnback unmeasured',
                human_precision=None,human_recall=None,intrusion_completed=None,intrusion_state_changed=False,
                threshold_status='provisional_official_reference_not_human_calibrated',
                matched_false_positive_operating_point_verified=False)
