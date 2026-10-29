# BATCH-0004 — 공식 API 복구 성공, 관절 품질에 따른 확대 보류

2026-10-29 KST. **공식 YOLO.predict로 두 native frame의 실제 추론과 원본/관절 비교 이미지 생성에 성공했다.** 오류·재시도는0이다. 다만 핵심030:90에서 사람/관절 출력이0개여서 유용한 관절 관측이 확인돼야 한다는 조건을 충족하지 못했다. remaining265와 행동 규칙·추적은 실행하지 않는다. 기존 모델을 교체할 근거는 없다.

| 입력 | 실제 반환 | 관절 품질과 행동 판단 |
| --- | --- | --- |
| E01_030 90초 | 정상 Results, 사람 후보0·관절0 | 기존 사용자 관찰은 세 사람이 문을 넘는 장면이다. 고정 native frame에서 관절 근거를 얻지 못함. 0출력을 정상 행동으로 읽지 않음 |
| E01_007 64초 | 정상 Results, 사람 후보2행·신뢰도 기준을 통과한 관절 추정23개 | 원본/오버레이 확보. 사람별 대응·가림·좌우 혼동은 사람 검수 대기. 출력 행은 person/track ID나 시도/완료 판정이 아님 |

23개는 confidence≥0.5·유한/원본 범위·비(0,0) 조건을 통과한 **추정값**이다. 정확한23관절 또는 사람2명 복원으로 해석하지 않는다. 새007 위치 검수만 두 로컬 비교 자료와 함께 한 번 요청했고030의 기존 사용자 관찰은 재사용했다. 클라우드 에이전트가 CCTV/관절 이미지를 확인한 것처럼 서술하지 않는다. 030 overlay에 골격이 없는 것은 파일 생성 실패가 아니라 실제 빈 예측이다. 정밀 GT 없는 정확도/recall/F1/FPR·완료·법적 침입 판단은 산출하지 않는다.

## 바뀐 경로와 실제 실행

이전 EXP-0021은 직접 inner-model 호출의 초기화/인자 문제로 성공 예측을 반환하지 못했다. EXP-0022는 같은 Ultralytics8.4.192·YOLO26m-Pose 체크포인트·환경·267개 native PTS/RGB를 유지하고 공식 public API로 바꿨다. RGB를 연속 BGR ndarray로 전달하고 Results의 원본 좌표를 재변환하지 않는다.

공식 predictor의 end2end 선택·fusion·첫 warmup을 따랐다. 이전 unfused/no-warmup 실패 경로와 실행 방법까지 동일하다고 주장하지 않는다. full-frame640/FP32/batch1/conf0.25/nmsFalse/rectFalse로 고정했다. sample forward2회와 별도의 공식 warmup forward1회를 관측했다. 새 가중치·모델·학습·입력 크기/임계값 변경은 없다.

CPU 검사30개, 독립 검사15개 및 핵심 회귀3개가 통과했다. 겹치는 검사를 독립 요구사항/예측 수로 합산하지 않는다. 실행 source `7c281e34bc12bd9b53f7cebe73f313f801f870e2`, 기존 Run/단일 GPU queue의 job `c99e0da0610348e7a74bf38d66d19801`, attempt `6509c805b40e4d7a8137f770cfa04a05`가 성공했다. [상세 보고서](EXP-0022-yolo26-public-predict.md), [ADR-0021](../decisions/ADR-0021-yolo26-public-predict.md)을 따른다.

## 비용과 해석 범위

| 측정 범위 | 관측 |
| --- | --- |
| 실행 전 여유 VRAM | 7864MiB, 기존6144MiB 기준 통과 |
| CPU checkpoint/YOLO 생성 | 0.2215초. CUDA 전송·fusion은 첫 predict setup에 포함 |
| public predict wall | 첫030 입력0.9094초, 다음007 입력0.0275초. 첫 입력에는 setup·warmup 포함 |
| Results.speed inference | 각각12.63ms·13.31ms. 계측/동기화 영향이 있는 단2프레임, 영상 FPS 환산 없음 |
| PyTorch allocator peak | allocated204,846,592bytes(약195.36MiB), reserved228,589,568bytes(218MiB). 장치 전체 사용량과 다름 |
| run-entry / queue attempt | 6.464초 / 11.141초. 입력 검증·프로세스 준비 등 범위가 다름 |

이전 EXP-0021 로딩은 CPU+CUDA 이동까지 포함했으므로 새 CPU 생성 시간과 직접 비교하지 않는다. 장치 전체 샘플에는 다른 GPU 작업도 섞일 수 있다. 두 장의 기술 성공을 연속 영상 안정성이나 관절 정확성으로 일반화하지 않는다.

## 다음 결정

이번 핵심 기술 복구는 성공했다. 필수 넘기 장면030에 관절 근거가 없으므로 **확대·행동 규칙·기본 적용은 보류**한다. 007의 검수가 긍정적이어도030의 누락이 사라지는 것은 아니다. 다음 결정에는030처럼 작고 겹친 인물에서 유용한 관절 단서를 확보할 수 있는지에 대한 별도 근거가 필요하다. 이번 배치에서 입력/모델/임계값을 바꾸거나 새 GPU 작업을 예약하지 않는다.

[독립 검토](../reviews/EXP-0022-independent-review.md)와 [전달 기록](BATCH-0004-delivery.md)은 기술 실행/관절 품질/로컬 화면/GitHub 게시를 각각 구분한다. 기존 실패·공식 라벨·CV/VLM 결과는 보존하고 원본/오버레이/관절 원시값/가중치/runtime은 로컬에만 둔다.
