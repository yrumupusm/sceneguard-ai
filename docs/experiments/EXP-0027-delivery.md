# EXP-0027 전달 및 종료 확인

2026-10-29. [진단 결과](EXP-0027-detection-low-confidence-diagnosis.md)의 **14회 실행·독립 검토·기존 웹 등록·실제 렌더·GitHub 게시를 각각 확인**했다. 실제 사람 대응과 학습 라벨 의미 검수는 미완료이고 기본 채택은 보류한다. 이 문서는 새 실험이나 사람 검수 완료를 뜻하지 않는다.

## 구현과 실행

- GitHub 계획 `b79a9eb`을 로컬 변경 충돌 없이 fast-forward했다. 코드·입력 freeze는 `f8360446b68a8807a4b07a7f8dad1c9b52ec7330`이다.
- 기존 Orca Run `run_3d23462a014a`에서 추론 Sol high, CPU 라벨 감사 Sol high, 독립 검토 Astra high의 실제 requested/effective 모델·effort를 확인했다. 새 총괄이나 GPU 큐를 만들지 않았다.
- canonical job `3eda4fd66f9c4fed9ef98997436362cb` / attempt `111e49f413a4446586e629cd65419721` 한 번 성공. sample14, warmup2, 오류/OOM/retry0. 기존43jobs/43attempts의 모든 행을 보존해44/44가 됐다.
- CPU39개와 라벨 감사13개가 통과했다. 원본 ZIP·준비파일1,108개·환경·가중치·과거 결과를 보존했다. 비교 이미지7장과 개별 패널21장·raw Results·원시 tensor/로그는 로컬 전용이다.
- 세 작업자의 worker_done을 실제 Task/Dispatch와 대조한 뒤 모두 release했다. 이 작업의 미회수 worker0, queued/running/unknown GPU job0을 확인했다. 다른 사용자가 보유한 기존 터미널은 변경하지 않았다.

## 독립 검토와 등록

[독립 검토](../reviews/EXP-0027-independent-review.md)는 `accepted_for_comparison`, 적용은 `adoption_on_hold`다. 원시14 Results의 구간별 계수와 캐시 재현·측정값69개·정확한 보고서/metrics SHA를 독립 확인했다. immutable [binding](../reviews/EXP-0027.binding.json)과 기존 COMPLETE_CLI로 담당3의 EXP-0027에 등록했다. 등록 응답이 GitHub/브라우저를 자동 검증한다고 해석하지 않았다.

| 대상 | SHA256 |
|---|---|
| 진단 보고서 | `242718f4862ac9375615370179d9c8301048fb891460577f13f78190288a0cca` |
| 공개 metrics | `56330c93b7476ad1b69ebb49c334afd5d865edb46db17ffe7757d42c7afcaf35` |
| 독립 검토 | `46af9d165e34debf346f55cfcef11141137da672c6e5b1cba51358c2ffa92218` |
| review binding | `774169d614afc56ddfa92a18981ff70d065609ba588f1673912ead4f6388209c` |

## 실제 로컬 화면

주소는 `http://127.0.0.1:8765/`, **담당3 → EXP-0027**이다. 실행 전 실제 카드에서 Sol high 배정·진행 중·결과 미등록을 확인했고, 완료 후 등록 결과11개 중 EXP-0027을 선택해 검증했다. 카드의 과거 작업자 실패 문구는 슬롯의 과거 이력을 합친 표시이며 EXP-0027 실패가 아니다.

Orca 브라우저의 실제 DOM에서 보고서/검토 본문, 측정값69개와 미측정 표시, 그래프2개, 비교 이미지7개의 표시·decode를 검증했다. 각 이미지5760×1140이고 served bytes가 로컬 SHA와 같으며16.5초 갱신 후 동일 이미지 노드가 유지됐다. 이번 산출물은 정지 이미지이므로 새 영상 재생 검증은 해당 없음이다. 이미지 표시 검증은 사람이 박스 대응을 확인했다는 뜻이 아니다. 스크린샷이나 media bytes를 외부 에이전트로 전송하지 않았다.

서비스 `/api/experiments/EXP-0027`의 review_integrity는 current이고 current_source_sha256은 위 네 파일과 같다. 서비스가 제공하는 기존 app.js SHA는 `cae122f859102f7a6f0dd3255d9e4a7ec5491814f340dc9a4e28fff6ba8b9fcd`로 로컬과 일치하며 웹 기능/디자인 변경은0이다. 로컬 증거는 `runtime/EXP-0027/delivery/progress-browser.json`, `browser-images.json`, `browser-command.json`이다.

## GitHub 게시

`f836044` 구현 커밋과 `b4ab5fdc71807fc0e067d7cff1d5abe5df445249` 결과 커밋을 origin/main에 push했다. GitHub 검증 도구로 remote main 및 실제 원격 Git 객체의 catalog/assignment/report/metrics/review/binding 바이트를 읽어 로컬과 대조했다. 해당 결과 커밋 검증 시각은 2026-10-29T14:47:00Z이며 네 파일의 SHA가 실제 서비스와도 같았다. 짧은 SHA 인자를 거부한 첫 검증 호출은 원격 게시 실패가 아니며, 전체40자리 SHA로 확인한 성공 receipt를 따로 보존했다.

게시 전에 변경 경로·확장자·크기를 검토하고 원본 영상/이미지·라벨·weights·cache·raw output·runtime가 ignore 대상임을 확인했다. 공개는 코드·문서·비식별 집계와 등록 정보뿐이다. 이 전달 기록은 위 결과 커밋 다음에 추가하며 결속된 실험 파일의 해시를 바꾸지 않는다. 로컬 `github-results-fullsha.json`과 후속 최신 HEAD 검증 receipt를 웹 검증과 분리 보관한다.

## 남은 한계와 종료

90초 낮은 점수 출력은 사전학습6/학습 후1행이고94초는 양쪽0행이다. 실제3명 대응·중복·신체 일부·배경 여부는 사용자에게 한 번에 요청했으며 아직 미확정이다. 라벨 전체113패널/354행은 review_pending, 우선27행/15패널, D0false다. 기술 실행 성공을 파인튜닝·검출·행동 성능 성공으로 표시하지 않는다. 다음은 이 준비 자료의 사람 대응 검수 한 가지이며, 현재14회 한도 종료 후 추가 학습·추론·설정 sweep·기본값 변경을 예약하지 않는다.
