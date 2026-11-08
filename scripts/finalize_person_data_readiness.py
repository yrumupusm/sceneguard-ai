"""Record bounded visual observations and conservative review-only split proposal."""
from collections import Counter, defaultdict
import argparse
import csv
import json
from pathlib import Path

from audit_person_data_readiness import ROOT, AUG, OLD, read, rows, save, sha

OUT = ROOT / 'outputs/model-comparison/exp0070/data-readiness-v1'

# Observations from the actual six-point contact sheets, plus full-resolution
# P15/P27 and waterfront images. They are NOT complete-frame human GT.
OBS = {
'P01': ('월담·철제 울타리 가림·뒤에서 서 있는 사람', '56–63.667초 월담 자세와 뒤쪽 인물. 0–8초에도 태양광 구조물 뒤 다리가 보여 빈 배경으로 쓰면 안 됨.', ['wall_pose','occlusion','standing_context']),
'P02': ('야간·작은 사람·텐트 가림', '108–116초 텐트 뒤/옆 작업 인물. 0–8초에도 사람이 있음. 단순 정상 대기로 분류하지 않음.', ['small','occlusion','night']),
'P03': ('원거리 사람·낮은 자세·잔디 배경', '68–75.667초 텐트 옆 인물. 0/4/8초는 빈 배경 검수 후보이나 먼 배경까지 전체 프레임 확인 필요.', ['small','low_pose','empty_candidate']),
'P04': ('나무·현수막 가림·정지 자세', '85–93초 현수막 작업 중 인물과 서 있는 인물. 정상 대기 의미는 미확정. 0–8초는 빈 배경 검수 후보.', ['occlusion','standing_context','empty_candidate']),
'P05': ('보행·굽힌 자세·쓰레기통 배경', '54–62초 물건을 다루다 걸어 나감. 특히 60–62초 이후 보행을 별도 주석할 가치가 있음. 0–8초 빈 배경 후보.', ['walking_context','low_pose','empty_candidate']),
'P06': ('작은 웅크린 사람·해안 배경', '73–81초 웅크린 사람. central-park 메타데이터지만 P08/P12와 같은 해안 시설이 보여 장소 분리 근거를 보류.', ['small','low_pose','location_conflict','empty_candidate']),
'P07': ('앉은 사람과 보행 인물·나무 광장', '21–28.667초 서 있는/이동하는 사람과 벤치 인물. 0–8초에도 벤치 인물이 있어 빈 배경 아님.', ['walking_context','sitting','bystander']),
'P08': ('서 있는 사람·해안 배경', '69–76.667초 서 있는 사람. daesin-park 메타데이터와 P06/P12의 동일 해안 배경 의심.', ['standing_context','location_conflict','empty_candidate']),
'P09': ('보행·서 있는 인물·인물 간 가림', '25–32.667초 여러 인물의 통행과 전단지 전달. 0–8초 빈 배경 후보. 정상 보행인과 작업 인물 구분 필요.', ['walking_context','standing_context','occlusion','empty_candidate']),
'P10': ('보행·몸 굽힘·화면 경계 잘림', '11.667–19.333초 여러 인물, 몸 굽힘과 화면 밖으로 잘린 사람. 0–8초 빈 배경 후보.', ['walking_context','low_pose','truncation','empty_candidate']),
'P11': ('보행·인물 간 가림·큰 사람', '14–22초 물건을 다루는 사람과 다른 보행인. 가까운 사람의 잘림·중첩 포함. 0–8초 빈 배경 후보.', ['walking_context','occlusion','truncation','empty_candidate']),
'P12': ('해안의 서 있는 사람·낚시 자세', '12–20초 두 인물. 0–8초에도 사람이 있음. P06/P08과 같은 해안으로 보여 3장소/3독립 사건으로 세지 않음.', ['standing_context','location_conflict']),
'P13': ('아주 작은 사람·먼 현수막·무대 배경', '134–142초 오른쪽 먼 곳의 작업 인물. 0–8초도 먼 배경까지 확인해야 빈 배경 여부를 판단할 수 있음.', ['small','occlusion','empty_candidate']),
'P14': ('나무 뒤 가림·현수막 작업', '13.667–21.333초 나무 앞뒤 사람. 시작부터 사람이 있어 빈 배경 아님. 좌측 텐트와 먼 통행인도 라벨 범위에 포함.', ['occlusion','standing_context','bystander']),
'P15': ('작은 사람·나무/현수막 가림·역광', '178.333초 원본 확대에서 나무 뒤 사람이 보임. 축소 모음에서는 비어 보일 수 있어 빈 배경으로 판정 금지.', ['small','occlusion','backlight']),
'P16': ('매우 작은 원거리 보행인', '21–28.667초 상단 먼 경로의 작은 인물. 0–8초에도 먼 인물 가능성이 있어 빈 배경 검수에서 제외.', ['small','walking_context']),
'P17': ('먼 곳에서 접근하는 보행인', '51.333–59초 보행인의 크기가 변함. 0–8초에도 화면 진입 인물이 있음. P16과 같은 배경·촬영일로 함께 묶음.', ['small','walking_context','scale_change']),
'P18': ('정상 서 있기·주변 보행', '19.333–27초 세 인물이 서 있는 문맥. 이번 구간은 미검수. 같은 원본의 53–61초 25프레임/74박스만 기존 검수 재사용.', ['standing_context','walking_context']),
'P19': ('월담·철제 울타리 가림', '53.667–61.333초 월담. P01과 같은 태양광 울타리·같은 촬영일이므로 신규 학습 후보에서 보류. 시작부터 사람 있음.', ['wall_pose','occlusion','cross_split_scene_hold']),
'P20': ('작은 월담 인물·기둥/울타리 가림', '95.333–103초 먼 울타리에서 넘어오는 인물과 동행자. 배경의 작은 사람까지 포함 필요. P21과 같은 배경·날짜 묶음.', ['small','wall_pose','occlusion','bystander']),
'P21': ('월담 자세·기둥 가림·여러 사람', '92–100초 새 구간은 미검수. 같은 원본의 33–41초 25프레임/77박스만 기존 검수 재사용.', ['wall_pose','occlusion','bystander','empty_candidate']),
'P22': ('야간·텐트 가림·낮은 자세', '130–138초 사람. P02와 같은 잔디/카메라 배경·촬영일이므로 신규 학습 후보에서 보류. 0–8초는 빈 배경 검수 후보.', ['small','occlusion','night','cross_split_scene_hold','empty_candidate']),
'P23': ('야간·나무 가림·현수막 인물', '131–138.667초 어두운 인물과 나무/현수막 가림. 0–8초는 어둡고 빈 배경 여부 추가 확인 필요.', ['small','occlusion','night','empty_candidate']),
'P24': ('새벽·작은 사람·현수막 가림', '150–158초 현수막/나무 근처 인물. 0–8초 빈 배경 후보. P04와 같은 메타 장소/일자이나 다른 배경이므로 독립 촬영 확인 필요.', ['small','occlusion','low_light','empty_candidate']),
'P25': ('보행·몸 굽힘·쓰레기통 가림', '16–23.667초 달리거나 이동하고 몸을 굽힘. stand 선언을 정상 대기로 채택하지 않음. 0–8초 빈 배경 후보.', ['walking_context','low_pose','occlusion','semantic_conflict','empty_candidate']),
'P26': ('월담·계단 난간 가림', '17.333–25초 높은 목재 난간을 넘는 인물. 0–8초 빈 배경 후보. P27/P28과 같은 배경·촬영일로 묶음.', ['wall_pose','occlusion','empty_candidate']),
'P27': ('월담·행동 라벨 불일치', '73.667초 stand 박스 대상이 난간을 넘는 자세. 정상 대기 정답으로 사용 금지. 사람 박스용으로도 동행자 누락 검수 필요.', ['wall_pose','occlusion','semantic_conflict','empty_candidate']),
'P28': ('야간 월담·목재 난간 가림', '17.333–25초 야간 월담. 0–8초 빈 배경 후보. P26/P27과 같은 배경·촬영일이므로 별도 사건 수로 늘리지 않음.', ['wall_pose','occlusion','night','empty_candidate']),
'P29': ('야간 앉은 인물·조명 변화', '116–120.333초 앉은 사람. 시작부터 앉아 있어 빈 배경 아님. 앉기 편중 확대 목적이 아니라 야간 검출 유지 대조용.', ['sitting','night']),
}


def main():
    plan=read(OUT/'candidate-plan-before-decode.json');cases={r['candidate_id']:r for r in plan['cases']}
    checks={r['candidate_id']:r for r in read(OUT/'source-checks.json')['results']}
    groups={r['group_id'] for r in cases.values()};parent={g:g for g in groups}
    def find(g):
        while parent[g]!=g:
            parent[g]=parent[parent[g]];g=parent[g]
        return g
    merges=[(['P01','P19'],'same solar-fence scene and capture date; reserve development'),
            (['P02','P22'],'same night-tent scene and capture date; reserve development'),
            (['P06','P08','P12'],'same waterfront landmarks/date despite inconsistent location metadata'),
            (['P16','P17'],'same path scene/date; not independent capture evidence'),
            (['P20','P21'],'same canopy/fence scene/date; conservative capture-session reservation'),
            (['P26','P27','P28'],'same staircase/wood fence/date; conservative capture-session reservation')]
    for ids,reason in merges:
        roots=sorted({find(cases[i]['group_id']) for i in ids})
        for g in roots[1:]:parent[g]=roots[0]
    comps=defaultdict(list)
    for cid,r in cases.items():comps[find(r['group_id'])].append(cid)
    mapping={};components=[]
    for index,(_,ids) in enumerate(sorted(comps.items(),key=lambda kv:min(kv[1])),1):
        key=f'capture-reservation-{index:02d}'
        parts={cases[c]['proposal_split'] for c in ids}
        part='development' if 'development' in parts else next(iter(parts))
        assert not ('new_test' in parts and len(parts)>1)
        for c in ids:mapping[c]=(key,part)
        components.append(dict(reservation_id=key,candidates=sorted(ids),reserved_split=part,
            original_group_ids=sorted({cases[c]['group_id'] for c in ids}),
            event_independence_certified=False,location_metadata_verified=False))
    finalized=[]
    for cid,r in cases.items():
        reason,observation,tags=OBS[cid];reservation,part=mapping[cid]
        disposition='review_candidate'
        if r['proposal_split']!=part:disposition='hold_training_to_preserve_development_scene'
        if cid in ['P06','P08','P12']:disposition='hold_location_and_capture_identity'
        if checks[cid]['status'].startswith('hold'):disposition='hold_content_similarity'
        finalized.append(dict(candidate_id=cid,source_id=r['source_id'],original_filename=r['original_filename'],
            metadata_location=r['location'],date_captured=r['date_captured'],
            original_group_id=r['group_id'],capture_reservation=reservation,
            original_proposal_split=r['proposal_split'],reserved_split=part,disposition=disposition,
            selection_reason=reason,visual_observation=observation,condition_tags=tags,
            visual_review_scope='six source snapshots; P15/P27 and waterfront additionally full-resolution; not frame-complete GT',
            person_labels_complete_for_new_windows=False,action_truth_verified=False,training_eligible=False,
            proposed_windows=checks[cid]['windows'],source_sha256=checks[cid]['source_sha256'],
            label_sha256=r['label_sha256'],h640_annotation_p10=r['label_geometry']['h640_p10'],
            additional_review='전 프레임의 모든 사람 박스, 원본 PTS/프레임 정렬, 가림 범위, 정상행동 의미, 촬영 사건·멀티카메라 연결',
            review_priority='P0' if cid in ['P06','P08','P12','P19','P22','P25','P27'] else 'P1',
            source_reference=r['resolved']['source_reference'],label_reference=r['resolved']['label_reference']))
    group_to_reservation={g:(c['reservation_id'],c['reserved_split']) for c in components for g in c['original_group_ids']}
    closure=[]
    for r in plan['closure_members']:
        key,part=group_to_reservation[r['group_id']]
        closure.append(dict(**r,capture_reservation=key,reserved_split=part,
            eligible_for_reserved_split=False,
            reservation_note='Reservation only. Existing training/validation/test assignments remain unchanged; old train never becomes development GT.'))
    reviews=read(ROOT/'outputs/model-comparison/exp0067/confirmed-person-v1/manifest.json')
    reused=[]
    for case in (1,3,5):
        fs=[f for f in reviews['frames'] if f['case_number']==case]
        reused.append(dict(case_number=case,split=fs[0]['split'],frames=len(fs),
            boxes=sum(len(f['confirmed_person_boxes']) for f in fs),source_sha256=fs[0]['source_sha256'],
            pts_range=[min(f['source_pts'] for f in fs),max(f['source_pts'] for f in fs)],
            request_id=fs[0]['request_id'],answer_version=fs[0]['answer_version'],
            reuse_scope='exact reviewed frames only; no repeat question',
            scope_complete_person_boxes=True,new_dataset_release=False,
            new_cohort_note='case5 remains legacy diagnostic development; EXP65 similarity hold requires capture/duplicate resolution before cohort expansion' if case==5 else 'training only'))
    save(OUT/'review-reuse.json',dict(EXP0067=reused,
        EXP0066_cases_2_4_6='Reuse prior no-missing-visible-person answers for their exact displayed windows; coordinate/frame-origin certification not implied; not silently merged with EXP67.'))
    save(OUT/'visual-observations.json',dict(observer='assistant source-image inspection',cases=finalized,conservative_merges=merges))
    save(OUT/'split-proposal.json',dict(status='review_only_not_training_release',
        camera_identity_verified=False,independent_event_count_certified=None,
        captures=components,closure_members=closure,cases=finalized,
        protected_school45=True,protected_exp0064_test_originals=296,protected_test_closure_members=327,
        old_splits_rewritten=False,training_executed=False))
    with (OUT/'candidate-review-list.csv').open('x',newline='') as f:
        cols=['candidate_id','original_filename','metadata_location','date_captured','capture_reservation','reserved_split',
              'disposition','selection_reason','visual_observation','person_labels_complete_for_new_windows','h640_annotation_p10','review_priority']
        writer=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore');writer.writeheader();writer.writerows(finalized)
    # Data-level checks: no accidental release, protected closure or label drift.
    original_inventory={r['source_id']:r for r in rows(OUT/'source-inventory.jsonl')}
    assert all(original_inventory[r['source_id']]['proposed_partition'] not in
               {'protected_exp0064_test','protected45','excluded_user_scenario'} for r in closure)
    # Existing label-error siblings remain in the reservation graph to prevent
    # leakage, but cannot be selected as label-ready candidate sources.
    assert all(original_inventory[r['source_id']]['proposed_partition'] != 'quarantine' for r in finalized)
    quarantine_siblings=[r['source_id'] for r in closure if original_inventory[r['source_id']]['proposed_partition']=='quarantine']
    assert len({r['source_id'] for r in finalized})==len(finalized)
    assert not any(r['training_eligible'] for r in finalized)
    for key in ('source_sha256','capture_reservation'):
        scopes=defaultdict(set)
        for r in finalized:
            if r['disposition']=='review_candidate':scopes[r[key]].add(r['reserved_split'])
        assert all(len(s)==1 for s in scopes.values()),key
    bindings=read(OUT/'input-bindings.json')
    assert all(sha(ROOT/p)==h for p,h in bindings.items())
    audit=dict(candidate_count=len(finalized),reservation_count=len(components),closure_members=len(closure),
        review_candidate_counts=dict(Counter(r['reserved_split'] for r in finalized if r['disposition']=='review_candidate')),
        held_counts=dict(Counter(r['disposition'] for r in finalized if r['disposition']!='review_candidate')),
        reserved_counts=dict(Counter(c['reserved_split'] for c in components)),
        inputs_preserved=True,protected_or_user_excluded_closure_members=0,
        quarantined_siblings_reserved_but_not_selected=quarantine_siblings,cross_split_source_hashes=0,
        cross_split_active_capture_reservations=0,complete_new_person_label_windows=0,
        fresh_wall_pose_test_windows=0,action_semantic_truth_certified=False,
        all_candidate_native_fps=[3],source_decode_frames=sum(w['frames'] for c in checks.values() for w in c['windows']),
        source_content_check_bytes=sum(c['source_size_bytes'] for c in checks.values()),
        gpu_inference=0,training=0)
    save(OUT/'final-audit.json',audit)
    report_rows=[]
    for r in finalized:
        w=r['proposed_windows'][0]['actual_pts'];part={'train':'학습','development':'개발','new_test':'새 시험'}[r['reserved_split']]
        if r['disposition']!='review_candidate':part+=' **보류**'
        report_rows.append(f'| {r["candidate_id"]} | {part} | `{r["original_filename"]}` | {w[0]:.3f}–{w[-1]:.3f}초 | {r["selection_reason"]} | {r["visual_observation"]} |')
    (OUT/'candidate-table.md').write_text('| ID | 제안 | 원본 파일 | 주 구간 원본 PTS | 선정 이유 | 실제 관찰과 검수 범위 |\n|---|---|---|---|---|---|\n'+'\n'.join(report_rows)+'\n')
    # Clarify conservative holds in the already generated local viewer.
    page=OUT/'index.html';text=page.read_text().replace('ラベル draft','라벨 초안')
    notice='<p style="color:#ffcc66">최종 분할 보완: P19/P22는 개발 배경과 겹쳐 신규 학습 보류. P06/P08/P12는 장소 기록 충돌로 새 시험 보류. P27의 stand는 실제 월담 자세여서 정상 정답으로 쓰지 않습니다. 모든 새 구간의 완전한 사람 박스는 아직 미검수입니다.</p>'
    text=text.replace('<h1>데이터 보강 후보 — 검수 전 / 학습 불가</h1>','<h1>데이터 보강 후보 — 검수 전 / 학습 불가</h1>'+notice)
    page.write_text(text)
    print(json.dumps(audit,ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--folder',type=Path,default=OUT)
    args=parser.parse_args()
    OUT=args.folder.resolve()
    main()
