# 다음 작업 — BATCH-0002 비교 종료, 자동 후속 실행 없음

2026-10-29 KST. [종합 결과](experiments/BATCH-0002-summary.md)와 [전달 기록](experiments/BATCH-0002-delivery.md)을 먼저 읽는다. 입력 감사 → RF-DETR Medium 11개 고유 프레임 → Qwen3-VL-4B NF4 16개 view의 사전 고정 비교를 완료했다. 기존 2B 원래 질문 출력과 FCOS 캐시를 재사용했고 신규 가중치는 종류별 한 개다. 실제 CV 사람 대응은 미확정, 4B는 부분 후보 개선과 양성 출력 손실·6개 형식 실패가 공존해 둘 다 기본 적용 보류다. 결합 PoC는 근거 게이트를 충족하지 않아 실행하지 않았다.

- **완료한 실행:** CV 2개 queue 작업/11회 예측, 오류/OOM/retry 0. VLM 17개 job/attempt 중 16개 생성 성공과 v01의 보존된 준비 실패 1개; 논리적 오류 retry는 v01 한 번뿐이다. 모델 로딩 전 오류 복구를 성능 개선 설정으로 세지 않는다. 성공한 결과는 재생성하지 않았다.
- **형식과 행동:** 접근 q02/q03/q05의 유효 여섯 view에서는 잘못된 후보가 4→0이고 q04 C는 유지됐다. q04 B 누락, q03 B/q05 B의 근거 없는 완료 주장, q01/q06 B·C 및 v01/v03의 빈 행동 목록 실패가 남았다. v04 후보는 사라졌지만 세부 행동의 근거를 확정하지 않았다. 파싱 실패를 정상 또는 적절한 판단 유보로 처리하지 않는다.
- **관찰 범위:** q no-crossing 5/attempt-progress 1/primary positive 0, q06은 030 155–160초만 no-person/event. v01 새 관찰은 줄을 넘어 반대편에 서는 행동에 한정하고 과거 완료 미평가는 이력으로 둔다. v03의 바위 올라섬과 이전 옆 틈 시도 기록은 경계 통과 정밀 정답이 아니다. 031의 종료 미완료를 030에 전이하지 않는다.
- **전달:** 새 보고서/metrics/review/binding과 로컬 원본 참고·실제 입력 표시를 기존 완료 CLI/웹에 연결한다. 원격 GitHub byte 확인과 실제 브라우저 보고서·그래프·영상 재생/seek 확인은 각각 전달 기록을 따른다. 원본·프레임·가중치·원시 응답·receipt·DB·환경은 로컬 전용이다.

이번 배치의 고정 비교는 종료했다. 기존 MVP·CV/ByteTrack·원래 질문·ROI·경계와 EXP-0006 기본 보류는 그대로 둔다. 새 모델/프롬프트/해상도/추론을 자동 실행하지 않는다. 다음 별도 검증 후보 한 가지는 **같은 4B와 원래 질문에서 배경 기준 고정 감시 영역 입력 한 축의 효과**를 검토하는 것이다. q04 B/C 차이는 가설의 근거이지 원인 확정이 아니며, v01의 전체 화면 양성 실패가 출발점이다. 정답 사람 위치/사건 시각으로 crop하거나 이 개발 결과를 독립 성능으로 주장하지 않는다. 이 후속 실행은 이번 배치에 포함되지 않는다.

---

# 보존된 실행 전 지침 — BATCH-0002 CV/VLM 대안 검증

2026-10-29. 사용자가 **모델 개선 단계 진행**을 승인했다. 이 문서의 이전 `EXP-0017 종료 / 새 GPU 실행 없음` 지시는 역사적 범위의 종료 기록이며, **이번 명시적 승인 한도에서만** 아래 작업으로 대체한다. [BATCH-0002 고정 상한·평가 계획](experiments/BATCH-0002-model-upgrade-plan.md)을 처음부터 끝까지 읽고, AGENTS/관련 실험 문서와 적용 충돌을 확인한 뒤 진행한다.

## 총괄 실행 순서 (세부 단계 재승인 불필요)

1. **입력 충분성 감사:** q01~q06/v01~v04 + 기존 030/007 문제 장면의 원본과 실제 Qwen processor 입력·PTS·2fps·ROI/resize 정보를 로컬에서 확인. 미저장 q processor RGB는 과거 byte 동등성으로 주장하지 않는다. 입력에 시도 자세가 보이는지 미확정인지를 기록.
2. **CV 새 후보 1개:** FCOS/ByteTrack 과거 실패를 기준으로, 우선 RF-DETR Medium의 공식 오픈 체크포인트·라이선스·의존성을 검토. 소량 사람 검출 프레임(전체 최대240장)을 같은 PTS로 FCOS와 비교. 과거 FCOS 캐시가 동일하지 않으면 고정 FCOS만 재측정. 검출 개수·COCO AP는 SceneGuard 정확도가 아니다. 실제 넘기 순간의 사람 존재·중복·박스 안정성을 우선 점검.
3. **VLM 새 후보 1개:** 우선 Qwen3-VL-4B-Instruct를 공식 카드/라이선스/10GB 양자화 호환성 검증 후, q04/q05 1~2건 smoke → q/v 총10개 5초 개발창의 baseline 대조. 기존 ORIGINAL prompt(실패한 EXP-0017 수정본 아님), 원본 PTS·프레임·평가 기준 고정. 새 모델 4bit와 기존 2B BF16은 양자화도 달라진 비교임을 기록.
4. **결합은 조건부:** CV가 사건 순간 사람 관측을 개선하고 VLM과 상호 보완 근거가 확인될 때만, 저장 결과 중심의 오프라인 통합 PoC **최대 1개**. 조건 불충족 시 결합 **실행하지 않고 보류 결론**으로 종료. CV 검출 성공만을 VLM 호출의 필수 게이트로 삼지 않는다.
5. **독립 검토/배포:** 기존 총괄 Astra max, Sol high 담당(최대2)·Astra high reviewer, native Task/Dispatch, 기존 GPU 단일 queue 및 **여유 VRAM≥6144MiB** 게이트 유지. 정해진 상한 내 CPU 준비 병렬/GPU 직렬. 기존 완료 CLI와 웹 결과 등록, GitHub push·원격/실제 로컬 화면 검증을 별개로 완료. 한 페이지 비교 요약을 제출하고 멈춤.

**범위:** 신규 CV 체크포인트 최대1, 신규 VLM 최대1, 모델당 사전 고정 baseline 1회와 최소 smoke, 결합 PoC 최대1; 별도의 무제한 개선 실행·정답별 프롬프트 튜닝 없음. 신규 학습/파인튜닝/외부 추론 API/유료 결제/새 웹 UI/별도 큐/기존 파일 덮어쓰기는 금지. 새로운 라벨·영상 정답을 AI가 창작하지 않고, 10개 q/v는 개발 자료로서 독립 테스트/F1/FPR을 만들지 않는다. 원본 미디어/모델 가중치/raw inference/runtime은 로컬 전용. 게이트 실패 시 우회하지 않고 미실행 사유·부분 성과·다음 하나의 의사결정을 보고한다.

---

# 다음 작업 — EXP-0017 비교 종료, 자동 후속 실행 없음

2026-10-29 KST. 사용자가 승인한 단일 prompt 개선의 실제 비교를 완료했다. [EXP-0017 결과](experiments/EXP-0017-prompt-evidence-results.md), [실행 기록](experiments/EXP-0017-execution.md), [평가 코드 검증](experiments/EXP-0017-evaluation-notes.md), [전달 기록](experiments/EXP-0017-delivery.md)을 우선한다. EXP-0016은 실행 전 자원 차단 이력이며 그 보고서·binding은 변경하지 않았다.

## 현재 판단

- 기능 실행: 기존 canonical GPU queue에서 4개 job·20개 응답 저장, 오류/OOM/retry 0. 준비된 단일 prompt만 바뀌었으며 새 모델/가중치/설정 튜닝은 없다.
- 평가: q01–q06 기존 사용자 확인과 새 v01–v04 확인을 분리 적용했다. 저장된 131개 입력/결과 파일 검증과 21개 CPU 계약 테스트를 완료했다. 과거 q의 processor RGB/확장 질문은 미저장으로 byte 동등성을 확정할 수 없다.
- 성능: q02/q03/q05 잘못된 후보 감소 실패. q04 C 후보는 유지됐지만 완료 과장, B 누락은 지속. v01 후보 소실·v03 누락·v04 잘못된 후보 지속. **수정 prompt 채택 보류, 기존 구성도 성능 충족 선언 불가.**
- 정답: q no-crossing 5, attempt/progress positive 1, primary positive 0. q06 사람/사건 없음은 030 155–160초에만 해당한다. 031 영상 종료 미완료 관찰을 030에 전이하지 않는다. v01/v03 완료는 미평가, v03은 문 옆 틈의 시도다. v 4창은 2 source group이며 독립 카메라/장소 검증은 부족하다.

## 이후 제안과 종료 기준

추가 개선은 경계 근처 보행/대기와 실제 몸 올림/상대 이동을 구별할 시각 근거가 충분한지 확인하는 별도 계획부터 시작한다. 이번 결과에 맞춘 prompt 재튜닝, 새 입력/모델 비교를 자동 실행하지 않는다. 기존 기본값·CV·EXP-0006 적용 보류는 유지한다. 사람에게 이미 확인받은 q/v 전체를 다시 검수시키지 않는다.

이번 작업은 독립 Astra 검토, 담당3 완료 등록, 실제 보고서·14측정값/2그래프·검토·원본 참고 영상8개 재생/seek, 정상 GitHub push와 원격 byte 검증까지 통과했다. 각각의 receipt와 해시는 전달 기록을 따른다. 승인된 단일 개선 비교를 종료하고 추가 추론/튜닝 없이 멈춘다. 기능 실행·비교 평가 완료가 행동 성능 충족을 뜻하지 않는다.

---

## 보존된 이전 지침 — EXP-0016

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

이번 전달은 local 결과 등록, 실제 브라우저 확인, GitHub 게시와 원격 verify까지 완료했다. 표준 WSL git push에는 인증이 없어 connected GitHub Git Data API의 fast-forward publication을 사용했다. prompt 효과는 여전히 미측정/채택 보류다. 행동 비교를 재개할 때 GPU free memory가 최소 6144 MiB 이상일 때만 새 attempt를 만들고 기존 prompt·manifest·model·queue·한도를 유지한다.

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
