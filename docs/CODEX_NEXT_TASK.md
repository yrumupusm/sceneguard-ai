# Codex 다음 작업 — 실험 배정부터 화면 확인까지

2026-10-28. 재사용 가능한 배정/완료 등록과 별도 게시·화면 확인 절차를 구현했다. [DELIVERY_VALIDATION](orchestration/DELIVERY_VALIDATION.md)에서 코드 테스트와 실제 브라우저 확인의 범위를 먼저 확인한다. 이번 작업은 새 CV/VLM 실험 실행 승인이 아니다.

## 다음 승인된 실험의 필수 완료 조건

1. [EXPERIMENT_DELIVERY](orchestration/EXPERIMENT_DELIVERY.md), [COMPLETE_CLI](orchestration/COMPLETE_CLI.md), [ADR-0014](decisions/ADR-0014-experiment-delivery.md), 최초 독립 검토 및 재검토를 읽는다. 기존 지침과 실행 예산은 유지한다.
2. 총괄 하나/공통 GPU 큐를 유지하며 native Task/Dispatch를 배정한다. 실효 작업자 모델/effort를 확인하고 `assign`으로 해당 EXP와 담당 1·2·3 중 하나를 연결한다. **첫 실제 실험에서 진행 중 카드 표시를 실제 브라우저로 확인한다.** 모의 상태로 대신하지 않는다.
3. 승인된 실행 후 보고서·측정값·로컬 비교 영상을 저장한다. 실패·미측정·비교 불가도 보존한다. 작업자 완료 메시지 후 총괄이 별도 검토문에 report/metrics SHA256과 의견을 기록한다.
4. `complete`로 원문/측정치/검토/로컬 artifact allowlist를 연결하고 `status`로 근거 버전을 확인한다. 동일 재시도만 허용하며 다른 내용의 완료 ID를 덮어쓰지 않는다. 과거 전용 importer로 새 배정을 지우지 않는다.
5. 코드·공개 요약을 커밋·푸시한 원격 SHA와 실제 서비스가 읽는 저장소 버전을 따로 확인한다. `verify_delivery github`와 `browser`의 별도 receipt를 보존한다. 담당 카드 선택→해당 보고서 펼치기→측정 표/그래프→등록 영상 재생·seek→총괄 검토까지 확인해야 화면 완료다.
6. 완료 메시지에서 **코드 구현 / 실제 실험 실행 / GitHub 게시 / 로컬 화면 확인**을 분리한다. 이번 TEST 성공이나 과거 EXP5 재생을 첫 실제 새 실험 검증으로 세지 않는다. 필요한 자료가 없거나 브라우저가 실패하면 해당 항목은 미완료로 남긴다.

## 반드시 읽을 것

1. AGENTS.md, [HANDOFF](HANDOFF.md), [실제 세팅 보고서](orchestration/LOCAL_SETUP_REPORT.md).
2. [ADR-0013](decisions/ADR-0013-orca-local-experiment-lab.md), [역할](orchestration/AGENT_ROLES.md), [정책](../configs/orchestration/model_policy.json).
3. [최초 독립 검토](reviews/ORCA-SETUP-independent-review.md)와 [수정 후 검토](reviews/ORCA-SETUP-recheck.md), [최종 R4 검토](reviews/ORCA-SETUP-final-review.md). 초기 needs_revision 기록을 삭제하지 않는다.
4. EXP-0006·0007의 실패/데이터/평가 제한, 특히 EXP7의 실제 입력 검수 시트와 구조화 실패 기록.

## 확인된 세팅

Astra max 총괄 한 명 + Sol high 실행기 + Terra high 화면 + Astra high 검토를 현재 계정에서 확인했다. 기존 Run을 재사용했고 중첩 fanout은 없다. 새 `.venv-orca-lab`, 공통 runtime, CPU mock 직렬 큐, loopback 읽기 전용 웹을 사용한다. `http://127.0.0.1:8765/`에서 기존 7개 실험을 미배정 카드로 읽는다. 담당1·2·3의 실제 비교 실험은 아직 배정하지 않았다.

32개 fixture와 실제 서로 다른 worktree 큐, 영상4개 재생/seek, 이미지6개 decode, 서비스 재시작/파일 부재/기존 환경 보존을 확인했다. 실행 성공·AI 검수 초안·모델 채택은 별도 상태다. 웹 조회는 모델이나 큐를 시작하지 않는다. 세팅을 반복하거나 기존 `.venv`/`.venv-vlm`을 갱신하지 않는다.

## 다음 준비 범위 — 아직 실행하지 않은 제안

- 사용자가 로컬 EXP7 입력 시트를 확인할 수 있게 기존 기록을 안내하고, 접근/대기/접촉/넘기·가림의 검수 초안과 확정 정답을 구분한다. 기존 VLM 응답을 새 정답으로 삼지 않는다.
- 기존 six clips/카메라 중복/샘플링 한계를 유지한 비교 manifest, 공통 프롬프트·출력 스키마·프레임/픽셀 예산, OOM·반복·파싱 실패 중단 조건을 먼저 작성한다.
- 후보가 필요하면 공식 자료와 현재 RTX3080 여유 메모리를 바탕으로 제안한다. 정책의 최대3후보·후보별최대2설정은 상한이며 세 모델 실행 의무가 아니다. 전부 채택 보류할 수 있다.
- 실제 모델 job을 큐에 등록하기 전에 명령 allowlist, 단일 GPU 잠금, orphan/timeout, 원천/설정 해시, 원시 결과의 로컬 보존, 메트릭/검토 binding을 검토한다. 현재 CPU mock을 그대로 실제 GPU 실행 보장이라고 주장하지 않는다.
- **실제 다운로드·추론·비교 배치는 별도 하나의 범위 승인을 받은 뒤 시작한다.** 승인된 배치 내부의 세부 단계마다 반복 확인하지 않는다. 이번 인계에서 자동 실행하지 않는다.

## 유지할 제한

기존 공식 라벨·EXP-0001~0007·출력·CV/추적/경계 코드와 두 환경을 보존한다. EXP-0006 기본 적용, EXP-0007 자동 CV 연동은 보류다. 정밀 정답·카메라 독립성·G1E는 미확정이다. 원본/이미지/가중치/원시 응답/runtime DB/인증정보는 로컬 전용이다. raw CCTV를 클라우드 에이전트 이미지 도구에 보내지 않는다. API 유료 전환, 공개 배포, 무인 반복, 기본 보호 설정 해제, 새 총괄 중복 생성은 하지 않는다.
