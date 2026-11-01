"""Bind frozen truth to explicit user camera assignments without relabelling events.

Local-only output: original truth and inventory are never overwritten. No model
or pixel inputs are read, and execution does not receive any truth fields.
"""
import argparse
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

from scripts import mvp_full_evaluation_adapter as old


def rebind_gate(value, gate):
    if isinstance(value, dict):
        return {k: gate if k == 'gate_id' else rebind_gate(v, gate)
                for k, v in value.items()}
    if isinstance(value, list):
        return [rebind_gate(v, gate) for v in value]
    return value


def mapped_row(row, registry, clocks):
    result = deepcopy(row)
    source = registry['sources'].get(str(Path(row['path']).absolute()))
    if source is None or source['sha256'] != row['sha256']:
        raise ValueError('User registry must bind the same original source')
    camera = registry['cameras'][source['camera_id']]
    result.update(camera_id=source['camera_id'],
                  gate_id=camera['legacy_boundary_config']['boundary_id'],
                  camera_assignment_status='user_explicit_group',
                  camera_assignment_provenance='user static grouping 2026-11-02')
    rate = Fraction(row['media']['average_rate'])
    if rate not in (Fraction(30), Fraction(30000, 1001)):
        raise ValueError('Unsupported native source rate')
    result['media']['full_native_end_seconds'] = float(
        Fraction(clocks['native_pts'][-1])*Fraction(clocks['time_base'])+1/rate)
    # Original media duration, split and annotation uncertainty remain unchanged.
    result['prior_support_assessment'] = result.pop('support', None)
    result['support'] = {'status': 'explicit_registry_pending_execution',
                         'not_a_success_claim': True}
    return result


def prepare(inventory_path, truth_directory, registry_path, output, root=old.ROOT):
    inventory_path, truth_directory, registry_path, output = map(
        Path, (inventory_path, truth_directory, registry_path, output))
    if output.exists():
        raise ValueError('Fresh expanded evaluation directory required')
    inventory, registry = old.read(inventory_path), old.read(registry_path)
    result = deepcopy(inventory)
    result['prior_summary'] = result.pop('summary', None)
    result['provenance_extension'] = dict(
        original_inventory_sha256=old.sha256(inventory_path),
        registry_sha256=old.sha256(registry_path),
        scope='Camera/gate identity and explicit native EOF only; no truth tuning')
    rows = []
    for row in inventory['videos']:
        path = old.resolve(row['native_pts_path'], root)
        if old.sha256(path) != row['native_pts_sha256']:
            raise ValueError('Original source clock changed')
        rows.append(mapped_row(row, registry, old.read(path)['clocks']))
    if set(registry['sources']) != {str(Path(r['path']).absolute()) for r in rows}:
        raise ValueError('Registry must preserve the exact complete inventory')
    result['videos'] = rows
    output.mkdir(parents=True)
    invpath = output/'inventory.json'
    old.save(invpath, result)
    mapping = {r['video_id']: r['gate_id'] for r in rows}
    for name in ('official-zero-based', 'official-one-based', 'reviewed'):
        source_path = truth_directory/(name+'.json')
        truth = old.read(source_path)
        if truth['inventory_sha256'] != old.sha256(inventory_path):
            raise ValueError('Original truth inventory binding differs')
        if {r['video_id'] for r in truth['videos']} != set(mapping):
            raise ValueError('All original truth rows are required')
        target = deepcopy(truth)
        target.update(inventory_sha256=old.sha256(invpath),
                      previous_truth_sha256=old.sha256(source_path),
                      camera_registry_sha256=old.sha256(registry_path))
        target['videos'] = [rebind_gate(r, mapping[r['video_id']]) for r in truth['videos']]
        old.save(output/(name+'.json'), target)
    return dict(videos=len(rows), output=str(output))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('inventory', 'truth-directory', 'registry', 'output'):
        p.add_argument('--'+key, type=Path, required=True)
    args = p.parse_args()
    print(prepare(args.inventory, args.truth_directory, args.registry, args.output))
