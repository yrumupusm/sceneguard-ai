# EXP-0063 실제 클립 후보 생성 계약 v1 및 명시적 정상행위 v2

2026-11-06. 이 문서는 실제 학습 결과가 아닌, 저장된 공식 주석에서 전처리 전 후보를 고정하는 계약과 로컬 전체 후보 감사를 기록한다. 코드 소유 범위는 `scripts/build_action_training_clips.py`, `tests/test_action_clip_builder.py`, 이 문서와 새 `clip-plan-v1`/`clip-plan-v2` 산출물이다. 트레이너·큐·기존 보고서·카탈로그·바인딩·감사 원본은 수정하지 않는다. 영상 디코딩, 새 검출, GPU 실행, 가중치 다운로드는 이 작업에서 0건이다.

## 입력과 검수의 의미

월담 `data-audit/manifest.jsonl` 1,056원본과 정상 `normal-audit-v1/manifest.jsonl` 384원본을 사용한다. 분할은 최종 `combined-split-v3/split-manifest.json` SHA256 `bfb0f9fcd570794036cc6d2eaad46f988679b612996e21282a34821203ad5499`와 EXP-0062 `baseline/attempt-002/baseline-lock.json`에 고정한다. 원본 1,440개 중 학습671·검증153·시험296·사용자 제외313·오류격리7개를 이동하지 않는다. 장소·촬영그룹·같은 바이트 원본이 분할을 넘지 않는지 검사한다. 기존 45회귀 원본은 경로와 SHA 양쪽으로 거절한다.

작업 시작 시 웹 `pending --include-acknowledged` 조회는 성공했고 미처리 요청은 없었다. 총괄이 처리한 정확한8답변의 applied snapshot과 policy evidence를 경로/SHA 및 `(request_id, version, answer_version)`으로 검증한다. 답변은 오른쪽 박스 선호6개와 차이 없음2개이며 표본 정렬 관찰이다. 사용자는 이전 채팅에서 혼동되는 질문으로 모든 정밀 시작/종료를 인증할 수 없다고 밝혔다. 전체 시간 경계·행동 의미·ROI를 사람이 검수했다는 주장으로 확대하지 않으며 같은 질문을 다시 만들지 않는다.

manifest에는 `label_policy=official_actor_action_intervals_sampled_alignment_review`, `review_status=sampled_alignment_review_complete`와 제한된 검수 범위를 기록한다. `review_status`는8표본에 대한 처리 상태이며 각 클립의 사람 검수 완료가 아니다. 각 행의 의미 정답은 공식 주석 참조다. 최종 전처리용 불변 release는 총괄이 **manifest 생성 뒤** manifest/SHA·분할/SHA·동일 검수 snapshot을 묶어 별도로 만든다. 후보가 자기 최종 release를 참조하는 순환 바인딩은 만들지 않는다.

감사 manifest의 원본/SHA는 분할에 바인딩하며, 이 단계에서 큰 원본 영상 전체를 다시 해시하지 않는다. 실제 전처리 단계는 원본 바이트 SHA와 디코딩 PTS를 다시 확인해야 한다. 공식 JSON은 실제 파일을 읽고 감사 SHA와 대조한다. packet PTS 목록·기준 lock·설정·생성 코드·검수 근거 해시도 별도 `input-bindings.json`에 고정하며 생성 중 입력/코드 변경을 거절한다.

## 고정된 시간·박스·ROI 선택

공식 event의 actor_id/object_id와 그 구간에 있는 annotation class를 연결한다. 파일명 또는 주석 부재로 행동 정답을 만들지 않는다. `wall_over`만 양성이다. 최초 v1 음성은 명시된 `moving`/`stand`만 허용했다. 같은 원본/actor-event당 중심 클립 하나만 만들며 실패한 중심을 다른 창으로 바꿔 찾지 않는다. 모델 결과·임계값·시각·ID 예외로 선택하지 않는다.

선언 프레임 `[s,e]`가 양끝 포함일 때0번 해석은 decoded `[s,e]`,1번 해석은 `[s-1,e-1]`이다. 교집합은 decoded index `s..e-1`이다. 이 안에서8연속 native 프레임을 중심 정렬하고 두 중심이 동률이면 앞쪽을 고른다. 시작 index는 `s + floor((e-s-8)/2)`이고 `e-s<8`이면 제외한다. 3FPS에서 첫–마지막 간격은7/3초다. 반복 프레임·패딩·보간·영상 전체 라벨은 없다. 정수초 start_time/end_time를 정밀 경계로 사용하지 않는다.

decoded index `d`의 박스는0번 해석 annotation `d`,1번 해석 annotation `d+1`을 모두 요구한다. 따라서8샘플에는 보통9개의 서로 다른 annotation frame이 필요하다. 이 전체 집합에 target actor/object의 박스가 정확히 하나씩 있어야 한다. 누락·중복·모순·비유한 값·영상 밖 좌표·다중 행동을 격리한다. 전체 event의 서로 다른 class도 격리한다. 선택한 구간 바깥의 sparse warning만으로 유효한 중심을 버리지는 않지만, 선택 구간에서는 보간이나 대체를 하지 않는다. 같은 actor의 다른 event가 겹치면 object_id가 달라도 거절한다. 다른 actor의 일반 행동은 양성을 자동 거절하는 이유가 아니다.

음성은 선택된9개 주석 frame 중 **다른 actor를 포함한 원본 어디에라도** `wall_over` annotation이 있으면 제외한다. 박스가 드물어도 다른 wall_over event가 해당 구간과 겹치면 제외한다. ROI 밖의 넘기 주석도 보수적으로 제외한다. 이는 사람 한 명의 stand를 다른 사람이 넘는 화면의 음성으로 사용하는 것을 막는다.

ROI는 양쪽 해석에서 선택된 target actor 박스 전체의 static union이다. union 중심에서 가로3배·세로2배로 대칭 확대하고 바깥쪽 정수 좌표로 반올림한 뒤 영상 경계에 clip한다. 사람의 움직임과 주변 울타리 맥락을 남기기 위한 동일한 기하 정책이다. 문·울타리의 존재나 모든 crop의 적절성을 사람이 확인했다는 뜻은 아니다. `roi_human_inspected=false`, 원본 좌표계, 원래 actor union, 영상 크기, 확대 정책을 함께 저장한다. 움직이는 crop·추적·새 검출·사람별 수동 crop은 없다.

`verified_action_interval`은 기존 트레이너 인터페이스의 필드명이며, 값은 **공식 라벨의 두 원점 교집합 내부 PTS**다. 정밀 사람 검증이라는 의미로 바꾸지 않도록 `interval_basis=label_derived_both_origin_interior_not_precise_human_boundaries`를 기록한다. `temporal_alignment=annotation_interior_both_origins`, `box_alignment=official_annotations_sampled_alignment_review`다. 실제 decoded frame 가용성은 packet 개수만으로 인증하지 않고 전처리 검증 대기로 기록한다.

## v1 전체 후보 감사와 v2 변경 이유

v1 최종 후보는 `outputs/action-recognition/exp0063/clip-plan-v1/release-candidate/candidate-manifest.json`이며 초기 `draft`/`final` 중간 계획을 보존한다. 사용 가능한 중심은4,875개(1,001원본·39그룹), 제외는3,303개다. 전체8,178 event에 후보 또는 제외 기록이 정확히 하나씩 있다. 독립 로컬 oracle이 생성기를 import하지 않고 실제 주석을 다시 읽어 전체 event의 class/중심/양쪽 박스/ROI/분할/제외 이유를 확인했다.

| 분할 | wall_over | moving | stand |
|---|---:|---:|---:|
| 학습 | 1,571 | 569 | 893 |
| 검증 | 411 | 0 | 0 |
| 시험 | 582 | 304 | 545 |

v1의 제외는 사용자 제외1,265·오류 원본91·짧은 공통 내부716·허용 외/모호한 행동964·중복/모순 박스199·박스 누락66·actor event 중첩2개다. 오류7원본·사용자 제외313원본을 별도 source audit에 보존한다. 검증 정상40원본의 event는 `sit_down_bench`183개와 `sit_down_floor`184개뿐이어서 v1은 양쪽 검증 클래스 조건을 충족하지 않는다. 이 문제를 숨기거나 분할을 이동하지 않았다.

총괄은 정상행위 자료의 기존 사용자 승인 범위를 확인하고 독립 검토 뒤 [명시적 정상행위 음성 정책 v2](EXP-0063-negative-policy-v2.md)를 고정했다. 실제 전처리·학습·모델 결과 조회 전에 음성 허용 class에 `sit_down_bench`와 `sit_down_floor`를 추가했다. `--negative-policy explicit_normal_actions_v2`를 명시해야 하며 v1 기본값은 그대로다. v2 policy evidence의 허용 class와 CLI 정책이 다르면 거절한다. smoking 등 다른 class나 무주석 구간은 자동 음성으로 추가하지 않는다.8답변이 앉기 의미를 사람이 인증한 근거가 되는 것도 아니다.

v2는 새 `outputs/action-recognition/exp0063/clip-plan-v2`에 저장한다. 검증 음성이 앉기만 포함한다는 한계를 subtype 집계와 manifest에 명시한다. 검증 CE로 고른 checkpoint가 보행·대기 구분에 최적이라는 주장을 하지 않는다. 같은 장소 시험과 별도 장소 시험은 별도 집계하며, 모든 후속 지표는 의미 정답 coverage가 충분하기 전까지 공식 참조 라벨 기준이다. 행동 분류와 침입 완료 판정을 동일시하지 않는다.

v2 후보는5,741개(1,081원본·41그룹), 제외는2,437개다. 전체8,178 event의 분모를 유지한다. 최종 manifest SHA256은 `72912fab027a068d0e6043f328d86a2c7d15a239afa751d126984c5c10498931`이다.

| 분할 | wall_over | moving | stand | sit_down_bench | sit_down_floor | 전체 |
|---|---:|---:|---:|---:|---:|---:|
| 학습 | 1,571 | 569 | 893 | 159 | 393 | 3,585 |
| 검증 | 411 | 0 | 0 | 134 | 180 | 725 |
| 시험 | 582 | 304 | 545 | 0 | 0 | 1,431 |

같은 장소 시험은1,099개(양성252·moving304·stand543), 별도 장소 children-grand-park 시험은332개(양성330·stand2)다. 별도 장소의 음성2개는 충분한 정상 coverage가 아니며 합산 시험 점수로 장소 일반화 성능을 주장하지 않는다. 각 장소/그룹/분할의 정확한 집계는 `summary.json`과 `coverage-counts.json`에 저장한다.

v2 제외는 사용자 제외1,265·오류 원본91·짧은 공통 내부724·허용 외/모호한 행동6·중복/모순 박스239·박스 누락110·actor event 중첩2개다. source/event별 단일 우선 사유를 보존하며, 이 수는 독립된 실제 사건 수가 아니다. 전처리 전 데이터 구조 검사에서는 양쪽 학습/검증 클래스가 존재하지만, 실제 바이트 디코딩과 crop 내용 검증은 후속 단계다.

## 재현과 전달

```bash
.venv-cv-batch02/bin/python scripts/build_action_training_clips.py \
  --wall-audit outputs/action-recognition/exp0063/data-audit \
  --normal-audit outputs/action-recognition/exp0063/normal-audit-v1 \
  --split-manifest outputs/action-recognition/exp0063/combined-split-v3/split-manifest.json \
  --baseline-lock outputs/action-recognition/exp0063/baseline/attempt-002/baseline-lock.json \
  --review-evidence runtime/action-recognition/exp0063/review-followup-v1/policy-evidence-v2.json \
  --negative-policy explicit_normal_actions_v2 \
  --output outputs/action-recognition/exp0063/clip-plan-v2-reproduction
.venv-cv-batch02/bin/python -m unittest discover -s tests -p test_action_clip_builder.py -v
```

출력 경로는 새 경로만 허용한다. `candidate-manifest.json`은 원본/JSON 경로와 SHA, source_id, event_group, split, label, actor/object/event_index, 장소·cohort·시나리오, 실제 PTS와 index, ROI, 공식 annotation SHA/event_index/선택 annotation index와 hash를 담는다. `exclusions.jsonl`은 source/event별 사유, `source-audit.jsonl`은 모든 원본의 상태, `summary.json`은 class/place/cohort/group/split과 제외 집계, `input-bindings.json`은 입력 해시, `executed-script.py`는 실행 소스다. 로컬 raw 경로/좌표/샘플을 Git에 올리지 않는다.

17개 counterexample 시험이 통과했다. 시험은 원점 교집합, 양쪽 박스 union,9번째 주석 누락, 중복/모순·비정상 좌표, 타인 넘기 음성 오염, 다른 object_id의 동일 actor 충돌, 명시적 앉기 v2, 원본/그룹 누수,45회귀 제외, 검수의 정확한 버전/해시를 확인한다. 전체 후보 oracle은 합성 시험과 별도로 저장한다. v2의 `full-candidate-audit.json`도 전체8,178 event에 대해 통과했으며 후보5,741/제외2,437과 모든 단일 제외 사유가 독립 재계산과 일치했다. 검수 표본의 한계와 실제 전처리·훈련·평가 미실행 상태는 유지한다.
