# EXP-0022 — YOLO26m-Pose 공식 public API 복구

2026-10-29. BATCH-0004의 별도 실험이며 [복구 계획](BATCH-0004-yolo26-pose-recovery-plan.md)과 [ADR-0021](../decisions/ADR-0021-yolo26-public-predict.md)을 따른다. **현재는 구현·CPU 사전검증 단계이며 GPU 실행/실제 Results·관절 품질은 아직 미측정이다.** EXP-0021의 두 실패/한도 종료는 그대로 보존한다.

## 목적·데이터·평가 단위

같은 공식 YOLO26m-Pose를 public `YOLO.predict`로 정상 실행해 원본 030:90/007:64의 실제 결과와 원본/pose overlay 두 장을 우선 확보한다. 사람별 정밀 GT가 없어 모델 개수/confidence를 사람 복원·정확도로 해석하지 않는다. 기존 EXP-0019/0021의 정확한 267개 native PTS/RGB는 11 diagnostic과 5개 사전 고정 구간에서 deduplicate된 개발 입력이다. 10fps 이하, 새 프레임·crop·라벨 개정은 없다. 첫 stage는 030_090/007_064뿐이다. 나머지265는 실제 사람/관절 usefulness 검수와 총괄의 별도 stage 허가 전 미실행이다.

q04의 문 잡기/발 올림과 완료 미관찰, 030 여러 인물의 개별 완료 미확정, 접근-only 비교, 004 줄 넘기 별도 domain을 유지한다. 031의 종료 관찰을 030으로 전이하지 않는다. 자료 편중·사람별 GT 부족으로 accuracy/precision/recall/F1/FPR/시간당 오탐은 null이다. 규칙·tracker·VLM 결합은 미실행이다.

## 환경·모델·실행 조건

기존 Python3.10.12 / Torch2.5.1+cu124 / Torchvision0.20.1+cu124 / Ultralytics8.4.192 격리 환경과 RTX3080을 재사용한다. 새 설치/env/weight 다운로드는 없다. 체크포인트 49,036,866bytes, SHA256 `2fbf16367022256a226035695c5c389384c6706e8bb8ab8fcd0e7976f05443c4`. AGPL-3.0·로컬 연구 한정이며 원본/사람좌표/weights/raw Results/미디어는 Git 제외다.

full-frame/연속 BGR ndarray/640 square/rectFalse/FP32(public quantizeNone)/batch1/conf0.25/nmsFalse/max_det300/noaugment, save/show/verbose/streamFalse다. 전체 kwargs는 새 command/manifest에 고정한다. 공식 predictor가 fuse=True 및 최초 warmup을 수행하는 변경을 기록한다. warmup의 모델 forward와 synthetic random-box NMS는 두 sample prediction 수에 포함하지 않는다. Results 좌표는 원본 좌표로 읽고 다시 변환하지 않는다.

CPU preflight는 CUDA 숨김과 가중치 미로딩으로 실제 installed config/signature·공식 preprocess·synthetic Results·lease/queue 보존·profiler 오류 회귀를 검사한다. 성공 테스트는 실제 모델 호환성/관절 품질을 보증하지 않는다. source commit은 총괄이 작성하고, exact source freeze·독립 Astra review·총괄 authorization 후 기존 단일 queue에서만 GPU를 실행한다.

```bash
CUDA_VISIBLE_DEVICES='' .venv-pose-batch03/bin/python -m unittest tests_orca.test_batch04_pose tests_orca.test_queue -v
CUDA_VISIBLE_DEVICES='' .venv-pose-batch03/bin/python -m batch04_pose.preflight
# 총괄의 smoke 한정 execution-authorization 이후에만 실행
.venv-pose-batch03/bin/python -m batch04_pose.cli enqueue --stage smoke
.venv-pose-batch03/bin/python -m batch04_pose.cli run-once
```

실제 명령에는 새 로컬 설정/캐시 디렉터리를 사용한다. canonical Run/Task/Dispatch, free6144MiB gate, 상속 GPU lock·실제 parent/child·source/config/input/weights/environment 해시를 유지한다. 부분 성공은 보존하고 자동 재생성/재시도를 제공하지 않는다. 오류 재시도는 새 배치 최대1회이며 CPU 수정·독립 리뷰·새 freeze가 먼저다. 0 people은 정상 API 반환이다.

## 결과 — 실행 후 채움

| 판정 | 현재 근거 |
| --- | --- |
| CPU 계약 | 테스트/로컬 audit 진행, source freeze/검토 대기 |
| 실제 GPU 기술 실행 | 미실행 |
| 실제 native Results/원본-overlay 두 장 | 아직 없음 |
| 사람·관절 시각 품질 | 미검수 |
| remaining265/시간 행동 | 미실행/미측정 |
| 독립 결과 검토·웹·GitHub | 총괄이 각자 확인 예정 |

로딩은 YOLO 생성 시간, predictor deepcopy/fuse/CUDA 준비는 첫 predict setup 시간이다. 공식 preprocess tensor는 로컬 저장하며 warmup/network 시도와 정상 반환, Results.speed, public predict wall, run-entry wall을 분리한다. profiler·동기화·tensor capture 오버헤드를 포함한 시간을 순수 benchmark로 쓰지 않는다. allocator peak와 device-wide sampling은 범위가 다르다. 실측 전 FPS/VRAM/지연을 만들지 않는다.

완료 후 새 public 집계와 costs/metrics는 records/EXP-0022에만 작성한다. 원본·overlay/raw Results/좌표/tensor·runtime/receipt는 로컬 전용이다. 코드·CPU 성공·기술 실행·시각 품질·행동 성능·전달을 분리하고, batch 종료 뒤 새 GPU 작업을 시작하지 않는다.
