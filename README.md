# SceneGuard

**EXP-0029:** 기존 관측을 보존한 사후 tracklet 연결을 실제030·007연속구간에서 비교했습니다.030연결0,007연결1은 같은raw ID의 공백복원이며 넘기 전후 연결 개선은 확인되지 않았습니다. 원본/기존ID/연결ID 비교4영상과 실패 사례를 남기고 기본 적용을 보류합니다. [실제 결과](docs/experiments/EXP-0029-results.md) · [전달 확인](docs/experiments/EXP-0029-delivery.md).

**EXP-0026:** YOLO26m Detection의 첫20epoch 탐색 학습을 완료했습니다(약3분44초). C6의90·94초 검출0개가 유지되고84초는3→1개로 감소해 적용을 보류합니다. 학습 실행 성공과 실제 검출 개선을 구분하며 미검수 라벨의 의미 검수는 남아 있습니다. 기존 모델 기본값을 유지합니다. [실험 결과](docs/experiments/EXP-0026-exploratory-person-finetune.md) · [고정 계획](docs/experiments/EXP-0026-exploratory-training-plan.md).

**BATCH-0006:** C6 ROI의 입력 해상도만640→960으로 바꾼 세 장 비교를 완료했습니다. 사용자 검수상84초는 양호하고94초 문 위 사람을 새로 포착했지만,90초는 출력0개로 핵심 누락이 지속됩니다. 기본 적용·행동 판단 확대는 보류합니다. [종합 결과](docs/experiments/BATCH-0006-summary.md) · [실험 보고서](docs/experiments/EXP-0025-c6-pose-960.md) · [전달 기록](docs/experiments/BATCH-0006-delivery.md).

**BATCH-0004:** 공식 YOLO.predict로 두 프레임의 실제 추론과 관절 비교 이미지 생성에 성공했습니다. 030의90초는 사람 후보0개로 관절 근거를 얻지 못했고,007의64초는2개 후보/관절 추정23개로 실제 위치 검수는 별도입니다. 나머지265프레임·행동 규칙·기본 교체는 보류합니다. [종합 결과](docs/experiments/BATCH-0004-summary.md) · [전달 기록](docs/experiments/BATCH-0004-delivery.md).

**BATCH-0003 종료:** YOLO26m-Pose의 두 smoke가 실행 어댑터 호환성 오류로 실패해 재시도 한도를 소진했습니다. 관절 출력0개로 품질·행동 구분은 미측정이며 기존 모델을 유지합니다. [종합 결과](docs/experiments/BATCH-0003-summary.md) · [전달 기록](docs/experiments/BATCH-0003-delivery.md).

**CCTV 행동 후보와 근거 구간을 저장하는 로컬 프로토타입 — MVP-0001 코드·실제 전체 영상 실행 완료, 행동 성능 검증·채택 보류**

SceneGuard는 AI Software Engineer 직무 포트폴리오를 위한 실험 프로젝트다. 공개된 CCTV 영상에서 **사람의 출입 경계 통과/넘기 행동**을 감지하고, 카메라별 경계 설정·오탐·감지 시점·실행 비용을 재현 가능하게 평가하는 것이 첫 목표다. 법적 **무단침입이나 출입 권한을 영상만으로 확정하지 않는다.**

최신 모델 대안 비교는 [BATCH-0002 종합 결과](docs/experiments/BATCH-0002-summary.md)를 따른다. [실제 입력 감사](docs/experiments/EXP-0018-input-audit.md), [RF-DETR와 기존 FCOS 캐시 비교](docs/experiments/EXP-0019-cv-comparison.md), [Qwen 4B NF4와 기존 2B BF16 비교](docs/experiments/EXP-0020-vlm-comparison.md)를 분리 기록한다. 새 모델은 기존 MVP에 자동 연결하지 않는다. q/v는 개발 자료이며 출력 개수·파싱 성공·GPU 실행 가능성을 행동 정확도로 읽지 않는다. [전달 기록](docs/experiments/BATCH-0002-delivery.md)에서 GitHub 게시와 실제 로컬 화면 확인을 구분한다.

## MVP-0001 구현과 평가 범위

기존 CV 결과와 전체 화면 Qwen을 보존하고, 같은 Qwen에 **배경 기준 고정 감시 영역**을 입력하는 구성을 비교했다. EXP-0013은 기존 가중치를 재사용했다. 원본 처음부터 끝까지 5초 창/2.5초 간격/약2fps로 처리하며, CV 후보가 없어도 분석한다. 시간창→행동/판단 불가→겹치는 후보 묶음→원본 근거 구간 저장을 별도 `mvp/` 경로로 구현했다. 기존 CV·경계 규칙·웹 기능은 보존한다.

**원본 3개의 실제 전체 영상 추론으로 이벤트 후보·근거를 생성했고, 저장 출력의 소규모 평가와 사용자 라벨 개정까지 완료했다. EXP-0015에서 q 6개는 no-crossing 5개, attempt/progress positive 1개, primary positive 0개다. 비시도 장면을 후보로 만들고 시도를 놓치는 문제가 남아 행동 성능·운영 채택은 보류한다.** [EXP-0013 실행 보고서](docs/experiments/EXP-0013-mvp-comparison.md), [EXP-0015 사용자 라벨 개정](docs/experiments/EXP-0015-user-label-revision.md), [종합 결과](docs/experiments/MVP-0001-summary.md), [전달 기록](docs/orchestration/MVP-0001_DELIVERY.md)에서 기능·평가·게시·화면 검증을 구분한다. EXP-0014 당시 음성 정답이 없었던 상태는 과거 이력이다. q06의 사람/사건 없음은 030의 155–160초에만 적용하며 031의 종료 미완료 관찰을 030에 옮기지 않는다. 테스트 통과나 candidate 출력은 행동 정확도 또는 무단침입 판정이 아니다. [실행 계약](docs/design/MVP_LOCAL_CLI.md), [선택 이유](docs/decisions/ADR-0016-mvp-fixed-camera-region.md)를 따른다. 기존 차단·실행·평가 보고서는 보존한다.

```bash
# 저장소 루트, 기존 환경과 공통 큐를 사용한다.
MVP_PYTHON="$PWD/.venv-vlm/bin/python"
MVP_QUEUE_RUNTIME="$HOME/dev/sceneguard-orca-lab/runtime/orca-lab/gpu-queue"
"$MVP_PYTHON" -m mvp.cli --help
"$MVP_PYTHON" -m mvp.cli --runtime "$MVP_QUEUE_RUNTIME" status
```

실제 작업 등록에는 살아 있는 기존 Orca Run/Task/Dispatch와 고유 job key가 필요하다. [CLI 문서](docs/design/MVP_LOCAL_CLI.md)의 `enqueue` 뒤 동일 큐의 `run-once`를 사용한다. GPU 여유가 고정 기준에 못 미치면 모델을 로드하지 않는다. 직접 실행·자동 반복·사건 시각 인수는 제공하지 않는다. 카메라 예시는 [mvp0001_cameras.json](configs/mvp0001_cameras.json), 입력3개는 [mvp0001_sources.json](configs/mvp0001_sources.json)이다. 이 첫 실행기는 해당 로컬 자료와 환경에 고정된 개발용이며 임의의 새 CCTV를 검증한 범용 도구가 아니다.

로컬 결과는 실행별 `windows.jsonl`, `emissions.jsonl`, `events.jsonl`, 창별 원문/측정치, `evidence/` 원본 구간이다. 후보 시각·마지막 입력 PTS·최초 출력 시각·후속 병합/근거 저장 시각을 구분한다. `indeterminate`, `insufficient_data`, `parse_failed`는 정상 판정이 아니다. 모델 설명과 후보 수는 정답·성공 건수가 아니다. 모든 미디어·원시 응답·캐시는 Git에서 제외한다.

이하 기존 CV 실험 이력은 보존한다.

첫 로컬 CV baseline을 구현·진단했다. **SSDLite320에서 작은/가려진 사람 검출 누락이 확인돼 메인 모델 채택은 보류**한다. 결과·처리 속도·재현 명령은 [EXP-0001](docs/experiments/EXP-0001-phase2a-cv-baseline.md), 실행 방법은 [CLI 문서](docs/design/CV_BASELINE_CLI.md)에 기록했다. 최종 precision/recall/F1·시간당 오탐률은 정답 검수 전이므로 산출하지 않았다.

추가로 **FCOS COCO_V1**을 동일 네 짧은 구간에서 비교했다. 실제 사람 일부를 새로 검출했지만 누락·중복·배경 오검출 의심과 연결 실패가 남아 메인 채택은 보류한다. 실측 비교와 다음 작업: [EXP-0002](docs/experiments/EXP-0002-fcos-detector-comparison.md), [ADR-0008](docs/decisions/ADR-0008-fcos-detector-comparison.md). 모델과 입력 크기가 함께 바뀐 결과이며 해상도 단독 효과가 아니다.

같은 FCOS 캐시로 **IoU / ByteTrack high-only / low 2차 연결**도 비교했다. 일부 실제 사람의 연결이 개선됐지만 중복·배경 track과 부분 신체 기반 경계 후보 오류가 남아 기본 tracker 교체는 보류한다. [EXP-0005](docs/experiments/EXP-0005-bytetrack-cache-comparison.md)에 재현·연속 검수·실패를 기록했다. 검출 재추론이나 새 가중치 다운로드는 없었다.

## 초기 결정 이력 (2026-10-27)
- **첫 MVP 방향 잠정 채택:** 학교 등 고정형 CCTV에서 카메라별 감시선/ROI를 지정해 **출입 경계 통과·넘기 이벤트 후보를 검토하는 시스템**. [ADR-0004](docs/decisions/ADR-0004-boundary-crossing-cctv-mvp.md).
- **현재 데이터 후보:** [AI-Hub 71850 지능형 관제 서비스 CCTV 영상 데이터](https://aihub.or.kr/aihubdata/data/view.do?dataSetSn=71850)의 **침입 범주**. 사용자 제공 전체 장면 미리보기에서 학교 철제 출입구 반복이 확인됨. 특수 사례는 **4번 줄 넘기**, **7번 공원 울타리 넘기**로 구별.
- **검증 완료/보류 구분:** 로컬 Training MP4·JSON 45개 대응, CCTV 10개 소량 감사 및 사용자 행동 검수 기록 완료. **미확정:** 실제 독립 카메라 수, 비이벤트 평가 정답 시간, E01_006 프레임 수 차이(원본 4,006/JSON 4,011), 정밀 사람별 행동 시각, 최종 모델 및 공개 영상 활용권. [사용자 검수](docs/data/AIHUB_INTRUSION_USER_REVIEW.md), [평가 계획](docs/data/AIHUB_INTRUSION_EVALUATION_PLAN.md).
- **최초 승인된 작업(Phase 2A, 완료):** [ADR-0006](docs/decisions/ADR-0006-limited-cv-baseline-prototype.md) 및 [Codex 지시](docs/CODEX_NEXT_TASK.md)에 따라 **사전학습 사람 탐지 1개 → 최소 IoU 연결 → 카메라별 ROI/경계 통과 후보 출력**을 로컬 개발 영상 2~4개에 대해 제한적으로 구현·진단. 모델 재학습/VLM/UI는 보류. G1E 데이터 최종 승인과는 별개.
- **기술 방향:** 공통 사전학습 사람 검출기(SSDLite320 첫 진단 및 FCOS 추가 비교 완료, 메인 채택 보류) + 간단한 인접 IoU 연결 + 카메라별 설정한 ROI/유한 경계선의 양측 움직임 후보. **가상 선 통과는 실제 넘기 시작·완료와 다를 수 있음**. VLM은 baseline 실패/처리비용 검토 이후 판단.
- **장비:** 로컬 RTX 3080 10GB. 첫 진단의 처리 속도·메모리는 EXP-0001에 실측 기록. 정답 기반 정확도는 미평가.

## 왜 이 문제인가
- ACCIDENT 교통 사고 CCTV는 실제 영상·정답 검증에 성공했지만 짧은 **사고 포함 클립** 위주라 정상 구간 오탐 평가에 제약이 있음.
- AI-Hub 침입 영상은 소량 감사에서 약 2~3분 길이임을 확인. 일부 5초 개발창에 사용자 비사건 확인이 있지만 연속 운영 음성 시간과 독립 표본은 충분하지 않아 시간당 오탐률을 산출하지 않는다.
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
