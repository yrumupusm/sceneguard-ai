"""Audit authorized normal-action ZIPs and save a combined pre-training split.

Does not extract frames or assign negative training labels. ZIP members are copied
to a new local directory by validated unique basename; original ZIPs stay intact.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

from audit_action_dataset import BASE, audit_pair, sha256, write_json, write_jsonl


def combined_split(rows):
    """Join overlapping captures and exact copies, including simultaneous cameras.

    Same location/family/scenario is also joined across dates and camera clocks.
    A shared date alone does not establish the same event. Same-location test is
    explicitly separate from site holdout.
    """
    parent = {r['source_id']: r['source_id'] for r in rows}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    def union(a, b):
        a,b=find(a),find(b)
        if a!=b:parent[max(a,b)]=min(a,b)
    by_hash, by_scenario, places = {}, {}, defaultdict(list)
    edges=[]
    for r in rows:
        key=r['source_id'];digest=r['source_sha256']
        if digest and digest in by_hash:
            union(key,by_hash[digest]);edges.append([key,by_hash[digest],'exact_sha256'])
        if digest: by_hash[digest]=key
        info=(r.get('label') or {}).get('info',{})
        scenario_key=(info.get('location'),r.get('scenario_family',4),r.get('scenario'))
        if scenario_key[0] and scenario_key[2] is not None:
            if scenario_key in by_scenario:
                union(key,by_scenario[scenario_key]);edges.append([key,by_scenario[scenario_key],'same_location_family_scenario'])
            by_scenario[scenario_key]=key
        try:
            start=datetime.strptime(info['date_captured'],'%Y/%m/%d %H:%M:%S')
            duration=r['video']['stream_duration_seconds']
            places[info['location']].append((start,start+timedelta(seconds=duration),key))
        except (KeyError,TypeError,ValueError):
            continue
    for location, captures in places.items():
        active=[]
        for start,end,key in sorted(captures):
            active=[(e,k) for e,k in active if e>=start]
            for _,other in active:
                union(key,other);edges.append([key,other,'overlapping_capture_same_location'])
            active.append((end,key))
    components=defaultdict(list)
    for r in rows:components[find(r['source_id'])].append(r)
    groups=[]
    heldout='busan_children-grand-park'
    strata=defaultdict(list)
    for members in components.values():
        ids=sorted(r['source_id'] for r in members)
        gid='event-'+hashlib.sha256('\n'.join(ids).encode()).hexdigest()[:20]
        locations={r['label']['info']['location'] for r in members if r.get('label') and r['label'].get('info')}
        use=[r for r in members if not r['excluded'] and not r['errors']]
        classes=set(c for r in use for c in r['label']['event_classes'])
        stratum='normal' if classes & {'moving','stand','sit_down_bench','sit_down_floor'} and 'wall_over' not in classes else 'wall_over_or_mixed'
        group={'group_id':gid,'source_ids':ids,'locations':sorted(locations),'stratum':stratum,
               'split':'quarantine' if len(locations)!=1 else 'test' if heldout in locations else None,
               'evaluation_cohort':'heldout_place' if heldout in locations else 'same_place_separate_capture'}
        groups.append(group)
        if group['split'] is None:strata[(next(iter(locations)),stratum)].append(group)
    for stratum, members in sorted(strata.items()):
        members.sort(key=lambda g:hashlib.sha256(('exp0063-seed6301:'+g['group_id']).encode()).hexdigest())
        # Allocation is based on group count/declared class, never model outcomes.
        n=len(members); nv=max(1,round(n*.15)) if n>=3 else 0; nt=max(1,round(n*.15)) if n>=3 else 0
        for i,g in enumerate(members):g['split']='validation' if i<nv else 'test' if i<nv+nt else 'train'
    by_id={r['source_id']:r for r in rows};assignments=[]
    for group in groups:
        for key in group['source_ids']:
            r=by_id[key]
            assignments.append({'source_id':key,'source_sha256':r['source_sha256'],
                'label_sha256':r['label_sha256'],'group_id':group['group_id'],
                'location':r['label']['info']['location'] if r.get('label') else None,
                'split':'excluded' if r['excluded'] else 'quarantine' if r['errors'] else group['split'],
                'excluded':r['excluded'],'evaluation_cohort':group['evaluation_cohort'],
                'training_eligible':False,'reason':'temporal_box_and_semantic_review_pending'})
    return {'schema_version':'exp0063-combined-split-v3','status':'frozen_original_groups_pending_label_review',
        'policy':['same_location_overlapping_capture_intervals_inclusive','simultaneous_multicamera_via_capture_overlap',
                  'same_location_family_scenario_across_dates','exact_sha256_globally','site_and_class_group_stratification_before_training'],
        'revision_reason':'Normal data authorized; retain scenario grouping even when camera capture clocks do not overlap. Prior v1/v2 proposals preserved; no training yet.',
        'test_location':heldout,'held_out_test_locations':[heldout],'seed':6301,
        'limitations':['Capture metadata not independently verified; questionable sessions require quarantine.',
                      'Same-place test shares backgrounds/actors and is not independent camera generalization.',
                      'Held-out place has insufficient verified negative coverage.'],
        'assignments':sorted(assignments,key=lambda x:x['source_id']),
        'groups':sorted(groups,key=lambda x:x['group_id']),'connections':edges}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',type=Path,default=BASE)
    p.add_argument('--wall-audit',type=Path,required=True)
    p.add_argument('--baseline-lock',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--normal-audit',type=Path,help='Reuse audited normal sources to create a fresh combined split without decoding')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    if a.normal_audit:
        paths=[a.wall_audit/'manifest.jsonl',a.normal_audit/'manifest.jsonl']
        rows=[json.loads(line) for path in paths for line in path.read_text().splitlines()]
        baseline=json.loads(a.baseline_lock.read_text())
        forbidden={v['sha256'] for v in baseline['regression_only_videos']}
        if any(r['source_sha256'] in forbidden for r in rows):
            raise ValueError('Regression source overlap')
        split=combined_split(rows)
        split.update(wall_manifest_sha256=sha256(paths[0]),normal_manifest_sha256=sha256(paths[1]),
                     script_sha256=sha256(__file__))
        write_json(a.output/'split-manifest.json',split)
        print(json.dumps({'split_sha256':sha256(a.output/'split-manifest.json'),
                          'counts':dict(Counter(r['split'] for r in split['assignments']))}))
        return
    source_dir=a.output/'sources';label_dir=a.output/'labels';source_dir.mkdir();label_dir.mkdir()
    origins={}
    for kind, name, destination, suffix in [
        ('source','원천데이터/TS_행위(정상행위)데이터.zip',source_dir,'.mp4'),
        ('label','라벨링데이터/TL_행위(정상행위)데이터.zip',label_dir,'.json')]:
        archive=a.base/name;members={}
        with zipfile.ZipFile(archive) as z:
            for entry in z.infolist():
                if entry.is_dir():continue
                base=Path(entry.filename).name
                if not re.fullmatch(r'[A-Za-z0-9_.-]+',base) or not base.endswith(suffix) or base in members:
                    raise ValueError('Unexpected or colliding archive member')
                dest=destination/base
                with z.open(entry) as src, dest.open('xb') as dst:shutil.copyfileobj(src,dst,1024*1024)
                members[base]={'zip_member':entry.filename,'crc32':entry.CRC,'size':entry.file_size}
        origins[kind]={'path':str(archive),'sha256':sha256(archive),'members':members}
        print(json.dumps({'extracted':kind,'files':len(members)}),flush=True)
    write_json(a.output/'archive-provenance.json',origins)
    if {Path(n).stem for n in origins['source']['members']} != {Path(n).stem for n in origins['label']['members']}:
        raise ValueError('Archive source and label basename sets differ')
    rows=[]
    with (a.output/'packet-pts.jsonl').open('w') as pts_file, (a.output/'manifest.partial.jsonl').open('w') as partial:
        for i,f in enumerate(sorted(label_dir.glob('*.json'))):
            d=json.loads(f.read_text());source=source_dir/d['info']['filename']
            parts=source.stem.split('_')
            row=audit_pair({'source_id':'normal/'+source.stem,'scenario':int(parts[2]),
                'scenario_family':int(parts[1]),'excluded':False,'exclusion_reason':None,
                'source_path':str(source.resolve()),'label_path':str(f.resolve())})
            if row['video']:
                pts_file.write(json.dumps({'source_id':row['source_id'],**row['video'].pop('_packet_records')})+'\n')
            rows.append(row);partial.write(json.dumps(row,ensure_ascii=False)+'\n');partial.flush()
            if (i+1)%24==0:print(json.dumps({'audited_normal':i+1}),flush=True)
    (a.output/'manifest.partial.jsonl').rename(a.output/'manifest.jsonl')
    wall=[json.loads(line) for line in (a.wall_audit/'manifest.jsonl').read_text().splitlines()]
    all_rows=wall+rows
    baseline=json.loads(a.baseline_lock.read_text());forbidden={v['sha256'] for v in baseline['regression_only_videos']}
    if any(r['source_sha256'] in forbidden for r in all_rows):raise ValueError('Regression source overlap')
    split=combined_split(all_rows)
    split['wall_manifest_sha256']=sha256(a.wall_audit/'manifest.jsonl')
    split['normal_manifest_sha256']=sha256(a.output/'manifest.jsonl')
    write_json(a.output/'combined-split-manifest.json',split)  # BEFORE any frame decode.
    errors=Counter(e['code'] for r in rows for e in r['errors'])
    summary={'normal_sources':len(rows),'normal_events':dict(sum((Counter(r['label']['event_classes']) for r in rows),Counter())),
        'normal_errors':dict(errors),'normal_sources_with_errors':sum(bool(r['errors']) for r in rows),
        'normal_fps':dict(Counter(r['video']['average_rate'] for r in rows if r['video'])),
        'normal_total_seconds':sum(r['video']['stream_duration_seconds'] for r in rows if r['video']),
        'combined_source_count':len(all_rows),'combined_split_counts':dict(Counter(r['split'] for r in split['assignments'])),
        'combined_groups':len(split['groups']),'group_split_counts':dict(Counter(g['split'] for g in split['groups'])),
        'normal_negative_labels_created':0,'training':0,'frames_extracted':0,
        'normal_manifest_sha256':sha256(a.output/'manifest.jsonl'),
        'combined_split_sha256':sha256(a.output/'combined-split-manifest.json'),
        'script_sha256':sha256(__file__),'audit_script_sha256':sha256(Path(__file__).with_name('audit_action_dataset.py'))}
    write_json(a.output/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':main()
