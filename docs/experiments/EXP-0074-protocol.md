# EXP-0074 사람 검출 A/B/C 비교 준비

2026-11-09. 이번 승인 범위는 사람 라벨 보완, 사전학습 기준선의 실제 평가, 비교 실행 준비다. 추가학습은 실행하지 않는다. 행동 분류·추적·침입 규칙은 변경하지 않는다.

## 자료와 승인 범위

EXP67의 검수75프레임과 EXP71의 검수122프레임을 합친197프레임을 별도 manifest로 고정한다. 학습122프레임/333박스, 개발75프레임/56박스다. 개발에는 기존25프레임과 P05 이동25·명시적 빈 배경25프레임을 포함한다. 원본 영상의 행동 종류가 다른 것은 사람 검출용 프레임을 제외하는 이유가 아니다. 모든 보이는 사람의 검수, 정확한 시각·좌표, 원본·촬영 묶음 분리를 기준으로 한다.

EXP73에서 승인된 수정 좌표5개와 지정 위치의 배경 후보17개 제거는 새 라벨 보완본에 반영한다. 기존 정답·웹 답변·연결 영상은 덮어쓰지 않는다. 이 승인을 다른 모델 제안이나 프레임 전체 완전성 승인으로 확대하지 않는다. 야간23.333초는 프레임 전체를 제외한다. 미확정 라벨은 일반 YOLO 학습이나 정밀도 계산에 섞지 않는다.

학습과 개발의 원본 SHA·촬영 closure·보수적 예약 겹침을 검사한다. P26/P28은 같은 학습 예약19이며 두 독립 사건으로 세지 않는다. 기존 case5의 개발 closure는 별도로 보존한다. 메타데이터 분리를 실제 물리적 촬영 독립성 인증으로 표현하지 않는다. 학교45·EXP64 시험296 및 연결 보호 자료는 학습·개발·임계값 결정에서 제외한다.

## 동일 조건과 유일한 차이

| 조건 | 초기값 | 학습 대상 | BN 누적 통계 |
|---|---|---|---|
| A | 공식 YOLO26m에서 정확히 보존한 person 분류 행 | 추가학습 없음 | 사전학습 값 |
| B | A와 같은 초기값 | 전체 학습 가능한 파라미터 | 학습 배치로 갱신 |
| C | A와 같은 초기값 | B와 동일, BN의 weight/bias 포함 | 사전학습 running_mean/var/count 고정 |

초기 checkpoint는 EXP68에서 optimizer step0에 저장한 initial.pt이며 SHA256은 `436426a56cb2699c7be3391b3dc1e4c06b268b357b330e3b1cf13409ee01ef53`이다. 학습된 last.pt를 초기값으로 사용하지 않는다. 공식80종 head의 숨은 폭·박스 예측층·특징 추출부를 유지하고 최종 person 행만 선택한 초기 상태의 일치를 검증한다.

B/C는 seed68, 같은 프레임 목록·epoch별 순서, batch2, 640 정사각 letterbox, FP32, AdamW(lr0.0001, weight_decay0.0005, betas0.9/0.999, eps1e-8), 5epoch를 사용한다. 현재122학습 프레임에서 epoch당61step, 총305step이다. AMP·EMA·증강·warmup·gradient accumulation은 적용하지 않는다. box7.5/cls0.5/dfl1.5와 gradient clip10, 기존 dual-head loss schedule도 맞춘다. 데이터셋이나 학습량을 바꾸면 두 조건을 함께 새 계획으로 고정한다.

C는 model.train() 호출 뒤 각 BN을 eval 모드로 돌려 고정된 평균·분산으로 정규화한다. 다른 레이어와 BN affine 파라미터의 학습은 유지한다. 단순히 momentum=0만 설정하거나 forward 후 buffer를 되돌리는 방식과 구분한다. B/C의 차이는 BN 처리이며 나머지 설정·초기 파라미터·배치 순서는 동일해야 한다.

각 epoch 종료 시 epoch-01.pt–epoch-05.pt checkpoint와 optimizer/step/설정·자료 해시를 저장한다. 주 비교는 사전 지정한 epoch5다. epoch별 결과는 성능 저하의 진행을 진단하는 용도로 모두 보존하며 좋은 epoch만 골라 최종 결과로 바꾸지 않는다. C의 세 종류 BN buffer가 초기값과 바이트 단위로 동일한지 확인하고, BN affine의 requires_grad와 gradient 경로도 검증한다. 현재 확인하는 checkpoint 저장 동작은 준비 시험이며 실제 학습 checkpoint 생성으로 보고하지 않는다.

## 평가와 다음 보강

모든 조건은 같은 CPU FP32 평가, 640 letterbox, one2one head의 top300, 추가 NMS 없음, confidence0.5·IoU0.5의 프레임별 일대일 최대 매칭을 사용한다. score0.05 이상 결과와 전체 anchor를 진단용으로 보존하지만 평가 임계값은 바꾸지 않는다. 동일한 GT ID로 기존 검출 유지·누락 회복·새 누락·계속 누락을 나누고, FP는 별도로 집계한다. 사건/촬영 묶음마다 분모와 빈 배경 FP를 함께 보여 준다. 박스 행 수를 고유 인원수나 침입 사건 성공 수로 바꾸지 않는다.

고정 개발75프레임의 A 결과는56TP/0FP/0FN이며 작은 사람 정답이0이다. 따라서 이 자료는 검출 유지·새 누락·새 오검출 검증에는 사용 가능하지만 누락 회복률의 분모는0이다. 학습용에서 발견된45FN을 개발 누락 회복 분모로 옮기지 않는다.

이 부족 조건만 보강하기 위해 개발 예약 P01의56.000·58.333·61.667초 세 장을 작은 별도 검수 묶음으로 준비한다. 먼 산책로의 작은 대상·중복 박스·전체 사람 누락 여부가 미확정이며, 기존에 제거한 배경 위치나 승인된5좌표를 다시 묻지 않는다. 확인 후 세 장을 새 버전 개발 목록에 반영하고 A를 먼저 평가한다. 실제 FN이 생겨야 누락 회복 비교가 가능하며, 모델이 놓칠 것이라고 미리 정답·FN을 확정하지 않는다.

새 독립 시험 확보는 별도다. 기존 학습·개발과 촬영 사건/멀티카메라가 겹치지 않는 주·야간, 작은 사람, 난간·문 가림, 월담 자세, 보행·대기 및 빈 배경이 필요하다. 원본 시각·해상도·FPS, 모든 보이는 사람 박스와 명시적 빈 프레임 확인, 촬영 연결 근거를 요구한다. 독립 시험 미확보를 현재 개발 실험의 실행 코드 준비와 혼동하지 않는다.

마지막 분류·박스 예측층만 학습하는 조건은 후속 후보로 남긴다. 이번 첫 비교에 네 번째 조건이나 임계값 탐색을 추가하지 않는다.

## 저장 checkpoint 평가 경로

`scripts/evaluate_exp0074_checkpoint.py evaluate`는 실제 학습 checkpoint와 그 epoch 영수증·고정 manifest 해시가 일치할 때만 CPU로 개발 프레임을 평가한다. 합성 저장 시험 파일은 거절하고, C checkpoint는 사전학습 BN 통계 불변도 다시 확인한다. 이 경로는 준비됐지만 현재 B/C checkpoint가 없으므로 실행하지 않았다.

```bash
CUDA_VISIBLE_DEVICES='' .venv-pose-batch03/bin/python scripts/evaluate_exp0074_checkpoint.py evaluate \
  --checkpoint EPOCH_CHECKPOINT --receipt EPOCH_CHECKPOINT_RECEIPT \
  --manifest outputs/model-comparison/exp0074/person-data-v1/manifest.json \
  --output NEW_EPOCH_EVALUATION_DIRECTORY
```

B/C 각각 epoch1–5를 모두 평가한 뒤, 주 비교에는 epoch5를 사용한다. `prepare_person_bn_comparison.py compare`에는 `A-development-predictions.jsonl`과 B/C의 개발 전용 predictions를 입력한다. A의 전체197 예측 중 개발75만 뽑은 파일은 이미 저장했고 추가 추론하지 않았다. 개별 B/C 평가의 FN은 그 조건의 누락 수이며 A의 누락 회복 분모와 혼동하지 않도록 필드를 분리했다.
