# EXP-0022 — YOLO26m-Pose 공식 public API 복구

2026-10-29. BATCH-0004의 별도 실험이며 [복구 계획](BATCH-0004-yolo26-pose-recovery-plan.md)과 [ADR-0021](../decisions/ADR-0021-yolo26-public-predict.md)을 따른다. **공식 API smoke 2/2가 정상 반환했고 실제 native Results와 원본/overlay 비교 두 장을 저장했다. 030_090은 정상 0명, 007_064는 2개 person row/23개 retained joint estimate다. 030의 기존 사용자 확인 사람/올라탐에 대한 관절 근거가 없어 remaining265는 미실행으로 보류했다.** EXP-0021의 두 실패/한도 종료는 그대로 보존한다.

## 목적·데이터·평가 단위

같은 공식 YOLO26m-Pose를 public `YOLO.predict`로 정상 실행해 원본 030:90/007:64의 실제 결과와 원본/pose overlay 두 장을 우선 확보한다. 사람별 정밀 GT가 없어 모델 개수/confidence를 사람 복원·정확도로 해석하지 않는다. 기존 EXP-0019/0021의 정확한 267개 native PTS/RGB는 11 diagnostic과 5개 사전 고정 구간에서 deduplicate된 개발 입력이다. 10fps 이하, 새 프레임·crop·라벨 개정은 없다. 첫 stage는 030_090/007_064뿐이다. 나머지265는 총괄이 실제 pose 근거 부족으로 **enqueue하지 않고 보류**했다. 007의 관절 대응은 별도 한 묶음의 사람 검수 답변 대기이며 검수 전 정확성을 확정하지 않는다.

q04의 문 잡기/발 올림과 완료 미관찰, 030 여러 인물의 개별 완료 미확정, 접근-only 비교, 004 줄 넘기 별도 domain을 유지한다. 031의 종료 관찰을 030으로 전이하지 않는다. 자료 편중·사람별 GT 부족으로 accuracy/precision/recall/F1/FPR/시간당 오탐은 null이다. 규칙·tracker·VLM 결합은 미실행이다.

## 환경·모델·실행 조건

기존 Python3.10.12 / Torch2.5.1+cu124 / Torchvision0.20.1+cu124 / Ultralytics8.4.192 격리 환경과 RTX3080을 재사용한다. 새 설치/env/weight 다운로드는 없다. 체크포인트 49,036,866bytes, SHA256 `2fbf16367022256a226035695c5c389384c6706e8bb8ab8fcd0e7976f05443c4`. AGPL-3.0·로컬 연구 한정이며 원본/사람좌표/weights/raw Results/미디어는 Git 제외다.

full-frame/연속 BGR ndarray/640 square/rectFalse/FP32(public quantizeNone)/batch1/conf0.25/nmsFalse/max_det300/noaugment, save/show/verbose/streamFalse다. 전체 kwargs는 새 command/manifest에 고정한다. 공식 predictor가 fuse=True 및 최초 warmup을 수행하는 변경을 기록한다. warmup의 모델 forward와 synthetic random-box NMS는 두 sample prediction 수에 포함하지 않는다. Results 좌표는 원본 좌표로 읽고 다시 변환하지 않는다.

CPU preflight는 CUDA 숨김과 가중치 미로딩으로 실제 installed config/signature·공식 preprocess·synthetic Results·lease/queue 보존·profiler 오류 회귀를 검사한다. 성공 테스트는 실제 모델 호환성/관절 품질을 보증하지 않는다. source commit은 총괄이 작성하고, exact source freeze·독립 Astra review·총괄 authorization 후 기존 단일 queue에서만 GPU를 실행한다.

```bash
CUDA_VISIBLE_DEVICES='' YOLO_CONFIG_DIR="$PWD/runtime/BATCH-0004/ultralytics-settings" MPLCONFIGDIR="$PWD/runtime/BATCH-0004/matplotlib" .venv-pose-batch03/bin/python -m unittest tests_orca.test_batch04_pose tests_orca.test_queue -v
CUDA_VISIBLE_DEVICES='' YOLO_CONFIG_DIR="$PWD/runtime/BATCH-0004/ultralytics-settings" MPLCONFIGDIR="$PWD/runtime/BATCH-0004/matplotlib" .venv-pose-batch03/bin/python -m batch04_pose.preflight
# 총괄의 smoke 한정 execution-authorization 이후에만 실행
.venv-pose-batch03/bin/python -m batch04_pose.cli enqueue --stage smoke
.venv-pose-batch03/bin/python -m batch04_pose.cli run-once
```

실제 명령에는 새 로컬 설정/캐시 디렉터리를 사용한다. canonical Run/Task/Dispatch, free6144MiB gate, 상속 GPU lock·실제 parent/child·source/config/input/weights/environment 해시를 유지한다. 부분 성공은 보존하고 자동 재생성/재시도를 제공하지 않는다. 오류 재시도는 새 배치 최대1회이며 CPU 수정·독립 리뷰·새 freeze가 먼저다. 0 people은 정상 API 반환이다.

## 실제 실행·보존 근거

총괄이 먼저 source commit `7c281e34bc12bd9b53f7cebe73f313f801f870e2`의 15개 Git object byte/작업트리 hash를 고정했다. CUDA 숨김의 구현16+기존 queue14, 총30 CPU 테스트가 통과했고 독립 Astra의 별도15 계약 테스트와 exact-source preflight PASS를 받았다. 그 뒤 총괄은 smoke만 명시 허가했다. CPU 준비 성공을 실제 추론 성공으로 미리 표현하지 않았다.

기존 Run `run_3d23462a014a`, Task `task_5df19346a61c`, Dispatch `ctx_9a8df3d90186`의 canonical queue에서 job `c99e0da0610348e7a74bf38d66d19801` / attempt `6509c805b40e4d7a8137f770cfa04a05`가 **succeeded**다. load 전 free VRAM 7,864MiB로 6,144MiB gate를 통과했다. 모델 생성1회, public predict2회/실제 native Results2개, sample model forward 시도2/정상반환2, 공식 warmup model forward 시도1/정상반환1, 오류0/retry0다. 새 모델/weight/env·학습은0이다. warmup은 별도이고 두 sample의 재추론은 없다.

실행 source digest는 `1f33d6f8d9e4d1bf92645437b1d04d8abb99ccfeb6c265552c92328767f505a2`, 새 manifest SHA256은 `dcd6501ef11cd8b7a06aeb2d0bf6c303acb6665ac65dc3a4f6e5d45bba8c4c98`, 실제 summary SHA256은 `84905e3841a7394f0e3a0e214f7298746f33226fdaa3fafb703c3ded40cf5cde`다. 두 native Results, 두 실제 preprocess tensor, 원본/overlay/비교 PNG와 관측 JSON의 모든12개 artifact hash를 대조했다. 원래39 jobs/39 attempts의 모든 row·70개 기존 public source/report/config/record bytes와 전체 고정 입력/설치 환경 해시는 보존됐다. smoke 종료 뒤 추가 GPU 실행은 하지 않았다.

| 입력 | 정상 native Results | person row | retained joint estimate | 품질/확대 판단 |
| --- | --- | ---: | ---: | --- |
| 030_090 (원본90초) | boxes(0,6), keypoints(0,17,3) | 0 | 0 | 기존 사용자 확인 사람/올라탐에 pose 근거 없음; empty는 기술 오류가 아님 |
| 007_064 (원본64초) | boxes(2,6), keypoints(2,17,3) | 2 | 23 | 원본과 관절 실제 대응은 미검수; row는 사람 ID가 아님 |

두 원본/overlay 비교 이미지는 **실제 반환 Results에서 생성**했다. 030의 empty 출력에서는 원본과 overlay PNG가 같은 hash이며 가짜 skeleton을 만들지 않았다. 007의 23개는 confidence≥0.5·유한·원본범위 내·(0,0)이 아닌 추정치 수로, 17×2 중 실제 관절 GT 23개나 사람 복원 성공이라는 뜻이 아니다. 두 장 모두 로컬 전용이며 cloud 이미지 도구로 열거나 업로드하지 않았다. 기존 사용자 관찰을 재사용한 030과 새 007의 관절 검수를 구분한다.

## 비용과 측정 범위

| 실측 | 값 | 범위 |
| --- | ---: | --- |
| YOLO checkpoint CPU constructor | 0.221487초 | CPU 모델 생성/체크포인트 읽기와 종료 CUDA sync, 첫 predictor 준비 제외 |
| 최초 공식 setup_model | 0.408727초 | deepcopy/fuse/CUDA backend 준비, profiler/동기화 포함 |
| 최초 공식 warmup | 0.425134초 | 실제 preprocess tensor의 모델 forward + synthetic random-box NMS |
| 위 warmup 내부 network predict | 0.344752초 | warmup에 포함되는 중첩 관측; 별도 합산하지 않음 |
| run-entry wall | 6.463836초 | lease/input 검증 포함, interpreter startup/final summary save 제외 |
| allocator allocated / reserved peak | 204,846,592 / 228,589,568 bytes | import 후 constructor 전 reset부터 마지막 frame, 장치 전체 VRAM 아님 |

| 입력 | Results preprocess | Results inference | Results postprocess | public predict wall |
| --- | ---: | ---: | ---: | ---: |
| 030_090 | 34.144559ms | 12.631883ms | 20.207677ms | 0.909371초 |
| 007_064 | 7.294324ms | 13.310806ms | 0.688229ms | 0.027484초 |

두 실제 preprocess tensor는 모두 **CUDA0 / float32 / (1,3,640,640)** 이고 공식 backend의 pt/end2endTrue/fp16False/kpt_shape17×3/stride32/fusedTrue/done_warmupTrue를 관측했다. 이번은 과거 unfused/no-warmup 경로와 다르다. setup/warmup의 profile return값 None은 해당 메서드의 정상 계약이며 실패를 뜻하지 않는다. model forward에서는 시도와 non-None 정상 반환을 따로 계수한다.

**측정은 중첩되며 합산 가능한 독립 단계가 아니다.** 공식 Results.speed는 warmup을 제외하지만, preprocess에는 관측기의 실제 tensor CPU copy/save(각11.586/6.330ms)와 동기화가 포함된다. 다른 단계도 Python profiler 영향을 포함한다. public predict wall에는 첫 setup/warmup/관측 저장이 포함되고, frame wall은 RGB 검증·native Results/PNG/JSON 저장도 포함한다. queue attempt wall과 장치 전체 sampled used/free는 [costs](../../records/EXP-0022/costs.json)에 별도 저장했다. 다른 GPU process를 포함하는 device sampling과 PyTorch allocator peak를 혼동하지 않는다. 두 장의 시간으로 일반 FPS/지연·실시간성·행동 성능을 주장하지 않는다.

## 판정·재현·남은 작업

- 기술 실행: **성공**, public API2회/Results2개, 오류0/retry0.
- 사람·관절: 030은 pose 근거 부족, 007은 **미검수**. bbox 개수/confidence만으로 정합성 성공을 선언하지 않는다.
- remaining265·시간 행동 구분: **미실행/미측정**, 총괄이 확장을 보류했다. 규칙·tracker·VLM 결합 없음.
- 독립 검토: 실행 전 exact-source PASS, 실제 출력과 최종 report/metrics byte 검토는 독립 리뷰 문서/총괄 전달 기록에 분리한다.
- 웹·GitHub: 총괄이 보고서/graph/두 이미지 실제 표시와 remote byte를 각각 검증한다. 이 실험 문서 자체로 전달 완료를 선언하지 않는다.

[comparison](../../records/EXP-0022/comparison.json), [costs](../../records/EXP-0022/costs.json), [metrics](../../records/EXP-0022/metrics.json)는 실제 저장 결과에서 가져온 비식별 집계다. [CPU builder](../../records/EXP-0022/build_summary.py)는 frozen inference source 15개 밖에 두어 추론 provenance를 바꾸지 않는다. `PYTHONPATH=. python3 records/EXP-0022/build_summary.py`는 기존 로컬 결과/queue/environment/hash만 검증하고 공개 집계를 재생성하며 모델을 구성/추론하거나 미디어를 시각화하지 않는다. raw Results/사람 좌표/미디어·tensor·환경·receipt·절대 로컬 경로는 공개물에 포함하지 않는다.

기존 CV/VLM·공식 라벨·EXP-0021 실패 기록/한도는 유지한다. 정확도/F1/FPR·사람별 완료·위법성은 null/미판정이다. 이번 기술 복구 성공을 행동 성능 충족으로 확대하지 않으며, 더 GPU 작업·retry·모델 변경을 예약하지 않는다. 다음 한 선택은 사용자에게 제시한 새 007 원본/관절 비교의 대응 검수를 기록하는 것이고, 이는 자동 확대 승인이 아니다.
