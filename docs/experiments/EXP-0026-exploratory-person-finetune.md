# EXP-0026 — Climbing Fence 잠정 사람 라벨의 Detection 학습

2026-10-29. **20 epoch 학습과 동일7장 비교 실행 완료 / 핵심 누락 개선 확인 안 됨 / 채택 보류**. 사용자 신규 학습 승인에 따라 [실행 전에 고정한 계획](EXP-0026-exploratory-training-plan.md)을 한 번 실행했다. 90·94초의 출력0개가 유지됐고84초와 일부 접근 장면의 출력은 줄었다. 라벨 시각 검수와 Gate D0는 미완료이며, 준비 사본의 과거 metadata는 보존했다.

## 실행과 비용

기존 Run `run_3d23462a014a`, Sol high Task `task_96b539b1624d` / Dispatch `ctx_76b9a0360296`, canonical GPU job `2f759b9e169441d8a339adad0fc78551`, attempt `616f05a480c7434f82253e90ae7a096e`다. 고정 소스 커밋은 `1a0a647427dcb8e9fe51edd38a51a747d4485a24`다. Astra high의 사전 소스·입력·승인 대조를 거쳐 기존 단일 큐에서 실행했다. [독립 검토](../reviews/EXP-0026-independent-review.md)와 [공개 측정값](../../records/EXP-0026/metrics.json)을 함께 본다.

| 항목 | 실측 |
|---|---:|
| 학습 / validation | 20 epoch / 21회(매 epoch20 + 종료 best1) |
| 학습 시간 | 223.544초(약3분44초), 준비·validation·최종 best validation 포함 |
| 기준7장 단계 | 1.520초 |
| 학습 후7장 단계 | 0.830초 |
| runner 전체 | 241.128초(약4분1초), 무결성 확인 등 포함 |
| PyTorch peak allocated / reserved | 1373.003 / 1984.000MiB |
| 전체 GPU 사용량 표본 최대 | 3760MiB, nvidia-smi1662회 표본; 다른 프로세스 포함 |
| 시작 여유 / 실행 중 표본 최소 여유 | 8684 / 6294MiB |
| 오류 / OOM / 재시도 | 0 / 0 / 0 |

RTX3080에서 batch2·640·FP32·freeze10·AdamW·lr0=0.0001·weight_decay=0.0005·seed0·추가 증강0으로 실행했다. 기존 Ultralytics8.4.192/torch2.5.1+cu124 환경을 바꾸지 않았다. 명목 nbs64/gradient accumulation32, 실제 optimizer weight 그룹 decay0.0005 및 BN/bias 그룹0을 확인했다. `optimizer.defaults`의 생성자 기본 lr/decay와 실제 parameter group 값을 혼동하지 않는다.

train/validation 계산은 FP32, 저장된 checkpoint는 공식 API의 FP16 저장 형식이다. 비교 predict는 두 조건 모두 FP32, fuse 및 end-to-end 경로였다. 공식 로그는 **person 이름으로1/1 class head 행 remap,768/768 items 전이**를 기록했다. COCO80→person1 출력 클래스 구조 변경은 있으며, 사람 head를 전부 무작위 초기화했다고 설명하지 않는다.

기준/학습 후 단계 시간은 로딩·최초 warmup·fuse·로컬 결과 저장의 영향을 포함한다. 순서가 있는 단 한 번의 실행이므로 1.520→0.830초를 학습으로 인한 속도 향상이나 연속 CCTV FPS로 해석하지 않는다. 훈련 자체의 성공을 데이터 의미 검수·일반화 성능 성공으로 바꾸지 않는다.

## 동일 입력의 결과

conf0.25·imgsz640·NMS 설정·고정 ROI·원본 PTS·person 필터를 동일하게 유지했다. 다음은 **출력된 박스 수**이며 실제 사람 수/TP/감지 성공 수가 아니다.

| 원본/시각 | 입력 | pretrained → fine-tuned | 해석 |
|---|---|---:|---|
| E01_03084초 | C6 | 3→1 | 이전 사용자 관찰상3명이 보이는 접근 장면. 출력 감소; 이번 새1개의 실제 대응은 미검수 |
| E01_03090초 | C6 | 0→0 | 사용자 관찰상3명 넘기 중. 필수 장면의 검출 근거를 여전히 얻지 못함 |
| E01_03094초 | C6 | 0→0 | 사용자 관찰상문 위1명·이미 넘어간1명. 두 조건 모두 박스 없음 |
| E01_03050초 | C6 | 1→0 | 접근 대조 프레임의 출력 소실; 정확한 인물 대응 미검수 |
| E01_03055초 | C6 | 2→1 | 접근 대조 프레임의 출력 감소; 개별 대응 미검수 |
| E01_00747.5초 | C3 | 0→0 | 고정 ROI에서 출력 없음; 실제 사람 부재/정상 분류 성공을 뜻하지 않음 |
| E01_00752.5초 | C3 | 2→2 | 같은 개수일 뿐 동일 인물·동일 박스 품질을 뜻하지 않음 |

이7장은 개발용이고 같은 카메라의 프레임을 여러 독립 표본으로 세지 않는다. 비교 이미지는 원본 좌표에 같은 고정 ROI와 예측 박스를 표시했다. 원본 PTS가 확정된 자료에서 좌표 offset을 한 번만 적용했다. 이미지는 사람이 나중에 확인할 자료이며, Codex가 새 출력의 실제 인물 대응을 확인했다고 기록하지 않는다. 추가 검수 질문으로 현재 작업을 멈추지 않는다.

## 학습 데이터 내부 진단

best는 사전에 정한 valid20의 fitness로 선택됐으며 **epoch5**였다. CCTV 결과로 epoch를 고르거나 last/best를 번갈아 재시험하지 않았다. 최종 best validation의 제공 라벨 일치 지표는 precision0.8835, recall0.9484, mAP50=0.9411, mAP50–95=0.6200이다. **미검수 valid20/24박스에 대한 수치**로, 검증된 CCTV 정확도·90초의 사람 recall·행동 성능이 아니다. pretrained와 같은 valid 집합의 별도 baseline mAP 비교를 실행하지 않았으므로 mAP 향상을 주장하지 않는다.

train box loss1.79415→0.65676, cls loss1.67475→0.21721, l1 loss0.04420→0.01471이다. loss 감소와 이 데이터의 높은 mAP가 CCTV 핵심 실패 개선으로 이어지지 않았다. 일반 사람 자료 혼합 없음, 자연 이미지/고정 CCTV 구도 차이, 미검수 박스 범위, 작은 split과 설정의 영향은 가능한 설명이며 **이번 실행으로 원인별 인과관계를 확정하지 않았다**.

## 산출물과 검증

로컬 결과 루트는 `outputs/batch0007/EXP-0026/train_compare/616f05a480c7434f82253e90ae7a096e/`다. 원본/ROI cache, raw Results, 학습 로그, 비교 이미지7장, loss 그래프, best/last는 Git에서 제외한다.

- best: `training/weights/best.pt`,44,017,682bytes,SHA256 `1b120a24c8983507e137304ec3ef814a2415d97c866113df80a6cb61c260dd4f`.
- last: `training/weights/last.pt`,44,017,682bytes,SHA256 `91febb4e1a5f3b24b13da9dd571055880cf2cae788bda80bade4d73c634b80f9`.
- 주요 이미지: `030_084-baseline-after.png`, `030_090-baseline-after.png`, `030_094-baseline-after.png`. 접근 대조4장도 같은 폴더에 보존.
- loss 그래프: `training-loss-curve.png`; 생성 코드는 `scripts/summarize_batch0007_training.py`. upstream CSV 해시를 확인하고 그대로 그리며 raw media나 모델을 불러오지 않는다.
- 원시 실행 summary SHA256: `ba1fdb049f2c030576817b7d781ff6180e9337a077ffd148679ee1ddd044cc99`.

CPU Detection 계약10개, 입력 준비9개, 기존 큐 회귀14개가 통과했다. 원본 시각·crop·bbox offset·빈/잘못된 Results·실제 lease 없을 때 거부·source/input/Git 변경 거부·추가 큐 등록의 기존 이력 보존·OOM/NaN 자동 복구 거부·마지막 validation을21번째 epoch로 세지 않는 검사를 포함한다. CPU 검사 통과,20epoch 실제 실행 성공,검출 품질 개선은 별개의 판단이다.

기존42jobs/42attempts를 보존하고 신규1job/1attempt만 추가했다. 원본 ZIP/준비 사본247장·라벨·metadata·기존 환경·기존 실험 출력은 보존한다. API 내부 자동 재시도를 막는 관측 guard 외 학습 알고리즘을 변경하지 않았으며, 오류 수정 재시도 기회도 사용하지 않았다.

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

## 결정과 다음 한 가지

**학습 경로는 작동하지만 이 checkpoint의 적용은 보류한다.** 기존 검출기/포즈/VLM/경계 판단·기본값을 유지하고 추가 epoch·임계값·ROI·모델 탐색은 실행하지 않는다. 다음 우선순위는 사용자가 돌아왔을 때 준비된113개 데이터 비교 자료에서 **사람 라벨이 개인의 어느 범위를 감싸는지와 누락 라벨을 확인**하는 것이다. 이번 실패를 라벨 문제 하나로 확정하거나, 반복 학습만으로 해결된다고 가정하지 않는다. 라벨 품질과 목표 CCTV의 차이를 확인한 뒤 새 학습 설계를 판단한다.
