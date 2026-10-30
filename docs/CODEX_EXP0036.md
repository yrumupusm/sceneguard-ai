# EXP-0036 — 여러 침입 의심을 출입구별 사건 카드 하나로

최신 사용자 승인: 여러 사람이 동시에 침입하더라도 사람마다 알릴 필요가 없다. 같은 출입구에서 짧게 반복되는 의심은 한 카드로 표시하고 처음 한 번만 알린다. **EXP-0035의 완화한 후보 생성은 그대로 유지한다. 이 작업은 판별/학습 실험이 아니라 알림 정리 기능이다.** 이전 문서의 자동 추가 작업 중단은 이전 배치 종료 기록이며 이번 명시적 승인에 우선하지 않는다.

## 이번에 구현한 것과 남은 것

- `sceneguard/incident_cards.py`: 순서대로 들어오는 의심을 출입구별 카드로 묶는 순수 Python 모듈. 첫 이벤트는 `created, notify=true`, 이후는 `updated, notify=false`. 동일 이벤트 재전송은 `duplicate, notify=false`이며 수를 늘리지 않는다.
- `sceneguard/exp0036_application.py`: 기존 EXP-0035 JSON의 `events` 중 침입 의심과 보존된 `existing_alerts`를 읽는 CPU 전용 어댑터. 복사본인 `losses`, `review_changes`는 중복 집계하지 않는다. 정상/판단불가 행은 `ignored_non_alert_rows`와 원본에 보존한다.
- `sceneguard/incident_card_preview.py`: 생성된 JSON과 기존 비교 MP4로 작은 카드 재생 HTML을 만드는 도구. 신규 동영상 렌더·모델 추론·서버 설치 없이 기존 영상 사용.
- `tests/test_incident_cards.py`: 격리 Python 환경에서 합성 테스트 30개 통과. 알림 시각, 원본 보존, 미리 표시 방지, 다른 출입구 분리, 중복 재전송, 상한, 경로/HTML 검증 포함.
- Chromium의 **합성 DOM 검사 6개** 통과: 첫 카드, 즉시 알림, 무음 갱신, 누적 표시, 과거로 이동 시 미래 정보 미노출, 같은 알림 재표시 억제. 실제 로컬 CCTV 재생/전체 저장소 회귀/기존 웹 연동은 아직 미실행이다.

## 고정 동작

1. 같은 `(녹화 세션, 카메라, 출입구)`의 **직전 알림 이후 3초 이내** 이벤트는 같은 카드로 묶는다. 첫 알림부터 **최대 10초**까지만 묶고 이후 이벤트는 새 카드로 연다. 결과를 보고 값을 계속 탐색하지 않는다. 이 숫자는 알림 UX 시작 설정이며 침입 확률/검출 임계값이 아니다.
2. **첫 의심이 들어오면 즉시 알린다.** 3초 수집 후에 알리는 방식이 아니다. 후속 이벤트마다 같은 카드의 종료 시각/관련 알림 수/ID/근거 링크만 갱신하고 소리/팝업은 반복하지 않는다.
3. 여러 ID와 서로 다른 규칙이 같은 카드에 있어도 ID 병합·동일인 판정·인원 수 산출을 하지 않는다. 원래 이벤트, 시각, source pointer, ID, 기존 경보는 모두 남긴다. 이미 생성된 의심을 출발 영역·방향·VLM 조건으로 다시 차단하지 않는다.
4. 카드 상태는 기본 **침입 의심**이다. 개수가 많아지거나 시간이 지나도 **침입 확인**으로 자동 승격하지 않는다. 기존 검토자 확인 상태가 있다면 별도 필드로 유지하며 새 자동 이벤트가 덮어쓰지 않는다.
5. 다른 출입구/카메라/세션을 시간만으로 합치지 않는다. session ID는 동일 원본·동일 재생에서 고정하고 새로고침할 때 바꾸지 않는다. 여러 출입구 영상에는 실제 gate ID를 부여해야 하며 추측해서 합치지 않는다.
6. 알림은 `decision_time_pts` 또는 기존 `emitted_at_pts`로 순서화한다. 마지막 관측 시각/추정 침입 시각으로 알림을 소급하지 않는다. `timeline`에는 당시 버전의 카드 snapshot만 들어 있고, 최종 카드의 미래 ID/알림수를 앞선 프레임에 보이면 안 된다.
7. 프로세스·브라우저 재시작/폴링까지 첫 알림 한 번을 유지하려면 `notification_key`의 전달 영수증을 기존 서비스에서 저장해야 한다. 모듈 내부의 중복 방지는 인스턴스 범위이며 영구적 전달 보장을 주장하지 않는다. 프리뷰는 sessionStorage와 메모리로 재생 데모 토스트 중복을 줄이고, 탐색/되감기에는 새 토스트를 내지 않는다. 원본 재분석·새 외부 알림 발송은 없다.
8. 후보를 묶어 카드 수가 줄어도 **오탐 제거/정확도 상승이 아니다.** 정상 접근 56~58초의 기존 오탐과 해당 ID를 카드 안에서 볼 수 있어야 한다. 3초 연속 연결은 여러 근접 상황을 한 카드에 담을 수 있으므로 카드는 검토 단위이지 정답 사건 수가 아니다.

## 로컬 Codex — 이번에 실제로 마칠 작업

최신 main을 기존 변경 보존 방식으로 가져오고 이 문서를 우선한다. 새 detector/tracker/VLM 호출·학습·GPU 작업·폴리곤 조정은 하지 않는다. 기존 로컬 원본과 JSON을 공개 업로드하지 않는다.

먼저 합성 테스트를 로컬에서 재실행한다.

```bash
.venv/bin/python -m unittest discover -s tests -p test_incident_cards.py -v
```

기존 EXP-0035 결과 JSON에 각 1회 적용한다. 경로가 다르면 실제 저장된 파일을 확인해 사용하고 데이터를 지어내거나 표에서 역산하지 않는다. 아래 C3/C6 gate는 기존 설정의 boundary_id와 대조한다.

```bash
.venv/bin/python -m sceneguard.exp0036_application \
  --result outputs/exp0035/007-v1.json \
  --output outputs/exp0036/007-cards-v1.json \
  --camera-id C3 --gate-id C3_fence --session-id E01_007-original

.venv/bin/python -m sceneguard.exp0036_application \
  --result outputs/exp0035/030-v1.json \
  --output outputs/exp0036/030-cards-v1.json \
  --camera-id C6 --gate-id C6_fence --session-id E01_030-original
```

C3_fence/C6_fence는 현재 저장소의 기존 boundary_id와 대조했다. 로컬에서도 기존 이벤트의 출입구 이름을 그대로 사용한다. gate ID 이름 확인은 좌표 변경이 아니며, 명시된 boundary_id가 다르면 어댑터는 거부한다.

기존 영상으로 카드 재생을 확인한다. 아래 MP4는 원본 전체가 아니라 해당 분석 구간으로 잘린 비교 영상이며, 영상 0초가 JSON의 source_window[0]에 대응한다.

```bash
.venv/bin/python -m sceneguard.incident_card_preview \
  --bundle outputs/exp0036/007-cards-v1.json \
  --media outputs/exp0035/compare007-v1.mp4 \
  --output outputs/exp0036/007-cards-v1.html

.venv/bin/python -m sceneguard.incident_card_preview \
  --bundle outputs/exp0036/030-cards-v1.json \
  --media outputs/exp0035/compare030-v1.mp4 \
  --output outputs/exp0036/030-cards-v1.html
```

기존 결과 화면에 이 카드 흐름을 최소한으로 연결한다. 해당 서비스가 별도 저장소라면 기존 구조/권한을 확인하고 기존의 등록·미디어 표시 경로를 재사용한다. 새 서버/대형 UI를 만들지 않는다. 필요한 범위의 카드 UI 변경만 허용한다. HTML 생성만으로 서비스 적용까지 됐다고 쓰지 않는다.

## 실제 확인 항목

- 007 72.433/72.600초 알림과 가까운 기존 경보가 한 카드에 붙는지, 최초 알림은 늦추지 않았는지 확인.
- 007 정상 접근 오탐의 raw 알림을 삭제하지 않고 묶어서 표시하는지 확인. 이전/이후 통계에서 오탐을 감추지 않는다.
- 030 양측 관측/소실/기존 경보가 같은 시간대면 함께 표시되는지 확인.
- 새 카드 1회 알림, 기존 카드 갱신 무음, 폴링 중복 알림 없음, 재생·seek·과거 시각의 카드 내용 일치. 여러 사람이 있는 경우 사람 수를 써버리지 않는다.
- 결과표는 `원래 개별 알림 수 / 카드 수 / 최초 알림 횟수 / 무음 갱신 수`로만 작성한다. 원래 이벤트 모두가 정확히 한 카드에 들어갔는지 확인한다.
- 기존 관측·모델·영역·EXP-0035 JSON의 해시를 보존한다. 주석·threshold·인물 연결을 건드리지 않는다.

실제로 적용한 결과와 간단한 전달 문서만 GitHub에 게시한다. raw 영상/JSON/개인 이미지/로컬 DB는 제외한다. 새 검출 실험을 시작하거나 실패를 핑계로 의심 조건을 다시 엄격하게 하지 않는다. 이번 완료 기준은 **사건 카드와 1회 알림이 실제 화면에서 동작하는 것**이며, 모델 정확도를 새로 인증하는 것이 아니다.
