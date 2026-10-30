"""EXP-0031 one-shot, offline representative-quality comparison.

Reads preserved EXP-0029 observations/tracklets; selects alternative crops;
reuses exact saved embeddings when possible; runs only necessary new CPU ReID.
Does not write new IDs into EXP-0030, touch polygons, infer real identity,
or train/detect. Alternative associations are an unadopted experiment.
"""
import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
import time

import numpy as np

from .exp0031_quality import (SelectionPolicy, choose_representatives,
                              build_feature_map, changed_pair_report)
from .run_tracklet_linking import (load_inputs, read_jsonl, sha256, REID_SHA,
                                    create_encoder, decode_native, validate_features,
                                    write_json)
from .tracklet_linking import (LinkSettings, build_tracklets, endpoint_rows,
                                link_tracklets, unit_features)
from .mvp_review_quality import QUESTION_PAIRS


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def encode_alternatives(video, cached, selected, old_map, *, weights,
                        interval, review_dir, encoder_factory=create_encoder,
                        decoder=decode_native):
    """Only new (frame_index,cache_index) crops are sent to pinned pretrained encoder."""
    needed = { (r['frame_index'],r['cache_index']):r
               for endpoints in selected.values() for rows in endpoints.values()
               for r in rows if (r['frame_index'],r['cache_index']) not in old_map}
    new_map = {}
    calls=0
    load_seconds=encode_seconds=encode_cpu_seconds=0.
    model_batches=[]
    model_info={}
    forward_hook=None
    if needed:
        started=time.perf_counter()
        encoder=encoder_factory(weights, interval)
        load_seconds=time.perf_counter()-started
        model=getattr(encoder,'model',None)
        if model is not None:
            # Observe real model calls without changing crop selection or inference.
            forward_hook=model.register_forward_pre_hook(
                lambda _model,args: model_batches.append(int(args[0].shape[0])))
            model_info=dict(providers=model.session.get_providers(),
                            input_shape=model.session.get_inputs()[0].shape,
                            crop_size=list(encoder.imgsz),batch_size=encoder.batch_size,
                            fp16=encoder.fp16,device=str(encoder.device))
        by_frame={}
        for key, row in needed.items():
            by_frame.setdefault(key[0],[]).append((key,row))
        review_dir.mkdir(parents=True,exist_ok=False)
        width, height = cached[0]['source_size']
        for frame_index, bgr in decoder(video,cached):
            if frame_index not in by_frame:
                continue
            if bgr.shape != (height,width,3) or bgr.dtype != np.uint8:
                raise ValueError('Original BGR decoding mismatch')
            batch=by_frame[frame_index]
            boxes=np.array([r['bbox'] for _,r in batch],dtype=float)*[width,height,width,height]
            xywh=boxes.copy()
            xywh[:,2:]-=xywh[:,:2]
            xywh[:,:2]+=xywh[:,2:]/2
            started=time.perf_counter()
            cpu_started=time.process_time()
            returned=encoder(bgr, xywh)
            encode_cpu_seconds+=time.process_time()-cpu_started
            encode_seconds+=time.perf_counter()-started
            calls+=1
            if len(returned)!=len(batch):
                raise ValueError('ReID feature count mismatch')
            for (key,_), feature, box in zip(batch,returned,boxes):
                vector=unit_features([feature])[0]
                if vector.size!=512:
                    raise ValueError('Expected original 512-dimensional pretrained ReID features')
                new_map[key]=vector
                # Keep full-resolution review crops local; never upload to GitHub.
                import cv2
                x1,y1,x2,y2=box
                crop=bgr[max(0,math.floor(y1)):min(height,math.ceil(y2)),
                         max(0,math.floor(x1)):min(width,math.ceil(x2))]
                if not crop.size or not cv2.imwrite(str(review_dir/f'frame{key[0]:06d}_cache{key[1]:03d}.jpg'),crop):
                    raise ValueError('Could not write local representative crop')
        if set(new_map)!=set(needed):
            raise ValueError('Not all required native frames were decoded/encoded')
        if forward_hook is not None:
            forward_hook.remove()
    features={}
    for sid,endpoints in selected.items():
        features[sid]={}
        for end,rows in endpoints.items():
            features[sid][end]=[(old_map.get((r['frame_index'],r['cache_index']))
                                 if (r['frame_index'],r['cache_index']) in old_map
                                 else new_map[(r['frame_index'],r['cache_index'])]).tolist()
                                for r in rows]
    selected_keys=[(r['frame_index'],r['cache_index'])
        for endpoints in selected.values() for rows in endpoints.values() for r in rows]
    return features,dict(previous_embeddings_reused=sum(
        (r['frame_index'],r['cache_index']) in old_map
        for endpoints in selected.values() for rows in endpoints.values() for r in rows),
        distinct_new_crops=len(new_map),encoder_calls=calls,
        selected_slots=len(selected_keys),distinct_selected_crops=len(set(selected_keys)),
        distinct_reused_crops=len(set(selected_keys)&set(old_map)),
        new_embedding_slots=sum(key not in old_map for key in selected_keys),
        real_model_forwards=len(model_batches) if model_info or not needed else None,
        model_forward_batch_sizes=model_batches,encoder_runtime=model_info,
        encoder_initialization_including_any_warmup_seconds=load_seconds,
        crop_encoder_elapsed_seconds=encode_seconds,crop_encoder_process_cpu_seconds=encode_cpu_seconds,
        original_feature_count=len(old_map),device='existing_pinned_CPU_ReID_only_if_needed')


def question_comparison(video_key, segments, baseline_features, alternate_features,
                        original_associations, alternate_associations):
    names=QUESTION_PAIRS[video_key]
    before_old={(r['before'],r['after']):r for r in original_associations['links']}
    before_new={(r['before'],r['after']):r for r in alternate_associations['links']}
    by_id={s['id']:s for s in segments}
    result=[]
    for q, before, after in names:
        a,b=by_id[before],by_id[after]
        gap=b['start']-a['end']
        def sim(feats):
            left=unit_features(feats[before]['tail'])
            right=unit_features(feats[after]['head'])
            return float(np.median(np.clip(left@right.T,-1,1)))
        old, new=before_old.get((before,after)),before_new.get((before,after))
        # Outside 5-second/geometry gates remains audit-only; cannot auto-associate.
        result.append(dict(question=q,before_tracklet=before,after_tracklet=after,
                           before_raw_id=a['raw_id'],after_raw_id=b['raw_id'],
                           gap_seconds=gap,baseline_similarity=sim(baseline_features),
                           alternate_similarity=sim(alternate_features),
                           baseline_status=old['status'] if old else 'outside_original_gates',
                           alternate_status=new['status'] if new else 'outside_original_gates',
                           adopted=False,identity_verified=False,
                           requires_human_review=True))
    return result


def run(cache, tracks, video, prior, weights, out, policy=SelectionPolicy(),
        *, encoder_factory=create_encoder, decoder=decode_native):
    started=time.perf_counter()
    cpu_started=time.process_time()
    policy.validate()
    out=Path(out)
    if (not out.resolve().is_relative_to(Path('outputs').resolve())
          or out.exists() or out.is_symlink() or any(p.is_symlink() for p in out.parents)):
        raise FileExistsError('EXP-0031 must use a NEW non-symlink local outputs/ directory')
    meta,cached,tracked,interval,hashes=load_inputs(cache,tracks,video)
    original={name:read(Path(prior)/f'{name}.json') for name in
              ('tracklets','representatives','associations','summary')}
    features_saved=read(Path(prior)/'features.local.json')
    settings=LinkSettings(**original['associations']['settings']).validate()
    if (original['summary']['source_hashes'] != hashes or
          features_saved['binding'] != dict(inputs=hashes,weights=REID_SHA,settings=asdict(settings))):
        raise ValueError('EXP-0029 features are not bound to this source/settings')
    if sha256(weights)!=REID_SHA:
        raise ValueError('Original pretrained ReID weight SHA mismatch')
    segments=build_tracklets(tracked,settings)
    if segments!=original['tracklets']:
        raise ValueError('Historical tracklets differ from frozen observed data')
    baseline_select={s['id']:{end:endpoint_rows(s,end,settings) for end in ('head','tail')}
                     for s in segments if s['eligible']}
    if baseline_select!=original['representatives']:
        raise ValueError('Original representatives do not match baseline selection')
    validate_features(features_saved['features'],baseline_select)
    original_computed=link_tracklets(segments,features_saved['features'],settings)
    if original_computed!=original['associations']:
        raise ValueError('Cannot reproduce immutable original associations')
    selected,audit=choose_representatives(segments,tracked,policy)
    old_map=build_feature_map(original['representatives'],features_saved)
    protected_inputs = ([Path(prior)/name for name in ('features.local.json','representatives.json',
                      'tracklets.json','associations.json','summary.json')] +
                      [Path(tracks),Path(video),Path(weights)])
    frozen_hashes = {str(path):sha256(path) for path in protected_inputs}
    out.mkdir(parents=True,exist_ok=False)
    try:
        alternate_features,reuse=encode_alternatives(video,cached,selected,old_map,
            weights=weights,interval=interval,review_dir=out/'new_representative_crops',
            encoder_factory=encoder_factory,decoder=decoder)
        validate_features(alternate_features,selected)
        new_associations=link_tracklets(segments,alternate_features,settings)
        comparison=changed_pair_report(segments,original['associations'],new_associations,audit)
        video_key=meta['video_id'].split('_')[-1]
        if video_key not in QUESTION_PAIRS:
            raise ValueError('Only original development clips 030/007 are supported')
        questions=question_comparison(video_key,segments,features_saved['features'],
                          alternate_features,original['associations'],new_associations)
        old_auto={(r['before'],r['after']) for r in original['associations']['links'] if r['status']=='accepted'}
        new_auto={(r['before'],r['after']) for r in new_associations['links'] if r['status']=='accepted'}
        internal_appearance = {}
        for sid, pair in alternate_features.items():
            h, t = unit_features(pair['head']), unit_features(pair['tail'])
            med = float(np.median(np.clip(h @ t.T,-1,1)))
            internal_appearance[sid] = dict(head_to_tail_cosine_median=med,
                    possible_appearance_change_or_person_mix=(med < .65),
                    identity_verified=False, cause='unknown_pose_crop_or_id_switch')
        summary=dict(status='comparison_complete_requires_human_identity_review',
                     experiment='EXP-0031',video_id=meta['video_id'],
                     baseline_accepted=len(old_auto),alternative_algorithm_accepted=len(new_auto),
                     new_accepted_not_adopted=sorted([list(x) for x in new_auto-old_auto]),
                     old_accepted_not_adopted=sorted([list(x) for x in old_auto-new_auto]),
                     endpoint_clean_proxies=sum(v['clean_endpoint_proxy']
                         for ends in audit.values() for v in ends.values()),
                     endpoint_total=sum(len(ends) for ends in audit.values()),
                     reuse=reuse,identity_verified=False,accuracy=None,
                     polygon_status='untouched_current_user_config',
                     detector_forwards=0,tracker_forwards=0,
                     elapsed_seconds_through_comparison=time.perf_counter()-started,
                     process_cpu_seconds_through_comparison=time.process_time()-cpu_started,
                     note='Fixed quality-aware selection package (window and risk ranking); alternate associations are experimental only')
        for name,value in (('selected_representatives',selected),('selection_audit',audit),
                           ('alternative_features.local',dict(features=alternate_features)),
                           ('alternative_associations',new_associations),
                           ('raw_id_appearance_warnings',internal_appearance),
                           ('paired_comparison',comparison),('question_comparison',questions),
                           ('summary',summary)):
            write_json(out/(name+'.json'),value)
        if any(sha256(path) != frozen_hashes[str(path)] for path in protected_inputs):
            raise ValueError('Historical inputs changed during EXP-0031')
        provenance=dict(input_sha256=frozen_hashes,
                        settings=asdict(settings),selection_policy=asdict(policy),
                        old_files_unchanged=True,model='EXP-0028 pretrained 512D CPU encoder')
        write_json(out/'provenance.json',provenance)
        return summary
    except Exception as exc:
        write_json(out/'failure.json',dict(type=type(exc).__name__,message=str(exc)))
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache',type=Path,required=True)
    p.add_argument('--tracks',type=Path,required=True)
    p.add_argument('--video',type=Path,required=True)
    p.add_argument('--prior',type=Path,required=True)
    p.add_argument('--weights',type=Path,default=Path('weights/exp0028/yolo26n-reid.onnx'))
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    result=run(a.cache,a.tracks,a.video,a.prior,a.weights,a.output)
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))


if __name__=='__main__':
    main()
