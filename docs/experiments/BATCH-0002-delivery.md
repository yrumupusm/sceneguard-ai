# BATCH-0002 전달 검증 기록

2026-10-29 KST. 실험 실행, 독립 검토, 로컬 등록, 실제 화면, GitHub 게시를 각각 확인한다. 아래는 완료된 단계만 기록하며 미등록 EXP 결과를 완료로 취급하지 않는다.

## 입력 감사 EXP-0018

- 기존 Run `run_3d23462a014a`, Sol high Task `task_806f089dde4f` / Dispatch `ctx_f0c0eef8ed14`, 담당 1 배정을 사용했다.
- 독립 Astra high Task `task_ee659fa7f415` / Dispatch `ctx_27488fe9f84b`가 실제 audit 재실행 없이 소스·111개 소비 파일·29개 표시 자료·14개 합성 테스트와 사용자 관찰의 적용 범위를 검토했다. 판정은 비교 허용, 채택 보류다.
- `orchestration.complete`로 보고서·4개 감사 측정값·독립 검토·세 로컬 영상을 등록했다. 보고서와 metrics는 독립 검토의 SHA-256과 동일하며 [binding](../reviews/EXP-0018.binding.json)에 연결돼 있다.
- 2026-10-28 16:50 UTC 실제 `http://127.0.0.1:8765/` 브라우저에서 담당 1 → EXP-0018 → 보고서 펼치기, 4개 측정값/2개 그래프, 검토 의견, q04/v01/v03의 5초 영상 재생과 1.5초 seek를 확인했다. 상태 폴링 뒤 영상 노드도 유지됐다. 화면 자료는 2fps 샘플 표시이며 전체 프레임 원본 영상과 다르다.
- API의 보고서·metrics·review·binding 해시와 실제 서비스의 JavaScript 해시를 로컬 checkout과 별도로 대조했다. JS SHA-256은 `cae122f859102f7a6f0dd3255d9e4a7ec5491814f340dc9a4e28fff6ba8b9fcd`다. 새 웹 기능은 없다.
- 로컬 receipt: `runtime/BATCH-0002/input-delivery/browser-r1.json`. 이 기록의 화면 확인은 GitHub 게시 확인을 대신하지 않는다.

## 진행 중 배정 표시

2026-10-28 16:55 UTC 기존 실제 브라우저의 담당 2와 담당 3 카드에 각각 진행 중 상태가 나타남을 확인했다. native projection은 정확한 CV Task/Dispatch와 VLM Task/Dispatch를 live/working으로 연결했다. 이는 에이전트 작업 상태이며 GPU 추론 중이라는 뜻은 아니다. 당시 CV의 두 GPU 작업은 이미 완료됐고 VLM은 가중치 다운로드와 코드 준비 중이었다. 과거 실패 작업도 기존 카드에 함께 표시되므로 카드 전체의 문구를 현재 실험 실패로 해석하지 않는다. 로컬 receipt는 `runtime/BATCH-0002/working-cards-browser.json`, `status-after-cv.json`이다.

## 단계별 GitHub 게시

`3e9a6bb`는 입력 감사 코드/계약, `e0dc11a`는 검토된 입력 감사·신규 모델 선정 문서·RF-DETR 실행 전 소스 고정이다. 정상 HTTPS `git push origin main`으로 `1a06f6c..e0dc11a` 게시를 확인했다. 이 커밋 시점에는 CV 실제 실행 결과와 EXP-0018 완료 등록은 아직 포함되지 않았다. 각 최종 결과의 원격 byte 확인은 해당 결과 등록 후 별도 수행한다.

원본/추출 미디어·배열·raw 예측/응답·weights·환경·DB·raw log·receipt는 로컬 전용이다. `.venv-cv-batch02`와 `.venv-vlm-batch02`도 저장소 ignore에 추가했고, 기존 환경과 이전 실험은 보존했다.
