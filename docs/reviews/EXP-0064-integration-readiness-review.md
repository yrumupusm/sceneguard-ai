# EXP-0064 행동 점수 관측층 통합 준비 독립 검토

2026-11-07 최종 보완. EXP-0063 학습 준비 독립 검토 중 총괄이 추가 배정한 코드·실제 통합 결과·공개 지표 읽기 전용 검토다. 구현·큐·원본·기존 사건 상태를 수정하지 않았고 GPU를 실행하지 않았다.

현재 판정은 **실제 45개 전구간 별도 비교와 최종 공개 수치 검증 통과, 운영 채택 보류**다. 184,300 native 프레임·3,573개 점수·467개 후보 창과 기존 출력 405개 보존을 확인했다. 입력 준비부터 배치 처리까지 원본 시간 기준 최대 차이 85.9초가 있으며 오프라인 비교로 한정한다. 사람 행동 성능·침입 개선·실시간 알림 성능과 웹 전달 완료는 인증하지 않는다. 실제 학습 및 별도 장소 정상 2/2 FP 한계는 `EXP-0063-training-readiness-review.md`를 따른다.

**아래의 CPU 준비·실제 추론 대기는 단계별 이력이다. 최신 바이트·완료 증거·한계는 마지막 실제 결과 절이 우선한다.** 추가 추론·튜닝·기본 적용의 승인이 아니다.

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

후속 train-only provenance adapter commit `4db1231`은 공용 `action_training_command.py`를 수정하지만 이 문서의 queue/inference/CPU 계획 소스는 바꾸지 않았다. 해당 변경의 독립85시험에는 이 integration/inference 회귀도 포함됐고 모두 통과했다. 최신 공용 adapter SHA와 실제 준비·자원 보류 상태는 `EXP-0063-training-readiness-review.md`의 마지막 보완 절을 따른다. 따라서 실제 inference authorization은 과거 source freeze를 재사용하지 않고 최신 공용 adapter까지 포함한 커밋 바이트를 새로 연결해야 한다.

보존 한계: 구현 담당이 초기 v1 계획 디렉터리를 삭제한 뒤 재생성했고 최초 v1 해시는 기록하지 않았다고 보고했다. 현재 v1은 재생성 진단 자료이므로 최초 v1 바이트 보존을 인증하지 않는다. v2는 동결된 원래 tracking에서 독립 재계산했고 기존 baseline/원본/큐 변경이나 모델 결과 생성은 없었다. 이 한계를 v2 계획의 검증과 구분한다.

## 남은 검토

1. 위 최종 소스의 구현 담당 커밋을 확인하고 실제 실행 authorization의 HEAD와 소스 바인딩을 다시 대조한다. 3,573개는 CPU 계획 창 수이며 GPU 실행 완료 수가 아니다.
2. 실제 전구간 디코딩·픽셀 crop·GPU 추론 결과가 준비되면 native PTS 및 원본·baseline 보존과 실제 결과 수를 확인한다.
3. 실제10epoch 학습·validation 선택·test 완료 receipt와 weights SHA가 고정된 후에만 inference 입력을 연결한다. 사람 행동 정답 부족 지표, 침입 완료 정확도·실제 개선은 null을 유지한다.
4. 기존95 queue jobs/attempts와45 baseline 출력은 새 작업 추가와 구분해 보존을 확인한다. 현재 GPU 실행·queue migration은 이 검토자가 수행하지 않았다.


## 실제 학습 모델 연결과 재개 실행기 검토

별도 standalone 학습은 revised attempt `67e95fc8cf204de7be9627e81f524931`의10epoch·전체1,431test로 완료됐다. 검증 손실 최저 epoch6의 `best.pt` SHA는 `8b4e2eb74bee656f651a172403e4ddfe1e1ce8f9a4438d70c76b5a1b17825b73`다. 원래 실패 시도와 두 smoke를 보존하며, 실제 결과·checkpoint·AMP 카운터·공식 참조 수치의 독립 검토는 학습 준비 검토 문서 및 runtime `training-v2-result-independent-audit.json`, `training-checkpoints-v2-independent-audit.json`을 따른다. 별도 장소 음성2개가 모두 FP인 한계와 사람 기준 지표null을 유지한다.

실제 실행에 사용한 source freeze는 HEAD `166c96aa0ee3de18b8d1fe01f26b7430084adef3`, v5 SHA `de1b2368f7fda067422732d1e402da9631adca2361a7857b7bc17fca2ecafe5f`다. 현재 파일·Git21개 바이트를 대조했다. runtime launcher v3 SHA `98e4d2f8e5a718a0b363932be74ae8f2c5df1c6390c8635e9cd8347ff58d09e5`는 이미 검토한 v2에서 HEAD·freeze경로/SHA·독점 실행 marker만 바꾼다. 이전 v1/v2 파일은 보존됐다. 별도7CPU stub 시험을 독립 실행해0.272초에 통과했고, 이 시험은 실제 GPU 추론이 아니다.

최종 CPU 입력 후보 `e887c2ac87d6208e12c3611f4d8587f79cc5797396fb58be57aeb583fbebd6f9`와 입력 파일 SHA `73bce77cedad5fcffc087895a164365f5ace4028bfbe77bf39150a0a4cfa98ff`, canonical digest `a63cde50fc4bb4f19a7142570cd6ece8733656a00b9229501655fedd665d1b96`를 독립 대조했다. 현재 `standalone_contract`가 실제 성공 training receipt·같은 attempt의 config/history/test/checkpoint와 epoch6 선택에 대해 통과했다. 원래 독립 감사한45개 계획에서 plan45·selected-source675·baseline405 바인딩을 다시 구성해 실제 입력의 모든 맵과 같음을 확인했다. 원본 미디어 중복 scan이나 새 모델 로드는 하지 않았다.

총괄의 단일 GO `msg_2d96d46b6172`는 runtime launch plan SHA `a0060e3e14f2b030432ddd000730884961c25232f67a43e480ef30152c2fd0ec`, 최종 config SHA `beecff4ca1ff9e384dc5c4d53f624bfaf755579a0ff30cc874b4d70c6785e3f3`, authorization SHA `b51adc4a4a5d60ee92241a7927a9b2535433a0fa09ed8b5a2300ebf8d30b7809`와3600초 timeout을 연결한다. 이 바이트·새 live context·고정 input/source 연결을 읽기 전용 확인했다. 실행기는 자원 gate와 독점 marker·enqueue_started·unknown 상태의 읽기 전용 복구 정책을 유지하며 자동 retry하지 않는다.

## 표시 자료와 기존 사용자 관찰의 범위

실제 standalone summary SHA `3b9ac6817d3540f41ec808a38cfc8921ab0220c2a41528f95cff56a28e9f69e8`와 failure manifest SHA `2abca9ddd2fc2f164af2f83ea55fd557963050704292eb9850f0bab2b881bc54`를 원래 시험 점수와 독립 산술에 대조했다. 두 FP 표시 영상/JPG의 현재 SHA,각8프레임·3FPS·960×630과 원본 nativePTS를 확인했다. 영상은 실제 model sample 시점의 원본 문맥에 ROI를 표시한 자료이며,112px 입력 tensor나 원본 FPS의 연속 구간을 뜻하지 않는다. 원본 미디어를 cloud vision에 올리거나 실제 행동 의미를 새로 판정하지 않았다.

두 구간은 기존 EXP0063 표본 검수의4-61 actor0(request-5beb7b452b1d4abd82f3e198c0f14cb2,`exp0063-wall-00-video`)와4-62 actor1(request-f6003c590bd64bb3afa7fb1a7f75866e,`exp0063-wall-05-video`)다. 두 답변 version4/answer_version1을 다시 읽었고 오른쪽 박스 선호 및 작은 시간 차이라는 관찰을 재사용한다. 새로운 것은 모델-공식 라벨 불일치 결과이며 새 장면이 아니다. 이를 새 검수 대상으로 표현한 검토 메시지는 정정했고 실제 반복 요청은0개다. 과거 정렬 관찰을 전체 의미·시작/끝·정상 정답으로 자동 승격하지 않는다.

공개 지표 runtime draft가 다른 모델의 standalone summary와 회귀 결과를 잘못 짝지을 수 있음을 발견했다. 총괄은 checkpoint/training result/history/test/manifest SHA의 정확한 연결,고정45개 고유 ID·영상별 native/sample/window 수·합계,원래 계획 baseline map과 복사 hash map의 대응을 추가했다. 또 browser draft는 정지된 video node의 polling 유지밖에 보이지 않았으므로 실제 재생 지속을 주장할 수 없었다. 수정본은 polling 동안 muted 첫 영상을 재생하고 unpaused/timeupdate/decoded-frame 증가와 node 보존을 확인한다.

최종 runtime 소스 검토 SHA는 summarize `8a610f10816e3e014e7b4c4f39703eaf0f9a117b2431b14ede5c36508356e5de`, build-metrics `3a3189aae96ea86268d05afa9459a66003d43b9d6b3f0145f701bb365d066916`, browser probe `15fc67398f3b181dbb90c96854fd821bdcd679ccad486e164b363e6e24cd7127`다. 실제 최종 지표나 브라우저 실행 통과는 해당 실제 결과/receipt 확인 전 주장하지 않는다. 고정 source/HEAD는 수정하지 않았다.


## 실제 all45 결과 독립 검증

canonical job `54af6a33721a480bad99dba88535a0b9`, attempt `3825ad63d2254611921ccb7b349c2feb`는 succeeded/exit 0이다. 결과 경로는 `outputs/action-recognition/exp0064/queued-inference/all45/3825ad63d2254611921ccb7b349c2feb/result.json`, SHA는 `b465170efe203655deb76f857549101180e6ce56171ae510c69347595d7e34a8`다. supervisor 2341948·child 2342044·launcher 2341619의 종료를 확인한 뒤 문서 동결을 해제했다. 실제 실행의 코드 HEAD는 `166c96aa0ee3de18b8d1fe01f26b7430084adef3`로 유지됐으며, 이후 보고서 전용 커밋을 실행 코드 변경으로 오인하지 않는다.

별도 `audit_actual_inference.py`로 고정 계획의 정확한 45개 ID와 모든 score row를 검증했다. native 프레임 184,300개, 점수 3,573개, threshold 0.5 이상 후보 467개가 맞다. 각 창·sample PTS·같은 track의 실제 박스 8개·ROI·메타데이터·최종 부분 batch까지 처리 시각과 기존 카드의 시간상 연결이 계획과 일치한다. 42개 영상에 후보가 하나 이상 있지만 42/45를 재현율로 해석하지 않는다. 원래 baseline 405개와 별도 복사본 405개의 모든 SHA가 같고, 이전 큐의 99개 job·99개 attempt 각각의 행 SHA가 유지된다. 공유 DB 전체 파일 바이트가 불변이라는 주장은 하지 않는다.

원본 native PTS 184,300개에 대해 선택된 모델용 sample은 18,459개다. 실제 관측이 한 번 이상 있는 창 8,630개 중 적격 3,573개·부분 관측 5,057개이며, track와 전역 창의 교차에서 관측 0인 179,245개는 별도다. 관측 부족은 사람 검수 검출 FN이 아니고 검출되지 않은 사람을 이 분모가 모두 포함하지도 않는다. 1,408 track ID도 사람 수가 아니다. 기존 사건 상태 변경은 0이며 사람 행동 precision/recall/F1·침입 완료 정확도·성능 개선은 미측정이다.

전체 3,573행에서 `batch_flushed_at_source_pts - available_after_pts`를 독립 계산한 최대값은 85.9초다. E01_040의 window `000141-1`은 입력 준비 49.333333초, 마지막 batch 처리 135.233333초다. 이는 저장 영상을 순서대로 처리한 원본 시간축의 차이이며 wall-clock 실시간 지연 측정값이 아니다. 늦게 처리한 점수를 과거 입력 시각의 알림으로 소급하지 않는다. 현재 비교는 오프라인 관측층으로만 통과하며 실시간 통지 성능을 인증하지 않는다.

독립 근거는 `runtime/action-recognition/exp0064/independent-integration-review/`의 `actual-inference-independent-audit.json`, `actual-inference-audit.log`, `actual-inference-exit-proof.json`, `final-public-report-metrics-review.json`이다. 실제 canonical 실행과 원래 결과를 읽기 전용으로 대조했으며 새 추론이나 GPU 실행을 하지 않았다.

## 최종 공개 보고서·39지표 판정

| 자료 | 검토한 SHA256 |
|---|---|
| `docs/experiments/EXP-0064-results.md` | `d222f1e8f2055c8a0a68d799157ff2b5ec0622b81c74d9f8ff531b9e1aa37337` |
| `records/EXP-0064/metrics.json` | `ef39ca9ab51c1abebd3a31debf8bf5fa32b5879a008f95eaee1de3bf5eb688f2` |

39개 지표의 고유 이름·수치 33개·미측정 null 6개와 출처 파일의 현재 SHA를 대조했다. 세 시험 cohort의 TP/FP/FN/TN과 precision/recall/F1, 행동별 FPR·분모, 2,250/2,248/2 update 기록, 선택 epoch 6, 최대 할당 848.65771484375 MiB, 45개 처리 수치가 독립 결과와 일치한다. 467개는 겹치는 후보 클립이며 침입 사건 수가 아니다. 기존 상태 변경 0은 구조상 보존이며 성능 개선 증거가 아니다. 사람 기준 3지표와 검출 FN·침입 완료·45개 행동 정밀도는 null이다.

공개 보고서는 공식 annotation 참조, 여덟 정렬 관찰의 제한된 의미, 별도 장소 음성 2/2 FP, 검증 음성의 앉기 편중, 두 실패 장면의 기존 검수 재사용, 오프라인 최대 85.9초 차이와 채택 보류를 명시한다. 계산·수치·보존 검토의 미해결 차단 사유는 없다. 독립 일반화·완전한 사람 정답·실시간 침입 알림 개선을 주장할 근거는 부족하다. 추가 튜닝·재검수를 자동 시작하지 않는다.

브라우저 probe는 소스 검토만 했으며, 실제 등록·재생·되감기·polling 유지·게시 완료는 본 검토에서 인증하지 않았다. 별도 전달 기록의 실제 증거가 필요하다. 이 제한은 계산 완료 판정과 구분한다.
