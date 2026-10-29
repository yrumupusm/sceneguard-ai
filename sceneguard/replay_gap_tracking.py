"""Compare strict vs gap-tolerant tracking on preserved pretrained FCOS caches.

CPU replay only. No checkpoint loading, learning, detector inference or ReID.
Old cache, tracker code, boundary code and experiment results stay unchanged.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import time

from .boundary import ObservedBoundary
from .gap_boundary import GapTolerantBoundary

STAGE = 'model_return_after_internal_filters_nms_global_cap_before_project_score'
FCOS_SHA = '99b0c9b7cfb1527d782db86b91d207f00547c792fb4103fc612b651d0a07b9e7'
POSTPROCESS = dict(score_thresh=.2, topk_candidates=1000, nms_thresh=.6, detections_per_img=100)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def load_cache(directory):
    directory = Path(directory)
    meta_path, cache_path = directory / 'run.json', directory / 'person_cache.jsonl'
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    cache_hash = sha256(cache_path)
    if (meta.get('status') != 'complete' or meta.get('model_sha256') != FCOS_SHA
            or meta.get('model_postprocess') != POSTPROCESS
            or meta['person_cache'].get('schema') != 1
            or meta['person_cache'].get('stage') != STAGE
            or meta['person_cache'].get('sha256') != cache_hash):
        raise ValueError('Expected intact historical pretrained FCOS person cache')
    frames = [json.loads(line) for line in cache_path.read_text(encoding='utf-8').splitlines()]
    if len(frames) != meta['frames'] or len(frames) < 2:
        raise ValueError('Cache frame count mismatch or insufficient frames')
    times = []
    size = frames[0]['source_size']
    if len(size) != 2 or any(type(x) is not int or x <= 0 for x in size):
        raise ValueError('Positive integer source dimensions required')
    for frame in frames:
        pts = frame['pts']
        if not math.isfinite(pts) or (times and pts <= times[-1]):
            raise ValueError('Strictly increasing finite timestamps required')
        times.append(pts)
        if frame['source_size'] != size or len(frame['boxes']) != len(frame['scores']):
            raise ValueError('Changing source size or mismatched cache arrays')
        for box, score in zip(frame['boxes'], frame['scores']):
            if (len(box) != 4 or not all(math.isfinite(x) for x in [*box, score])
                    or not 0 <= score <= 1):
                raise ValueError('Invalid cached box or score')
        # These fields are copied to output, never replaced by display FPS.
        if 'native_pts' not in frame or 'time_base' not in frame:
            raise ValueError('Native timing metadata required')
    intervals = [b - a for a, b in zip(times, times[1:])]
    interval = statistics.median(intervals)
    if not 1/31 <= interval <= 1/29 or any(abs(x - interval) > 1e-6 for x in intervals):
        raise ValueError('Existing near-30Hz, unsampled cache required')
    return meta, frames, interval, {'cache': cache_hash, 'metadata': sha256(meta_path)}


def make_adapter(retain_seconds, interval):
    # Lazy import keeps --help and pure state tests free of tracker dependencies.
    from .byte_adapter import ByteAdapter
    adapter = ByteAdapter(use_low=True)
    if retain_seconds is not None:
        count = max(1, math.ceil(retain_seconds / interval - 1e-9))
        adapter.tracker.args.track_buffer = count
        adapter.tracker.buffer_size = count
        adapter.tracker.max_time_lost = count
    return adapter


def write_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def run(cache_directory, output_directory, retain_seconds=3.0, adapter_factory=None):
    if not math.isfinite(retain_seconds) or retain_seconds <= 0:
        raise ValueError('retain_seconds must be finite and positive')
    output = Path(output_directory)
    # Reject symlink output roots and preexisting results rather than overwriting.
    if output.exists() or output.is_symlink() or any(p.is_symlink() for p in output.parents):
        raise FileExistsError('Output must be a new, non-symlink directory')
    meta, frames, interval, input_hashes = load_cache(cache_directory)
    factory = adapter_factory or make_adapter
    output.mkdir(parents=True, exist_ok=False)
    summaries = []
    try:
        for condition in ('strict', 'gap'):
            # Sequential construction: upstream ByteTrack resets a global ID counter.
            adapter = factory(None if condition == 'strict' else retain_seconds, interval)
            config = dict(meta['config'])
            if condition == 'strict':
                boundary = ObservedBoundary(config)
            else:
                config.update(dwell_seconds=.2, cooldown_seconds=2.0)
                boundary = GapTolerantBoundary(config, retain_seconds, min_observations=3)
            folder = output / condition
            folder.mkdir()
            events, gaps, last_seen, ids = [], [], {}, set()
            count, observations, costs = 0, 0, []
            with (folder / 'frames.jsonl').open('x', encoding='utf-8') as sink:
                for frame in frames:
                    start = time.perf_counter()
                    obs, states, unmatched = adapter.step(frame)
                    emitted = boundary.step(frame['pts'], obs)
                    costs.append(time.perf_counter() - start)
                    for row in obs:
                        tid = row['track_id']
                        ids.add(tid)
                        if tid in last_seen and frame['pts'] - last_seen[tid] > interval + 1e-6:
                            gaps.append(dict(track_id=tid, before=last_seen[tid], after=frame['pts'],
                                             seconds=frame['pts'] - last_seen[tid]))
                        last_seen[tid] = frame['pts']
                    count += bool(obs)
                    observations += len(obs)
                    record = {k: frame[k] for k in ('pts', 'native_pts', 'time_base')}
                    record.update(detections=obs, states=states, unmatched=unmatched)
                    sink.write(json.dumps(record, allow_nan=False) + '\n')
                    events.extend(event | dict(video_id=meta['video_id'], condition=condition)
                                  for event in emitted)
            for name, records in (('events', events), ('reobservations', gaps)):
                with (folder / (name + '.jsonl')).open('x', encoding='utf-8') as sink:
                    for record in records:
                        sink.write(json.dumps(record, allow_nan=False) + '\n')
            summary = dict(condition=condition, frames=len(frames), observed_boxes=observations,
                           frames_with_observations=count, observed_ids=len(ids),
                           reobservations_after_gap=len(gaps), candidates=len(events),
                           bridged_gap_candidates=sum(e.get('bridged_observation_gap', False) for e in events),
                           tracker_buffer_frames=adapter.tracker.max_time_lost,
                           boundary_retain_seconds=retain_seconds if condition == 'gap' else 0,
                           config=config, boundary_stats=boundary.stats,
                           native_frame_interval=interval, input_sha256=input_hashes,
                           replay_seconds=sum(costs), timing_scope='CPU tracking/rules only; not inference FPS',
                           identity_verified=False, cctv_accuracy=None, uses_finetuned_model=False,
                           uses_reid=False, note='Counts are diagnostics, not correct persons or crossings')
            write_json(folder / 'summary.json', summary)
            summaries.append(summary)
        if (sha256(Path(cache_directory) / 'person_cache.jsonl') != input_hashes['cache']
                or sha256(Path(cache_directory) / 'run.json') != input_hashes['metadata']):
            raise ValueError('Historical input changed during replay')
        write_json(output / 'summary.json', dict(status='complete', comparisons=summaries,
                    actual_video_review='pending', source_model='pretrained FCOS COCO_V1',
                    settings_scope='Practical package: buffer + retained state + dwell/cooldown; not one-axis attribution'))
    except Exception as exc:
        write_json(output / 'failure.json', dict(status='failed', error_type=type(exc).__name__, error=str(exc)))
        raise
    return summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('clips', nargs='+', choices=['030', '006', '007', '031'])
    parser.add_argument('--cache-root', type=Path, default=Path('outputs/cv_phase2d'))
    parser.add_argument('--output-root', type=Path, default=Path('outputs/exp0028/practical-v1'))
    parser.add_argument('--retain-seconds', type=float, default=3.0)
    args = parser.parse_args()
    if not args.output_root.resolve().is_relative_to(Path('outputs').resolve()):
        parser.error('Keep raw tracking results under the Git-ignored outputs/ directory')
    for clip in args.clips:
        result = run(args.cache_root / ('cache' + clip), args.output_root / ('track' + clip), args.retain_seconds)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    main()
