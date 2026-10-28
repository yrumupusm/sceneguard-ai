# Codex 다음 작업 — 첫 VLM 배치 종료 후 검수 대기

2026-10-28. **이번 배치의 모델 실행은 종료했다. 새 조건·모델을 자동 실행하지 않는다.** [BATCH-0001 비교 결론](experiments/BATCH-0001-vlm-comparison.md), [전달 기록](orchestration/BATCH-0001_DELIVERY.md), [독립 검토](reviews/BATCH-0001-independent-review.md), [HANDOFF](HANDOFF.md)를 먼저 읽는다.

## 현재 판단

Qwen3-VL-2B 기준(EXP8), SmolVLM2-2.2B 기준(EXP9), Qwen 전체 화면 픽셀 예산 한 대조(EXP10)의 세 조건을 기존 GPU 큐에서 실행했다. 각6클립 생성 완료, 모델 실행 오류/재시도/OOM0. 두 후보 모두 넘기 근거·완료·유보의 안정성이 부족해 채택 보류다. 더 큰 Qwen 입력의 유효한 행동 개선도 확인하지 못했다. JSON 형식 통과와 짧은 생성 시간을 행동 정확도로 취급하지 않는다.

## 다음 판단에 필요한 자료

- 로컬 웹 담당1의 EXP8/10, 담당2의 EXP9에서02/06 표시 자료를 우선 확인한다. 원본 연속/2fps 표본 비교 영상과 실제 모델 입력 시트는 서로 다른 자료다.
- 사람이 직접 확인하기 전 기존 관찰 초안과 Codex 텍스트 검토를 사용자 확정 정답으로 바꾸지 않는다. 특히02의 개인별 반대편 이동과06의 접촉/가림은 미확정이다.
- 기존6클립은 개발용이며 카메라가 중복된다. 다음 실험을 요청받으면 먼저 평가 근거와 승인된 범위를 정하고 새 EXP/Task/Dispatch/job/attempt를 사용한다. 이번 결과에 맞춘 프롬프트 반복 조정, 새 모델 자동 다운로드, 연속 CCTV 자동 발견·범용 정확도 주장은 하지 않는다.
- 기본 CV·추적·경계 규칙과 EXP6 적용 보류를 유지한다. 영상/이미지/가중치/원시 응답/DB/로그는 로컬 전용이며 클라우드 에이전트 이미지 도구에 CCTV 픽셀을 보내지 않는다.

## 다음 승인된 실험의 필수 완료 조건

1. [EXPERIMENT_DELIVERY](orchestration/EXPERIMENT_DELIVERY.md), [COMPLETE_CLI](orchestration/COMPLETE_CLI.md), [ADR-0014](decisions/ADR-0014-experiment-delivery.md), 최초 독립 검토 및 재검토를 읽는다. 기존 지침과 실행 예산은 유지한다.
2. 총괄 하나/공통 GPU 큐를 유지하며 native Task/Dispatch를 배정한다. 실효 작업자 모델/effort를 확인하고 `assign`으로 해당 EXP와 담당 1·2·3 중 하나를 연결한다. **첫 실제 실험에서 진행 중 카드 표시를 실제 브라우저로 확인한다.** 모의 상태로 대신하지 않는다.
3. 승인된 실행 후 보고서·측정값·로컬 비교 영상을 저장한다. 실패·미측정·비교 불가도 보존한다. 작업자 완료 메시지 후 총괄이 별도 검토문에 report/metrics SHA256과 의견을 기록한다.
4. `complete`로 원문/측정치/검토/로컬 artifact allowlist를 연결하고 `status`로 근거 버전을 확인한다. 동일 재시도만 허용하며 다른 내용의 완료 ID를 덮어쓰지 않는다. 과거 전용 importer로 새 배정을 지우지 않는다.
5. 코드·공개 요약을 커밋·푸시한 원격 SHA와 실제 서비스가 읽는 저장소 버전을 따로 확인한다. `verify_delivery github`와 `browser`의 별도 receipt를 보존한다. 담당 카드 선택→해당 보고서 펼치기→측정 표/그래프→등록 영상 재생·seek→총괄 검토까지 확인해야 화면 완료다.
6. 완료 메시지에서 **코드 구현 / 실제 실험 실행 / GitHub 게시 / 로컬 화면 확인**을 분리한다. 이번 TEST 성공이나 과거 EXP5 재생을 첫 실제 새 실험 검증으로 세지 않는다. 필요한 자료가 없거나 브라우저가 실패하면 해당 항목은 미완료로 남긴다.

## 실행 환경과 복구

기존 Run·canonical GPU queue·loopback 웹을 재사용한다. `.venv`/`.venv-vlm`은 보존했고 새 Smol 환경만 추가했다. 현재 등록 명령은 CPU mock과 고정 `vlm-batch01` 세 adapter뿐이다. 등록되어 있다는 사실은 다음 실행을 허가하지 않는다. 시작/중지/상태/복구 명령 및 실제 서비스 버전은 전달 기록에 있다. supervisor 사망 시 timeout 강제가 중단될 수 있으며 상속 잠금이 남는 구간은 원인을 확인한다. reset·강제 덮어쓰기·무한 재시도·무음 모델 대체를 하지 않는다.
