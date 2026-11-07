"""Prepare a new full-frame official-reference task-head plan; never releases semantics or trains."""
import argparse
from collections import Counter,defaultdict
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'outputs/action-recognition/exp0063/clip-plan-v2/candidate-manifest.json'
SPLIT=ROOT/'outputs/action-recognition/exp0063/combined-split-v3/split-manifest.json'
BASELINE=ROOT/'outputs/action-recognition/exp0063/baseline/attempt-002/baseline-lock.json'
SHA_MANIFEST='72912fab027a068d0e6043f328d86a2c7d15a239afa751d126984c5c10498931'
SHA_SPLIT='bfb0f9fcd570794036cc6d2eaad46f988679b612996e21282a34821203ad5499'
SHA_BASELINE='3799ae3eee427b60e698b21f6ee958ac5306eacba07b5d85e4c35dbfa6457b40'


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def window_for(row,label):
    # Use only the previously released actual native eight-frame interior.
    pts=[Fraction(t)*Fraction(row['time_base']) for t in row['sample_pts_ticks']]
    if len(pts)!=8 or any(b-a!=Fraction(1,3) for a,b in zip(pts,pts[1:])):
        raise ValueError('existing_native_8frame_contract_changed')
    anchor=(pts[0]+pts[-1])/2
    requested=[anchor+Fraction(i-8)*Fraction(4,30) for i in range(16)]
    if min(requested)<pts[0] or max(requested)>pts[-1]:raise ValueError('outside_released_interior')
    selected=[min(range(8),key=lambda j:(abs(pts[j]-t),pts[j])) for t in requested]
    frames=[row['sample_frame_indices'][j] for j in selected]
    required=set(frames)|{i+1 for i in frames}
    annotations=label['annotations'];by_frame=defaultdict(list);classes=defaultdict(set)
    for ann in annotations:
        classes[ann['actor_id'],ann['object_id']].add(ann['class_name'])
        if ann['actor_id']==row['actor_id']:by_frame[ann['cur_frame']].append(ann)
    for f in required:
        matching=[a for a in by_frame[f] if a['object_id']==row['object_id']]
        if len(matching)!=1 or any(a['class_name']!=row['action_class'] for a in by_frame[f]):
            raise ValueError('missing_or_ambiguous_selected_actor_action')
        box=matching[0]['bbox'];(x1,y1),(x2,y2)=box
        if not all(math.isfinite(x) for x in (x1,y1,x2,y2)) or not (0<=x1<x2<=row['source_width'] and 0<=y1<y2<=row['source_height']):
            raise ValueError('invalid_selected_actor_box')
    for i,e in enumerate(label['events']):
        if e['ev_start_frame']>max(required) or e['ev_end_frame']<min(required):continue
        if i!=row['event_index'] and e['actor_id']==row['actor_id']:
            raise ValueError('overlapping_actor_events')
        if row['label']==0 and 'wall_over' in classes[e['actor_id'],e['object_id']]:
            raise ValueError('source_wide_wall_event_conflict')
    if row['label']==0 and any(a['class_name']=='wall_over' and a['cur_frame'] in required for a in annotations):
        raise ValueError('source_wide_wall_annotation_conflict')
    anchor_j=min(range(8),key=lambda j:(abs(pts[j]-anchor),pts[j]))
    af=row['sample_frame_indices'][anchor_j]
    boxes=[next(a['bbox'] for a in by_frame[f] if a['object_id']==row['object_id']) for f in (af,af+1)]
    target=dict(actor_id=row['actor_id'],object_id=row['object_id'],label=row['label'],action_class=row['action_class'],
                anchor_boxes_origin0_origin1=boxes,source_clip_id=row['clip_id'],event_index=row['event_index'],
                annotation_matching_policy='require_same_query_overlap_both_origins; unmatched_queries_unknown')
    for key in ('source_id','source_path','source_sha256','label_path','label_sha256'):
        if key in row:target[key]=row[key]
    target['anchor_frame_index']=af
    target['anchor_pts']=float(pts[anchor_j])
    return dict(anchor_pts=float(anchor),sample_requested_pts=list(map(float,requested)),sample_frame_indices=frames,
                sample_pts=[float(pts[j]) for j in selected],sample_pts_ticks=[row['sample_pts_ticks'][j] for j in selected],
                observed_unique_frames=len(set(frames)),duplicate_mask=[i in frames[:j] for j,i in enumerate(frames)],
                available_after_pts=float(max(pts[j] for j in selected)),target=target)


def prepare(output):
    for p,h in ((MANIFEST,SHA_MANIFEST),(SPLIT,SHA_SPLIT),(BASELINE,SHA_BASELINE)):
        if sha(p)!=h:raise ValueError('Protected source manifest changed')
    original=read(MANIFEST);split=read(SPLIT);baseline=read(BASELINE)
    assignments={r['source_id']:r for r in split['assignments']}
    forbidden={r['sha256'] for r in baseline['regression_only_videos']}
    forbidden|={r['source_sha256'] for r in split['assignments'] if r['split']=='test'}
    held={r['source_sha256'] for r in split['assignments'] if r['split'] in ('quarantine','excluded')}
    rows=[r for r in original['clips'] if r['split'] in ('train','validation')]
    source_splits=defaultdict(set);group_splits=defaultdict(set);label_cache={};bindings={};windows={};rejected=[]
    for row in rows:
        a=assignments[row['source_id']]
        if row['source_sha256'] in forbidden or row['source_sha256']!=a['source_sha256'] or row['split']!=a['split'] or row['event_group']!=a['group_id']:
            raise ValueError('Protected source/split/group leak')
        if row['source_sha256'] in held or a.get('excluded'):
            rejected.append(dict(clip_id=row['clip_id'],reason='same_bytes_as_quarantined_or_excluded_source'))
            continue
        source_splits[row['source_sha256']].add(row['split']);group_splits[row['event_group']].add(row['split'])
        path=row['label_path']
        if path not in label_cache:
            if sha(path)!=row['label_sha256']:raise ValueError('Selected annotation changed')
            label_cache[path]=read(path);bindings[path]=row['label_sha256']
        try:window=window_for(row,label_cache[path])
        except ValueError as e:
            rejected.append(dict(clip_id=row['clip_id'],reason=str(e)));continue
        key=digest([row['source_sha256'],window['sample_frame_indices']])
        target=window.pop('target')
        if key in windows:
            existing=windows[key]
            if existing['label']!=row['label'] or existing['split']!=row['split']:raise ValueError('Mixed full-frame window labels/splits')
            if target not in existing['targets']:existing['targets'].append(target)
            continue
        windows[key]=dict(window,window_id='head-'+key[:24],source_path=row['source_path'],source_sha256=row['source_sha256'],
                          source_id=row['source_id'],source_size=[row['source_width'],row['source_height']],time_base=row['time_base'],
                          split=row['split'],event_group=row['event_group'],location=row['location'],label=row['label'],
                          targets=[target],label_path=path,label_sha256=row['label_sha256'],
                          spatial_domain='whole_original_frame',semantic_scope='official_reference_weak_scene_label_not_human_ground_truth')
    if any(len(s)!=1 for s in [*source_splits.values(),*group_splits.values()]):raise ValueError('Source/group crosses split')
    output.mkdir(parents=True,exist_ok=False)
    counts=Counter((w['split'],w['label']) for w in windows.values())
    value=dict(schema_version=2,status='not_training_release',training_release=False,
               source_manifest=dict(path=str(MANIFEST),sha256=SHA_MANIFEST),split_manifest=dict(path=str(SPLIT),sha256=SHA_SPLIT),
               baseline_lock=dict(path=str(BASELINE),sha256=SHA_BASELINE),windows=list(windows.values()),rejected=rejected,
               label_bindings=bindings,counts={f'{s}:{y}':n for (s,y),n in counts.items()},
               observed_native_fps=3,requested_samples=16,requested_interval_seconds=4/30,
               repeated_samples_are_new_observations=False,source_pixels_decoded=False,
               protected_test_pixels_or_labels_read=False,school45_used=False,
               fullframe_negative_semantics_human_verified=False,
               validation_normal_subtypes='sitting_only; cannot establish walking_waiting_turnback false-alarm level',
               training_protocol='frozen encoder pooled features or joint query AVA logits; source-wide label-conflict rejection',
               selection_policy='no school45/test selection; new head release and source decoding required before training')
    value['smoke_window_ids']=select_smoke(value['windows'])
    path=output/'manifest.json';path.write_text(json.dumps(value,sort_keys=True,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(path=str(path),sha256=sha(path),counts=value['counts'],windows=len(windows),rejected=len(rejected))))


def select_smoke(windows):
    """Fixed label/action/source round robin, independent of any model output."""
    chosen=[]
    for split,count in (('train',32),('validation',8)):
        buckets=defaultdict(list)
        for w in windows:
            if w['split']==split:
                actions=tuple(sorted({t['action_class'] for t in w['targets']}))
                buckets[(w['label'],actions)].append(w)
        for rows in buckets.values():rows.sort(key=lambda w:digest([66,w['window_id']]))
        used=set();selected=[]
        while len(selected)<count:
            progress=False
            for key in sorted(buckets):
                rows=buckets[key]
                if not rows:continue
                i=next((i for i,w in enumerate(rows) if w['source_sha256'] not in used),0)
                w=rows.pop(i);selected.append(w['window_id']);used.add(w['source_sha256']);progress=True
                if len(selected)==count:break
            if not progress:raise ValueError('Insufficient stratified smoke windows')
        chosen.extend(selected)
    return chosen


def embargo(plan):
    """Only protected metadata is read; never open test pixels or annotations."""
    for key,expected in (('source_manifest',SHA_MANIFEST),('split_manifest',SHA_SPLIT),('baseline_lock',SHA_BASELINE)):
        if plan[key]['sha256']!=expected or sha(plan[key]['path'])!=expected:raise ValueError('Frozen metadata changed')
    assignments=read(plan['split_manifest']['path'])['assignments']
    by_id={r['source_id']:r for r in assignments}
    forbidden={r['source_sha256'] for r in assignments if r['split'] not in ('train','validation')}
    forbidden|={r['sha256'] for r in read(plan['baseline_lock']['path'])['regression_only_videos']}
    forbidden_groups={r['group_id'] for r in assignments if r['split']=='test'}
    groups=defaultdict(set);hashes=defaultdict(set);ids=set()
    for w in plan['windows']:
        if w['window_id'] in ids:raise ValueError('Duplicate window')
        ids.add(w['window_id'])
        if w['split'] not in ('train','validation') or w['source_sha256'] in forbidden or w['event_group'] in forbidden_groups:
            raise ValueError('Protected source/group leak')
        for t in w['targets']:
            a=by_id[t['source_id']]
            if (t['source_sha256']!=w['source_sha256'] or a['source_sha256']!=t['source_sha256']
                    or a['split']!=w['split'] or a['group_id']!=w['event_group']):raise ValueError('Target provenance/split changed')
        groups[w['event_group']].add(w['split']);hashes[w['source_sha256']].add(w['split'])
    if any(len(v)!=1 for v in [*groups.values(),*hashes.values()]):raise ValueError('Cross split leak')


def selected_frames(path,windows):
    """Seek to contiguous requested spans and stream native PTS, with one decoder thread.

    Yields each requested native timestamp once; no frame-index/FPS approximation.
    Consumers retain only frames required by overlapping windows.
    """
    import av
    tb=Fraction(windows[0]['time_base']);size=windows[0]['source_size'];ticks=set()
    index_ticks={}
    for w in windows:
        if Fraction(w['time_base'])!=tb or w['source_size']!=size:raise ValueError('Source geometry/clock conflict')
        if len(w['sample_pts_ticks'])!=16 or len(set(w['sample_pts_ticks']))!=7:raise ValueError('Expected16 slots and7 native frames')
        for i,t,p in zip(w['sample_frame_indices'],w['sample_pts_ticks'],w['sample_pts']):
            if i in index_ticks and index_ticks[i]!=t:raise ValueError('Native index conflict')
            index_ticks[i]=t
            if abs(float(t*tb)-p)>1e-8:raise ValueError('Native timestamp conflict')
            ticks.add(t)
    spans=[]
    for tick in sorted(ticks):
        if not spans or (tick-spans[-1][-1])*tb>2:spans.append([])
        spans[-1].append(tick)
    with av.open(str(path)) as container:
        stream=container.streams.video[0];stream.codec_context.thread_count=1
        if Fraction(stream.time_base)!=tb:raise ValueError('Actual native timebase changed')
        for span in spans:
            wanted=set(span);found=set();container.seek(span[0],stream=stream,backward=True,any_frame=False)
            for frame in container.decode(stream):
                if frame.pts is None or Fraction(frame.time_base)!=tb:raise ValueError('Missing/changed native clock')
                if frame.pts>span[-1]:break
                if frame.pts not in wanted:continue
                if frame.pts in found:raise ValueError('Duplicate native PTS')
                if [frame.width,frame.height]!=size:raise ValueError('Actual source dimensions changed')
                found.add(frame.pts)
                yield frame.pts,frame.to_ndarray(format='rgb24')
            if found!=wanted:raise ValueError('Missing selected native PTS')


def window_pixels(path,windows,frame_sink=None):
    """Bounded ring of selected frames; shared frames decoded once per source span."""
    import numpy as np
    endings=defaultdict(list);uses=Counter();cache={}
    for w in windows:
        endings[max(w['sample_pts_ticks'])].append(w);uses.update(set(w['sample_pts_ticks']))
    for tick,rgb in selected_frames(path,windows):
        if frame_sink:frame_sink(tick,rgb)
        cache[tick]=rgb
        for w in endings[tick]:
            if any(t not in cache for t in w['sample_pts_ticks']):raise ValueError('Missing requested input')
            yield w,np.stack([cache[t] for t in w['sample_pts_ticks']])
            for t in set(w['sample_pts_ticks']):
                uses[t]-=1
                if not uses[t]:del uses[t];del cache[t]
    if uses or cache:raise ValueError('Incomplete selected pixel execution')


def prepare_source(job):
    path,windows,out=job
    expected=windows[0]['source_sha256'];p=Path(path);before=p.stat()
    if sha(p)!=expected:raise ValueError('Selected source checksum changed: '+path)
    frames=[];seen=0
    def sink(tick,rgb):
        frames.append(dict(pts_tick=tick,rgb_sha256=hashlib.sha256(rgb.tobytes()).hexdigest(),shape=list(rgb.shape)))
    window_proofs=[]
    for w,clip in window_pixels(path,windows,sink):
        seen+=1
        window_proofs.append(dict(window_id=w['window_id'],rgb_slots_sha256=hashlib.sha256(clip.tobytes()).hexdigest(),
                                  observed_unique_frames=len(set(w['sample_pts_ticks']))))
    after=p.stat()
    if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):raise ValueError('Source changed during preparation')
    proof=dict(source_path=path,source_sha256=expected,source_size=windows[0]['source_size'],time_base=windows[0]['time_base'],
               selected_native_frames=len(frames),scored_windows=seen,frames=frames,windows=window_proofs,
               source_stat=dict(size=after.st_size,mtime_ns=after.st_mtime_ns),decode='PyAV seek verified native PTS; RGB24; codec threads1')
    name=out/(expected+'.json')
    with name.open('x',encoding='utf-8') as stream:json.dump(proof,stream,sort_keys=True,indent=2,allow_nan=False)
    return dict(path=str(name),sha256=sha(name),source_path=path,source_sha256=expected,
                selected_native_frames=len(frames),windows=seen)


def prepare_pixels(plan_path,output,workers=2):
    from concurrent.futures import ProcessPoolExecutor
    if workers not in (1,2):raise ValueError('At most2 CPU workers')
    output=output.resolve()
    plan=read(plan_path);embargo(plan)
    if plan['schema_version']!=2 or plan['smoke_window_ids']!=select_smoke(plan['windows']):raise ValueError('Exact v2 selection required')
    output.mkdir(parents=True,exist_ok=False);(output/'sources').mkdir()
    labels={t['label_path']:t['label_sha256'] for w in plan['windows'] for t in w['targets']}
    source_paths={t['source_path']:t['source_sha256'] for w in plan['windows'] for t in w['targets']}
    for path,h in labels.items():
        if sha(path)!=h:raise ValueError('Selected label bytes changed')
    grouped=defaultdict(list)
    for w in plan['windows']:grouped[w['source_sha256']].append(w)
    representatives={h:rows[0]['source_path'] for h,rows in grouped.items()}
    # Alternate-name targets are independently bound too; never assume same-name labels.
    aliases={p:h for p,h in source_paths.items() if representatives[h]!=p}
    for p,h in aliases.items():
        if sha(p)!=h:raise ValueError('Alternate source checksum changed')
    jobs=[(representatives[h],rows,output/'sources') for h,rows in sorted(grouped.items())]
    proofs=[]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for proof in pool.map(prepare_source,jobs):
            proofs.append(proof);print(json.dumps(dict(prepared_sources=len(proofs),total=len(jobs))),flush=True)
    result=dict(status='cpu_pixels_verified_not_training_release',training_release=False,
                plan=dict(path=str(plan_path.resolve()),sha256=sha(plan_path)),sources=proofs,label_bindings=labels,
                source_alias_bindings=aliases,windows=sum(p['windows'] for p in proofs),
                unique_source_hashes=len(proofs),source_paths_verified=len(source_paths),label_files_verified=len(labels),
                selected_unique_native_frames=sum(p['selected_native_frames'] for p in proofs),
                protected_test_pixels_or_labels_read=False,semantic_ground_truth_verified=False,workers=workers)
    with (output/'result.json').open('x',encoding='utf-8') as stream:json.dump(result,stream,sort_keys=True,indent=2,allow_nan=False)
    print(json.dumps(dict(result=str(output/'result.json'),sha256=sha(output/'result.json'))),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--prepare-pixels',type=Path);parser.add_argument('--workers',type=int,default=2)
    args=parser.parse_args()
    if args.prepare_pixels:prepare_pixels(args.prepare_pixels,args.output,args.workers)
    else:prepare(args.output)
