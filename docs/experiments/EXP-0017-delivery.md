# EXP-0017 — 실행·검토·전달 기록

2026-10-29 KST. [결과 보고서](EXP-0017-prompt-evidence-results.md)의 실제 실행과 행동 개선 판정을 구분한다. 실행은 성공, 목표한 행동 개선은 확인되지 않았으며 기본 적용은 보류다. 이전 EXP-0016의 자원 차단 보고서와 등록은 변경하지 않았다.

## 실제 담당 및 실행

기존 Run `run_3d23462a014a`와 canonical GPU queue를 재사용했다. 총괄은 기존 Astra 세션 하나이며 별도 총괄/queue를 만들지 않았다.

| 역할 | 실효 모델 / effort | Task / Dispatch | 결과 |
| --- | --- | --- | --- |
| GPU 실행 | gpt-6.1-sol / high | task_032ba4cbc816 / ctx_65e6cdf6b6f4 | 4개 직렬 job·20개 생성 성공, 오류/OOM/retry 0; 종료/해제 |
| CPU 평가 | gpt-6.1-sol / high | task_92a58bc9727e / ctx_cce6645f155d | 21개 계약 테스트,131개 실제 파일 검증; 종료 뒤 release 응답이 user_takeover/retained로 보존 |
| 독립 검토 | gpt-6-astra / high | task_deaaa68f6feb / ctx_027c0ebf6c1f | PASS: accepted_for_comparison / adoption_on_hold; 종료/해제 |

모델 배정은 launch requested뿐 아니라 effective 필드로 확인했다. release가 user_takeover를 보고한 evaluator 터미널은 강제 종료하지 않았다. 이번 실행·평가 외 기존 사용자 소유 터미널을 건드리지 않았다.

실행 중 실제 브라우저의 담당3 카드는 EXP-0017을 작업 진행 중/결과 미등록으로 표시했다. active queue attempt와 native Task/Dispatch를 함께 기록한 receipt는 로컬 `runtime/EXP-0017/browser-live-card.json`에 있다. 실행 source commit은 `64ab297775d712a18f5149c0fd8f3d8d19dec848`, 23개 실행 source/config는 고정 사양과 동일하다. 정확한 attempts와 명령은 [실행 기록](EXP-0017-execution.md), 소비 파일 해시는 [평가 노트](EXP-0017-evaluation-notes.md)를 따른다.

## 검토와 완료 등록

현재 report SHA256 `03971787b3d7ffffb633f7c7dbcfa92ef497e071f042766cab7ac6c47d5f34b5`, metrics SHA256 `2b78c499bbb055bffa5d1cbe026bf4d894dcc228a4bd987002165cd70fbf07a4`를 독립 검토 대상으로 고정했다. comparison SHA256은 `a4003df7447b70fc591dfabb4251e0704de0b3f53a5ef183b9211c1ded8a9b3c`다. [Astra 독립 검토](../reviews/EXP-0017-independent-review.md)가 해당 고정 byte를 PASS했고 기존 완료 CLI로 담당3에 등록했다. 등록 상태는 succeeded / accepted_for_comparison / adoption_on_hold이며 report/metrics/review integrity는 current다. 이 판정은 행동 성능이나 채택 승인이 아니다.

기존 원본 전용 q02/q03/q04/q05/q06/v01/v03/v04의 5초 클립 8개를 근거 자료로 준비했다. 이는 모델 답변을 시각화한 비교 영상이 아니라 사람이 검수한 원본 참고 입력이다. q04 C 후보 유지도 완료 정확성이나 정상 운영 성공으로 표시하지 않는다. 새 이미지/영상 생성이나 미디어 업로드는 없다.

### 실행 보고서의 공개 경로 정리

총괄이 실행 담당 제출 후 `EXP-0017-execution.md`의 명령 8개를 공개하기 위해 절대 interpreter/runtime 경로를 저장소 상대 경로와 `MVP_QUEUE_RUNTIME`으로 바꾸고 설명 문장을 보완했다. run-index의 원 제출 보고서 SHA `1cdbed452b463254c2c08475ec4fbad4e159d2f48ed1b8b31331bcfb0de6dfd5`는 보존하며 현재 공개 문서 SHA는 `a41e7ca97af43e89d7faf761f7903c9a1bea6aa58e3b373172d9bdda3a4874c9`다. 원 제출 Markdown byte 사본은 별도 보관되지 않아 문서 전체 변경 범위는 총괄 편집 기록에 근거한다. 명령 8개는 경로를 복원한 argv가 원 index의 실행 argv와 모두 같음을 CPU로 검증했다. 실행 소스·원시 결과·run-index·verification·비교 보고서·metrics는 변경하지 않았다. 로컬 provenance receipt에 두 문서 해시와 argv 검증을 남겼다.

## 실제 로컬 화면 확인

기존 주소 http://127.0.0.1:8765/ 에서 2026-10-28 15:25:36 UTC 기준 실제 브라우저 검증이 통과했다. 담당3 카드 → EXP-0017 선택 → 보고서 펼침 → 측정값 14행/그래프 2개 → 검토 표시를 확인했다. 등록 원본 참고 영상 8개 모두 5초 duration, 실제 재생 진행, 1.5초 seek/decode와 polling 후 video node 보존을 확인했다. 화면 기능/디자인은 변경하지 않았다.

서비스 API의 report/metrics/review/binding byte 해시가 현재 등록본과 같고, 제공된 viewer JavaScript SHA `cae122f859102f7a6f0dd3255d9e4a7ec5491814f340dc9a4e28fff6ba8b9fcd`도 저장소와 같았다. 서비스는 기존 저장소/config를 읽으며 재시작 없이 새 등록을 반영했다. review SHA `4dc0de52ea001c7ce9f48b06c9364f842ee0c15cd1bed24b102e709842985482`, binding SHA `afc413f5bcb7e58d5b6295fe4701cb1b9dd04f2af5b84395911bd63bbeb5befa`다. 로컬 receipt는 `runtime/EXP-0017/browser-final.json`; GitHub 검증과 별개다. 카드에 보이는 기존 작업자 실패는 EXP-0016 이력이며 이번 EXP-0017 실행은 성공이다.

## GitHub 및 로컬 전용 파일

사용자의 GitHub 인증 완료 후 정상 HTTPS `git push origin main`이 성공했다. 기존 누적 main을 `64ab297`까지 fast-forward 게시했으며 로컬 작업을 reset/stash/강제 push하지 않았다. EXP-0017 코드/문서/공개 요약 17개 파일을 commit `622e360de27329777a0964dde11c76333acac2ed`로 정상 push했다. fetch 후 `verify_delivery github`에서 원격 main, assignment/catalog와 report/metrics/review/binding byte 해시 일치가 통과했다. 로컬 receipt는 `runtime/EXP-0017/github-result.json`이다. 이 게시 완료 사실을 기록하는 후속 문서 커밋도 정상 push하고 별도 최종 receipt로 원격 HEAD를 확인한다. 바인딩된 report/metrics/review는 변경하지 않는다.

게시 대상은 평가 코드·테스트·문서·공개 가능한 요약/metrics·assignment/catalog/binding이다. 원본/참고 영상·이미지·weights·raw response·processor RGB·raw predictions·artifact manifest·runtime DB/log/receipt·인증정보는 로컬에만 보존한다. 완료 후 추가 GPU 작업/자동 튜닝/웹 확장은 시작하지 않는다.

## 완료 구분

| 항목 | 최종 상태 |
| --- | --- |
| 코드/CPU 검증 | 저장 출력 평가기와 회귀 테스트21개 통과 |
| 실제 GPU 실행 | 기존 queue의4개 job·20개 응답 성공, 오류/OOM/retry0 |
| 행동 평가 | q/v 사용자 라벨 대비 완료; 목표한 개선 확인 실패, 독립 일반화 검증 부족 |
| 독립 검토 | Astra high PASS for comparison; 성능 승인/기본 채택 아님 |
| 기존 웹 등록/실제 화면 | 담당3·보고서·14측정값/2그래프·검토·8원본 참고 영상 재생/seek 확인 |
| GitHub | 정상 HTTPS push와 원격 파일 해시 검증 통과; 미디어/runtime 제외 |
| 적용/후속 | 수정 prompt 기본 적용 보류, 기존 설정도 성능 부족. 추가 작업 자동 예약 없음 |
