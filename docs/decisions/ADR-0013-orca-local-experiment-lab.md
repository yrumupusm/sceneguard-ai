# ADR-0013 — Orca native 작업 조정과 로컬 결과 조회 분리

- 날짜: 2026-10-28
- 상태: 세팅 범위 채택. 실제 모델 비교 배치·서비스 운영 승인은 별도.
- 근거: 사용자 승인, SETUP_ORCA, AGENT_ROLES, model_policy, 설치된 Orca 1.4.240 orchestration 가이드.

기존 EXP-0001~0007의 실패와 비용을 같은 화면에서 읽고 다음 실험을 나눠 수행할 준비가 필요하다. 기존 CV/VLM 실행 환경과 데이터는 보존해야 하며, 세팅 성공을 모델 성능이나 사건 감지 성공으로 바꿀 수 없다.

Orca Run/Task/Dispatch와 완료·ack·release를 작업 조정의 원본으로 사용한다. 별도 LLM 총괄이나 Codex 중첩 fanout을 만들지 않는다. 현재 총괄 세션을 재사용하고 작업자는 최대 3명, GPU 작업은 호스트 공통 runtime의 잠금 하나로 제한한다. SQLite는 등록 CPU mock 실행과 결과 조회용 상태에만 사용한다. Orca의 작업 생명주기를 DB에서 다시 결정하지 않는다.

모델은 정책의 정확한 ID를 authenticated Codex model/list와 실제 세션 메타데이터로 확인한다. 총괄 Astra max, 구현 Sol high, 화면 Terra high, 검토 Astra high가 목표다. 목록에는 ultra도 있지만 자동 task delegation 모드이므로 이 단일 계층 세팅에서는 정책의 max 우선순위를 유지한다. Astra Pro ID는 반환되지 않았으며 임의로 만들거나 API 결제로 전환하지 않는다. 실패한 시작 receipt의 effective model만으로 실행 성공을 선언하지 않는다.

초기 `worker-start --agent codex --model … --effort …`는 저장소 신뢰와 업데이트 안내에서 막혔다. 사용자가 SceneGuard 신뢰 확인과 CLI 0.165.0 업데이트를 수행했다. Orca 기본 terminal launch의 process argv에 보호 우회 옵션이 확인돼 작업 수행 전에 실패한 세션을 정리했다. 버전 가이드의 custom argv 경로인 `terminal create` → 준비 확인 → `worker-start --terminal`을 사용한다. 명시적 `workspace-write`와 승인 정책을 사용하며 native Task/Dispatch를 유지한다. 이 경로의 launch 모델 필드는 null이므로 Codex thread 메타데이터와 실제 작업 수행 기록으로 보강한다. `--shell wsl.exe`와 `powershell.exe`의 상충된 거부는 생성 전 실패했고, 안내대로 shell을 생략하자 UNC worktree의 WSL terminal이 선택됐다.

웹은 FastAPI + 로컬 HTML/CSS/JavaScript, 새 `.venv-orca-lab`을 사용한다. 모델을 로딩하지 않고 GET/HEAD로 등록된 보고서·측정치·artifact만 조회한다. 보고서 원문과 그래프용 metrics는 서로 다른 수동 숫자를 유지하지 않으며, 가져온 수치는 JSON 포인터와 SHA256으로 원천에 연결한다. 임의 경로/static data mount·외부 CDN·미디어 업로드·공개 bind·실행 버튼은 제외한다.

대안인 새 스케줄러/대형 대시보드 프레임워크/클라우드 결과 저장소는 현재 소규모 실험에 필요한 범위를 넘는다. 반대로 설정 문서만 작성하면 실제 모델·메시지·직렬 실행·복구·영상 Range를 입증하지 못하므로 실제 호출과 CPU mock 및 로컬 브라우저 검사를 수행한다. 실제 테스트 결과와 남은 제약은 LOCAL_SETUP_REPORT에 따로 기록한다.

기본 채택 의견은 새 실험 모델이 아니라 이 제한된 실험 준비 구조에 대한 것이다. 장기간 무인 운영이나 장애 시 자동 무한 재시도는 보장하지 않는다. WSL/Orca bridge 권한 또는 버전 변화로 native 연결이 깨지면 해당 역할을 blocked로 표시하고 우회·무음 모델 대체 없이 재검증한다.
