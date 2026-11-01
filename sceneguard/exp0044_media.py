"""Simple local-only EXP44 videos from saved observations and exact native PTS.

No new flow, detection, tracking, long trails, or action score. Automatic states
are prefix-only; manual review remains separate and is never fabricated here.
"""
import argparse
from bisect import bisect_right
from fractions import Fraction
import json
from pathlib import Path
import time

from .directional_loss import SavedGateDirection, pixel_box
from .exp0044_application import sha, save
from .incident_notifications import notification_cards_at

AUTOMATIC_LABELS={'confirmed':'침입 확인 · 자동','suspicion':'침입 의심',
                  'deferred':'판단 불가','pending':'판정 대기'}


def motion_display(motion, pts, history_seconds=1.):
    age=None if motion is None else max(0.,pts-motion['end_pts'])
    return dict(age_seconds=age,arrow_visible=age is not None and age<=history_seconds+1e-9)


def frame_clock(row):
    value=Fraction(row['native_pts'])*Fraction(row['time_base'])
    if abs(float(value)-row['pts'])>1e-9:
        raise ValueError('Native source clock mismatch')
    return value


def causal_case(segment, decision, pts, engine, previous=None):
    """Use only actual segment prefix; never show future location/direction/state."""
    rows=[r for r in segment['rows'] if r['pts']<=pts+1e-9]
    if not rows:
        return None
    current=engine.direction(dict(segment,rows=rows))
    # The last valid direction may precede the last actual observation.
    motion=current if current['direction']!='unknown' else previous
    decided=pts+1e-9>=decision['decision_time_pts']
    return dict(segment=segment['id'],last=rows[-1],motion=motion,
        loss_wait_elapsed=max(0.,pts-rows[-1]['pts']),
        automatic_status=(('confirmed' if decision['automatic_confirmation'] else
            'suspicion' if decision['notify'] else 'deferred') if decided else 'pending'),
        decision_available=decided,
        reason=decision['reason'] if decided else None,
        decision_time_pts=decision['decision_time_pts'] if decided else None)


def execute(directory, paths_directory, baseline_path, media_name='media-v2'):
    import av
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    from .run_tracklet_linking import decode_native

    begin=time.perf_counter();directory=Path(directory);paths=Path(paths_directory)
    baseline=json.loads(Path(baseline_path).read_text())
    proposal=json.loads((directory/'directional-cards.json').read_text())
    scene_path=Path(baseline['source_paths']['scene'])
    scene=json.loads(scene_path.read_text())
    evidence=paths/'frame-evidence.jsonl'
    frames=[json.loads(line) for line in evidence.read_text().splitlines() if line.strip()]
    source=Path(baseline['source_paths']['video'])
    protected={str(p):sha(p) for p in (source,evidence,scene_path,Path(baseline_path),
        directory/'directional-cards.json',directory/'baseline-cards.json',Path(__file__))}
    clocks=[frame_clock(r) for r in frames]
    if any(b<=a for a,b in zip(clocks,clocks[1:])):raise ValueError('Increasing native PTS required')
    engine=SavedGateDirection(frames,scene)
    segments={s['id']:s for s in baseline['segments']}
    decisions={d['segment']:d for d in proposal['decisions']}
    if media_name not in ('media','media-v2'):raise ValueError('Fixed local media destination required')
    output=directory/media_name;output.mkdir(exist_ok=False)
    font_path=Path('/mnt/c/Windows/Fonts/malgun.ttf')
    font=ImageFont.truetype(str(font_path),22)
    specs=[dict(name='continuous',segment=None,start=frames[0]['pts'],end=frames[-1]['pts'])]
    for sid,d in decisions.items():
        specs.append(dict(name='case-'+sid,segment=sid,
            start=max(frames[0]['pts'],d['last_observed_pts']-1.5),
            end=min(frames[-1]['pts'],d['decision_time_pts']+1.)))
    width,height,header=960,540,190
    w,h=scene['source_size'];scale=np.array([width/w,height/h])
    tb=Fraction(frames[0]['time_base']);rate=1/(clocks[1]-clocks[0]);handles=[]
    for spec in specs:
        chosen=[r for r in frames if spec['start']-1e-9<=r['pts']<=spec['end']+1e-9]
        spec.update(path=str(output/(spec['name']+'.mp4')),mapping=[],first_native_pts=chosen[0]['native_pts'])
        container=av.open(spec['path'],'w');stream=container.add_stream('libx264',rate=rate)
        stream.width=width*2;stream.height=height+header;stream.pix_fmt='yuv420p'
        stream.time_base=tb;stream.codec_context.time_base=tb
        stream.options={'crf':'21','preset':'fast'}
        handles.append((spec,container,stream))
    cached={};last_motion={};decoded=0
    def xy(p):return tuple(np.rint(np.asarray(p)*scale).astype(int))
    def paint(image,state,pts,cards):
        original=cv2.resize(image,(width,height));overlay=original.copy()
        for name,color in [('outside',(240,160,60)),('inside',(80,220,80))]:
            polygon=np.asarray(scene['zones'][name])*[w,h]
            cv2.polylines(overlay,[np.rint(polygon*scale).astype(np.int32)],True,color,1)
            center=engine.geometry['zone_centers'][name]
            cv2.circle(overlay,xy(center),4,color,-1)
            cv2.putText(overlay,name+' center',xy(center),0,.5,color,1)
        a=engine.geometry['a'];v=engine.geometry['vector'];mid=[a[k]+v[k]/2 for k in (0,1)]
        cv2.line(overlay,xy(a),xy([a[k]+v[k] for k in (0,1)]),(240,90,220),2)
        normal=engine.geometry['inward_normal']
        if normal:
            cv2.arrowedLine(overlay,xy(mid),xy([mid[k]+normal[k]*100 for k in (0,1)]),(60,255,255),3,tipLength=.25)
            cv2.putText(overlay,'INWARD',xy(mid),0,.6,(60,255,255),2)
        labels=[f"source {pts:.6f}s | ORIGINAL (left) / DIRECTION + LAST ACTUAL OBSERVATION (right)",
            'Automatic rule is separate from manual review; human_verified=false. No new detector or flow.']
        if state:
            last=state['last'];b=pixel_box(last['bbox'],(w,h));center=[(b[0]+b[2])/2,(b[1]+b[3])/2]
            cv2.rectangle(overlay,xy(b[:2]),xy(b[2:]),(50,220,255),2)
            cv2.circle(overlay,xy(center),4,(50,220,255),-1)
            motion=state['motion']
            display=motion_display(motion,pts,engine.policy.history_seconds)
            if motion and motion.get('displacement_pixels') and display['arrow_visible']:
                delta=motion['displacement_pixels']
                cv2.arrowedLine(overlay,xy(center),xy([center[k]+delta[k]*3 for k in (0,1)]),(30,80,255),3,tipLength=.25)
            labels.extend([f"case {state['segment']} | last actual {last['pts']:.6f}s | loss wait {state['loss_wait_elapsed']:.3f}/1.000s",
                f"motion {motion['direction'] if motion and display['arrow_visible'] else 'unknown / stale no arrow'} (x3) | last valid {motion['end_pts'] if motion else 'none'} | age {display['age_seconds']} | paired {len(motion.get('point_ids',[])) if motion else 0}",
                f"자동 판정: {AUTOMATIC_LABELS[state['automatic_status']]} | 판정 시각 {state['decision_time_pts']} | 사용자 수동 검토: 별도"])
        else:labels.extend(['No target-bound candidate observation available yet.','',''])
        labels.append('Causal cards: '+', '.join(('confirmed' if c['automatic_confirmation'] else 'suspicion')+
            f" [notice {c['first_notification_pts']}, first auto {c['first_confirmation_pts']}]" for c in cards))
        canvas=np.zeros((height+header,width*2,3),dtype=np.uint8)
        canvas[header:,:width]=original;canvas[header:,width:]=overlay
        # Render only the header via the already installed Korean font; raw
        # media and overlays stay in this local process.
        banner=Image.fromarray(canvas[:header,:,::-1]);draw=ImageDraw.Draw(banner)
        for n,label in enumerate(labels):draw.text((10,3+n*29),label,font=font,fill=(235,235,235))
        canvas[:header]=np.asarray(banner)[:,:,::-1]
        return canvas
    try:
        for index,image in decode_native(source,frames):
            decoded+=1;row=frames[index];states={}
            for sid,d in decisions.items():
                segment=segments[sid]
                if not segment['rows'][0]['pts']<=row['pts']<=d['decision_time_pts']+1.+1e-9:continue
                last_i=bisect_right([r['pts'] for r in segment['rows']],row['pts']+1e-9)-1
                key=(sid,last_i)
                if key not in cached:
                    cached[key]=causal_case(segment,d,row['pts'],engine,last_motion.get(sid))
                    if cached[key] and cached[key]['motion']:last_motion[sid]=cached[key]['motion']
                # Waiting and verdict clocks advance even when no new actual row arrives.
                state=dict(cached[key]);decided=row['pts']+1e-9>=d['decision_time_pts']
                state.update(loss_wait_elapsed=max(0.,row['pts']-state['last']['pts']),
                    automatic_status=(('confirmed' if d['automatic_confirmation'] else 'suspicion' if d['notify'] else 'deferred') if decided else 'pending'),
                    decision_available=decided,reason=d['reason'] if decided else None,
                    decision_time_pts=d['decision_time_pts'] if decided else None)
                states[sid]=state
            cards=notification_cards_at(proposal['timeline'],row['pts'])
            for spec,container,stream in handles:
                if not spec['start']-1e-9<=row['pts']<=spec['end']+1e-9:continue
                state=states.get(spec['segment']) if spec['segment'] else max(states.values(),key=lambda s:s['last']['pts'],default=None)
                canvas=paint(image,state,row['pts'],cards)
                frame=av.VideoFrame.from_ndarray(canvas,format='bgr24')
                frame.pts=row['native_pts']-spec['first_native_pts'];frame.time_base=tb
                for packet in stream.encode(frame):container.mux(packet)
                spec['mapping'].append(dict(frame_index=index,native_pts=row['native_pts'],time_base=row['time_base'],
                    source_pts=row['pts'],presentation_pts=float(frame.pts*tb),
                    focus_segment=state['segment'] if state else None,
                    last_actual_pts=state['last']['pts'] if state else None,
                    last_valid_direction_pts=state['motion']['end_pts'] if state and state['motion'] else None,
                    automatic_status=state['automatic_status'] if state else None,
                    automatic_label=AUTOMATIC_LABELS[state['automatic_status']] if state else None,
                    motion_arrow_visible=motion_display(state['motion'],row['pts'])['arrow_visible'] if state else False,
                    first_confirmation_pts=[c['first_confirmation_pts'] for c in cards]))
    finally:
        for spec,container,stream in handles:
            for packet in stream.encode():container.mux(packet)
            container.close()
    for spec,_,_ in handles:
        with av.open(spec['path']) as container:actual=[float(f.pts*f.time_base) for f in container.decode(video=0)]
        expected=[r['presentation_pts'] for r in spec['mapping']]
        if len(actual)!=len(expected) or any(abs(a-b)>1e-6 for a,b in zip(actual,expected)):
            raise ValueError('Encoded/source clock mismatch: '+spec['name'])
        for row in spec['mapping']:
            if row['last_actual_pts'] is not None and row['last_actual_pts']>row['source_pts']+1e-9:raise ValueError('Future box')
            if row['last_valid_direction_pts'] is not None and row['last_valid_direction_pts']>row['source_pts']+1e-9:raise ValueError('Future direction')
            if any(t is not None and t>row['source_pts']+1e-9 for t in row['first_confirmation_pts']):raise ValueError('Future automatic card')
        spec.update(frames=len(expected),sha256=sha(spec['path']))
    if protected!={p:sha(p) for p in protected}:raise ValueError('Protected render input changed')
    manifest=dict(experiment='EXP-0044',video_id=baseline['video_id'],videos=specs,
        source_frames_decoded=decoded,frames_encoded=sum(s['frames'] for s in specs),
        elapsed_seconds=time.perf_counter()-begin,input_sha256=protected,
        source_clock_validation='every encoded frame locally decoded and compared to native source intervals',
        pixels_local_only=True,flow_calls=0,detector_calls=0,tracker_calls=0,vlm_calls=0,
        human_verified=False,long_trails=False,action_score=False,
        font_path=str(font_path),font_sha256=sha(font_path),
        stale_direction_arrow_hidden_after_seconds=engine.policy.history_seconds)
    save(output/'manifest.json',manifest)
    return {k:v for k,v in manifest.items() if k not in ('videos','input_sha256')}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory',type=Path,required=True);p.add_argument('--paths',type=Path,required=True)
    p.add_argument('--baseline',type=Path,required=True);a=p.parse_args()
    print(json.dumps(execute(a.directory,a.paths,a.baseline),indent=2))

if __name__=='__main__':main()
