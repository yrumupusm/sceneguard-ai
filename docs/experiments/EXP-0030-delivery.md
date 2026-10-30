# EXP-0030 전달 확인

2026-10-30. 실험 실행과 결과 전달을 분리한다. main `adaa238`을 fast-forward한 뒤 현행 사용자 영역으로2,190프레임을 CPU1회 처리했다. 새 모델/GPU/영역 수정 전후 비교는 없다.

실효 Sol high 담당2명과 Astra high 독립 검토를 기존 Orca Run으로 연결했다. 영상 담당의 첫 시작은 선택적 Codex 업데이트 안내 때문에 실패했고 안내를 건너뛴 뒤 동일Task를1회 다시 시작했다. 프로그램 업데이트나 권한 우회는 없었다. 실행 중 기존 웹 담당3에 EXP-0030 진행중/결과미등록 표시를 실제 DOM에서 확인했다.

현재 결과 보고서와 집계는 독립 검토 결속 후 고정한다. 실제 영상 검수는 총괄의 로컬 원본/오버레이 표본 검수이며 아래 브라우저 재생 검사는 사람 정체 정답 검증을 대신하지 않는다.

| 확인 항목 | 실제 결과 |
|---|---|
| 실행/테스트 |단일 CPU실행2,190프레임,282.928931초,오류/retry0; 합성36테스트 통과|
| 보존 |소스6·입력170·기존 보호390파일,canonical45jobs/45attempts 정확히 유지|
| 독립 검토 |Astra high 최종 SHA결속,accepted_for_comparison / adoption_on_hold|
| 완료 등록 |EXP-0030 등록,report/metrics/review/binding current|
| 실제 웹 |담당3 완료 등록 확인; 보고서·검토 펼침,26항목·그래프2개 표시|
| 영상 실제 재생 |등록7영상 디코드·0.2초 이상 재생·1.5초seek,16.5초 주기갱신 중 영상 유지 통과|
| 입력 이미지 |등록 Q01–Q08 8장 실제 로딩 완료/원본 크기 확인,HTTP바이트=로컬SHA|
| 실제 서비스 버전 |보고서/metrics/review/binding SHA가 등록·독립 검토본과 동일; 웹기능 변경/서비스 재시작 없음|
| GitHub 게시 |아래 후속 게시 확인에 기록|

브라우저 영상 확인 시각은2026-10-30 13:41 KST다.030 비교16초/480프레임,007 비교57초/1,710프레임이며 sourcePTS와 사후 가용시각을 표시한다. 나머지 등록5영상은 원래선후보3개·현재양측후보1개·007접근참조1개의 원본 구간이다. 전체42개 생성미디어 중 기존뷰어에 필요한7영상과 기존입력8이미지를 등록했고, 나머지는 각 로컬index에서 연다. 실제HTTP로 읽은 등록미디어15개의바이트SHA가로컬과일치한다.

실행 가능한3개 담당은 모두succeeded 뒤released로정리했고,실패한최초시작1개도released다.미정리reclaimable0이며기존사용자보존22개는그대로다.완료된담당의이미닫힌질문에대한reply는dispatch_inactive로거절됐지만,앞서보낸인수메시지와정상worker_done/정리로작업은종결됐다.

기존 `webapp/app.js` SHA는 `cae122f859102f7a6f0dd3255d9e4a7ec5491814f340dc9a4e28fff6ba8b9fcd`로동일하다. 로컬 검증 receipt는 `runtime/EXP-0030/delivery/`에 보관한다. 미디어 재생 검사는 사람 정체나 월장 완료 정답 확인이 아니다.

로컬 핵심 영상:

- `outputs/exp0030/current-v1/track030/evidence/comparison.mp4`
- `outputs/exp0030/current-v1/track007/evidence/comparison.mp4`

각 `evidence/index.html`에서 사건/연결 후보의 근거 원본 클립과 대응 비교 구간을 연다. 전체 시야 비교판, 개별raw/auto 원본 크기 영상, Q01–Q08 입력 패널을 함께 사용한다. 미디어·좌표·특징·영역 설정·weights·runtime DB/로그는 Git 제외이고 코드·문서·비식별 집계만 게시한다. 기존 결과와 검토 결속은 변경하지 않는다.


이미지 추가 검사에서 기존 Orca 탭의 lazy image `decode()` 대기가 runtime timeout을 일으켰고, 제한시간을 둔 후속 확인·reload도 응답하지 않았다. 서비스 HTTP와 Orca runtime은 정상임을 따로 확인했다. 같은 로컬 웹 주소의 새 브라우저 탭에서 EXP-0030을 선택하고, 검증 중 DOM의 이미지 loading만 eager로 지정해8개 모두complete=true/1920×1130을 확인했다. 앱 소스·기능·디자인·서버는 바꾸지 않았다. 실제 이미지 표시 확인은13:46 KST이며 실패한 검사 receipt도 보존했다. 기존7영상 재생 성공 기록과 추가 이미지 확인을 합쳐 기록한다.
