"""Read saved EXP-0005 C records once in PTS order; no detector/tracker execution."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
from sceneguard.candidate_review import CandidateReview, CONFIG


def read(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(root):
    root.mkdir(parents=True,exist_ok=False)
    summary={}
    for clip in ['030','006','007','031']:
        source=Path(f'outputs/cv_phase2e/track{clip}/C')
        frames=read(source/'frames.jsonl'); events=read(source/'events.jsonl')
        before=deepcopy(frames); originals=deepcopy(events)
        on,off=CandidateReview(),CandidateReview(enabled=False)
        changes=[]; passthrough=[]
        for frame in frames:
            arriving=[e for e in events if e['emitted_at_pts']==frame['pts']]
            changes.extend(on.step(frame['pts'],frame['detections'],arriving))
            passthrough.extend(off.step(frame['pts'],frame['detections'],arriving))
        changes.extend(on.finish()); assert off.finish()==[]
        assert passthrough==originals and frames==before and events==originals
        final=[r for r in changes if r['status']!='pending']
        assert [r['original'] for r in final]==originals
        assert all(r['last_observation_pts'] is None or r['last_observation_pts']<=r['decision_pts'] for r in final)
        folder=root/clip;folder.mkdir()
        (folder/'original_events.jsonl').write_bytes((source/'events.jsonl').read_bytes())
        for name,values in [('updates',changes),('final',final),('disabled',passthrough)]:
            (folder/f'{name}.json').write_text(json.dumps(values,indent=2))
        summary[clip]=dict(frames=len(frames),candidates=len(events),statuses=[r['status'] for r in final],
                           frames_sha256=sha(source/'frames.jsonl'),events_sha256=sha(source/'events.jsonl'),disabled_exact=True)
    assert sum(v['frames'] for v in summary.values())==2060
    metadata=dict(config=CONFIG,summary=summary,head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                  code_sha256={p:sha(Path(p)) for p in ['sceneguard/candidate_review.py','scripts/compare_candidate_review.py']})
    (root/'summary.json').write_text(json.dumps(metadata,indent=2))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=Path('outputs/cv_phase2g/comparison'))
    run(p.parse_args().output)
