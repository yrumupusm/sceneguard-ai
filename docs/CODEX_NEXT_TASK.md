# 다음 작업 — EXP-0016 단일 프롬프트 개선 비교 마무리

2026-10-28. 이 범위는 사용자가 승인했다. 작은 단계별 재승인을 요청하지 않는다. 작업 단위는 담당 배정 → 준비/실행 → 기록 → 독립 검토 → 기존 결과 화면 등록 → GitHub 게시와 실제 화면 확인까지다.

## 목표와 현재 상태

EXP-0015에서 사용자 확인한 q02/q03/q05 접근/비사건 장면의 false candidate를 줄이면서 q04 시도/진행 후보를 보존할 수 있는지, **Qwen 공통 prompt 하나만 수정**해 비교한다. 근거와 가설/한계는 [ADR-0017](decisions/ADR-0017-qwen-temporal-evidence-prompt.md), 실험 고정값과 결과는 [EXP-0016](experiments/EXP-0016-prompt-evidence-rubric.md)에 둔다.

- 완료된 준비: 실패 근거 검토, revised prompt, fixed q01–q06 두-view queue phase, CPU tests, 사용자 추가 v01–v04 라벨 수집.
- 현재 확인: 실행 담당 Sol high Task `task_305549d14771` / Dispatch `ctx_65256d02af82`가 2026-10-28 14:36 UTC에 RTX 3080 8464 MiB used / 1590 MiB free / 99% utilization을 측정하고 6144 MiB 최소 gate에서 중단했다.
- 실행 여부: canonical GPU queue에 EXP-0016 job/attempt 0개, Qwen 추론·model load 없음. 아래 모든 model outcome/cost는 미측정이다. Dispatch `failed`는 GPU 부족으로 인한 계획된 차단이며 추론 오류/OOM이 아니다.
- 별도 표본: E01_004 60–65초(v01 attempt/progress, completion not assessed), E01_004 0–5초(v02 non-event), E01_021 65–70초(v03 attempt/progress at adjacent gap, boundary relation ambiguous and completion not assessed), E01_021 0–5초(v04 non-event). 원본 source frame만 모델에 입력하고 prompt 기준/라벨/official timestamps는 전달하지 않는다. 기존 full-frame prompt와 revised prompt를 같은 입력으로 비교할 준비 중이다. E01_004/E01_021에 calibrated ROI가 없으므로 full-frame 하나만 쓴다.

## 현재 완료 상태

단일 공통 prompt 변경 코드, fixed q01–q06 및 v01–v04 경로와 CPU 검증은 구현됐다. `.venv-vlm`의 107 MVP tests와 `.venv-orca-lab`의 14 queue tests가 통과했다. 그러나 실행 담당 GPU 사전검사는 RTX 3080에서 1590 MiB free로 기존 6144 MiB gate를 통과하지 못했다. canonical queue는 EXP-0016 job/attempt 0, model load/inference 0이다. Astra는 blocked-before-inference 기록과 현재 report/metrics hash binding을 PASS했으나 행동 결과를 검토한 것은 아니다. 로컬 결과는 `inconclusive / blocked / adoption_on_hold`로 등록됐다. 기존 로컬 웹 화면에서 담당 slot3 카드, 보고서, 2개 그래프, review와 네 개 사용자 검수 원본 참고 영상의 재생/seek를 확인했다. 실제 행동 비교·비용·prompt 효과는 미측정이며 자동 채택하지 않는다.

마지막 미완료 단계는 GitHub 게시/원격 검증이다. 이후 실행은 GPU free memory가 최소 6144 MiB 이상일 때만 새 attempt로 재개하며, 기존 prompt·manifest·model·queue·한도를 유지한다.

## 순서

1. 현재 담당 Sol high가 수정한 four-window independent comparison phase와 tests를 총괄이 검토한다. 라벨 비유입, source/window/prompt hash, canonical Run/queue gate, 새 output 경로를 확인한다.
2. 최초 q six-window phase의 tests/code도 검토하고 q labels/EXP-0015 outputs가 바뀌지 않았음을 확인한다. 지원 환경 `.venv-vlm`에서 `tests_mvp`와 queue suite를 실행한다.
3. 코드/spec/docs를 먼저 커밋해 exact source hash를 고정한다. 기존 Run `run_3d23462a014a`와 canonical queue만 사용한다. 실효 담당모델/effort와 실제 card 진행을 확인한다.
4. 실행 직전 GPU free memory≥6144 MiB를 확인한다. 미달이면 실행/모델 load/enqueue를 보류하고, threshold 조정이나 queue 우회/다른 process 종료를 하지 않는다. 자원이 확보되면 q B/C revised prompt와 independent full-frame baseline/revised prompt를 등록된 작업 한도 안에서 직렬 실행한다. job 오류 재시도는 최대1회.
5. 실제 GPU output만으로 q01–q06의 사용자 라벨·기존 B/C·새 B/C·변화·불확실성을 비교한다. 독립 v01–v04에서는 action class와 completion, v03 boundary-location ambiguity를 분리해 본다. 모든 candidate를 제거/indeterminate로 바꾼 결과는 개선으로 보지 않는다. 정밀 정확도/F1/FPR/시간당 false alarms는 산출하지 않는다.
6. 코드, logs binding, report, null-safe metrics를 독립 Astra high에게 검토시킨다. 총괄은 exact report/metrics SHA review 후 기존 `orchestration.complete` 절차로 결과를 등록한다. 점수 성능이 개선되지 않거나 q04를 잃으면 기본 변경 채택 보류.
7. 코드/문서/공개 가능한 요약만 push한다. GitHub remote/ref/파일 해시와 실제 local page/service/browser 반영을 별도로 확인한다. 영상·이미지·weights/raw response/cache/runtime DB/receipts는 GitHub에 올리지 않는다.

## 완료 판단을 나눌 것

- **기능/테스트:** 코드, fixed-conditions, PTS/hash/queue tests가 통과했는가.
- **실행:** GPU queue/attempt, 실제 모델 호출, 메모리/생성 비용이 확인됐는가.
- **행동 성능:** q04 유지와 q02/q03/q05 감소가 동시에 있었는가, 독립 표본에서 behavior evidence가 유효했는가.
- **독립 검토:** Astra가 report/metrics의 고정 byte hashes와 해석을 확인했는가.
- **배포/전달:** 기존 페이지의 result/card/review 등록과 GitHub 게시를 각각 실제로 확인했는가.

필수 요약 상태/최신 사용자 라벨은 [MVP-0001 summary](experiments/MVP-0001-summary.md)를 따른다. q06의 no person/event는 E01_030 155–160초에만 해당하며, E01_031 종료 전 행동 관찰을 E01_030으로 전이하지 않는다. EXP-0014 과거 상태와 모든 원본/기존 결과는 보존한다.
