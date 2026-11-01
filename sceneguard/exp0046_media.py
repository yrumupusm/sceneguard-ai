"""Local-only EXP46 original/evidence media with causal native-PTS mappings.

Reads completed results; never classifies a loss again or runs a vision model.
Historical boxes are labelled with their observation PTS, never drawn as current.
"""
import argparse
from bisect import bisect_right
from fractions import Fraction
import json
import math
from pathlib import Path
import time

from .directional_loss import SavedGateDirection, pixel_box
from .exp0044_application import sha, save
from .exp0044_media import frame_clock
from .gate_episode_evidence import EpisodePolicy, Gate
from .incident_notifications import notification_cards_at

from .exp0045_media import (causal_history, causal_birth, displayed_motion,
    inward_band, specs_for, validate_mapping as validate_legacy_mapping)
from .portal_births import KIND


def causal_observation(audit, observations, frames, at, event=None):
    """Actual prefix only; the candidate and decision appear at their decision PTS."""
    if audit['birth_pts'] > at+1e-9:
        return None
    rows = [r for r in observations if r['pts'] <= at+1e-9]
    if not rows:
        return None
    prior = [dict(pts=f['pts'], frame_index=f['frame_index'],
                  actual_boxes=[b for b in f['actual_boxes'] if b.get('observed') is not False])
             for f in frames if audit['birth_pts']-1.-1e-9 <= f['pts'] < audit['birth_pts']-1e-9]
    decision = event['decision_time_pts'] if event and event['decision_time_pts'] <= at+1e-9 else None
    return dict(run_id=audit['run_id'],first_pts=audit['birth_pts'],first_bbox=audit['bbox'],
        last_pts=rows[-1]['pts'],last_bbox=rows[-1]['bbox'],
        current=abs(rows[-1]['pts']-at)<1e-6,observation_refs=rows,
        prior_actual_observations=prior,site=audit['site'],eligible=audit['eligible'],
        decision_time_pts=decision,candidate=decision is not None)


def validate_mapping(rows):
    validate_legacy_mapping(rows)
    for row in rows:
        focus=row.get('portal_observation')
        if not focus:
            continue
        at=row['source_pts']
        if focus['first_pts'] > at+1e-9 or focus['last_pts'] > at+1e-9:
            raise ValueError('Future portal actual observation')
        if focus['decision_time_pts'] is not None and focus['decision_time_pts'] > at+1e-9:
            raise ValueError('Future portal decision')
        if any(r['pts'] > at+1e-9 for r in focus['observation_refs']):
            raise ValueError('Future portal support')
        if any(r['pts'] >= focus['first_pts']-1e-9 for r in focus['prior_actual_observations']):
            raise ValueError('Prior observation must predate the first actual box')


def execute(directory, paths_directory, baseline_path, review_runs=()):
    import av
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    from .run_tracklet_linking import decode_native

    started=time.perf_counter(); directory=Path(directory); paths=Path(paths_directory)
    baseline=json.loads(Path(baseline_path).read_text())
    scene=json.loads((directory/'scene-used.json').read_text())
    evidence=paths/'frame-evidence.jsonl'
    frames=[json.loads(line) for line in evidence.read_text().splitlines() if line.strip()]
    decisions=json.loads((directory/'history-decisions.json').read_text())
    births=json.loads((directory/'inside-birth-events.json').read_text())
    audits=json.loads((directory/'birth-audits.json').read_text())['portal']
    region=json.loads((directory/'portal-region.json').read_text())
    observation_runs=json.loads((directory/'observation-runs.json').read_text())
    review_audits=[a for a in audits if a['run_id'] in review_runs]
    if set(review_runs) != {a['run_id'] for a in review_audits}:
        raise ValueError('Review selection must reference existing saved birth audits')
    views={mode:json.loads((directory/(mode+'-cards.json')).read_text())
           for mode in ('baseline','history','portal-only','combined')}
    source=Path(baseline['source_paths']['video'])
    inputs=[source,evidence,Path(baseline_path),directory/'scene-used.json',
        directory/'history-decisions.json',directory/'inside-birth-events.json',directory/'birth-audits.json',
        directory/'portal-region.json',directory/'observation-runs.json',
        *(directory/(mode+'-cards.json') for mode in views)]
    code=[Path(__file__),Path(__file__).with_name('directional_loss.py'),
          Path(__file__).with_name('gate_episode_evidence.py'),Path(__file__).with_name('exp0045_media.py'),
          Path(__file__).with_name('exp0044_media.py'),Path(__file__).with_name('run_tracklet_linking.py')]
    protected={str(p):sha(p) for p in inputs+code}
    gate=Gate(scene); engine=SavedGateDirection(frames,scene)
    segments={s['id']:s for s in baseline['segments']}; by_segment={d['segment']:d for d in decisions}
    output=directory/'media'; output.mkdir(exist_ok=False)
    specs=specs_for(frames,decisions,births)
    existing={s['segment'] for s in specs}
    for decision in decisions:
        if decision['automatic_confirmation'] and decision['segment'] not in existing:
            specs.append(dict(name='history-'+decision['segment'],segment=decision['segment'],birth_event_id=None,
                start=max(frames[0]['pts'],decision['last_observed_pts']-2.),
                end=min(frames[-1]['pts'],decision['decision_time_pts']+1.)))
    for audit in review_audits:
        specs.append(dict(name='first-observation-'+audit['run_id'],segment=None,birth_event_id=None,
            review_run=audit['run_id'],start=max(frames[0]['pts'],audit['birth_pts']-1.),
            end=min(frames[-1]['pts'],audit['birth_pts']+1.5)))
    clocks=[frame_clock(row) for row in frames]
    if any(b<=a for a,b in zip(clocks,clocks[1:])):
        raise ValueError('Increasing native PTS required')
    width,height,header=960,540,260
    w,h=scene['source_size']; scale=np.array([width/w,height/h])
    tb=Fraction(frames[0]['time_base']); rate=1/(clocks[1]-clocks[0])
    font_path=Path('/mnt/c/Windows/Fonts/malgun.ttf'); font=ImageFont.truetype(str(font_path),21)
    handles=[]; cached={}; decoded=0

    def xy(p):
        return tuple(np.rint(np.asarray(p)*scale).astype(int))

    def box(image, bbox, color, label, dashed=False):
        b=pixel_box(bbox,(w,h)); a,z=xy(b[:2]),xy(b[2:])
        if dashed:
            for p,q in ((a,(z[0],a[1])),((z[0],a[1]),z),(z,(a[0],z[1])),((a[0],z[1]),a)):
                distance=math.dist(p,q)
                for offset in range(0,max(1,int(distance)),12):
                    end=min(distance,offset+6)
                    cv2.line(image,tuple(round(p[k]+(q[k]-p[k])*offset/max(distance,1)) for k in (0,1)),
                        tuple(round(p[k]+(q[k]-p[k])*end/max(distance,1)) for k in (0,1)),color,2)
        else:
            cv2.rectangle(image,a,z,color,2)
        center=((b[0]+b[2])/2,(b[1]+b[3])/2)
        cv2.circle(image,xy(center),3,color,-1)
        cv2.putText(image,label,(max(0,a[0]),max(14,a[1]-5)),0,.44,color,1)
        return center

    def paint(image,row,state,visible_births,cards,review):
        original=cv2.resize(image,(width,height)); overlay=original.copy(); at=row['pts']
        for name,color in [('outside',(240,160,60)),('inside',(80,220,80))]:
            polygon=np.asarray(scene['zones'][name])*[w,h]
            cv2.polylines(overlay,[np.rint(polygon*scale).astype(np.int32)],True,color,1)
        # Current saved detections are distinct from any historical evidence box.
        for actual in row['actual_boxes']:
            if actual.get('observed') is not False:
                box(overlay,actual['bbox'],(160,160,160),'NOW '+str(actual['cache_index']))
        focus_birth=visible_births[-1] if visible_births else None
        portal=np.rint(np.asarray(region['polygon'])*[width,height]).astype(np.int32)
        cv2.polylines(overlay,[portal],True,(220,200,40),3)
        a=gate.a; b=tuple(a[k]+gate.v[k] for k in (0,1)); mid=tuple((a[k]+b[k])/2 for k in (0,1))
        cv2.line(overlay,xy(a),xy(b),(230,80,230),3)
        for p in (a,b):cv2.circle(overlay,xy(p),5,(230,80,230),-1)
        cv2.arrowedLine(overlay,xy(mid),xy([mid[k]+gate.normal[k]*100 for k in (0,1)]),(50,255,255),3,tipLength=.25)
        cv2.putText(overlay,'INWARD (configured)',xy(mid),0,.5,(50,255,255),2)
        labels=[f"SOURCE {at:.6f}s | ORIGINAL left / EXP46 CAUSAL EVIDENCE right",
            'Cards '+ ' | '.join(f"{m}: {len(cs)} / auto {sum(c.get('automatic_confirmation',False) for c in cs)}" for m,cs in cards.items()),
            'Combined notice / first auto: '+str([(round(c['first_notification_pts'],6),c.get('first_confirmation_pts')) for c in cards['combined']]),
            'B fixed projected portal (yellow); center inside OR overlap >= 0.5; B alone is suspicion']
        if state:
            last=state['last']; current=state['current']
            center=box(overlay,last['bbox'],(50,220,255),('CURRENT' if current else 'LAST')+f" {last['pts']:.3f}",not current)
            contact=state['contact']
            if contact:
                box(overlay,contact['bbox'],(255,170,70),f"HISTORY {contact['pts']:.3f}",True)
                r=contact['radius_pixels']; outer=inward_band(gate,r)
                capsule=[outer[3],outer[2],tuple(b[k]-gate.normal[k]*r for k in (0,1)),
                         tuple(a[k]-gate.normal[k]*r for k in (0,1))]
                cv2.polylines(overlay,[np.array([xy(p) for p in capsule],dtype=np.int32)],True,(255,170,70),1)
                for p in (a,b):cv2.circle(overlay,xy(p),round(r*scale[0]),(255,170,70),1)
            motion=state['motion']; display=displayed_motion(motion,at)
            if motion and display['arrow_visible'] and motion.get('displacement_pixels'):
                delta=motion['displacement_pixels'];cv2.arrowedLine(overlay,xy(center),
                    xy([center[k]+3*delta[k] for k in (0,1)]),(40,70,255),3,tipLength=.25)
            labels.extend([f"A {state['segment']} | {'CURRENT' if current else 'LAST actual'} {last['pts']:.6f} | decision {state['decision_time_pts']} | {state['automatic_status']}",
                f"A historical near box {contact['pts'] if contact else None} | direction {motion.get('direction') if motion else 'unknown'} at {motion.get('end_pts') if motion else None} (arrow x3, hidden if >1s old)"])
        else:
            labels.extend(['A: no loss-case observation available in this local interval.',''])
        for birth in visible_births:
            box(overlay,birth['first_bbox'],(255,100,220),f"B FIRST {birth['first_pts']:.3f}",True)
            box(overlay,birth['last_bbox'],(100,255,180),('B NOW' if birth['current'] else 'B LAST')+f" {birth['last_pts']:.3f}",not birth['current'])
        if review:
            box(overlay,review['first_bbox'],(255,100,220),f"FIRST actual {review['first_pts']:.3f}",abs(review['first_pts']-at)>1e-6)
            box(overlay,review['last_bbox'],(100,255,180),('CURRENT actual' if review['current'] else 'LAST actual')+f" {review['last_pts']:.3f}",not review['current'])
            prior=review['prior_actual_observations']
            if prior:
                for observed in prior[-1]['actual_boxes']:
                    box(overlay,observed['bbox'],(190,150,80),f"PRIOR actual {prior[-1]['pts']:.3f}",True)
            site=review['site']; legacy=site['legacy_ground_test']
            labels.append(f"B {review['run_id']} | FIRST {review['first_pts']:.6f} / decision {review['decision_time_pts']} | center {site['portal_center_inside']} overlap {site['portal_box_overlap']:.3f} | old location {legacy['inside_birth_site']} | eligible {review['eligible']}")
        elif focus_birth:
            site=focus_birth['site']
            labels.append(f"B first {focus_birth['first_pts']:.6f} / decision {focus_birth['decision_time_pts']:.6f} | center {site['portal_center_inside']} overlap {site['portal_box_overlap']:.3f}")
        else:
            labels.append('B: no selected first actual observation available at this PTS.')
        labels.append('Gray=current actual; dashed=historical actual PTS; yellow=portal / inward arrow; red=measured motion; automatic rule != human review.')
        canvas=np.zeros((height+header,width*2,3),dtype=np.uint8)
        canvas[header:,:width]=original; canvas[header:,width:]=overlay
        banner=Image.fromarray(canvas[:header,:,::-1]); draw=ImageDraw.Draw(banner)
        for i,label in enumerate(labels):draw.text((10,2+i*31),label,font=font,fill=(235,235,235))
        canvas[:header]=np.asarray(banner)[:,:,::-1]
        return canvas

    try:
        for spec in specs:
            chosen=[r for r in frames if spec['start']-1e-9<=r['pts']<=spec['end']+1e-9]
            spec.update(path=str(output/(spec['name']+'.mp4')),mapping=[],first_native_pts=chosen[0]['native_pts'])
            container=av.open(spec['path'],'w'); stream=container.add_stream('libx264',rate=rate)
            stream.width=width*2; stream.height=height+header; stream.pix_fmt='yuv420p'
            stream.time_base=tb; stream.codec_context.time_base=tb
            stream.options={'crf':'21','preset':'fast','threads':'2'}
            handles.append((spec,container,stream))
        for index,image in decode_native(source,frames):
            decoded+=1; row=frames[index]; at=row['pts']; states={}
            for sid,decision in by_segment.items():
                segment=segments[sid]
                if not segment['rows'][0]['pts']<=at<=decision['decision_time_pts']+1.+1e-9:
                    continue
                end=bisect_right([r['pts'] for r in segment['rows']],at+1e-9)-1
                key=(sid,end,at+1e-9>=decision['decision_time_pts'])
                if key not in cached:
                    cached[key]=causal_history(segment,decision,at,gate,engine)
                state=dict(cached[key]); state['current']=abs(state['last']['pts']-at)<1e-6
                states[sid]=state
            visible_births=[b for event in births if event['decision_time_pts']<=at+1e-9<=event['decision_time_pts']+1.5+1e-9
                            for b in [causal_birth(event,at)] if b]
            cards={m:notification_cards_at(view['timeline'],at) for m,view in views.items()}
            for spec,container,stream in handles:
                if not spec['start']-1e-9<=at<=spec['end']+1e-9:
                    continue
                state=states.get(spec['segment']) if spec['segment'] else max(states.values(),key=lambda s:s['last']['pts'],default=None)
                bs=[b for b in visible_births if not spec['birth_event_id'] or b['event_id']==spec['birth_event_id']]
                focus_event=next((e for e in births if e['event_id']==spec['birth_event_id']),None)
                available_audits=[a for a in audits if a['birth_pts']<=at+1e-9<=a['birth_pts']+2.+1e-9
                    and (not spec.get('review_run') or a['run_id']==spec['review_run'])
                    and (not focus_event or a['run_id']==focus_event['source_event']['run_id'])]
                selected=available_audits[-1] if available_audits else None
                candidate=next((e for e in births if selected and e['source_event']['run_id']==selected['run_id']),None)
                review=causal_observation(selected,observation_runs[selected['run_id']],frames,at,candidate) if selected else None
                canvas=paint(image,row,state,bs,cards,review)
                frame=av.VideoFrame.from_ndarray(canvas,format='bgr24')
                frame.pts=row['native_pts']-spec['first_native_pts']; frame.time_base=tb
                for packet in stream.encode(frame):container.mux(packet)
                contact=state['contact'] if state else None; motion=state['motion'] if state else None
                spec['mapping'].append(dict(frame_index=index,native_pts=row['native_pts'],time_base=row['time_base'],
                    source_pts=at,presentation_pts=float(frame.pts*tb),focus_segment=state['segment'] if state else None,
                    actual_cache_indices=[b['cache_index'] for b in row['actual_boxes'] if b.get('observed') is not False],
                    last_actual_pts=state['last']['pts'] if state else None,last_box_is_current=state['current'] if state else None,
                    last_actual_bbox=state['last']['bbox'] if state else None,
                    gate_contact_pts=contact['pts'] if contact else None,gate_contact_bbox=contact['bbox'] if contact else None,
                    gate_contact_radius_pixels=contact['radius_pixels'] if contact else None,
                    motion_end_pts=motion.get('end_pts') if motion else None,
                    motion_arrow_visible=displayed_motion(motion,at)['arrow_visible'],
                    decision_time_pts=state['decision_time_pts'] if state else None,
                    automatic_status=state['automatic_status'] if state else None,
                    gate_line_normalized=scene['line'],inward_normal=gate.normal,
                    geometry_kind=KIND,portal_observation=review,
                    reviewed_first_observation=None if review is None else dict(
                        run_id=review['run_id'],first_pts=review['first_pts'],bbox=review['first_bbox'],site=review['site'],eligible=review['eligible']),
                    births=[{k:b[k] for k in ('event_id','first_pts','first_bbox','last_pts','last_bbox','decision_time_pts')} for b in bs],
                    cards={m:[dict(incident_id=c['incident_id'],first_notification_pts=c['first_notification_pts'],
                        first_confirmation_pts=c.get('first_confirmation_pts')) for c in cs] for m,cs in cards.items()}))
    finally:
        for spec,container,stream in handles:
            for packet in stream.encode():container.mux(packet)
            container.close()
    for spec,_,_ in handles:
        validate_mapping(spec['mapping'])
        with av.open(spec['path']) as container:
            actual=[float(frame.pts*frame.time_base) for frame in container.decode(video=0)]
        expected=[r['presentation_pts'] for r in spec['mapping']]
        if len(actual)!=len(expected) or any(abs(a-b)>1e-6 for a,b in zip(actual,expected)):
            raise ValueError('Encoded native clock mismatch: '+spec['name'])
        spec.update(frames=len(expected),sha256=sha(spec['path']))
    if protected!={p:sha(p) for p in protected}:
        raise ValueError('Protected media input/source changed')
    manifest=dict(experiment='EXP-0046',video_id=baseline['video_id'],videos=specs,
        source_frames_decoded=decoded,frames_encoded=sum(s['frames'] for s in specs),
        elapsed_seconds=time.perf_counter()-started,input_sha256=protected,
        code_sha256={str(p):protected[str(p)] for p in code},font_sha256=sha(font_path),
        pixels_local_only=True,detector_calls=0,tracker_calls=0,flow_calls=0,vlm_calls=0,
        actual_loss_classifications=0,source_clock_validation='every encoded frame decoded locally; native/source/presentation mapping checked',
        gate_line=scene['line'],inward_normal=gate.normal,policy=EpisodePolicy().__dict__,
        geometry_kind=KIND,portal_region=region,
        original_panel='unannotated source resized to 960x540',human_verified=False)
    manifest['review_run_selection']=list(review_runs)
    manifest['review_selection_affects_decisions']=False
    save(output/'manifest.json',manifest)
    return {k:v for k,v in manifest.items() if k not in ('videos','input_sha256')}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--paths',type=Path,required=True)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--review-run',action='append',default=[],help='Existing audit ID for display only; never changes decisions')
    args=parser.parse_args()
    print(json.dumps(execute(args.directory,args.paths,args.baseline,args.review_run),indent=2))


if __name__=='__main__':
    main()
