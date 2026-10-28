"""Audit anonymous inputs, source pixels, timestamps and fixed VLM run conditions."""
import argparse,hashlib,json,re
from pathlib import Path
import av
import numpy as np

ROOT=Path('outputs/vlm_exp0007')


def audit(run):
    manifest=json.loads(Path('configs/vlm_exp0007_manifest.json').read_text())
    out=[]
    for clip in manifest['clips']:
        c=clip['id'];folder=ROOT/c
        meta=json.loads((folder/'input.json').read_text());rgb=np.load(folder/'rgb.npy')
        pts=[r['pts'] for r in meta['frames']]
        assert len(pts)==10 and all(a<b for a,b in zip(pts,pts[1:]))
        assert all(0<=r['pts']-r['target']<1/meta['fps']+1e-6 for r in meta['frames'])
        assert len({hashlib.sha256(a.tobytes()).hexdigest() for a in rgb})==10
        expected={r['native_pts']:i for i,r in enumerate(meta['frames'])};seen=[]
        with av.open(f"data/TS_침입/{clip['source']}.mp4") as inp:
            inp.seek(int((clip['start']-1)/inp.streams.video[0].time_base),stream=inp.streams.video[0])
            for f in inp.decode(video=0):
                if float(f.pts*f.time_base)>=clip['end']:break
                if f.pts in expected:
                    assert np.array_equal(f.to_ndarray(format='rgb24'),rgb[expected[f.pts]])
                    seen.append(f.pts)
        assert seen==[r['native_pts'] for r in meta['frames']]
        result=json.loads((ROOT/run/c/'result.json').read_text())
        text=(ROOT/run/c/'expanded_prompt.txt').read_text()
        assert all(s not in text for s in ['E01_','침입','EXP-','track_id','candidate_pts'])
        assert text.count('<|im_start|>user')==1 and '<|im_start|>assistant' in text
        assert result['source_pts']==pts and result['resize_calls']==1
        assert result['video_grid_thw']==[[5,28,48]] and result['visual_tokens']==1680
        assert result['resized_shape']==[10,3,448,768]
        assert not result['extra_sampling'] and result['temporal_padding_frames']==0
        actual=np.load(ROOT/run/c/'processor_resized_rgb.npy')
        assert len(actual)==10 and len({hashlib.sha256(a.tobytes()).hexdigest() for a in actual})==10
        timestamps=re.findall(r'<([0-9.]+) seconds>',text)
        assert len(timestamps)==5
        out.append(dict(clip_id=c,pts=pts,intervals=np.diff(pts).tolist(),model_timestamps_seconds=timestamps,
                        original_pixels_exact=True,source_duplicates=0,resized_duplicates=0,source_metadata_not_in_prompt=True))
    (ROOT/'input_audit.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',default='run02');audit(p.parse_args().run)
