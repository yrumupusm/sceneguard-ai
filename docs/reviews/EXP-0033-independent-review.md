# EXP-0033 독립 검토

2026-10-30. **사전·실제 실행·최종 보고서 수치 및 출처 검토 완료 / 자동 판정 채택 보류.** 생성 성공과 행동 판단 충족은 별개다. 아래 사전 검토 문단의 대기 항목은 당시 상태이며 실제 결과는 후반에 분리 기록한다. 검토자는 추론·가중치 다운로드·코드 변경·독립 시각 정답 확정을 수행하지 않았다.

## 사전 검토

- 최신 계약은 `docs/CODEX_EXP0033.md`이다. 기존 후보030 90.4초와007 70.133333초, 독립 정상 대조007 52.5–57.5초의 고정3창이며 정상 대조는 CV 후보가 아니다.
- 원본2개 SHA, 기존 gap 이벤트의 영상/조건/raw ID/출력 시각/유일성을 CPU에서 직접 확인했다. 세 창은 각각10개의 서로 다른 실제 native PTS 프레임을 반환했다.030은85–94초/1초 간격,007 후보64–73초/1초 간격, 정상 대조52.5–57초/0.5초 간격이다. 원본 display FPS는 모두30이다.
- 기존 Qwen revision `89644892e4d85e24eaac8bacfd4f463576704203`의 로컬 metadata와 weight SHA `7de1838c87a5349b016c26a1c3f7d2bc400a3d485f95ef39a7059ffd734977a0`를 대조했다. 고정 C6/C3 ROI와 기존 greedy/BF16/SDPA/384-token 설정을 유지한다.
- 텍스트 입력은 익명 창 번호와 같은 행동 질문이다. CV 이벤트·raw ID·파일명·사람 관찰 정답·과거 모델 답변은 모델 텍스트 경로에 없다. 참조 JSON의 실제 읽기는 별도 posthoc 함수 안에 있고 모델 source/input contract에는 포함되지 않는다.
- 공식 processor는 native PTS에서 창 시작을 뺀 시간에 원본 FPS를 곱한 좌표를 사용하며, 추가 sampling을 끈다. 공식 시간쌍 평균/0.1초 caption 반올림은 원본 PTS와 구분한다. 실제 resize·padding·expanded prompt는 실행 담당의 CPU freeze 및 실제 결과와 추가 대조할 예정이다.
- canonical 큐의 실제 lock inode/상속 flock/살아 있는 parent/attempt 상태와 source/input/config 해시 검증이 모델 생성 전에 있다. 다만 candidate phase 자체는 기존 Run 및 현재 Orca Task/Dispatch를 강제하지 않으므로 실행 전 실제 배정 기록을 별도로 검증해야 한다. 공통 큐의 일반 retry 기능과 이번 실험의 무재시도 한도도 구분해야 한다.
- 독립 CPU 계약 테스트12개가 통과했다. 실원본 CPU 확인 과정에는 torch를 import하지 않았다. 확인 당시 기존 큐는45 jobs/45 attempts였고 전체 행 사본을 로컬에 보존했다.

## 로컬 근거와 남은 검토

`runtime/EXP-0033/independent-preflight.json`은 source/input/config 해시, 모델 파일 해시, 실제 프레임 및 후보 출처, 기존 큐 행을 보존한다. `independent-tests.txt`는12개 테스트 결과이다. 원본·좌표·raw 응답은 이 문서에 복제하지 않는다.

실행 담당의 최종 freeze, 총괄의 보호 파일 snapshot, 실제 신규1 job/1 attempt,3개 raw/parse 결과와 근거 MP4 metadata, 비용, 최종 결과 문서/metrics의 정확한 SHA는 아직 검토 대상이다. 총괄의 원본 시각 초안과 사용자 관찰은 별도 출처로 다루며 독립 의미 정답으로 인증하지 않는다. 이3개 개발 사례로 일반 정확도·F1·전체 사건 recall·실시간 성능·완료/법적 무단침입을 확정할 수 없다.

## 최종 사전 판정

**고정1회 실행에 GO.** 실행 직전 현재 Orca 배정 재확인과 실제6144MiB 자원 gate를 그대로 통과해야 한다. 총괄의 실행 지시를 대체하거나 추가 실행/재시도를 허용하는 판정은 아니다.

실행 freeze SHA는 `7cb6f5c0b34977f66662f8c263e93db7490bea47d6138c6587640be0972672a0`, source hash는 `bf4d744992165c18df9e8ed7ea3ca84e4804b2ba2f8de1be8d438d27b944ac3b`이다. 독립 입력 해시와 실행 담당의 입력 해시가 같고, 모델·설정·프롬프트·파서의 변경은 없다. 보강은 실제 expanded prompt/processor RGB/token·실패 진단·원본 sampling/근거 clip 비용·run context 저장, 정확10장 실행 guard와 summary binding이다. 보강 후 candidate 테스트11개가 별도로 통과했다. 실행 담당의153 MVP/14 queue 테스트 로그도 확인했다.

CPU 공식 processor의 세 창은 FP32이고10장 입력/10장 처리, padding0/추가sampling0이다.030 resize는480×704/visual1650/input2148 tokens,007 두 창은608×544/visual1615/input2113 tokens이다.10초창의 caption은 상대0.5/2.5/4.5/6.5/8.5초,5초 대조는0.2/1.2/2.2/3.2/4.2초이며 공식 쌍 평균·반올림 결과이다. 보존 snapshot1069파일을 직접 재해시해 불일치0, 세 주체가 보관한 기존45 jobs/45 attempts 행이 모두 같음을 확인했다. 원본·사용자 regions·EXP-0029/0030/0031과 고정 카메라/설정이 보호 대상이다.

실행 담당의 현재 native Task/Dispatch가 기존 Run에 속하며 revoked/completed가 아님을 확인했다. 이번 단발성 실행에서는 실행 직전 외부 배정 검증으로 기존 MVP registry의 Run/Dispatch 강제 누락을 보완한다. 최종 산출물과 보고서 SHA 검토 전에는 전체 독립 검토 완료로 표시하지 않는다.


## 실제 실행·출력 독립 대조

실제 canonical job1개/attempt1개에서 모델 로딩1회와 생성3회를 완료했고 자동 retry0이다. 시작 자원 gate는 free8126MiB로 통과했다. 과거45 jobs/45 attempts는 전 필드가 정확히 같고 최종46/46이다. 보호1069파일을 다시 해시해 불일치0이다. source/input/config 및 실제 processor RGB·expanded prompt·native PTS/metadata는 사전 freeze와 정확히 같았다.

세 generated-token 배열을 기존 로컬 tokenizer로 CPU decode해 각 저장 raw 응답과 일치함을 확인했다. 원본 시야의 재인코딩 clip3개를 실제로 디코딩해1920×1080/30fps,300/300/150프레임과10/10/5초를 확인했다. 이는 metadata·실행 검증이며 원본 영상의 독립 의미 판독이 아니다.

| 창 | 기존 strict parser | 기존 fence 제거 후 schema | 유효 행동·완료 필드 | 별도 원문 진단 |
| --- | --- | --- | --- | --- |
| 030 후보 | 실패 | 실패: 허용 밖 action | parsed null, completion unknown | JSON 문법은 유효하지만 미허용 action3개이며 raw completion은 observed |
| 007 후보 | 실패 | 성공 | contact + climbing_attempt_or_in_progress / observed | 근거 문장은 몸 기울임·접근을 반복하고 실제 몸·다리 올림을 설명하지 않음 |
| 007 정상 대조 | 실패 | 성공 | passage_or_waiting / observed | 보행 분류와 완료 주장이 모순됨 |

엄격 파싱0/3, 기존 fence 제거 후 유효2/3이다. **원문 완료 주장3개와 schema 유효 완료 주장2개를 구분한다.**030의 무효 출력을 새 정상/음성 판정으로 바꾸거나 미허용 action을 기존 action으로 보정하지 않았다. 모든 출력은 코드펜스를 포함한다. 토큰은152/133/128(총413)이며384 상한 도달0이다. 형식 실패를 토큰 절단으로 설명할 근거는 없다.

별도 CPU posthoc 참조 대조의007 후보 시간 부합은 기존 coarse 관찰과의 대조일 뿐이다. 세 창 모두 visual_agreement_verified=false를 유지하며 완료 정답·동일인 정답을 새로 만들지 않는다. 정상 대조를 보행으로 분류한 사실만으로 오탐 억제 성공으로 세면 완료 모순을 숨긴다. **두 양성창의 실제 몸 올림 설명 및 정상 대조의 일관된 비넘기 판정을 요구한 도입 기준 미충족이므로 자동 판정/기본 적용을 보류하는 결론이 타당하다.**

## 비용과 한계

supervisor 구간70.280626초, model load2.424488초, 세 창 generation합12.614629초, prepare합0.142047초, 원본 decode/sampling합15.755906초, 근거 clip 생성합33.488005초다. 이 합은 감독·해시·입출력 등 모든 비용을 분해한 전체합이 아니며70.280626초는 enqueue 전 검증/해시와 후속 검수를 포함하지 않는다. 저장된121개 GPU 표본의 최대 전체 used6807MiB/최소 free3247MiB, torch 최대 allocated4482.630859MiB/reserved4598MiB를 서로 구분한다. monitor 오류0이며 샘플 최대치를 연속시간 절대 peak로 확대하지 않는다.

전체 관측750프레임과 모델 입력30프레임은 다른 수치다. 후보2개와 독립 대조1개로 일반 정확도/F1/FPR·미검출 사건 recall·실시간 성능을 산출하지 않는다.10초/1fps와5초/2fps 차이, 개발 사례 선택 및 동일카메라 ROI 의존성이 있다. 학습·새 모델·프롬프트/임계값/ROI 변경·추가 실행은 수행하지 않는다. 독립 검토는 수치·출처·논리 대조이며 총괄의 시각 초안을 독립 의미 GT로 인증하지 않는다.

로컬 근거: `runtime/EXP-0033/independent-result-audit.json`, `independent-token-clip-audit.json` 및 실행 담당의 원본 freeze/실행 receipts. 결과 문서와 metrics의 최종 검토는 아래 binding으로 완료했다.


## 최종 보고서·metrics binding

**검토 통과: 실제 실행·입출력·보존·비용 근거는 확인됐고, 행동 기준 미충족 및 자동 채택 보류 결론을 지지한다.** 최종 보고서의 모든18개 metrics에 대해 로컬 원본 SHA, JSON 경로/집계식, 수치와 단위 변환을 직접 대조했다. 생성·전처리·메모리·토큰·파싱 및 완료 주장 계수의 출처가 일치한다.

- [최종 결과](../experiments/EXP-0033-results.md) SHA256: `0cdba1cb54746cd051a3545201fc25ff3fb11aaadadfe3d4c8022d962e2aefb7`
- [실측값18개](../../records/EXP-0033/metrics.json) SHA256: `fadf5a65332651aa506526733a8800726d667aa807ff890825eb4f310f8c87d6`

결과 초안의 Python3.12는 실제 summary의3.10.12로 바로잡힌 버전을 검토했다. 감독 실행 시간에서 enqueue 전 검증·후속 검수가 제외됨을 명시하고, 정상 대조의 보행 범주는 일부 부합하되 완료 주장은 잘못됐다는 구분을 유지한 최종 버전이다.030 일부 반대편 이동에 대한 총괄 관찰을 전 인원 완료나 모든 완료 주장의 반증으로 확대하지 않았다.

총괄의 원본0.5초 간격50프레임·마지막3프레임·실제 processor30프레임 판독 범위는 로컬 수기 기록과 일치한다. 이는 총괄 시각 초안이며 사용자 확정 정답이나 본 검토자의 별도 시각 검수가 아니다. 본 검토자는 원본 이미지를 별도 판독하지 않았고, 전750프레임의 수동 정밀 검수·사람별 정체/완료 시각 인증도 하지 않았다. GitHub 게시와 실제 웹 재생/seek·보고서/그래프 렌더 확인은 총괄의 별도 전달 기록에 맡기며 여기서 인증하지 않는다.

정확한 binding과 검토 근거 해시는 로컬 `runtime/EXP-0033/independent-final-binding.json`에 있다. 위 두 파일이 바뀌면 해당 변경은 이 binding의 검토 범위 밖이다. 추가 추론·튜닝·학습 승인으로 해석하지 않는다.


## Registration-format revalidation (2026-10-30)

공개 등록용 JSON 경로를 `/a/b`에서 `$.a.b`로 바꾼 metadata만 재검토했다. 변환 중 발견한 메모리 환산식의 점 표기는 총괄이 원래 `(bytes / 2^30)`로 복구했으며, 최종18개 수치·단위·표본수·범위·출처 SHA와 모든 경로/집계식이 기존 로컬 근거와 일치한다. 등록기의 `public`/`metrics` 읽기 전용 검증도 통과했다. 현재 metrics SHA256은 `7dd258034ebe87c93d5d2d1881087b072f220f706e1800ec8fb47aafb13bcc45`, 변경 없는 결과 보고서 SHA256은 `0cdba1cb54746cd051a3545201fc25ff3fb11aaadadfe3d4c8022d962e2aefb7`이다. 위의 이전 metrics SHA와 `independent-final-binding.json`은 당시 bytes의 역사적 binding으로 보존하며, 새 SHA는 경로 표기 변경에 한해서만 이를 대체한다. 기존 실질 감사와 자동 채택 보류 결론은 그대로다. 현재 Task/Dispatch와 실제 Astra high 배정,18개 대조 및 검증 기록은 로컬 `runtime/EXP-0033/independent-registration-format-audit.json`에 보존했다. 총괄은 이 새 binding으로 등록할 수 있으며, 본 검토에서는 등록 mutation·게시·미디어 열람·추론을 수행하지 않았다.
