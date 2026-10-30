# EXP-0034 전달 확인

2026-10-30. [결과 보고서](EXP-0034-results.md)의 실행 성공과 자동 적용 보류 결론을 기존 결과 화면에 연결했다. 웹 기능·디자인·새 서버를 추가하지 않았다. 원본/크롭/좌표/가중치/원시 응답/로그/DB는 로컬 전용이다.

## 실제 로컬 화면

`http://127.0.0.1:8765/`의 **담당3 → EXP-0034**에서 확인했다. 배정 직후 실제 Orca 진행 중 상태를 먼저 확인했고, 완료 등록 뒤 실제 브라우저에서 보고서·독립 검토·실측값 20개와 그래프 2개를 열었다. 영상 4개 전부 재생 및 seek를 실행하고 자동 폴링 뒤에도 재생 요소가 유지되는 것을 확인했다. 이미지 13개는 실제 디코드/naturalWidth 확인을 통과했다. 이 17개 미디어의 HTTP 응답 바이트와 로컬 해시가 같았다. 검사 시각은 2026-10-30 10:37:52 UTC다.

등록 영상은 다음과 같다. 모든 영상은 표시 시계에 원본 PTS를 남긴다.

- 030 원본/관측/방향·소실·상태 비교: `outputs/exp0034/render030-v2/comparison.mp4` (16초).
- 007 원본/관측/방향·소실·상태 비교: `outputs/exp0034/render007-v2/comparison.mp4` (57초).
- 각 영상의 전체 시야 상세: 같은 디렉터리의 `direction_loss_status.mp4`.

이미지는 6개 실제 외형 비교판, 부분/혼합/가림 3개 실제 processor 판, 기존 영역/별도 가림 주석 2개, 원본 문맥 비교 2개다. 그 외 원본/관측 영상과 검사 이미지는 로컬에 보존했다. 표시용 확대와 원래 모델 입력 크롭은 명확히 구분했다.

실제 서비스의 결과 API/브라우저가 읽은 파일 해시는 독립 검토·등록 파일과 같았다.

| 파일 | SHA-256 |
|---|---|
| 결과 보고서 | `c06d3830796f293313169e4bef3ef6a9a3c698707d2f40e7d6cabd662e038602` |
| 공개 실측값 | `ee77952e5240607eb2b5a963b5ce8338f4ca0cf2a0c9abfb4fbb92cb7a182152` |
| 독립 검토 | `6ee24cbd91b66deef9e516dbdebef8e0472bacedda8816ab506a6605dda41243` |
| 등록 결속 | `32d3eb5bc8c41166c8756bc36c3e12de9b5c8f5de2cf31437f0db8fc63b1b465` |

기존 JS 해시 `cae122f859102f7a6f0dd3255d9e4a7ec5491814f340dc9a4e28fff6ba8b9fcd`도 같았다. 소스만 구현하고 화면 확인을 대신한 것이 아니다. DOM/재생 검사는 영상 의미 검수와 별개이며 후자는 결과 보고서의 총괄 초안이다. 세부 receipt는 로컬 `runtime/EXP-0034/delivery/browser-media.json`에 보존했다.

## 코드·결과 검증과 작업 정리

CPU 관련 77개, MVP 전체 167개, 큐 14개 테스트가 통과했다. 기존 보호 파일 1,132개와 과거 큐 46/46행을 보존하고 새 한 job/attempt만 추가됐다. 기존 catalog/assignment 행은 그대로이며 EXP-0034만 추가했다. 코드·문서·공개 metrics/등록 기록만 명시적으로 스테이징하고 미디어/runtime 경로의 Git 제외를 확인한다.

기존 Orca Run에서 CPU/GPU Sol high 두 담당과 Astra high 독립 검토를 사용했다. 실제 세 dispatch `ctx_0f246793dbf0`, `ctx_93298a31e489`, `ctx_2b702374a616`은 모두 succeeded 후 명시적으로 release했다. 총괄을 새로 만들지 않았고 사용자 보존 터미널은 종료하지 않았다. 후속 GPU 작업·모델·영역/임계값 탐색은 예약하지 않았다.

## GitHub 게시

**결과 커밋 게시와 원격 main 확인 완료:** `d3a0e30866d4759d57d0975bce06bb44841f8729` — Run EXP-0034 disappearance and appearance review with preserved observations.

2026-10-30 10:39:54 UTC, GitHub 원격 main이 이 커밋을 가리킴을 `git ls-remote`로 확인했다. 해당 커밋의 catalog/assignment 및 보고서·실측값·독립 검토·등록 결속 바이트가 현재 로컬과 같았다. 이 네 해시는 앞서 실제 서비스 API/브라우저가 읽은 해시와도 일치한다. 공개 코드·문서·요약 19파일만 게시했고 미디어/runtime/인증 파일은 포함하지 않았다. GitHub 검증 receipt는 로컬 `runtime/EXP-0034/delivery/github-result-commit.json`에 있다.

이 전달 확인 문서 갱신은 별도 후속 문서 커밋으로 게시한다. 검토가 결속된 보고서·metrics·review·binding은 바꾸지 않으며 추가 실행은 없다. **기능 실행/제한된 검수/웹 전달/GitHub 게시 완료, 성능 기준 미충족과 자동 적용 보류**를 구분해 종료한다.
