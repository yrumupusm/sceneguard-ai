"""Freeze full-screen RGB video samples and original PTS; no annotations in model input."""
import json,hashlib,datetime
from pathlib import Path
import av
import numpy as np
from PIL import Image,ImageDraw

ROOT=Path('outputs/vlm_exp0007')


def prepare():
    if (ROOT/'preregistered.json').exists():raise FileExistsError('Existing frozen experiment; use a new ROOT')
    manifest=json.loads(Path('configs/vlm_exp0007_manifest.json').read_text())
    frozen={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in ['configs/vlm_exp0007_manifest.json','configs/vlm_exp0007_prompt.txt','docs/decisions/ADR-0012-local-vlm-clip-analysis.md']}
    (ROOT/'preregistered.json').write_text(json.dumps(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),hashes=frozen),indent=2))
    for clip in manifest['clips']:
        folder=ROOT/clip['id'];folder.mkdir(exist_ok=False)
        src=Path('data/TS_침입')/(clip['source']+'.mp4')
        selected=[];native=[];k=0
        with av.open(str(src)) as inp:
            stream=inp.streams.video[0];fps=float(stream.average_rate)
            inp.seek(int(max(0,clip['start']-1)/stream.time_base),stream=stream)
            for frame in inp.decode(video=0):
                pts=float(frame.pts*frame.time_base)
                if pts>=clip['end']:break
                if pts+1e-9 < clip['start']+k*.5:continue
                selected.append(frame.to_ndarray(format='rgb24'))
                native.append(dict(pts=pts,native_pts=frame.pts,time_base=str(frame.time_base),target=clip['start']+k*.5))
                k+=1
                if k==10:break
        assert k==10 and len({r['native_pts'] for r in native})==10
        array=np.stack(selected);np.save(folder/'rgb.npy',array)
        metadata=dict(clip_id=clip['id'],source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),fps=fps,source_shape=list(array.shape),frames=native,relative_indices=[round((r['pts']-native[0]['pts'])*fps) for r in native])
        (folder/'input.json').write_text(json.dumps(metadata,indent=2))
        sheet=Image.new('RGB',(1280,5*390))
        for i,a in enumerate(array):
            tile=Image.fromarray(a).resize((640,360));x=(i%2)*640;y=(i//2)*390
            sheet.paste(tile,(x,y+30));ImageDraw.Draw(sheet).text((x+5,y+8),f"{clip['id']} ORIGINAL PTS {native[i]['pts']:.6f}",fill='white')
        sheet.save(folder/'review_input.jpg',quality=95)
        print(clip['id'],array.shape,flush=True)


if __name__=='__main__':prepare()
