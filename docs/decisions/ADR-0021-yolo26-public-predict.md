# ADR-0021 — YOLO26m-Pose 공식 public predict 경로 복구

2026-10-29. 상태: **CPU/독립 preflight 후 공식 API smoke2/2 정상 반환, 030 pose 근거 부족으로 확장 보류**. BATCH-0004 / EXP-0022는 [새 승인 계획](../experiments/BATCH-0004-yolo26-pose-recovery-plan.md)의 별도 배치다. EXP-0021의 두 실패와 소스·queue·결과를 바꾸지 않는다.

## 문제와 선택

BATCH-0003의 직접 inner-model 경로는 head 초기화와 지원하지 않는 `visualize` 인자로 실제 예측을 반환하지 못했다. 모델 사람·관절 품질은 미측정이다. 저수준 경로를 다시 보완하는 대신, 동일 Ultralytics 8.4.192의 **공식 `YOLO.predict(source=bgr, **PREDICT_KWARGS)`** 를 사용한다. 다른 모델/환경/weight·학습·성능 튜닝은 대안으로 실행하지 않는다.

기존 `.venv-pose-batch03`, 체크포인트 49,036,866 bytes / SHA256 `2fbf16367022256a226035695c5c389384c6706e8bb8ab8fcd0e7976f05443c4`, 고정 267개 원본 native PTS/RGB와 환경 전체 해시를 그대로 검증한다. 새 manifest는 과거 manifest SHA256 `6ea2fe8d692611f7808b1109a591fedff9cd8c901f13cc43474246324927883d` 및 동일 입력을 연결한다. 이전 추론 구현을 호출하지 않고 CPU provenance 계약만 재사용한다.

## 정확한 공식 API 계약

원본 RGB uint8 H×W×3 배열을 `np.ascontiguousarray(rgb[..., ::-1])`로 BGR ndarray로 변환한다. 허용되지 않는 source 형식/URL/기본 예시 입력을 받지 않는다. 공개 kwargs 전체는 [batch04 command](../../orchestration/batch04_pose_command.py)의 `PREDICT_KWARGS`에 고정한다: imgsz640, rectFalse, batch1, conf0.25, CUDA0, **quantize=None(FP32)**, nmsFalse, max_det300, iou0.7, agnosticFalse, classes[0], augmentFalse, compileFalse, channels_lastFalse, save/save_txt/save_crop/show/verbose/stream/visualizeFalse, embedNone. 8.4.192에서 halfFalse는 deprecated alias이므로 사용하지 않는다.

공식 경로는 `Model.predict → PosePredictor → AutoBackend → PyTorchBackend → BaseModel.predict(augment, embed)`다. `visualize=False`는 유효한 public 설정이며 inner predict로 전달되지 않는다. 직접 forward/head setter/NMS/좌표 변환을 새 추론에 구현하지 않는다. 공식 Results의 boxes.data(N×6)와 keypoints.data(N×17×3)는 이미 원본 좌표다. 재스케일하지 않는다. 명시적 empty N=0는 정상 반환이고 None·행 수/shape 불일치·NaN/Inf·비정상 box는 기술 오류로 분리한다. 낮은 confidence/좌표 범위 밖/(0,0) 관절은 raw 값을 보존하고 unknown으로 표시한다. confidence≥0.5는 정확성 GT가 아니다.

## 공식 처리 경로 차이와 측정

공식 setup_model은 deepcopy 후 end2end 선택을 **fuse 전에** 수행하며 fuse=True를 사용한다. 첫 preprocess 입력으로 공식 warmup이 실행된다. CUDA PyTorch warmup은 모델 forward 1회와 random-box synthetic NMS를 수행한다. 따라서 sample의 end2end NMS-free 처리와 전체 실행의 NMS 호출0을 혼동하지 않는다. 이 경로는 EXP-0021의 unfused/no-warmup 경로와 다르다.

Python profiler는 `inspect.unwrap`으로 고유한 공식 메서드 body를 관측한다. 모델 알고리즘을 대체하지 않는다. 실제 preprocess tensor의 shape/dtype/device/hash·로컬 NPY, warmup/network의 시도/정상 반환을 별도 기록한다. setup/warmup/network wall은 동기화·profiler 영향을 포함한다. Results.speed, public predict wall, run-entry wall, allocator peak와 장치 전체 샘플은 다른 범위다. load는 YOLO 생성이며, predictor deepcopy/fuse/CUDA 이동은 첫 predict setup에 포함된다. 예외의 profile return(None)은 완료 forward로 세지 않는다.

## 실행 게이트·공개 범위

CPU에서 설치된 config와 전체 public/downstream signature를 검사하고 synthetic BGR·공식 preprocess·Results empty/unknown/불일치·오류와 profiler decorator/exception 회귀를 검증한다. source commit/해시와 독립 검토 뒤 총괄의 smoke 한정 허가를 받아 기존 canonical queue·실제 parent/child·상속 lock·Run/Task/Dispatch·free VRAM≥6144MiB에서만 모델을 구성한다. socket transport/DNS를 차단하며 새 다운로드를 하지 않는다.

030_090/007_064 각각 public predict 1회 후 실제 native Results와 로컬 원본/overlay 비교 두 장을 먼저 보존한다. input-start marker와 queue attempt/key 예산은 부분 성공 재생성을 막는다. 오류 correction은 자동 실행하지 않고 CPU 수정·독립 리뷰·새 freeze 후 배치의 최대1 retry 한도에서 별도 처리해야 한다. remaining265는 exact smoke lineage/artifact 해시와 실제 사람의 관절 usefulness 검수 receipt를 가진 총괄 허가 없이는 실행할 수 없다. 규칙/추적은 구현하지 않는다.

새 소스의 SPDX는 AGPL-3.0-only이며 미수정 upstream은 [공식 v8.4.192](https://github.com/ultralytics/ultralytics/tree/v8.4.192)와 기존 ADR-0020의 라이선스/출처를 따른다. 연구·기술 실험 밖의 상용/네트워크 통합은 별도 검토가 필요하다. 무라이선스 제3자 구현은 복제하지 않는다. 영상·이미지·raw 좌표·tensor·Results·weights/runtime/receipts는 로컬만 둔다. 공개물은 코드·비식별 집계·해석이다. 기본 CV/VLM·공식 라벨·accuracy/F1/FPR·위법성 판단을 바꾸지 않는다.

판단을 뒤집을 근거는 테스트/개수가 아닌 실제 public API 반환, 원본과 관절의 사람 검수 및 필요한 시간·경계 근거다. 기술 성공·시각 품질·행동 성능·독립 검토·웹/GitHub 전달을 각각 판정한다.

공식 코드 근거: [Model.predict](https://github.com/ultralytics/ultralytics/blob/v8.4.192/ultralytics/engine/model.py), [predictor](https://github.com/ultralytics/ultralytics/blob/v8.4.192/ultralytics/engine/predictor.py), [PyTorch backend](https://github.com/ultralytics/ultralytics/blob/v8.4.192/ultralytics/nn/backends/pytorch.py), [AutoBackend warmup](https://github.com/ultralytics/ultralytics/blob/v8.4.192/ultralytics/nn/autobackend.py), [pose Results](https://github.com/ultralytics/ultralytics/blob/v8.4.192/ultralytics/models/yolo/pose/predict.py). 설치 파일의 해시와 signature는 로컬 CPU audit에 남긴다.

## 실제 관측에 따른 결정

source `7c281e34bc12bd9b53f7cebe73f313f801f870e2`의 smoke는 정상 Results2개/오류0/retry0를 남겼다. 공식 fuseTrue와 첫 warmup1회+sample forward2회를 실제 관측했다. 030_090은 정상 empty로 person0, 007_064는2행/retained23개이며 후자는 원본 대응 미검수다. 기존 사용자 확인 사람이 있는030에서 pose 근거를 얻지 못했으므로 총괄은 remaining265/규칙/추적을 보류했다. 이 관측은 public API 선택의 기술 복구 근거이지만 사람·관절·행동 품질 채택 근거는 아니다. 새 모델이나 threshold 변경/empty 재시도는 실행하지 않는다. 최종 측정·범위는 [EXP-0022](../experiments/EXP-0022-yolo26-public-predict.md)를 따른다.
