# EXP-0026 — Climbing Fence 잠정 사람 라벨의 Detection 학습

2026-10-29. **실행 준비 중 — 아직 학습 성공/검출 개선 결과가 아니다.** 사용자 신규 학습 승인에 따라 [실행 전에 고정한 계획](EXP-0026-exploratory-training-plan.md)을 수행한다. 라벨 시각 검수와 Gate D0는 미완료이며, 준비 사본의 과거 metadata는 보존한다.

## 비교가 답하는 질문

YOLO26m Detection의 같은 pretrained 파일에서 시작해, 미검수 person 박스의 작은 데이터로 학습했을 때 기존 CCTV 누락 장면의 박스 출력이 어떻게 달라지는가? 관절 추정·넘기 행동·완료·출입 권한 판단 실험이 아니다. 기존 Pose640/960 결과는 이력이며 이번 Detection 기준 측정의 대체물이 아니다.

## 재현 경로

원본 ZIP과 [형식 변환 기록](../data/CLIMBING_FENCE_PREPARATION.md), 새 `configs/batch0007_detect_manifest.json`을 따른다. 기존 원본/출력/환경에 쓰지 않고 별도 EXP-0026 출력과 train-data 사본을 사용한다. 공식 Detection 가중치 하나만 추가하며, 기존 Pose 가중치와 모델 기본값은 변경하지 않는다.

```bash
# 저장소 루트. 실제 실행은 현재 native 담당·검토된 source/input/commit 승인 필요.
.venv-pose-batch03/bin/python -m batch07_detect.cli enqueue
.venv-pose-batch03/bin/python -m batch07_detect.cli run-once
.venv-pose-batch03/bin/python -m batch07_detect.cli status
```

위 명령은 현재 고정 데이터·기존 단일 큐의 개발 실행용이다. 완료 후 같은 작업을 다시 실행하는 명령이 아니며 이미 등록한 작업/출력을 덮어쓰지 않는다. live lease 없이 runner 직접 실행은 거부한다. CPU 평가 입력 준비 코드는 `scripts/prepare_batch0007_evaluation.py`이며 정확한 원본 PTS만 허용한다.

## 평가의 한계

train210/valid20/test17 중 test는 미사용한다. 제공된 valid 라벨과의 일치 수치는 검수된 정답에 대한 정확도가 아니다. 복수 사람·부분 박스·누락 라벨과 원 촬영 그룹 독립성은 미확정이다. 일반 사람 자료 혼합도 하지 않아 원래 사람 검출 능력 저하 가능성이 있다.

고정 CCTV7장은 이미 본 개발용 세 장과 접근 장면 네 장이다. 정밀 bbox GT와 독립 카메라 검증이 없으므로 CCTV mAP/F1/recall 및 행동 성능은 계산하지 않는다. 새 박스가 실제 사람을 올바르게 감싸는지는 사용자 후속 검수 대상이며, 출력 개수 증가만으로 개선을 확정하지 않는다.
