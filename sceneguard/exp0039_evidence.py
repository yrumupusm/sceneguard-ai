"""Render saved EXP-0039 correspondences without re-running optical flow.

Three panels retain the original frame, saved detector/tracker measurements,
and a fixed native crop with stable-ID LK paths. Predictions are outlined in
magenta and labelled PRED; image features are points, never person boxes.
"""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import time

from .exp0039_application import sha, write
from .gap_observation_support import catalog_frame


def extend_paths(paths, record, background=False, initial=False):
    prefix='background_' if background else ''
    ids=record[prefix+'point_ids']
    points=record[prefix+'points_original_pixels']
    if len(ids)!=len(points) or len(set(ids))!=len(ids):
        raise ValueError('Saved unique correspondence IDs required')
    # Only IDs present now can acquire another vertex; no interpolation/reseed.
    active={}
    for identity,point in zip(ids,points):
        if not initial and identity not in paths:
            raise ValueError('Feature reappeared after dropout')
        active[identity]=paths.get(identity,[])+[point]
    return active


def alarm_label(pts, decision_pts):
    return 'SUSPECTED' if pts >= decision_pts-1e-9 else 'PENDING (not yet emitted)'


def unchanged_proposal(baseline, original_cards, diagnostic):
    """Reproduce original grouping in a separate review copy, never cancel rows.

    The coordinator selected no suppression because zero actual cases qualified.
    Even overlap or surviving image features would not establish person identity.
    """
    from copy import deepcopy
    from .exp0036_application import make_bundle
    from .incident_cards import GroupPolicy
    scope=original_cards['events'][0]
    regenerated=make_bundle(baseline,scope['camera_id'],scope['gate_id'],scope['session_id'],
                            GroupPolicy(**original_cards['policy']))
    for field in ('events','cards','timeline','counts'):
        if regenerated[field]!=original_cards[field]:
            raise ValueError('Original card grouping could not be reproduced: '+field)
    if any(r['flow_support']['outcome']=='image_continuation_supported_review_only'
           for r in diagnostic['results']):
        raise ValueError('Supported cases require a separate coordinator review decision')
    by_pointer={r['source_pointer']:r for r in diagnostic['results']}
    decisions=[]
    for event in regenerated['events']:
        pointer=event['source_ref']['source_pointer'];case=by_pointer.get(pointer)
        decisions.append(dict(event_id=event['event_id'],source_ref=deepcopy(event['source_ref']),
            source_reason=event['source_event'].get('reason',event['source_event'].get('condition')),
            original_status=event['status'],proposed_status=event['status'],suppressed=False,
            decision_reason='no_supported_image_continuation' if case else 'original_gap_or_bilateral_preserved',
            flow_outcome=None if case is None else case['flow_support']['outcome']))
    return dict(experiment='EXP-0039',video_id=baseline['video_id'],
        baseline=deepcopy(original_cards),proposal=regenerated,row_decisions=decisions,
        counts=dict(original=original_cards['counts'],proposal=regenerated['counts'],suppressed=0,
                    diagnostic_losses=len(diagnostic['results']),judgment_deferred=len(diagnostic['results'])),
        identity_truth=False,false_alarm_reduction=None,wrongly_downgraded_suspicions=0,
        decision='coordinator_no_suppression_zero_supported_cases',automatic_adoption=False)


def write_proposal(baseline_path, cards_path, directory, output):
    import html
    baseline_path,cards_path,directory,output=map(Path,(baseline_path,cards_path,directory,output))
    page=output.with_suffix('.html')
    if output.exists() or page.exists():raise ValueError('Fresh proposal files required')
    proposal=unchanged_proposal(json.loads(baseline_path.read_text()),json.loads(cards_path.read_text()),
                               json.loads((directory/'summary.json').read_text()))
    proposal['provenance']=dict(baseline_path=str(baseline_path),baseline_sha256=sha(baseline_path),
        original_cards_path=str(cards_path),original_cards_sha256=sha(cards_path),
        diagnostic_sha256=sha(directory/'summary.json'),code_sha256=sha(__file__))
    write(output,proposal)
    rows=''.join('<tr>'+''.join('<td>'+html.escape(str(r[k]))+'</td>' for k in
        ('source_ref','source_reason','original_status','proposed_status','decision_reason','flow_outcome'))+'</tr>'
        for r in proposal['row_decisions'])
    page.write_text('<!doctype html><meta charset="utf-8"><title>EXP-0039 separate proposal</title>'
        '<h1>EXP-0039 별도 제안 보기 · 원래 알림 유지</h1><p>지원된 영상 연속성 0 · 알림 변경 0 · 새 동일인 정답 없음</p>'
        '<pre>'+html.escape(json.dumps(proposal['counts'],ensure_ascii=False,indent=2))+'</pre>'
        '<table border="1"><thead><tr><th>원래 행</th><th>원래 이유</th><th>원래 상태</th><th>제안 상태</th>'
        '<th>유지 이유</th><th>영상 근거</th></tr></thead><tbody>'+rows+'</tbody></table>',encoding='utf-8')
    return proposal


def render_original(source, cached, first, last, target):
    """Plain original pixels for human visibility review, with an exact PTS map."""
    import av
    from .run_tracklet_linking import decode_native
    target=Path(target)
    if target.exists():raise ValueError('Never overwrite evidence')
    selected=cached[first:last+1];mapping=[]
    with av.open(str(target),'w') as output:
        stream=output.add_stream('libx264',rate=30)
        stream.width,stream.height=selected[0]['source_size'];stream.pix_fmt='yuv420p'
        stream.time_base=Fraction(selected[0]['time_base']);stream.codec_context.time_base=stream.time_base
        stream.options={'crf':'18','preset':'fast'}
        for offset,bgr in decode_native(source,selected):
            source_row=selected[offset]
            frame=av.VideoFrame.from_ndarray(bgr,format='bgr24')
            frame.pts=source_row['native_pts']-selected[0]['native_pts'];frame.time_base=stream.time_base
            for packet in stream.encode(frame):output.mux(packet)
            mapping.append(dict(frame_index=first+offset,native_pts=source_row['native_pts'],
                time_base=source_row['time_base'],source_pts=source_row['pts'],
                presentation_pts=float(frame.pts*frame.time_base)))
        for packet in stream.encode():output.mux(packet)
    with av.open(str(target)) as result:
        stamps=[float(f.pts*f.time_base) for f in result.decode(video=0)]
    if len(stamps)!=len(mapping) or any(abs(t-r['presentation_pts'])>1e-6 for t,r in zip(stamps,mapping)):
        raise ValueError('Plain original clip PTS mismatch')
    return dict(path=str(target),sha256=sha(target),frames=len(mapping),pts_mapping=mapping,
        first_source_pts=selected[0]['pts'],last_source_pts=selected[-1]['pts'],
        plain_original_pixels=True,lossy_encode=True,visibility_truth='pending_human_review')


def render_segment(source, cached, tracked, support, target, width=640):
    import av
    import cv2
    import numpy as np
    from .run_tracklet_linking import decode_native
    target=Path(target)
    if target.exists():
        raise ValueError('Never overwrite existing evidence')
    records=support['flow_records'];audit=support['detector_audit']
    if not records:
        raise ValueError('No saved flow records to render')
    first,last=records[0]['frame_index'],records[-1]['frame_index']
    if last-first+1!=len(records) or records[-1]['pts']!=audit['decision_time_pts']:
        raise ValueError('Complete causal frame interval required')
    x1,y1,x2,y2=support['working_crop'];paths={};background={}
    height=360;header=128;begin=time.perf_counter();count=0
    with av.open(str(target),'w') as output:
        stream=output.add_stream('libx264',rate=30)
        stream.width=width*3;stream.height=height+header;stream.pix_fmt='yuv420p'
        stream.time_base=Fraction(records[0]['time_base'])
        stream.codec_context.time_base=stream.time_base
        stream.options={'crf':'20','preset':'fast'}
        for offset,bgr in decode_native(source,cached[first:last+1]):
            record=records[offset];index=first+offset
            if record['frame_index']!=index or record['native_pts']!=cached[index]['native_pts']:
                raise ValueError('Saved path/native frame mismatch')
            measured=bgr.copy();h,w=bgr.shape[:2]
            for c in catalog_frame(cached[index],tracked[index]):
                a,b,cx,d=c['bbox'];color=(0,230,0) if c['assignment']=='confirmed_track' else (0,180,255)
                cv2.rectangle(measured,(round(a*w),round(b*h)),(round(cx*w),round(d*h)),color,2)
                cv2.putText(measured,f"c{c['cache_index']} ID{c['track_ids']} {c['assignment']}",
                    (round(a*w),max(15,round(b*h)-3)),0,.42,color,1)
            predictions=0
            for state in tracked[index].get('states',[]):
                if state.get('observed') is False and state.get('prediction_bbox'):
                    a,b,c,d=state['prediction_bbox'];predictions+=1
                    cv2.rectangle(measured,(round(a*w),round(b*h)),(round(c*w),round(d*h)),(255,0,255),1)
                    cv2.putText(measured,f"PRED ID{state.get('track_id')}",(round(a*w),round(b*h)),0,.5,(255,0,255),1)
            paths=extend_paths(paths,record,initial=offset==0);background=extend_paths(background,record,True,initial=offset==0)
            crop=bgr[y1:y2,x1:x2].copy()
            for group,color in ((background,(255,190,0)),(paths,(0,0,255))):
                for identity,vertices in group.items():
                    points=np.asarray(vertices,dtype=float)-[x1,y1]
                    points=np.rint(points).astype(np.int32)
                    if len(points)>1:cv2.polylines(crop,[points],False,color,1)
                    cv2.circle(crop,tuple(points[-1]),2,color,-1)
                    if group is paths:cv2.putText(crop,str(identity),tuple(points[-1]),0,.3,color,1)
            canvas=np.zeros((height+header,width*3,3),dtype=np.uint8)
            for panel,image in enumerate((bgr,measured,crop)):
                scale=min(width/image.shape[1],height/image.shape[0])
                resized=cv2.resize(image,(round(image.shape[1]*scale),round(image.shape[0]*scale)))
                canvas[header:header+resized.shape[0],panel*width:panel*width+resized.shape[1]]=resized
            lines=[f"EXP39 {audit['segment']} raw{audit['raw_id']} | native PTS {record['native_pts']} * {record['time_base']} = {record['pts']:.6f}s",
                f"seed {records[0]['pts']:.6f} | last observed {audit['last_observed_pts']:.6f} | decision {audit['decision_time_pts']:.6f} | frame {index}",
                f"original/proposed alarm: {alarm_label(record['pts'],audit['decision_time_pts'])} (unchanged) | {support['flow_support']['outcome']}",
                f"ORIGINAL                         STORED: green measured / magenta PRED ({predictions})       LK CROP: red target / cyan background; points NOT people"]
            for n,line in enumerate(lines):cv2.putText(canvas,line,(10,23+28*n),0,.53,(230,230,230),1)
            frame=av.VideoFrame.from_ndarray(canvas,format='bgr24')
            # Native PTS remains in overlay and mapping; browser clips start at 0.
            frame.pts=record['native_pts']-records[0]['native_pts']
            frame.time_base=Fraction(record['time_base'])
            for packet in stream.encode(frame):output.mux(packet)
            count+=1
        for packet in stream.encode():output.mux(packet)
    # Decode the produced artifact; transport success is insufficient.
    with av.open(str(target)) as result:
        stamps=[float(f.pts*f.time_base) for f in result.decode(video=0)]
    expected=[float((r['native_pts']-records[0]['native_pts'])*Fraction(r['time_base'])) for r in records]
    if len(stamps)!=len(expected) or any(abs(a-b)>1e-6 for a,b in zip(stamps,expected)):
        raise ValueError('Encoded evidence PTS mismatch')
    mapping=[dict(frame_index=r['frame_index'],native_pts=r['native_pts'],time_base=r['time_base'],
                  source_pts=r['pts'],presentation_pts=pts) for r,pts in zip(records,stamps)]
    return dict(path=str(target),sha256=sha(target),frames=count,first_pts=stamps[0],last_pts=stamps[-1],
        source_first_pts=records[0]['pts'],source_last_pts=records[-1]['pts'],
        native_pts_overlay_and_mapping=True,pts_mapping=mapping,
        seconds=time.perf_counter()-begin,flow_recomputed=False,
        visual_semantics='Codex draft; no person identity ground truth or intrusion verdict')


def execute(directory, output_name='comparison'):
    from .exp0034_application import validated_inputs
    directory=Path(directory);summary=json.loads((directory/'summary.json').read_text())
    baseline=next(p for p in summary['input_sha256'] if p.endswith('-v1.json') and 'exp0035' in p)
    b=json.loads(Path(baseline).read_text())
    spec,data,_=validated_inputs(summary['video_id'][-3:],b['source_paths']['scene'],b['input_sha256']['scene'])
    for path,digest in summary['input_sha256'].items():
        if sha(path)!=digest:raise ValueError('Rendering input changed')
    if Path(output_name).name!=output_name:raise ValueError('Output directory name required')
    media=directory/output_name;media.mkdir(exist_ok=False)
    receipts=[]
    for case in summary['results']:
        support=json.loads((directory/(case['segment']+'-support.json')).read_text())
        receipts.append(render_segment(spec['video'],data['cached'],data['tracked'],support,media/(case['segment']+'.mp4')))
    write(media/'render-receipt.json',dict(videos=receipts,alarm_changes=0,new_identity_truth=False,
        render_code_sha256=sha(__file__),summary_sha256=sha(directory/'summary.json')))
    return receipts


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--output-name',default='comparison')
    parser.add_argument('--proposal-baseline',type=Path)
    parser.add_argument('--original-cards',type=Path)
    parser.add_argument('--proposal-output',type=Path)
    args=parser.parse_args()
    if any((args.proposal_baseline,args.original_cards,args.proposal_output)):
        if not all((args.proposal_baseline,args.original_cards,args.proposal_output)):
            parser.error('All three proposal arguments are required')
        result=write_proposal(args.proposal_baseline,args.original_cards,args.directory,args.proposal_output)
        print(json.dumps(result['counts'],indent=2))
    else:
        print(json.dumps(execute(args.directory,args.output_name),indent=2))
