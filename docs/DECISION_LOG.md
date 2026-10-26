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
| 미정 | 최초 MVP 사건, 평가 단위, 모델 | 미결정 | Phase 1 샘플 감사 후 결정 | 사용자 검토 필수 |

결정을 변경할 때는 기존 ADR을 삭제하지 않고 후속 ADR로 상태와 이유를 연결한다.
