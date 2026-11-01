"""Display-only grouped review of saved EXP47 ambiguous handoffs; pixels local."""
from fractions import Fraction
from pathlib import Path
import json

from .exp0044_application import save, sha
from .exp0044_media import frame_clock


def execute():
    import av
    import cv2
    import numpy as np
    from .run_tracklet_linking import decode_native

    directory=Path('outputs/exp0047/007-v2');portal=Path('outputs/exp0046/007-v1')
    result=json.loads((directory/'lifecycle-cards.json').read_text())
    runs=json.loads((portal/'observation-runs.json').read_text())
    baseline_path=Path('outputs/exp0035/007-v1.json')
    baseline=json.loads(baseline_path.read_text());source=Path(baseline['source_paths']['video'])
    evidence=Path('outputs/exp0042/007-v1/frame-evidence.jsonl')
    frames=[json.loads(s) for s in evidence.read_text().splitlines() if s.strip()]
    selections=[r for r in result['resolutions'] if r['kind']=='observation_handoff'
                and (r['observation_key'],r['next_observation_key']) in
                [('observation-00034','observation-00038'),('observation-00041','observation-00038'),
                 ('observation-00050','observation-00048')]]
    specs=[dict(resolution=r,start=r['decision_time_pts']-.7,end=r['decision_time_pts']+.7,
                title=r['observation_key']+' -> '+r['next_observation_key']) for r in selections]
    final=next(r for r in result['resolutions'] if r['kind']=='inward_loss')
    specs.append(dict(resolution=final,start=final['decision_time_pts']-.6,
                      end=final['decision_time_pts']+.8,title='final inward-loss: TWO cards / identity UNKNOWN'))
    inputs=[source,evidence,baseline_path,directory/'lifecycle-cards.json',portal/'observation-runs.json',Path(__file__)]
    protected={str(p):sha(p) for p in inputs};output=directory/'supplemental-media';output.mkdir(exist_ok=False)
    path=output/'new-handoff-links.mp4';tb=Fraction(frames[0]['time_base']);step=frames[1]['native_pts']-frames[0]['native_pts']
    rate=1/(frame_clock(frames[1])-frame_clock(frames[0]))
    container=av.open(str(path),'w');stream=container.add_stream('libx264',rate=rate)
    stream.width=1920;stream.height=660;stream.pix_fmt='yuv420p';stream.time_base=tb;stream.codec_context.time_base=tb
    stream.options={'crf':'21','preset':'fast','threads':'2'}
    mapping=[]
    try:
        for index,image in decode_native(source,frames):
            row=frames[index];at=row['pts'];chosen=[(i,s) for i,s in enumerate(specs) if s['start']-1e-9<=at<=s['end']+1e-9]
            if not chosen:continue
            chapter,spec=chosen[0];resolution=spec['resolution'];overlay=cv2.resize(image,(960,540));original=overlay.copy()
            focus=[]
            if resolution['kind']=='observation_handoff':
                match=resolution['evidence']['matches'][0]
                pairs=[(resolution['observation_key'],match['source_frame'],'SOURCE LAST',(40,180,255)),
                       (resolution['next_observation_key'],index,'TARGET actual',(80,230,80))]
            else:pairs=[(resolution['observation_key'],index,'LAST actual',(40,180,255))]
            for key,limit,label,color in pairs:
                visible=[r for r in runs[key] if r['frame_index']<=min(limit,index)]
                if not visible:continue
                last=visible[-1];b=np.rint(np.array(last['bbox'])*[960,540,960,540]).astype(int)
                cv2.rectangle(overlay,tuple(b[:2]),tuple(b[2:]),color,3)
                cv2.putText(overlay,label+f" {last['pts']:.3f}",(max(0,b[0]),max(16,b[1]-7)),0,.55,color,2)
                focus.append(dict(run_id=key,label=label,last=last))
            canvas=np.zeros((660,1920,3),dtype=np.uint8);canvas[120:,:960]=original;canvas[120:,960:]=overlay
            lines=[f"NEW LINK REVIEW {chapter+1}/4 | source {at:.6f}s | {spec['title']}",
                f"Saved rule handoff/confirmation at {resolution['decision_time_pts']:.6f}s (not human identity verification)",
                'Original left / SOURCE last orange and TARGET actual green right. Review only association; prior scene labels reused.']
            for i,line in enumerate(lines):cv2.putText(canvas,line,(10,27+i*34),0,.63,(240,240,240),1)
            frame=av.VideoFrame.from_ndarray(canvas,format='bgr24');frame.pts=len(mapping)*step;frame.time_base=tb
            for packet in stream.encode(frame):container.mux(packet)
            mapping.append(dict(chapter=chapter+1,frame_index=index,native_pts=row['native_pts'],time_base=row['time_base'],
                source_pts=at,presentation_pts=float(frame.pts*tb),resolution_id=resolution['resolution_id'],
                decision_visible=at>=resolution['decision_time_pts'],focus=focus))
    finally:
        for packet in stream.encode():container.mux(packet)
        container.close()
    with av.open(str(path)) as c:actual=[float(f.pts*f.time_base) for f in c.decode(video=0)]
    assert len(actual)==len(mapping)
    assert all(abs(a-r['presentation_pts'])<1e-6 for a,r in zip(actual,mapping))
    assert all(f['last']['pts']<=r['source_pts']+1e-9 for r in mapping for f in r['focus'])
    assert protected=={p:sha(p) for p in protected}
    manifest=dict(experiment='EXP-0047',video_id='E01_007',pixels_local_only=True,display_only=True,
        actual_loss_classifications=0,input_sha256=protected,videos=[dict(name='new-handoff-links',path=str(path),
        kind='new_ambiguity',frames=len(mapping),sha256=sha(path),mapping=mapping)],
        note='Four chronological chapters; presentation removes gaps while each frame retains exact source PTS. Static chapter description is a review question, not causal status.')
    save(output/'manifest.json',manifest);print(str(path))


if __name__=='__main__':execute()
