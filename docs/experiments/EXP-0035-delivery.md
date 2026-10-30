# EXP-0035 결과 전달 확인

실험 적용과 전달 검증을 구분한다. [실제 결과](EXP-0035-results.md)는 기존 관측에 대한 CPU 조건 완화 비교다. 이번에는 기존 CV/VLM 기본 구성이나 웹 기능을 변경하지 않았다.

- 기존 Run `run_3d23462a014a`의 Sol high 담당: task `task_dc6d3f8432b9`, dispatch `ctx_0cef69d9c18e`. Orca 요청/실효 모델 모두 `gpt-6.1-sol`, effort high.
- Astra high 독립 검토: task `task_c9d666160c47`, dispatch `ctx_6b1b16edbd69`. 요청/실효 모델 모두 `gpt-6-astra`, effort high. 별도 총괄/큐를 만들지 않았다.
- 담당3에 실제 배정을 등록했고 실행 중 기존 화면에서 `EXP-0035 · 결과 미등록 · 진행 중` 표시를 확인했다. 종료/결과 등록/채택은 서로 다른 상태다.
- 실제 적용007/030 각1회.107 관련 테스트 통과, data34/MVP167/VLM8 추가 환경 검증 통과. 다른 전체 테스트의 환경 의존성·과거 이력 fixture 문제는 원 보고서와 로그에 남긴다.
- 영상 원본/관측/새 상태 렌더는007163.429499초,03048.686450초. 후속 원본/기존/변경 후 나란히 배치는007129.481750초,03035.435698초다. 제작 비용이며 모델 추론 속도나 실제 경보 지연이 아니다.

## 실제 자료

|자료|로컬 경로|기간|
|---|---|---|
|007 원본 / 기존 / 완화|`outputs/exp0035/compare007-v1.mp4`|57초, 원본48–104.967초|
|030 원본 / 기존 / 완화|`outputs/exp0035/compare030-v1.mp4`|16초, 원본84–99.967초|
|007 새 상태 전체 시야|`outputs/exp0035/render007-v1/direction_loss_status.mp4`|57초|
|030 새 상태 전체 시야|`outputs/exp0035/render030-v1/direction_loss_status.mp4`|16초|
|추가14후보의 원본/실제 박스 비교판|`outputs/exp0035/root-v1/`|마지막 관측/논리 판단 PTS 각각 표시|

비교 영상은1920×1000,H264/yuv420p,0071,710프레임/030480프레임이다. 세 패널의 원본 native PTS/RGB 해시 지도와 재생 PTS를 대조했고 기존 source map과 정확히 같다. 화면의 글자 폭은 실제 폰트로 측정해 각 열 내부임을 확인했다. 개별 새 상태 영상은1920×1152로 전체 시야를 유지하고 별도 footer에 시간을 표시한다. 과거 EXP-0034 영상/결과는 덮어쓰지 않았다.

등록 자료는 비교/상태 영상4개·추가 후보 이미지14개다. 이미지의 사람 정체·실제 완료 여부를 새로 확정한 것이 아니며 기존 사용자 관찰/검수 초안과 현재 수치 결과를 구분한다. 클라우드 작업자에게 원본 영상을 자동 전송하지 않았다. 공식 라벨·원본·이미지·결과 JSON·scene·runtime DB·로그는 GitHub에서 제외한다.

이미 생성한 비교 영상을 덮어쓰거나 재실험하지 않는다. 표시용 재현 인터페이스는 다음과 같다.

```bash
.venv/bin/python -m sceneguard.exp0035_evidence --key 007 --output outputs/exp0035/compare007-v1.mp4
.venv/bin/python -m sceneguard.exp0035_evidence --key 030 --output outputs/exp0035/compare030-v1.mp4
```

새 경로만 허용하며 입력/기존 렌더/결과 해시가 다르면 거부한다. 실행한 원래 명령/시간/해시는 로컬 receipt에 남는다.

## 웹과 GitHub

기존 화면은 `http://127.0.0.1:8765/`의 담당3 → EXP-0035다. 실제 등록과 브라우저 재생은 아래처럼 확인했다. GitHub 게시도 별도 검증을 완료했다.

등록 CLI는 실제 EXP-0035를 새 행으로 추가했고 이전 catalog/assignment 행은 그대로다. 기존 브라우저에서 담당3 선택→EXP-0035 선택→보고서 펼치기·측정표13행·그래프2개·검토 의견 표시를 확인했다. 등록 영상4개가 실제 디코드·재생 진행·seek를 통과했고 자동 갱신 뒤에도 유지됐다. 이미지14개도 실제 디코드됐으며18개 artifact의 HTTP 바이트와 로컬 파일 SHA-256이 모두 같았다. 기존 웹 JavaScript 해시도 그대로여서 웹 기능 추가는 없다.

실제 서비스 API/DOM이 읽은 검토본은 다음과 같다.

|파일|SHA-256|
|---|---|
|`docs/experiments/EXP-0035-results.md`|`b611739f36c54994ecdebf9abbe11562b964119a370407904466349b8f791869`|
|`records/EXP-0035/metrics.json`|`610d158ac1fd702f9737fedee7aef06cf055412329cb5df094302f8eefd7b5a1`|
|`docs/reviews/EXP-0035-independent-review.md`|`2d6c8add8d2b44e8279b108e8cf97711c871a2c2a7faf6cd3099297e7fafd424`|
|`docs/reviews/EXP-0035.binding.json`|`bc581e2c10b0c1d5a5e84bd32cf3a5a0e7e1e91c67cd4d6dc905e19e1dc77146`|

위 확인은 영상 의미의 새 사람 정답이나 정확도 인증이 아니다. 새 상태 생성과 원본 PTS 결속, 브라우저 전달 기능을 확인한 것이다. 영상 의미는 기존 사용자 관찰/EXP-0034 초안을 재사용하고 새 의심의 정체/완료는 미확정으로 남긴다.

실제 receipts는 `runtime/EXP-0035/delivery/browser-media.json`과 하위 browser 명령 기록에 있다. 두 작업자는 완료 뒤 release했고 Run에는 이번 작업의 미정리 worker가 없다. 기존 retained 작업자22개는 건드리지 않았다. 보호1,358파일과 GPU47jobs/47attempts 보존을 독립 확인했다.

결과 커밋 **`973874b6d1b9819122a28918c1a98dd1c8112f31`**을 GitHub main에 푸시하고 `git ls-remote`의 원격 main 일치를 확인했다. `verify_delivery github`가 catalog/assignment 및 보고서·metrics·독립 검토·binding의 게시 바이트를 로컬과 대조해 통과했다. 실제 브라우저/API가 읽은 위 네 해시와 원격 게시본도 같다. 확인 시각은2026-10-30 11:46:07 UTC이며 receipt는 `runtime/EXP-0035/delivery/github-result-commit.json`이다.

이 전달 확인 문서는 후속 문서 커밋으로 게시한다. 검토 결속된 보고서·metrics·독립 검토·binding은 변경하지 않는다. 최종 푸시 뒤 같은 네 파일과 원격 main을 다시 확인하며 receipt는 `github-final-commit.json`에 로컬 보관한다. 원본·영상·이미지·관측·가중치·인증·runtime/원시 로그는 커밋에서 제외했다. 새로 게시한16파일은 코드·테스트·문서·공개 집계/등록 기록뿐이다.

**기능 실행·기존 화면 전달·GitHub 게시 확인 완료 / 가림 후보 확대와 접근 오탐 증가 확인 / 침입 판별 성능 충족 미확인 / 기본 적용 보류.** 승인된 비교를 종료했고 추가 실행은 하지 않는다.
