# EXP-0038 전달 확인

2026-10-31. [실제 결과](EXP-0038-results.md)와 [독립 검토](../reviews/EXP-0038-independent-review.md)를 별도 결속했다. **8B NF4 실제 실행 완료 / 원문 형식 개선 / 혼합·가림 외형 품질 충분하지 않음 / 기본 적용 보류.** 기존 MVP·사용자 영역·추적·의심·카드·검토 저장·환경을 유지하고 추가 실험 없이 종료한다.

## 기존 화면과 자료

기존 **http://127.0.0.1:8765/ → 담당3 → EXP-0038**을 사용한다. 원본 맥락6개와 원본 크롭/실제2B/실제8B 입력·응답 비교판6개다. P2의 불확실한 하의, P5의 복수 인물 혼합, P6 가림 유보와 P3/P4 구분 손실을 함께 보여준다. 미디어는 로컬 서비스에서만 제공하며 raw 응답·전체 원본·가중치를 외부에 게시하지 않는다.

담당 카드 최초 배정은 CPU 준비 `task_5e783fa73799` 이력이다. immutable 배정 계약을 변경하지 않았다. 실제 GPU 실행은 활성 Sol high `task_144932ec63a8`/`ctx_95618a8e831d`, 별도 Astra high 검토는 `task_cae376586829`/`ctx_8abdfb34093e`다. 큐/Orca 실행 상태와 기존 카드의 CPU 배정 표시를 구분하며, 새 GPU 작업자가 실행 중 카드에 표시됐다고 주장하지 않는다. 완료 결과는 기존 카드에서 조회한다. 웹 기능·디자인 변경이나 새 서버는 없다.

기능 실행 성공·수치 감사·기존 검수 초안 기반 의미 분석·새 사람 정답의 부재를 구분한다. 이미지 디코드/DOM 확인은 새로운 사람 동일성 판정을 대신하지 않는다. 새 라벨 제작이나 원본 클라우드 전송은 하지 않았다.

## 로컬 기록과 보존

새 출력은 `outputs/mvp0001/EXP-0038/2045864aebe541f6bda49875a03efc6e/`, 새 비교판은 `outputs/exp0038/comparison-v1/`, 원본 맥락은 `outputs/exp0034/pairs-v1/`다. 모든 원시 응답·processor arrays·체크포인트·로그·DB·receipt는 로컬 전용이다. 보호3174파일·기존48jobs/attempts·실행소스29파일이 보존됐고 job/attempt각1개만 추가했다. 과거36개 catalog 결과와 webapp6파일도 변경 없이 보존한다.

기존 환경/코드 검사 이후 CPU 후처리의 첫 셸 호출은 system Python 별칭 부재, 이미지 디코드 확인은 system Python의 Pillow 부재로 종료됐다. 각각 기존 python3/기존 CV 가상환경으로 수정해 처리했으며 설치·환경 변경·GPU 재실행은 없었다. 추론 자체는 첫 시도 성공, OOM/retry0이다.

화면 검사 도중 과거 browser page ID가 현재 tab list에서 사라져 이미지 decode 명령이55초 만에 timeout됐다. 현재 tab list의 기존 SceneGuard 페이지로만 검증 대상을 바꿨다. 첫 검증 receipt를 보존하며 실제 모델·웹 기능·서비스는 변경하지 않았다. 검증 스크립트의 저장소 import 경로는 `PYTHONPATH=.`로 지정했다.

## 실제 확인 범위와 남은 제한

기존 완료 CLI 등록 후 실제 브라우저에서 담당3 EXP-0038의 보고서 펼치기, 측정29행(실측28/null1), 실측 그래프2개, 독립 검토, 원문 해시와16.5초 폴링 이후 상태를 확인했다. 등록 원본/비교 이미지12개는 로컬 JPEG 디코드 및 서비스 HTTP 바이트 SHA가 모두 일치했다. 서비스 JS/CSS/HTML도 현재 로컬·게시 main과 같고 서버 재시작이나 기능 수정은 없었다.

**이미지12개의 실제 브라우저 디코드 완료 확인은 미완료다.** 기존 페이지 ID 변경 후 현재 tab list의 페이지로 재지정했으나 `img.decode()` 검사도55초 timeout됐고, 단순 DOM 조회도 Orca `runtime_timeout`으로 끝났다. 보고서·그래프 확인은 성공한 별도 receipt에 근거한다. HTTP200/파일 디코드를 실제 이미지 화면 확인으로 대체하지 않는다. 미디어 파일 결함인지 Orca 페이지 통신 문제인지 확정하지 않으며 웹 기능이나 모델을 변경해 우회하지 않았다. 추가 추론은 필요 없다. 사용자는 기존 담당3 카드의 P1–P6 이미지에서 확인할 수 있도록 등록돼 있다.

실제 화면·해시 영수증은 `runtime/EXP-0038/delivery/browser-media.json`, `local-image-validation.json`, `browser-page-transition.json`, `image-display-blocked.json`이다. 최초 페이지 영수증도 보존했다. 이번 새 실행·검토 작업자는 모두 종료·해제했고 reclaimable0, 기존 retained22개는 유지한다.

| 검토된 원문 | SHA256 |
|---|---|
|`docs/experiments/EXP-0038-results.md`|`216dccffbc2fbeb0e2794dcd6a23b927fe1ac2874a0b7ac5b75a78be77ce655f`|
|`records/EXP-0038/metrics.json`|`0693e641d56b9791475d2999e0bab4b071b8bee2e98585c2e420b3b7a4eef291`|
|`docs/reviews/EXP-0038-independent-review.md`|`9683411d13c5a012bb81aff277d9828d82745d4b2e86621bd0ffc9013d9c73e3`|
|`docs/reviews/EXP-0038.binding.json`|`7788688f2da992f0bca6a058f56f622f750acccfeebd6b71b0e68aa23c16dc03`|

코드 준비는 기존 `eb6e6fb`에 게시돼 있다. 이번 결과·검토·측정값·등록 문서를 명시적으로 스테이징하며, GitHub 최종 게시 확인은 아래 후속 기록에 남긴다.

## GitHub 게시 확인

결과·검토·측정·등록 커밋 `3071a7dd23013a07bc3fc664426b58e75af758be`를 origin/main에 푸시했고 완료 검증 CLI로 원격 커밋과 보고서/측정/독립 검토/결속4파일 바이트 일치를 확인했다(`github-result-commit.json`, passed). 실제 서비스 JS/CSS/HTML과 EXP-0038 API의 검토 결속도 게시 커밋 및 로컬과 일치했다(`posted-service-version.json`). 웹 기능은 변경하지 않았다. 이는 위에 명시한 이미지 DOM 확인 미완료를 해소한 것으로 주장하지 않는다. 이 게시 확인 문단은 별도 문서 커밋으로 남긴다.
