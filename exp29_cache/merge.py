"""Byte-preserving original + extension merge and fresh continuous CPU replay."""
import json
from pathlib import Path
import time

from orchestration.exp29_cache_command import timing_rows
from sceneguard.replay_gap_tracking import load_cache, run as replay, sha256, write_json


def merge_and_replay(original, extension, output, replay_output, schedule):
    original, extension, output, replay_output = map(Path, (original, extension, output, replay_output))
    if any(p.exists() or p.is_symlink() or any(q.is_symlink() for q in p.parents)
           for p in (output, replay_output)):
        raise FileExistsError('Merge/replay outputs must be fresh non-symlink paths')
    old_meta, old_rows, _, old_hash = load_cache(original)
    new_meta, new_rows, _, new_hash = load_cache(extension)
    timing_rows(old_rows, 737280, 600)
    timing_rows(new_rows, 1044480, 1110)
    for label, rows in [('original', old_rows), ('extension', new_rows)]:
        actual = [{k: row[k] for k in ('pts', 'native_pts', 'time_base', 'source_size')} for row in rows]
        if actual != schedule[label]:
            raise ValueError('Exact CPU-preflight native frame schedule differs')
    keys = ('video_id', 'source_sha256', 'source_size', 'model', 'model_sha256', 'model_postprocess',
            'model_input', 'model_input_observed', 'seed', 'batch_size', 'precision', 'threads',
            'warmup_frames', 'sampling', 'config', 'torch', 'torchvision', 'av', 'numpy')
    if any(old_meta[k] != new_meta[k] for k in keys):
        raise ValueError('FCOS model/preprocessing/environment/camera contract differs')
    old_bytes = (original/'person_cache.jsonl').read_bytes()
    new_bytes = (extension/'person_cache.jsonl').read_bytes()
    if not old_bytes.endswith(b'\n') or not new_bytes.endswith(b'\n'):
        raise ValueError('Complete JSONL byte streams required')
    output.mkdir(parents=True, exist_ok=False)
    with (output/'person_cache.jsonl').open('xb') as stream:
        stream.write(old_bytes)
        stream.write(new_bytes)
    rows = old_rows + new_rows
    meta = {k: old_meta[k] for k in keys}
    meta.update(status='complete', experiment_id='EXP-0029', frames=1710,
                first_pts=rows[0]['pts'], last_pts=rows[-1]['pts'], requested_window=[48.0,105.0],
                person_cache={**old_meta['person_cache'], 'sha256': sha256(output/'person_cache.jsonl')},
                original_frames_reused=600, new_frames_inferred=1110, original_bytes_preserved=True,
                provenance=dict(original=dict(path=str(original),sha256=old_hash),
                                extension=dict(path=str(extension),sha256=new_hash)),
                completion='unknown', ground_truth_loaded=False, timing_comparable=False,
                tracking='Not merged; fresh replay from first frame is authoritative',
                processing_wall_scope='Segment timings stay in their original metadata; no combined inference FPS')
    write_json(output/'run.json', meta)
    _, merged, _, _ = load_cache(output)
    timing_rows(merged, 737280, 1710)
    if (output/'person_cache.jsonl').read_bytes() != old_bytes + new_bytes:
        raise ValueError('Merged cache is not exact original byte prefix plus extension bytes')
    begin = time.perf_counter()
    summaries = replay(output, replay_output, retain_seconds=3.0)
    # Preserve the entire old tracker history as the prefix: no reset at the join.
    for condition in ('strict', 'gap'):
        tracks = [json.loads(line) for line in (replay_output/condition/'frames.jsonl').read_text().splitlines()]
        if len(tracks) != 1710 or any(any(a[k] != b[k] for k in ('pts','native_pts','time_base'))
                                      for a,b in zip(merged,tracks)):
            raise ValueError('Fresh tracking output native continuity differs')
    for path, hashes in [(original,old_hash), (extension,new_hash)]:
        if sha256(path/'person_cache.jsonl') != hashes['cache'] or sha256(path/'run.json') != hashes['metadata']:
            raise ValueError('Input segment changed during merge/replay')
    return dict(merged_frames=1710, original_frames_reused=600, new_frames_inferred=1110,
                exact_original_byte_prefix=True, exact_native_continuity=True,
                join_native_pts=[old_rows[-1]['native_pts'],new_rows[0]['native_pts']],
                cache_sha256=sha256(output/'person_cache.jsonl'),
                metadata_sha256=sha256(output/'run.json'),
                replay_wall_seconds=time.perf_counter()-begin, replay=summaries)
