# SPDX-License-Identifier: AGPL-3.0-only
"""Repeatable CPU report/metrics and private original/pose comparison media builder."""
from fractions import Fraction
import json
from pathlib import Path
import time
from batch03_pose.prepare import sha
from orchestration.batch03_pose_command import ROOT,LOCAL,MANIFEST,manifest,output_path,COCO17
from orchestration.mock_job import atomic_json
SKELETON=((5,6),(5,7),(7,9),(6,8),(8,10),(5,11),(6,12),(11,12),(11,13),(13,15),(12,14),(14,16),(0,1),(0,2),(1,3),(2,4))


def records_for(smoke,remaining):
    d=manifest();summaries=[];paths=[]
    for stage,attempt in [('smoke',smoke),('remaining',remaining)]:
        path=output_path(stage,attempt)/'summary.json';s=json.loads(path.read_text())
        if s['status']!='succeeded' or not s['technical_pass']:raise ValueError('both fixed stages must pass')
        summaries.append(s);paths.append(path)
    records=[r for s in summaries for r in s['results']]
    if len(records)!=len(d['frames']) or {r['frame_id'] for r in records}!={r['frame_id'] for r in d['frames']}:raise ValueError('complete unique fixed frame set required')
    return d,summaries,paths,{r['frame_id']:r for r in records}


def coverage(rows):
    persons=[p for r in rows for p in r['persons']];total=len(persons)*17
    return dict(frames=len(rows),frames_with_output=sum(bool(r['persons']) for r in rows),person_output_rows=len(persons),
        returned_joint_slots=total,retained_joint_estimates=sum(p['retained_joint_count'] for p in persons),
        unknown_joint_slots=total-sum(p['retained_joint_count'] for p in persons),
        joint_retained_estimates={name:sum(p['keypoints'][i]['observed_xy'] is not None for p in persons) for i,name in enumerate(COCO17)},
        interpretation='output slots, not distinct people or visually verified joints; no row-to-person/temporal identity correspondence')


def draw_pose(image,persons,low=False):
    from PIL import ImageDraw
    draw=ImageDraw.Draw(image)
    for p in persons:
        draw.rectangle(p['xyxy'],outline='orange',width=3)
        draw.text((p['xyxy'][0],p['xyxy'][1]),f"row{p['output_index']} conf{p['confidence']:.3f} (not ID)",fill='orange')
        if not low:
            for a,b in SKELETON:
                x=p['keypoints'][a]['observed_xy'];y=p['keypoints'][b]['observed_xy']
                if x is not None and y is not None:draw.line([tuple(x),tuple(y)],fill='lime',width=3)
        for k in p['keypoints']:
            xy=k['raw_xy'] if low and k['observed_xy'] is None else k['observed_xy'] if not low else None
            if xy is None:continue
            x,y=xy;color='gray' if low else 'lime'
            draw.ellipse((x-3,y-3,x+3,y+3),outline=color,width=2);draw.text((x+4,y+3),str(k['index']),fill=color)
    return image


def title(image,text):
    from PIL import ImageDraw
    draw=ImageDraw.Draw(image);draw.rectangle((0,0,image.width,27),fill='black');draw.text((7,7),text,fill='white');return image


def pair(item,result):
    import numpy as np
    from PIL import Image
    original=Image.fromarray(np.load(ROOT/item['rgb_path'],allow_pickle=False));pose=draw_pose(original.copy(),result['persons'])
    canvas=Image.new('RGB',(1920,540));pts=f"{item['source_id']} nativePTS={item['native_pts']} tb={item['time_base']} t={item['pts_seconds']:.6f}"
    canvas.paste(title(original.resize((960,540)),'Original | '+pts),(0,0))
    canvas.paste(title(pose.resize((960,540)),'Pose conf>=0.5 estimates; identity UNREVIEWED | '+pts),(960,0));return canvas


def make_media(d,records,target):
    import av
    import numpy as np
    from PIL import Image,ImageDraw
    from batch02_cv.compare import fcos_boxes
    target.mkdir(parents=True,exist_ok=True);by_id={r['frame_id']:r for r in d['frames']};artifacts=[]
    old=json.loads((ROOT/'configs/batch0002_cv_manifest.json').read_text())
    rf={}
    for stage in ('smoke','remaining'):
        for p in (ROOT/'outputs/batch0002/cv/EXP-0019'/stage).glob('*/summary.json'):
            s=json.loads(p.read_text())
            if s['status']=='succeeded':rf.update({r['frame_id']:r for r in s['results']})
    for item in [r for r in d['frames'] if r['diagnostic']]:
        r=records[item['frame_id']];original=Image.fromarray(np.load(ROOT/item['rgb_path'],allow_pickle=False));panels=[]
        historical=next(f for f in old['frames'] if f['frame_id']==item['frame_id'])
        if historical['native_pts']!=item['native_pts'] or historical['rgb_bytes_sha256']!=item['rgb_bytes_sha256']:raise ValueError('historical RGB/PTS differs')
        for label,boxes in [('Original',[]),('FCOS >=0.5 historical',fcos_boxes(historical)),('RF-DETR >0.5 historical',rf[item['frame_id']]['persons'])]:
            img=original.copy();draw=ImageDraw.Draw(img)
            for b in boxes:draw.rectangle(b['xyxy'],outline='orange',width=3)
            panels.append(title(img.resize((960,540)),label))
        panels.append(title(draw_pose(original.copy(),r['persons']).resize((960,540)),'YOLO26m-pose joints conf>=0.5 estimates; not visual GT'))
        canvas=Image.new('RGB',(1920,1080))
        for i,p in enumerate(panels):canvas.paste(p,((i%2)*960,(i//2)*540))
        path=target/(item['frame_id']+'-diagnostic.png');canvas.save(path)
        title(draw_pose(original.copy(),r['persons'],low=True).resize((960,540)),'LOW/UNKNOWN joints separate, no skeleton; never valid observations').save(target/(item['frame_id']+'-unknown.png'))
        pair(item,r).save(target/(item['frame_id']+'-original-pose.png'))
        artifacts.append(dict(kind='diagnostic',frame_id=item['frame_id'],path=str(path.relative_to(ROOT)),sha256=sha(path)))
    for w in d['windows']:
        path=target/(w['alias']+'-original-pose.mp4')
        with av.open(str(path),mode='w') as output:
            stream=output.add_stream('libx264',rate=10);stream.width=1920;stream.height=540;stream.pix_fmt='yuv420p';stream.options={'crf':'20','preset':'fast'};stream.time_base=Fraction(1,90000);stream.codec_context.time_base=Fraction(1,90000)
            times=[]
            for frame_id in w['frames']:
                item=by_id[frame_id];stamp=Fraction(item['native_pts'])*Fraction(item['time_base'])-Fraction(str(w['start']));times.append(float(stamp))
                frame=av.VideoFrame.from_ndarray(np.asarray(pair(item,records[frame_id])),format='rgb24');frame.pts=round(stamp*90000);frame.time_base=Fraction(1,90000)
                for packet in stream.encode(frame):output.mux(packet)
            for packet in stream.encode():output.mux(packet)
        with av.open(str(path)) as video:
            decoded=[float(f.pts*f.time_base) for f in video.decode(video=0)]
            if len(decoded)!=len(w['frames']) or any(abs(a-b)>1/90000+.000001 for a,b in zip(decoded,times)):raise ValueError('normal-speed encoded PTS/frame count differs')
        artifacts.append(dict(kind='normal_speed_original_pose',alias=w['alias'],path=str(path.relative_to(ROOT)),sha256=sha(path),frames=len(times),decoded_pts=decoded,source_interval=[w['start'],w['end']],times_relative_to_source_interval=True))
    atomic_json(target/'artifacts.local.json',dict(artifacts=artifacts,pixels='private local only',low_confidence='separate diagnostic unknown panels'))
    return artifacts


def build(smoke,remaining,media=False):
    d,summaries,paths,records=records_for(smoke,remaining);out=ROOT/'records/EXP-0021';out.mkdir(exist_ok=True)
    windows=[dict(alias=w['alias'],**coverage([records[k] for k in w['frames']])) for w in d['windows']]
    diagnostics=[dict(frame_alias=f['frame_id'],native_pts=f['native_pts'],time_base=f['time_base'],person_outputs=records[f['frame_id']]['person_count'],retained_joint_estimates=sum(p['retained_joint_count'] for p in records[f['frame_id']]['persons']),visual_correspondence=None) for f in d['frames'] if f['diagnostic']]
    comparison=dict(experiment_id='EXP-0021',scope='267 purposive original native development frames; output coverage only, no visual correspondence GT',
        settings=d['settings'],total=coverage(list(records.values())),windows=windows,diagnostic_frames=diagnostics,
        person_correspondence='unreviewed',temporal_identity='not_established; no tracker',behavioral_validation='not_established',
        rule_status='not_run; pose correspondence and boundary geometry gate unvalidated',adoption='adopt_on_hold',formal_behavior_metrics={k:None for k in ['accuracy','precision','recall','f1','false_positive_rate']})
    atomic_json(out/'comparison.json',comparison)
    metrics=[]
    for w in windows:
        for key,unit in [('frames','frames'),('frames_with_output','frames'),('person_output_rows','output rows'),('retained_joint_estimates','joint estimates'),('unknown_joint_slots','joint slots')]:
            metrics.append(dict(label=w['alias']+' '+key,value=w[key],unit=unit,sample_n=w['frames'],scope=w['interpretation'],source='records/EXP-0021/comparison.json',source_sha256=sha(out/'comparison.json'),source_pointer=['windows',windows.index(w),key],verification='bound_saved_pose_summary_native_PTS_only'))
    for stage,s,p in zip(('smoke','remaining'),summaries,paths):
        n=len(s['results'])
        for key,unit in [('model_construction_load_seconds','seconds'),('run_entry_wall_seconds','seconds'),('load_peak_allocated_bytes','bytes'),('load_peak_reserved_bytes','bytes')]:
            metrics.append(dict(label=stage+' '+key,value=s[key],unit=unit,sample_n=n,scope='Instrumented run-entry wall/load (run function begins before validation; Python/module startup excluded); no warmup; allocator peak includes resident model; not device-wide total',source=str(p.relative_to(ROOT)),source_sha256=sha(p),source_pointer=[key],verification='saved_summary'))
    costs={stage:{k:sum(r[k] for r in s['results']) for k in ['input_read_verify_seconds','preprocess_seconds','inference_seconds','postprocess_seconds','save_seconds','frame_wall_seconds']} for stage,s in zip(('smoke','remaining'),summaries)}
    cost= dict(stages=costs,preparation=json.loads((LOCAL/'frame-binding.json').read_text())['decode'],
        model_load_seconds=[s['model_construction_load_seconds'] for s in summaries],
        inference_only_fps=len(records)/sum(v['inference_seconds'] for v in costs.values()),
        measured_frame_wall_fps=len(records)/sum(v['frame_wall_seconds'] for v in costs.values()),
        peaks=dict(allocated_bytes=max(r['peak_allocated_bytes'] for r in records.values()),reserved_bytes=max(r['peak_reserved_bytes'] for r in records.values())),
        denominators='unique267 forwards including both cold starts; inference seconds exclude CPU decode/save; frame wall includes verification/preprocess/capture/save overhead; preparation decode+RGB/save/hash separate; not realtime throughput or controlled FCOS/RF speed comparison')
    atomic_json(out/'costs.json',cost)
    atomic_json(out/'metrics.json',dict(schema_version=1,experiment_id='EXP-0021',execution_status='succeeded',behavioral_validation='not_established',adoption='adopt_on_hold',comparison_group='EXP-0021',cross_experiment_comparable=False,
        scope=comparison['scope'],formal_behavior_metrics=comparison['formal_behavior_metrics'],metrics=metrics,
        comparison_source='records/EXP-0021/comparison.json',comparison_sha256=sha(out/'comparison.json'),
        source_bindings=dict(manifest_sha256=sha(MANIFEST),checkpoint_sha256=d['model']['sha256'],requirement_lock_sha256=sha(ROOT/'requirements-pose-batch03-lock.txt'),execution_commit=summaries[0]['registration']['code_sha'],execution_source_sha256=summaries[0]['registration']['source_hash'],stage_summary_sha256=[sha(p) for p in paths])))
    atomic_json(LOCAL/'report-binding.local.json',dict(summary_files={str(p.relative_to(ROOT)):sha(p) for p in paths},public_files={str(p.relative_to(ROOT)):sha(p) for p in out.glob('*.json')},costs=cost))
    if media:
        t=time.perf_counter();artifacts=make_media(d,records,ROOT/'outputs/batch0003/comparison');atomic_json(LOCAL/'media-cost.local.json',dict(cpu_media_wall_seconds=time.perf_counter()-t,artifacts=len(artifacts)))
    print(json.dumps(dict(frames=len(records),coverage=comparison['total'],windows=windows,costs=cost),indent=2))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--smoke-attempt',required=True);p.add_argument('--remaining-attempt',required=True);p.add_argument('--media',action='store_true');a=p.parse_args();build(a.smoke_attempt,a.remaining_attempt,a.media)
