# EXP-0068 — YOLO26m 소량 추가학습 전후 결과

2026-11-08. **실제 추가학습은 완료됐지만, 고정 검증 자료에서는 사람 검출이 악화됐다.** 학습 전 검출31/누락0에서 학습 후 검출6/누락25로 변했다. 이번 가중치는 기본 모델로 채택하지 않는다. 학교 CCTV 성능 개선과 전체 모델 비교는 아직 측정하지 않았다.

## 실제로 한 일

사용자가 검수한 EXP-0067 사람 박스로 YOLO26m을 5회 학습하고 실제 가중치를125번 갱신했다. 학습50프레임/151박스/2촬영 사건, 검증25프레임/31박스/다른1사건으로 원래 분할을 유지했다. 사람 위치와 보이는 사람의 누락 여부에 대한 기존 답변을 재사용했다. 행동·신원 라벨로 확대하지 않았다.

공식 사전학습 모델의 사람 클래스 가중치를 보존해1클래스로 변환한 초기값과, 동일 모델의 마지막5회 학습 가중치를 비교했다. 분류층을 무작위로 초기화하지 않았다. 변환 전후 두 헤드의 원시 사람 점수·회귀 출력은 검증25프레임에서 차이0이었다. 다만80클래스 전체의 상위 후보 경쟁과1클래스의 상위 후보 경쟁은 다르므로 공식80클래스 최종 검출 목록과 완전히 같다고 주장하지 않는다.

FP32·640입력·batch2·AdamW 학습률0.0001·무증강 조건을 실행 전에 고정했다. 검증 점수로 최적 가중치나 임계값을 선택하지 않았다. [실행 전 조건](EXP-0068-protocol.md), [실제 실행과 가중치 해시](EXP-0068-execution.md), [독립 검토](../reviews/EXP-0068-independent-review.md)를 함께 따른다.

## 같은 정답에 대한 비교

사람 신뢰도≥0.5, 정답 박스와 IoU≥0.5를 모두 만족해야 검출로 센다. 프레임별 일대일 최대 개수 매칭으로 중복 검출과 다른 사람의 박스를 구분한다. 아래31개는 반복 프레임의 박스 행이며31명의 사람이 아니다. AP나 넘기 행동 정확도도 아니다.

| 지표 | 학습 전 | 학습 후 |
|---|---:|---:|
| 맞게 검출한 박스 TP |31|6|
| 오검출 FP |0|0|
| 누락 FN |0|25|
| 정밀도 |100%|100%|
| 재현율 |100%|19.35%|
| F1 |1.0000|0.3243|

전후 모두 검출6, 새로 누락25, 회복0, 전후 모두 누락0이다. 학습 후 정밀도100%는 출력6개에 대한 값이므로 좋은 전체 성능이나 일반적인 오탐 억제를 뜻하지 않는다. 평균 매칭 IoU는0.976163→0.870231이지만 매칭된 집합이 달라 동일 사람 전체의 위치 변화 지표로 해석하지 않는다.

저장된 프레임당8400개 원시 후보만 읽어 누락25개를 진단했다. **25개 모두 IoU≥0.5인 후보가 있지만, 그중 최고 사람 점수도0.5 미만**이었다. 해당 최고점수 범위는0.000000794735–0.431627이다. 최종 박스 표시 오류나 상위300개 선택만으로 누락을 설명할 수 없다. 이는 출력에서 확인한 현상이며 학습 데이터 부족, 설정, BatchNorm 변화 등 특정 원인을 입증한 것은 아니다. 임계값을 내려 결과를 다시 만들지 않았다.

학습 loss 감소도 성능 개선 근거로 쓰지 않는다. 매 epoch의 one-to-many/one-to-one loss 비중이 달라져 단순한 같은 척도 비교도 아니다. 한 사건의 상관된25프레임, 검수된 YOLO26x 제안에서 출발한 정답이라는 선택 편향을 함께 남긴다. 학습 전100%를 독립 시험의100%로 보고하지 않는다.

## 비교 영상과 재현 자료

기존 웹 EXP-0068에 연결하는 영상은 왼쪽 원본+검수 정답, 가운데 학습 전, 오른쪽 학습 후다. 청록은 확정 사람 박스, 주황은 실제 모델 출력이며 점수를 표시한다. 화면의 번호는 사람 신원/추적 ID가 아니다. 원본13.333–21.333초의25프레임을 원래3FPS로 보여 주며 출력 길이는8.333초다. 각 화면의 시각은 원본 PTS다. 넘기 판정 영상이 아니다.

- 학습 출력: `outputs/model-comparison/exp0068/queued/train5/47adf16ca4fa4145b50e0ee150106c38/`
- 초기·최종 전체 모델과 optimizer: 위 경로의 `initial.pt`, `last.pt`.
- 전후 실제 박스/점수: `before-predictions.jsonl`, `after-predictions.jsonl`.
- 전후8400후보: `before-all-anchors.npz`, `after-all-anchors.npz`.
- 학습125회 기록·5회 전체 프레임 순서: `optimizer-steps.jsonl`, `epochs.json`.
- 비교 영상: `outputs/model-comparison/exp0068/preview-v1/validation-before-after.mp4`, 바인딩은 같은 폴더 `manifest.json`.
- 누락 진단: `outputs/model-comparison/exp0068/miss-diagnosis-v1.json`.
- 공개 집계와 출처: `records/EXP-0068/results.json`, `metrics.json`.

학습 소스 commit은 `40c434a70fd50a03b4698a7d18780a3febc2f8c0`이다. 실행 명령·입력/환경·모델·소스·승인 바인딩은 `runtime/model-comparison/exp0068/executor/execution/invocation.json`, `root-grant-v1.json`, 후보 및 canonical 큐 영수증에 보존했다. 실행기는 `executor/run.py`, 고정 단계는 `person-detector-train/train5`다. GPU 학습을 무심코 재실행하지 않으며, 기존 저장 출력의 CPU 비교는 다음과 같이 재현한다. 출력 경로는 기존 결과를 덮어쓰지 않는 새 경로를 사용한다.

```bash
python3 scripts/evaluate_person_detector_pair.py \
  --manifest outputs/model-comparison/exp0067/confirmed-person-v1/manifest.json \
  --before outputs/model-comparison/exp0068/queued/train5/47adf16ca4fa4145b50e0ee150106c38/before-predictions.jsonl \
  --after outputs/model-comparison/exp0068/queued/train5/47adf16ca4fa4145b50e0ee150106c38/after-predictions.jsonl \
  --output outputs/model-comparison/exp0068/recomputed-pair.json
```

영상 생성은 `scripts/render_person_detector_pair.py`에 같은 manifest/before/after와 새 `--output` 폴더를 전달한다. 누락 진단은 `scripts/diagnose_person_detector_misses.py`의 `--manifest`, `--result-dir`(위 실제 학습 폴더), `--evaluation`(paired JSON), `--output`을 사용한다. 두 도구는 기존 `.venv-pose-batch03/bin/python`에서 CPU로 실행한다. 영상·개별 라벨·가중치는 로컬에 보존하고 GitHub에는 코드·집계·보고서만 올린다.

## 실행 성공과 다음 단계의 구분

단일 GPU 작업/시도는 exit0으로 끝났고 자식·감독 프로세스 종료와 큐 유휴를 확인했다. 기존144개 작업/시도를 보존한 채145개가 됐으며 재시도는 없다. 실제396개 파라미터 텐서와 optimizer 상태125step, 유한 gradient, 모든 학습 프레임의 epoch별 사용을 독립 확인했다. 학습·평가19시험 및 기존 큐14시험이 통과했고, 기존 라벨 보완/내보내기 회귀도 통과했다. 실행 경과52.642615초는 로딩·적응·학습·저장·검증을 포함한 자식 monotonic 측정이며 원본 처리 FPS가 아니다.

다음 학습에서는 먼저 정상 보행·대기·접근후돌아가기와 가림·작은 인물을 포함해 **서로 다른 촬영 사건의 완전한 사람 주석**을 보강하고, 학습과 평가 자료를 사건 단위로 분리해야 한다. 검증 한 사건에 맞춘 임계값 변경이나 학습 횟수 연장은 근거가 부족하다. 충분한 자료로 새 프로토콜을 고정한 뒤, 일반 사전학습 동작을 보존하는 학습 설정과 점수 하락 원인을 검증한다. 이번 결과만으로 원인을 과적합 하나로 확정하지 않는다.

메인 비교 범위인 YOLO26m/l/x·EVAD-B/L·STMixer는 유지한다. 현재 완료한 것은 YOLO26m의 소량 학습 경로와 전후 검증이며, 나머지 모델 추가학습과 학교 CCTV 전후 비교는 남아 있다. EVAD/STMixer의 행동 출력에는 사람 박스 외에 대상별 행동·시간 대응 정답도 필요하므로 이번 사람 박스 승인을 행동 라벨 승인으로 대신하지 않는다. 기존45개와 EXP-0064시험은 학습·선택에서 보호하고, EXP-0062 AFTER·EXP-0064 선택 가중치/임계값0.5는 유지한다.

웹 등록·브라우저·GitHub 전달과 작업자 정리의 실제 확인은 별도 [전달 기록](EXP-0068-delivery.md)에 남긴다.
