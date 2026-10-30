# EXP-0036 독립 검토

2026-10-30. **알림 표시 기능 범위 검토 수락: 실제 저장 JSON·기존 웹 재생 증거·영수증·최종 보고서/metrics 결속 확인.** 침입 판별 정확도·동일인 연결·운영 exactly-once 전달을 인증하지 않는다. 아래 최종 바이트에 대한 미해결 차단 사항은 없다.

기존 EXP-0035 결과와 새 EXP-0036 bundle을 읽기 전용으로 대조했다. 검토자는 모델·추론·학습·GPU·영역·검출 규칙·인물 연결·영상 재생을 실행하거나 변경하지 않았다. 실제 CPU 적용은 담당자의 실행 receipt로 확인하며 같은 적용을 반복하지 않았다. 로컬 감사 스크립트와 결과는 `runtime/EXP-0036/independent-audit.py`, `independent-data-audit.json`이다.

| 영상 | 원래 개별 알림 | 카드 | 최초 알림 의도 | 무음 갱신 |
|---|---:|---:|---:|---:|
| 007 | 10 | 2 | 2 | 8 |
| 030 | 8 | 3 | 3 | 5 |
| 합계 | 18 | 5 | 5 | 13 |

표의 최초 알림은 저장 timeline의 `notify=true` 의도 수다. 아래 실제 재생의 visible DOM 토스트 5회와 수는 일치하지만, 영구 영수증 자체가 표시·사용자 수신을 증명하는 것은 아니다. 카드 감소는 오탐 제거·정확도 향상·사람 수 감소·정답 사건 수가 아니다.

## 데이터·시간·정체 계약

- EXP-0035 `events`의 침입 의심과 `existing_alerts`만 포함한다. 18개 원본 행은 payload와 source pointer를 그대로 보존하며 최종 카드에 각각 정확히 한 번 포함된다. `losses`와 `review_changes` 복사본을 재집계하지 않는다. 007 정상/비알림 6행은 `ignored_non_alert_rows`에 원문 그대로 남으며 030은 0행이다.
- 007 첫 카드는 56.000–65.333초 7행이다. 정상 접근의 기존 오탐 56.000/57.767/57.800초 3행도 그대로 포함된다. 이들을 묶는 것은 오탐 제거가 아니다. 연쇄 3초 연결로 다른 근접 상황이 같은 검토 카드에 들어갈 수 있다.
- 007 두 번째 카드는 기존 경보 70.133초에서 즉시 시작하고 72.433/72.600초 새 의심을 무음으로 덧붙인다. raw 8/13은 관련 추적 ID 목록이며 동일인·2명이라는 정답이 아니다.
- 030 카드는 86.033초 1행, 90.400–93.400초 6행, 99.233초 1행이다. 중간 카드에 기존 경보·양측 관측·소실 의심이 함께 남는다.
- 원래 `decision_time_pts`/`emitted_at_pts`로 순서를 정하며 마지막 관측이나 추정 사건 시각으로 소급하지 않는다. 모든 최초 알림 의도 시각은 해당 카드 첫 이벤트 시각과 같다. 직전 이벤트 간격 3초와 첫 이벤트부터 최대 10초는 고정이다.
- 세션 `E01_007-original`/`E01_030-original`, 카메라 C3/C6, 기존 출입구 C3_fence/C6_fence를 확인했다. 카드 ID와 notification key는 이 scope 및 첫 event ID에 기반한다. 실제 각 timeline snapshot의 event prefix, 관련 ID 합집합, count, source refs를 독립 대조하여 미래 정보가 앞선 snapshot에 들어가지 않음을 확인했다.
- 카드 상태는 침입 의심, person_count는 null, identity_merged/automatic_confirmation은 false다. 새 동일인 정답·침입 확인·행동 성능은 만들지 않는다.

## 웹 구현 검토

기존 서비스에 제한된 GET 카드 projection과 POST claim을 추가한다. bundle SHA·고정 policy·등록된 media ID·안전한 로컬 경로로 제한하고 raw source_event·좌표·provenance 파일 경로를 응답에 싣지 않는다. 원래 알림의 source pointer/event ID/raw ID/segment는 카드 상세에서 유지한다.

초기 검토에서 길이만 맞는 malformed snapshot의 미래 ID/중복 membership을 거부하지 못하는 점을 총괄에게 전달했다. 담당 수정 후 consumed event set, 정확한 snapshot prefix/ID 합집합/시각 검증과 관련 fixture 거부 테스트가 추가된 것을 확인했다. 실제 입력 bundle도 별도 감사에서 이 조건을 만족했다.

검토자가 기존 웹 환경에서 `python -m unittest tests_orca.test_incident_web -v`를 별도 실행하여 4/4 통과했다. 여기에는 동시 8개 claim 중 하나만 성공, 악성 origin/미등록 key/변조 SHA/부분 bundle/경로 이탈·symlink 거부와 미래/중복 snapshot 거부가 포함된다. 합성 fixture 결과이며 실제 브라우저 토스트의 증거는 아니다. 담당의 별도 CPU receipt는 incident 합성 30개와 EXP-0035 관련 회귀 82개 통과를 기록한다. 총괄이 저장한 실제 GET 응답 두 개도 bundle의 projection과 일치하고 raw payload·좌표·로컬 경로를 노출하지 않는 것을 독립 대조했다(`independent-projection-audit.json`).

최종 JS에 대해서도 검토자가 `node tests_orca/test_incident_web.js`를 실행하여 재생·seek·무음 갱신·영수증·poll fixture 통과를 확인했다(`independent-js-tests.txt`). 전체 저장소 테스트 통과나 영상 행동 정확도 검증으로 확대하지 않는다.

코드상 실제 재생이 created 시각을 통과할 때 즉시 claim하며 3초 수집 대기가 없다. updated는 무음이다. seek/rewind는 snapshot만 갱신하고 세대 번호로 이전 비동기 claim의 뒤늦은 표시를 차단한다. polling은 기존 video element가 있으면 재생 DOM 교체를 미룬다. 카드 DOM도 ID별로 유지하여 열린 원본 참조가 매 timeupdate마다 닫히지 않는다.

총괄의 실제 브라우저 명령과 결과 `delivery/cards-first-play-*`, `cards-030-and-navigation-*`, `cards-restart-navigation-*`를 읽어 검토했다. 실제 기존 MP4의 readyState 4에서 5개 최초 key가 각 한 번 visible DOM 토스트를 만들었고, 표시 시점의 원본 PTS 차이는 0.0313–0.2878초였다. 이는 로컬 재생 시점의 관측값이며 실시간 서버 처리 SLA나 일반 지연 성능이 아니다. 13개 후속 갱신은 무음이고, 007 접근 오탐 3행의 원래 참조도 보인다. 앞선 시각으로 seek하면 당시 prefix/ID/count만 남고, rewind 후 첫 시각을 다시 재생해도 토스트가 늘지 않았다. 수동 polling과 실제 15초 자동 polling 대기에서 video/card element와 currentTime이 유지됐다.

총괄의 서비스 재시작·페이지 새로고침 후 명령은 기존 5개 key를 모두 실제 재생으로 다시 통과했으며 새 토스트 0개였다. 최종 JS의 두 근거 버튼은 첫 의심 3초 전으로 pause/seek하고 과거 snapshot만 표시했으며 추가 토스트가 없었다. 브라우저에서 읽은 최종 JS SHA도 결과에 남아 있다. 이 검토는 명령·JSON 증거의 독립 확인이며, 검토자가 직접 CCTV를 보거나 사람 행동을 판정한 것이 아니다. `incident-toast-painted`는 앱의 DOM 가시 상태 계측이며 물리적 compositor 표시나 사용자의 실제 인지·수신 영수증은 아니다.

POST는 same-origin JSON과 등록된 notification_key만 수락한다. 별도 로컬 SQLite primary key와 INSERT OR IGNORE가 동시 claim을 한 번으로 제한하며 GPU 큐 DB·외부 알림·모델 호출은 건드리지 않는다. **저장 영수증은 claim 영수증이고 실제 토스트 표시/사용자 수신 영수증이 아니다.** claim 이후 네트워크 단절·탐색·페이지 종료가 생기면 토스트가 표시되지 않은 채 claim만 남을 수 있다. 정확히 한 번 전달을 보장한다고 쓰면 안 된다.

검토자가 이 DB를 읽기 전용으로 대조한 결과 실제 5개 최초 key와 정확히 일치했고 재시작 전 저장한 행과도 같았다(`independent-receipt-audit.json`). 이번 승인된 브라우저 검증에서 이미 claim을 소비했으므로 같은 녹화 세션의 이후 사용자 재생은 의도적으로 무음이다. 최초 알림을 다시 보이게 하려고 영수증을 지우거나 session ID를 바꾸지 않았다.

## 보존 및 최종 결속

초기 독립 해시 대조에서 보호 목록 1,440개 중 1,439개는 동일하고, 이번 승인된 웹 통합 대상 `webapp/app.js` 한 개가 변경됐다. 이를 1,440개 모두 불변이라고 보고하면 안 된다. 총괄에게 이전 등록 source bytes의 보존/결속과 이 예외의 명시를 요청했다. 원본·EXP-0035 출력·모델·관측·영역·캐시의 추가 차이는 없으며 canonical 47 jobs/47 attempts의 전체 행이 원본 snapshot과 같았다.

총괄이 보존한 `runtime/EXP-0036/webapp-app-before.js`의 SHA-256 `cae122f859102f7a6f0dd3255d9e4a7ec5491814f340dc9a4e28fff6ba8b9fcd`는 기존 보호 목록의 app.js SHA와 같다. 이 예외는 최신 사용자 승인에 따른 UI 코드 수정이며 과거 실험 결과를 덮어쓴 것으로 해석하지 않는다.

기준 commit `884afb8`의 기존 catalog 34개 항목은 현재와 같고, 기존 등록 report/metrics/review source 95개의 SHA 대조도 전부 일치했다(`independent-prior-registration.json`).

최종 재검사에서도 보호 1,439개는 동일하고 app.js만 승인된 변경이며 canonical 47 jobs/47 attempts의 전체 행은 그대로다. 현재 JS SHA-256 `ef4de9325fafa9596dd6c8f4f44ad846223366bb719d4b86352d3b8f88506225`는 재시작 후 실제 브라우저가 읽은 바이트와 같다.

총괄이 실제 브라우저 확인 후 freeze한 다음 두 파일을 읽고 최종 바이트를 결속했다. metrics 11개 모두 원천 SHA와 JSON pointer의 실제 값이 일치한다. 카드 감소의 한계, 의도/DOM 표시/claim의 구분, 정상 오탐 보존, 사람 수·동일인·침입 확인 부정, 승인 UI 예외와 큐 보존을 결과 문서가 함께 설명한다.

| 최종 검토 대상 | SHA-256 |
|---|---|
| `docs/experiments/EXP-0036-results.md` | `c17c18a2c848256511fd9b92c77a7a3bd11f85f0a3dc641a83f57a145045fa4c` |
| `records/EXP-0036/metrics.json` | `b9d3fe40d2acb3f1153666e8bb66eba241d77a60a7f6c63de79f2178341d048b` |

최종 로컬 감사는 `runtime/EXP-0036/independent-final-audit.json`에 코드·브라우저 증거 SHA와 함께 보관했다. 위 파일을 변경하면 이 검토를 새 바이트에 재사용할 수 없다. 최종 등록 후 화면/미디어와 GitHub 게시의 바이트 확인은 총괄의 별도 EXP-0036 전달 기록이며 이 검토가 선행 인증하지 않는다. 새 추론·학습·영역/의심 기준 변경을 승인하지 않는다.
