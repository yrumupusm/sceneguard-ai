"""Local-only EXP45 original/evidence media with causal native-PTS mappings.

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
from .exp0044_media import frame_clock, motion_display
from .gate_episode_evidence import EpisodePolicy, Gate
from .incident_notifications import notification_cards_at


def displayed_motion(motion, at):
    return motion_display(motion if motion and 'end_pts' in motion else None, at)


def inward_band(gate, radius):
    """Finite inward rectangle: no infinite line extension or far-inside region."""
    if not math.isfinite(radius) or radius <= 0:
        raise ValueError('Positive finite band width required')
    a = gate.a; b = tuple(a[k]+gate.v[k] for k in (0,1))
    return [a, b, tuple(b[k]+gate.normal[k]*radius for k in (0,1)),
            tuple(a[k]+gate.normal[k]*radius for k in (0,1))]


def causal_history(segment, decision, at, gate, engine=None):
    rows = [r for r in segment['rows'] if r['pts'] <= at+1e-9]
    if not rows:
        return None
    last = rows[-1]; decided = at+1e-9 >= decision['decision_time_pts']
    motion = (decision.get('direction') if decided else
              engine.direction(dict(segment, rows=rows)) if engine else None)
    contacts = [dict(pts=r['pts'], bbox=r['bbox'], **gate.locate(r['bbox'], birth=False))
                for r in rows if last['pts']-r['pts'] <= gate.policy.history_seconds+1e-9]
    contacts = [r for r in contacts if r['near'] and
                (not motion or r['pts'] <= motion.get('end_pts', at)+1e-9)]
    contact = decision.get('gate_contact') if decided else (contacts[-1] if contacts else None)
    if contact is None and decided:
        eligible = [r for r in decision.get('gate_history', []) if r['pts'] <= at+1e-9]
        contact = eligible[-1] if eligible else None
    return dict(segment=segment['id'], last=last, current=abs(last['pts']-at)<1e-6,
        contact=contact, motion=motion, decision_available=decided,
        decision_time_pts=decision['decision_time_pts'] if decided else None,
        automatic_status=('confirmed' if decision['automatic_confirmation'] else 'suspicion') if decided else 'pending',
        reason=decision['reason'] if decided else None)


def causal_birth(event, at):
    raw = event['source_event']
    if at+1e-9 < event['decision_time_pts']:
        return None
    refs = raw['observation_refs']
    if (not refs or refs[0]['pts'] != raw['birth_pts'] or
            any(r['pts'] > event['decision_time_pts']+1e-9 for r in refs)):
        raise ValueError('Causal actual birth references required')
    return dict(event_id=event['event_id'], first_pts=raw['birth_pts'],
        first_bbox=raw['first_actual_bbox'], last_pts=refs[-1]['pts'],
        last_bbox=raw['current_actual_bbox'], current=abs(refs[-1]['pts']-at)<1e-6,
        decision_time_pts=event['decision_time_pts'], site=raw['birth_site'])


def validate_mapping(rows):
    previous = -math.inf
    for row in rows:
        at = row['source_pts']
        if at <= previous or abs(float(frame_clock(dict(pts=at, native_pts=row['native_pts'],
                                                       time_base=row['time_base'])))-at)>1e-9:
            raise ValueError('Increasing exact native frame clock required')
        previous = at
        for key in ('last_actual_pts','gate_contact_pts','motion_end_pts','decision_time_pts'):
            if row.get(key) is not None and row[key] > at+1e-9:
                raise ValueError('Future evidence: '+key)
        for birth in row['births']:
            if any(birth[k] > at+1e-9 for k in ('first_pts','last_pts','decision_time_pts')):
                raise ValueError('Future birth evidence')
        review=row.get('reviewed_first_observation')
        if review and review['first_pts'] > at+1e-9:
            raise ValueError('Future reviewed first box')
        for mode, cards in row['cards'].items():
            for card in cards:
                if card['first_notification_pts'] > at+1e-9 or (
                        card.get('first_confirmation_pts') is not None and card['first_confirmation_pts'] > at+1e-9):
                    raise ValueError('Future card state: '+mode)


def specs_for(frames, decisions, births):
    start, end = frames[0]['pts'], frames[-1]['pts']
    specs = [dict(name='continuous', segment=None, birth_event_id=None, start=start, end=end)]
    # Preserve a short local review artifact for every new automatic upgrade.
    for decision in decisions:
        if decision['reason'] != 'recent_gate_encounter_inward_then_loss':
            continue
        contact = decision['gate_contact']['pts']
        specs.append(dict(name='history-'+decision['segment'], segment=decision['segment'], birth_event_id=None,
            start=max(start, min(contact,decision['last_observed_pts'])-1.),
            end=min(end,decision['decision_time_pts']+1.)))
    for event in births:
        specs.append(dict(name='birth-'+event['event_id'][:12], segment=None, birth_event_id=event['event_id'],
            start=max(start,event['source_event']['birth_pts']-1.),
            end=min(end,event['decision_time_pts']+1.5)))
    return specs


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
    audits=json.loads((directory/'birth-audits.json').read_text())
    review_audits=[a for a in audits if a['run_id'] in review_runs]
    if set(review_runs) != {a['run_id'] for a in review_audits}:
        raise ValueError('Review selection must reference existing saved birth audits')
    views={mode:json.loads((directory/(mode+'-cards.json')).read_text())
           for mode in ('baseline','history','birth-only','combined')}
    source=Path(baseline['source_paths']['video'])
    inputs=[source,evidence,Path(baseline_path),directory/'scene-used.json',
        directory/'history-decisions.json',directory/'inside-birth-events.json',directory/'birth-audits.json',
        *(directory/(mode+'-cards.json') for mode in views)]
    code=[Path(__file__),Path(__file__).with_name('directional_loss.py'),
          Path(__file__).with_name('gate_episode_evidence.py'),
          Path(__file__).with_name('exp0044_media.py'),Path(__file__).with_name('run_tracklet_linking.py')]
    protected={str(p):sha(p) for p in inputs+code}
    gate=Gate(scene); engine=SavedGateDirection(frames,scene)
    segments={s['id']:s for s in baseline['segments']}; by_segment={d['segment']:d for d in decisions}
    output=directory/'media'; output.mkdir(exist_ok=False)
    specs=specs_for(frames,decisions,births)
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
        focus_bbox=review['bbox'] if review else focus_birth['first_bbox'] if focus_birth else state['last']['bbox'] if state else None
        radius=gate.locate(focus_bbox)['radius_pixels'] if focus_bbox else min(w,h)*gate.policy.maximum_near_image_fraction
        band=np.array([xy(p) for p in inward_band(gate,radius)],dtype=np.int32)
        cv2.polylines(overlay,[band],True,(220,200,40),2)
        a=gate.a; b=tuple(a[k]+gate.v[k] for k in (0,1)); mid=tuple((a[k]+b[k])/2 for k in (0,1))
        cv2.line(overlay,xy(a),xy(b),(230,80,230),3)
        for p in (a,b):cv2.circle(overlay,xy(p),5,(230,80,230),-1)
        cv2.arrowedLine(overlay,xy(mid),xy([mid[k]+gate.normal[k]*100 for k in (0,1)]),(50,255,255),3,tipLength=.25)
        cv2.putText(overlay,'INWARD (configured)',xy(mid),0,.5,(50,255,255),2)
        labels=[f"SOURCE {at:.6f}s | ORIGINAL left / EXP45 CAUSAL EVIDENCE right",
            'Cards '+ ' | '.join(f"{m}: {len(cs)} / auto {sum(c.get('automatic_confirmation',False) for c in cs)}" for m,cs in cards.items()),
            'Combined notice / first auto: '+str([(round(c['first_notification_pts'],6),c.get('first_confirmation_pts')) for c in cards['combined']]),
            f"B finite inward band {radius:.2f}px ({'first box' if focus_birth or review else 'current/last box reference' if focus_bbox else 'maximum width only'}); B candidates are NOT people counts"]
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
            box(overlay,review['bbox'],(255,100,220),f"FIRST rejected {review['birth_pts']:.3f}",True)
            site=review['site']
            closest=tuple(gate.a[k]+min(1.,max(0.,site['along']))*gate.v[k] for k in (0,1))
            cv2.line(overlay,xy(site['center_pixels']),xy(closest),(255,100,220),1)
            labels.append(f"B REJECTED first {review['birth_pts']:.6f} | distance {site['distance_pixels']:.2f} / width {site['radius_pixels']:.2f}px | along {site['along']:.3f} | eligible {review['eligible']}")
        elif focus_birth:
            labels.append(f"B first {focus_birth['first_pts']:.6f} / decision {focus_birth['decision_time_pts']:.6f} | distance {focus_birth['site']['distance_pixels']:.2f} / allowed {focus_birth['site']['radius_pixels']:.2f}px")
        else:
            labels.append('B: no emitted new-observation candidate available at this PTS.')
        labels.append('Gray=actual NOW; dashed=historical PTS; yellow=configured inward, red=measured motion; automatic rule != human review.')
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
                available_audits=[a for a in review_audits if a['birth_pts']<=at+1e-9<=a['birth_pts']+1.5+1e-9
                                  and (not spec.get('review_run') or a['run_id']==spec['review_run'])]
                review=available_audits[-1] if available_audits else None
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
                    reviewed_first_observation=None if review is None else dict(
                        run_id=review['run_id'],first_pts=review['birth_pts'],bbox=review['bbox'],site=review['site'],eligible=review['eligible']),
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
    manifest=dict(experiment='EXP-0045',video_id=baseline['video_id'],videos=specs,
        source_frames_decoded=decoded,frames_encoded=sum(s['frames'] for s in specs),
        elapsed_seconds=time.perf_counter()-started,input_sha256=protected,
        code_sha256={str(p):protected[str(p)] for p in code},font_sha256=sha(font_path),
        pixels_local_only=True,detector_calls=0,tracker_calls=0,flow_calls=0,vlm_calls=0,
        actual_loss_classifications=0,source_clock_validation='every encoded frame decoded locally; native/source/presentation mapping checked',
        gate_line=scene['line'],inward_normal=gate.normal,policy=EpisodePolicy().__dict__,
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
