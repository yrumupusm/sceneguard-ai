"""Local original/EXP48/EXP49 comparison, using only causal saved snapshots.

Rendering never recomputes a decision. Every encoded frame is independently
fully decoded and checked against native, source, and presentation PTS.
"""
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
import argparse
import json
import time
from .exp0049_application import load, save, sha
from .exp0044_media import frame_clock
from .gate_activity_episodes import activity_cards_at
from .incident_lifecycle import lifecycle_cards_at

CONTRACT = 'EXP0049_threeway_gate_activity_v1'


def snapshot(result, at):
    """All cards' latest full evidence snapshots, never only the last card row."""
    states = {}
    for row in result['timeline']:
        if row['decision_time_pts'] > at+1e-9: break
        for state in row['evidence']:
            states[state['event_id']] = deepcopy(state)
    cards_at = activity_cards_at if result['experiment']=='EXP-0049' else lifecycle_cards_at
    return dict(cards=cards_at(result['timeline'], at), evidence=list(states.values()))


def specs_for(frames, result):
    specs = [dict(name='continuous', kind='full_comparison', start=frames[0]['pts'], end=frames[-1]['pts'])]
    # Change windows are selected for explanation, never used by grouping rules.
    if result['video_id']=='E01_030':
        specs.append(dict(name='continued-gate-event', kind='changed_grouping', start=96., end=frames[-1]['pts']))
    else:
        specs.append(dict(name='grouping-confirmation-closure', kind='changed_grouping', start=71.5, end=75.))
    # Preserve any actual observation gap that splits source-card membership.
    source_to_new = result['source_to_activity_cards']
    for card in result['closed_cards']:
        if any(len(source_to_new[s])>1 for s in card['source_incident_ids']):
            at=card['observation_closed_pts']
            specs.append(dict(name='observation-gap-'+str(len(specs)), kind='actual_gap_original_context',
                start=max(frames[0]['pts'], (card['last_gate_observation_pts'] or card['first_alert_pts'])-1.),
                end=min(frames[-1]['pts'],at+1.)))
    return specs


def validate_mapping(rows):
    previous = None
    for row in rows:
        at=row['source_pts']
        if previous is not None and at<=previous: raise ValueError('Increasing source PTS required')
        if abs(float(Fraction(row['native_pts'])*Fraction(row['time_base']))-at)>1e-9:
            raise ValueError('Native/source mismatch')
        if abs(row['presentation_pts']-(at-rows[0]['source_pts']))>1e-7:
            raise ValueError('Presentation/source mismatch')
        for layer in ('exp48','exp49'):
            for card in row[layer]['cards']:
                for key in ('first_alert_pts','lifecycle_updated_pts','first_confirmation_pts',
                            'observation_closed_pts','last_gate_observation_pts'):
                    if card.get(key) is not None and card[key]>at+1e-9: raise ValueError('Future card state')
                for ref in card.get('last_gate_observation_refs',[]):
                    if ref['pts']>at+1e-9: raise ValueError('Future gate reference')
            for state in row[layer]['evidence']:
                for key in ('opened_pts','last_state_change_pts','first_confirmation_pts','released_pts'):
                    if state.get(key) is not None and state[key]>at+1e-9: raise ValueError('Future evidence')
                for handoff in state.get('observation_history',[]):
                    if handoff['pts']>at+1e-9: raise ValueError('Future evidence routing')
        if any(abs(b['actual_pts']-at)>1e-9 for b in row['actual_boxes']):
            raise ValueError('Current box source mismatch')
        if any(b['actual_pts']>at+1e-9 for b in row['last_gate_boxes']):
            raise ValueError('Future actual gate box')
        if any(r['pts']!=at or r['frame_index']!=row['frame_index'] for r in row['portal_observation_refs']):
            raise ValueError('Portal presence must use current actual frame')
        if any(r['decision_time_pts']>at+1e-9 for r in row['routing']):
            raise ValueError('Future source routing')
        previous=at


def execute(directory, paths_directory, baseline_path, portal_directory):
    import av
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    from .run_tracklet_linking import decode_native
    begin=time.perf_counter();directory=Path(directory);paths=Path(paths_directory);portal=Path(portal_directory)
    result=load(directory/'activity-cards.json');prior=load(directory/'prior-lifecycle-preserved.json')
    if result.get('experiment')!='EXP-0049' or prior.get('experiment')!='EXP-0048':
        raise ValueError('Distinct EXP49/48 contracts required')
    baseline=load(baseline_path);source=Path(baseline['source_paths']['video'])
    frames=[json.loads(line) for line in (paths/'frame-evidence.jsonl').read_text().splitlines() if line.strip()]
    region=load(portal/'portal-region.json');font_path=Path('/mnt/c/Windows/Fonts/malgun.ttf')
    inputs=[source, Path(baseline_path), paths/'frame-evidence.jsonl', directory/'activity-cards.json',
        directory/'prior-lifecycle-preserved.json',directory/'request.json',portal/'portal-region.json',
        font_path,Path(__file__),Path(__file__).with_name('gate_activity_episodes.py'),
        Path(__file__).with_name('incident_lifecycle.py')]
    protected={str(p):sha(p) for p in inputs}
    output=directory/'media'
    if output.exists() or output.is_symlink() or any(p.is_symlink() for p in output.parents):
        raise ValueError('Fresh non-symlink local media directory required')
    output.mkdir()
    clocks=[frame_clock(f) for f in frames]
    if any(b<=a for a,b in zip(clocks,clocks[1:])): raise ValueError('Unordered source clock')
    tb=Fraction(frames[0]['time_base']);rate=1/(clocks[1]-clocks[0])
    width,height,header=640,360,240;font=ImageFont.truetype(str(font_path),16)
    specs=specs_for(frames,result);handles=[]
    lookup={(f['frame_index'],b['cache_index']):(f,b) for f in frames for b in f['actual_boxes']}
    for spec in specs:
        chosen=[r for r in frames if spec['start']-1e-9<=r['pts']<=spec['end']+1e-9]
        spec.update(path=str(output/(spec['name']+'.mp4')), mapping=[],first_native_pts=chosen[0]['native_pts'])
        container=av.open(spec['path'],'w');stream=container.add_stream('libx264',rate=rate)
        stream.width=width*3;stream.height=height+header;stream.pix_fmt='yuv420p'
        stream.time_base=tb;stream.codec_context.time_base=tb
        stream.options={'crf':'21','preset':'fast','threads':'2'}
        handles.append((spec,container,stream))
    decoded=0
    def rect(image, bbox, color, label, thick=1):
        x1,y1,x2,y2=np.rint(np.array(bbox)*[width,height,width,height]).astype(int)
        cv2.rectangle(image,(x1,y1),(x2,y2),color,thick)
        cv2.putText(image,label,(x1,max(12,y1-3)),0,.35,color,1)
    try:
        for index,img in decode_native(source,frames):
            row=frames[index];at=row['pts'];decoded+=1
            actual=[dict(b, actual_pts=at) for b in row['actual_boxes']]
            views={layer:snapshot(r,at) for layer,r in [('exp48',prior),('exp49',result)]}
            audit=result['activity_audit'][index]
            gate_boxes=[]
            for card in views['exp49']['cards']:
                for ref in card['last_gate_observation_refs']:
                    saved,box=lookup[(ref['frame_index'],ref['cache_index'])]
                    if saved['pts']!=ref['pts']: raise ValueError('Last gate box binding mismatch')
                    gate_boxes.append(dict(incident_id=card['incident_id'],bbox=box['bbox'],
                        actual_pts=saved['pts'],frame_index=saved['frame_index'],cache_index=box['cache_index']))
            original=cv2.resize(img,(width,height));panels=[original]
            gate_indices={r['cache_index'] for r in audit['portal_observation_refs']}
            for layer in ('exp48','exp49'):
                overlay=original.copy()
                cv2.polylines(overlay,[np.rint(np.array(region['polygon'])*[width,height]).astype(np.int32)],True,(220,200,70),1)
                for box in actual:
                    is_gate=box['cache_index'] in gate_indices
                    rect(overlay,box['bbox'],(60,220,60) if is_gate else (150,150,150),
                         ('GATE NOW ' if is_gate else 'NOW ')+str(box['cache_index']),2 if is_gate else 1)
                if layer=='exp49':
                    for box in gate_boxes:
                        if box['actual_pts']<at-1e-9:
                            rect(overlay,box['bbox'],(20,210,255),f"LAST GATE {box['actual_pts']:.3f}s",2)
                panels.append(overlay)
            routing=[r for r in result['source_outcome_routing'] if r['decision_time_pts']<=at+1e-9][-1:]
            cards=views['exp49']['cards']
            labels=[f'SOURCE {at:.6f}s | ORIGINAL / EXP48 / EXP49 | Green: current gate box; grey: other actual; yellow: LAST actual gate',
                'EXP48 '+(' | '.join(f"{c['automatic_status']} first={c['first_alert_pts']:.3f} confirm={c['first_confirmation_pts']}" for c in views['exp48']['cards']) or 'no incident'),
                'EXP49 '+(' | '.join(f"{c['automatic_status']} {c['observation_status']} first={c['first_alert_pts']:.3f} confirm={c['first_confirmation_pts']}" for c in cards) or 'no incident'),
                'GATE '+(' | '.join(f"last={c['last_gate_observation_pts']} closed={c['observation_closed_pts']} reason={c['observation_close_reason']}" for c in cards) or 'no incident'),
                'INDIVIDUAL evidence '+(' | '.join(f"confirmed={len(c['confirmed_event_ids'])} pending={len(c['unresolved_event_ids'])} released={len(c['released_event_ids'])}" for c in cards) or 'none'),
                'Latest SOURCE decision '+(' | '.join(f"{r['decision_time_pts']:.6f}s {r['reason']}" for r in routing) or 'none'),
                'Observation closure is NOT suspicion release. Frozen evidence unchanged. No identity/normality/entry ground truth. Local pixels only.']
            canvas=np.zeros((height+header,width*3,3),dtype=np.uint8)
            for j,panel in enumerate(panels): canvas[header:,j*width:(j+1)*width]=panel
            banner=Image.fromarray(canvas[:header,:,::-1]);draw=ImageDraw.Draw(banner)
            for j,label in enumerate(labels): draw.text((8,4+j*33),label,font=font,fill=(235,235,235))
            canvas[:header]=np.asarray(banner)[:,:,::-1]
            mapping=dict(frame_index=index,native_pts=row['native_pts'],time_base=row['time_base'],source_pts=at,
                **views,actual_boxes=actual,last_gate_boxes=gate_boxes,
                portal_observation_refs=audit['portal_observation_refs'],routing=routing)
            for spec,container,stream in handles:
                if not spec['start']-1e-9<=at<=spec['end']+1e-9: continue
                frame=av.VideoFrame.from_ndarray(canvas,format='bgr24')
                frame.pts=row['native_pts']-spec['first_native_pts'];frame.time_base=tb
                for packet in stream.encode(frame): container.mux(packet)
                spec['mapping'].append(dict(mapping,presentation_pts=float(frame.pts*tb)))
    finally:
        for _,container,stream in handles:
            for packet in stream.encode(): container.mux(packet)
            container.close()
    if decoded!=len(frames): raise ValueError('Incomplete original decode')
    for spec,_,_ in handles:
        validate_mapping(spec['mapping'])
        with av.open(spec['path']) as container: actual_pts=[float(f.pts*f.time_base) for f in container.decode(video=0)]
        expected=[r['presentation_pts'] for r in spec['mapping']]
        if len(actual_pts)!=len(expected) or any(abs(a-b)>1e-6 for a,b in zip(actual_pts,expected)):
            raise ValueError('Full decode presentation clock mismatch')
        spec.update(frames=len(expected),sha256=sha(spec['path']),all_frames_decoded=True)
    if protected!={p:sha(p) for p in protected}: raise ValueError('Media inputs changed')
    manifest=dict(experiment='EXP-0049',contract=CONTRACT,video_id=result['video_id'],videos=specs,
        source_frames_decoded=decoded,input_sha256=protected,elapsed_seconds=time.perf_counter()-begin,
        pixels_local_only=True,new_decisions=0,detector_calls=0,tracker_calls=0,flow_calls=0,vlm_calls=0,
        all_stored_actual_boxes_shown=True,human_verified=False,
        source_clock_validation='Every encoded frame fully decoded against native/source/presentation mapping')
    save(output/'manifest.json',manifest)
    save(output/'manifest-binding.json',dict(contract=CONTRACT,manifest_sha256=sha(output/'manifest.json'),
        video_sha256={s['path']:s['sha256'] for s in specs}))
    return dict(video_id=result['video_id'],videos=[s['path'] for s in specs],
                elapsed_seconds=manifest['elapsed_seconds'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('directory','paths','baseline','portal-result'): p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(json.dumps(execute(a.directory,a.paths,a.baseline,a.portal_result),indent=2))

if __name__=='__main__': main()
