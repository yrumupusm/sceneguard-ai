# SceneGuard

**산업현장 사고·이상상황 영상 분석 및 사람 검토 지원 — 데이터 검증 단계**

> 목표는 최신 AI 모델을 많이 넣는 것이 아니라, 실제 CCTV 영상에서 관찰 가능한 안전 이벤트를 확인하고 **문제 정의 → 선행연구 → 대안 비교 → 데이터 검증 → 기술 선택 → 실험·개선** 전 과정을 근거와 함께 기록하는 것이다.

## 현재 상태 (2026-10-27)
- ✅ 프로젝트 목표 및 개발·기록 원칙 정리
- ✅ 선행연구 요약: [Unsafe-Net 등 R-001](docs/research/0001-literature-and-initial-hypotheses.md), [iSafetyBench R-002](docs/research/0002-isafetybench-review.md)
- ✅ Safe and Unsafe Behaviours 영상 8개 소량 다운로드·라벨·디코딩 감사 ([결과](docs/data/SAMPLE_AUDIT.md))
- ✅ 패널 상태 분류는 메인 MVP에서 제외 ([결정 근거](docs/decisions/ADR-0002-reconsider-safety-dataset.md))
- ✅ **제품 방향 설정:** 이미 선택한 짧은 사고·이상상황 영상에 대한 복합 행동/사건 분석 및 안전 담당자 검토 지원 ([ADR-0003](docs/decisions/ADR-0003-incident-review-product-direction.md))
- ⬜ **iSafetyBench 실제 데이터 검증(다음 할 일)**: 출처·라이선스·정답·소량 영상 감사 (메인 데이터 확정 아님)
- ⬜ 첫 MVP 대상 안전 이벤트 결정
- ⬜ 최종 모델/아키텍처 결정 및 자체 실험
- ⬜ 추론 최적화·서비스 운영·포트폴리오 완성

## 프로젝트 문제
산업현장 안전 담당자가 이미 선택한 **짧은 사고·이상상황 클립의 행동/사건 후보를 분석**하고, 근거 후보와 설명을 확인·수정·확정하여 관리할 수 있도록 돕는 소프트웨어를 탐색한다. 실제 안전 담당자의 업무 개선 효과는 아직 검증하지 않았다. **장시간 CCTV에서 사고 구간을 자동 발견하거나 사고 전 위험을 예측하는 기능은 후속 과제**다. 단, 법규상 위반·작업 권한·허용 적재량은 영상만으로 확정하지 않는다. 실제 사용자 요구를 인터뷰해 검증한 단계는 아니다.

기존 데이터의 **설비 패널 열린/닫힌 상태**는 시각적으로 확인했지만, 프로젝트 메인 MVP에서는 제외했다. 복합 안전 행동 및 사고 영상 분석은 차기 후보이며 미확정이다.

## 기술과 데이터 — 모두 후보
- 기존 감사 데이터: [Safe and Unsafe Behaviours](https://huggingface.co/datasets/Voxel51/Safe_and_Unsafe_Behaviours) ([결과](docs/data/SAMPLE_AUDIT.md)) — 연구 자료 보존, 메인 확정 아님
- 새 검증 후보: [iSafetyBench](https://huggingface.co/datasets/raiyaanabdullah/isafety-bench) — 실제 미디어·주석·라이선스 확인 전
- 추가 후보: [CMOT](https://github.com/XZ-YAN/CMOT-Dataset), [Construction-PPE](https://docs.ultralytics.com/datasets/detect/construction-ppe)
- CV/시간 분석: YOLO 계열, 필요시 추적기(BoT-SORT 등), 행동 인식 모델
- 언어·상황 설명: VLM 후보
- 추론 최적화/운영: 필요성이 검증되면 ONNX, TensorRT, API, Docker 검토
- 로컬 목표: NVIDIA RTX 3080 (VRAM·실행 환경·속도는 확인 전)

**YOLO/BoT-SORT/VLM을 당연한 구성요소로 확정하지 않는다.** 선행연구와 실제 데이터, 정확도·속도·자원·라벨링 비용을 보고 최소 기술을 선정한다.

## 바로 시작하는 방법
1. [Codex 작업 규칙](AGENTS.md), [프로젝트 목표](docs/PROJECT_CHARTER.md), [작업 계획](docs/WORK_PLAN.md)을 읽는다.
2. [새 Codex 작업 지시](docs/CODEX_NEXT_TASK.md)에 따라 iSafetyBench의 출처·라벨·접근·사용 조건과 가능한 샘플 6~10개를 감사한다.
3. [후보 데이터 감사 계획](docs/data/ISAFETYBENCH_AUDIT_PLAN.md)에 따라 `docs/data/ISAFETYBENCH_SAMPLE_AUDIT.md` 작성.
4. 사람이 실제 영상을 검수하고 **Go / Conditional Go / No-Go** 결정을 내린다.
5. 첫 이벤트·평가 단위를 확정한 뒤 [ADR](docs/decisions/ADR-0001-research-first.md)에 근거를 쌓아 모델을 선정한다.

## 기록 위치
| 문서/폴더 | 목적 |
| --- | --- |
| [PROJECT_CHARTER](docs/PROJECT_CHARTER.md) | 목표·제약·성공 기준 |
| [PRODUCT_WORKFLOW](docs/PRODUCT_WORKFLOW.md) | 가정 사용자 업무 흐름과 검증할 효용 |
| [WORK_PLAN](docs/WORK_PLAN.md) | 진행 단계·담당·완료 조건 |
| [research](docs/research/) | 논문에 보고된 사실·한계 |
| [decisions](docs/decisions/) / [decision log](docs/DECISION_LOG.md) | 기술 대안·선정·번복 이유 |
| [data](docs/data/) | 영상/라벨/라이선스 적합성 |
| [experiments](docs/experiments/) | 실제 실험 환경·명령·측정값 |
| [troubleshooting](docs/troubleshooting/) | 실패·원인·수정·검증 |
| [PORTFOLIO_EVIDENCE](docs/PORTFOLIO_EVIDENCE.md) | 채용 포트폴리오용 증거 |
| [HANDOFF](docs/HANDOFF.md) | 다음 세션 인수인계 |
| [SETUP_DOCS](docs/SETUP_DOCS.md) | 로컬 클론·Codex 시작 안내 |

## 공개 저장소 유의사항
원본 영상·모델 가중치·개인정보·비밀키·대용량 출력은 기본적으로 커밋하지 않는다. 스크린샷/영상 공개는 데이터 라이선스 확인 후 진행한다. 논문 수치나 미실행 실험을 자체 성과처럼 표현하지 않는다.
