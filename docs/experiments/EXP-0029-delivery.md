# EXP-0029 전달 확인

2026-10-30. 실제 실행과 결과 전달을 별도로 기록한다. 결과 보고서·측정값·독립 검토의 검토 결속 뒤에는 해당 원문을 바꾸지 않는다.

| 항목 | 상태 / 근거 |
|---|---|
| main 반영 | `e5cd1ab` fast-forward, 시작 시 로컬 tracked 변경 없음 |
| 실제 담당 | 기존 Run, Sol high 캐시 확장·연결 담당2명과 Astra high 독립 검토1명; launch effective 확인 |
| 실행 중 실제 화면 | slot3/EXP-0029 선택, 결과미등록·Orca진행중·실효Sol/high DOM 확인 |
| 실제 실행 |030480+0071,710프레임, 신규GPU1,110샘플/1job1attempt, 오류/retry0 |
| 기존 자료 |보호82파일·과거44jobs/44attempts와 기존600캐시/추적prefix 보존 |
| 기술 검증 |tracklet43개·extension10개·canonicalqueue14개 통과; 별도 합산29개 회귀의 과거fixture1실패 기록 |
| 행동 결론 |전후동일인물복원 개선미확인·기본적용보류; 같은영역후보양쪽0을성공으로세지않음 |
| 완료 등록 / 실제 재생 |EXP-0029 등록·review current; 실제 브라우저에서 보고서/검토 펼침·32측정항목·그래프2개·4영상 재생/1.5초 seek·16.5초 주기갱신 중 영상 유지 통과 |
| GitHub 게시 / 서비스 버전 |게시 후 별도 확인 예정 |

로컬 영상은 `outputs/exp0029/track030/v1/` 및 `outputs/exp0029/track007/v1/`의 `original_raw_linked.mp4`와 `original_raw_linked_focus.mp4`다. 전체판이 후기 인물을 포함한 원본 전체 시야를 보존한다. 확대판의 표시 범위를 분석 ROI나 모든 인물의 가시성 보장으로 해석하지 않는다.

기존 결과 화면 `http://127.0.0.1:8765/`의 담당3에서 EXP-0029를 선택한다. 웹 기능과디자인·app.js는 변경하지 않았으며 모델기본값교체·자동후속실험은 없다. 원본·이미지·영상·원시좌표·특징·가중치·runtime DB/로그는 Git 제외이고 코드·문서·비식별집계만 게시한다.

실제 브라우저 검증 시각은2026-10-30 03:38 KST다.030영상2개는16초/480프레임,007영상2개는57초/1,710프레임이며 H264/yuv420p다. 실제 HTTP로 읽은4개 미디어바이트SHA가로컬파일과같고,서비스가읽는보고서/metrics/review/binding SHA도등록본과같았다. 렌더표본의원본PTS90초/70초를총괄이별도로확인했다. DOM재생검증이사람정체정답검증을대신하지않는다.

초기 브라우저 검증 helper를직접파일명으로실행했을때는repository import경로누락으로중단됐고,기존runpy호출로복구했다. 모델/GPU재실행은없었다. viewer app.js SHA `cae122f859102f7a6f0dd3255d9e4a7ec5491814f340dc9a4e28fff6ba8b9fcd`는작업전과같다.

게시 전검사에서새runner의EOF여분빈줄1개만제거했다. 실행문장은동일하며실제실행바이트는 `runtime/EXP-0029/runner.executed.py`, 전후SHA는 `packaging-whitespace.json`에보존했다. 이포장정리는실행후이므로과거sourcefreeze/실행receipt를최신코드SHA로덮어쓰지않았다.
