# EXP-0065 재현 명령과 산출물

기존 CPU 영상 환경에서 실행한다. 새 모델·GPU·학습·추론은 필요하지 않다. 기존 산출물을 덮어쓰지 않고 새 출력 디렉터리를 지정한다. 원천 CCTV·라벨·점수·가중치·로컬 DB는 공개 저장소에 포함하지 않는다.

## 저장 점수 진단

[사건 진단 보고서](EXP-0065-coverage-results.md)의 고정 해시와 실제 명령을 따른다. `evaluation-manifest.json`은 정답 목록이 아니라 출처 영수증이며, 정답은 잠긴 `after-manifest.json`, 기존 확인 대응은 `after-scoring.json`이다. 원래 추론 파일 해시를 포함한 `--inference-receipt`가 필수다.

```bash
.venv-cv-batch02/bin/python scripts/audit_action_event_coverage.py \
  --baseline-lock outputs/action-recognition/exp0063/baseline/attempt-002/baseline-lock.json \
  --plan outputs/action-recognition/exp0064/regression-plan-v2/manifest.json \
  --inference-result outputs/action-recognition/exp0064/queued-inference/all45/3825ad63d2254611921ccb7b349c2feb/result.json \
  --references outputs/validation/false-confirmation-guard-all45-v1/run-001/after-manifest.json \
  --baseline-report outputs/validation/false-confirmation-guard-all45-v1/run-001/after-scoring.json \
  --evaluation-receipt outputs/validation/false-confirmation-guard-all45-v1/run-001/evaluation-manifest.json \
  --inference-receipt outputs/action-recognition/exp0064/regression-plan-v2/integration-execution-report-v1.json \
  --output outputs/action-recognition/exp0065/coverage-reproduction-new
```

현재 검토된 실제 출력은 `coverage-v1`이다. summary SHA `99db42a936988b94054fb856f593cb8edbae4a0df1619553c39c641c291e69ca`, per-video SHA `9d5cc2359cbc1f2bafdea0b9157c57a5d3202e1578ab2c9da3113c713e7b4295`를 사용한다. 새 경로로 재현하면 출처 경로가 포함된 JSON 해시가 달라질 수 있으므로 기존 검토 해시를 무조건 바꾸어 통과시키지 않고 내용과 출처를 다시 대조한다.

## 원본·박스·모델 입력 검수 영상

```bash
.venv-cv-batch02/bin/python scripts/render_action_followup.py \
  --coverage outputs/action-recognition/exp0065/coverage-v1 \
  --coverage-summary-sha256 99db42a936988b94054fb856f593cb8edbae4a0df1619553c39c641c291e69ca \
  --coverage-per-video-sha256 9d5cc2359cbc1f2bafdea0b9157c57a5d3202e1578ab2c9da3113c713e7b4295 \
  --plan outputs/action-recognition/exp0064/regression-plan-v2/manifest.json \
  --inference-result outputs/action-recognition/exp0064/queued-inference/all45/3825ad63d2254611921ccb7b349c2feb/result.json \
  --clip-manifest outputs/action-recognition/exp0063/clip-plan-v2/candidate-manifest.json \
  --test-scores outputs/action-recognition/exp0063/queued-training/train/67e95fc8cf204de7be9627e81f524931/test-scores.json \
  --prepared outputs/action-recognition/exp0063/prepared-v3/prepared.json \
  --output outputs/action-recognition/exp0065/review-media-reproduction-new
```

현재 공식 미디어는 `review-media-v2`이고 manifest SHA는 `d1ab37cf391fc7730d7d7d6f1f1715f5fa7e86240d7f33a7e49102af90ae009e`다. 25개 MP4·25개 미리보기와 모든 표시 프레임의 PTS·실제 박스·입력 위치·112픽셀 입력 해시·선정 이유를 보존했다. v1은 해시 연결 보완 전의 미등록 예비 결과다. 1번 시작 박스 해석은 기존 표본 검수에 따른 표시 선택이며, 실제 학습은 원래 양쪽 해석 내부 구간과 합집합 ROI를 그대로 썼다.

## 보강 후보와 분할

`scripts/prepare_action_augmentation.py`의 `inventory`, `plan`, `fingerprint` 단계를 순서대로 실행한다. 각 단계는 원래 자료와 기존 분할을 읽기만 하며 새 출력 파일을 배타적으로 만든다. 실제 실행 버전·장소 예약·후보 선택·내용 중복 점검과 한계는 [자료 보강 보고서](EXP-0065-augmentation-results.md)를 따른다. 공식 라벨 후보 목록은 학습 허용 목록이 아니다. 검수·내용 중복이 해결되지 않은 자료는 보류 상태로 남긴다.

## 검증과 전달

```bash
.venv-cv-batch02/bin/python -m unittest discover -s tests -p 'test_action_event_coverage.py' -v
.venv-cv-batch02/bin/python -m unittest discover -s tests -p 'test_action_followup_media.py' -v
.venv-cv-batch02/bin/python -m unittest discover -s tests -p 'test_action_augmentation.py' -v
```

실제 52행 대조와 미디어 디코딩의 독립 근거는 `runtime/action-recognition/exp0065/independent/`에 있다. 웹 등록 package·artifact 목록·새 질문 명세·화면 재생 영수증·보존 검사는 `runtime/action-recognition/exp0065/delivery/`에 남긴다. 재현 실행이나 합성 시험 통과로 새 행동 정답을 생성하지 않는다.
