# SceneGuard

**CCTV 출입 경계 침범 이벤트 탐지·검토 지원 — 최소 CV 첫 실험·실패 분석 단계**

SceneGuard는 AI Software Engineer 직무 포트폴리오를 위한 실험 프로젝트다. 공개된 CCTV 영상에서 **사람의 출입 경계 통과/넘기 행동**을 감지하고, 카메라별 경계 설정·오탐·감지 시점·실행 비용을 재현 가능하게 평가하는 것이 첫 목표다. 법적 **무단침입이나 출입 권한을 영상만으로 확정하지 않는다.**

첫 로컬 CV baseline을 구현·진단했다. **SSDLite320에서 작은/가려진 사람 검출 누락이 확인돼 메인 모델 채택은 보류**한다. 결과·처리 속도·재현 명령은 [EXP-0001](docs/experiments/EXP-0001-phase2a-cv-baseline.md), 실행 방법은 [CLI 문서](docs/design/CV_BASELINE_CLI.md)에 기록했다. 최종 precision/recall/F1·시간당 오탐률은 정답 검수 전이므로 산출하지 않았다.

추가로 **FCOS COCO_V1**을 동일 네 짧은 구간에서 비교했다. 실제 사람 일부를 새로 검출했지만 누락·중복·배경 오검출 의심과 연결 실패가 남아 메인 채택은 보류한다. 실측 비교와 다음 작업: [EXP-0002](docs/experiments/EXP-0002-fcos-detector-comparison.md), [ADR-0008](docs/decisions/ADR-0008-fcos-detector-comparison.md). 모델과 입력 크기가 함께 바뀐 결과이며 해상도 단독 효과가 아니다.

같은 FCOS 캐시로 **IoU / ByteTrack high-only / low 2차 연결**도 비교했다. 일부 실제 사람의 연결이 개선됐지만 중복·배경 track과 부분 신체 기반 경계 후보 오류가 남아 기본 tracker 교체는 보류한다. [EXP-0005](docs/experiments/EXP-0005-bytetrack-cache-comparison.md)에 재현·연속 검수·실패를 기록했다. 검출 재추론이나 새 가중치 다운로드는 없었다.

## 현재 결정 (2026-10-27)
- **첫 MVP 방향 잠정 채택:** 학교 등 고정형 CCTV에서 카메라별 감시선/ROI를 지정해 **출입 경계 통과·넘기 이벤트 후보를 검토하는 시스템**. [ADR-0004](docs/decisions/ADR-0004-boundary-crossing-cctv-mvp.md).
- **현재 데이터 후보:** [AI-Hub 71850 지능형 관제 서비스 CCTV 영상 데이터](https://aihub.or.kr/aihubdata/data/view.do?dataSetSn=71850)의 **침입 범주**. 사용자 제공 전체 장면 미리보기에서 학교 철제 출입구 반복이 확인됨. 특수 사례는 **4번 줄 넘기**, **7번 공원 울타리 넘기**로 구별.
- **검증 완료/보류 구분:** 로컬 Training MP4·JSON 45개 대응, CCTV 10개 소량 감사 및 사용자 행동 검수 기록 완료. **미확정:** 실제 독립 카메라 수, 비이벤트 평가 정답 시간, E01_006 프레임 수 차이(원본 4,006/JSON 4,011), 정밀 사람별 행동 시각, 최종 모델 및 공개 영상 활용권. [사용자 검수](docs/data/AIHUB_INTRUSION_USER_REVIEW.md), [평가 계획](docs/data/AIHUB_INTRUSION_EVALUATION_PLAN.md).
- **최초 승인된 작업(Phase 2A, 완료):** [ADR-0006](docs/decisions/ADR-0006-limited-cv-baseline-prototype.md) 및 [Codex 지시](docs/CODEX_NEXT_TASK.md)에 따라 **사전학습 사람 탐지 1개 → 최소 IoU 연결 → 카메라별 ROI/경계 통과 후보 출력**을 로컬 개발 영상 2~4개에 대해 제한적으로 구현·진단. 모델 재학습/VLM/UI는 보류. G1E 데이터 최종 승인과는 별개.
- **기술 방향:** 공통 사전학습 사람 검출기(SSDLite320 첫 진단 및 FCOS 추가 비교 완료, 메인 채택 보류) + 간단한 인접 IoU 연결 + 카메라별 설정한 ROI/유한 경계선의 양측 움직임 후보. **가상 선 통과는 실제 넘기 시작·완료와 다를 수 있음**. VLM은 baseline 실패/처리비용 검토 이후 판단.
- **장비:** 로컬 RTX 3080 10GB. 첫 진단의 처리 속도·메모리는 EXP-0001에 실측 기록. 정답 기반 정확도는 미평가.

## 왜 이 문제인가
- ACCIDENT 교통 사고 CCTV는 실제 영상·정답 검증에 성공했지만 짧은 **사고 포함 클립** 위주라 정상 구간 오탐 평가에 제약이 있음.
- AI-Hub 침입 영상은 소량 감사에서 약 2~3분 길이임을 확인. 사건 전후 시점이 있지만 **검수 완료 비이벤트 시간은 아직 0초**로, 오탐 성능을 확정해 보고하지 않는다.
- 학교 출입구 구도가 반복되는 **장면 편중** 때문에 카메라별 설정 방식과 새로운 카메라 일반화 성능을 구분해 측정해야 한다.
- 상용 침입 검지 기능 자체를 새 발명으로 주장하지 않는다. **기존 단순 방식의 실패·오탐과 VLM 도입 필요성을 실험으로 판단하는 과정**을 핵심 성과로 삼는다.

## 데이터 조사 이력 (보존)
| 데이터 | 실제 확인한 결과 | 현재 역할 |
| --- | --- | --- |
| [Safe and Unsafe Behaviours](docs/data/SAMPLE_AUDIT.md) | 8개 CCTV 영상 검사, 패널 상태 중심의 단순 문제 | 감사 이력 |
| [iSafetyBench](docs/data/ISAFETYBENCH_SAMPLE_AUDIT.md) | 1,100개 주석과 8개 영상 감사, 일반/편집 촬영 포함 | 보조 참고 |
| [SteelBench](docs/data/STEELBENCH_SAMPLE_AUDIT.md) | 공식 배포 주소 HTTP 401, 영상 확보 0개 | 접근 문제로 보류 |
| [ACCIDENT](docs/data/ACCIDENT_SAMPLE_AUDIT.md) | 2,027개 공개 주석 연결 및 실제 교통 CCTV 5개 감사 | 교통 사고 대안, 보존 |

관련 결정: [ADR-0001](docs/decisions/ADR-0001-research-first.md), [ADR-0002](docs/decisions/ADR-0002-reconsider-safety-dataset.md), [ADR-0003](docs/decisions/ADR-0003-incident-review-product-direction.md), [ADR-0004](docs/decisions/ADR-0004-boundary-crossing-cctv-mvp.md), **[ADR-0006](docs/decisions/ADR-0006-limited-cv-baseline-prototype.md)**.

## 다음 작업과 운영 원칙
- [AGENTS.md](AGENTS.md): Codex 프로젝트 작업·보안·검증 지침
- [docs/WORK_PLAN.md](docs/WORK_PLAN.md): Phase 1E 감사·평가 설계 → Phase 2A 제한 실험 → 이후 평가·개선
- [docs/PROJECT_CHARTER.md](docs/PROJECT_CHARTER.md): 프로젝트 문제·성공 기준
- [docs/PRODUCT_WORKFLOW.md](docs/PRODUCT_WORKFLOW.md): 관제·검수 시나리오
- [docs/HANDOFF.md](docs/HANDOFF.md): 최신 인수인계

**영상·추출 프레임·원 주석·개인정보·비밀키/토큰·모델 가중치는 GitHub에 공개하지 않는다.** 데이터 접근·재배포 조건을 확인한 뒤 필요한 자료만 로컬에서 감사한다. 선행연구 보고치와 SceneGuard 실측을 구분한다.
