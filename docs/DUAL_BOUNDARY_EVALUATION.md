# 두 경계·출발 이력 평가 준비

2026-11-04. `40f22e7` 기반 별도 평가 worktree에서 평가기와 고정 정의를 준비했다. **후보 규칙 재생은 실행하지 않았다.** 구현 담당자의 고정 revision·code-root·선택 scene key를 코디네이터가 전달한 뒤 별도 실행한다. 이 문서와 `scripts/evaluate_dual_boundary_passage.py`, `tests/test_dual_boundary_evaluation_runner.py`만 평가 담당 소유다. 규칙·구현 시험·HANDOFF·원본·정답·웹 DB는 수정하지 않았다.

작업 시작의 `pending --include-acknowledged` 읽기 전용 조회는 성공했고 요청은 `[]`였다. 기존 검수를 정답으로 승격하거나 새 검수를 등록하지 않았다. 상위 범위는 `docs/DUAL_BOUNDARY_PASSAGE_PLAN.md`를 따른다.

## 고정 비교 기준

BEFORE는 canonical data root의 다음 **선택된 after 자료**다.

- `outputs/validation/continuation-crossing-v1/default-selected-001/after-manifest.json`
- 같은 폴더의 `after-report.json`, `videos/E01_001..045/cards.json`
- 같은 폴더의 `provenance.json`, `summary.json`은 해시로 보호하며 기록 출처로 보존한다.

과거 `repaired-replay.py`의 32/52 BEFORE를 복사하지 않는다. `default-selected-001/provenance.json`에 남은 옛 32/52 baseline 설명도 현재 비교 기준으로 사용하지 않는다. 선택된 카드에서 예측을 다시 추출해 manifest와 정확히 같음을 확인하고, manifest를 평가해 저장된 after-report의 inventory/protocol/modes와 정확히 같은지 검사한다. 이어 확인 TP39·의심 TP51·확인 이른 최초 통지8을 검사한다. 45영상·공식52사건, 006의 미확정1건, 008의 공식 참조 사건을 유지한다.

## 후보 결과를 보기 전 동결한 정의

각 실행은 후보 프로세스 시작 전에 `evaluation-protocol.json`과 SHA256을 저장한다. 프로토콜 ID는 `DUAL-BOUNDARY-SAVED-EVENT-v1`이다. 임계값 최적화·반복 탐색·영상별 시각 예외는 평가기에 없다.

| 항목 | 정의 |
| --- | --- |
| 단위·구간 | 사람/프레임이 아닌 출입구 사건; 원본 PTS의 반열린 `[start,end)` |
| 의심·확인 | 기존 `accuracy_evaluation`을 각각 독립 적용; 실제 근거 시각이 동일 gate의 참조 구간 안에 있어야 매칭 |
| 배정 | 기존 결정적 최대 카디널리티 일대일 매칭; 카드 ID의 전후 동일성을 가정하지 않음 |
| 이득·손실 | 영상+공식 사건 ID+mode별 gained/lost/retained/missed; 매칭에 쓰인 prediction ID도 저장 |
| 최초 알림 | 실제 `notification_intents`와 timeline을 adapter로 대조; 이후 TP가 생겨도 앞선 이른 알림·정상 구간 알림을 삭제하지 않음 |
| 시각 | 최초 매칭 근거와 해당 카드 최초 통지를 별도 표시; 물리적 행동 시작 지연으로 해석하지 않음 |
| 정상 구간 | 기존 `verified_non_event_intervals`만 음성 정답; 나머지 시간은 미검수 |
| 전체 precision/F1 | 미검수 예측이 있으면 null; 제한된 참조 사건 재현율을 전체 행동 정확도로 표현하지 않음 |
| 006 | 시간 미확정1건은 공식52와 별도 유지; 임의 시간/사건을 만들지 않음 |
| 008 | 공식 참조는 유지하고 의미 검수 보류도 유지 |
| 010 | 공식 시각과 사용자 등반 시작 약63초를 별도 보고; 약63초를 새 정밀 정답으로 쓰지 않음 |
| 누락/불확실성 | 원본 후보·evidence partition 불일치는 adapter 오류; 미확인 seed/evidence와 원래 이유/binding을 보존하며 출발·연결 누락을 추정으로 메우지 않음 |
| subset | 선택 영상만 따로 평가하고 full45/official52 집계로 표시하지 않음; BEFORE 전체45 검증은 먼저 수행 |
| 실패 | 후보 오류가 있으면 전체 성공 집계를 만들지 않고 provenance/errors·로컬 stderr를 남김 |

안→밖 우선 목록은 013·015·021·028·034·036·043·044·045다. 이는 기존 토의의 방향 문맥이며 새 사람별 방향 정답이 아니다. 028의 공식 종료 뒤 확인, 036의 전반 누락과 후반 별도 사건, 045의 동시 양방향 혼합 문맥을 따로 표시한다. 전체 누락은 우선 목록 밖도 포함한다.

## 재현 명령과 입력 인터페이스

기존 canonical `.venv-cv-batch02/bin/python`을 사용한다. 기본 mode는 `prepare`이며 후보 pipeline을 호출하지 않는다. `--videos`를 생략하면 전체45다. output은 `data-root/outputs/validation/dual-boundary-passage-v1/` 아래의 **존재하지 않는 새 디렉터리**여야 한다. 재사용·덮어쓰기·symlink 출력은 거절한다.

```bash
/home/jhc7484/dev/sceneguard-ai/.venv-cv-batch02/bin/python \
  scripts/evaluate_dual_boundary_passage.py \
  --data-root /home/jhc7484/dev/sceneguard-ai \
  --code-root /home/jhc7484/dev/sceneguard-ai/sg-dual-boundary-eval \
  --output /home/jhc7484/dev/sceneguard-ai/outputs/validation/dual-boundary-passage-v1/preparation-001

/home/jhc7484/dev/sceneguard-ai/.venv-cv-batch02/bin/python \
  -m unittest tests.test_dual_boundary_evaluation_runner -v
```

후보 실행에는 코디네이터가 준 실제 Git commit을 `--implementation-revision`, 실제 구현 checkout을 `--code-root`, 확정한 선택 scene key를 `--scene-key`로 추가하고 `--mode replay`를 지정한다. `--videos 10 13 15 21 28 34 36 43 44 45`는 subset이고, 생략하면 full45다. CPU workers는 1/2/4 중 선택하며 기본4다. 코디네이터 인터페이스 전달 전 후보 실행은 금지한다.

현재 제안한 인터페이스는 `scene[KEY] = draft_normalized`다. 평가기가 canonical `outputs/region-revisions/inside-boundary-draft-20261104-v1/draft-manifest.json`의 카메라별 polyline을 새 output `profiles/Cn-scene.json`에 넣는다. 원래 scene의 `line`·zones와 portal은 보존하고, portal도 새 프로필 폴더에 바이트 복사한다. C5의 꺾인5정점을 직선으로 단순화하지 않는다. `profile-manifest.json`이 exact polyline/원래 geometry 경로/새 profile 경로/key를 묶는다. scene key에 다른 구조가 필요하면 후보 결과를 보기 전에 코디네이터를 통해 계약을 수정한다. 초안 manifest의 과거 pending/applied 상태를 덮어쓰지 않으며, 이번 구현 승인 출처는 상위 계획이다.

저장 측정값은 C5의014·016·018·020·021·038에 `mvp-c5-v1`, 나머지에 `mvp-all-v3`의 원래 `attempt-1` analysis와 frame-evidence를 사용한다. `make_bundle`와 `analyze_observations`에 이 자료와 새 geometry만 전달한다. 기존 request/scene/portal/registry를 수정하지 않는다. 모델/GPU/검출/추적/flow/영상 디코딩 호출 경로는 없다. 새 CPU 규칙 판정과 과거 카드 기준 재평가이며 새 추론이 아니다.

## 출처·보존 검증과 산출물

`sceneguard/**/*.py`와 adapter를 code snapshot에 복사하고 runner 자체도 별도 바이트로 포함한다. replay에서는 package 파일 목록과 각 파일·adapter가 확정 commit의 바이트와 같은지 검사한다. runner는 평가 worktree에서 가져오며 별도 SHA256으로 묶이므로 구현 commit에 runner가 아직 없어도 된다. 각 worker는 `python -I` 새 프로세스에서 snapshot 경로만 명시적으로 import하고 모든 로드된 `sceneguard` 모듈 경로를 검사한다. 설치된 패키지나 canonical root의 옛 코드가 끼면 실패한다.

입력 해시는 전체45의 request/analysis/frame-evidence/선택 BEFORE cards, 참조된 scene/portal/registry, BEFORE manifest/report/summary/provenance, 경계 초안 manifest를 실행 전후 대조한다. request의 geometry 해시와 선택 baseline provenance의 저장 측정값 해시도 검사한다. 새 profile을 실행 전후 보호하고 원래 geometry JSON은 별도 `archived_geometry_snapshot`에도 보존한다. 원본 영상은 열거나 재해시하지 않으며 manifest와 request에 저장된 원본 영상 해시가 같은지만 대조한다. 원본 영상·공식 라벨 파일·DB·영수증을 직접 열거나 쓰지 않으며, 동결 manifest의 참조 정답만 읽는다. 따라서 전체 원본 미디어 재감사를 했다고 주장하지 않는다.

| 파일 | 내용 |
| --- | --- |
| `evaluation-protocol.json` | 결과 확인 전 고정한 정의 |
| `code_snapshot/`, `archived_geometry_snapshot/` | 실제 코드와 원래 geometry JSON |
| `before-manifest.json`, `before-report.json`, `before-audit.json` | 정확한 선택 baseline과 재계산·전체 누락·통지 감사 |
| `execution-plan.json`, `profiles/`, `jobs/` | replay에만 생성하는 고정 코드/geometry/작업 입력과 로컬 stdout/stderr |
| `videos/E01_nnn/*.json` | pipeline의 모든 반환 항목, 예측, 미확인 seed/evidence, CPU·import 출처 |
| `after-manifest.json`, `after-report.json` | 성공한 후보의 선택 영상 범위 평가 |
| `comparison.json` | 모든 사건 전후 매칭/이득/손실, 전체 최초 통지, 이른 통지,010 별도 비교, 우선9영상, 남은 전체 확인 누락 |
| `per-video-runtime.json`, `summary.json` | 성공 영상별 wall/process CPU 시간, 전체 또는 subset 집계 |
| `provenance.json` | 실제 코드 revision/해시, 보호 입력, 전체 실행 wall/parent CPU 시간, worker CPU 합, 오류·보존·완료 상태 |

최종 산출물 유효성은 `provenance.status`와 보호 입력/코드/snapshot 불변 검사까지 함께 확인한다. 도중 실패로 남은 부분 결과·summary를 완료 결과로 읽지 않는다. worker CPU 합과 전체 wall 시간은 서로 다른 측정이며 실시간 처리속도나 GPU 시간으로 표현하지 않는다. 준비 실행의 baseline self-comparison에 있는 `after`는 **동일 baseline 자체**이며 후보 결과가 아니다. 원시 측정·snapshot·로컬 경로 포함 JSON은 ignored outputs에만 두고 Git에는 넣지 않는다.

## 준비 검증 결과

canonical 실제 자료의 `preparation-001`은 11.434초 wall / 11.073초 parent CPU로 끝났다. 보호 입력204개와 소스/snapshot 불변 검사를 통과했다. candidate_replay_executed는 false다. 이 준비 출력은 이후 runner 보완 전의 첫 실행 바이트를 snapshot으로 보존한다. 최종 runner의 `preparation-003`은 10.145초 wall / 9.884초 parent CPU로 성공했고, 입력204개·원래 geometry snapshot19개·코드/snapshot이 보존됐다. 오류는0개이며 후보 재생은 false다. `preparation-002`도 후보 없는 중간 준비 검증으로 보존했다.

| 기준 지표 | 의심 | 자동 확인 |
| --- | ---: | ---: |
| TP/FP/FN | 51/10/1 | 39/1/13 |
| 중복 FP | 9 | 1 |
| 미검수 예측 | 58 | 9 |
| 최초 통지 | 112 | 49 |
| 매칭 사건의 이른 최초 통지 | 29 | 8 |
| 검수된 정상62.133333초의 최초 오알림 | 3 | 0 |

확인 이른8건은010(59.933333),011(64.433333),016(60.866667),029(132.166667),030(71.633333),032(25.166667),038(4.333333),041(58.366667)초다. 이는 공식 참조 구간보다 앞선 **최초 통지**다. 뒤의 TP가 이 기록을 없애지 않는다. 010의 첫 매칭 근거는62.133333초, 최초 확인은59.933333초다. 최초 확인은 공식 시작62.066667초보다2.133333초 앞서고, 사용자 관찰 약63초보다 약3.066667초 앞선다.

기준의 전체 확인 누락13건은 아래와 같다. 공식 ID·원래 순서는 유지한다.

| 영상 | 공식 사건 | `[start,end)` 초 |
| --- | --- | --- |
| 013 | official-row-000 | [60.6,66.066667) |
| 015 | official-row-000 | [49.866667,69.633333) |
| 021 | official-row-000 | [64.233333,78.666667) |
| 026 | official-row-000 | [63.633333,70.266667) |
| 028 | official-row-000 | [44.7,69.233333) |
| 034 | official-row-000 | [26.633333,66.7) |
| 035 | official-row-000 | [0.033333,2.3) |
| 035 | official-row-001 | [60.6,63.533333) |
| 036 | official-row-001 | [16.666667,32.6) |
| 042 | official-row-000 | [69.166667,78.466667) |
| 043 | official-row-000 | [63.633333,72.066667) |
| 044 | official-row-000 | [59.433333,79.266667) |
| 045 | official-row-001 | [9.0,14.433333) |

현재 focused runner fixture17개가 통과했다. 이른 통지 보존·사건별 손실/이득·전체 누락·미검수 알림·정답 변조 거절·006/008 보존·옛 report 거절·카드 누락·미확인 출발/연결 보존·새 C5 프로필·소스 변경 탐지·확정 commit 파일 누락 거절·격리 import·worker 성공/실패 산출물을 검사한다. pipeline 호출 시험은 stub fixture이며 실제 후보 행동 개선을 측정한 것이 아니다. 후보 실행·실제 행동 비교·독립 검토·기본 채택은 아직 미완료다.

최종 준비 실행의 runner SHA256은 `c2d86d3ca9fedc50b8452b1b70225326bb605e443b88a2408b4eb6b3665af9fc`, 고정 protocol SHA256은 `7e528b56577899818f933e3aecd7bee6b3748c76578e1061b3f445fbdf642d7d`다. `preparation-003/code_snapshot`의 runner와 현재 파일이 일치함을 확인했다. 후보 revision/key는 아직 전달받지 않았으므로 이 커밋은 준비 완료만 뜻한다.
