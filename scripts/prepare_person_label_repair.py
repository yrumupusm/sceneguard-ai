"""Prepare only the75 originally reviewed native frames for separate box drafts."""
import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'outputs/model-comparison/exp0066/label-repair-v1'
FIXED={
 'review':(ROOT/'outputs/model-comparison/exp0066/detector-label-review-v1/review.json','c6a64a9a8cac5f3ca6e6f149b4152cdb82b0f0938d5476695cafed10b40dae0e'),
 'responses':(ROOT/'runtime/model-comparison/exp0066/label-review-followup/reviewed-v1/acknowledged-answers.json','c428fd7d09f1aaa65063655991aed612eb2197f905d45eca9287cfd2bc07795d'),
 'decisions':(ROOT/'runtime/model-comparison/exp0066/label-review-followup/reviewed-v1/decisions.json','97524bd90b66e1b8ab1d90fb84fc4f999735523ae2a6f0f1c4aff7a3234f414f'),
 'plan':(ROOT/'outputs/model-comparison/exp0066/head-plan-v2/manifest.json','28cd2ad0f57ec2230c8de5acf18dae56046ecf512e0e46f917de6c4c577add18'),
 'pilot':(ROOT/'outputs/model-comparison/exp0066/reviewed-person-pilot-v1/manifest.json','1df00c365ed086e3d6a2fa801a65fdf78bda5f41361c600c3ce3c237385ff814'),
 'baseline':(ROOT/'outputs/action-recognition/exp0063/baseline/attempt-002/baseline-lock.json','3799ae3eee427b60e698b21f6ee958ac5306eacba07b5d85e4c35dbfa6457b40')}
CASES={1:('train',99,1),3:('train',159,2),5:('validation',40,1)}


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'),
                      parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON '+x)))


def binding(path):return dict(path=str(Path(path).resolve()),sha256=sha(path))


def fixed_inputs():
    data={}
    for name,(path,h) in FIXED.items():
        if sha(path)!=h:raise ValueError('Frozen input changed: '+name)
        data[name]=read(path)
    if (data['decisions']['review_sha256']!=FIXED['review'][1]
            or data['decisions']['response_snapshot_sha256']!=FIXED['responses'][1]
            or data['review']['plan_sha256']!=FIXED['plan'][1]):raise ValueError('Input provenance differs')
    return data


def select_cases(review,responses,decisions,plan,pilot,baseline):
    cases={v['number']:v for v in review['cases']};answers={v['id']:v for v in responses['requests']}
    windows={v['window_id']:v for v in plan['windows']};choices={v['case_number']:v for v in decisions['cases']}
    if (len(cases)!=len(review['cases']) or len(choices)!=len(decisions['cases'])
            or set(cases)!=set(range(1,7)) or set(choices)!=set(cases)):
        raise ValueError('Exact original six-case review required')
    selected=[];protected={v['sha256'] for v in baseline['regression_only_videos']}
    for n,(split,start,version) in CASES.items():
        c=cases[n];d=choices[n];w=windows[c['window_id']];a=answers[d['request_id']]
        if (d['disposition']!='hold_incomplete_or_uncertain_person_scope'
                or c['split']!=split or w['split']!=split or d['original_split']!=split
                or d['window_id']!=c['window_id'] or c['source_sha256']!=w['source_sha256']
                or c['source_sha256'] in protected or c['event_group']!=w['event_group']
                or c['source_size']!=w['source_size'] or c['displayed_frame_origin']!=1
                or d['answer_version']!=version or a['answer_version']!=version
                or a['source_binding_sha256']!=d['source_binding_sha256']
                or a['artifact_id']!=f'exp0066-label-{n:02d}-video'
                or a['status'] not in ('acknowledged','applied')):
            raise ValueError('Review version/scope/source/original split differs')
        frames=c['frames'];indices=[f['frame_index'] for f in frames];tb=Fraction(w['time_base'])
        if len(frames)!=25 or indices!=list(range(start,start+25)) or d['frame_indices']!=indices:
            raise ValueError('Exactly25 original native frames per case required')
        for ref in frames:
            if (set(ref['boxes'])!={'0','1'} or not all(isinstance(ref['boxes'][k],list) for k in ('0','1'))
                    or abs(float(ref['native_pts_tick']*tb)-ref['source_pts'])>1e-8
                    or abs(ref['source_pts']-ref['frame_index']/3)>1e-8
                    or len(ref['source_rgb_sha256'])!=64):raise ValueError('Native3FPS/origin/RGB reference differs')
        selected.append((c,w,d,a))
    combined=[dict(split=c['split'],event_group=c['event_group'],source_sha256=c['source_sha256']) for c,_,_,_ in selected]+pilot['frames']
    for key in ('event_group','source_sha256'):
        if {r[key] for r in combined if r['split']=='train'} & {r[key] for r in combined if r['split']=='validation'}:
            raise ValueError('Original split leakage')
    return selected


def selected(data):return select_cases(*(data[k] for k in ('review','responses','decisions','plan','pilot','baseline')))


def frame_identity(c,w,d,a,ref):
    return dict(frame_id=f"case-{c['number']:02d}-frame-{ref['frame_index']:06d}",case_number=c['number'],
        split=c['split'],event_group=c['event_group'],source_id=c['source_id'],source_path=w['source_path'],
        source_sha256=c['source_sha256'],source_size=c['source_size'],frame_index=ref['frame_index'],
        native_pts_tick=ref['native_pts_tick'],time_base=w['time_base'],source_pts=ref['source_pts'],
        source_rgb_sha256=ref['source_rgb_sha256'],original_boxes_by_origin=ref['boxes'],
        original_annotations=ref['boxes']['1'],annotation_frame_origin=1,frame_origin_certified=False,
        label_file_bindings=c['label_bindings'],request_id=d['request_id'],answer_version=d['answer_version'],
        source_binding_sha256=d['source_binding_sha256'],review_answer=a['answer'],
        review_snapshot_version=a['version'],human_verified=False,training_eligible=False)


def export(output):
    import av
    from PIL import Image
    data=fixed_inputs();cases=selected(data);output=Path(output).resolve()
    if output==OUTPUT or OUTPUT not in output.parents:raise ValueError('Fresh owned output subdirectory required')
    output.mkdir(parents=True,exist_ok=False);rows=[]
    raw=output/'original-labels';raw.mkdir()
    for c,w,d,a in cases:
        if sha(w['source_path'])!=c['source_sha256']:raise ValueError('Original source changed')
        copies=[]
        for path,h in c['label_bindings'].items():
            if sha(path)!=h:raise ValueError('Original label changed')
            target=raw/(h+'.json')
            if not target.exists():shutil.copyfile(path,target)
            if sha(target)!=h:raise ValueError('Verbatim original label copy differs')
            copies.append(dict(original_path=path,copy=binding(target)))
        refs={f['frame_index']:f for f in c['frames']};found=set()
        with av.open(w['source_path']) as source:
            stream=source.streams.video[0];stream.codec_context.thread_count=1
            if Fraction(stream.average_rate)!=3:raise ValueError('Actual native3FPS required')
            for index,frame in enumerate(source.decode(stream)):
                if index>max(refs):break
                if index not in refs:continue
                ref=refs[index];rgb=frame.to_ndarray(format='rgb24')
                if (frame.pts!=ref['native_pts_tick'] or Fraction(frame.time_base)!=Fraction(w['time_base'])
                        or abs(float(frame.pts*frame.time_base)-ref['source_pts'])>1e-8
                        or list(rgb.shape[1::-1])!=c['source_size']
                        or hashlib.sha256(rgb.tobytes()).hexdigest()!=ref['source_rgb_sha256']):
                    raise ValueError('Actual native index/PTS/RGB/geometry differs')
                row=frame_identity(c,w,d,a,ref);folder=output/'images'/c['split'];folder.mkdir(parents=True,exist_ok=True)
                image=folder/(row['frame_id']+'.png');Image.fromarray(rgb).save(image)
                row.update(image=binding(image),original_label_copies=copies);rows.append(row);found.add(index)
        if found!=set(refs):raise ValueError('Missing original reviewed frames')
    rows.sort(key=lambda r:(r['case_number'],r['frame_index']))
    value=dict(schema_version=1,purpose='person_label_repair_drafts_only',case_numbers=[1,3,5],
               training_release=False,human_verified=False,detector_proposals_are_ground_truth=False,
               model_inference_count=0,frame_counts=dict(Counter(r['split'] for r in rows)),frames=rows,
               preparation_inputs={k:dict(path=str(p),sha256=h) for k,(p,h) in FIXED.items()},
               preparer_sha256=sha(__file__),original_annotations_modified=False,protected_school_or_test_used=False)
    path=output/'manifest.json'
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False);f.write('\n')
    validate_preparation(path)
    return binding(path)


def validate_preparation(path):
    """Verify selected source bytes, original labels, and all prepared native RGBs."""
    from PIL import Image
    import numpy as np
    path=Path(path).resolve();m=read(path);data=fixed_inputs();cases=selected(data)
    if (m.get('purpose')!='person_label_repair_drafts_only' or m.get('case_numbers')!=[1,3,5]
            or m.get('training_release') is not False or m.get('human_verified') is not False
            or m.get('detector_proposals_are_ground_truth') is not False or m.get('model_inference_count')!=0
            or m.get('preparer_sha256')!=sha(__file__) or m.get('original_annotations_modified') is not False
            or m.get('protected_school_or_test_used') is not False
            or m.get('preparation_inputs')!={k:dict(path=str(p),sha256=h) for k,(p,h) in FIXED.items()}):
        raise ValueError('Unreleased native preparation scope/provenance differs')
    expected={}
    sources={};labels={};images={}
    for c,w,d,a in cases:
        sources[w['source_path']]=c['source_sha256'];labels.update(c['label_bindings'])
        for ref in c['frames']:
            row=frame_identity(c,w,d,a,ref);expected[row['frame_id']]=row
    seen=set()
    for row in m['frames']:
        key=row['frame_id']
        if key in seen or key not in expected or any(row.get(k)!=v for k,v in expected[key].items()):
            raise ValueError('Changed, duplicate or extra frame/annotation/review')
        seen.add(key);image=path.parent/'images'/row['split']/(key+'.png')
        if row['image']!=binding(image) or image.resolve().parent!=(path.parent/'images'/row['split']).resolve():
            raise ValueError('Prepared image binding/path changed')
        with Image.open(image) as im:
            if im.mode!='RGB' or list(im.size)!=row['source_size']:raise ValueError('Native image format/size differs')
            rgb=np.asarray(im)
            if hashlib.sha256(rgb.tobytes()).hexdigest()!=row['source_rgb_sha256']:raise ValueError('Native RGB changed')
        images[str(image)]=row['image']['sha256']
        copies=row['original_label_copies']
        if len(copies)!=len(row['label_file_bindings']):raise ValueError('Original label copies missing')
        if {x['original_path'] for x in copies}!=set(row['label_file_bindings']):raise ValueError('Original label links differ')
        for copy in copies:
            h=row['label_file_bindings'][copy['original_path']];target=path.parent/'original-labels'/(h+'.json')
            if copy['copy']!=binding(target) or copy['copy']['sha256']!=h:raise ValueError('Original label copy changed')
            labels[str(target)]=h
    if seen!=set(expected) or len(seen)!=75 or m['frame_counts']!={'train':50,'validation':25}:
        raise ValueError('Exactly75 reviewed native frames required')
    for name,h in {**sources,**labels}.items():
        if sha(name)!=h:raise ValueError('Actual selected source/label changed')
    return dict(preparation_sha256=sha(path),fixed_inputs={k:h for k,(_,h) in FIXED.items()},
                source_files=sources,original_labels=labels,images=images,frame_ids=sorted(seen))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();print(json.dumps(export(args.output),sort_keys=True))
