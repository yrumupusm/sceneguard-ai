# SceneGuard

**CCTV 출입 경계 침범 이벤트 탐지·검토 지원 — 데이터 감사 단계**

SceneGuard는 AI Software Engineer 직무 포트폴리오를 위한 실험 프로젝트다. 공개된 CCTV 영상에서 **사람의 출입 경계 통과/넘기 행동**을 감지하고, 카메라별 경계 설정·오탐·감지 시점·실행 비용을 재현 가능하게 평가하는 것이 첫 목표다. 법적 **무단침입이나 출입 권한을 영상만으로 확정하지 않는다.**

## 현재 결정 (2026-10-27)
- **첫 MVP 방향 잠정 채택:** 학교 등 고정형 CCTV에서 카메라별 감시선/ROI를 지정해 **출입 경계 통과·넘기 이벤트 후보를 검토하는 시스템**. [ADR-0004](docs/decisions/ADR-0004-boundary-crossing-cctv-mvp.md).
- **현재 데이터 후보:** [AI-Hub 71850 지능형 관제 서비스 CCTV 영상 데이터](https://aihub.or.kr/aihubdata/data/view.do?dataSetSn=71850)의 **침입 범주**. 사용자 제공 전체 장면 미리보기에서 학교 철제 출입구 반복이 확인됨. 특수 사례는 **4번 줄 넘기**, **7번 공원 울타리 넘기**로 구별.
- **아직 검증 전:** 로컬 원본 MP4·JSON 파일 접근, 실제 카메라/장소 중복, 비이벤트 구간, 영상별 정답, 다운로드/배포·개인정보 조건, 최종 모델.
- **다음 작업:** [Codex 지시](docs/CODEX_NEXT_TASK.md)와 [침입 데이터 감사 계획](docs/data/AIHUB_INTRUSION_AUDIT_PLAN.md)에 따라 공식 자료 접근 확인 → 6~10개 이내 소량 감사 → 사용자 영상 검수 → 데이터 Go/No-Go 결정.
- **기술 후보(선정 전):** 공통 사람 검출/추적 + CCTV별 설정한 ROI/가상선 baseline. 실제 울타리 넘기와 선 통과의 차이를 평가. VLM의 추가 가치는 CV baseline의 실패·처리비용 분석 이후 판단.
- **장비:** 로컬 RTX 3080. 모델 성능·속도·GPU 메모리는 아직 측정되지 않았다.

## 왜 이 문제인가
- ACCIDENT 교통 사고 CCTV는 실제 영상·정답 검증에 성공했지만 짧은 **사고 포함 클립** 위주라 정상 구간 오탐 평가에 제약이 있음.
- AI-Hub 침입 범주의 일부 CCTV 영상은 사용자 확인상 **1~2분 길이**로 사건 전후 확인에 유리할 가능성이 있음. 실제 비이벤트 시간은 아직 정답으로 검수되지 않았다.
- 학교 출입구 구도가 반복되는 **장면 편중** 때문에 카메라별 설정 방식과 새로운 카메라 일반화 성능을 구분해 측정해야 한다.
- 상용 침입 검지 기능 자체를 새 발명으로 주장하지 않는다. **기존 단순 방식의 실패·오탐과 VLM 도입 필요성을 실험으로 판단하는 과정**을 핵심 성과로 삼는다.

## 데이터 조사 이력 (보존)
| 데이터 | 실제 확인한 결과 | 현재 역할 |
| --- | --- | --- |
| [Safe and Unsafe Behaviours](docs/data/SAMPLE_AUDIT.md) | 8개 CCTV 영상 검사, 패널 상태 중심의 단순 문제 | 감사 이력 |
| [iSafetyBench](docs/data/ISAFETYBENCH_SAMPLE_AUDIT.md) | 1,100개 주석과 8개 영상 감사, 일반/편집 촬영 포함 | 보조 참고 |
| [SteelBench](docs/data/STEELBENCH_SAMPLE_AUDIT.md) | 공식 배포 주소 HTTP 401, 영상 확보 0개 | 접근 문제로 보류 |
| [ACCIDENT](docs/data/ACCIDENT_SAMPLE_AUDIT.md) | 2,027개 공개 주석 연결 및 실제 교통 CCTV 5개 감사 | 교통 사고 대안, 보존 |

관련 결정: [ADR-0001](docs/decisions/ADR-0001-research-first.md), [ADR-0002](docs/decisions/ADR-0002-reconsider-safety-dataset.md), [ADR-0003](docs/decisions/ADR-0003-incident-review-product-direction.md), **[ADR-0004](docs/decisions/ADR-0004-boundary-crossing-cctv-mvp.md)**.

## 다음 작업과 운영 원칙
- [AGENTS.md](AGENTS.md): Codex 프로젝트 작업·보안·검증 지침
- [docs/WORK_PLAN.md](docs/WORK_PLAN.md): Phase 1E 데이터 감사 → Phase 2 평가·모델 설계 → 실험
- [docs/PROJECT_CHARTER.md](docs/PROJECT_CHARTER.md): 프로젝트 문제·성공 기준
- [docs/PRODUCT_WORKFLOW.md](docs/PRODUCT_WORKFLOW.md): 관제·검수 시나리오
- [docs/HANDOFF.md](docs/HANDOFF.md): 최신 인수인계

**영상·추출 프레임·원 주석·개인정보·비밀키/토큰·모델 가중치는 GitHub에 공개하지 않는다.** 데이터 접근·재배포 조건을 확인한 뒤 필요한 자료만 로컬에서 감사한다. 선행연구 보고치와 SceneGuard 실측을 구분한다.
