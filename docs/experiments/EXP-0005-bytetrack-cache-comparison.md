# EXP-0005 — 고정 FCOS 캐시의 IoU / ByteTrack 연결 비교

- 날짜/담당: 2026-10-28 (KST) / Codex 구현·로컬 실행·검수 초안.
- 상태: A/B/C 캐시 재생, 회귀·관측 검증, 고정 35프레임/추가 연속 장면 검사 완료. **ByteTrack은 후속 검증 후보, 기본 tracker 교체는 보류**.
- 관련: Issue #1, [ADR-0010 실행 전 선택·설정](../decisions/ADR-0010-bytetrack-cache-comparison.md), [EXP-0004](EXP-0004-fcos-score-threshold-comparison.md), [검수표](EXP-0005-visual-review.md).
- 실행 기반 HEAD: `22e53e3e1cf67c467fc9e2b6cf41af64fc131231` + 이 작업의 코드. 실제 파일 해시 및 기반 캐시 provenance는 로컬 `track{ID}/provenance.json`에 기록, 최종 커밋은 이 문서의 Git 이력.

## 목적과 잠정 판단

같은 검출 반환 결과에서 연결 방식 전체를 바꾸면 문을 넘는 **실제 사람**의 연결이 개선되는지 비교했다. B는 A보다 일부 명확한 접근 장면에서 ID를 유지하고, C는 B에서 관측이 끊기는 030 넘기 장면·006/031 일부 사람 주변을 low 관측으로 연결했다. 하지만 중복 track, 배경 track의 지속, 부분 신체/겹침 때문에 불확실한 대응, 오래 가려진 사람의 누락도 남는다. **ID 수 감소나 긴 span을 성공으로 해석하지 않는다.**

C에서 030/007 각각 후보 2개가 생겼다. 030 후보는 실제 넘기 장면과 시간적으로 겹치지만 신체 일부 bbox의 하단 이동 때문에 정확한 사건/완료 시점 정답은 아니다. 007의 두 후보는 문 밖 접근·서기 중 bbox 범위 변화에 민감한 실패 의심 사례다. 침입 감지 성공으로 계수하지 않았다. 특정 Kalman/Hungarian/low score 하나의 인과 효과라고 일반화하지 않는다.

## 데이터와 고정 검출

EXP-0004의 `outputs/cv_phase2d/cache{030,006,007,031}/person_cache.jsonl`만 사용했다. 030 [84,100) 480, 006 [117,133.67) 500, 007 [48,68) 600, 031 [30,46) 480, 합계 **2,060프레임**. 35개 검수 PTS도 동일하다. 캐시는 FCOS 내부 score>0.2/top-k1000/NMS .6/전체 cap100 이후 person 반환 결과이며, 그 이전 탈락 후보는 없다.

캐시 SHA256은 EXP-0004 표와 동일: 030 `20ccd053814f8777d46765892881e4872687bb62c0222904ad6f5bcb72f76687`, 006 `45beed27fcb513f93a880a8f05693ede4feffe204aa256dab6adf206f370baaf`, 007 `ecb55d37b8d15806366453263d33df8fb096b5293e18d3c5144e7d3789e4753b`, 031 `07e0b1e6add33ffb2769a4e065b51bd1e7db78cbfdc73ab249721bae4422d8e4`.

FCOS COCO_V1·가중치 SHA·원본 1920×1080/내부 749×1333·원본 PTS·카메라 C3/C6/C7 ROI/유한 경계·band .005/dwell .1/max gap .1/cooldown 1초/양방향을 그대로 유지했다. 모델 재추론 **0회**, 새 가중치 다운로드 **0개**, 학습/크롭 추론/해상도·NMS·경계 변경 없음. ByteTrack의 tracked/lost 중복 정리는 tracker의 기존 lifecycle이고 검출 NMS 재실행이 아니다.

AI-Hub 71850 로컬 Training 개발 표본, 독립 테스트 아님. 006/007 동일 카메라 C3 그룹 누수 방지 유지. 공식 라벨을 로드해 추적을 조정하지 않았다. 006 후기 보행은 감시 ROI 밖·비이벤트 후보이고 4006/4011 프레임 불일치가 남는다. 031 약 33초 접촉≠공식 43.6초 시작, 전체 영상 종료까지 모든 사람 완료 미확인 상태 유지. G1E/정밀 객체·추적 정답 미완료.

## 구현 선정·설정 동결

[공식 ByteTrack](https://github.com/FoundationVision/ByteTrack/tree/d1bf0191adff59bc8fcfeaa0b33d3d1642552a99/yolox/tracker) 커밋 `d1bf0191adff59bc8fcfeaa0b33d3d1642552a99`의 네 tracker 모듈을 vendor했다. [MIT LICENSE](https://github.com/FoundationVision/ByteTrack/blob/d1bf0191adff59bc8fcfeaa0b33d3d1642552a99/LICENSE), 저작권 고지, 원본 SHA256 및 변경 내역은 `sceneguard/vendor/bytetrack/`에 포함했다. 검출기까지 들어오는 패키지/다른 tracker는 도입하지 않았다.

공식 소스 대비 변경은 상대 import, 미사용 torch/cv2 import 제거, NumPy 2의 np.float 호환, 명시적인 점수 구간, 대응된 원본 검출 index/raw bbox 계측이다. 알고리즘을 새로 구현한 대체품이나 완전 무수정 upstream 실행이라고 주장하지 않는다. 세부 근거·재검토 조건은 ADR-0010.

실행 전 `data/cv_phase2e/preregistered.json`에 설정 문서 hash `837827eedb41e3b17ad0942f0320fc62b893e4c312c9df2f308cbc07ad889fd8`와 시각(2026-10-28 01:15:30 KST)을 기록했다. 결과를 본 뒤 설정을 조정하지 않았다.

| 조건 | 입력/시작 기준 | 연결과 유지 |
| --- | --- | --- |
| A | 캐시 person score ≥.5 | 기존 보수적 인접 IoU ≥.3, 모호 매칭/미검출 시 ID reset |
| B | high ≥.5만 입력, 신규 ≥.6 | 공식 ByteTrack, low 입력 없음 |
| C | high ≥.5 및 low ≥.25·<.5 | B와 동일하고 low 2차 연결만 추가. low 단독 신규 생성 불가 |

공식 upstream의 high `>.5` 대신 이 실험에서는 `>=.5`로 명시하고 테스트했다. low도 `>.1` 대신 `>=.25`·`<.5`이다. 신규 생성은 upstream `score < track_thresh+.1` 탈락, 즉 **≥.6**를 유지한다. 최초 프레임 신규는 confirmed, 이후 신규는 다음 high 매칭으로 확인한다. 따라서 A와 B 차이는 할당 방식뿐 아니라 생성/확인/lost 관리 등 **tracker 전체 정책 차이**도 포함한다. B/C는 같은 코드를 쓰고 입력에 low가 있는지 한 가지 차이만 있다.

1차 연결은 tracked+lost에 score-fused 비용 `1−IoU×score` 한계 .8(mot20=False), 2차는 1차 미매칭 중 Tracked만 plain `1−IoU` 한계 .5. lost track은 low로 재활성화하지 않으며 unconfirmed도 high만으로 확인(비용 .7)한다. lap 비용 한계의 동등값 포함은 합성 테스트로 확인했다. tracked/lost IoU>.85 중복 정리의 기간 비교도 공식 그대로다. active track끼리 모든 중복을 제거하는 기능은 아니다. IoU는 공식 cython_bbox의 pixel-inclusive 관례(+1)를 유지한다. 예를 들어 [0,0,1,1]과 [1,0,2,1]은 1/3으로 관측되며, A의 연속 좌표 IoU와 동일 계산이라고 가정하지 않는다.

frame_rate=30/track_buffer=30 → max_time_lost=30. 빈 검출도 건너뛰지 않고 매 원본 프레임 한 번 update, Kalman dt=1 frame. 약 1초이며 006은 30프레임=1.001초. 제거 조건 `frame_id−end_frame >30`과 연결 후 만료 검사 순서는 upstream 유지한다. 표시 FPS로 PTS를 재생성하지 않는다. 실제 PTS 간격은 006 약 .0333667, 나머지 .0333333초이며 캐시 구간이 일정 간격인지 assert한다. 불규칙 FPS/프레임 생략을 지원한다고 일반화하지 않는다.

## 관측·예측·경계 계약

- `byte_adapter.py`가 캐시 원본 좌표를 입력한다. img_info=img_size=(1080,1920), 공식 scale=1. 좌표 확대·축소가 이중 적용되지 않음을 합성 테스트와 2,060프레임 검출 index 대조로 검증했다.
- `frames.jsonl`의 `detections`는 confirmed + 현재 프레임 검출과 실제 대응한 관측뿐이다. `bbox`는 **원본 캐시 검출**이고 `filter_bbox`는 별도 Kalman 추정 위치다. `cache_index`, high/low_second 연결 종류, score, native PTS/time_base를 남긴다.
- `states`는 confirmed 관측·unconfirmed 관측·lost_prediction을 구분한다. 예측만인 경우 observed=false, bbox=null, prediction_bbox와 last_observed_pts/unobserved_seconds를 별도 저장한다. `unmatched`는 입력 중 최종 유지 track에 배정되지 않은 검출이며, 미매칭 외에 생성 거절/중복 정리도 포함할 수 있다.
- `boundary.py`에서 공통 규칙을 BoundaryRules로 분리했고 기존 BoundaryTracker의 IoU step은 보존했다. 외부용 ObservedBoundary는 ByteTrack ID를 그대로 사용하며 재-IoU 할당하지 않는다. confirmed 실제 검출 박스만 경계 규칙에 전달한다.
- **한 프레임이라도 confirmed 관측이 없으면 그 ID의 경계 상태를 reset**한다. PTS 간격 >.1초도 reset한다. 이는 기존 보수적 경계 동작 유지이며, ByteTrack이 ID 자체를 더 오래 유지해도 경계 관측을 보간하지 않는다. 예측만으로 dwell/통과 이벤트를 만들 수 없다.
- 실제 발생한 네 후보 모두 anchor부터 emission까지 같은 ID에 실제 검출이 매 원본 프레임 존재하고 인접 PTS 간격 ≤.1임을 독립 검사했다. `candidate_interval`이 .1초보다 길어도 band/dwell 동안 연속 관측이 존재할 수 있다. max_gap은 이벤트 구간 폭 제한이 아니라 관측 간격 제한이다.

## 환경·실행·재현

WSL2 Ubuntu 22.04 / Linux 6.6.87.2, Python 3.10.12, Ryzen 7 9800X3D 8코어/16논리 CPU. 추적은 CPU, RTX 3080에서 검출 모델을 실행하지 않았다. 기존 NumPy 2.2.6/PyAV 16.0.1/Pillow 12.3.0 환경에 SciPy 1.15.3, lap 0.5.12, cython-bbox 0.1.5를 추가했다. cython-bbox 빌드/선언 의존성으로 Cython 3.3.0도 설치되어 `requirements-tracking.txt`에 고정했다. 기존 torch/torchvision·모델 가중치는 변경하지 않았다.

```bash
uv pip install --python .venv/bin/python -r requirements-tracking.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m sceneguard.replay_tracking 030 006 007 031
.venv/bin/python scripts/audit_tracking_replay.py
.venv/bin/python scripts/render_tracking_review.py 030 006 007 031
```

기존 출력 덮어쓰기를 거부한다. 첫 재현 기본 경로는 `outputs/cv_phase2e/track{ID}/{A,B,C}`이고 `--output-root`로 재생 경로를 바꿀 수 있다. 별도 루트를 쓰면 audit/render의 ROOT도 맞춰야 한다. 원본 영상은 render에만 필요하며 재생은 캐시만 읽는다. base 원본/가중치/캐시 provenance는 EXP-0004와 각 track/provenance에 연결했다.

실제 실행 파일 SHA256:

- `sceneguard/boundary.py`: `81363952ed953fb29bb88beb38d240d73d485b00f5b312232174faa765f42279`
- `sceneguard/byte_adapter.py`: `cd026fa51b66337d3116900d8221634cf3808c177fea229c7ab914a894489e09`
- `sceneguard/replay_tracking.py`: `aee03bf979dadb91cb9c88e247f724abbbd816c06bcc63afe2e882bad4205ac0`

## 실제 진단 결과

| 영상 | 조건 | 관측 존재 프레임 | 관측 박스 | 관측 ID | low 관측 | 예측만인 track-frame | gap 후 재관측 | 경계 후보 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 030 | A | 313 | 597 | 101 | 0 | 0 | 0 | 0 |
| 030 | B | 292 | 559 | 10 | 0 | 473 | 41 | 0 |
| 030 | C | 320 | 700 | 8 | 133 | 333 | 12 | 2 |
| 006 | A | 235 | 387 | 21 | 0 | 0 | 0 | 0 |
| 006 | B | 223 | 367 | 7 | 0 | 301 | 12 | 0 |
| 006 | C | 369 | 562 | 6 | 191 | 178 | 3 | 0 |
| 007 | A | 570 | 1120 | 392 | 0 | 0 | 0 | 0 |
| 007 | B | 568 | 1044 | 12 | 0 | 439 | 35 | 0 |
| 007 | C | 569 | 1252 | 9 | 199 | 246 | 8 | 2 |
| 031 | A | 261 | 318 | 63 | 0 | 0 | 0 | 0 |
| 031 | B | 76 | 86 | 6 | 0 | 240 | 13 | 0 |
| 031 | C | 265 | 284 | 5 | 181 | 94 | 2 | 0 |


‘관측 박스’는 confirmed 검출 대응 수(프레임 누적), ‘관측 ID’는 한 번 이상 confirmed 관측된 임시 ID의 종류다. unconfirmed ID는 이 수에서 제외한다. 둘 다 실제 사람/정답 수가 아니다. 예측만인 track-frame은 같은 프레임에 여러 track이 있으면 각각 센다. gap 후 재관측은 같은 ID가 최소 한 빈 관측 프레임을 지나 다시 관측된 횟수이지 정체 유지 정답이 아니다.

B의 예측만인 유지 길이 최대는 030/007/031 1.000초, 006 1.001초이며 C도 동일하다. 재관측 전 최장 실제 PTS gap은 B에서 030 .867/006 .968/007 .600/031 .600초, C에서 .833/.868/.367/.600초. **이 gap을 경계 이벤트로 연결하지 않았다.** raw 검출이 없는 상태, high만 사용해서 제외된 low, 신규/확인 기준 때문에 버린 검출을 동일한 ‘검출 모델 미탐’으로 합치지 않는다.

### CPU 캐시 추적+경계 처리 시간

| 영상 | A mean / p50 / p95 ms | B mean / p50 / p95 ms | C mean / p50 / p95 ms |
| --- | --- | --- | --- |
| 030 | 0.0324 / 0.0115 / 0.0448 | 0.2817 / 0.2613 / 0.6856 | 0.3109 / 0.3132 / 0.6237 |
| 006 | 0.0084 / 0.0038 / 0.0194 | 0.1606 / 0.1081 / 0.4049 | 0.2550 / 0.2563 / 0.4808 |
| 007 | 0.0185 / 0.0152 / 0.0365 | 0.3198 / 0.3033 / 0.5777 | 0.4336 / 0.3958 / 0.8281 |
| 031 | 0.0121 / 0.0085 / 0.0250 | 0.1132 / 0.0600 / 0.3660 | 0.3054 / 0.2648 / 0.6024 |


프레임마다 normalize/adapter/ByteTrack 또는 IoU/경계 규칙과 관측 계측을 포함해 perf_counter로 측정했다. 파일 읽기·JSON 저장·decode·render·모델 추론은 제외했고 별도 warmup/반복 벤치마크는 하지 않았다. A는 단순 규칙이고 B/C에는 원본 박스 일치 검사 등 진단 비용도 포함된다. **전체 영상 추론 FPS나 모델 속도 비교가 아니다.** CPU/GPU 메모리 개선·실시간 시스템 성능을 주장하지 않는다.

## 실제 사람 연결: B 대 A, C 대 B

| 영상 | B 대 A | C 대 B | 남은 실패/유보 |
| --- | --- | --- | --- |
| 030 | 흰옷 #1이 관측 gap을 포함해 84~92초에 재사용되고, 앞 인물 #3은 84~88.767초 유지. A의 빈번한 새 ID보다 국소 연결 개선 | 앞 인물 부근 #3이 92.4초까지, 중앙 #4가 87.4~91.733초 관측됨. 90초 B는 예측 3개뿐, C는 low 실제 관측 2개 | 왼쪽 인물은 90초 여전히 미관측. #3/#4 부분/겹친 신체, 뒤 신규 #5와 중복 가능. 94초 모두 누락, 이후에도 신규 ID 발생 |
| 007 | 50→52초의 분홍 신발/배낭 두 사람은 각각 B #2/#3 유지(A는 2/16→22/27). 국소 이점 | C #2가 가려진 앞 사람 상체 관측을 low로 이어 줌. B에서 초기 배낭 #1은 짧게 끊기지만 C는 더 오래 유지 | C 54초 배낭 인물에 #1/#5 중복. 56초 배경 #6, 66초 배경 #12 low 유지. 64초 B/C 모두 두 사람에 3track. 56초대 사람/부분 박스 대응 유보 |
| 031 | 32/42/44초 상점 물체 의심 track 생성 억제. 동시에 실제 관측도 크게 감소(.6 시작/확인 정책 포함) | 울타리 옆 #1의 관측을 30~38.6초에 유지, 36/38초 실제 인물 부근 low 복원 | 여러 인물 겹침/작은 크기로 동일 개인 여부 유보. 40/42/44초 실제 인물 누락 지속. 상점 track 감소를 전체 성능 개선으로 보지 않음 |
| 006 | 두 원거리 보행자 위치를 일부 같은 ID로 유지하지만 관측 공백은 예측일 뿐 | 121/125/133초 근처 검은옷 보행자 low 관측 복원, 이후 구간 연결 연장 | 123/127/129초 근처 관측 없음. ID가 여러 번 바뀜. 현재 감시 ROI 밖이므로 이벤트 후보 0은 정상 판정 성공 아님 |

숫자 span은 관측과 gap이 섞인 시간 범위다. C의 030 #3 243관측, #4 121관측 등 긴 기록을 전체 기간 연속/정체 보존 성공으로 표현하지 않는다. 031의 #1은 사람 영역에 머무르지만 가려진 옆 사람으로 옮겨 붙었는지 확정할 객체 정답이 없다. 007의 중복 track과 배경 track이 오래 남는 실패는 별도로 기록했다. 관찰한 구간 밖의 잘못된 연결이 없다고 주장하지 않는다.

## 경계 후보의 실제 장면 검토

| 조건/영상/ID | anchor → 최초 반대쪽 / emission (초) | 방향 | 의미 검수 초안 |
| --- | --- | --- | --- |
| C/030/#3 | 90.100→90.200 / 90.300 | positive→negative | 실제 넘기 중. 전신→상체 부분 bbox 변화가 동반되어 정확한 선 통과·완료로 확정 불가 |
| C/030/#4 | 89.866667→90.200 / 90.300 | positive→negative | 중앙 인물 부근 연속 관측. 다른 인물과 겹침/부분 신체 대응 유보, 독립 성공 건수 아님 |
| C/007/#2 | 56.066667→56.533333 / 56.633333 | positive→negative | 문 밖 접근·서기, 해당 시점 넘기 확인 안 됨. 부분 신체 박스 하단 이동에 의한 후보 의심 |
| C/007/#2 | 56.633333→56.666667 / 56.766667 | negative→positive | bbox bottom y=.2605→.3667, 상체→큰 몸 박스 변화. 짧은 양방향 후보를 두 침입으로 세면 안 됨 |

030 89.600~90.500의 28연속 프레임, 007 55.900~57.000의 34연속 프레임을 원본/B/C로 나란히 확인했다. 030 #3 bottom y는 90.100 .5555→90.300 .4719로 크게 올라가며 실제 동작과 bbox 축소가 함께 작용한다. 007 #2의 부호 거리도 +.00541→−.01239→+.02701로 변하지만 발 위치/실제 통과 정답이 아니다. 관측만으로 생성됐다는 구현 검증과 사건 의미 정당성은 별개의 문제다.

## 로컬 검수 산출물

- `outputs/cv_phase2e/review{030,006,007,031}/continuous_ABC.mp4`: 원본/A/B/C 4분할, 1280×780, 각각 480/500/600/480 프레임. 전체 짧은 구간을 연속 비교 가능. 소리 없음.
- 같은 디렉토리 `compare_{PTS:.6f}.jpg` 35장, 기존 검수 manifest 그대로. `native_pts.json`은 원본 PTS와 출력 영상의 상대 시각을 연결한다.
- `review030`, `review007`의 `event_sequence_*.jpg`: 후보 주위 모든 원본 프레임을 담은 표시용 확대 카드. 검출/추적 크롭 입력으로 사용하지 않음.
- `track{ID}/{A,B,C}/frames.jsonl`, events.jsonl, reobservations.jsonl, summary.json, provenance.json, `audit.json`은 로컬 전용. 예측/관측을 섞어 평가하지 않도록 별도 필드 제공.
- 실제 검수 범위는 고정 35장 + 후보 연속 62프레임. 비교 영상의 전 구간 모든 사람을 수동 정답화하거나 인간이 전체 영상을 재생 검수 완료했다고 주장하지 않는다.

## 검증·실패 기록

- **24개 테스트 통과**(기존 16 + 새 8): low 단독 생성 금지, ≥.25/.5/.6 경계, high-only B/C 동일 입력 동일 출력, lost의 low 재활성화 금지, 빈 프레임/lost 만료, 원본 좌표와 Kalman 좌표 분리, lap 비용 동등값, 외부 ID/예측 이벤트 금지/미관측·PTS gap reset/기존 규칙 동등성.
- A의 2,060프레임 전체 PTS/native PTS/time_base·bbox/score/순서/track_id/observed가 EXP-0004 0.5와 정확 일치하고 EXP-0002와도 동일. 이벤트 0도 재현.
- 세 조건 모든 관측의 원본 캐시 index/좌표/점수 대조, 이벤트 anchor~emission 연속 실제 관측 검사 통과. 낮은 점수 후보를 새로 만들거나 캐시 밖 후보 복구 없음.
- 비교 영상 재디코딩에서 2,060프레임/PTS 순서 확인. 원본 시작을 뺀 상대 PTS와 최대 차이 약 2.14e-14초. 35검수 manifest 동일.
- 이전 출력/캐시/공식 JSON/config **412파일**의 사전 SHA256 유지. 네 원본 영상·기존 FCOS 가중치의 해시도 캐시 provenance와 일치. 기존 공식 라벨/EXP-0001~0004 보고서 수정 없음.
- 초기 환경에는 pip 모듈이 없어 기존 uv로 최소 의존성을 설치했다. 첫 재생 CLI에서 통계 dict 괄호 누락 SyntaxError가 발생해 실행 전 수정하고 py_compile·실제 재생으로 검증했다. 합성 테스트만으로 CLI 문법 검증을 대신할 수 없음을 기록한다.
- upstream np.float는 NumPy 2에서 제거되어 float로 호환 수정했다. 알고리즘 변경과 계측/호환 변경을 vendor UPSTREAM.md에 구분했다.

정밀 사람별 추적 정답이 없어 **IDF1/HOTA/침입 정확도/F1/시간당 오탐률 미산출**. 공식 영상 라벨을 tracker ID 정답으로 바꾸지 않았고 현재 표본은 독립 테스트가 아니다.

## 다음 판단

ByteTrack C의 국소 연결 복원은 후속 검증 가치가 있다. 그러나 기본 tracker 교체/침입 감지 성공 선언은 보류한다. 먼저 030 #3/#4, 007 #2·중복 track, 031 #1의 사람별 정체·부분 신체를 사용자가 확인하고 별도 연속 정답으로 확정한다. 007 배경 #6/#12처럼 low가 배경도 유지한다는 비용을 함께 평가해야 한다.

후속 검수는 기존 캐시/영상으로 가능하다. 최종 설정 선정에는 카메라 그룹을 분리한 별도 표본과 평가 규칙 동결이 필요하다. 다음 실험을 자동으로 확대하지 않으며 새 검출기/재학습/해상도·NMS·경계 튜닝/VLM/UI는 이번 범위에 추가하지 않았다. 코드·라이선스·설정·테스트·요약 문서만 GitHub에 게시하고 영상·이미지·캐시·원시 결과는 로컬에 둔다.
