# EXP-0064 행동 점수 관측층 통합 준비 독립 검토

2026-11-06. EXP-0063 학습 준비 독립 검토 중 총괄이 추가 배정한 읽기 전용 검토다. 구현·큐·원본·기존 사건 상태를 수정하지 않으며, GPU 실행이나 기본 적용을 승인한 문서가 아니다.

현재 판정은 **최종 v2 CPU 계획·소스·큐 연결 검토 통과, 구현 파일 커밋 가능, 실제 GPU 추론은 대기**다. 실제 실행 전 합성 시험만으로 전체45개 실행·성능 개선을 인증하지 않는다. 실제 학습 준비의 단계별 판정은 `EXP-0063-training-readiness-review.md`를 따른다.

## 고정 범위

`docs/experiments/EXP-0063-integration-plan.md` SHA256 `25e9a1d0c839c45a29f658fb247ee2658738f378f921c62bba0a6ab0896c3868`를 읽었다. 기존 EXP-0062 AFTER의45개 원본·실제 observed 추적 박스와 사건 출력을 보존하며, 원본 PTS0의3FPS 목표격자에 가장 가까운 native 프레임을 사용한다. 양성 점수는 넘기 동작 후보일 뿐 침입 확인·해제·완료로 전파하지 않는다.

이번 추가 배정 시작의 웹 `pending --include-acknowledged`는 성공했고 미처리 요청은0이었다. 기존 여덟 표본의 정렬 관찰을 전체 동작/완료 정답으로 확대하지 않는다. 기존 공식52시간참조,006미확정·008보류와 부족한 사람 정답은 보존한다.

## draft에서 확인한 설계와 초기 발견

- `sample_grid`는 실제 native PTS를 사용하고 동률이면 앞 프레임을 고르며 동일 native 프레임 반복을 거절한다. 같은 track의8개 실제 observed 박스가 모두 있어야 창을 만든다. 예측 박스·새 ID로 결측을 채우지 않는다.
- `process_video`는 원본을 EOF까지 한 번 디코딩하고 전체 tracking native PTS와 대조한다. 최대8개 샘플 프레임과4개 crop을 유지하며 source 마지막 PTS에서 남은 batch를 처리한다.
- 창의 `available_after_pts`와 실제 batch의 `batch_flushed_at_source_pts`는 다르다. 후자의 지연을 첫 실시간 통지 시각으로 숨기지 않으며 `real_time_notice_measured=false`다.
- 전체 track×global-window 교차의 관측0창과 최소 한 개 실제 관측이 있는 창을 분리한다. active denominator는 적격+부분 관측 창이며, 이를 사람 검증 검출 누락률로 부르지 않는다. 한 번도 검출되지 않은 사람은 이 추적 기반 분모에 나타나지 않는다.
- baseline JSON은 별도 출력에 원래 바이트로 복사하고 해시를 전후 대조한다. 사건과의 관계는 `temporal_overlap_only_identity_unknown`이며 사람 동일성·원인·확인 상태를 전파하지 않는다. 상태 불변은 구조적 보존 성질이고 성능 향상의 증거가 아니다.

초기 `standalone_contract`는 test score 파일이 비어 있지 않다는 조건만 검사했다. 따라서 일부 시험 행만 남은 파일도 완료한 standalone 평가로 통과할 수 있었다. 총괄에게 **frozen training manifest의 전체 test clip ID·정답과 정확히 일치하는 고유 목록, 유한0..1점수, 동일 성공 attempt의 인접 training contract manifest/config 바인딩**을 요구하도록 전달했다. 최종 소스는 이를 검사하고 원래 평가 함수로 보고서까지 재계산해 대조한다. 해당 반례 시험을 포함한 최종44개 시험을 독립 실행하여 모두 통과했다.

고정 integration-plan 문서 SHA도 최종 실행 계약에 연결됐다. `action-infer`는 기존 큐에 허용 명령만 추가하며 기존 공유 GPU 잠금·supervisor·실제 running attempt·현재 배정·커밋된 소스 바인딩을 그대로 요구한다. schema migration은 백업 후 기존 행을 보존하고 활성 예약이 있으면 거절한다. inference는 별도 검토 없는 retry를 거절하며 기존 action-train 분기는 유지된다. 최종 inference의 Torch import 전 CUBLAS 설정도 학습과 일치한다. 학습 최저 validation CE checkpoint, 전체 시험 평가, 성공한 원래 training receipt 및 checkpoint 전체 SHA를 실제로 확인하기 전에는 GPU inference GO를 내릴 수 없다.

## 최종 CPU 소스와 독립 근거

`outputs/action-recognition/exp0064/regression-plan-v2/final-cpu-source-bindings.json`의 다음 바이트를 시험 전후 대조했다.

| 파일 | SHA256 |
|---|---|
| orchestration/queue.py | `43867d3a8c937c3096ae7bd2cf972d05e78f0aafef80d1a0c20305c5888e6279` |
| scripts/prepare_action_regression.py | `71c5b07d088467afa89991709f3c59df39af2324fe9bd1dede79e8c7cdad2ba2` |
| scripts/infer_action_regression.py | `7bccb00554f9b7ba248f7b009b553882a2e61d12fc4638e5e56d079b1c9faf4c` |
| orchestration/action_inference_command.py | `3dc6a86c9fbb49588e382b78b869c393ee3db502ed13e0a774e69dc01099eb37` |
| tests/test_action_regression.py | `99cc53b2fe17ae543a0323d8de6cc6f3d1b6a22ab932f15f161af5a2d578b425` |
| tests_orca/test_action_inference.py | `bed054d2eb7ce9560a081d7004938e4b54bbcc9ecfcf62583a89311e8641b1f4` |

최종 독립 시험은 action regression/inference/training adapter/기존 queue의44개로8.062초에 통과했다. 로그와 해시는 `runtime/action-recognition/exp0064/independent-integration-review/`의 `final-tests.log`, `final-reviewed-source-bindings.json`에 있다. 합성 계약/큐 시험은 실 GPU 실행 증거가 아니다.

v2 manifest SHA는 `f8bea6c8b4b36d5d09daf8f3b43a7e8923319ef5bde3b5c4e5cd5f00f0f7cb17`다. planner를 import하지 않는 별도 oracle로45개 저장 tracking의184,300 native PTS,3FPS 최근접 선택, 실제 observed 박스8개, 같은 track, ROI union과 확장, 모든 누락 창을 재구성했다. 기존 baseline405파일의 해시도 동결 lock과 일치했다. 18,459샘플 프레임·6,053전역 창·1,408track ID에서 적격3,573창, 부분 관측5,057창, 관측0창179,245개로 계획과 모두 일치했다. 실제 관측이 한 번 이상 있는 분모8,630창과 전체 교차 분모187,875창은 별개다. track 수는 사람 수가 아니며 누락 비율은 사람 검증 재현율이 아니다. `audit_plan.py`와 `plan-independent-audit.json`이 독립 근거다.

canonical DB를 읽기 전용으로 확인해 기존95 jobs와95 attempts의 각 행 해시가 최초 보호 스냅샷과 모두 같았다. 이 검토는 새 작업 등록·migration·GPU·실제 픽셀 디코딩을 수행하지 않았다.

보존 한계: 구현 담당이 초기 v1 계획 디렉터리를 삭제한 뒤 재생성했고 최초 v1 해시는 기록하지 않았다고 보고했다. 현재 v1은 재생성 진단 자료이므로 최초 v1 바이트 보존을 인증하지 않는다. v2는 동결된 원래 tracking에서 독립 재계산했고 기존 baseline/원본/큐 변경이나 모델 결과 생성은 없었다. 이 한계를 v2 계획의 검증과 구분한다.

## 남은 검토

1. 위 최종 소스의 구현 담당 커밋을 확인하고 실제 실행 authorization의 HEAD와 소스 바인딩을 다시 대조한다. 3,573개는 CPU 계획 창 수이며 GPU 실행 완료 수가 아니다.
2. 실제 전구간 디코딩·픽셀 crop·GPU 추론 결과가 준비되면 native PTS 및 원본·baseline 보존과 실제 결과 수를 확인한다.
3. 실제10epoch 학습·validation 선택·test 완료 receipt와 weights SHA가 고정된 후에만 inference 입력을 연결한다. 사람 행동 정답 부족 지표, 침입 완료 정확도·실제 개선은 null을 유지한다.
4. 기존95 queue jobs/attempts와45 baseline 출력은 새 작업 추가와 구분해 보존을 확인한다. 현재 GPU 실행·queue migration은 이 검토자가 수행하지 않았다.
