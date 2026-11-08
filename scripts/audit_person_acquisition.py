"""EXP0071 local acquisition audit; no models, split edits or media exports.

Run with .venv-cv-batch02/bin/python. Output JSON contains LOCAL ONLY paths
and original captions. The separately written public report must omit both.
Existing search transcripts are evidence of bounded searches, not all-disk proof.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import zipfile

import av

from prepare_action_augmentation import fingerprint_bytes, suspicious_content

ROOT = Path(__file__).resolve().parents[1]
ACQ = ROOT / 'outputs/model-comparison/exp0071/acquisition-v1'
READY = ROOT / 'outputs/model-comparison/exp0070/data-readiness-v1'
AUG = ROOT / 'outputs/action-recognition/exp0065/augmentation-v1'
OLD = ROOT / 'outputs/action-recognition/exp0063'
OFFICIAL = 'https://www.aihub.or.kr/aihubdata/data/view.do?currMenu=115&dataSetSn=477&topMenu=100'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def save(path, value):
    with path.open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def inventory_audit(out):
    inventory = rows(READY / 'source-inventory.jsonl')
    search_names = ['storage-matches.txt', 'extracted-park-files.txt',
                    'c-drive-other-matches.txt', 'storage-search-errors.txt',
                    'extracted-search-errors.txt', 'c-drive-other-errors.txt']
    searches = {n: (ACQ / n).read_text().splitlines() for n in search_names}
    found_paths = sorted(set(searches['storage-matches.txt'] + searches['extracted-park-files.txt']
                             + searches['c-drive-other-matches.txt']))
    extracted = defaultdict(list)
    for p in found_paths:
        if Path(p).suffix.lower() in ('.mp4', '.json') and Path(p).is_file():
            extracted[Path(p).name].append(p)
    archive_paths = {r[k]['archive_path'] for r in inventory
                     for k in ('source_reference', 'label_reference')}
    archive_paths.update(p for p in found_paths if p.endswith('.zip'))
    archives = {}; archive_members = defaultdict(list); missing = []
    archive_stats = []
    for p in sorted(archive_paths):
        if not Path(p).is_file():
            missing.append(p)
            continue
        with zipfile.ZipFile(p) as z:
            entries = [m for m in z.infolist() if not m.is_dir()]
            archives[p] = {m.filename: (m.file_size, m.CRC) for m in entries}
            for m in entries:
                archive_members[Path(m.filename).name].append(dict(
                    archive_path=p, member=m.filename, bytes=m.file_size, crc32=m.CRC))
            families = Counter()
            for m in entries:
                name = Path(m.filename).name
                if name.startswith('C_') and name.endswith('.mp4'):
                    families[name.split('_')[1]] += 1
            archive_stats.append(dict(path=p, bytes=Path(p).stat().st_size,
                                      members=len(entries), video_family_counts=dict(families),
                                      metadata_only=True, full_archive_sha256=None))
    audited = []; new_recoveries = []; unverified_recovery_matches = []
    for r in inventory:
        checks = {}
        for kind in ('source_reference', 'label_reference'):
            ref = r[kind]; name = Path(ref['member']).name
            listed = archive_members.get(name, [])
            direct = extracted.get(name, [])
            original = archives.get(ref['archive_path'], {}).get(ref['member'])
            original_ok = original is not None and (kind != 'source_reference' or
                              original == (ref['bytes'], ref['crc32']))
            checks[kind] = dict(basename=name, historical_reference=ref,
                original_archive_member_metadata_matches=original_ok,
                archive_basename_matches=listed,
                extracted_basename_matches=[dict(path=p, bytes=Path(p).stat().st_size) for p in direct],
                basename_alone_is_identity_proof=False)
        prior_missing = not r['available_pair']
        # A basename hit is only a candidate; validate any recovered missing bytes.
        if prior_missing:
            recovered = {}
            for kind, check in checks.items():
                verified = []
                for p in check['extracted_basename_matches']:
                    h = sha(p['path'])
                    expected = r.get('label_sha256' if kind == 'label_reference' else 'source_sha256')
                    if expected and h == expected:
                        verified.append(dict(**p, sha256=h))
                    else:
                        unverified_recovery_matches.append(dict(source_id=r['source_id'], kind=kind,
                            path=p['path'], sha256=h, expected_sha256=expected))
                for ref in check['archive_basename_matches']:
                    with zipfile.ZipFile(ref['archive_path']) as z:
                        raw = z.read(ref['member'])
                    h = hashlib.sha256(raw).hexdigest()
                    expected = r.get('label_sha256' if kind == 'label_reference' else 'source_sha256')
                    if expected and h == expected:
                        verified.append(dict(**ref, sha256=h))
                    else:
                        unverified_recovery_matches.append(dict(source_id=r['source_id'], kind=kind,
                            reference=ref, sha256=h, expected_sha256=expected))
                recovered[kind] = verified
            if all(recovered.values()):
                new_recoveries.append(dict(source_id=r['source_id'], recovered=recovered,
                    status='hold_original_split_and_event_closure_check_required'))
        audited.append(dict(source_id=r['source_id'], family=r['scenario_family'],
                            prior_available_pair=r['available_pair'], checks=checks))
    save(out / 'member-reconciliation.local.json', dict(local_only=True, rows=audited,
        duplicate_policy='Extracted and archive basename copies are never counted as new independent sources.'))
    missing_rows = [r for r in audited if not r['prior_available_pair']]
    wall = [r for r in inventory if r['scenario_family'] == 4]
    summary = dict(historical_rows=len(inventory), prior_available_pairs=sum(r['available_pair'] for r in inventory),
        prior_missing_pairs=len(missing_rows), missing_archives=missing,
        missing_source_basename_hits=sum(bool(r['checks']['source_reference']['archive_basename_matches'] or
            r['checks']['source_reference']['extracted_basename_matches']) for r in missing_rows),
        missing_label_basename_hits=sum(bool(r['checks']['label_reference']['archive_basename_matches'] or
            r['checks']['label_reference']['extracted_basename_matches']) for r in missing_rows),
        recovered_pairs=new_recoveries, unverified_recovery_matches=unverified_recovery_matches,
        inventory_duplicate_source_basenames={k:v for k,v in Counter(r['original_filename'] for r in inventory).items() if v>1},
        source_rows_with_extracted_and_archive_basename_copy=sum(bool(r['checks']['source_reference']['extracted_basename_matches'])
            and r['checks']['source_reference']['original_archive_member_metadata_matches'] for r in audited),
        extracted_copy_identity_limit='Matching basename/size is not a full-byte duplicate certificate; existing extracted videos were not rehashed.',
        archive_member_source_metadata_mismatches=sum(r['source_reference']['archive_path'] in archives and
            not a['checks']['source_reference']['original_archive_member_metadata_matches'] for r,a in zip(inventory,audited)),
        archive_inventory=archive_stats,
        wall_family=dict(total=len(wall), available=sum(r['available_pair'] for r in wall),
            by_archive=dict(Counter(Path(r['source_reference']['archive_path']).name for r in wall)),
            prior_proposal_counts=dict(Counter(r['proposal_split'] for r in wall)),
            excluded=sum(r['excluded'] for r in wall),
            note='Existing family4 is retained material, not recovered/new independent wall-climbing test evidence.'),
        search_evidence={n:dict(sha256=sha(ACQ/n), lines=len(v)) for n,v in searches.items()},
        search_scope='Reuses coordinator C/D/E/F + home/tmp search; permission failures prevent universal absence proof.',
        shortcuts=[p for p in found_paths if p.endswith('.lnk')],
        official_redownload=dict(url=OFFICIAL, exact_missing_paths=missing,
            path_source='Historical archive references, not a newly authenticated download listing',
            download_attempted=False, release_after_recovery=False))
    save(out / 'inventory-audit.local.json', summary)
    return summary


def downloads_audit(out):
    result = []
    for p in sorted(Path('/mnt/c/Users/jhc74/Downloads').glob('SceneGuard_FCOS_miss_comparison*.zip')):
        with zipfile.ZipFile(p) as z:
            members = [dict(member=m.filename, bytes=m.file_size, sha256=hashlib.sha256(z.read(m)).hexdigest())
                       for m in z.infolist() if not m.is_dir()]
        result.append(dict(path=str(p), sha256=sha(p), bytes=p.stat().st_size, members=members,
            media_members=sum(Path(m['member']).suffix.lower() in ('.mp4','.avi','.mov','.jpg','.png') for m in members),
            classification='specification_only_no_source_or_labels_acquired'))
    save(out / 'download-archives.local.json', result)
    return result


def invasion_audit(out):
    inventory = rows(AUG / 'other-local-07-labels.jsonl')
    selected = sorted((r for r in inventory if r['filename'] in
                       {f'E01_{i:03}.mp4' for i in range(51,56)}), key=lambda r:r['filename'])
    assert len(selected) == 5
    protected = rows(AUG / 'protected-content-fingerprints.jsonl')
    assert len(protected) == 341 and all('fingerprints' in r for r in protected)
    school = [r for r in protected if r['source_id'].startswith('regression:')]
    assert len(school) == 45
    school_same_date = [r for r in inventory if r['protected45'] and r['capture_date']=='240929']
    assert len(school_same_date) == 12
    old = rows(OLD / 'data-audit/manifest.jsonl') + rows(OLD / 'normal-audit-v1/manifest.jsonl')
    all_old_hashes = {r['source_sha256'] for r in old} | {p['recorded_source_sha256'] for p in protected}
    result = []; zip_hashes = {}
    for r in selected:
        source = r['source_references'][0]
        for path in (source['archive_path'], r['label_archive']):
            if path not in zip_hashes:
                zip_hashes[path] = sha(path)
        with zipfile.ZipFile(r['label_archive']) as z:
            labelraw = z.read(r['label_member'])
        labelsha = hashlib.sha256(labelraw).hexdigest()
        assert labelsha == r['label_sha256']
        label = json.loads(labelraw)
        with zipfile.ZipFile(source['archive_path']) as z:
            info = z.getinfo(source['member'])
            assert (info.file_size,info.CRC) == (source['bytes'],source['crc32'])
            raw = z.read(source['member'])
        h = hashlib.sha256(raw).hexdigest()
        with av.open(io.BytesIO(raw)) as c:
            s = c.streams.video[0]; s.codec_context.thread_count = 1
            props = dict(average_rate=str(s.average_rate), base_rate=str(s.base_rate),
                time_base=str(s.time_base), start_pts=s.start_time,
                duration_seconds=float(s.duration*s.time_base), declared_container_frames=s.frames,
                width=s.width,height=s.height,container_duration_seconds=c.duration/av.time_base)
        fps = float(s.average_rate)
        prints = fingerprint_bytes(raw)
        annotations = label['annotations']
        windows = [dict(declared_frames=pair, origin0_seconds=[v/fps for v in pair],
            origin1_seconds=[(v-1)/fps for v in pair], frame_origin_certified=False,
            span_seconds=(pair[1]-pair[0])/fps) for pair in annotations['event_frame']]
        exact = [p['source_id'] for p in protected if p['recorded_source_sha256']==h]
        limited = [p['source_id'] for p in protected if suspicious_content(prints,p['fingerprints'])]
        result.append(dict(candidate_id=Path(r['filename']).stem, source_reference=source,
            source_sha256=h, label_reference=dict(archive_path=r['label_archive'],member=r['label_member']),
            label_sha256=labelsha, source_bytes=len(raw), original_label=label,
            native_video=props,event_windows=windows, fingerprints=prints,
            label_metadata_matches_stream=dict(
                dimensions=[label['metadata']['width'],label['metadata']['height']]==[props['width'],props['height']],
                frame_count=label['metadata']['frame_count']==props['declared_container_frames'],
                capture_date_matches_inventory=label['metadata']['date']==r['capture_date']),
            declared_event_length_seconds=annotations['event_length'],
            event_length_minus_frame_span_seconds=annotations['event_length']-sum(w['span_seconds'] for w in windows),
            exact_protected_matches=exact, exact_any_old_hash_match=h in all_old_hashes,
            limited_protected_matches=limited,
            same_capture_date_protected_sources=[r['filename'] for r in school_same_date],
            status='hold_shared_capture_date_independent_event_not_proven',
            independent_test_acquired=False, complete_person_gt=False, training_eligible=False,
            caption_semantics='Official event-level fence-crossing description; not independently verified pixels, actor boxes or permission truth.'))
        print(json.dumps(dict(candidate=Path(r['filename']).stem, source_sha256=h,
                             limited_protected_matches=len(limited))),flush=True)
    overlaps = [dict(a=a['candidate_id'],b=b['candidate_id'], exact=a['source_sha256']==b['source_sha256'],
        limited=suspicious_content(a['fingerprints'],b['fingerprints']))
        for i,a in enumerate(result) for b in result[i+1:]
        if a['source_sha256']==b['source_sha256'] or suspicious_content(a['fingerprints'],b['fingerprints'])]
    value = dict(local_only=True, source_inventory_rows=len(inventory), selected=result,
        archive_sha256=zip_hashes, protected_sources=len(protected), school_sources=len(school),
        protected_same_capture_date=12, candidate_pair_overlap_flags=overlaps,
        limitation='Five relative-time CPU fingerprints, not full decode or crop/shift/partial-copy proof; same date alone is not same-event proof or independence proof.',
        visual_semantic_review_performed=False, media_exported=False, persisted_pixel_frames=0)
    save(out / 'invasion-candidates.local.json', value)
    return value


def main(out):
    out.mkdir(parents=True,exist_ok=True)
    outputs = ['member-reconciliation.local.json','inventory-audit.local.json',
               'download-archives.local.json','invasion-candidates.local.json','acquisition-audit.json']
    if any((out/n).exists() for n in outputs):
        raise FileExistsError('Use a fresh audit output; existing evidence is immutable')
    bindings = [READY/'source-inventory.jsonl', READY/'input-bindings.json',READY/'review-reuse.json',
        READY/'split-proposal.json', AUG/'other-local-07-labels.jsonl',AUG/'protected-content-fingerprints.jsonl',
        AUG/'split-manifest.json',OLD/'combined-split-v3/split-manifest.json',
        OLD/'baseline/attempt-002/baseline-lock.json',
        ROOT/'outputs/model-comparison/exp0067/confirmed-person-v1/manifest.json',
        ROOT/'runtime/model-comparison/exp0067/review-application-v1/resolved-answers.json']
    before = {str(p):sha(p) for p in bindings}
    inv = inventory_audit(out); downloads=downloads_audit(out); invasion=invasion_audit(out)
    after = {str(p):sha(p) for p in bindings}
    assert before == after
    old_bindings = read(READY/'input-bindings.json')
    assert all(sha(ROOT/p)==h for p,h in old_bindings.items())
    proposal = read(READY/'split-proposal.json')
    reuse = read(READY/'review-reuse.json')
    old_test_count = sum(r['split']=='test' for r in read(OLD/'combined-split-v3/split-manifest.json')['assignments'])
    school_count = len(read(OLD/'baseline/attempt-002/baseline-lock.json')['regression_only_videos'])
    confirmed_frames = sum(r['frames'] for r in reuse['EXP0067'])
    assert old_test_count == proposal['protected_exp0064_test_originals'] == 296
    assert school_count == 45 and proposal['protected_school45'] is True
    assert proposal['protected_test_closure_members'] == 327 and confirmed_frames == 75
    summary = dict(title='EXP0071 acquisition audit',created_utc=datetime.now(timezone.utc).isoformat(),
        local_only=True, script_sha256=sha(Path(__file__)),
        historical_pairs=inv['historical_rows'],available_pairs=inv['prior_available_pairs'],
        missing_pairs=inv['prior_missing_pairs'],missing_archives=len(inv['missing_archives']),
        recovered_missing_pairs=len(inv['recovered_pairs']), wall_family=inv['wall_family'],
        specification_only_download_zips=len(downloads), additional_invasion_candidates=len(invasion['selected']),
        independent_new_test_confirmed=0, complete_person_gt=0, model_training_runs=0,
        model_loads=0, model_inference_runs=0,gpu_jobs=0,external_media_transfers=0,split_changes=0,
        preserved_input_sha256=before, preserved_input_hashes_unchanged=before==after,
        exp0070_all_original_input_bindings_match=True,baseline_test_sources=old_test_count,
        related_protected_members=proposal['protected_test_closure_members'],
        school_regression_sources=school_count,existing_confirmed_person_frames=confirmed_frames,
        qualification='Acquisition audit complete; independent-event certification and complete people GT remain held.',
        outputs={n:sha(out/n) for n in outputs if (out/n).exists()})
    save(out/'acquisition-audit.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('preserved_input_sha256','outputs','wall_family')},ensure_ascii=False))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ACQ)
    main(parser.parse_args().output)
