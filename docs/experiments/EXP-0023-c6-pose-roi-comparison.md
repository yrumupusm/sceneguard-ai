# EXP-0023 — YOLO26m-Pose 전체화면 / 기존 C6 고정 ROI 비교

2026-10-29, Sol high 실행 담당. BATCH-0005의 별도 실험이며 [승인 계획](BATCH-0005-c6-pose-roi-comparison-plan.md), [ADR-0022](../decisions/ADR-0022-c6-pose-roi.md)를 따른다. 상태: CPU preflight 준비, 실제 GPU 실행 전.

기존 EXP-0022에서 030:90 full은 정상 0행이었다. 고정 배경 ROI에서 입력상 사람 크기가 커지면 관절 근거를 얻을 수 있다는 가설만 비교한다. 기존 native PTS 84/90/94초 세 RGB를 그대로 사용하며 사람별 정밀 GT는 없다. 개발용 같은 원본 세 시점이며 독립 카메라/최종 행동 평가가 아니다. accuracy/precision/recall/F1/FPR·완료/위법성은 null이다.

기존 Python3.10.12/Torch2.5.1+cu124/Torchvision0.20.1+cu124/Ultralytics8.4.192·RTX3080·공식 YOLO26m-Pose SHA256 `2fbf16367022256a226035695c5c389384c6706e8bb8ab8fcd0e7976f05443c4`를 재사용한다. 새 환경/weight 다운로드/학습/VLM은 없다. AGPL-3.0 연구 조건을 유지한다.

고정 C6 [0.28,0.20,0.75,0.80] → RGB[216:864,537:1440],903×648. RGB→연속 BGR 변환과 공식 public kwargs 전체는 batch04의 검증된 코드를 읽기 전용으로 재사용한다. 640/FP32/rectFalse/conf.25/nmsFalse/batch1. ROI native local 결과의 unknown 여부를 먼저 판별하고 원본좌표 표현에는 (+537,+216)을 한 번만 적용한다. full은 무변환이다. local/raw/unknown도 보존한다.

순서는 030_090_C6 → 030_084_full → 030_084_C6 → 030_094_full → 030_094_C6다. 030_090_full은 EXP-0022 Results/artifact hash를 검증해 재사용하며 새 예측은 금지한다. 정상 empty여도 84/94는 계속한다. 기술 예외는 중단·부분 보존하고 자동 retry는 없다.

```bash
CUDA_VISIBLE_DEVICES='' YOLO_CONFIG_DIR="$PWD/runtime/BATCH-0005/ultralytics-settings" MPLCONFIGDIR="$PWD/runtime/BATCH-0005/matplotlib" .venv-pose-batch03/bin/python -m unittest tests_orca.test_batch05_pose tests_orca.test_queue -v
CUDA_VISIBLE_DEVICES='' YOLO_CONFIG_DIR="$PWD/runtime/BATCH-0005/ultralytics-settings" MPLCONFIGDIR="$PWD/runtime/BATCH-0005/matplotlib" .venv-pose-batch03/bin/python -m batch05_pose.preflight
# source commit + 독립 검토 + 총괄의 exact authorization 이후에만:
.venv-pose-batch03/bin/python -m batch05_pose.cli enqueue --stage comparison
.venv-pose-batch03/bin/python -m batch05_pose.cli run-once
```

실제 비용/수치/실패는 실행 후 저장 결과에서 기록한다. setup/fuse/최초 공식 warmup, 5개 새 예측, 1개 cached 결과를 분리하고 중첩 계측을 합산하지 않는다. 세 시점의 native 원본/전체/ROI triptych는 로컬만 보관한다. 이미지 생성·decode와 실재 관절 정합성 검수는 별개이며 사용자 검수 전 미확정이다. ROI 절단/가림/누락·중복·비사람 의심도 검수 전 확정하지 않는다. C6 calibrated는 실제 fence top/far-side의 교정이 아니다.

기술 실행·사람 관절 품질·행동 성능·독립 review·기존 웹/GitHub 전달은 따로 기록한다. 추가 조건/267 처리/추적/규칙/결합·새 UI는 없다. 기존 결과와 실패 원본을 보존하며 이번 다섯 조건 뒤 새 GPU 작업을 자동 진행하지 않는다.
