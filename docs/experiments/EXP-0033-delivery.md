# EXP-0033 전달 확인

2026-10-30. [실제 결과](EXP-0033-results.md)·[독립 검토](../reviews/EXP-0033-independent-review.md)의 고정 버전을 기존 서비스에 등록했다. **실제 실행 완료와 행동 성능 기준 미충족·자동 채택 보류를 구분**한다.

## 실행·독립 검토

기존 Run·canonical GPU 큐에서1job/1attempt·3generate만 수행했다. 새 가중치/모델·학습·ROI/임계값 변경·재시도0.153 MVP/14 queue 테스트와 실제 출력/입력/원본 clip 검사 완료. 보호1,069파일 및 과거45jobs/45attempts 전 필드를 보존했고 최종46/46이다.

기존 총괄 아래 실제 Sol high 실행 담당, Astra high 독립 검토를 사용했다. 완료 등록 형식 보완은 추가 Astra high 작업으로 최종 metadata만 재검토했다. 세 dispatch는 종료 뒤 모두 release했고 활성/회수 대상0개, 과거 사용자 보유22개는 보존했다. GPU 추론을 다시 실행하지 않았다.

## 등록 오류와 해결

최초 completion 호출은 metrics의 JSON 경로 `/timing/...` 등을 절대 로컬 경로로 인식해 **쓰기 전 검증에서 거부**했다. 기존 공개정보 보호 검사를 약화시키지 않고 경로 표기만 `$.timing...` 형식으로 고쳤다. 변환 중 GPU 값의 설명식에 포함된 나눗셈 기호까지 치환된 문제를 독립 검토가 발견해 `bytes / 2^30`을 복원했다.

18개 값·단위·표본 수·측정 범위·원본 SHA·집계식은 이전 검토본과 동일함을 재검증했다. 보고서 바이트는 그대로이고 metrics의 표기 변경과 새 SHA를 독립 검토에 추가한 뒤 등록에 성공했다. 최초 오류는 모델 실행 실패/OOM/retry가 아니다. 인프라 기능 변경도 없다.

## 기존 화면 실제 확인

주소: `http://127.0.0.1:8765/`, **담당3 → EXP-0033 CV 후보 Qwen 3장면 검토**.

시작 때 실제 배정 카드의 진행 중, 종료 후 결과 등록 및 작업자 완료 상태를 확인했다. 기존 completion CLI로 등록했으며 웹 소스는 수정하지 않았다. 실제 브라우저에서 보고서 열기·VLM 판단 요약표·독립 검토·실측18행·그래프2개를 확인했다.

등록된 원본 MP4 3개는1920×1080,10/10/5초다. 각각 실제 재생 시간이 증가하고1.5초 seek가 동작했으며 프레임 디코드가 확인됐다.16.5초 상태 갱신 뒤 선택과 영상 노드도 유지됐다. 실제 모델 입력30장을 담은6개 확인판과 원본 창 끝1개 확인판, 총7개 이미지의 정상 디코드도 확인했다.10개 미디어 모두 HTTP 응답 SHA와 로컬 파일 SHA가 같다.

| 실제 서비스·독립 검토가 연결한 파일 | SHA256 |
|---|---|
| `docs/experiments/EXP-0033-results.md` | `0cdba1cb54746cd051a3545201fc25ff3fb11aaadadfe3d4c8022d962e2aefb7` |
| `records/EXP-0033/metrics.json` | `7dd258034ebe87c93d5d2d1881087b072f220f706e1800ec8fb47aafb13bcc45` |
| `docs/reviews/EXP-0033-independent-review.md` | `456422107868af46b3a7b0c2ca270b70c6cc77db1156db8f05e50d5aea1dd293` |
| `docs/reviews/EXP-0033.binding.json` | `44fe2201961ce6b2db98f2626f362cb4df11e4fd60cef2e02467f72c151a47a0` |

기존 viewer JavaScript SHA는 `cae122f859102f7a6f0dd3255d9e4a7ec5491814f340dc9a4e28fff6ba8b9fcd`로 변경하지 않았다. API와 실제 DOM의 문서 해시도 위 버전과 같고 검토 무결성은current다. 등록 성공 자체를 실제 화면 확인으로 대체하지 않았다.

웹 동작 receipt는 로컬 `runtime/EXP-0033/delivery/browser-media.json`, 시작 카드 확인은 `assignment-browser.json`이다. 이는 실제 렌더/재생 검증이며 행동 정답 검증은 아니다. 총괄의0.5초 순서 원본50장·창 끝3장·실제 입력30장 판독은 보고서에 **시각 초안**으로 한정했다. 새 사용자 확정 라벨이나750프레임 전수 수동 주석을 만들지 않았다.

## 로컬 근거

- `outputs/mvp0001/EXP-0033/6a318ed0ba2c43a7a2e9518c810adbac/index.html`: 세 창의 원본 및 모델 검토 의견.
- 같은 attempt의 `windows/w000001/original_clip.mp4`:030 85–95초.
- `windows/w000002/original_clip.mp4`:007 64–74초.
- `windows/w000003/original_clip.mp4`:007 정상52.5–57.5초.
- `outputs/exp0033/coordinator-v1/`: 실제 입력·원본 PTS 검수판 및 총괄 수기 초안.

원본·이미지·원시 응답·가중치·캐시·runtime DB/로그·인증정보는 로컬 전용이다. 게시 목록은 진단 코드·회귀 테스트·비식별 문서·집계18행·기존 카탈로그 배정/완료 기록뿐이다.

## GitHub 게시

이 문서의 최초 작성 시점에는 게시 전이다. 코드·문서 검토 후 push하고, 원격 main의 커밋 및 실제 서비스와 연결된4개 문서의 바이트를 별도로 대조해 후속 문서 커밋에 기록한다. 위 실제 브라우저 확인을 GitHub push 성공으로 표현하지 않는다.

이번 단발성 비교는 종료했다.030 유효 행동 출력 실패·007 근거 부족·정상 장면 완료 모순으로 자동 판정을 채택하지 않는다. 기존 CV 후보·근거 영상 MVP와 사용자 영역을 유지하며 추가 모델/프롬프트 탐색·학습을 시작하지 않는다.
