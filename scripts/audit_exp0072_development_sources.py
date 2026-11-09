"""Read-only metadata/hash audit; never releases sources or changes assignments.

Only Python's standard library is used. Media are streamed for SHA256, never
decoded, inferred, extracted, or uploaded. All detailed paths remain local.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
READY = 'outputs/model-comparison/exp0070/data-readiness-v1/'
PREP = 'outputs/model-comparison/exp0071/wall-normal-preparation-v2/'
AUG = 'outputs/action-recognition/exp0065/augmentation-v1/'
OLD = 'outputs/action-recognition/exp0063/'


def digest(stream):
    h = hashlib.sha256()
    for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
        h.update(block)
    return h.hexdigest()


def sha(path):
    with Path(path).open('rb') as stream:
        return digest(stream)


def read(path):
    return json.loads((ROOT / path).read_text())


def rows(path):
    return [json.loads(line) for line in (ROOT / path).read_text().splitlines()]


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def interval(row):
    start = datetime.strptime(row['date_captured'], '%Y/%m/%d %H:%M:%S')
    return start, start + timedelta(seconds=row['declared_frames'] / row['fps'])


def relation(left, right):
    """Negative metadata checks do not certify physical independence."""
    a, b = interval(left), interval(right)
    same_place = left['location'] == right['location']
    return dict(same_metadata_place=same_place,
                same_metadata_date=a[0].date() == b[0].date(),
                inclusive_capture_overlap=same_place and max(a[0], b[0]) <= min(a[1], b[1]),
                same_place_family_scenario=same_place and
                (left['scenario_family'], left['scenario_number']) ==
                (right['scenario_family'], right['scenario_number']))


def main(output, record):
    inputs = [READY + x for x in ('source-inventory.jsonl', 'split-proposal.json',
              'group-closures.json', 'input-bindings.json', 'source-checks.json',
              'P01-source-check.json', 'P26-source-check.json', 'P28-source-check.json')]
    inputs += [PREP + 'source-reservations.json', PREP + 'summary.json',
               AUG + 'verified-candidates.jsonl', AUG + 'protected-content-fingerprints.jsonl',
               OLD + 'combined-split-v3/split-manifest.json',
               OLD + 'baseline/attempt-002/baseline-lock.json',
               OLD + 'normal-audit-v1/manifest.jsonl',
               'scripts/audit_person_data_readiness.py', 'scripts/prepare_action_augmentation.py',
               'scripts/finalize_person_data_readiness.py', 'scripts/prepare_wall_normal_training_review.py',
               'docs/experiments/EXP-0070-data-readiness.md',
               'docs/experiments/EXP-0071-training-preparation-followup.md',
               'docs/experiments/EXP-0071-acquisition-audit.md']
    bindings = {p: sha(ROOT / p) for p in inputs}
    historical = read(READY + 'input-bindings.json')
    bindings.update({p: sha(ROOT / p) for p in historical})
    assert all(bindings[p] == expected for p, expected in historical.items())
    inventory = rows(READY + 'source-inventory.jsonl')
    by_id = {r['source_id']: r for r in inventory}
    split = read(READY + 'split-proposal.json')
    old = read(OLD + 'combined-split-v3/split-manifest.json')
    old_by_id = {r['source_id']: r for r in old['assignments']}
    groups = {g['group_id']: g for g in read(READY + 'group-closures.json')}
    prep = {r['source_id']: r for r in read(PREP + 'source-reservations.json')}
    verification = rows(AUG + 'verified-candidates.jsonl')
    protected_prints = rows(AUG + 'protected-content-fingerprints.jsonl')
    assert len(protected_prints) == 341 and all('fingerprints' in p for p in protected_prints)
    school = read(OLD + 'baseline/attempt-002/baseline-lock.json')['regression_only_videos']
    school_hashes = {r['sha256'] for r in school}
    old_test = {r['source_sha256'] for r in old['assignments'] if r['split'] == 'test'}
    held_groups = {r['group_id'] for r in verification
                   if r['status'] != 'bounded_duplicate_checks_passed_semantic_review_pending'}
    closures = {r['source_id']: r for r in split['closure_members']}
    captures = {r['reservation_id']: r for r in split['captures']}
    normal = [r for r in inventory if r['scenario_family'] in (30, 31, 32, 33)]
    output.mkdir(parents=True, exist_ok=False)
    archives = {}

    def inspect(ref, expected, label=False):
        info = dict(reference=ref, present=False, sha256=None, matches_expected_sha256=None)
        try:
            if 'path' in ref:
                path = Path(ref['path'])
                with path.open('rb') as stream:
                    raw = stream.read() if label else None
                    actual = hashlib.sha256(raw).hexdigest() if label else digest(stream)
                info.update(present=True, bytes=path.stat().st_size)
            else:
                archive = ref['archive_path']
                if archive not in archives:
                    archives[archive] = zipfile.ZipFile(archive)
                z = archives[archive]
                member = z.getinfo(ref['member'])
                with z.open(member) as stream:
                    raw = stream.read() if label else None
                    actual = hashlib.sha256(raw).hexdigest() if label else digest(stream)
                info.update(present=True, bytes=member.file_size, crc32=member.CRC,
                            matches_recorded_size_crc=(member.file_size, member.CRC) ==
                            (ref.get('bytes', member.file_size), ref.get('crc32', member.CRC)))
            info.update(sha256=actual, expected_sha256=expected,
                        matches_expected_sha256=actual == expected if expected else None)
            if label:
                data = json.loads(raw)
                info['label_info'] = data.get('info', {})
        except (OSError, KeyError, zipfile.BadZipFile, RuntimeError, ValueError) as error:
            info['error'] = type(error).__name__ + ': ' + str(error)
        return info

    audit = []
    for index, r in enumerate(normal):
        source = inspect(r['resolved']['source_reference'], r['source_sha256'])
        label = inspect(r['resolved']['label_reference'], r['label_sha256'], label=True)
        p = prep.get(r['source_id'])
        g = groups[r['group_id']]
        protected = g['partition'] == 'protected_exp0064_test'
        if protected:
            status = 'protected_test_closure'
        elif r['prior_content_hold']:
            status = 'prior_content_hold'
        elif r['proposed_partition'] == 'quarantine':
            status = 'quarantine_in_train_reservation'
        elif p and p['disposition'] == 'train_review_pool':
            status = 'train_reserved_not_development'
        else:
            status = 'unknown_requires_investigation'
        bad = (not source['present'] or not label['present'] or
               source['matches_expected_sha256'] is False or
               label['matches_expected_sha256'] is not True or
               source.get('matches_recorded_size_crc') is False)
        label_info = label.get('label_info', {})
        metadata_matches = all(label_info.get(k) == r[v] for k, v in
                               [('location', 'location'), ('date_captured', 'date_captured'),
                                ('frame', 'declared_frames'), ('fps', 'fps')])
        audit.append(dict(source_id=r['source_id'], group_id=r['group_id'],
            family=r['scenario_family'], scenario=r['scenario_number'],
            declared_actions=sorted({e['class_name'] for e in r['events']}),
            walking_standing_family=r['scenario_family'] in (32, 33),
            metadata_location=r['location'], date_captured=r['date_captured'],
            inventory_available_pair=r['available_pair'], current_available_pair=source['present'] and label['present'],
            current_integrity_issue=bad, current_label_metadata_matches_inventory=metadata_matches,
            availability_status='available' if source['present'] and label['present'] else 'not_available',
            independence_status='unknown_not_certified', development_disposition=status,
            proposed_partition=r['proposed_partition'], proposal_split=r['proposal_split'],
            prior_content_hold=r['prior_content_hold'], prior_errors=r['errors'],
            partition_reasons=r['partition_reasons'],
            old_assignments=[old_by_id[k] for k in r['existing_original_ids']],
            reservation=p['reservation'] if p else None,
            prep_hold_reasons=p['hold_reasons'] if p else [],
            source=source, label=label, safe_development_candidate=False, release=False))
        if (index + 1) % 100 == 0:
            print(json.dumps({'hashed_normal_pairs': index + 1}), flush=True)

    group_audit = []
    for gid in sorted({r['group_id'] for r in normal}):
        rs = [r for r in audit if r['group_id'] == gid]
        vs = [r for r in verification if r['group_id'] == gid]
        group_audit.append(dict(group_id=gid, source_count=len(rs),
            current_available_pairs=sum(r['current_available_pair'] for r in rs),
            disposition_counts=dict(Counter(r['development_disposition'] for r in rs)),
            prior_content_hold=gid in held_groups,
            verification_status_counts=dict(Counter(r['status'] for r in vs)),
            verification_sources=[r['source_id'] for r in vs],
            content_edges=[dict(source_id=r['source_id'], suspects=r.get('suspected_content_overlap', []))
                           for r in vs if r.get('suspected_content_overlap')],
            closure=groups[gid],
            closure_policy=old['policy'], physical_independence_certified=False))

    cases = []
    for cid in ('P01', 'P26', 'P28'):
        case = next(c for c in split['cases'] if c['candidate_id'] == cid)
        r = by_id[case['source_id']]
        check = read(READY + cid + '-source-check.json')
        cases.append(dict(candidate_id=cid, source_id=r['source_id'],
            group_id=r['group_id'], reservation=case['capture_reservation'],
            reserved_split=case['reserved_split'], disposition=prep[r['source_id']]['disposition'],
            metadata_location=r['location'], date_captured=r['date_captured'],
            source=inspect(r['resolved']['source_reference'], check['source_sha256']),
            label=inspect(r['resolved']['label_reference'], r['label_sha256'], label=True),
            prior_bounded_protected_check=dict(exact_match=check['exact_protected_or_other_split_match'],
                suspected_protected_content=check['protected_content_suspects'],
                scope='EXP70 saved five-point fingerprints, not a new decode or independence proof'),
            physical_independence_certified=False, release=False))

    comparisons = []
    # Include whole reservation groups, not only the selected camera/candidate.
    for left_cap in ('capture-reservation-01',):
        left = [r for r in inventory if r['group_id'] in captures[left_cap]['original_group_ids']]
        for right_cap in ('capture-reservation-14', 'capture-reservation-15', 'capture-reservation-19'):
            right = [r for r in inventory if r['group_id'] in captures[right_cap]['original_group_ids']]
            overlaps = [(a['source_id'], b['source_id']) for a in left for b in right
                        if relation(a, b)['inclusive_capture_overlap']]
            comparisons.append(dict(left=left_cap, right=right_cap, left_members=len(left), right_members=len(right),
                shared_source_ids=sorted({r['source_id'] for r in left} & {r['source_id'] for r in right}),
                shared_group_ids=sorted({r['group_id'] for r in left} & {r['group_id'] for r in right}),
                inclusive_metadata_overlap_pairs=overlaps,
                physical_independence_certified=False,
                conclusion='no recorded closure/time collision; physical capture independence unknown'))
    for z in archives.values():
        z.close()

    assert all(sha(ROOT / p) == h for p, h in bindings.items()), 'An input changed during audit'
    expected = Counter({'protected_test_closure': 147, 'prior_content_hold': 108,
                        'quarantine_in_train_reservation': 4, 'train_reserved_not_development': 173})
    assert Counter(r['development_disposition'] for r in audit) == expected
    assert all(r['prior_content_hold'] == (r['group_id'] in held_groups) for r in normal)
    assert len(old_test) == 296 and len(school_hashes) == 45
    assert not any(r['current_integrity_issue'] or not r['current_label_metadata_matches_inventory'] for r in audit)
    assert all(c['source']['matches_expected_sha256'] and c['label']['matches_expected_sha256'] for c in cases)
    assert not any(r['source']['sha256'] in school_hashes | old_test for r in audit
                   if r['development_disposition'] != 'protected_test_closure')
    assert all(not c['shared_source_ids'] and not c['shared_group_ids'] and
               not c['inclusive_metadata_overlap_pairs'] for c in comparisons)
    summary = dict(status='audit_complete_no_safe_normal_development_candidates',
        normal_sources=len(audit), current_available_normal_pairs=sum(r['current_available_pair'] for r in audit),
        unavailable_normal_pairs=sum(not r['current_available_pair'] for r in audit),
        disposition_counts=dict(sorted(expected.items())),
        walking_standing_sources=sum(r['walking_standing_family'] for r in audit),
        walking_standing_dispositions=dict(Counter(r['development_disposition'] for r in audit if r['walking_standing_family'])),
        safe_normal_development_candidates=0, certified_independent_events=None,
        current_source_hashes_checked=len(audit) + len(cases),
        current_label_hashes_checked=len(audit) + len(cases),
        normal_source_hashes_with_prior_comparison=sum(r['source']['matches_expected_sha256'] is not None for r in audit),
        source_or_label_hash_changes=0, current_label_metadata_changes=0,
        protected_school45=45, protected_exp64_originals=296,
        protected_exp64_inventory_closure_members=sum(r['proposed_partition'] == 'protected_exp0064_test' for r in inventory),
        protected_exp64_all_group_members=sum(groups[r['group_id']]['partition'] == 'protected_exp0064_test' for r in inventory),
        certified_p01_p26_p28_physical_independence=False,
        training_runs=0, inference_runs=0, gpu_runs=0, new_decodes=0,
        split_assignments_changed=0, holds_overridden=0, new_person_ground_truth_frames=0,
        source_hash_scope='current local bytes or decompressed ZIP member; all normal pairs plus P01/P26/P28',
        protected_hash_scope='frozen test296/school45 hashes and saved protected341 fingerprints; protected files not rehashed',
        script_sha256=sha(Path(__file__)), input_sha256=bindings)
    with (output / 'normal-source-audit.jsonl').open('x') as stream:
        for r in audit:
            stream.write(json.dumps(r, ensure_ascii=False, allow_nan=False) + '\n')
    save(output / 'normal-group-audit.json', group_audit)
    save(output / 'candidate-hold-list.json', dict(safe_development_candidates=[],
         held_normal_sources=[r['source_id'] for r in audit if r['development_disposition'] != 'train_reserved_not_development'],
         train_reserved_not_development=[r['source_id'] for r in audit if r['development_disposition'] == 'train_reserved_not_development']))
    save(output / 'p01-p26-p28-audit.json', dict(cases=cases, reservation_comparisons=comparisons,
         reservations=[dict(captures[k], closure_members=[r for r in split['closure_members'] if r['capture_reservation'] == k])
                       for k in ('capture-reservation-01', 'capture-reservation-14', 'capture-reservation-15', 'capture-reservation-19')]))
    save(output / 'summary.json', summary)
    hashes = {p.name: sha(p) for p in sorted(output.iterdir()) if p.is_file()}
    save(output / 'output-hashes.json', hashes)
    if record:
        record.parent.mkdir(parents=True, exist_ok=True)
        public = {k: v for k, v in summary.items() if k not in ('input_sha256',)}
        public['output_hashes'] = hashes
        public['output_hash_manifest_sha256'] = sha(output / 'output-hashes.json')
        public['reproduce'] = 'python3 scripts/audit_exp0072_development_sources.py --output NEW_OUTPUT'
        save(record, public)
    print(json.dumps({k: v for k, v in summary.items() if k != 'input_sha256'}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='Must not already exist')
    parser.add_argument('--record', type=Path, help='Optional new aggregate JSON record')
    args = parser.parse_args()
    main(args.output, args.record)
