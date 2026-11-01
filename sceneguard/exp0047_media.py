"""Local original/lifecycle comparison. Reads saved decisions, never classifies loss.

Historical boxes retain their actual source time; future states are never shown.
"""
from bisect import bisect_right
from fractions import Fraction
from pathlib import Path
import argparse
import json
import time

from .directional_loss import SavedGateDirection, pixel_box
from .exp0044_application import sha, save
from .exp0044_media import frame_clock
from .incident_lifecycle import lifecycle_cards_at
from .lifecycle_followup import ObservationHistory


def grouped_specs(frames, resolutions):
    """Group nearby actual releases; never invent a release example."""
    spans=[]
    for r in resolutions:
        if r['kind']!='outward_loss' or not r['changed_event_ids']: continue
        a=max(frames[0]['pts'],r['last_observed_pts']-2.)
        b=min(frames[-1]['pts'],r['decision_time_pts']+1.)
        if spans and a<=spans[-1]['end']+1e-9:
            spans[-1]['end']=max(b,spans[-1]['end'])
            spans[-1]['resolution_ids'].append(r['resolution_id'])
        else:spans.append(dict(start=a,end=b,resolution_ids=[r['resolution_id']]))
    return [dict(s,name=f'releases-{i+1:02d}',kind='actual_releases') for i,s in enumerate(spans)]


def validate_mapping(rows):
    previous=None
    for r in rows:
        at=r['source_pts']
        if previous is not None and at<=previous:raise ValueError('Increasing source clock required')
        if abs(float(Fraction(r['native_pts'])*Fraction(r['time_base']))-at)>1e-9:
            raise ValueError('Native/source mismatch')
        if any(c['lifecycle_updated_pts']>at+1e-9 for c in r['cards']):
            raise ValueError('Future card state')
        focus=r.get('focus')
        if focus and (focus['last']['pts']>at+1e-9 or
                      focus['motion'].get('end_pts',0)>at+1e-9):
            raise ValueError('Future observation or direction')
        previous=at


def execute(directory, paths_directory, baseline_path, portal_directory):
    import av
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    from .run_tracklet_linking import decode_native

    begin=time.perf_counter();directory=Path(directory);portal=Path(portal_directory)
    read=lambda p:json.loads(Path(p).read_text())
    result=read(directory/'lifecycle-cards.json');baseline=read(baseline_path)
    frames=[json.loads(s) for s in (Path(paths_directory)/'frame-evidence.jsonl').read_text().splitlines() if s.strip()]
    scene=read(portal/'scene-used.json');region=read(portal/'portal-region.json')
    runs=read(portal/'observation-runs.json');source=Path(baseline['source_paths']['video'])
    inputs=[source,Path(baseline_path),Path(paths_directory)/'frame-evidence.jsonl',
        directory/'lifecycle-cards.json',portal/'scene-used.json',portal/'portal-region.json',
        portal/'observation-runs.json',Path(__file__),Path(__file__).with_name('lifecycle_followup.py'),
        Path(__file__).with_name('directional_loss.py'),Path(__file__).with_name('incident_lifecycle.py')]
    protected={str(p):sha(p) for p in inputs}
    specs=grouped_specs(frames,result['resolutions'])
    # This selection is display-only: show new lineage uncertainty, not repeat
    # prior scene questions or manufacture a release when none occurred.
    if result['video_id']=='E01_007':
        specs.append(dict(name='new-confirmation-lineage',kind='new_ambiguity',
            start=57.,end=73.6,resolution_ids=[r['resolution_id'] for r in result['resolutions']
                if r['kind']=='inward_loss']))
    specs.append(dict(name='continuous',kind='full_comparison',start=frames[0]['pts'],
                      end=frames[-1]['pts'],resolution_ids=[]))
    output=directory/'media';output.mkdir(exist_ok=False)
    clocks=[frame_clock(r) for r in frames];tb=Fraction(frames[0]['time_base'])
    rate=1/(clocks[1]-clocks[0]);width,height,header=960,540,156
    w,h=scene['source_size'];scale=np.array([width/w,height/h])
    font_path=Path('/mnt/c/Windows/Fonts/malgun.ttf');font=ImageFont.truetype(str(font_path),21)
    handles=[];obs=ObservationHistory(runs,frames);engine=SavedGateDirection(frames,scene)
    timeline=result['timeline'];times=[r['decision_time_pts'] for r in timeline]
    handoffs={}
    for r in result['resolutions']:
        if r['kind']=='observation_handoff':handoffs.setdefault(r['decision_time_pts'],[]).append(r)
    def xy(p):return tuple(np.rint(np.asarray(p)*scale).astype(int))
    for spec in specs:
        chosen=[r for r in frames if spec['start']-1e-9<=r['pts']<=spec['end']+1e-9]
        spec.update(path=str(output/(spec['name']+'.mp4')),mapping=[],first_native_pts=chosen[0]['native_pts'])
        container=av.open(spec['path'],'w');stream=container.add_stream('libx264',rate=rate)
        stream.width=width*2;stream.height=height+header;stream.pix_fmt='yuv420p'
        stream.time_base=tb;stream.codec_context.time_base=tb
        stream.options={'crf':'21','preset':'fast','threads':'2'}
        handles.append((spec,container,stream))
    cached={};decoded=0
    try:
        for index,image in decode_native(source,frames):
            row=frames[index];at=row['pts'];decoded+=1;obs.advance(row)
            for r in handoffs.get(at,[]):obs.link(r['observation_key'],r['next_observation_key'])
            cards=lifecycle_cards_at(timeline,at)
            pos=bisect_right(times,at+1e-9)-1;focus=None
            if pos>=0:
                available=[e for e in timeline[pos]['evidence'] if e['observation_key']]
                if available:
                    evidence=max(available,key=lambda e:e['opened_pts']);key=evidence['observation_key']
                    rows=obs.motion_rows(key)
                    if rows:
                        cache_key=(key,rows[-1]['frame_index'],len(rows))
                        if cache_key not in cached:cached[cache_key]=engine.direction(dict(id=key,rows=rows))
                        focus=dict(run_id=key,last=rows[-1],motion=cached[cache_key],
                            automatic_status=evidence['automatic_status'],
                            lineage=evidence.get('observation_history',[]))
            original=cv2.resize(image,(width,height));overlay=original.copy()
            for name,color in [('outside',(240,160,60)),('inside',(80,220,80))]:
                cv2.polylines(overlay,[np.rint(np.array(scene['zones'][name])*[width,height]).astype(np.int32)],True,color,1)
            cv2.polylines(overlay,[np.rint(np.array(region['polygon'])*[width,height]).astype(np.int32)],True,(220,200,40),2)
            cv2.line(overlay,tuple(np.rint(np.array(scene['line'][0])*[width,height]).astype(int)),
                     tuple(np.rint(np.array(scene['line'][1])*[width,height]).astype(int)),(220,80,220),2)
            label='No bound candidate observation yet.'
            if focus:
                last=focus['last'];b=pixel_box(last['bbox'],(w,h));current=abs(last['pts']-at)<1e-6
                color=(80,230,100) if current else (50,200,255)
                cv2.rectangle(overlay,xy(b[:2]),xy(b[2:]),color,2)
                cv2.putText(overlay,('NOW' if current else 'LAST')+f" {last['pts']:.3f}s",xy(b[:2]),0,.5,color,2)
                motion=focus['motion'];end=motion.get('end_pts');delta=motion.get('displacement_pixels')
                recent=end is not None and 0<=at-end<=engine.policy.history_seconds+1e-9
                if recent and delta and motion['direction']!='unknown':
                    center=[(b[0]+b[2])/2,(b[1]+b[3])/2]
                    cv2.arrowedLine(overlay,xy(center),xy([center[k]+3*delta[k] for k in (0,1)]),(30,80,255),3,tipLength=.25)
                label=f"{focus['run_id']} | LAST actual {last['pts']:.6f}s | motion {motion['direction'] if recent else 'unknown/stale'} at {end} | {focus['automatic_status']}"
            labels=[f'SOURCE {at:.6f}s | ORIGINAL left / EXP47 state + last actual + measured direction right',
                ' / '.join(f"{c['automatic_status']} [first {c['first_notification_pts']:.3f}, confirm {c['first_confirmation_pts']}]" for c in cards) or 'No incident yet.',
                label,'Yellow portal; green inside; blue outside; red mean movement x3 (hidden when stale). Historical box retains LAST time.',
                'Automatic rule / human review separate; lineage is not verified identity. External notifications disabled.']
            canvas=np.zeros((height+header,width*2,3),dtype=np.uint8)
            canvas[header:,:width]=original;canvas[header:,width:]=overlay
            banner=Image.fromarray(canvas[:header,:,::-1]);draw=ImageDraw.Draw(banner)
            for i,label in enumerate(labels):draw.text((10,2+i*30),label,font=font,fill=(235,235,235))
            canvas[:header]=np.asarray(banner)[:,:,::-1]
            mapping=dict(frame_index=index,native_pts=row['native_pts'],time_base=row['time_base'],
                source_pts=at,cards=cards,focus=focus)
            for spec,container,stream in handles:
                if not spec['start']-1e-9<=at<=spec['end']+1e-9:continue
                frame=av.VideoFrame.from_ndarray(canvas,format='bgr24')
                frame.pts=row['native_pts']-spec['first_native_pts'];frame.time_base=tb
                for packet in stream.encode(frame):container.mux(packet)
                spec['mapping'].append(dict(mapping,presentation_pts=float(frame.pts*tb)))
    finally:
        for _,container,stream in handles:
            for packet in stream.encode():container.mux(packet)
            container.close()
    for spec,_,_ in handles:
        validate_mapping(spec['mapping'])
        with av.open(spec['path']) as container:
            actual=[float(f.pts*f.time_base) for f in container.decode(video=0)]
        expected=[r['presentation_pts'] for r in spec['mapping']]
        if len(actual)!=len(expected) or any(abs(a-b)>1e-6 for a,b in zip(actual,expected)):
            raise ValueError('Encoded native clock mismatch')
        spec.update(frames=len(expected),sha256=sha(spec['path']))
    if protected!={p:sha(p) for p in protected}:raise ValueError('Protected media inputs changed')
    manifest=dict(experiment='EXP-0047',video_id=result['video_id'],videos=specs,
        input_sha256=protected,source_frames_decoded=decoded,elapsed_seconds=time.perf_counter()-begin,
        actual_release_groups=sum(s['kind']=='actual_releases' for s in specs),
        pixels_local_only=True,actual_loss_classifications=0,detector_calls=0,tracker_calls=0,
        flow_calls=0,vlm_calls=0,human_verified=False,font_sha256=sha(font_path),
        source_clock_validation='Every encoded frame locally decoded and compared with native mapping')
    save(output/'manifest.json',manifest)
    return dict(video_id=result['video_id'],videos=[s['path'] for s in specs],elapsed_seconds=manifest['elapsed_seconds'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('directory','paths','baseline','portal-result'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(json.dumps(execute(a.directory,a.paths,a.baseline,a.portal_result),indent=2))

if __name__=='__main__':main()
