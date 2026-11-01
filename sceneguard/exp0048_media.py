"""EXP48 local original/EXP47/EXP48 evidence viewer; no outcome classification.

Every actual box is drawn, including unalerted late passages. Final endpoint
labels are explicitly retrospective diagnostics, never causal state evidence.
"""
from bisect import bisect_right
from fractions import Fraction
from pathlib import Path
from collections import defaultdict
import argparse
import json
import time

from .exp0044_application import sha, save
from .exp0044_media import frame_clock
from .exp0047_media import grouped_specs
from .incident_lifecycle import lifecycle_cards_at

CONTRACT='EXP0048_threeway_all_actual_boxes_v1'


def snapshot(result, at):
    timeline=result['timeline'];times=[r['decision_time_pts'] for r in timeline]
    pos=bisect_right(times,at+1e-9)-1
    return dict(cards=lifecycle_cards_at(timeline,at),
                evidence=[] if pos<0 else timeline[pos]['evidence'])


def specs_for(frames, result):
    specs=grouped_specs(frames,result['resolutions'])
    if result['video_id']=='E01_007':
        specs.extend([dict(name='late-pedestrians',kind='late_passage_diagnostic',start=84.,end=104.,resolution_ids=[]),
            dict(name='pending-outward-box-motion',kind='unresolved_diagnostic',start=54.,end=57.,resolution_ids=[])])
    return specs+[dict(name='continuous',kind='full_comparison',start=frames[0]['pts'],end=frames[-1]['pts'],resolution_ids=[])]


def validate_mapping(rows):
    previous=None
    for r in rows:
        at=r['source_pts']
        if previous is not None and at<=previous:raise ValueError('Increasing source clock required')
        if abs(float(Fraction(r['native_pts'])*Fraction(r['time_base']))-at)>1e-9:
            raise ValueError('Native/source mismatch')
        for layer in ('exp47','exp48'):
            if any(c['lifecycle_updated_pts']>at+1e-9 for c in r[layer]['cards']):raise ValueError('Future card state')
            if any(e['opened_pts']>at+1e-9 for e in r[layer]['evidence']):raise ValueError('Future evidence')
            if any(b['actual_pts']>at+1e-9 for b in r['historical_boxes'][layer]):raise ValueError('Future historical box')
        if any(abs(b['actual_pts']-at)>1e-9 for b in r['actual_boxes']):raise ValueError('Current box clock mismatch')
        if any(x['decision_time_pts']>at+1e-9 for x in r['routing']):raise ValueError('Future routing')
        previous=at


def execute(directory,paths_directory,baseline_path,portal_directory):
    import av
    import cv2
    import numpy as np
    from PIL import Image,ImageDraw,ImageFont
    from .run_tracklet_linking import decode_native
    begin=time.perf_counter();directory=Path(directory);portal=Path(portal_directory)
    read=lambda p:json.loads(Path(p).read_text())
    result=read(directory/'lifecycle-cards.json');prior=read(directory/'prior-lifecycle-preserved.json')
    if result.get('experiment')!='EXP-0048' or prior.get('experiment')!='EXP-0047':raise ValueError('Distinct EXP48/47 contracts required')
    baseline=read(baseline_path);source=Path(baseline['source_paths']['video'])
    frames=[json.loads(s) for s in (Path(paths_directory)/'frame-evidence.jsonl').read_text().splitlines() if s.strip()]
    scene=read(portal/'scene-used.json');region=read(portal/'portal-region.json');runs=read(portal/'observation-runs.json')
    audit=read(directory/'all-observations-audit.json');records={r['run_id']:r for r in audit['records']}
    inputs=[source,Path(baseline_path),Path(paths_directory)/'frame-evidence.jsonl',
        directory/'lifecycle-cards.json',directory/'prior-lifecycle-preserved.json',directory/'all-observations-audit.json',
        directory/'outcome-routing.json',portal/'scene-used.json',portal/'portal-region.json',portal/'observation-runs.json',
        Path(__file__),Path(__file__).with_name('incident_lifecycle.py'),Path(__file__).with_name('exp0047_media.py')]
    font_path=Path('/mnt/c/Windows/Fonts/malgun.ttf');inputs.append(font_path)
    protected={str(p):sha(p) for p in inputs}
    by_reference=defaultdict(list);by_key={};last_seen={}
    for rid,rows in runs.items():
        by_key[rid]=rows
        for row in rows:by_reference[(row['frame_index'],row['cache_index'])].append(rid)
    specs=specs_for(frames,result);output=directory/'media'
    if output.exists() or output.is_symlink() or any(p.is_symlink() for p in output.parents):raise ValueError('Fresh non-symlink media directory required')
    output.mkdir()
    clocks=[frame_clock(r) for r in frames];tb=Fraction(frames[0]['time_base']);rate=1/(clocks[1]-clocks[0])
    width,height,header=640,360,180;font=ImageFont.truetype(str(font_path),16)
    handles=[]
    for spec in specs:
        chosen=[r for r in frames if spec['start']-1e-9<=r['pts']<=spec['end']+1e-9]
        spec.update(path=str(output/(spec['name']+'.mp4')),mapping=[],first_native_pts=chosen[0]['native_pts'])
        container=av.open(spec['path'],'w');stream=container.add_stream('libx264',rate=rate)
        stream.width=width*3;stream.height=height+header;stream.pix_fmt='yuv420p'
        stream.time_base=tb;stream.codec_context.time_base=tb;stream.options={'crf':'21','preset':'fast','threads':'2'}
        handles.append((spec,container,stream))
    decoded=0
    def rect(image,bbox,color,text,thick=1):
        x1,y1,x2,y2=np.rint(np.array(bbox)*[width,height,width,height]).astype(int)
        cv2.rectangle(image,(x1,y1),(x2,y2),color,thick)
        cv2.putText(image,text,(x1,max(12,y1-3)),0,.30,color,1)
    try:
        for index,img in decode_native(source,frames):
            row=frames[index];at=row['pts'];decoded+=1
            actual=[]
            for box in row['actual_boxes']:
                ids=by_reference.get((index,box['cache_index']),[])
                actual.append(dict(cache_index=box['cache_index'],bbox=box['bbox'],actual_pts=at,run_ids=ids))
                for rid in ids:last_seen[rid]=dict(bbox=box['bbox'],actual_pts=at)
            views={'exp47':snapshot(prior,at),'exp48':snapshot(result,at)}
            hist={};original=cv2.resize(img,(width,height));panels=[original]
            for layer in ('exp47','exp48'):
                overlay=original.copy();view=views[layer];hist[layer]=[]
                for name,color in [('outside',(220,140,50)),('inside',(70,180,70))]:
                    cv2.polylines(overlay,[np.rint(np.array(scene['zones'][name])*[width,height]).astype(np.int32)],True,color,1)
                cv2.polylines(overlay,[np.rint(np.array(region['polygon'])*[width,height]).astype(np.int32)],True,(200,200,70),1)
                # All current observations, irrespective of candidate binding.
                for box in actual:
                    rect(overlay,box['bbox'],(80,220,80),'NOW '+','.join(k.rsplit('-',1)[-1] for k in box['run_ids']))
                # Latest bound evidence shows its actual last box/time, never an extrapolation.
                bound=[e for e in view['evidence'] if e.get('observation_key') in last_seen]
                if bound:
                    evidence=max(bound,key=lambda e:e['opened_pts']);key=evidence['observation_key'];last=last_seen[key]
                    hist[layer].append(dict(last,run_id=key))
                    if last['actual_pts']<at-1e-9:
                        rect(overlay,last['bbox'],(20,200,255),f"LAST {last['actual_pts']:.3f}s",2)
                panels.append(overlay)
            routing=[r for r in result['outcome_routing'] if r['decision_time_pts']<=at+1e-9]
            routing=routing[-1:]
            active=sorted({rid for box in actual for rid in box['run_ids']})
            diagnostics=[dict(run_id=rid,state_category=records[rid]['state_category'],
                endpoint_reason=records[rid]['endpoint_assessment']['reason'],
                diagnostic_only=True,retrospective=True) for rid in active]
            labels=[f'SOURCE PTS {at:.6f}s | ORIGINAL / EXP47 / EXP48 | Green NOW boxes: ALL stored actual observations',
                'EXP47 '+(' / '.join(f"{c['automatic_status']} first={c['first_notification_pts']:.3f} confirm={c['first_confirmation_pts']}" for c in views['exp47']['cards']) or 'no incident'),
                'EXP48 '+(' / '.join(f"{c['automatic_status']} first={c['first_notification_pts']:.3f} confirm={c['first_confirmation_pts']}" for c in views['exp48']['cards']) or 'no incident'),
                'RETROSPECTIVE run audit (never state evidence): '+(' | '.join(f"{d['run_id'].rsplit('-',1)[-1]} {d['state_category']} {d['endpoint_reason']}" for d in diagnostics[:5]) or 'no current run'),
                'Latest causal routing: '+(' | '.join(f"{r['decision_time_pts']:.3f} {r['reason']} selected={len(r['selected_event_ids'])} excluded={len(r['excluded_event_ids'])}" for r in routing) or 'none'),
                'Yellow LAST box retains actual past PTS. No identity/normality/entry ground truth; no external alerts; endpoint labels are retrospective.']
            canvas=np.zeros((height+header,width*3,3),dtype=np.uint8)
            for j,panel in enumerate(panels):canvas[header:,j*width:(j+1)*width]=panel
            banner=Image.fromarray(canvas[:header,:,::-1]);draw=ImageDraw.Draw(banner)
            for j,label in enumerate(labels):draw.text((8,4+j*28),label,font=font,fill=(235,235,235))
            canvas[:header]=np.asarray(banner)[:,:,::-1]
            mapping=dict(frame_index=index,native_pts=row['native_pts'],time_base=row['time_base'],source_pts=at,
                **views,actual_boxes=actual,historical_boxes=hist,routing=routing,retrospective_run_diagnostics=diagnostics)
            for spec,container,stream in handles:
                if not spec['start']-1e-9<=at<=spec['end']+1e-9:continue
                frame=av.VideoFrame.from_ndarray(canvas,format='bgr24');frame.pts=row['native_pts']-spec['first_native_pts'];frame.time_base=tb
                for packet in stream.encode(frame):container.mux(packet)
                spec['mapping'].append(dict(mapping,presentation_pts=float(frame.pts*tb)))
    finally:
        for _,container,stream in handles:
            for packet in stream.encode():container.mux(packet)
            container.close()
    for spec,_,_ in handles:
        validate_mapping(spec['mapping'])
        with av.open(spec['path']) as container:actual=[float(f.pts*f.time_base) for f in container.decode(video=0)]
        expected=[r['presentation_pts'] for r in spec['mapping']]
        if len(actual)!=len(expected) or any(abs(a-b)>1e-6 for a,b in zip(actual,expected)):raise ValueError('Decoded encoded clock mismatch')
        spec.update(frames=len(expected),sha256=sha(spec['path']),all_frames_decoded=True)
    if protected!={p:sha(p) for p in protected}:raise ValueError('Media inputs changed')
    manifest=dict(experiment='EXP-0048',contract=CONTRACT,video_id=result['video_id'],videos=specs,
        input_sha256=protected,source_frames_decoded=decoded,elapsed_seconds=time.perf_counter()-begin,
        actual_release_groups=sum(s['kind']=='actual_releases' for s in specs),
        pixels_local_only=True,actual_loss_classifications=0,detector_calls=0,tracker_calls=0,flow_calls=0,vlm_calls=0,
        human_verified=False,all_stored_actual_boxes_shown=True,source_clock_validation='Every encoded frame independently decoded against native/source/presentation mapping')
    save(output/'manifest.json',manifest)
    save(output/'manifest-binding.json',dict(contract=CONTRACT,manifest_sha256=sha(output/'manifest.json'),video_sha256={s['path']:s['sha256'] for s in specs}))
    return dict(video_id=result['video_id'],videos=[s['path'] for s in specs],elapsed_seconds=manifest['elapsed_seconds'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('directory','paths','baseline','portal-result'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(json.dumps(execute(a.directory,a.paths,a.baseline,a.portal_result),indent=2))

if __name__=='__main__':main()
