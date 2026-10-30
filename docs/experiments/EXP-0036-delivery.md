# EXP-0036 화면 적용·결과 전달

기존 `http://127.0.0.1:8765/` → **담당3 → EXP-0036 → 사건 카드 재생**에서007/030의 기존 비교 영상과 카드 흐름을 확인한다. 원래 EXP-0035 결과/미디어는 보존한다. 이 결과는 알림 정리 기능의 적용이며 모델 정확도 인증이 아니다.

## 실제 수행과 화면 확인

- 최신 main `884afb8`을 clean 작업 트리에 fast-forward. 기존 Run `run_3d23462a014a` 재사용.
- CPU Sol high: task `task_d4d957340ef8`, dispatch `ctx_3089225530c8`. 웹 Terra high: task `task_654675873690`, dispatch `ctx_e9017a6b540a`. 독립 Astra high: task `task_4f45dad9cffc`, dispatch `ctx_a4d391bc24a2`. 요청 모델/effort와 실제 launch가 모두 일치했다.
- 실제00710알림/2카드/최초2/무음8,0308/3/3/5. 기존 JSON에 각1회만 적용했고 새 MP4 생성이나 GPU 호출은 없다.
- 기존 서비스의 배정된 EXP-0036 화면에서 실제 영상 재생을 통해 최초 DOM 토스트5회·무음 갱신13회, 과거 시각의 카드/ID/참조 일치, 같은 카드 DOM/펼친 상세 유지, 수동·15초 자동 폴링 중 재생 위치 유지 확인.
- 서비스 프로세스를 정상 stop/start하고 브라우저를 새로고침한 뒤5개 최초 알림 시점을 재생해 중복0회 확인. 별도 로컬 영수증 DB의5행이 전후 정확히 같았다. 기존 GPU 큐47jobs/47attempts는 별개이며 바꾸지 않았다.
- 최종 코드의 근거 이동 버튼도 실제00767.133초/03087.400초로 seek+일시정지하고 무음임을 확인했다.

현재 저장 재생 데모의 최초5회는 위 검증에서 이미 표시됐다. 같은 세션을 다시 재생해도 새 토스트를 반복하지 않고 카드는 당시 정보대로 다시 표시한다. 영수증을 임의로 초기화하거나 테스트를 실제 새 사건으로 생성하지 않았다. 선점 뒤 표시 실패 가능성은 남으므로 영구적 exactly-once 사용자 수신을 보장하지 않는다.

코드만 작성한 것과 실제 화면 확인을 구분한다. 첫 표시/재생은 `cards-first-play-result.json`,030·폴링·되감기는 `cards-030-and-navigation-result.json`,최종 새로고침·재시작·버튼은 `cards-restart-navigation-result.json`에 기록했다. 모두 로컬 `runtime/EXP-0036/delivery/`에 보관한다. 브라우저 사건 관측은 앱 DOM 표시 계측이며 사용자의 시각 수신을 인증하지 않는다.

## 로컬 연결·복구

기존 local_config의 `incident_bundles`에 두 bundle의 상대 경로·SHA-256·`experiment_id: EXP-0036`·기존 media_artifact_id를 등록했다.007은 `exp0036/007-cards-v1.json`과 `exp0035-007-comparison`,030은 같은 이름의030 자료다. 임의 경로 API/원본 JSON 업로드/외부 알림은 없다. 서버는 등록된 배정 또는 완료 결과와 실제 artifact를 확인한다. 코드·문서는 GitHub, JSON·HTML·원본 미디어·설정·영수증 DB는 로컬 전용이다.

기존 환경의 Python으로 아래 명령을 사용한다. `LOCAL_CONFIG`는 이미 사용하던 로컬 설정 파일이다. 다른 서버나 큐를 만들지 않는다.

```bash
python -m orchestration.lab --config LOCAL_CONFIG status
python -m orchestration.lab --config LOCAL_CONFIG stop
python -m orchestration.lab --config LOCAL_CONFIG start
```

기존 서비스 관리기는 저장 PID의 실제 identity를 확인하고 자신이 관리하는 web/projection만 재시작한다. GPU 큐·Orca 에이전트는 중지하지 않는다. 영수증 파일 `exp0036-notification-receipts.sqlite3`은 기존 canonical runtime에 따로 있으며 GPU DB와 분리했다. 원본 번들 해시가 다르거나 미등록이면 카드 API는 거부하므로 경로/해시/등록/서비스 상태를 확인한다. 구 결과나 알림 영수증을 지워 복구하지 않는다.

기존 app.js SHA는 `cae122f859102f7a6f0dd3255d9e4a7ec5491814f340dc9a4e28fff6ba8b9fcd`,최종은 `ef4de9325fafa9596dd6c8f4f44ad846223366bb719d4b86352d3b8f88506225`다. 상속 보호 목록1439개 불변과 승인된 이1개 변경을 분리했다. 기존 등록 보고서/metrics/검토95파일과 이전 catalog34행은 보존했다.

## 등록·게시 확인

결과 보고서·metrics·독립 검토를 정확한 해시로 완료 등록했고 실제 서비스의 보고서/그래프/검토/미디어를 대조했다. GitHub 게시 검증도 별도로 완료했다.

등록 후 실제 담당3/EXP-0036에서 원문 펼치기·측정표11행·그래프2개·독립 검토·기존 영상2개의 디코드/재생/seek와 자동 폴링 유지가 통과했다. 두 artifact의 HTTP 바이트도 원본 로컬 MP4와 일치한다. 별도 카드 재생 부분에서도00710알림/2카드와0308알림/3카드가 표시되고, 재생·폴링 중 같은 video/card와 펼친 원래 참조가 유지되며 중복 토스트0임을 다시 확인했다.

완료된 서비스 API/DOM의 원문 버전은 다음과 같다.

|파일|SHA-256|
|---|---|
|`docs/experiments/EXP-0036-results.md`|`c17c18a2c848256511fd9b92c77a7a3bd11f85f0a3dc641a83f57a145045fa4c`|
|`records/EXP-0036/metrics.json`|`b9d3fe40d2acb3f1153666e8bb66eba241d77a60a7f6c63de79f2178341d048b`|
|`docs/reviews/EXP-0036-independent-review.md`|`941b26a07409bb49c4ba151d477669846ef15aadaf383db0ecf82725191ba830`|
|`docs/reviews/EXP-0036.binding.json`|`489540243b4bcc53dc19bd65f856db67e3a11bce2d02ee0eb7d9bfc14a0a34f9`|

`browser-media.json`과 `cards-registered-result.json`이 완료 등록 뒤의 실제 화면 receipt다. 최초 알림 시험과 원래 JSON의 분류 정확도를 혼동하지 않는다. 이번 세 작업자는 완료 후 release했고 미정리 worker0이다. 이전 retained 작업자는 그대로다.

코드·문서·공개 집계/등록 기록16파일만 명시적으로 staging했다. 미디어·원시 결과·로컬 설정·DB·로그는 제외했다.

결과 commit **`431fe803eb262f133913f798f53145fb607e9cd9`**을 GitHub main에 푸시했다.2026-10-30 13:19:24 UTC에 원격 main이 해당 commit인지 확인했고, catalog/assignment 및 위 보고서·metrics·독립 검토·binding4파일의 게시 바이트가 실제 서비스/로컬과 일치했다. 서비스가 제공한 app.js/style.css도 Git commit의 바이트와 정확히 같았다. 영수증은 로컬 `github-result-commit.json`, `github-served-assets.json`이다.

이 전달 확인 문서는 후속 문서 commit으로 게시하며 검토 결속된4파일이나 코드·결과를 바꾸지 않는다. 최종 원격 main과 동일 검토본 확인 receipt는 `github-final-commit.json`에 로컬 보관한다.

**사건 카드 기능·최초1회/무음 갱신·실제 기존 화면 적용·GitHub 게시 확인 완료.** 기존 침입 의심 조건·모델·영역과 판별 성능의 한계는 그대로이며 추가 실험을 시작하지 않는다.
