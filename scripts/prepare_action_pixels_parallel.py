"""CPU-only, byte-equivalent preparation using the frozen action trainer decoder.

Never imports torch or launches the GPU queue. A benchmark is separate from a full
prepared artifact and performs the same complete input gates before decoding.
"""
import argparse
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
import importlib.util
import json
import multiprocessing
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
TRAINER_PATH = ROOT / 'scripts/train_action_recognizer.py'
TRAINER_SHA = '2a0d01de3ec9b872c99761472b0626ba1e5f41a5b9f2c9be4eef4fe5626ff350'
SPLIT_SHA = 'bfb0f9fcd570794036cc6d2eaad46f988679b612996e21282a34821203ad5499'


def trainer():
    spec = importlib.util.spec_from_file_location('frozen_action_pixel_decoder', TRAINER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.sha(TRAINER_PATH) != TRAINER_SHA:
        raise ValueError('Frozen trainer bytes differ')
    return module


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def verify_contract(args):
    module = trainer()
    paths = {name: getattr(args, name).resolve() for name in
             ('manifest', 'baseline_lock', 'split_manifest', 'config', 'review_release')}
    hashes = {name: module.sha(path) for name, path in paths.items()}
    manifest, baseline, split, settings = [json.loads(paths[name].read_text()) for name in
                                          ('manifest', 'baseline_lock', 'split_manifest', 'config')]
    module.validate_config(settings)
    if hashes['split_manifest'] != SPLIT_SHA:
        raise ValueError('Frozen combined split v3 required')
    if (len(baseline.get('regression_only_videos', [])) != 45 or
            len({r['sha256'] for r in baseline['regression_only_videos']}) != 45):
        raise ValueError('All45 regression source hashes are required')
    for key, name in [('config_sha256', 'config'), ('baseline_lock_sha256', 'baseline_lock'),
                      ('source_split_sha256', 'split_manifest')]:
        if manifest.get(key) != hashes[name]:
            raise ValueError('Manifest input binding differs: ' + name)
    release = module.validate_release(paths['manifest'], paths['split_manifest'], paths['review_release'],
                                      args.review_release_sha256)
    for name in ('review_snapshot', 'interpretation_policy'):
        paths[name] = Path(release[name]['path']).resolve()
        hashes[name] = release[name]['sha256']
    counts = module.validate_manifest(manifest, baseline, settings['frames'], split)
    snapshot = getattr(args, 'sequential_snapshot', None)
    snapshot_hash = getattr(args, 'sequential_snapshot_sha256', None)
    if bool(snapshot) != bool(snapshot_hash):
        raise ValueError('Sequential snapshot path and hash must be supplied together')
    if snapshot:
        paths['sequential_snapshot'] = snapshot.resolve()
        hashes['sequential_snapshot'] = module.sha(snapshot)
        saved = json.loads(snapshot.read_text())
        if (hashes['sequential_snapshot'] != snapshot_hash or
                saved.get('manifest_sha256') != hashes['manifest'] or not saved.get('clips') or
                not set(saved['clips']).issubset({r['clip_id'] for r in manifest['clips']})):
            raise ValueError('Sequential snapshot hash/manifest/clip binding differs')
    return manifest, settings, dict(paths={k: str(v) for k, v in paths.items()}, hashes=hashes,
                                    counts=counts, trainer_sha256=TRAINER_SHA,
                                    driver_sha256=module.sha(__file__))


def source_bindings(rows):
    bindings = {}
    for row in rows:
        for key, hash_key in [('source_path', 'source_sha256'), ('label_path', 'label_sha256')]:
            path, expected = row[key], row[hash_key]
            if path in bindings and bindings[path] != expected:
                raise ValueError('Contradictory source/annotation hashes: ' + path)
            bindings[path] = expected
    return sorted(bindings.items())


def _hash_source(binding):
    path, expected = binding
    actual = trainer().sha(path)
    if actual != expected:
        raise ValueError('Source/annotation changed: ' + path)
    return dict(path=path, sha256=actual)


def pool():
    return ProcessPoolExecutor(max_workers=4, mp_context=multiprocessing.get_context('spawn'))


def bounded_map(function, tasks):
    """At most four submitted/buffered tasks; observe any failure before replenishing."""
    workers = pool()
    pending, completed = {}, {}
    iterator = enumerate(tasks)
    next_result = 0
    exhausted = False
    try:
        while pending or not exhausted:
            while not exhausted and len(pending)+len(completed) < 4:
                try:
                    index, task = next(iterator)
                except StopIteration:
                    exhausted = True
                else:
                    pending[workers.submit(function, task)] = index
            if not pending:
                break
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            # Check every completed future for errors before yielding/submitting more work.
            values = [(future, future.result()) for future in done]
            for future, value in values:
                completed[pending.pop(future)] = value
            while next_result in completed:
                yield completed.pop(next_result)
                next_result += 1
    finally:
        for future in pending:
            future.cancel()
        workers.shutdown(wait=True, cancel_futures=True)


def verify_sources(rows):
    bindings = source_bindings(rows)
    results = []
    for index, result in enumerate(bounded_map(_hash_source, bindings), 1):
        results.append(result)
        if index % 100 == 0 or index == len(bindings):
            print(json.dumps(dict(phase='source_hash', completed=index, total=len(bindings))), flush=True)
    return results


def _decode_to_file(task):
    index, row, size, folder = task
    import numpy as np
    module = trainer()
    array = module.decode_clip(row, size)
    target = Path(folder) / f'clip-{index:06d}.npy'
    temporary = target.with_name(target.name + '.tmp')
    if target.exists():
        raise FileExistsError(str(target))
    with temporary.open('xb') as stream:
        np.save(stream, array, allow_pickle=False)
    os.replace(temporary, target)
    return row['clip_id'], dict(path=str(target.resolve()), sha256=module.sha(target),
                                shape=list(array.shape), dtype=str(array.dtype))


def decode_rows(rows, size, folder, parallel=True):
    tasks = [(i, row, size, str(Path(folder).resolve())) for i, row in enumerate(rows)]
    entries = {}
    if parallel:
        for index, (key, entry) in enumerate(bounded_map(_decode_to_file, tasks), 1):
            entries[key] = entry
            if index % 100 == 0 or index == len(rows):
                print(json.dumps(dict(phase='decode', completed=index, total=len(rows))), flush=True)
    else:
        entries = dict(_decode_to_file(task) for task in tasks)
    if len(entries) != len(rows):
        raise ValueError('Incomplete or duplicate prepared rows')
    return entries


def benchmark_plan(rows):
    """Predetermined examples covering every available class/split/cohort bucket and ROI extremes."""
    selected, buckets = {}, set()
    for index, row in enumerate(rows):
        bucket = (row['action_class'], row['split'], row['evaluation_cohort'])
        if bucket not in buckets:
            selected.setdefault(index, []).append('class_split_cohort:' + ':'.join(bucket))
            buckets.add(bucket)
    predicates = {
        'roi_touches_source_boundary': lambda r: r['roi_xyxy'][0] == 0 or r['roi_xyxy'][1] == 0 or
            r['roi_xyxy'][2] == r['source_width'] or r['roi_xyxy'][3] == r['source_height'],
        'wide_roi': lambda r: r['roi_xyxy'][2]-r['roi_xyxy'][0] > r['roi_xyxy'][3]-r['roi_xyxy'][1],
        'tall_roi': lambda r: r['roi_xyxy'][2]-r['roi_xyxy'][0] < r['roi_xyxy'][3]-r['roi_xyxy'][1],
    }
    for name, predicate in predicates.items():
        index = next((i for i, row in enumerate(rows) if predicate(row)), None)
        if index is not None:
            selected.setdefault(index, []).append(name)
    aspect = lambda i: ((rows[i]['roi_xyxy'][2]-rows[i]['roi_xyxy'][0]) /
                         (rows[i]['roi_xyxy'][3]-rows[i]['roi_xyxy'][1]))
    for name, operation in [('minimum_roi_aspect', min), ('maximum_roi_aspect', max)]:
        index = operation(range(len(rows)), key=aspect)
        selected.setdefault(index, []).append(name)
    return [dict(manifest_index=i, clip_id=rows[i]['clip_id'], reasons=selected[i],
                 action_class=rows[i]['action_class'], split=rows[i]['split'],
                 cohort=rows[i]['evaluation_cohort'], source_id=rows[i]['source_id'],
                 roi_xyxy=rows[i]['roi_xyxy']) for i in sorted(selected)]


def compare_entries(left, right):
    import numpy as np
    module = trainer()
    if set(left) != set(right):
        raise ValueError('Equivalence clip sets differ')
    for key in left:
        a, b = left[key], right[key]
        x = np.load(a['path'], allow_pickle=False)
        y = np.load(b['path'], allow_pickle=False)
        if (module.sha(a['path']) != a['sha256'] or module.sha(b['path']) != b['sha256'] or
                a['sha256'] != b['sha256'] or x.dtype != y.dtype or x.shape != y.shape or
                not np.array_equal(x, y)):
            raise ValueError('NPY byte/array/dtype/shape equivalence failed: ' + key)
    return dict(compared=len(left), npy_sha256_equal=True, arrays_equal=True,
                dtype_equal=True, shape_equal=True)


def verify_final_contract(contract):
    module = trainer()
    if module.sha(__file__) != contract['driver_sha256']:
        raise ValueError('Driver changed during processing')
    if module.sha(contract['_contract_path']) != contract['_contract_sha256']:
        raise ValueError('Preparation contract changed during processing')
    for name, path in contract['paths'].items():
        if module.sha(path) != contract['hashes'][name]:
            raise ValueError('Input contract changed during processing: ' + name)


def process_pixels(manifest, settings, contract, output, mode):
    """Caller has completed all gates; failed preparation never publishes prepared.json."""
    output = Path(output)
    if mode == 'benchmark':
        plan = benchmark_plan(manifest['clips'])
        rows = [manifest['clips'][entry['manifest_index']] for entry in plan]
        atomic_json(output/'benchmark-plan.json', plan)
        results, times = {}, {}
        for name, parallel in [('sequential', False), ('parallel', True)]:
            folder = output/name
            folder.mkdir()
            start = time.monotonic()
            results[name] = decode_rows(rows, settings['image_size'], folder, parallel)
            times[name] = time.monotonic()-start
        equivalent = compare_entries(results['sequential'], results['parallel'])
        result = dict(status='benchmark_passed', full_prepared=False, workers=4, clips=len(rows),
                      seconds=times, speedup=times['sequential']/times['parallel'],
                      equivalence=equivalent, entries=results)
        verify_final_contract(contract)
        atomic_json(output/'benchmark-result.json', result)
        return result
    entries = decode_rows(manifest['clips'], settings['image_size'], output)
    module = trainer()
    verify_final_contract(contract)
    if 'sequential_snapshot' in contract['paths']:
        saved = json.loads(Path(contract['paths']['sequential_snapshot']).read_text())['clips']
        equivalent = compare_entries(saved, {key: entries[key] for key in saved})
        atomic_json(output/'sequential-equivalence.json', equivalent)
    prepared = dict(manifest_sha256=contract['hashes']['manifest'],
                    config_sha256=contract['hashes']['config'], clips=entries,
                    preparation=dict(contract=dict(path=contract['_contract_path'],
                                     sha256=contract['_contract_sha256']),
                                     trainer_sha256=TRAINER_SHA, driver_sha256=contract['driver_sha256'],
                                     workers=4))
    atomic_json(output/'prepared.json', prepared)
    return dict(status='prepared', clips=len(entries), workers=4,
                prepared_sha256=module.sha(output/'prepared.json'))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('manifest', 'baseline-lock', 'split-manifest', 'config', 'review-release', 'output'):
        parser.add_argument('--'+flag, type=Path, required=True)
    parser.add_argument('--review-release-sha256', required=True)
    parser.add_argument('--mode', choices=['prepare', 'benchmark'], required=True)
    parser.add_argument('--workers', type=int, choices=[4], default=4)
    parser.add_argument('--sequential-snapshot', type=Path)
    parser.add_argument('--sequential-snapshot-sha256')
    args = parser.parse_args(argv)
    manifest, settings, contract = verify_contract(args)
    args.output.mkdir(parents=True, exist_ok=False)
    contract.update(argv=sys.argv if argv is None else argv, mode=args.mode, workers=4,
                    start_monotonic=time.monotonic(), expected_clips=len(manifest['clips']))
    atomic_json(args.output/'contract.json', contract)
    contract['_contract_path'] = str((args.output/'contract.json').resolve())
    contract['_contract_sha256'] = trainer().sha(args.output/'contract.json')
    try:
        sources = verify_sources(manifest['clips'])
        atomic_json(args.output/'verified-source-hashes.json', dict(status='passed', files=sources))
        result = process_pixels(manifest, settings, contract, args.output, args.mode)
        result['elapsed_seconds'] = time.monotonic()-contract['start_monotonic']
        atomic_json(args.output/'result.json', result)
        print(json.dumps({key: value for key, value in result.items() if key != 'entries'}), flush=True)
    except BaseException as error:
        atomic_json(args.output/'failure.json', dict(status='failed', type=type(error).__name__,
                    error=str(error), prepared_published=(args.output/'prepared.json').exists()))
        raise


if __name__ == '__main__':
    main()
