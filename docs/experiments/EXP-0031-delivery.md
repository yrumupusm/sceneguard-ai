# EXP-0031 전달 확인

2026-10-30. 실험 실행·코드 구현과 기존 서비스의 실제 화면 확인, GitHub 게시는 별도로 확인한다. [결과 보고서](EXP-0031-representative-quality-comparison.md)와 [독립 검토](../reviews/EXP-0031-independent-review.md)의 고정 버전을 사용했다.

## 완료한 실행과 검토

030/007 각1회 CPU 실행·오류/retry0, 새 ReID forward14/47개,25개 테스트를 완료했다. Q01–Q08 상태 불변, 추가 일반 보행자 연결A01은 총괄 시각 초안이며 월장 복원 성능 미충족/기본 적용 보류다. 기존 사용자 영역·기존 결과461파일·큐45jobs/45attempts는 보존했다. Sol high 담당2명과 Astra high 독립 검토의 실제 배정은 기존 Orca Run에 연결했으며 작업 종료 후3개 dispatch를 모두 release했다. 기존 사용자 보유 터미널은 건드리지 않았고 reclaimable0개다.

## 기존 웹에서 실제 확인

주소는 `http://127.0.0.1:8765/`, **담당3 → EXP-0031 대표 크롭 품질 비교**다. 시작 때 실제 진행 중 카드, 완료 후 결과 등록/작업자 완료 상태를 확인했다. 기존 completion CLI로 별도 실험을 등록했고 UI 소스나 웹 기능은 변경하지 않았다.

브라우저 DOM에서 보고서 펼치기, 측정값14개, 집계 그래프2개, 독립 검토 의견, 등록 이미지32개의 실제 디코드를 확인했다. 이미지32개는 기존/새 대표26패널+동시 원본 대조4장+전체 배치1장+A01 연속 확인1장이다. HTTP로 내려받은 모든 등록 이미지의SHA가 로컬 파일과 일치한다. 영상 재생 테스트라고 보고하지 않으며 이미지 로딩 검증은 영상 의미 판독과 별개다.

| 실제 서비스와 독립 검토가 읽은 파일 | SHA256 |
|---|---|
| 결과 보고서 |`9e943f4c1ec31c4344d4b453ffae145170df5c4933124ada2d769382d1fc8d2a`|
| 공개 metrics |`2efdc1c140004632c83beec5a6e07700ab8e4f3e60209b16d43ef88018d018ca`|
| 독립 검토 |`689ffa5a4f6ca903a9249c19f3b24fa18dc475d3c4746134dca178ff6f19cc9a`|
| 완료 binding |`23030fcf76f42269a39bfa4af8d0ffe5d1c2f558accbe80f085f8a28ae64c554`|
| 기존 viewer JavaScript |`cae122f859102f7a6f0dd3255d9e4a7ec5491814f340dc9a4e28fff6ba8b9fcd`|

API의 현재 source hash와 실제 DOM source hash가 위 버전과 일치했고 검토 무결성은current다. 확인 receipt는 로컬 `runtime/EXP-0031/delivery/browser-images.json`이다. 화면이 새로 구현됐다는 설명으로 실제 열기 확인을 대체하지 않았다.

## 로컬 자료

- `outputs/exp0031/review-v1/index.html`: 전체 비교판·원본 문맥·크롭·전처리 재현 이미지.
- `outputs/exp0031/review-v1/risk-audit.html`: 고정 정책의 이전/새 대표 위험 값.
- `outputs/exp0031/coordinator-v1/manual-review.json`: 처음 unknown 양식과 별도로 작성한 Codex 검수 초안.
- `outputs/exp0031/coordinator-v1/A01-continuity.jpg`: 새 일반 보행자 연결의 native PTS 연속 확인.

원본·이미지·특징·tensor·좌표·polygon·가중치·runtime DB와 로그는 로컬 전용이며 Git에 넣지 않는다. 코드·테스트·비식별 문서·공개 집계·기존 카탈로그 배정/완료 기록만 게시 대상으로 확인한다.

## GitHub 게시

실행·코드·보고서·검토·집계·등록 기록15파일은 GitHub main의 `1a0f84fa39c28397d5aa9e12b772db913d8f34de`에 게시했다. 실제 push 성공 후 `ls-remote`로 원격 SHA를 확인했고 fresh fetch의 `origin/main`에서15파일을 모두 읽어 로컬 바이트와 일치시켰다. 별도 GitHub 전달 검증도 보고서·metrics·독립 검토·binding 및 카탈로그/배정의 일치를 통과했다.

이 절의 게시 확인 보충은 후속 문서 커밋으로 반영한다. 보충은 이미 독립 검토·화면 확인된 보고서/측정값/검토/binding 바이트를 바꾸지 않는다. 실제 웹이 읽은 위4개 SHA와 게시된 SHA는 같으며, 기존 viewer JavaScript도 동일하다. 최초 게시 영수증은 로컬 `runtime/EXP-0031/delivery/github-result.json`,15파일의 원격 대조는 `remote-all-files.json`이다.

기능 실행과 자료 제작은 완료했지만 월장 전후 동일인 연결 목표는 미충족이다. 일반 보행자 개선 초안1개를 근거로 기본 구성을 바꾸지 않으며, 이번 한 차례 비교와 전달을 마친 뒤 멈춘다.
