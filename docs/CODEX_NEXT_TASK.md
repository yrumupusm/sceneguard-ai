# Codex 다음 작업 — Orca 에이전트 실험실 세팅

2026-10-28 사용자 승인: 최고 가용 성능의 총괄 모델, 역할별 하위 모델, GPU 순차 실행, 동일 결과를 읽는 직관적인 로컬 웹페이지를 세팅한다. **이 파일 갱신은 로컬 세팅 완료가 아니다.**

## 반드시 읽을 것

1. [세팅 구현·검증 지시](orchestration/SETUP_ORCA.md)
2. [역할별 지침](orchestration/AGENT_ROLES.md)
3. [목표 모델 정책](../configs/orchestration/model_policy.json)
4. AGENTS.md, 최신 HANDOFF, EXP-0007. 기존 실험의 데이터/평가 제한은 유지한다.

## 이번 승인과 실행 순서

- 이전의 UI/서버/에이전트 도입 금지는 **이 세팅 범위에 한해 해제**한다. 기존 CV·VLM 환경 변경이나 새 모델 비교를 포괄 승인한 것은 아니다.
- Orca/WSL/Codex 가용성, 로그인 컨텍스트, 모델 목록·supported effort와 짧은 실제 호출을 먼저 확인한다. target 모델이 API에 있다는 이유로 Codex 계정 사용 가능하다고 가정하지 않는다. 최고 모델 사용 불가/권한·결제 변경 필요시 해당 역할을 blocked로 기록하고 필요한 사용자 조치만 질문한다.
- 총괄 target gpt-6-astra 최고 지원 effort, 구현/실험 담당 gpt-6.1-sol high, 독립 reviewer gpt-6-astra high, 웹 담당 gpt-6.1-terra high. 실제 더 높은 Astra Pro가 Codex에 노출되고 도구까지 작동하면 정확한 ID로 검증 후 총괄에 사용한다. 임의 Pro ID/무음 fallback 금지.
- Orca의 버전별 `orca skills get orchestration --full`을 읽고 native Run/Task/Dispatch를 우선 사용한다. 한 명의 총괄만 두며 Codex 내장 fanout과 Orca 총괄을 중첩하지 않는다. 실제 미지원시 문서상의 역할을 실행됐다고 보고하지 않는다.
- 새 worktree/브랜치와 독립 `.venv-orca-lab`에서 GPU 큐·상태/결과 계약·읽기 전용 웹페이지를 만든다. 주어진 범위에서 세부 구현마다 재승인 요청하지 않는다.
- GPU 작업은 host 공통 lock으로 한 번에 하나. 코딩/보고 준비는 최대 세 worker 병렬. 세팅은 CPU mock 작업으로 큐/실패/재시작을 검증하고 실제 새 CV/VLM 실험은 시작하지 않는다.
- 페이지는 총괄 카드, 담당1/2/3+미배정 카드, 선택한 보고서/실측 그래프/로컬 영상/총괄 검토/다음 작업의 단일 화면. 보고서 원본 하나를 그대로 렌더링하고 metrics 원본으로 그래프를 만든다. 실행 버튼·공개 배포는 만들지 않는다.
- 기존 EXP-0001~0007의 실제 내용을 표시한다. 미측정/미검증/없음은 그대로 보인다. synthetic 큐 테스트를 실제 성능으로 섞지 않는다.
- 세팅 보고서 `docs/orchestration/LOCAL_SETUP_REPORT.md`에 실제 모델·effort·가용성, 통합 smoke 결과, 시작/중지/복구 명령, 화면 주소, 테스트, 미완료, 커밋을 작성한다. 설치 사용자 PC에서 확인하지 않은 것은 미검증으로 남긴다.
- 테스트·diff·허용파일 확인 후 총괄이 통합/커밋/푸시한다. 원본 미디어·가중치·credential·runtime DB·원시 agent 로그는 Git 제외. API 유료전환·전역 설치/업그레이드·외부 미디어 전송·새 모델 가중치 다운로드·무인 반복은 금지한다.

## 이번 완료 조건

정책 파일만 만들어 놓는 것으로 끝내지 않는다. 실제 계정의 모델별 invocation 확인, worker 결과를 총괄이 받아 review한 무해한 smoke, GPU 큐 직렬화/실패해제/중복방지, 기존 보고서와 로컬 영상의 실제 UI 동작, 기존 환경 보존을 검증한다. 막힌 항목은 이유와 다음 사용자 동작을 명시한다. 완료 후 다음 실험 batch 계획만 제시하고 실행은 멈춘다.

## 이전 실험 상태 (보존)

EXP-0007 Qwen3-VL-2B 6개 5초 개발 클립 실행은 완료했으나 넘기 누락·문 열기 환각·반복·엄격 JSON 실패로 기본 연동 보류. EXP-0006은 전 후보 유보/근거부족으로 기본 적용 보류. 공식 라벨·이전 보고서·CV/추적/경계 코드·.venv/.venv-vlm을 그대로 보존한다. 데이터 카메라 독립성·검수 정답·G1E 제한은 세팅 완료와 별개다.
