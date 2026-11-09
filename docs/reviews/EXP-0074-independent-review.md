# EXP-0074 독립 검토

2026-11-09. **라벨 보완·저장된 A 기준선·B/C 준비 범위를 승인한다. 이 검토는 재학습 실행 승인이나 성능 개선 판정이 아니다.** 최종 안정화 통지를 받은 뒤 자료·코드·보고서·계획 바인딩을 확인했다. 준비 범위에 남은 차단 결함은 발견하지 않았고, 검토 중 발견한 P2 세 건은 수정 후 재검증했다.

검토 대상은 데이터 exporter, baseline 평가·렌더링·P01 검수 준비, 미래 checkpoint 평가, B/C 준비·trainer·canonical queue 연결 및 관련 시험이다. [주 결과](../experiments/EXP-0074-results.md), [계획](../experiments/EXP-0074-protocol.md), [데이터 준비](../experiments/EXP-0074-data-readiness.md), [B/C 준비](../experiments/EXP-0074-bc-preparation.md)의 수치와 주장 범위도 대조했다. 검토자는 새 모델 추론·학습·GPU 실행·미디어 열람/업로드·실제 큐 변경·웹 쓰기·Git 변경을 하지 않았다. 합성 CPU 단위 시험과 저장된 수치 재계산만 수행했다.

## 발견 사항과 해결

| 심각도 | 발견한 구체적 문제 | 최종 상태 |
| --- | --- | --- |
| P2 | 미래 `dataset_contract`가 학습 행의 `person_completeness_verified=false` 또는 누락을 거부하지 않아 불완전 라벨이 계획에 들어갈 수 있었다. | 행마다 명시적 `true`를 요구한다. false/missing 반례를 직접 다시 실행해 거부를 확인했다. 현재197의 완전성에는 문제가 없었다. |
| P2 | 원본 SHA가 같은 train/development 프레임도 event/reservation 문자열이 다르면 미래 계약을 통과했다. | 유효한 원본 SHA256 필수 및 원본별 split 분리 검사를 추가했다. SHA 누락·잘못된 형식·같은 원본의 교차 분할을 모두 거부한다. 현재197/수정72의 분할에는 문제가 없었다. |
| P2 | 새 B/C checkpoint 평가가 A용 요약 필드를 재사용하여 B/C의 FN을 `recovery_denominator`로 표시하고, 해당 조건 검출을 `baseline_detected`로 표시할 수 있었다. | `summarize_epoch`가 조건 누락을 `condition_missed_gt_rows`, 검출을 `detected`로 분리하고 A 참조 필요를 명시한다. A 검출/B 누락 반례에서 A 회복 분모0이 유지되는 회귀 시험이 통과했다. |

이 수정은 기존 확정 라벨이나 A 예측을 바꾸지 않았다. 미래 실행에는 여전히 별도 실행 release와 실제 배정·큐 조건이 필요하며, 이 보고서를 그 release로 사용하지 않는다.

## 라벨과 분할 검증

고정197의 이미지·라벨 해시, PNG 해상도, YOLO 좌표 왕복, 기존 EXP67/71 좌표·ID 보존을 확인했다. 학습은122프레임/333박스, 개발은75프레임/56박스이며 개발의 명시적 빈 프레임은25다. 기존 case5는 legacy 개발 closure를 유지하며 예약19로 재배정하지 않았다. P05의 검수된 이동과 빈 프레임을 원본 전체의 행동 종류 때문에 제외하지 않았다.

별도 수정본은72이미지/71불완전 라벨이다. 승인 좌표5개와 배경 후보17개 제거가 보존되며, 보류71프레임의167박스는 승인5+미확정162다. 야간23.333초의 한 프레임은 진단 후보2개를 보존하되 라벨을 내보내지 않았다. 수정본을 신규 완전 정답이나 고정197에 편입하지 않았다.

고정197과 수정72를 합친269프레임에서도 원본 SHA·event group·capture reservation의 학습/개발 교집합은 각각0이다. 학교45/EXP64 시험의 보호 원본 해시와 고정197의 교집합도0이다. 이는 메타데이터 분리 검사이며 물리적 촬영 독립성 인증이 아니다. 특히 기존 case5의 촬영 연관 한계는 남는다.

P01 검수 패키지는 index168/175/185의 세 장만 포함한다. 저장된 원본 RGB/시각 바인딩과 후보 좌표·ID가 수정본의 미확정 후보와 일치한다. 기존 승인5좌표·제외 야간 프레임을 다시 묻지 않고 신규 GT는0이다. 검토자는 영상을 열어 사람 여부를 새로 판단하지 않았다. 시작 및 최종 WEB pending 읽기 전용 조회는 모두 미처리0건이었다.

## A 기준선 독립 재계산

생산 matcher를 호출하지 않는 별도 subset dynamic-programming 최대 매칭으로197프레임을 재계산했다. 모든 프레임의 TP/FP/FN이 저장값과 일치했고, 저장 매칭의 GT/예측 일대일성·IoU≥0.5·confidence≥0.5·unmatched 집합도 확인했다. 전체1,654,800 anchor에서 top300 및 저장 confidence0.05 필터 결과가 저장 예측과 일치한다. A 개발75 예측 subset도 원본 예측의 정확한 부분집합이다.

| 범위 | 프레임 | GT 박스 행 | TP | FP | FN |
| --- | ---: | ---: | ---: | ---: | ---: |
| 개발 | 75 | 56 | 56 | 0 | 0 |
| 학습 진단 | 122 | 333 | 288 | 9 | 45 |

개발 GT는 입력640 기준 중간28·큰28·작은0이다. **A 누락 회복 분모는0이며 개선 효과는 아직 측정할 수 없다.** 학습45FN을 개발 분모로 옮기지 않는다. 개발100%는 제한된 검수 프레임의 박스 결과이며 고유 인원·침입 성공·학교 성능·독립 일반화를 뜻하지 않는다. 학습 빈 배경0, 미편입 주·야간 예약19, 개발 작은 사람·가림·야간 조건 부족을 최종 결과 문서가 명시한 것도 확인했다.

baseline의 저장 invocation은 CPU FP32, epoch0/optimizer step0 초기 checkpoint와 평가 전후 모델 상태 보존을 기록한다. 그 실행을 검토자가 다시 수행한 것은 아니다. 저장 예측·해시·계산 결과 및 실행 코드를 대조한 검토다. 대표영상3개의 해시와 총75프레임 메타데이터를 확인했으며 브라우저 재생/시각적 적절성 검수는 총괄 전달 범위다.

## B/C 준비와 실행 차단 검증

최종 `plan-v3.json`은 현재 manifest·원본 이미지·가중치·소스·환경에서 다시 만든 계획과 완전히 일치한다. B/C는 동일 초기 checkpoint, seed68, batch2,640,FP32,AdamW lr0.0001, loss/clip 설정 및 epoch별 프레임 순서를 공유한다. 각 epoch61batch, 총305step을 계획하며 epoch5를 고정 선택한다. 모델을 학습한 `last.pt`로 초기화하지 않는다.

C는 `model.train()` 뒤 BN만 eval 모드로 바꾸고 affine weight/bias와 나머지 파라미터는 학습 가능하게 유지한다. B는 누적 통계를 갱신한다. 저장된 실제 YOLO CPU 합성 forward 근거는124BN/396파라미터 텐서, B buffer372개 변경/C0개 변경, 파라미터 불변, optimizer/backward0을 기록한다. 이 근거는 최종 dataset guard 수정 전의 v3이며 BN/초기화 검증 함수 본문 해시가 이후에도 동일함을 독립 확인했다. 최신 소스로 실제 모델을 다시 실행했다고 소급하지 않았다.

epoch-01–05 checkpoint 저장 코드는 모델·state_dict·optimizer·step·설정/자료/소스 해시를 담고 fsync 후 배타적으로 게시한다. 합성 모듈의5회 저장/재로드·중단/덮어쓰기 거부를 확인했지만, 실제 YOLO의 populated optimizer checkpoint와 실제 학습 수렴은 미검증이다. 미래 CPU evaluator는 실제 checkpoint receipt/manifest/state 바인딩과 C BN 불변을 확인하고 A와 같은 전처리·head·top300·고정 임계값을 사용한다. 실제 B/C 모델이 없어 해당 평가 실행은 하지 않았다.

미승인 B/C envelope 두 개가 최종 계획을 정확히 가리키며 `authorization=null`인 상태에서 validation에 실패함을 확인했다. 실행 경로는 committed source, 새 independent release/root grant, 실제 배정, canonical snapshot·running attempt·상속 lock FD·supervisor identity·resource gate를 요구한다. 큐 성공에는5개 실제 checkpoint 영수증과 정확한 step/epoch5가 필요하고 자동 retry는 거부한다. 기존 명령 이름·행·foreign key·backup 보존과 결과 없는 exit-zero child 실패는 임시 큐에서 시험했다.

최종 canonical DB 읽기 전용 확인은145jobs/145attempts, EXP74 B/C job0, 새 명령 schema migration0이다. 실제 큐를 열어 쓰거나 작업을 등록하지 않았다.

## 시험과 근거 고정

독립 실행한 서로 다른 시험은 총66개이며 모두 통과했다: 데이터14, baseline/checkpoint6, matcher9, 기존 queue14, B/C23. B/C23개는 `torch.optim.AdamW` 생성 자체를 차단한 상태에서 실행했고 CUDA 미초기화를 확인했다. 합성 forward/backward와 임시 checkpoint/queue 시험을 실제 모델 학습 성능으로 계산하지 않는다.

상세 로그·반례 전후·독립 재계산 코드·파일 바인딩은 로컬 `runtime/model-comparison/exp0074/independent-review-v1/`에 보존했다. 공개 문서에는 원본 이미지·좌표·DB·가중치를 포함하지 않는다.

| 검토한 근거 | SHA256 |
| --- | --- |
| 최종 주 결과 보고서 | `15ea621c6b74b8ce0f206ac15f03707cff39f94f67c3156d179fa57b97d0c4a8` |
| 고정197 manifest | `01a08a3d42e610a3489b05859c9425ffe462b3709f46f967ea4537a48df2cf90` |
| 별도 라벨 수정 manifest | `39f467258ff66ccf685a362e4fc53f910e9b11df084d070767cb0e68c9a9d1bf` |
| A evaluation | `5563222273d2d579d0591a98ff800b21929ef671cdc7965fc05a96ea893cec57` |
| 최종 B/C plan-v3 | `6eced8e2ba857f3efd55d0d092713d9462e4462c917c279974f602b22e672dc7` |
| 독립 review-evidence.json | `8a2836652ad54b6be9fe9f07234bb76c261e5da646b608b35d3ba7e527c7a608` |

최종 판정은 **현재 준비 범위 통과, 재학습 미실행, B/C 성능 미측정, 독립 시험 미확보**다. P01의 새 사람/완전성 확인과 필요한 개발 보강은 실제 사용자 검수 후 별도 revision으로 처리해야 한다. 이번 검토는 추가71프레임 전부의 재검수나 자동 GT 승격을 요구하지 않는다.
