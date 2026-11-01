# MVP-0002 독립 통합 검토

2026-11-01. **최종 검토: `accepted_for_comparison` — 제한된 고정 카메라 오프라인 MVP의 실제 통합·기본 기능을 수용한다.** 시간 기반 폴링 중 연속 재생은 미검증이므로 전체 UI 점검이 모두 끝났다는 판정은 아니다. 실제 의심 해제, 미사용 영상의 일반화, 정확도·실시간 성능을 보증하지 않는다. 최신 `CODEX_NEXT_TASK.md`, `CODEX_MVP_FINISH.md`, 사용자가 제공한 `CODEX_MVP_FINALIZE.md`와 `MVP_V1_GUIDE.md`의 범위를 따르며, 아래 동결된 결과·지표 및 별도 웹 전달 근거에 한정한다.

기존 Run `run_3d23462a014a`, Task `task_4c8f7127016a`, Dispatch `ctx_504c7b86791d`의 독립 검토다. 검토자는 이 문서와 `runtime/MVP-0002/review/`만 수정한다. 구현·원본·실제 분석 출력·DB·영수증·기존 실험은 수정하지 않고 실제 영상 분석을 중복 실행하지 않는다. GPU, 하위 작업자, 원본 픽셀 외부 전송, 커밋·외부 게시를 수행하지 않는다.

## 코드와 합성 계약

초기 `mvp_pipeline.py`는 `video_cards`의 검증된 검출과 ByteTrack 초기 분석, 같은 원본의 CPU 점 경로, `RuleBackend`의 방향/문 이력/portal 의심/후속 상태, 사건 유지·종료를 연결한다. EXP 실행 래퍼의 과거 결과 디렉터리를 입력으로 읽지 않는다. `replay_scoped`와 `replay_activity`의 EXP 명칭은 재사용 알고리즘 계약이며, 현재 실행에서 생성한 결과를 전달하는 것과 과거 결과 재생을 구분한다. 최종 판정에 거절한 action event/signals를 투입하지 않는다.

`runtime/MVP-0002/review/contract_audit.py`에서 **모의 backend 없이 실제 RuleBackend**를 사용했다. 실제 영상이 아닌 고정 합성 180프레임의 검출0/후보0 입력은 카드·알림0으로 성공했다. 기본후보0/portal양성 입력은 의심1개·알림1개를 만들고 실제 마지막 문 관측 후3초에 관찰만 닫았으며 확인·해제0을 유지했다. 8개 prefix의 events/timeline/notification intents/activity audit 전체 필드가 전체 실행의 해당 시각까지 출력과 정확히 같았다. 원본 fixture 불변도 확인했다. 기존 연결·모의백엔드 41시험도 통과했다. 이 수치는 소프트웨어 계약 시험이며 CCTV 성능·정확도 표본이 아니다.

초기 감사에서 `replay_activity`가 최종 결과에 물려주는 `flow_calls=0`/`tracker_calls=0` 등이 전체 통합 실행의 CPU 특징/추적 실행량처럼 보일 수 있음을 총괄에 전달했다. 구현 담당은 이를 `rule_stage_calls`로 분리하고 현재 실행의 CPU 이미지 처리 프레임·추적 프레임·경과시간과 재사용을 별도 기록했다. 현재 실행 source 표기도 보완했다. 고정 규칙·구역·문턱값을 바꾸지 않은 수정이며 아래 실제 출력에 반영됐다.

수정 후 연결/실제 RuleBackend 합성46시험과 당시 완료 등록 namespace25시험, 총71시험을 기존 CV 환경에서 독립 실행해 통과했다. 이후 최종 완료 등록26시험을 별도로 다시 실행해 통과했다. `orchestration/complete.py`는 실제 결과 ID에 `MVP-숫자`를 허용하고 `adopted_for_offline_mvp`를 MVP namespace에만 허용하며 기존 synthetic/임의 ID 거부를 유지한다. 서비스 환경에서 별도로 실행한 등록 시험1개는 빈 결과 등록, 기존 등록 보존, 미완료 거부, default 설정 및 hash 변조 거부를 확인했다. 실제 운영 DB/브라우저 증거는 이 임시환경 시험과 구분한다.

## 실제 근거와 완료 범위

007/030은 개발 회귀 구간이다. 기존 사용자 장면 검수를 재사용하며 정밀 사람 ID/인원수/침입 완료 정답으로 확장하지 않는다. 실제 성공 출력은 `outputs/mvp-v1/007-acceptance-v2`, `030-acceptance-v2`, `007-normal84-104-v2`, `007-priorused45-48-v2`다. 첫007시도는 기존 환경에 `lap`이 없어 실패했으며 완료로 계산하지 않는다. 실행 담당의 기존 환경 의존성 보완 후 새 경로에서 성공한v2만 검토했다.

검토자의 `output_audit.py`는 분석/분류 함수를 호출하지 않고 저장 파일을 직접 읽는다. 007/030 전체 **2,190프레임**, 원래38후보, 매 시각 **27,722회 전체 근거 상태 대조**가 통과했다. 반복 상태 대조 수는 독립 사람·사건 정답 표본 수가 아니다. 현재 run의 lifecycle 근거를 activity 사건으로 옮겼을 때 모든 필드가 각 시각에 정확히 보존되며 미래 확인/해제/관찰 종료가 앞서 표시되지 않는다.

EXP49와 비교할 때 전체 raw candidate payload·cards·evidence·timeline·notification intents·activity audit·resolution·routing·원래 확인 시각이 일치했다. 이벤트는 측정된 source payload로 대응시키고 session/event/card/resolution/outcome/notification의 scope 파생 ID만 대응시켰다. 제외한 annotation은 `analysis_run_id`, `computed_in_current_run`, `rule_implementation`, `decision_source` 네 필드다. ID 정렬 때문에 순서가 바뀌는 참조 집합은 정규화하되 모든 상태·시각·측정 근거는 유지했다. 새로 계산한 CPU 경로도 EXP42의 모든2,190프레임에서 `event/signals`를 제외한 **전체 retained 필드**와 일치한다. 과거 출력은 비교 기준으로만 읽었다.

| 실행 | 원본 프레임 | 후보 / 사건 | 첫 의심 | 첫 확인 | 관찰 종료 | 의심/확인 알림 의도 |
|---|---:|---:|---:|---:|---|---:|
|007 48–105초|1,710|18 / 1|55.633333초|72.133333초|74.566667초|1 / 1|
|030 84–100초|480|20 / 1|86.033333초|92.733333초|끝99.966667초에서open|1 / 1|
|007 일반통행84–104초|600|0 / 0|없음|없음|사건 없음|0 / 0|
|007 기술확인45–48초|90|0 / 0|없음|없음|사건 없음|0 / 0|

007의 확인 근거2개/미결16개, 030의 확인3개/미결17개가 보존된다. 03097초대 후속3근거는 같은 확인 사건에 들어가면서 개별 미결로 남는다. 007 후반 일반통행은 새 의심이나 사건 재개가 없다. 실제 박스32,570개와 모든2,880 native PTS/문 polygon 참조를 점검했다. 정상600프레임은007개발 구간과 겹치고 90프레임도 이미 사용한 구간이므로 네 실행을 독립 평가 표본으로 세지 않는다. 새로운 미사용 구간의 일반화 검증은 없다.

## 계산·재사용·출처·지표

네 실행의 검출은 검증된 기존 FCOS 캐시를 사용했고 새 검출 프레임0이다. 현재 입력에서 ByteTrack과 CPU 특징 경로는 총2,880프레임을 새로 계산했다. 최초 실행의 image-paths/decision/media는 모두 신규이고 동일 명령 재실행에서는 모두 재사용되며 detector/tracker/CPU 이미지 처리 프레임은 모두0이다. 등록 재실행의 manifest/cards SHA256은 최초 검토한 출력과 같다. 초기 status snapshot을 따로 보존해 최초 계산 시간을 resume 시간으로 덮어쓰지 않았다.

네 실행의 source/config/code 해시, 24개 stage 영수증과 산출물, manifest/cards/근거 파일 해시를 직접 대조했다. 기존 EXP49 보호파일8개도 원래 hash와 같다. 소스 변경 거부는 실행 담당이 원본 대신 로컬 동일바이트 사본을 변경해 확인한 `source-invalidation-receipt.json`을 검토했고, 검토자가 중복 실행한 것으로 주장하지 않는다. 원본과 완료 stage 변조·다른 요청 재사용을 거부하는 코드 및 관련 회귀 시험을 함께 읽었다. `mvp_pipeline`은 처리 끝에 원본/설정/코드/검출 캐시를 다시 대조하며 부분 실패를 성공 manifest로 게시하지 않는다.

공개 `records/MVP-0002/metrics.json`의75지표를 모두 source SHA256와 source field에 대조했다. 73개 수치와030 관찰 종료 미도달/실제 해제 성능 미평가의2개 null을 구분한다. counts는 원래 후보/카드/알림 목록에서 다시 계산했다. 원본-재생 시계2,880행과 사건별 근거 클립 범위도 확인해 첫 의심/확인/관찰 종료/마지막 문 관측이 클립 밖으로 잘리지 않는지 검사했다. 이 검토는 저장 미디어 manifest/바이트/시계 감사이며 검토자가 영상을 다시 디코딩하거나 실제 브라우저 재생을 했다는 뜻이 아니다. 최초 총 경과시간 약222.768/110.595/103.561/20.855초는 병행 CPU 처리·근거 인코딩을 포함한 각 실행 시간이다. 실시간 추론 FPS나 운영 경보 지연으로 해석하지 않는다.

총괄의 보고서 동결 승인과 실행 담당의 최종 통지 뒤 아래 두 파일을 전체 재독하고 직접 SHA256을 확인했다. `metrics-frozen-audit.json`은75개 source field/hash와 기초 집계·재실행·시계를 다시 대조한 최종 감사다. 초기에 총괄에게 전한79개라는 수동 집계 문구는75개로 정정했으며 자동 감사 기록은 처음부터75개다.

| 동결 대상 | SHA256 |
|---|---|
|[실제 통합 결과](../experiments/MVP-0002-results.md)|`96e41a16e1fa6268671014de681251383bf674c149d8c198b47c054d557886f4`|
|[공개 지표](../../records/MVP-0002/metrics.json)|`cd6cb72f8d839804b7fd7dfe222d07dd44cdc8248ce7d689f14269fd57fd4fb6`|

## 기본 보기와 운영 보존

등록 어댑터는 완료 status/request/manifest/run/cards 해시를 확인하고 기존 Registry lock으로 config를 갱신한다. 기존 동일 등록은 재사용하고 충돌하는 ID는 거부하며, 외부 알림을 비활성화하고 검토 DB를 쓰지 않는다. 첫 감사에서 API의 `default`를 JS가 소비하지 않아 마지막 등록의 빈 결과가 기본이 될 수 있음을 전달했다. 현재 JS는 명시적인 default와 별도 `mvp-source/mvp-view` 저장키를 사용하도록 수정됐다. 실제 media allowlist도 MVP 등록을 허용하는 최소 변경을 확인했다. 새 MVP DOM 시험의 확인/관찰 종료/되감기/빈 결과 표시가 통과했다.

웹 담당의 실제 전달 영수증 `../sceneguard-orca-lab/runtime/orca-lab/mvp0002-web-receipt.json`을 읽고 SHA256 `56f1e7cdbe3ed4153143bbce750b192be604475d3b500007c9f9e25353e27956`에 결속했다. 검토자가 직접 브라우저를 조작한 것으로 주장하지 않는다. 영수증은 새 페이지의007 acceptance 기본 선택,007 재생/seek/확인/관찰 종료/되감기,030 후속 관측의 같은 카드 유지, 정상007 빈 목록/재생, 선택·PTS 새로고침 복원, 명시적인 refresh에서 영상 노드/PTS 보존을 실제 확인했다고 기록한다. API4등록·영상 Range206·기존 수동 검토2개 조회는 별도 API 근거다. 관리되지 않던 기존 listener를 기존 lab 관리 서비스로 옮겼으며 media-route 수정 뒤 서비스 재시작도 기록했다. 새 테스트 수동 검토는 쓰지 않았다.

**시간 기반 폴링 중 연속 재생은 미검증이다.** 두 시도에서 영상이 멈췄고, 별도 시도의 Chromium `AbortError`는 절전용 background video-only media 정지를 보고했다. 이것으로 애플리케이션의 결함 또는 정상 동작을 확정하지 않는다. 명시적 refresh·API·짧은 재생의 성공을 연속 자동 갱신 재생 성공으로 대신 세지 않는다. 총괄은 무제한 재시도를 중단하고 이 항목을 릴리스 제한으로 남겼다.

보존은 영수증의 요약만 믿지 않고 snapshot과 현재 config/DB를 읽기 전용으로 직접 대조했다. 기존63개 incident bundle과416개 artifact 설정은 모든 필드가 같고 새4개씩만 추가돼67/420개다. default는 `mvp-v1-007-acceptance`다. SQLite의 전체 논리 dump hash가 snapshot과 현재에 정확히 같으며 수동 검토2/이력5/알림 claims10을 보존한다. **DB 파일 자체의 SHA256은 서로 다르므로 바이트 동일 보존이라고 주장하지 않는다.** `web-preservation-audit.json`에 논리 hash/파일 hash/집계를 함께 남겼으며 메모 내용은 공개하지 않았다.

실제 바깥 이탈 해제 사례가 없어 **실제 해제 미검증**으로 남기는 것은 허용된 한계다. 무경보 일반 통행이나 관찰 종료를 해제 성공으로 세지 않는다. 최종 수용 범위는 고정 C3/C6·native30fps·로컬 저장 영상의 비실시간 시연이며 정확도·일반화·실시간 운영·법적 판정 보증이 아니다. 원래 필요한 확인 소실·빈 결과 실패·반복 확인 알림·수동 검토 손상·기본 결과 미표시의 차단 결함은 검토한 최종 근거에서 발견하지 않았다. 최종 커밋·원격 게시 확인은 총괄의 별도 전달 작업이며 이 검토가 실행했다고 주장하지 않는다.

검토 도구의 초기 실패도 로컬 로그에 보존했다. 실제 출력이 아직 `analyzing`일 때는 감사가 거부됐고 완료 후 검사를 진행했다.030의 첫 회귀 비교는 scope 파생 `outcome_key`를 매핑하지 않아 실패했으며, 그 식별자만 대응시킨 뒤 전체 필드 비교가 통과했다. 구현이나 실제 출력을 바꿔 통과시키지 않았다. 기존 `MVP-0002-independent-review.md`는 EXP13의 과거 검토임을 총괄이 알려 새 초안을 이 파일로 옮기고 원래 문서는 HEAD 바이트로 복원했다.

기존 로컬 `runtime/MVP-0002/review/final-binding.json`은 아래 편집 전 검토·보고서와 지표·전체 출력 감사·합성 시험·웹 전달 영수증·운영 보존 감사의 정확한 바이트를 결속한다. 이 파일은 그대로 보존하며 현재 공개 경로 정규화본의 결속과 구분한다.


## 공개 경로 정규화 후 결속 검토

2026-11-01. 같은 Run `run_3d23462a014a`의 Task `task_38357eab838b`, Dispatch `ctx_ae04d8281f0d`에서 공개 보고서의 편집 변경만 독립 확인했다. 새 실험·영상 분석·시험·픽셀 검수·코드 변경·커밋·외부 게시는 수행하지 않았다. 기존 완료 CLI의 공개 경로 거부는 출력/코드 실패가 아니며, 이번 확인이 실제 원격 게시 완료를 인증하지 않는다.

편집 전 보고서 `runtime/MVP-0002/report-before-public-path-normalization.md`의 SHA256은 `90d096f06246170bd86317f31e8b91122cff70e11dcd7ad70b2d7e777ef2e7d9`다. 변경은 등록 설정의 절대 경로를 `"$SCENEGUARD_LAB_CONFIG"`로, 서비스 Python 절대 경로를 `../sceneguard-orca-lab/.venv-orca-lab/bin/python`으로, 시간 측정 실행 파일의 절대 경로를 `time`으로 바꾼 세 문자열 각1회뿐이다. 원본 바이트에 이 세 치환을 적용한 결과가 현재 공개 보고서의 전체 바이트와 정확히 같다. 환경 변수는 기존 로컬 설정을 가리켜야 하며 `time -v`는 기존 외부 시간 측정 도구의 경로를 생략한 표기이지 셸 내장 명령으로 새로 측정했다는 뜻이 아니다. 결과·지표·시각·해석·제한의 의미는 변경되지 않았다.

편집 전에 기존 검토를 `runtime/MVP-0002/review-before-publication-normalization.md`로 바이트 그대로 보존했고 SHA256 `be4605176953d48ffe5e4c6081b5e867cf617f6eef9ed66823615eb7ad022289`를 확인했다. 위 동결 표는 정규화된 새 보고서 SHA256에 결속한다. 공개 지표의 SHA256 `cd6cb72f8d839804b7fd7dfe222d07dd44cdc8248ce7d689f14269fd57fd4fb6`는 기존과 동일하다. 검토 본문의 웹 전달 영수증 절대 경로도 서비스의 상대 경로 `../sceneguard-orca-lab/runtime/orca-lab/mvp0002-web-receipt.json`으로 정규화했고 실제 영수증 SHA256 `56f1e7cdbe3ed4153143bbce750b192be604475d3b500007c9f9e25353e27956`가 그대로임을 확인했다. 현재 보고서와 수정한 검토의 전체 문자열 각각에 `orchestration.complete.public`을 직접 적용해 모두 통과했다. 이 검사는 공개 payload 필터이며 실제 등록·원격 게시·브라우저 검증을 대체하지 않는다.

최종 판정은 기존과 같은 `accepted_for_comparison`이며 **제한된 고정 카메라 오프라인 MVP**에 한정한다. **시간 기반 폴링 중 연속 재생과 실제 바깥 이탈 의심 해제는 미검증**으로 유지한다. 현재 검토·새 보고서·변경 없는 지표 및 두 편집 전 문서의 정확한 해시는 별도 로컬 `runtime/MVP-0002/review/publication-normalization-binding.json`에 기록하며 기존 `final-binding.json`을 덮어쓰지 않는다.
