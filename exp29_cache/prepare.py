"""CPU-only native timing/environment preflight; never loads a detector."""
import json

from orchestration.exp29_cache_command import (ROOT, LOCAL, CACHE, VIDEO, VIDEO_SHA,
    WEIGHT, WEIGHT_SHA, OLD_FILES, checked, timing_rows, environment, sources, input_contract)
from orchestration.mock_job import atomic_json
from orchestration.queue import digest


def prepare():
    import av
    for name, sha in OLD_FILES.items():
        checked(CACHE/name, sha)
    checked(VIDEO, VIDEO_SHA)
    checked(WEIGHT, WEIGHT_SHA)
    meta = json.loads((CACHE/'run.json').read_text())
    original = [json.loads(line) for line in (CACHE/'person_cache.jsonl').read_text().splitlines()]
    schedule = dict(original=[], extension=[])
    with av.open(str(VIDEO)) as container:
        stream = container.streams.video[0]
        stream.thread_count = 2
        for frame in container.decode(stream):
            if frame.pts is None:
                raise ValueError('Native PTS required on every decoded frame')
            pts = float(frame.pts*frame.time_base)
            if pts >= 105:
                break
            if pts < 48:
                continue
            row = dict(pts=pts, native_pts=frame.pts, time_base=str(frame.time_base),
                       source_size=[frame.width, frame.height])
            schedule['original' if pts < 68 else 'extension'].append(row)
    timing_rows(schedule['original'], 737280, 600)
    timing_rows(schedule['extension'], 1044480, 1110)
    if schedule['original'] != [{k: row[k] for k in schedule['original'][0]} for row in original]:
        raise ValueError('Preserved 600 cache rows do not match exact original source decode')
    LOCAL.mkdir(parents=True, exist_ok=True)
    atomic_json(LOCAL/'cache007-config.local.json', meta['config'])
    atomic_json(LOCAL/'cache007-native-schedule.local.json', schedule)
    atomic_json(LOCAL/'cache007-environment.local.json', environment())
    contract = input_contract()
    import subprocess
    freeze = dict(status='cpu_preflight_passed_gpu_not_started', code_sha=subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), sources=sources(),
        inputs=contract, input_contract_sha256=digest(contract), original_frames=600,
        extension_frames=1110, merged_frames=1710, native_step=512, time_base='1/15360',
        original_last_native_pts=schedule['original'][-1]['native_pts'],
        extension_first_native_pts=schedule['extension'][0]['native_pts'],
        extension_last_native_pts=schedule['extension'][-1]['native_pts'],
        no_ground_truth_loaded=True, new_weights=0, training=0)
    atomic_json(LOCAL/'cache007-source-freeze.local.json', freeze)
    print(json.dumps({k:v for k,v in freeze.items() if k not in ('sources','inputs')}))
    return freeze


if __name__ == '__main__':
    prepare()
