# ADR-0008 — FCOS ResNet50-FPN 한 모델 추가 비교

- 2026-10-27 / 사용자 승인 범위의 **실험용 선택**, 최종 메인 모델 채택 아님.
- 기존 [ADR-0007](ADR-0007-phase2a-detector.md), [EXP-0001](../experiments/EXP-0001-phase2a-cv-baseline.md) 보존. 기존 네 smoke 구간·ROI·추적·score 0.5 유지. 학습/VLM/고급 tracker/UI 없음.

## 후보 비교 — 공식 문서/설치된 공식 버전 메타데이터

| 후보 | 입력·규모·환경 | 판단 |
| --- | --- | --- |
| **TorchVision FCOS ResNet50-FPN COCO_V1** | 크기 가변 입력, FPN, 약 32.27M parameters / 123.608 MiB 모델 메타데이터. 기존 TorchVision 0.20.1 그대로 사용 | 추가 모델 **하나로 선택**. GPU 실행/메모리는 실측으로 확인 |
| TorchVision Faster R-CNN ResNet50-FPN v2 COCO_V1 | 큰 입력 가능, 약 43.71M / 167.104 MiB. 공식 연산 메타데이터도 FCOS보다 큼 | 첫 대안보다 비용이 커 이번 설치/실행 제외 |
| YOLOv8n | 640급 입력의 경량 대안. 별도 패키지 및 AGPL/Enterprise 조건 검토 필요 | 기존 프레임워크 재사용 우선, 추가 설치하지 않음 |

문서 수치가 CCTV 사람 성능이나 RTX 3080 처리 속도를 보장하지 않는다. FCOS의 다중 스케일 특징과 더 큰 입력이 작은 사람 검출에 도움이 될 수 있다는 **가설**을 검증한다. 백본·헤드·가중치·전처리·점수 의미·NMS도 달라진다. **결과 차이를 해상도만의 인과 효과로 결론내리지 않는다.** 같은 score 0.5도 모델 간 동일한 보정 확률은 아니다.

## 고정 구현 조건과 권리

- torch 2.5.1+cu124 / torchvision 0.20.1+cu124, 기존 RTX 3080 10GB 환경. 새 의존성 설치 없음.
- `FCOS_ResNet50_FPN_Weights.COCO_V1`, 공식 파일 `fcos_resnet50_fpn_coco-99b0c9b7.pth`. [공식 다운로드](https://download.pytorch.org/models/fcos_resnet50_fpn_coco-99b0c9b7.pth), 공식 hash prefix 검증·weights_only 로드. 전체 SHA/실제 용량은 EXP-0002에 기록한다.
- 짧은 변 목표 **800**, 긴 변 최대 **1333**, 종횡비 유지 및 batch padding. 원본 1920×1080에서 긴 변 제한이 먼저 적용되므로 실제 입력이 정확히 800×1333이라고 가정하지 않고 transform hook으로 크기 기록. FP32/batch 1/warmup 10/CUDA 동기화 유지.
- 공식 pretrained FCOS 구조는 FrozenBatchNorm을 사용한다. 무작위 구조 생성 뒤 BN을 FrozenBN으로 바꿔 공식 구조와 일치시킨 후 strict state_dict 로드한다. 별도 ResNet backbone 가중치 다운로드/학습 없음.
- [TorchVision v0.20.1 LICENSE](https://raw.githubusercontent.com/pytorch/vision/v0.20.1/LICENSE): 코드 BSD-3-Clause. [모델 이용 안내](https://github.com/pytorch/vision#pre-trained-model-license)는 학습 데이터 유래 별도 조건 가능성을 명시한다. COCO_V1 가중치는 로컬 연구 추론에 한정하며 코드 라이선스를 영상/가중치 재배포 허가로 확장하지 않는다.
- 공식 모델 설명: [FCOS 0.20](https://docs.pytorch.org/vision/0.20/models/generated/torchvision.models.detection.fcos_resnet50_fpn.html), [Faster R-CNN v2 0.20](https://docs.pytorch.org/vision/0.20/models/generated/torchvision.models.detection.fasterrcnn_resnet50_fpn_v2.html). [FCOS 공식 구현](https://github.com/pytorch/vision/blob/v0.20.1/torchvision/models/detection/fcos.py). YOLO 대안 조건은 ADR-0007의 공식 링크 참조.

## 검증과 재검토

동일 네 구간의 원본 PTS/프레임·config 해시를 비교한다. 먼저 정한 매 2초 근거 프레임(각 구간 시작에 가장 가까운 원본 프레임부터)에서 양 모델의 누락과 비사람 오검출을 나란히 검토한다. 추가 이상 bbox/후보 시점은 탐색 사례로 표시해 구분한다. 전체 bbox 정답을 생성한 것처럼 precision/recall을 계산하지 않는다. 검출 개수 증가만으로 채택하지 않고, 실재 사람의 복원·새 오류·연결 안정성·처리 시간·GPU 메모리를 함께 기록한다. 비용/가림/오검출이 크면 메인 채택을 보류한다.


## 실행 후 판단

[EXP-0002](../experiments/EXP-0002-fcos-detector-comparison.md)의 동일 네 구간 2,060프레임에서 실제 사람 일부 복원을 확인했다. 동시에 030 넘기 자세/031 가림/006 원거리 누락, 007 중복·연결 모호성, 031 고정 물체 오검출 의심이 남았다. 후보 이벤트는 모두 0. FCOS는 후속 검증 후보로 유지하지만 메인 모델로 채택하지 않는다. 먼저 검수 정답/감시 범위를 확정한다. 속도·메모리는 실측했으나 과거 SSD 실행과 부하가 달라 통제 벤치마크로 해석하지 않는다.
