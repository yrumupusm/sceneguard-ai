# WEB-0005 독립 검토

2026-11-03. 현재 미커밋 변경을 독립 검토하고 담당자의 수정 후 재검증했다. **최초 중간 심각도 발견 3건은 수정 확인했고, 현재 검토 범위에서 미해결 높음/중간 코드 결함은 없다.** Python 51개·Node 12스위트와 별도 인메모리 재현 검증이 통과했다. 구현 수정·서비스·실제 브라우저 검증은 담당자가 소유하며, 아래 최초 발견 사항은 이력으로 남긴다.

## 최초 발견 사항

1. **중간 — 저장 중 수정한 답변의 미저장 상태가 사라짐.** 최초 `webapp/app.js:365–371`은 저장 버튼만 비활성화하고 성공 시 무조건 `dirty=false`로 바꾼다. 답변 A를 제출하고 응답을 지연시킨 동안 B로 편집하면 서버에는 A, 입력란에는 B가 남지만 저장 완료로 표시하며 새로고침 보호가 해제된다. 인메모리 Node DOM 재현에서 `posted=A`, `visible=B`, `dirty=false`를 확인했다. 입력을 잠그거나 제출 스냅샷/편집 세대를 비교해 새 편집을 미저장 상태로 보존해야 한다.
2. **중간 — artifact 단독 요청의 요청 시각을 재생에 반영하지 않음.** 최초 `webapp/app.js:320–325`는 artifact 단독 근거를 붙이기만 한다. 저장소는 명시적 `source_window`가 있으면 `source_time`이 있는 artifact 단독 요청을 허용하며 해당 Python 시험도 존재한다. 이런 요청에서 ‘요청 구간 보기’를 누르면 지정 시각 대신 영상 처음을 표시한다. 명시적 미디어 시계로 이동하거나, 시계가 확인되지 않으면 시각 지정 요청을 거부해야 한다.
3. **중간 — 같은 bundle의 두 검수 UI가 같은 라디오 그룹을 공유함.** 최초 `webapp/app.js:314`의 요청 근거와 하단 기본 흐름은 동일 bundle을 동시에 렌더할 수 있다. `addAssessment`의 최초 539행 라디오 이름은 bundle/incident/key만 포함하고 별도 form에 속하지 않아, 한 UI에서 선택하면 다른 UI의 선택이 해제된다. 이후 다른 UI의 저장이 `unreviewed` 기본값으로 바뀔 수 있다. 렌더 인스턴스별 그룹 이름 또는 form을 사용하되 API의 bundle/incident ID는 유지해야 한다. 이는 DOM 이름 규칙과 호출 경로의 정적 검토이며 최초 체크포인트에서 실제 브라우저 재현은 수행하지 않았다.

위 발견은 Orca 담당자에게 조기에 전달했다. 기존 Node 시험 세 개도 최초 실행에서 실패했다: `test_assessments.js:39`는 label 내부로 이동한 textarea를 직접 자식으로 찾고, `test_cards.js`는 새 summary 갱신에 필요한 DOM 모의 함수를 제공하지 않으며, `test_incident_web.js:117`은 제거된 링크에 따른 자식 인덱스와 이전 storage key를 가정한다. 동작 검증을 삭제하지 않는 fixture 수정과 재실행이 필요하다.

## 확인한 구현과 시험

- 요청별 `expected_version`과 `answer_version`을 `BEGIN IMMEDIATE` 안에서 검사한다. 오래된 쓰기는 409로 거부하고 현재 답변과 이력을 보존한다.
- 답변 수정은 AI 처리 상태를 `answered`로 되돌리며 이전 답변과 처리 메모는 이력에 남긴다. 웹은 답변 저장만 제공하고 acknowledge/resolve는 로컬 CLI로 분리한다.
- 요청이 없는 읽기는 DB를 만들지 않으며 빈 상태는 ‘검수 요청 없음’이다. 이전 수동 검수나 영수증을 새 요청의 완료 근거로 사용하지 않는다.
- 요청 목록은 experiment ID로 필터하며, 생성 시 bundle/artifact의 등록 실험 소속과 경로·시각 범위를 검증한다. 소스 등록 또는 바이트 변경은 후속 쓰기를 거부한다.
- 새 저장소는 `runtime_dir/review-requests.sqlite3`로 분리된다. 기존 incident/saved review/receipt 저장 코드는 변경하지 않으며 이 검토자는 운영 DB를 쓰지 않았다.
- 요청/근거 조회 실패는 오류 안내로 남기며 다른 실험의 근거로 대체하지 않는다. 페이지 요청 세대와 연결된 DOM 확인이 오래된 비동기 응답의 다른 실험 표시를 막는다.
- 초기 Python 실행: `/home/jhc7484/dev/sceneguard-orca-lab/.venv-orca-lab/bin/python -m unittest tests_orca.test_review_requests tests_orca.test_saved_result_review tests_orca.test_incident_web tests_orca.test_web` — **50개 통과**.
- 초기 전체 `tests_orca/test_*.js` 실행 — 위 세 fixture 실패. 수정 후 결과는 후속 절에 기록한다.

## 수정 후 재검증

1. `webapp/app.js:364–375`: 저장 진행 중 중복 제출을 거부하고 답변 옵션·직접 답변·검토자·메모를 모두 비활성화한다. 성공 및 실패 후 입력을 다시 활성화한다. 독립 Node 재현에서 모든 입력 잠금, 중복 POST 0회, 성공 후 해제, 409 후 `dirty=true` 보존을 확인했다.
2. `webapp/review_request_store.py:157–159`: 시각을 지정하려면 등록 bundle이 필요하다. artifact 단독은 시각 없이만 허용한다. 수정된 Python 시험이 등록 `source_window`만 있는 artifact의 시각 지정도 거부함을 확인한다. UI가 추측한 시계로 잘못된 구간을 열지 않도록 지원 범위를 명시적으로 제한했다.
3. `webapp/app.js:528,541`: 검수 라디오 이름이 렌더 인스턴스별로 분리됐다. 독립 Node 재현에서 동일 bundle·incident를 두 번 렌더한 두 세트의 그룹 이름이 겹치지 않음을 확인했다. API ID는 그대로다.
4. 기존 label 구조·링크 제거·실험별 storage key에 맞춘 시험 fixture 수정 뒤 **Node 12스위트 전체가 통과**했다. 기존 사건 검수 충돌/저장 이벤트, 재생·되감기·알림 영수증·폴링 동작 검증을 유지했다.
5. 위와 같은 Python 명령 재실행으로 **51개 통과**를 확인했다. 추가된 CLI `pending --include-acknowledged`는 중단된 처리도 재개할 수 있도록 이미 읽은 미처리 답변을 포함한다.

독립 인메모리 Node 검증은 stdin으로 실행했으며 구현·시험 파일에 새 변경을 남기지 않았다. 재검증한 핵심 파일 SHA-256은 다음과 같다.

| 파일 | SHA-256 |
| --- | --- |
| `webapp/app.js` | `8c7efc6403525fa2693906e50295d6d605b83c8abba790dbcf4e673660c5ccef` |
| `webapp/review_request_store.py` | `97610234cb2d95c3734e16592d4af58772ca30609a2b9ebbd9fea89c0a1344fd` |
| `webapp/review_requests.py` | `41583cd18d575f49a986b35e711b7ab6dc275e79630fd7f9a755657dc3c8e95c` |
| `scripts/review_requests.py` | `8954d2facd7949381b40fc477bb7f1fd2350868cce4ee6bb71781479ee76697c` |

## 범위와 한계

폴링은 질문 폼을 재구성하지 않고 같은 실험에서 이력으로 이동했다 돌아올 때 DOM이 유지된다. 다만 A 검수 → 이력 → B 검수 → 이력 → A 검수로 이동하면 A의 미저장 초안이 사라진다. 실험 간 초안 보존은 현재 지원 범위가 아니며, 담당자가 `docs/WEB_REVIEW_WORKFLOW.md`에 다른 실험으로 이동하거나 브라우저를 닫기 전에 저장하도록 명시했다.

요청에 묶인 기존 보고서·측정치·미디어를 수정하면 해당 요청의 후속 처리도 원본 변경으로 거부한다. ‘답변 반영 후 resolve’ 과정에서 기존 보고서를 직접 수정하는 경우의 충돌을 전달했고, 담당자가 위 workflow 29행에 기존 원본을 보존하고 새 후속 문서·새 결과 또는 작업 코드에 반영한 뒤 처리 메모로 연결하도록 명시했다. 이 제한은 원본 보호를 약화하지 않고 유지한다.

실제 서비스 재시작·운영 DB 해시 비교·실제 브라우저 재생은 담당자가 수행한다. 독립 검토자는 테스트용 임시 데이터만 사용했으며 운영 요청 생성, 모델/GPU, git commit/push, 구현 수정 및 중첩 에이전트를 사용하지 않았다. Python 시험 통과는 행동 성능이나 AI가 실제 답변을 반영했다는 증거가 아니다.
