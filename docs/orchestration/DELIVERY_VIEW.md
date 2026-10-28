# 배정·등록 결과 조회

화면은 `records/assignments.json`의 배정과 `records/catalog.json`의 등록 결과를 슬롯별로 읽는다. 배정 파일이 없으면 빈 목록으로 처리하며 잘못된 파일이나 심볼릭 링크는 오류로 표시한다. 배정된 작업에 등록 결과가 없으면 보고서 미등록과 실험 상태 미확인을 표시한다. 같은 슬롯의 등록 결과는 배정과 연결되고 별도 결과도 선택할 수 있다. `synthetic` 자료는 TEST로 표시한다. 기존 미배정 EXP-0001~0007과 원문·측정값·검토 연결 검증은 그대로 유지한다.

Orca 작업 상태는 `/api/status`에서 연결되고 유효 시간 내인 관측에 정확히 일치하는 Run, Task, Dispatch가 하나 있을 때만 표시한다. 누락·중복·불일치·연결 끊김·오래된 관측은 미확인이다. native 단계·생존·종료 결과는 기록된 실험 실행·검토·결정 상태와 별개이며 worker 종료는 GPU 실험 성공을 뜻하지 않는다. 15초마다 카탈로그와 상태를 조회한다. 선택을 유지하고 선택 결과의 카탈로그 항목이 바뀐 경우에만 상세를 새로 읽으며 영상 재생 중에는 일시정지 또는 종료까지 갱신을 미룬다. 이 화면은 읽기 전용이며 작업을 실행하지 않는다.

브라우저 검증용 표식은 `.slot[data-slot]`, 선택 버튼의 `data-id`, `data-slot`, `data-status` (`observed` 또는 `unverified`), `data-result` (`registered` 또는 `pending`)이다. `#detail`에는 `data-id`, `data-result`, 등록 결과에 `data-execution-status`가 있으며 검토 섹션은 `data-section="review"`다. `observed`는 실험 성공이 아닌 정확히 일치하는 최신 native 관측의 존재만 뜻한다.

fixture 검증:

```sh
/home/jhc7484/dev/sceneguard-orca-lab/.venv-orca-lab/bin/python -m unittest tests_orca.test_web -v
node tests_orca/test_cards.js
```

이 검사는 임시 fixture와 순수 상태 선택을 다룬다. 실제 로컬 브라우저에서 카드, 보고서, 그래프, 영상 재생 및 seek 확인은 총괄이 별도로 수행한다. 실제 실험, GPU 실행, GitHub 게시 확인은 이 작업에 포함되지 않는다.
