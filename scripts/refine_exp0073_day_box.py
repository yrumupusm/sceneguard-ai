"""One user-requested lower-edge adjustment; preserve the bound EXP73 preview."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'outputs/model-comparison/exp0073/box-repairs-v1/editor-package.json'


def main(output):
    from PIL import Image, ImageDraw
    package = json.loads(PACKAGE.read_text())
    frame = next(f for f in package['frames'] if f['review_id'] == 'R01')
    raw = Path(frame['image_path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == frame['image_sha256']
    old = frame['proposed_boxes'][0]['xyxy']
    new = copy.deepcopy(old)
    # User's displayed shoe bottom is near native y647. This manual boundary
    # remains a new coordinate proposal; no actor/model label is auto-approved.
    new[3] = 647.0
    assert new[:3] == old[:3] and new[1] < new[3] < old[3]
    output.mkdir(parents=True, exist_ok=False)
    for name, box in [('before', old), ('after', new)]:
        pic = Image.open(frame['image_path']).convert('RGB')
        ImageDraw.Draw(pic).rectangle(box, outline='#00ffff', width=4)
        pic.save(output/f'{name}.png')
    record = dict(experiment_id='EXP-0073', source_frame_id=frame['frame_id'],
        source_sha256=frame['source_sha256'], source_pts=frame['source_pts'],
        source_rgb_sha256=frame['source_rgb_sha256'], source_image_sha256=frame['image_sha256'],
        parent_package_sha256=hashlib.sha256(PACKAGE.read_bytes()).hexdigest(),
        user_request='청록색 박스 밑변이 신발쪽으로 조금만 더 올라가면 좋겠는데',
        before_xyxy=old, after_xyxy=new, changed_edges=['bottom'],
        coordinate_confirmed=False, training_release=False,
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        image_sha256={name:hashlib.sha256((output/f'{name}.png').read_bytes()).hexdigest()
                      for name in ('before','after')})
    (output/'revision.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
    (output/'index.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8">
<title>주간20초 박스 밑변 수정</title><style>body{max-width:1280px;margin:24px auto;padding:0 16px;font:18px sans-serif;background:#151515;color:#eee}img{width:100%;height:auto}summary{cursor:pointer;padding:12px}</style>
<h1>주간20초 · 박스 밑변 수정</h1><p>밑변을 신발 바로 아래까지 올렸습니다. 위쪽과 양옆은 그대로입니다.</p>
<img src="after.png" alt="밑변만 올린 새 청록색 박스"><details><summary>이전 박스와 비교</summary><img src="before.png" alt="이전 박스"></details>
<p>새 좌표 수정안입니다. 모델 재학습이나 자동 정답 확정은 하지 않았습니다.</p>
<a style="color:#8df" href="http://127.0.0.1:8765/#video-review?experiment=EXP-0073">실험 검수 화면</a></html>''')
    print(json.dumps(dict(changed_edge='bottom',old_bottom=old[3],new_bottom=new[3],coordinate_confirmed=False)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    main(p.parse_args().output)
