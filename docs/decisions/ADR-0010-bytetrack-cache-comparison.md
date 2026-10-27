# ADR-0010 — FCOS 캐시에서 ByteTrack 연결 비교

2026-10-28 / 실행 전 설정 고정. 사용자 승인 범위의 A/B/C 개발 실험용 도입이며 메인 tracker 채택은 미정.

## 선택과 출처

EXP-0004의 중복/미검출에서 보수적 IoU 연결 단절이 빈번했다. 낮은 점수를 무조건 신규 객체로 늘리지 않고 기존 track 연결에만 쓰는 ByteTrack을 공식 구현 하나로 비교한다. 다른 검출기·ReID·학습·가중치 다운로드는 없다. detector까지 포함하는 패키지를 설치하는 대신 공식 tracker subset을 vendor한다.

- [공식 ByteTrack](https://github.com/FoundationVision/ByteTrack), 고정 커밋 `d1bf0191adff59bc8fcfeaa0b33d3d1642552a99`.
- [공식 tracker 코드](https://github.com/FoundationVision/ByteTrack/blob/d1bf0191adff59bc8fcfeaa0b33d3d1642552a99/yolox/tracker/byte_tracker.py), [MIT LICENSE](https://github.com/FoundationVision/ByteTrack/blob/d1bf0191adff59bc8fcfeaa0b33d3d1642552a99/LICENSE). 저작권 고지·원본 파일 해시를 vendor 디렉토리에 보존.
- NumPy 기존 2.2.6 + SciPy 1.15.3, lap 0.5.12, cython-bbox 0.1.5. PyTorch/YOLOX/OpenCV/ReID는 tracker 실행에 필요하지 않게 미사용 import만 제거한다. Kalman/할당/중복 제거 알고리즘은 유지.
- NumPy 2 호환 np.float→float, 상대 import, 검출 index/raw bbox 계측, high `>`→`>=`, low `>0.1`→`>=0.25` 변경을 명시한다. 완전 무수정 공식 실행이라고 주장하지 않는다.

## 결과 보기 전 고정한 조건

- A: 기존 BoundaryTracker + person ≥0.5. EXP-0004/0002 전체 결과 정확 재현 확인.
- B: ByteTrack 입력 high ≥0.5만. C: 같은 설정에 low ≥0.25 및 <0.5를 2차 연결용으로 추가. low 단독 신규 track 생성 불가. .5 경계는 high에만 포함한다.
- 신규 생성은 공식 `score < det_thresh` 탈락 규칙 유지, det_thresh=.5+.1=.6 즉 ≥.6. 최초 프레임은 바로 confirmed, 이후 신규 track은 다음 high 매칭 확인 필요. .5~.6은 기존 track에 연결만 가능.
- 1차: tracked+lost, `1−IoU×score` 비용(lap cost_limit=.8, mot20=False). 2차: 미매칭 중 Tracked 상태만, `1−IoU` 비용 한계 .5. unconfirmed는 high만, score-fused 비용 한계 .7. low는 lost 복구/unconfirmed 확인에 사용되지 않는다.
- tracked/lost 중복 제거는 공식 IoU >.85·track 길이 규칙 유지. 이 단계는 검출 NMS 변경이 아니다. 같은 객체에 복수 active track이 남을 수 있다.
- frame_rate=30, track_buffer=30 → max_time_lost=30. 매 원본 프레임(빈 검출 포함) update 1회, Kalman dt=1 frame. 약 1초이며 006은 PTS 간격 약 .0333667초. 제거는 frame_id−end_frame >30이며 업데이트 순서는 공식 구현 유지. 실제 재연결/미관측 길이를 원본 PTS로 별도 기록한다.
- 원본 pixel 좌표 입력, img_info와 img_size 모두 (원본 높이,너비)로 scale=1. 출력 경계용 좌표만 원본 크기로 정규화. 추가 크롭/확대/축소 없음.
- 경계: 기존 ROI/유한선/band/dwell/max_gap/cooldown 그대로. 외부 ID를 다시 IoU로 재할당하지 않는다. 검출 연결된 confirmed 관측의 raw bbox만 경계 입력, 예측/미확인 상태는 이벤트 근거가 될 수 없다. 기존 보수성대로 한 프레임이라도 관측이 없으면 경계 상태 reset, PTS 간격 >.1초도 reset. ByteTrack ID 자체는 유지 가능하다.

## 검증과 판단 기준

합성 테스트로 threshold 동등/빈 프레임/low 단독 생성 금지/low 2차 연결/좌표 보존/장기 gap·예측 이벤트 금지/외부 ID 유지/A 회귀를 검사한다. 네 구간 2,060 캐시 프레임·고정 35검수 PTS 및 짧은 연속 영상을 비교한다. A↔B, B↔C를 구분하고 ID 감소·배경의 긴 track·경계 후보 자체를 성공으로 보지 않는다. 정체 이동·중복·누락·미관측을 의미 검수하고 정밀 정답 전 IDF1/HOTA/침입 정확도는 보고하지 않는다. 채택은 실제 인물 연결의 반복 개선과 잘못된 연결 위험 검수 후 재판단한다.
