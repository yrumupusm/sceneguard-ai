# EXP-0075 학교 검수 반영과 학습 전 기준선

2026-11-10. 사용자의 대화 **“검수 완료”**와 학교 편집기의12개 저장 답변을 읽고 정확한 revision1을 보존했다. 그중10프레임을 학교 회귀 평가용 정답으로 고정하고, 가림 사람이 추가로 있다는 메모가 있는2프레임은 전체 사람 평가에서 보류했다. 확정10프레임의 사전학습 A 평가를 CPU로 실행했다. **추가학습은 하지 않았다.**

## 검수 적용 범위

| 처리 | 프레임 | 사람 박스 행 | 근거 |
|---|---:|---:|---|
| 평가에 반영 | 10 | 19 |8장은 저장된 사람 좌표·모든 사람 확인,2장은 명시적 사람 없음 확인 |
| 전체 평가 보류 | 2 | 저장된6개 좌표 보존 |031의32초·40초: 추가 인물이 가려져 박스를 넣지 않았다는 메모 |
| 합계 | 12 | 25 |수신한12개 revision을 모두 읽고 적용/보류 기록 |

006의124.991533초는 편집기 상태도 complete였다. 나머지 상태는 draft로 저장됐지만 사람 있는 프레임은 모두 `confirmed=true`, 두 빈 프레임은 `empty_confirmed=true`였다. 이번 대화의 완료 확인을 해당 저장 revision과 함께 승인 근거로 기록했으며 편집기 상태나 좌표를 대신 수정하지 않았다. 빈 프레임의 사람 확인 체크가 꺼져 있었다는 이유로 같은 확인을 다시 요구하지 않는다. 명시적인 사람 없음 확인이 근거이며 모델 출력0이 근거가 아니다.

031의 두 메모는 체크박스보다 구체적인 제한으로 적용한다. 저장된3개씩의 박스는 보존하지만, 추가 인물의 가시성과 경계를 임의로 확정하지 않는다. 해당 두 프레임을 빈 배경으로 처리하거나 그 좌표만으로 전체 정밀도·재현율을 계산하지 않았다. 이번 첫 비교에는 나머지10장을 사용하므로 보류2장의 재검수는 필수 조건이 아니다.

043의68초와031의44초에 적은 블러 관련 메모는 원인 가설이며 사람 박스 승인 자체를 취소한 답변은 아니다. 얼굴 비식별화가 검출을 방해할 수 있다는 사용자 관찰을 보존하되, 블러 없는 대조 자료나 원인 분리 실험이 없으므로 실패 원인으로 확정하지 않는다. 비식별화를 제거하지 않았다.

## 동일 조건의 실제 A 결과

EXP74와 동일한 epoch0/optimizer step0 YOLO26m person 초기값, CPU FP32,640 letterbox,one2one top300,추가 NMS 없음,confidence0.5/IoU0.5의 일대일 매칭이다. 출력 점수0.05 이상과 전체 anchor를 저장했다. 실제 추론 전 정답 목록을 고정했고 모델 상태 불변·CUDA 미초기화를 확인했다.

| 영상 | 확정 평가 프레임 | 사람 정답 박스 | TP | FP | FN |
|---|---:|---:|---:|---:|---:|
|006|1|2|1|0|1|
|007|3|4|2|0|2|
|028|1|1|0|0|1|
|030|3|6|3|0|3|
|031|1|4|0|0|4|
|043|1|2|0|0|2|
|합계|10|19|6|0|13|

두 명시적 빈 배경 프레임은007/030의0초이며 둘 다 FP0이다. 입력640 기준 작은 정답7개 중1개 검출·6개 누락, 중간12개 중5개 검출·7개 누락이다. 이 크기 기준은 축소 후 박스 면적의 제곱근32/96 경계이며 COCO 원본 AP 기준과 다르다.

이 목적 표집에서 정밀도는100%, 재현율은31.58%지만, **학교45개 전체나 독립 시험 성능이 아니다.** 실패 문맥을 의도적으로 포함했고 프레임 수·박스 행을 독립 사건 수나 고유 인원수로 세지 않는다. B/C 결과는 아직 없으며 학습 개선은 미측정이다.

이제 학습 후 회복 여부를 비교할 A의 누락13개와 기존 검출6개가 확보됐다. 고정된 `(frame_id, gt_id)`별로 회복·유지·새 누락·계속 누락을 나누고 FP를 별도로 비교한다. 동일 영상 안에도 여러 시점이 있으므로 사건별 결과에는 평가한 시점·박스 분모를 함께 제시한다.

## 과거 저장 출력과의 경계값 차이

EXP66 공식80종 모델/GPU native 저장 출력을 이번 확정 정답에 대응하면5TP/0FP/14FN이다. 이번 A는6TP/0FP/13FN이다. 차이는007의66초 한 박스에서 과거 점수0.4994433224와 이번0.5000456572가 기준0.5의 양쪽에 놓인 것이다. 서로 다른 예측 경로·연산 조건의 영향을 분리하지 않았으므로 정확한 원인을 단정하지 않는다. 임계값을 조절하지 않았다.

이는 추가학습 결과가 아니다. EXP74의 학습 전 초기값과 같은 평가 경로로 다시 계산한 A를 B/C의 비교 기준으로 사용한다. 과거 출력은 역사적 참고로 보존하고, 이 한 박스 차이를 학습 후 회복으로 세지 않는다. 경계값 인접 사례임을 후속 비교에도 남긴다.

## 보존과 후속 평가 경로

학교 정답은 `outputs/model-comparison/exp0075/confirmed-school-v1/manifest.json`의 **school_regression** 분할에만 있다. 학습122/개발78 AI-Hub 목록은 바이트 그대로이며 학교를 합치지 않았다. 학교 manifest는 기존 학습 데이터 검사에서 거절되는 것도 확인했다. 좌표 텍스트는 평가 감사용이고 학습 YAML·실행 승인은 없다. B/C의 초기값·자료·seed·학습률·305step 계획은 변경하지 않았다.

`evaluate_exp0074_checkpoint.py evaluate --school-manifest ...` 경로를 준비했다. 학습 checkpoint 영수증은 원래 학습 manifest와 검증하고, 학교 평가 manifest는 별도로 읽는다. 두 자료의 원본/이미지 교차와 학교 학습 금지 선언을 검사한다. 학교를 학습 provenance에 포함시켜 영수증을 맞추는 우회는 하지 않는다. B/C checkpoint가 없으므로 이 경로의 실제 모델 실행은 아직 없으며, 데이터 분리·미검출 집계 경로만 시험했다.

학교용 출력에서 누락 분모를 development로 잘못 집계하지 않도록 평가 split을 명시하는 인자를 추가했다. 기존 개발 평가의 기본 동작과 기존 결과 파일은 유지했다. 새 학교 기준선 결과는 고정된19개 GT ID와 실제 예측·점수·원본 시각을 포함한다. B/C에는 동일 학교 목록과 동일 평가 설정을 사용하고 학교 결과로 모델/임계값을 선택하지 않는다.

## 재현·시험·처리 이력

```bash
python3 scripts/apply_school_person_review.py export \
  --evidence runtime/model-comparison/exp0075/review-application-v1 \
  --output NEW_SCHOOL_MANIFEST_DIRECTORY
CUDA_VISIBLE_DEVICES='' .venv-pose-batch03/bin/python scripts/apply_school_person_review.py evaluate \
  --manifest NEW_SCHOOL_MANIFEST_DIRECTORY/manifest.json --output NEW_A_OUTPUT_DIRECTORY
# 실제 B/C checkpoint가 생긴 뒤 사용하는 평가 명령. 이번에는 실행하지 않음.
CUDA_VISIBLE_DEVICES='' .venv-pose-batch03/bin/python scripts/evaluate_exp0074_checkpoint.py evaluate \
  --checkpoint EPOCH_CHECKPOINT --receipt EPOCH_CHECKPOINT_RECEIPT \
  --manifest outputs/model-comparison/exp0074/person-data-v2/manifest.json \
  --school-manifest outputs/model-comparison/exp0075/confirmed-school-v1/manifest.json \
  --output NEW_SCHOOL_EPOCH_EVALUATION_DIRECTORY
```

현재 A는 `outputs/model-comparison/exp0075/baseline-v1/`이다. 원시 검수 snapshot·대화 완료 원문·적용/보류 이력은 별도 로컬 파일에 저장했다. 이 검수는8773 별도 편집기에서 받은 것이며8765 질문에 답변이 제출됐다고 기록하지 않는다. 기존 웹 질문 조회는 정상 수행했고 신규/수정 대기 답변은 없었다. 기존 편집기 DB12revision은 그대로이며 `review-processing.json`에 정확한 버전별 반영/보류 이력을 남겼다.

새 승인범위·보류·명시적 빈 프레임·학교 분리 시험 및 기존 평가/편집기 회귀를 포함한28개 시험이 통과했다. 별도 최대 일대일 매칭 산술 감사도6TP/0FP/13FN을 재현했다. GPU queue는145 jobs/145 attempts 그대로이며 새로운 GPU 작업·optimizer step·학습 checkpoint는 없다.

| 자료 | SHA256 |
|---|---|
|학교 평가 manifest|`9b3276c3526119c58a9e16107b04d22759324a67686d83c52ecf2ce65080f6eb`|
|A 평가 결과|`3f484810415d2e8dab129914e52408dfbd7d4531d6ee592330f53aa35ebe4e5c`|
|버전별 반영/보류 기록|`8ec82ef5331f958c7bc02b929db8452c1c3369c930b75a0fba3562c0eac1f77a`|

원본·좌표·가중치·검수 DB는 로컬 전용이고 코드·집계·후속 보고서만 GitHub에 반영한다. 다음 단계는 고정한 B/C의 추가학습과 같은 학교 정답에 대한 비교이며, 이번 검수 완료를 추가학습 승인으로 해석하지 않았다.
