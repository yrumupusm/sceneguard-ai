"""Summarize the completed EXP-0026 output without loading a model or media.

The local plot describes training/validation losses against unreviewed labels.
It is not a CCTV accuracy graph. Public output contains aggregate values only.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path


def summarize(root, summary_path):
    root = root.resolve()
    path = summary_path.resolve()
    relative = path.relative_to(root).as_posix()
    if not relative.startswith('outputs/batch0007/EXP-0026/') or path.name != 'summary.json':
        raise ValueError('EXP-0026 local summary required')
    data = json.loads(path.read_text())
    if data['status'] != 'succeeded' or data['technical_pass'] is not True or data['epochs_completed'] != 20:
        raise ValueError('Completed twenty-epoch run required; preserve failures separately')
    if len(data['baseline']) != 7 or len(data['after']) != 7 or data['test17_used'] is not False:
        raise ValueError('Fixed diagnostic scope differs')
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    metrics = []

    def add(label, value, unit, count, scope):
        metrics.append(dict(label=label, value=value, unit=unit, sample_n=count,
                            scope=scope, source=relative, source_sha256=checksum,
                            verification='measured_local_output; semantic box review pending'))

    add('Completed training epochs', 20, 'epoch', 1, 'single exploratory training run')
    for key, label in [('baseline_seconds', 'Pretrained seven-frame stage'),
                       ('training_seconds', 'Training including validations'),
                       ('after_seconds', 'Fine-tuned seven-frame stage'),
                       ('run_entry_wall_seconds', 'Runner including integrity checks')]:
        add(label, data[key], 'seconds', 1, 'measured execution cost; not continuous-video FPS')
    for key, label in [('allocator_peak_allocated_bytes', 'Peak allocated GPU memory'),
                       ('allocator_peak_reserved_bytes', 'Peak reserved GPU memory')]:
        add(label, data[key] / (1024 ** 2), 'MiB', 1, 'PyTorch allocator across baseline/train/after')
    add('Validation calls', data['validation_calls'], 'calls', 1, 'valid20 only; includes final best validation')
    before = {r['frame_id']: r for r in data['baseline']}
    after = {r['frame_id']: r for r in data['after']}
    if before.keys() != after.keys():
        raise ValueError('Before/after inputs differ')
    comparisons = []
    for fid, row in before.items():
        other = after[fid]
        for key in ('native_pts', 'time_base', 'crop_sha256', 'source_sha256'):
            if row[key] != other[key]:
                raise ValueError('Before/after input provenance differs')
        comparisons.append(dict(frame_id=fid, before=row['person_count'], after=other['person_count'],
                                visual_review='pending', accuracy=None))
        for phase, entry in [('pretrained', row), ('fine_tuned', other)]:
            add(fid + ' ' + phase, entry['person_count'], 'boxes', 1,
                'diagnostic output count; not actual person count or detection accuracy')
    for key, value in data.get('final_best_validation_metrics', {}).items():
        if key.startswith('metrics/'):
            add('Unreviewed valid20: ' + key, value, 'ratio', 20,
                'agreement with provisional labels; not independent CCTV performance')

    # Read the immutable upstream CSV; never recalculate or infer missing metrics.
    csv_path = root / data['epoch_csv']['path']
    if hashlib.sha256(csv_path.read_bytes()).hexdigest() != data['epoch_csv']['sha256']:
        raise ValueError('Recorded training CSV hash differs')
    with csv_path.open() as stream:
        rows = [{k.strip(): float(v) for k, v in r.items()} for r in csv.DictReader(stream)]
    if [r['epoch'] for r in rows] != list(range(1, 21)):
        raise ValueError('Exactly twenty chronological epoch rows required')
    plot = path.parent / 'training-loss-curve.png'
    destination = root / 'records/EXP-0026/metrics.json'
    if plot.exists() or destination.exists():
        raise FileExistsError('Preserve previous summary artifacts')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), constrained_layout=True)
    for ax, prefix in zip(axes, ('train/', 'val/')):
        columns = [k for k in rows[0] if k.startswith(prefix) and k.endswith('loss')]
        if not columns:
            raise ValueError('Actual loss columns required')
        for key in columns:
            ax.plot([r['epoch'] for r in rows], [r[key] for r in rows], label=key)
        ax.set(xlabel='Epoch', ylabel='Loss', title=prefix.rstrip('/') + ' — provisional labels')
        ax.grid(alpha=.25)
        ax.legend()
    fig.suptitle('EXP-0026: unreviewed-label optimization, not CCTV accuracy')
    fig.savefig(plot, dpi=150)
    plt.close(fig)
    document = dict(schema_version=1, experiment_id='EXP-0026', metrics=metrics,
                    comparisons=comparisons, label_review='pending', D0_passed=False,
                    independent_validation=False, default_model_replaced=False,
                    training_settings='configs/batch0007_detect_manifest.json')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('x') as stream:
        json.dump(document, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    return dict(metrics_path=destination.relative_to(root).as_posix(),
                loss_plot=plot.relative_to(root).as_posix(), comparisons=comparisons)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--summary', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(summarize(Path(__file__).resolve().parents[1], args.summary), ensure_ascii=False))
