# BATCH-0006 전달 기록

2026-10-29. [고정 계획](BATCH-0006-c6-pose-960-resolution-plan.md)에 따른 EXP-0025다. 시작106ddf9의clean상태를 확인하고 사용자48372d4까지fast-forward했다. reset/stash/강제덮어쓰기 없이 기존코드·보고·640결과와41jobs/41attempts 보존기준을 로컬에 저장했다.

기존 Run run_3d23462a014a에서 담당 task_259c3da684ec/ctx_4941141147c8의 실효gpt-6.1-sol/high, 독립검토 task_9b776021b42c/ctx_56a299ea3db5의 실효gpt-6-astra/high를 native launch/live provider로 확인했다. 총괄·canonical단일GPU큐를 재사용하고 새 총괄·큐를 만들지 않았다. 기존 담당3 카드에 EXP-0025가진행중이며 실효Sol/high인 것을 실제브라우저에서 확인했다.

초기GPU여유8231MiB를 관찰했고 실제실행직전6144MiB게이트를 다시확인한다. 공개YOLO.predict kwargs22개 중imgsz만960으로 바꾼다. 기존batch04계측기의640고정검사를 발견해 과거소스는그대로두고 새경로에서960입력을검증한다. 동일PTS·RGB·C6crop·checkpoint·환경과640cached3개의 해시를 확인하고 CPU계약·sourcecommit·독립preflight PASS후에만 신규3회를 실행한다.

모델출력수와실제사람·관절대응은 별도판단이다. 기존사용자검수는EXP-0024에보존하고 새960결과는 이미지3장을 통한검수없이는 개선확정하지않는다. 미디어·raw좌표·tensor·weights·runtime/DB/receipt는로컬만보관하며 기존웹UI를 확장하지않는다.

## 실행 전 고정과 검토

코드/합성테스트/최소공개manifest/배정을 ecc8a55a68b806c7876b480b52a9b69b3e3aa85f에 commit/push했다. 실행의존33파일의현재bytes·Git객체·readiness를대조했다. source digest fae3a85787a5df77003a8075e40ac89ae892309d8faeda838000dfc27fedc8dc, input contract3642344b244ed1d82c664b7c3812a3ee1b771b4e479e9de66fc79f77e90b90de다. 신규CPU계약11개+기존큐회귀14개,독립합성6개가통과했다. 중복검사를별도성능수치로합산하지않는다.

Git diff검사에서새observer파일의EOF빈줄1개를제거하고소스해시를다시고정했다. 실행코드의동작변경/추론오류/retry는아니다. 독립exact-source PASS후총괄이여유8163MiB와커밋/입력/소스/역할을확인하고기존큐의90→84→94초C6960세조건만실행허가했다. 기존640캐시나baseline파일은수정하지않았다.

## 실제 실행과 사용자 검수

신규 job `a5cc40358de84429bcf75c4e0a0d61fd` / attempt `dbc34eb78e324d79a725925f48f4783c`는 succeeded다. 90→84→94초 새960 sample3회, model load1회, 별도 warmup1회, 오류/OOM/retry0이다. 기존640 native Results3개는 읽기 전용 재사용했고 재추론0회다. 실제 child 여유8172MiB와 CUDA0 FP32 1×3×960×960 입력을 확인했다. summary SHA256은 `e1b2c56fa82aa77b3b7b27946a5434b865c7c3f8b882b07680f9f41787e5d994`다.

신규 박스/retained 관절 추정은84초3/37,90초0/0,94초1/11이다. 기존640은3/38,1/12,0/0으로 보존했다. 새 triptych3장의 사용자 검수를 한 번 묶어 받았다. 84초는 잘 되고,90초는 이전과 같은 수준이라는 정성 평가이며,94초는 문 위 사람이 생각보다 잘 잡혔지만 이미 넘어간 사람은 누락됐다는 관찰이다. 90초의 정성 평가와 실제1→0개 출력 차이는 별도로 기록했다. 개별 관절 GT나 행동 성능으로 확대하지 않았고 같은 자료를 다시 검수 요청하지 않았다.

담당 CPU 집계와 독립 감사는 기존41jobs/41attempts·보호된129과거파일·고정33실행파일의 보존을 확인했다. 현재42jobs/42attempts이며 이번 새1건 이외 과거 큐 row를 바꾸지 않았다. 새 결과·원시 좌표·tensor·이미지·receipt는 로컬 보관한다. 기술 실행 완료와94초 한 사람의 제한된 개선은 인정하되90초 미해결·94초 반대편 누락 때문에 기본 적용은 보류한다.

## 독립 검토와 완료 등록

Astra high는 신규3회/캐시3개/별도warmup1회,47개metric의 현재 source hash/pointer와실측,33실행파일·129과거파일·41과거jobs/attempts 보존을 확인했다. 사용자 검수의 제한된84·94양호 및90·94누락 해석까지 포함한 최종 PASS다. 정밀관절/행동성능 PASS는 아니다.

검토 report SHA `80ee4f04a8569f6121864496b1d683c7dcef650fb929943d3fce506f2f6ed0ab`, metrics `7eaa71f84d54d6b4bcd5f06bd997a465f9e74756d9df3754359a8dc3326db7f5`, 총괄 요약 `36466ce9d9abde75cbb6d9126b208738248b866ad7b52fd24efd28c4555e38cd`를 고정했다. review SHA는 `b68d1b21e9bc185bb891c5cddc1e74dec1313ab3c678eb98346112a8c29dddba`, 완료binding SHA는 `47b779444ff920e334738ca9874aa5d264f20b5bda8297da1c2535b6db5362dd`다. 이들 검토파일은 등록 후 수정하지 않는다.

기존 complete 명령으로 담당3 EXP-0025를 succeeded / accepted_for_comparison / adoption_on_hold로 등록했다. catalog의 과거24개 결과는 그대로이며 이번 결과가25번째다. 두 작업자 모두 정확한 Task/Dispatch로 succeeded worker_done을 제출했고 총괄이 수용 후 각각worker-release했다. 종료대기 reclaimable0이며 기존 사용자소유 작업자는 변경하지 않았다. canonical 큐는38succeeded/4failed,queued/running0이고 과거4failed를 이번실패로 세지 않는다.

## 실제 기존 화면 확인

2026-10-29 07:03 UTC, 기존 http://127.0.0.1:8765/의 담당3에서 EXP-0025를 선택해 보고서·47측정값·그래프2개·독립 검토와 세 비교이미지의 실제 DOM 표시/펼침을 확인했다. 84초는5760×1344,90/94초는5760×1288로 decode/render되며15초목록polling 이후에도 같은 이미지요소가 유지된다. HTTP 이미지bytes도 로컬SHA와같다. 서비스가 읽는report/metrics/review/binding은 위검토bytes와같고 기존JS SHA cae122f859102f7a6f0dd3255d9e4a7ec5491814f340dc9a4e28fff6ba8b9fcd를유지한다. 웹기능변경/서비스재시작은없다.

완료된담당3의진행중표시는해제됐고 이번결과는succeeded다. 카드에같이보이는과거작업자실패는보존된다른실험이력이다. 정지이미지실험이므로영상재생/seek는해당없음이며공통검사기의빈video배열을재생통과근거로사용하지않는다. 화면표시검사와사용자관절검수도별개다. 실제receipt는로컬 runtime/BATCH-0006/delivery/browser-images.json에보관한다.

| artifact ID | 이미지 SHA256 |
| --- | --- |
| `exp0025-030-084-resolution-comparison` | `6e102474f33e3dd29a31fb5e2d1eb20888fe608c23be045298b17f40c51ee0f1` |
| `exp0025-030-090-resolution-comparison` | `7efcf7786c80079c932ab1a59b922f5f68f92018691f7964d755e8cc68e79dcb` |
| `exp0025-030-094-resolution-comparison` | `89ec86df5932ea988503ca930b0c0a58833edee4a7ee6819b790b01cf4b5839d` |
