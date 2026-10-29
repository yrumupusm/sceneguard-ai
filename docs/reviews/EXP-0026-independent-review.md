# EXP-0026 독립 검토

2026-10-29. 검토 Task `task_1d31f20f14b2` / Dispatch `ctx_556f3729a9e7`. 상태: **초기 계획/API 검토 완료, 구현·동결 소스의 사전 판정 대기**. GPU 실행 또는 최종 결과를 승인한 기록이 아니다.

사용자의 최신 학습 지시와 [탐색 학습 계획](../experiments/EXP-0026-exploratory-training-plan.md)을 이번 범위의 근거로 삼는다. [준비 기록](../data/CLIMBING_FENCE_PREPARATION.md)의 학습 미승인은 당시 이력이며 원본을 변경하지 않는다. 미검수 라벨의 의미·누락·복수 인물 여부와 split 독립성은 미확정이고 **Gate D0 미통과**다. 검토자는 CCTV 이미지를 외부로 전송하거나 시각 정답을 만들지 않는다.

## 초기 계획 판단

COCO YOLO26m Detection 기준 모델과 새로 로드한 동일 pretrained 파일의 단일 학습 실행, train210/valid20 및 test17 미사용, 고정 CCTV 7개 입력은 탐색 범위에 부합한다. COCO80→person1로 출력 공간이 달라진다. 설치본의 `cls_remap=True`는 이름이 맞고 shape가 호환되는 person class-logit 행을 공식 경로로 옮기므로, 실제 transfer 로그 확인 전 분류 head 재초기화를 단정하지 않는다. 일반 사람 자료 혼합이 없어 기존 사람 검출 성능의 저하 가능성은 남는다. valid 수치는 제공된 잠정 라벨과의 일치 진단이며 CCTV 검출 정확도·일반화·행동 성능을 입증하지 않는다.

## 설치 API에서 확인한 실행 전 해결 항목

검토 대상은 기존 환경의 Ultralytics 8.4.192 설치 소스다. [공식 train API](https://docs.ultralytics.com/modes/train/)와 [YOLO26 Detection 문서](https://docs.ultralytics.com/models/yolo26/)를 교차 확인했고, 버전별 실제 동작 판단은 설치 소스를 우선했다.

1. `engine/trainer.py`는 첫 epoch 메모리 오류에서 batch를 줄이고 최대3회 내부 재시도를 한다. 이번 고정 batch/자동 재시도 금지에 맞게 **재구축·다음 forward 전에 종료하는 관측 guard와 CPU 오류 시험**이 필요하다. 학습 알고리즘이나 private trainer 메서드를 교체하는 수정은 요구하지 않는다.
2. 같은 trainer는 NaN/Inf loss 또는 fitness 발생 시 `last.pt`를 다시 읽고 epoch를 재실행한다. 이 자동 복구도 실행 전에 차단하고 비유한 값 실패를 보존해야 한다.
3. 명시적 AdamW에서 기본 `warmup_bias_lr=0.1`은 자동으로 0이 되지 않는다. 계획의 lr0=0.0001과 별개로 1,000배 큰 초기 bias LR이 될 수 있으므로 작은 고정 warmup LR을 명시해야 한다. nominal `nbs=64`이면 batch2의 accumulate32 및 warmup 동안의 변화를 기록한다. 내부 validation dataloader는 batch4다.
4. HSV/기하 증강을 0으로 해도 선택적 Albumentations 기본 Blur/Gray/CLAHE는 남을 수 있다. 공개 `augmentations=[]`로 추가 변환을 끄고 실제 변환 경로를 확인한다.
5. `cache=False`여도 label cache를 생성하므로 원본 준비 사본이 아닌 별도 실행 사본을 사용한다. FP32 학습과 checkpoint의 FP16 저장은 구분하며, 매 epoch validation 외에 종료 시 best checkpoint validation이 추가됨을 계수한다.

위 항목은 구현 담당/총괄에게 전달했다. 최종 실제 kwargs, offline callback/네트워크 차단, source/input/weight SHA, 기존 canonical queue의 live lease와 free VRAM≥6144MiB, CPU 회귀와 소스 동결을 확인하기 전 preflight PASS를 내리지 않는다. 결과를 받은 뒤 성공 epoch·실제 비용·제공 라벨 진단·사람 박스 품질 미검수를 분리하여 이 문서에 최종 검토를 추가한다.
