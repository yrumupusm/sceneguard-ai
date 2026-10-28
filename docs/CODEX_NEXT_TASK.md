# Codex 다음 작업 — Orca 세팅 결과 인계와 다음 배치 준비

2026-10-28. Orca 로컬 기능 검증을 수행했다. 독립 재검토 R1~R4 해결과 실제 명령·게시 내역은 [LOCAL_SETUP_REPORT](orchestration/LOCAL_SETUP_REPORT.md)를 먼저 읽는다. 이 파일은 새 모델 실험 실행 승인이 아니다.

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
