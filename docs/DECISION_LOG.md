# SceneGuard 결정·방향 변경 로그

| 날짜 | 주제 | 상태 | 근거 | 비고 |
| --- | --- | --- | --- | --- |
| 2026-10-26 | 2023 우회전 단속 복원이 아닌 산업안전 주제 신규 프로젝트 | 결정 | [프로젝트 차터](PROJECT_CHARTER.md) | CV/VLM 응용 소프트웨어 역량·의사결정 근거 축적 |
| 2026-10-26 | 메인 후보 데이터 Safe and Unsafe Behaviours | **잠정** | [데이터 감사 계획](data/DATASET_AUDIT_PLAN.md) | 실물 미확인 |
| 2026-10-26 | 모델/아키텍처를 선제 고정하지 않음 | 결정 | [ADR-0001](decisions/ADR-0001-research-first.md) | YOLO/BoT-SORT/VLM 등은 후보 |
| 2026-10-26 | 선행연구→데이터 검증→기술 선택→필요한 실험 순서 | 결정 | [ADR-0001](decisions/ADR-0001-research-first.md) | 불필요한 중복 실험 줄이기 |
| 2026-10-26 | Safe and Unsafe Behaviours 8개 영상 샘플 감사 완료(6개 부합 관찰, 2개 보류) | 완료 / Conditional Go | [SAMPLE_AUDIT](data/SAMPLE_AUDIT.md) | 전체 영상 사람 검수는 아님 |
| 2026-10-26 | 패널 상태 분류는 SceneGuard 메인 MVP에서 제외 | **결정** | [ADR-0002](decisions/ADR-0002-reconsider-safety-dataset.md) | 열린/닫힌 상태는 확인했으나 복합 행동 분석 목표와 범위 불일치 |
| 2026-10-26 | iSafetyBench로 사고·복합 행동 영상 분석 가능성 재검토 | **조사 후보, 미확정** | [ADR-0002](decisions/ADR-0002-reconsider-safety-dataset.md) | 영상·라벨·라이선스 확인 전 데이터 확정 금지 |
| 2026-10-27 | 첫 제품 활용 목표를 사고·이상상황 영상의 **분석 및 사람 검토 지원**으로 정함 | **제품 방향 채택 / 구현 미검증** | [ADR-0003](decisions/ADR-0003-incident-review-product-direction.md) · [업무 흐름](PRODUCT_WORKFLOW.md) | 입력은 선택된 짧은 영상; 실시간 예방은 후순위. 메인 데이터·모델은 미확정 |
| 2026-10-27 | **학교 CCTV 출입 경계 침범 감지를 첫 MVP 문제로 잠정 선정** | **조건부 방향 결정 / 데이터·모델 미확정** | [ADR-0004](decisions/ADR-0004-boundary-crossing-cctv-mvp.md) · [감사 계획](data/AIHUB_INTRUSION_AUDIT_PLAN.md) | 카메라별 ROI/경계 설정, 정상 구간 오탐·새 카메라 일반화 검증. ACCIDENT 등 과거 감사 보존 |
| 미정 | AI-Hub 데이터 최종 채택, 구간 GT·평가 분할 및 모델 | 미결정 | Phase 1E 샘플 감사 후 결정 | 사용자 영상/권리 검토 필요 |

결정을 변경할 때는 기존 ADR을 삭제하지 않고 후속 ADR로 상태와 이유를 연결한다.
