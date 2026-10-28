# 실험 작업의 배정부터 화면 확인까지

2026-10-28 사용자 운영 지시. 앞으로 승인된 실험 하나의 완료 범위는 **담당 배정 → 실행 → 보고서·측정값 저장 → 총괄 검토 → 등록 → GitHub 게시 확인과 로컬 화면 확인**이다. 구현 완료, 실험 실행 완료, 결과 등록, GitHub 게시, 브라우저 확인을 서로 대신하지 않는다. 이 절차 자체는 새 모델 실험 실행 승인이 아니다.

## 상태와 책임

총괄은 실제 Orca Task/Dispatch 생성 후 담당 카드와 experiment_id를 연결한다. Orca가 작업 생명주기의 원본이다. 카드의 작업 진행/종료는 같은 Run/Task/Dispatch의 최근 native 관측으로 표시한다. 관측이 오래되거나 연결이 없으면 미확인이다. 작업자 종료는 GPU 실험 성공이나 검토 통과를 뜻하지 않는다.

작업자는 자기 보고서, 공개 가능한 metrics.json, 로컬 artifact 목록과 실행 결과를 제출한다. 공식 라벨/기존 출력은 보존한다. 총괄은 원문과 측정치를 확인하고 별도 검토문에 검토한 두 SHA256과 판정을 남긴다. 총괄만 공통 등록 명령을 실행한다. worker_done만으로 자동 승인하거나 새 실험을 시작하지 않는다.

## 공통 파일 계약

- `records/assignments.json`: `{schema_version: 1, assignments: [...]}`. 각 행은 `experiment_id`, `slot`(slot1/slot2/slot3), `title`, `run_id`, `task_id`, `dispatch_id`, `agent_model_requested`, `agent_model_effective`, `reasoning_effective`, `assigned_at`, `synthetic`를 갖는다. 미확인 실효 모델/effort는 null이다. 실제 배정 근거는 Orca receipt/세션 metadata로 로컬 보관한다. 동일 배정 재등록은 중복을 만들지 않고, 다른 내용으로 덮어쓰지 않는다.
- 기존 `records/catalog.json`은 완료 등록한 공개 결과의 인덱스다. 과거 EXP-0001~0007과 새 결과를 보존한다. 담당 슬롯에서 결과 목록을 열며 슬롯에 여러 완료 결과가 남을 수 있다.
- 완료 package JSON은 `experiment_id`, `attempt_id`, `title`, `summary`, `evaluated_model`, `execution_status`(succeeded/failed/inconclusive), `review_status`(accepted_for_comparison/needs_revision/blocked/inconclusive), `decision_status`(adoption_on_hold/rejected), `report_path`, `metrics_path`, `review_path`, `reviewed_report_sha256`, `reviewed_metrics_sha256`, `worker_opinion`, `next_step`, `limitations`, `evidence`를 갖는다. evidence 행은 `artifact_id`, `label`, `kind`(video/image). 경로는 등록된 공개 상대 경로만 허용한다.
- 실제 metrics 파일은 기존 metrics 계약(label/value/unit/sample_n/scope/source/source_sha256/verification)을 따른다. 유한 숫자 또는 null만 허용하고, 보고서와 별도로 그래프 숫자를 입력하지 않는다. 공개 package/records에 원시 응답·토큰·절대 로컬 경로를 넣지 않는다.
- 로컬 artifact manifest는 `{artifacts: {artifact_id: {path: ABSOLUTE_LOCAL_PATH, kind: video_or_image}}}`다. Git 제외 파일이며 기존 allow root 아래의 등록 가능한 일반 파일만 허용한다. 해당 결과의 evidence ID와 일치해야 한다. 파일 내용은 복사하지 않는다.

## 재사용 명령 계약

공통 명령은 `python -m orchestration.complete --config LOCAL_CONFIG`다. config의 repo_root가 등록 대상 저장소다. 실제 사용 전 구현의 `--help`와 아래 검증 결과를 함께 확인한다.

1. `assign --assignment ASSIGNMENT_JSON`: 검증된 배정 연결을 기록한다. 이 명령 자체는 에이전트를 생성하지 않는다.
2. `complete --package PACKAGE_JSON --artifacts LOCAL_ARTIFACTS_JSON`: 배정과 원문·metrics·review·검토 SHA·artifact를 검증하고 검토 binding/공개 인덱스/로컬 allowlist를 연결한다. 같은 내용은 재실행해도 중복되지 않는다. 기존 결과/다른 내용/ID 충돌은 거부한다. 명시적 검토 SHA 없이 최신 자료에 과거 검토를 자동 연결하지 않는다.
3. `status --experiment EXPERIMENT_ID`: 등록 상태와 근거 부재를 확인한다. GitHub 게시와 실제 브라우저 재생을 자동으로 확인했다고 반환하지 않는다.

원본 report/metrics/review는 이미 소유자가 작성한 파일을 참조한다. 완료 명령이 실험 결과나 검토 의견을 생성하지 않는다. 공통 runtime lock 아래에서 검증하고 catalog를 마지막에 원자적으로 교체한다. 중간 실패 후 같은 명령의 재실행은 안전하게 이어가며, 이전 결과를 지우지 않는다. 과거 전용 importer는 새 배정/결과가 있는 인덱스를 덮어쓰지 않는다.

## 완료 확인표 — 매 실험에서 저장

| 확인 | 필요한 실제 근거 | 기록 위치 |
| --- | --- | --- |
| 담당 배정·상태 | 정확한 native IDs와 실효 모델/effort; 실행 중 카드의 표시 | 실험 보고서 + 로컬 receipt |
| 실행·측정 | 종료 결과, 입력/설정/code SHA, 실패/미측정, 원천 참조 | 보고서/metrics + 로컬 원시 결과 |
| 총괄 검토 | 원문·metrics SHA에 연결된 별도 의견/한계/다음 판단 | 별도 review와 binding |
| 등록 | complete/status의 결과, 같은 명령 재실행 시 중복 없음 | 로컬 완료 receipt |
| GitHub 게시 | 원격 main 커밋과 게시 파일/해시 확인 | 보고서/완료 메시지 + 로컬 receipt |
| 로컬 반영 | 서비스가 읽는 repo/config, 재시작 필요 여부, 실제 API/브라우저 | 로컬 화면 확인 receipt |
| 실제 화면 확인 | 담당 카드 선택 → 해당 보고서·metrics 그래프 → 등록 비교 영상 재생·seek → 총괄 검토 | 로컬 브라우저 관측값, 픽셀 업로드 없음 |

GitHub push 성공만으로 화면 갱신을 완료 처리하지 않는다. HTTP 200만으로 브라우저 표시/재생 성공을 대신하지 않는다. 원격 게시 SHA와 실제 서비스 코드/자료 버전을 대조하고 각각 성공/실패/미확인 및 시각을 남긴다. 보고서·측정치가 바뀌면 이전 review binding과 화면 확인은 다시 검증한다.

**첫 실제 실험은 위 전체 흐름의 실행 중 상태와 완료 후 클릭/그래프/비교 영상까지 확인한다.** 현재 새 실험은 미실행이며, TEST 등록/모의 상태의 검증은 실제 실험 검증과 별도로 표시한다. 테스트 자료는 Git 제외 격리 fixture에만 만들고 실제 EXP 번호/원본 라벨/기존 보고서로 위장하지 않는다. 실패 실험도 실패 보고서를 남기며, 영상이 없으면 부재와 이유를 표시하고 영상 확인을 통과 처리하지 않는다.

완료 메시지는 `코드 구현`, `실제 실험 실행`, `GitHub 게시`, `로컬 화면 확인` 네 항목을 분리한다. 모델 채택과 사용자 확정 정답은 이 절차 완료와 별도다.
