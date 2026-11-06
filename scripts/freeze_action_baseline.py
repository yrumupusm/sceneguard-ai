"""Freeze the EXP-0062 *after* baseline without running or modifying it."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


CANDIDATE = "3927ce310da74aa8d6d3eb69e488c2ba35d625cee81b2589648205dbcde1d823"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def freeze(root, output):
    root, output = root.resolve(), output.resolve()
    if output.exists():
        raise ValueError('Output already exists; use a fresh attempt directory')
    output.mkdir(parents=True)
    base = root / 'outputs/validation/false-confirmation-guard-all45-v1/run-001'
    source = read(base / 'after/source-manifest.json')
    if source['manifest_sha256'] != CANDIDATE:
        raise ValueError('Wrong candidate: EXP-0062 after / EXP-0061 is required')
    expected = {}
    def merge(values):
        for path, digest in values.items():
            if path in expected and expected[path] != digest:
                raise ValueError('Conflicting historical binding: ' + path)
            expected[path] = digest
    merge(source['source_sha256'])
    merge(source['snapshot_sha256'])
    merge(read(base / 'evaluation-manifest.json')['output_hashes'])
    merge(read(base / 'evaluation-manifest.json')['evaluation_scripts'])
    videos, cache_records = [], []
    for i in range(1, 46):
        manifest = read(base / f'input-manifest-{i:03d}.json')
        merge(manifest['protected_sources'])
        merge(manifest['replay_inputs'])
        analysis_paths = [Path(p) for p in manifest['protected_sources']
                          if p.endswith('/source/analysis/analysis.json')]
        if len(analysis_paths) != 1:
            raise ValueError('Ambiguous measurement source: ' + manifest['video_id'])
        measurement = analysis_paths[0].parents[2]
        analysis = read(measurement / 'source/analysis/analysis.json')
        cache = Path(analysis['source_paths']['cache'])
        metadata = read(cache / 'run.json')
        bindings = read(measurement / 'source/tracking/stage.json')['binding']['cache_sha256']
        merge({str(cache / 'run.json'): bindings['metadata'],
               str(cache / 'person_cache.jsonl'): bindings['cache']})
        request = read(measurement / 'request.json')
        video = Path(request['video'])
        merge({str(video): request['input_sha256'][str(video)]})
        cache_records.append({'video_id': manifest['video_id'], 'metadata_path': str(cache / 'run.json'),
                              'model': metadata['model'], 'model_sha256': metadata['model_sha256'],
                              'torch': metadata.get('torch'), 'torchvision': metadata.get('torchvision'),
                              'detector_code_sha': metadata.get('code_sha'),
                              'model_input': metadata.get('model_input'),
                              'model_postprocess': metadata.get('model_postprocess')})
        videos.append({'video_id': manifest['video_id'], 'path': str(video),
                       'sha256': request['input_sha256'][str(video)],
                       'usage': 'regression_only_never_training_validation_or_threshold_selection',
                       'after': str(base / 'after' / manifest['video_id']),
                       'input_manifest': str(base / f'input-manifest-{i:03d}.json')})
        for path in [measurement / 'request.json', measurement / 'source/request.json',
                     measurement / 'source/tracking/stage.json', measurement / 'source/tracking/summary.json']:
            merge({str(path): sha(path)})
    model_hashes = {v['model_sha256'] for v in cache_records}
    if len(model_hashes) != 1:
        raise ValueError('Mixed detector weights must be investigated')
    weight = root / 'weights/fcos_resnet50_fpn_coco-99b0c9b7.pth'
    merge({str(weight): next(iter(model_hashes))})
    for path in base.glob('*.json'):
        merge({str(path): sha(path)})
    for path in (base / 'after').rglob('*.json'):
        merge({str(path): sha(path)})
    for path in (base / 'final-reports').rglob('*.json'):
        merge({str(path): sha(path)})
    errors, verified = [], {}
    for path, digest in sorted(expected.items()):
        try:
            actual = sha(path)
            if actual != digest:
                errors.append({'path': path, 'expected': digest, 'actual': actual})
            else:
                verified[path] = actual
        except OSError as exc:
            errors.append({'path': path, 'error': str(exc)})
    if not errors:
        shutil.copytree(base / 'after/code_snapshot', output / 'code_snapshot',
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        shutil.copy2(base / 'after/candidate-sha256.json', output / 'candidate-sha256.json')
    production = {str(p.relative_to(root)): sha(p) for p in (root / 'sceneguard').rglob('*.py')}
    result = {'experiment_id': 'EXP-0063', 'baseline_experiment': 'EXP-0062',
              'baseline_layer': 'after_including_EXP0061_guard', 'candidate_manifest_sha256': CANDIDATE,
              'status': 'verified' if not errors else 'binding_failed',
              'repository_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
              'verified_paths': verified, 'errors': errors, 'regression_only_videos': videos,
              'detector_provenance': cache_records, 'production_code_sha256': production,
              'new_inference': 0, 'training': 0,
              'evaluation': {'time_known_official_events': 52, 'unresolved_006_reference': 1,
                             '008_review_hold_preserved': True, 'overall_precision': None,
                             'baseline_confirmed_events': 37,
                             'note': 'Official matching is not verified action or intrusion-completion truth.'}}
    (output / 'baseline-lock.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'verified_files': len(verified), 'errors': errors,
                      'regression_videos': len(videos), 'manifest': str(output / 'baseline-lock.json')}, ensure_ascii=False))
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    existed_before = args.output.exists()
    try:
        freeze(args.root, args.output)
    except Exception as exc:
        if not existed_before and args.output.exists():
            failure = args.output / 'preparation-error.json'
            if not failure.exists():
                failure.write_text(json.dumps({'error': repr(exc), 'training': 0}) + '\n')
        raise
