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

## 단계별 GitHub 게시

`3e9a6bb`는 입력 감사 코드/계약, `e0dc11a`는 검토된 입력 감사·신규 모델 선정 문서·RF-DETR 실행 전 소스 고정이다. 정상 HTTPS `git push origin main`으로 `1a06f6c..e0dc11a` 게시를 확인했다. 이 커밋 시점에는 CV 실제 실행 결과와 EXP-0018 완료 등록은 아직 포함되지 않았다. 각 최종 결과의 원격 byte 확인은 해당 결과 등록 후 별도 수행한다.

원본/추출 미디어·배열·raw 예측/응답·weights·환경·DB·raw log·receipt는 로컬 전용이다. `.venv-cv-batch02`와 `.venv-vlm-batch02`도 저장소 ignore에 추가했고, 기존 환경과 이전 실험은 보존했다.
