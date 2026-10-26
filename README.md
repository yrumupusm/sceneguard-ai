# SceneGuard

**CV·VLM 기반 산업현장 안전 이벤트 분석 프로젝트 — 기획 및 데이터 검증 단계**

> 목표는 최신 AI 모델을 많이 넣는 것이 아니라, 실제 CCTV 영상에서 관찰 가능한 안전 이벤트를 확인하고 **문제 정의 → 선행연구 → 대안 비교 → 데이터 검증 → 기술 선택 → 실험·개선** 전 과정을 근거와 함께 기록하는 것이다.

## 현재 상태 (2026-10-26)
- ✅ 프로젝트 목표 및 개발·기록 원칙 정리
- ✅ 선행연구 요약: [Unsafe-Net 등 R-001](docs/research/0001-literature-and-initial-hypotheses.md), [iSafetyBench R-002](docs/research/0002-isafetybench-review.md)
- ⬜ **실제 데이터 검증(다음 할 일)**: 대표 정상·위험 영상 소량 확보, 라벨 매핑과 이용 조건 확인
- ⬜ 첫 MVP 대상 안전 이벤트 결정
- ⬜ 최종 모델/아키텍처 결정 및 자체 실험
- ⬜ 추론 최적화·서비스 운영·포트폴리오 완성

## 프로젝트 문제
산업현장 CCTV의 위험 **후보 이벤트**를 찾아 발생 구간과 근거 영상을 제시하고, 사람이 안전상황을 검토할 수 있도록 설명을 제공한다. 단, 법규상 위반·작업 권한·허용 적재량은 영상만으로 확정하지 않는다. 실제 사용자 요구를 인터뷰해 검증한 단계는 아니다.

최초 이벤트 후보: **지정 통로 이탈**, **설비 패널 개방**. 실제 샘플을 확인한 뒤 채택/보류한다.

## 기술과 데이터 — 모두 후보
- 우선 확인할 데이터: [Safe and Unsafe Behaviours](https://huggingface.co/datasets/Voxel51/Safe_and_Unsafe_Behaviours) ([원본 연구 데이터](https://data.mendeley.com/datasets/xjmtb22pff/1))
- 추가 후보: [CMOT](https://github.com/XZ-YAN/CMOT-Dataset), [Construction-PPE](https://docs.ultralytics.com/datasets/detect/construction-ppe)
- CV/시간 분석: YOLO 계열, 필요시 추적기(BoT-SORT 등), 행동 인식 모델
- 언어·상황 설명: VLM 후보
- 추론 최적화/운영: 필요성이 검증되면 ONNX, TensorRT, API, Docker 검토
- 로컬 목표: NVIDIA RTX 3080 (VRAM·실행 환경·속도는 확인 전)

**YOLO/BoT-SORT/VLM을 당연한 구성요소로 확정하지 않는다.** 선행연구와 실제 데이터, 정확도·속도·자원·라벨링 비용을 보고 최소 기술을 선정한다.

## 바로 시작하는 방법
1. [Codex 작업 규칙](AGENTS.md), [프로젝트 목표](docs/PROJECT_CHARTER.md), [작업 계획](docs/WORK_PLAN.md)을 읽는다.
2. [첫 Codex 작업 지시](docs/CODEX_FIRST_TASK.md)에 따라 샘플 6~10개의 접근성·라벨·행동을 감사한다.
3. [데이터 감사 템플릿](docs/data/SAMPLE_AUDIT_TEMPLATE.md)을 복제하여 `docs/data/SAMPLE_AUDIT.md` 작성.
4. 사람이 실제 영상을 검수하고 **Go / Conditional Go / No-Go** 결정을 내린다.
5. 첫 이벤트·평가 단위를 확정한 뒤 [ADR](docs/decisions/ADR-0001-research-first.md)에 근거를 쌓아 모델을 선정한다.

## 기록 위치
| 문서/폴더 | 목적 |
| --- | --- |
| [PROJECT_CHARTER](docs/PROJECT_CHARTER.md) | 목표·제약·성공 기준 |
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
