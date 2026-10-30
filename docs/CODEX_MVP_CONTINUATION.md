# SceneGuard 실용 MVP 후속 작업 — 현행 영역 고정, 끊김·혼합 관측 대응

2026-10-30 사용자 최신 지시. **사용자가 로컬에서 수정한 E01_030의 outside/inside polygon은 현재 설정으로 확정하여 그대로 사용한다.** 영역 수정 전/후 A/B 비교, polygon 재설계·재튜닝·별도 영역 수정 테스트를 **수행하지 않는다**. 로컬 runtime/EXP-0029/regions030.json 및 기존 사용자 수정 파일을 덮어쓰거나 과거 polygon으로 되돌리지 않는다. 실제 수정 좌표가 GitHub에 없는 것은 정상이며 임의로 만들어내지 않는다. E01_007의 현행 설정도 별도 요청 없이는 유지한다.

## 목표
기존 목표는 고정 CCTV의 물리적 경계 넘기/통과 **사건 후보 + 근거 영상**이다. 동시에 넘는 사람이 가려져 raw ID가 바뀌더라도 가능한 경우 전후 같은 사람의 추적 구간을 연결하고, 연결이 확실하지 않으면 자동 확정 대신 **검토할 연결 후보**를 제공한다. 이번 후속은 모델 정확도 논문 실험이 아닌, 개인 미니 프로젝트를 실제로 사용할 수 있는 소규모 MVP로 묶는 작업이다. 법적 무단침입이나 실제 월장 완료를 근거 없이 확정하지 않는다.

## 기반과 확인된 문제
- 기존 사전학습 FCOS + ByteTrack gap + EXP-0029 tracklet/ReID 결과를 재사용한다. 자체 파인튜닝 best/last, Roboflow 재학습, 새 detector·tracker·ReID 모델 도입은 없다.
- 입력 검수 이미지 Q01~Q08 중 030 Q01/Q03은 전후 유사한 옷차림이지만 자세·부분 박스 변화로 유사도가 낮았다. Q02의 raw11 최초 대표는 다른 인물이 섞였거나 부분/음영 박스일 가능성이 있다(시각 확정은 아님). 007 Q08은 두 인물이 한 박스/크롭에 겹쳐 있다. 이런 대표를 단일 인물의 확실한 외형 근거로 사용하지 않는다.
- 기존 EXP-0029 자동 연결은 030 0개, 007 1개(같은 raw9의 1.2초 분할 재결합)였고 전후 다른 ID 복원은 미달이었다. 이전 030 inside=0, 007 inside=14 수치는 **수정 전의 과거 설정에만 해당**하므로 현행 영역의 성능으로 반복 인용하지 않는다.

## 로컬 Codex가 지금 진행할 실제 구현
1. **기존 로컬 자료·사용자 polygon 보존:** 최신 main을 로컬 변경과 충돌 없이 동기화한다. 현행 영역을 사용한다는 사실만 source SHA/config SHA로 남긴다. **기존/수정 polygon 비교 수치나 변경 효과 검사는 만들지 않는다.**
2. **대표 외형 품질과 raw ID 변질 대응:** EXP-0029의 raw frame, tracklet, 대표 JPEG, 512차원 저장 특징을 재사용한다. 동일 시간대 박스 중복/겹침, 한 박스에 복수 인물이 담긴 가능성, 지나치게 부분적인 crop, 동일 raw ID의 갑작스런 외형 변화(특히 030 Q02와 007 Q08)를 근거와 함께 표시한다. 대표 특징 중 불일치하는 하나가 나머지 두 장과 다른 경우는 다중 대표·시간적 일치성을 우선해 리뷰 가능 상태로 표시하며, 확인되지 않은 두 사람을 강제 결합하지 않는다. 필요하다면 기존 동일 pretrained encoder를 몇 개 원본 crop에 CPU로 사용하되 새 학습·새 모델은 금지한다.
3. **자동 연결과 검토 연결 분리:** EXP-0029 자동 accepted와 raw ID는 보존한다. 자동 기준에 못 미치지만 시간·이동·외형 근거가 있는 쌍을 'possible_match / needs_review'로 따로 노출한다. 이를 자동 동일인으로 바꾸거나 0.65 임계값을 결과에 맞춰 낮추지 않는다. 최소한 030 Q01/Q02/Q03 및 007 Q04~Q08의 연결/거절/혼합 근거를 표에 남긴다.
4. **월장 동작 후보를 놓치지 않는 이벤트 흐름:** EXP-0029의 안정된 양측 영역 판정은 '통과 후보'에 활용하되, 양측 관측·연결 실패라는 이유만으로 기존 ByteTrack gap 경계 움직임 후보를 삭제하지 않는다. 030 약90초의 기존 후보와 007 약70.13초의 기존 후보를 '경계 움직임/월장 동작 검토 후보(완료 미확정)'로 별도 표시하고 근거 영상을 제공한다. 007 약56.7초 접근은 기존 사용자 확인상 실제 넘기 아닌 사례로 함께 표기한다. 기존 후보가 진짜 월장이라는 주장은 하지 않는다. 예측 박스로 보이지 않는 사람을 만들어 표시하지 않는다.
5. **실제 MVP 출력:** 각 후보에 원본/기존 ID/연결(혹은 연결 검토) ID, 시간 구간, 연결 근거/불확실성, 상태('동작 후보', '양측 관측 통과 후보', '판단 불가')와 짧은 원본 근거 구간을 로컬에서 확인할 수 있게 구현한다. 기존 결과 뷰어가 있다면 재사용하고, 별도 대규모 UI 개발은 하지 않는다.
6. **한 번의 실제 실행:** E01_030 84~100초와 E01_007 48~105초, 사용자가 수정한 현재 영역을 적용한 하나의 실행으로 비교 영상을 생성한다. **영역 수정 전후 비교는 절대 하지 않는다.** ID 연결/혼합 검출과 사건 후보의 의미를 직접 확인하고 제한된 사례표를 작성한다. 기능 테스트는 수행하되 영역 A/B나 무한 임계값 sweep은 하지 않는다.

## 산출물과 종료
코드·테스트·1회 실행 기록·비식별 집계·원본 근거를 가진 로컬 비교 영상 및 후보 목록을 만든다. 테스트 통과, 후보 수 증가, ReID 점수를 실제 동일 인물/물리 통과 성공으로 포장하지 않는다. 가능하면 '전후 자동 연결 / 전후 검토 제안 / 연결 불가'를 따로 집계한다. 기존 EXP-0029의 보고서·검토 결속·자료를 덮어쓰지 않고 새로운 출력 위치를 사용한다.

**문서 추가만으로 완료 처리하지 말고 실제 로컬 입력으로 실행·시각 확인하고 결과를 남겨라.** 원본 CCTV, 프레임, crop, 특징, 좌표, 로컬 polygon, weights는 Git 제외로 보존한다. 새로운 성능 수치·비식별 결론만 GitHub에 게시하고 종료한다. 실패하면 확인된 원인과 남은 사용성 한계를 보고하며 자동으로 다른 모델을 더 붙이지 않는다.


## 이미 추가된 CPU 검토 피드 (중복 구현하지 말 것)
- 코드: sceneguard/mvp_review_candidates.py
- 단위 테스트: tests/test_mvp_review_candidates.py (합성 테스트 10개, 실제 CCTV 성능 검증 아님).
- EXP-0029의 기존 associations.json, tracklets.json, features.local.json과 ByteTrack gap events.jsonl을 읽어 **자동 수락 / 검토할 유사 후보 / 기존 경계 움직임 후보**를 별개로 기록한다. 저장된 대표 특징의 head/tail 내부 일관성 수치도 함께 만든다. 후보가 떠도 동일인이나 실제 완료를 자동 확정하지 않는다.
- 현재 사용자 수정 polygon을 사용한 **정상 MVP 실행**에서 region events가 새로 나온 경우에만 --region-events로 추가할 수 있다. 예전 EXP-0029 폴리곤에서 계산된 events.json을 최신 결과인 양 입력하지 않는다. 현행 polygon으로 실행하더라도 과거 polygon과의 A/B 비교는 하지 않는다.
- 이 모듈은 JSON 검토 피드만 만든다. 실제 근거 동영상 clip/뷰어 연결, 혼합·부분 crop 검수, 같은 사람의 raw ID가 이동하는 문제 해결은 **로컬 Codex의 남은 실작업**이다.

실행 예시 (기존 로컬 cache와 저장 특징이 있는 저장소 루트):

~~~bash
.venv/bin/python -m unittest discover -s tests -p test_mvp_review_candidates.py -v

.venv/bin/python -m sceneguard.mvp_review_candidates \
  --video-id E01_030 --start 84 --end 100 \
  --gap-events outputs/exp0028/practical-v1/track030/gap/events.jsonl \
  --associations outputs/exp0029/track030/v1/associations.json \
  --tracklets outputs/exp0029/track030/v1/tracklets.json \
  --features outputs/exp0029/track030/v1/features.local.json \
  --output outputs/mvp_review/030.json

.venv/bin/python -m sceneguard.mvp_review_candidates \
  --video-id E01_007 --start 48 --end 105 \
  --gap-events outputs/exp0029/replay007/gap/events.jsonl \
  --associations outputs/exp0029/track007/v1/associations.json \
  --tracklets outputs/exp0029/track007/v1/tracklets.json \
  --features outputs/exp0029/track007/v1/features.local.json \
  --output outputs/mvp_review/007.json
~~~

명령은 **과거 line 후보 및 외형 증거를 정리**할 뿐, 최신 수정 영역의 성능을 주장하지 않는다. 출력은 기존 파일을 덮지 않는 새로운 경로다. 실제 데이터의 파일 이름과 형식은 확인한 뒤 사용하고, 오류가 나면 해당 원인만 수정한다.
