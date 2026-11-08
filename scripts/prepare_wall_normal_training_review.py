"""Narrow EXP0071 preparation to wall/normal sources; never releases labels."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
READY = ROOT / 'outputs/model-comparison/exp0070/data-readiness-v1'
DRAFT = ROOT / 'outputs/model-comparison/exp0071/person-drafts-v1'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p):
    return json.loads(p.read_text())


def save(p, value):
    with p.open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def main(out):
    out.mkdir(parents=True, exist_ok=False)
    inputs = read(READY / 'input-bindings.json')
    for path, expected in inputs.items():
        assert sha(ROOT / path) == expected, path
    inventory = [json.loads(line) for line in (READY / 'source-inventory.jsonl').read_text().splitlines()]
    split = read(READY / 'split-proposal.json')
    reservations = {r['source_id']: r for r in split['closure_members']}
    selected = [r for r in inventory if r['available_pair'] and r['scenario_family'] in (4,30,31,32,33)]
    archives = {}; rows = []
    for r in selected:
        problems = []
        for kind in ('source_reference', 'label_reference'):
            ref = r['resolved'][kind]
            if 'path' in ref:
                path = Path(ref['path'])
                if not path.is_file():
                    problems.append(kind + '_missing'); continue
                raw = path.read_bytes() if kind == 'label_reference' else None
            else:
                archive = ref['archive_path']
                if archive not in archives:
                    archives[archive] = zipfile.ZipFile(archive)
                z = archives[archive]; member = z.getinfo(ref['member'])
                if kind == 'source_reference':
                    if (member.file_size, member.CRC) != (ref['bytes'], ref['crc32']):
                        problems.append('source_member_metadata_changed')
                    raw = None
                else:
                    raw = z.read(ref['member'])
            if raw is not None and hashlib.sha256(raw).hexdigest() != r['label_sha256']:
                problems.append('label_hash_changed')
        reservation = reservations.get(r['source_id'])
        proposed = r['proposal_split']
        reasons = list(problems)
        if r['excluded']: reasons.append('user_excluded_scenario')
        if r['prior_content_hold']: reasons.append('prior_content_hold')
        if proposed not in ('train', 'development', 'new_test'): reasons.append(r['proposed_partition'])
        if reservation and reservation['reserved_split'] != proposed:
            reasons.append('capture_reserved_for_other_split')
        disposition = 'hold' if reasons else proposed + '_review_pool'
        rows.append(dict(source_id=r['source_id'],family=r['scenario_family'],
            role='wall_source' if r['scenario_family']==4 else 'normal_source',
            disposition=disposition,hold_reasons=reasons,
            reservation=reservation['capture_reservation'] if reservation else 'existing-group:'+r['group_id'],
            prior_partition=r['proposed_partition'],prior_split=proposed,
            source_reference=r['resolved']['source_reference'],label_reference=r['resolved']['label_reference'],
            label_sha256=r['label_sha256'],source_sha256=r['source_sha256'],
            source_integrity_scope='file presence or ZIP member size/CRC; not full decode',
            complete_new_person_ground_truth=False,training_release=False))
    for z in archives.values(): z.close()
    active = defaultdict(set)
    for r in rows:
        if r['disposition']!='hold': active[r['reservation']].add(r['disposition'])
    assert all(len(v)==1 for v in active.values())
    # Existing requests are reused, never recreated or auto-answered.
    with urllib.request.urlopen('http://127.0.0.1:8765/api/review-requests?experiment_id=EXP-0071') as response:
        requests = json.load(response)['requests']
    save(out/'review-snapshot.json', requests)
    request_map = {r['artifact_id']:r for r in requests}
    packages = []
    for rid in ('R02','R01','R04'):
        draft = read(DRAFT/f'{rid}-drafts.json')
        source = next(r for r in rows if r['source_id']==draft['source_id'])
        assert source['disposition']=='train_review_pool'
        request = request_map[f'exp0071-{rid.lower()}-comparison']
        flags = [dict(source_pts=f['source_pts'],reason='no_model_proposal_not_empty_ground_truth')
                 for f in draft['frames'] if not f['model_proposals']['boxes']]
        packages.append(dict(review_id=rid,request_id=request['id'],status=request['status'],
            answer_version=request['answer_version'],source_id=draft['source_id'],
            source_pts=draft['source_pts'],frame_count=draft['frame_count'],
            proposal_count=draft['proposal_count'],reservation=source['reservation'],
            draft_path=str((DRAFT/f'{rid}-drafts.json').relative_to(ROOT)),
            draft_sha256=sha(DRAFT/f'{rid}-drafts.json'),priority_flags=flags,
            purpose='all visible people, not only climbing actor',
            complete_person_ground_truth=False,training_release=False))
    prior = read(ROOT/'outputs/model-comparison/exp0067/confirmed-person-v1/manifest.json')
    for package in packages:
        d = read(ROOT/package['draft_path'])
        for frame in prior['frames']:
            if frame['source_sha256']==d['source_sha256']:
                assert all(abs(t-frame['source_pts'])>1e-6 for t in package['source_pts'])
    save(out/'source-reservations.json',rows)
    save(out/'first-review-batch.json',packages)
    counts = Counter((r['disposition'],r['role']) for r in rows)
    summary = dict(status='preparation_complete_waiting_for_human_labels_and_capture_checks',
        considered_sources=len(rows),by_disposition_and_role=[dict(disposition=d,role=r,count=n) for (d,r),n in sorted(counts.items())],
        review_reservations=len(active),certified_independent_events=None,
        current_label_hash_changes=sum('label_hash_changed' in r['hold_reasons'] for r in rows),
        first_batch_existing_questions=len(packages),first_batch_frames=sum(p['frame_count'] for p in packages),
        first_batch_draft_boxes=sum(p['proposal_count'] for p in packages),
        existing_confirmed_frames=len(prior['frames']),reasked_confirmed_frames=0,
        new_complete_ground_truth_frames=0,training_runs=0,gpu_inference=0,new_model_inference=0,
        new_review_questions=0,training_release=False,
        missing_archives_1_3_4_required=False,
        outside_focus_existing_requests=['R03','R05'],
        release_requirements=['all visible person boxes reviewed at exact native PTS',
            'capture and multicamera closure verified before train/development/test release',
            'normal walking/standing development coverage beyond legacy sitting case',
            'new wall test independent from training/development; protected school45/test296 preserved'],
        input_sha256={**inputs, str((READY/'source-inventory.jsonl').relative_to(ROOT)):sha(READY/'source-inventory.jsonl'),
            str((READY/'split-proposal.json').relative_to(ROOT)):sha(READY/'split-proposal.json')},
        script_sha256=sha(Path(__file__)))
    for path, expected in inputs.items(): assert sha(ROOT/path)==expected
    save(out/'summary.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k!='input_sha256'},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    main(parser.parse_args().output)
