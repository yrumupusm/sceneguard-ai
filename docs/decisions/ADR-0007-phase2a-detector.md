# ADR-0007 — Phase 2A 첫 진단 모델: SSDLite320 MobileNetV3

- 2026-10-27 / 제한된 개발 실험용 선택. 최종 모델 선정 아님. [ADR-0006](ADR-0006-limited-cv-baseline-prototype.md) 승인 범위.
- 구현 전 근거: 원거리 사람이 작은 CCTV, bbox/track 정답 미확정, RTX 3080 10GB 확인, PyTorch 미설치. 새 프레임워크 하나의 격리 환경에서 추론만 수행한다.

| 후보 | 적합성과 비용 | 선택 |
| --- | --- | --- |
| TorchVision SSDLite320 MobileNetV3 Large COCO_V1 | 약 3.4M 파라미터/13.4MiB, 고정 320 입력. 작은 검출기로 최소 파이프라인 진단 가능; 작은 사람 축소 손실 위험 큼 | 이번 첫 모델. 학습 없이 person만 출력 |
| YOLOv8n | 640 입력의 작은 모델 후보; 작은 사람 보존에 상대적으로 유리할 가능성이나 직접 비교 미실행. 별도 패키지와 AGPL/Enterprise 이용 조건 고려 | 설치·실행 보류 |
| TorchVision FCOS ResNet50 FPN | 더 큰 해상도/백본 대안. 동일 프레임워크로 바꿀 수 있지만 가중치·연산 비용 증가 | 첫 smoke test 이전 복수 모델 설치 금지, 후속 근거 후 검토 |

크기가 작다는 것이 CCTV에 적합하다는 증거는 아니다. 작은 사람 누락이 첫 실패 원인일 수 있다는 가설을 명시하고, IoU 연결·경계 규칙의 오류와 분리해 관찰한다. 이 모델로 높은 탐지 성능을 확보했다고 주장하지 않는다. 실패하면 임계값/경계의 사후 튜닝으로 결과를 꾸미지 않고 후속 해상도/검출기 비교를 제안한다.

## 출처·조건

- [TorchVision 0.20 모델 문서](https://docs.pytorch.org/vision/0.20/models/generated/torchvision.models.detection.ssdlite320_mobilenet_v3_large.html): SSDLite320 및 COCO_V1 제공, 입력 320×320.
- [TorchVision v0.20.1 LICENSE](https://raw.githubusercontent.com/pytorch/vision/v0.20.1/LICENSE): BSD-3-Clause 코드. [저장소 모델 안내](https://github.com/pytorch/vision#models)는 사전학습 가중치에 학습 데이터의 별도 조건이 적용될 수 있음을 안내한다. 코드 라이선스를 COCO 이미지/가중치의 무제한 재배포 허가로 해석하지 않는다. 공식 배포 가중치는 로컬 연구용 추론에만 사용하고 Git에 재배포하지 않는다.
- [공식 PyTorch 버전 조합](https://pytorch.org/get-started/previous-versions/): Python 3.10에서 torch 2.5.1 / torchvision 0.20.1 / CUDA 12.4 wheel 조합 고정. 최신 버전 주장 없음. 공식 state_dict만 weights_only로 로드한다.
- [YOLOv8 공식 문서](https://docs.ultralytics.com/models/yolov8/), [Ultralytics 라이선스](https://www.ultralytics.com/license): 이번 설치 대상 아님.
- PyAV의 `frame.pts * frame.time_base`로 원본 시각 유지. [시간 API](https://pyav.org/docs/stable/api/time.html). FPS로 정답 인덱스를 보정하지 않는다.

실측 모델 SHA·정확한 용량·패키지 버전·GPU 메모리·처리 속도는 실행 후 실험 문서에 기록한다. 검출 크기/가림 실패가 주원인이면 고해상도 검출을 검토하고, 연결 실패가 주원인일 때만 tracker 보강을 검토한다.

## 첫 실행 후 판단

[EXP-0001](../experiments/EXP-0001-phase2a-cv-baseline.md)에서 4개 smoke와 007 전체 클립을 실행했다. 030 smoke 사람 검출 1/480프레임, 031 smoke 0/480프레임, 007 full 312/4171프레임으로 사건 후보가 생성되지 않았다. 이 비율은 사람 정답 기반 recall이 아니다. 현재 SSDLite320/score 0.5 설정을 메인 감지 모델로 채택하지 않고, 다음 비교는 검출 해상도/가림 대응을 우선 후보로 둔다. 더 복잡한 tracker나 학습의 효과를 이번 결과로 입증하지 않았다.
