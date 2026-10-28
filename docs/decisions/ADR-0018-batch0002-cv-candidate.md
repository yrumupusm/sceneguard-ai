# ADR-0018 — BATCH-0002 CV 비교 후보와 입력 손실 게이트

2026-10-29 KST. 상태: **공식 출처 검토 완료, RF-DETR Medium을 조건부 우선 후보로 선택. 설치/가중치 다운로드/실제 추론/성능 확인 전.** [배치 계획](../experiments/BATCH-0002-model-upgrade-plan.md)과 입력 감사 게이트를 따른다. 기존 FCOS/ByteTrack 및 기본 MVP를 교체하지 않는다.

## 근거와 후보

FCOS는 사용자가 원본03090초에서 확인한 넘기 인물을 최종0.5에서 놓쳤고, 낮은 점수·부분 신체/중복 후보가 관찰됐다. 이 사실만으로 특정 architecture가 원인이라고 확정하지 못한다. RF-DETR Medium은 기존 FCOS와 다른 query 기반 검출 구성을 한 개만 비교할 수 있는 공개 후보다. COCO 성능이나 모델 출시 순서로 CCTV 사람 복원을 보장하지 않는다.

| 후보 | 확인한 공식 조건 | 이번 판단 |
| --- | --- | --- |
| RF-DETR Medium, COCO pretrained | 공식 Core Medium 코드·가중치 Apache-2.0, 기본576×576, DINOv2 계열 backbone. 로컬 `rfdetr` inference 경로 제공 | 우선 후보1개. input 충분성·환경·smoke가 통과할 때만 실행 |
| RT-DETR-R50 COCO+Objects365 | 공식 Hugging Face 카드 Apache-2.0, Transformers 경로 | 문서상 대안만 검토. 두 번째 CV checkpoint 다운로드/실행 금지 |
| 기존 FCOS COCO_V1 | TorchVision0.20.1/torch2.5.1의 현재 고정 구현, min800/max1333, 원본1920×1080의 실제 resize1333×749/pad1344×768 | 동일PTS 캐시 우선 기준. 캐시 없는 고정 프레임만 같은 모델로 실행 가능 |

공식 RF-DETR 문서의 T4/TensorRT 성능은 이 장비/실행기의 처리시간이 아니다. 새 모델의 점수0.5도 FCOS0.5와 같은 보정 확률을 뜻하지 않는다.

## 공식 소스 고정

- 조회한 PyPI 최신 release `rfdetr==1.11.2`; GitHub release1.11.2는 2026-10-04 게시, tag commit `7433d5919d0f7e72cc6cb78663e0a731afd499e0`다. develop branch 문서와 tag 코드가 다를 수 있으므로 실제 검토는 이 tag 소스에 고정했다.
- 해당 package metadata: Python≥3.10, torch≥2.2, torchvision≥0.17, transformers≥5.1,<6, supervision≥0.29 및 pydantic2 등. 기존 VLM transformers4.57.1 환경을 변경하면 충돌하므로 별도 환경이 필요하다. 아직 설치/호환성 통과를 주장하지 않는다.
- 공식 asset registry의 checkpoint URL은 `https://storage.googleapis.com/rfdetr/medium_coco/checkpoint_best_regular.pth`, 파일명 `rf-detr-medium.pth`, registry MD5 `7223f764a87b863f02eb8d52bf0ce2ee`다. HEAD 응답은 404,992,918 bytes와 같은 ETag를 반환했다. HEAD는 실제 다운로드/weight SHA256 검증이 아니다. 실행 시 로컬 전체 SHA256을 추가 고정한다.
- Medium config는 resolution576/patch16/decoder4, inherited num_queries300/num_select300이다. 공식 `predict`는 RGB를 bilinear(antialias=False)로 정사각형 resize·normalize하고, sigmoid score의 전체 상위300을 선택한 뒤 `score > threshold`를 반환한다. detection 경로에 별도 NMS는 없다. bbox는 원본 height/width로 복원한다. COCO sparse class ID와 연속 이름 목록을 혼동하지 않으며 실제 person 매핑을 smoke에서 검사한다.
- 추후 기준 실행은 batch1·576×576·threshold0.5, 별도 tracker/NMS 추가 없음으로 고정한다. eager FP32를 우선하며 compile/FP16/설정개선은 임의로 추가하지 않는다. 실제 런타임/장치/전처리/좌표·score 비교는 smoke 확인 전 미검증이다.

## 정보 손실과 결정 게이트

원본1920×1080이 FCOS에서는1333×749로 종횡비를 유지하지만 RF-DETR에서는576×576으로 변환된다. 좌우 축척은0.30, 세로는약0.533으로 다르고 정사각형 변환에서 종횡비가 바뀐다. 이는 새 모델이 더 작은 사람을 잘 본다는 근거가 아니라, 작은 대상의 공간정보 손실/형태 변화 가능성을 별도로 검사해야 한다는 이유다. 사람 크기 계산은 기존 검수 위치의 진단 초안일 뿐 정밀 bbox 정답이 아니다.

CPU 입력 감사로 원본/PTS/해시와 이전 사람 관찰의 적용 범위를 대조한 뒤, 비교 가능한 원본 프레임에서 최소 smoke1–2개만 먼저 실행한다. 모델이 추가 bbox를 냈다는 이유로 실제 사람이 복원됐다고 판단하지 않는다. 정밀 정답이 없어 precision/recall/F1은 null이며 새 중복·배경·부분박스를 함께 검수한다. native CV 입력의 관찰 가능성과 VLM2fps 축소 입력 충분성은 서로 다른 게이트다. 충분한 확인이 없으면 해당 단계는 보류하고 가중치를 추가로 탐색하지 않는다.

## 공식 참고 자료

- [RF-DETR tag의 inference 문서](https://github.com/roboflow/rf-detr/blob/7433d5919d0f7e72cc6cb78663e0a731afd499e0/docs/learn/run/detection.md), [라이선스](https://github.com/roboflow/rf-detr/blob/7433d5919d0f7e72cc6cb78663e0a731afd499e0/LICENSE)
- [PyPI1.11.2](https://pypi.org/project/rfdetr/1.11.2/), [공식 release](https://github.com/roboflow/rf-detr/releases/tag/1.11.2)
- [model config](https://github.com/roboflow/rf-detr/blob/7433d5919d0f7e72cc6cb78663e0a731afd499e0/src/rfdetr/config.py), [predict 구현](https://github.com/roboflow/rf-detr/blob/7433d5919d0f7e72cc6cb78663e0a731afd499e0/src/rfdetr/detr.py), [postprocess](https://github.com/roboflow/rf-detr/blob/7433d5919d0f7e72cc6cb78663e0a731afd499e0/src/rfdetr/models/postprocess.py), [checkpoint registry](https://github.com/roboflow/rf-detr/blob/7433d5919d0f7e72cc6cb78663e0a731afd499e0/src/rfdetr/assets/model_weights.py)
- [RT-DETR 공식 모델 카드](https://huggingface.co/PekingU/rtdetr_r50vd_coco_o365), [기존 FCOS 선택/결과](ADR-0008-fcos-detector-comparison.md)
