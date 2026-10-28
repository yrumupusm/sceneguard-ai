# BATCH-0002 전달 검증 기록

2026-10-29 KST. 실험 실행, 독립 검토, 로컬 등록, 실제 화면, GitHub 게시를 각각 확인한다. 아래는 완료된 단계만 기록하며 미등록 EXP 결과를 완료로 취급하지 않는다.

## 입력 감사 EXP-0018

- 기존 Run `run_3d23462a014a`, Sol high Task `task_806f089dde4f` / Dispatch `ctx_f0c0eef8ed14`, 담당 1 배정을 사용했다.
- 독립 Astra high Task `task_ee659fa7f415` / Dispatch `ctx_27488fe9f84b`가 실제 audit 재실행 없이 소스·111개 소비 파일·29개 표시 자료·14개 합성 테스트와 사용자 관찰의 적용 범위를 검토했다. 판정은 비교 허용, 채택 보류다.
- `orchestration.complete`로 보고서·4개 감사 측정값·독립 검토·세 로컬 영상을 등록했다. 보고서와 metrics는 독립 검토의 SHA-256과 동일하며 [binding](../reviews/EXP-0018.binding.json)에 연결돼 있다.
- 2026-10-28 16:50 UTC 실제 `http://127.0.0.1:8765/` 브라우저에서 담당 1 → EXP-0018 → 보고서 펼치기, 4개 측정값/2개 그래프, 검토 의견, q04/v01/v03의 5초 영상 재생과 1.5초 seek를 확인했다. 상태 폴링 뒤 영상 노드도 유지됐다. 화면 자료는 2fps 샘플 표시이며 전체 프레임 원본 영상과 다르다.
- API의 보고서·metrics·review·binding 해시와 실제 서비스의 JavaScript 해시를 로컬 checkout과 별도로 대조했다. JS SHA-256은 `cae122f859102f7a6f0dd3255d9e4a7ec5491814f340dc9a4e28fff6ba8b9fcd`다. 새 웹 기능은 없다.
- 로컬 receipt: `runtime/BATCH-0002/input-delivery/browser-r1.json`. 이 기록의 화면 확인은 GitHub 게시 확인을 대신하지 않는다.
- 정상 push 후 원격 `main`의 `d5f64061913f9a5fae4ca0259113b85c63123d51`에서 assignment/catalog와 보고서·metrics·review·binding byte 확인을 통과했다. 별도 receipt는 `runtime/BATCH-0002/input-delivery/github-r1.json`이다.

## 검출기 비교 EXP-0019

- Sol high Task `task_5dbd99e6ff9a` / Dispatch `ctx_0578048b13d3`, 담당 2를 사용했다. 기존 큐의 2개 작업/첫 attempt에서 11개 고유 프레임을 한 번씩 실행했다. 오류/OOM/retry 0, FCOS 재추론 0이며 원래 18개 작업/attempt를 보존했다.
- 독립 Astra high Task `task_14a8a08146b2` / Dispatch `ctx_ef71a0f01600`가 역사적 실행 소스 commit, 정확한 native PTS/cache, 45개 지표 포인터, 실제 반환값·시간·메모리·환경/기존 결과 보존을 검토했다. 12개 합성 테스트가 통과했다. 기술 실행/비교는 PASS, 사람 복원·박스 품질 판정과 채택·결합 PoC는 미확정/보류다.
- 기존 완료 CLI로 [보고서](EXP-0019-cv-comparison.md), 45개 metrics, [독립 검토](../reviews/EXP-0019-independent-review.md), [binding](../reviews/EXP-0019.binding.json), 11개 원본/FCOS/RF-DETR 정지 비교와 2개 기존 참고 영상을 등록했다.
- 2026-10-28 17:09 UTC 실제 브라우저에서 담당 2 → EXP-0019, 보고서 펼치기, 45개 측정값/2개 그래프, 검토 의견, 두 영상의 재생/1.5초 seek와 폴링 유지가 통과했다. 추가 DOM 검사에서 11개 비교 이미지 모두 2880×570으로 decode됨을 확인했다. 이미지를 AI가 시각적으로 검수했다는 뜻은 아니다.
- 영상 하나는 기존 030:88.6–91.5 원본/B/C 추적 비교(정상·0.25배속), 다른 하나는 007:62.5–67.5 원본 참고다. 신규 RF-DETR 연속 영상으로 표기하지 않았다. 신규 검출 비교는 고정한 11개 정지 화면이다.
- 서비스가 읽는 report/metrics/review/binding 및 JS 해시를 별도로 확인했다. 로컬 receipt는 `runtime/BATCH-0002/cv-delivery/browser-r1.json`과 `browser-images-r1.json`이다.
- VLM의 입력 준비 오류로 GPU 실행이 중지된 동안 검토된 CV 결과를 별도 커밋 `9ee67530cd527f6dab4cdc2e596d04368b985a7f`에 게시했다. 2026-10-28 17:46 UTC 원격 main의 assignment/catalog와 report/metrics/review/binding byte 검증을 통과했다(`github-r2.json`). 앞선 검증 호출은 전체 commit SHA 형식이 잘못돼 실행 전 거부됐으며 `github-r1.json`에 보존했다. 올바른 전체 SHA로 검증한 것이고 모델 재실행은 없다.

## 진행 중 배정 표시

2026-10-28 16:55 UTC 기존 실제 브라우저의 담당 2와 담당 3 카드에 각각 진행 중 상태가 나타남을 확인했다. native projection은 정확한 CV Task/Dispatch와 VLM Task/Dispatch를 live/working으로 연결했다. 이는 에이전트 작업 상태이며 GPU 추론 중이라는 뜻은 아니다. 당시 CV의 두 GPU 작업은 이미 완료됐고 VLM은 가중치 다운로드와 코드 준비 중이었다. 과거 실패 작업도 기존 카드에 함께 표시되므로 카드 전체의 문구를 현재 실험 실패로 해석하지 않는다. 로컬 receipt는 `runtime/BATCH-0002/working-cards-browser.json`, `status-after-cv.json`이다.

## VLM 비교 EXP-0020

- 담당 3의 기존 Sol high Task `task_cf14cc142ed2` / Dispatch `ctx_0d176c9c2889`, Astra high 독립 검토 Task `task_f5ce741eef6c` / Dispatch `ctx_0fd8c4b82c38`를 사용했다. 새 총괄·queue·웹 기능은 없다.
- 사전 고정 10개 5초창/16개 view의 생성을 각각 한 번 완료했다. 17개 새 queue job/attempt는 16성공과 v01의 모델 로딩 전 입력 기록 호환성 오류 1개다. 실패를 보존하고 v01의 논리적 retry 한 번만 사용했다. q 12개 성공 결과와 수정 전 33개 row를 바꾸지 않았고 최종 queue 37개 job/attempt는 모두 settled다. 파싱 실패 6개는 생성 실패/OOM과 구분한다.
- 원래 q 및 실패 v01 소스는 `952c52f`, 수정 후 v 네 조건은 `78ba67df03f9a2f3307d85488d7f201eed119924`다. 소스 25개/합산 digest `f7c7a461f0dc94b6e78a2d8c4ed1db6cde08ccfa1b3fd90b534ca3f5d524eac1`을 Git 객체와 대조하고 새 실행 허가에 연결했다. 원 실행 허가도 별도 보존했다. 명시적으로 연결된 수정 job과 좁은 retry guard를 사용했으며 DB trigger·복구용 schema 변경·원 row 덮어쓰기는 없다.
- 독립 검토는 28개 회귀 테스트를 직접 통과시켰고, 담당자의 전체 115개 중 113통과/2skip 기록, 네 실제 v의 CPU processor/RGB/확장 질문 동등성 및 immutable 16출력을 확인했다. 모델·가중치·질문·ROI·샘플링·생성 설정은 유지했다. 최종 검토는 38개 metrics의 원본 포인터, 224개 artifact/receipt 해시, CPU 요약 재생산과 총괄 결론까지 확인했다. 기술 실행·정직한 비교 기록은 PASS이며 행동 성능·채택은 보류다.
- 공개 결과는 원 응답 자체가 아닌 파싱·후보·완료 주장·비용과 기존 사용자 관찰에 대한 검토 초안이다. 메모리는 기존 2B의 준비/전송/생성 포함 peak와 새 4B의 별도 로딩/생성 peak를 구분한다. 선택한 개발창의 차이를 범용 정확도나 통제된 속도/메모리 우위로 표현하지 않는다.
- 기존 완료 CLI로 [보고서](EXP-0020-vlm-comparison.md), 38개 metrics, [독립 검토](../reviews/EXP-0020-independent-review.md), [binding](../reviews/EXP-0020.binding.json)을 등록했다. 보고서 SHA-256 `9dc4ac83f6c169ce805038effdf1e404f13d2130d03d7b69e4c906ec9e6c054f`, metrics `68ff7e077f97c02e0f5bed0ba70d0cd3ab8e8f740be2310c84fda15408e4927f`, review `55ef40e57689a432d1e857f8ddd347b664b8c8ee8a8a3054e3299c6b93d550f9`를 고정했다. 검토 상태는 `accepted_for_comparison`, 적용 상태는 `adoption_on_hold`다.
- 로컬 근거는 기존 원본 참고 영상 q04/q05/v01/v03 네 개와 실제 4B processor 입력 표시 일곱 개로 제한했다. 원본 동영상과 2fps 모델 관측 시트를 구분하며 새로운 영상 추론 결과나 사용자 확정 정답이 아니다. 기존 allowlist만 사용했다.
- 2026-10-28 18:55 UTC 실제 브라우저에서 담당 3 → EXP-0020 → 보고서 펼치기, 38개 측정값/2개 그래프와 검토 의견을 확인했다. 네 5초 영상 모두 실제 재생, 1.5초 seek, 상태 폴링 뒤 노드 유지가 통과했다. 별도 DOM 검사에서 일곱 입력 이미지의 decode와 자연 해상도를 확인했다(여섯 개 1920×504, q04 C 1920×914). 이는 화면 동작 확인이며 AI의 새로운 영상 의미 검수는 아니다.
- 실제 서비스의 report/metrics/review/binding byte와 JS SHA-256을 checkout과 별도로 대조했다. JS는 앞선 입력 감사/CV 때와 동일하며 웹 코드를 바꾸지 않았다. 로컬 receipt는 `runtime/BATCH-0002/vlm-delivery/browser-r1.json`과 `browser-images-r1.json`이다. GitHub 게시 검증은 아래에 별도로 기록한다.

## 작업 종료와 보존

입력 감사·CV·VLM 실행 담당과 독립 검토자의 실제 native `worker_done`을 각각 확인했다. 마지막 VLM 담당·검토자는 모두 `succeeded`로 종료했다. 종료 후 `worker-release`는 두 터미널 모두 사용자가 인계한 `user_takeover` 보존 대상으로 응답했으므로 강제 종료하지 않았다. Run의 정리 대상 `reclaimable` 작업자는 0이다. 이미 완료된 담당자에게 보낸 후속 종료 알림 하나는 `dispatch_inactive`로 거부돼 재전송하지 않았으며 새 작업/실행을 만들지 않았다.

최종 37개 GPU queue job/attempt는 모두 settled이고 추가 모델 작업·재시도·결합 PoC는 예약하지 않는다. 테스트 통과, 고정 실행 완료, 웹 전달 확인, 행동 성능 충족을 서로 구분한다. 이번에 확인된 것은 앞의 세 가지이며 새 두 모델의 기본 적용과 행동 성능 충족은 보류다.

## 단계별 GitHub 게시

`3e9a6bb`는 입력 감사 코드/계약, `e0dc11a`는 검토된 입력 감사·신규 모델 선정 문서·RF-DETR 실행 전 소스 고정이다. 정상 HTTPS `git push origin main`으로 `1a06f6c..e0dc11a` 게시를 확인했다. 이 커밋 시점에는 CV 실제 실행 결과와 EXP-0018 완료 등록은 아직 포함되지 않았다. 각 최종 결과의 원격 byte 확인은 해당 결과 등록 후 별도 수행한다.

`d5f6406`은 입력 감사 등록·전달, `952c52f`는 Qwen4B 실행 전 사양·코드 고정, `9ee6753`은 검토된 CV 실제 결과·등록, `78ba67d`는 한 번의 논리적 retry를 제한하는 과거 VLM 입력 기록 호환성 수정이다. 모두 정상 push로 게시했고 기존 결과와 공식 라벨을 덮어쓰지 않았다. 최종 VLM 결과/등록과 총괄 종료 문서는 별도 커밋으로 게시하고 원격 내용을 다시 확인한다.

원본/추출 미디어·배열·raw 예측/응답·weights·환경·DB·raw log·receipt는 로컬 전용이다. `.venv-cv-batch02`와 `.venv-vlm-batch02`도 저장소 ignore에 추가했고, 기존 환경과 이전 실험은 보존했다.
