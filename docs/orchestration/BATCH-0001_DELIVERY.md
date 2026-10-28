# BATCH-0001 실제 VLM 실행과 결과 전달

2026-10-28. [비교 결론](../experiments/BATCH-0001-vlm-comparison.md): Qwen 기준, Smol 기준, Qwen 전체 화면 픽셀 예산 대조의 세 조건을 완료했다. 같은 개발 클립6개를 반복한18회 생성이며 독립 표본18개가 아니다. **두 후보 모두 채택 보류, 배치 종료.** 새 모델은 Smol 한 개만 추가했고 추가 모델·조건·자동 재실험을 시작하지 않는다. CV/ByteTrack/경계 규칙, EXP-0006 기본 적용 보류는 유지했다.

## 구현과 실제 실행

기존 Run `run_3d23462a014a`, 총괄 terminal `term_a33bb862-d6c5-4f25-9c37-78e00f919db4`, canonical GPU 큐 하나를 재사용했다. 총괄은 실제 세션 metadata의 gpt-6-astra/max, 담당은 gpt-6.1-sol/high, 독립 검토는 gpt-6-astra/high다. 설정 파일의 희망 모델이나 모델 자기소개만으로 배정을 확인하지 않았다. 준비는 별도 worktree에서 병렬, 모델 추론은 기존 큐의 `vlm-batch01` 등록 명령으로 직렬 실행했다. 새 총괄·큐·대시보드 기능은 만들지 않았다.

| 결과 / 카드 | native Task / Dispatch | 실제 queue attempt | 상태 |
|---|---|---|---|
| EXP-0008 / 담당1 | `task_0bfc2bc3eafc` / `ctx_c9acf995dc40` | `8b93c06304724009b8ca5a0d15a28288` | 6/6 생성, 첫 attempt exit0 |
| EXP-0009 / 담당2 | `task_e56ab41484b8` / `ctx_b06f6387b019` | `ef353740b07d46d79ddb030e8d22ecd5` | 6/6 생성, 첫 attempt exit0 |
| EXP-0010 / 담당1 | `task_be6c4ddef130` / `ctx_735ddbea9bba` | `c0fd8f0c63154c5d837d5c149bf948b5` | 6/6 생성, 첫 attempt exit0 |
| 독립 검토 | `task_2243d4095409` / `ctx_652bea27629a` | GPU 사용 없음 | 원문18개·공개 숫자123개 출처 검토 완료 |

담당 코드·보고서 제출 및 worker_done을 수락한 뒤 각각 native release, 정확한 자기 terminal의 idle 확인, 탭 닫기를 수행했다. 기존 총괄·다른 세션·전체 Orca runtime은 종료하거나 reset하지 않았다. 외부 terminal은 release가 프로세스를 종료하지 않아 이 명시적 정리 순서가 필요했다. 작업자4개는 동시에4명이 아니라 담당 최대2명+검토1명의 한도 안에서 교대했다.

실제 큐 시작/종료 UTC: EXP8 08:53:10.997~08:53:34.851, EXP9 08:55:34.423~08:55:53.464, EXP10 09:09:45.815~09:10:10.513. 세 구간은 겹치지 않고 추론 retry/OOM0이다. 큐 경과는 생성 시간과 다르다. 실행 전후 기존8개 job/attempt의 모든 열이 동일했고 현재11개씩이며 queued/running/unknown0이다. 협조적인 큐 작업의 직렬 실행을 확인한 것이며 머신의 다른 GPU 프로세스까지 통제한다는 뜻은 아니다.

실행 명령은 고정 모델·환경·출력 ID를 allowlist로 선택하고 source/input/config 해시 및 살아 있는 canonical lease를 모델 로드 전에 확인한다. 기존 CPU 명령 제한을 이 등록 명령까지 확장하는 SQLite migration은 백업 후 기존 rows/FK/index를 보존했다. 원시 token ID는 텍스트 decode 전 저장하고 원문·파싱 실패를 유지한다. 의미를 바꾸지 않는 공통 코드 펜스/양끝 공백 제거만 별도로 평가한다. 모델별 공식 영상 전처리와 실제 프레임·PTS·입력량·비용은 각 실험 보고서가 원본이다.

## 담당 카드와 재사용 완료 절차

[EXPERIMENT_DELIVERY](EXPERIMENT_DELIVERY.md), [COMPLETE_CLI](COMPLETE_CLI.md)를 그대로 사용했다. 실험마다 assign→담당 제출→별도 총괄 검토→report/metrics SHA 고정→complete 순서다. EXP8/9/10을 실제 native 배정과 연결했고 각12개 근거 항목을 등록했다. 동일한 원본 비교 영상6개를 세 결과에서 참조하며 모델별 실제 입력 시트는 별도6개다. 원본 연속 화면과 선택한2fps 표본을 나란히 보여주는 영상은 **표시용**이며 모델 입력이 아니다.

보고서·실측 표/그래프·작업자 의견·총괄 검토는 공개 기록, 영상/입력 시트의 절대 경로는 로컬 allowlist에만 있다. clip02/06을 사람 확인 우선으로 표시했다. 나머지를 다시 전체 검수하도록 강제하거나 모델 문장을 정답으로 등록하지 않는다. 번호·파일명·기존 정답 설명은 추론 질문에 들어가지 않았다.

실행 전 카드 및 첫 실제 큐 child가 살아 있는 동안 담당1 진행 상태를 브라우저에서 확인했다. 첫 캡처는 가중치 로드 전일 수 있으므로 그 순간의 GPU 생성 화면이라고 주장하지 않는다. 실제 GPU 사용은 별도 실행 측정치로 확인했다. 완료 후 EXP8/9/10은 담당 카드 선택, 원문 보고서 펼치기, 두 그래프, 총괄 검토, 등록 영상6개 각각의 재생/seek 및 polling 중 플레이어 보존을 확인했다. 최종 세 결과의 GitHub 게시·서비스 버전·브라우저 검증은 별도 [게시 확인 기록](BATCH-0001_PUBLICATION.md)에 남긴다. 등록 성공/API200을 화면 검증으로 대체하지 않는다.

## 검증·오류·한계

- 최종 lab suite:75개 중74개 통과·1개 skip,7.814초. skip한 공식 Qwen processor 경로는 기존 VLM 환경에서 별도 CPU 검사했다. 독립 검토자가 queue/parser26개, Smol 합성11개, Qwen4개, records2개를 실행했다. 두 Node 카드/브라우저 probe fixture도 통과했다.
- 첫 전체 검사는 새 EXP8 등록 후 historical catalog가7개만 있다고 가정하던 테스트에서 실패했다. 과거7개 순서·해시·초안 속성 검사를 보존하고 새 결과 추가와 전체 ID 유일성을 허용했다. 실행 코드/실험 결과 수정은 아니다.
- 독립 검토에서 Smol 장치 메모리 최고값의 JSON pointer에 배열 인덱스가 빠진 것을 찾았다. 실제 최대값을 가리키는7을 추가하고 재검토했다. 수치·원천 파일·모델 출력 변경 없이 해결했다.
- Smol 담당이 생성/보고서 저장 후 Sol 용량 제한을 만났다. 같은 Sol/high로 마무리 요청을 한 번 이어서 commit/worker_done을 수신했다. 다른 모델·유료 API로 전환하지 않았다. 이는 GPU 실행 재시도0과 별개다.
- EXP8 재생 검증 후 추가 이미지 decode를 기다리던 브라우저 탭의 native 명령이 timeout됐다. HTTP와 Orca 작업은 살아 있어 해당 결과 탭만 닫고 같은 로컬 페이지를 다시 열었다. 이후 동기 DOM 조작과 별도 loaded/dimension 조회로 여섯 입력 이미지 로딩을 확인했다. 전체 runtime reset·GPU 실행 우회는 없었다.
- 원본 보존 검사:2,086개 기존 파일 size/mtime, 선택430개 SHA256, 두 기존 환경 freeze가 동일했다. 모든 영상/가중치 바이트를 재해싱한 검사는 아니다. 신규 batch 환경·Smol 가중치·새 결과만 추가했다.
- 큐 timeout은 감독 프로세스 생존에 의존한다. 감독 종료 시 상속 lock은 겹침을 막지만 무조건900초 내 orphan 종료를 보장하지 않는다. 실제 세 작업은 정상 종료했고 이 배치에서 orphan GPU 복구를 새로 실험하지 않았다.

보존·원문·패키지·큐·브라우저 receipt는 로컬 runtime에 있다. 영상 픽셀을 클라우드 에이전트로 자동 전달하지 않았으므로 DOM 재생/크기 확인은 사람의 의미 검수와 다르다. 현재 판단은 기존 관찰 초안과 응답 근거 검토이며 최종 정확도/F1/실시간 관제 성공은 미측정이다.

## 시작·중지·복구

최종 서비스 코드는 main 저장소, 기존 lab 환경·runtime을 사용한다. 웹 주소는 **http://127.0.0.1:8765/** 이며 읽기 전용 loopback이다. 이 명령은 모델 작업을 시작하지 않는다.

```bash
cd /home/jhc7484/dev/sceneguard-ai
SCENEGUARD_LAB_PY=/home/jhc7484/dev/sceneguard-orca-lab/.venv-orca-lab/bin/python
SCENEGUARD_LAB_CONFIG=/home/jhc7484/dev/sceneguard-orca-lab/runtime/orca-lab/local_config.json
"$SCENEGUARD_LAB_PY" -m orchestration.lab --config "$SCENEGUARD_LAB_CONFIG" status
"$SCENEGUARD_LAB_PY" -m orchestration.lab --config "$SCENEGUARD_LAB_CONFIG" stop
"$SCENEGUARD_LAB_PY" -m orchestration.lab --config "$SCENEGUARD_LAB_CONFIG" start
```

status가 살아 있는 서비스 소유권을 보여주면 start를 중복 호출하지 않는다. stop은 소유한 web/projection만 종료하며 GPU 큐/Orca agent를 종료하지 않는다. 부분 실패는 로컬 로그와 PID identity를 확인하고 같은 stop/start로 복구한다. queue 상태/비파괴 복구는 같은 runtime의 `python -m orchestration.queue --runtime .../gpu-queue status`와 `recover`다. 실제 큐 절대 경로는 기존 LOCAL_SETUP_REPORT를 따른다. DB/lock 삭제·완료 job 재실행·자동 retry는 금지하며 추가 모델 실행은 이번 종료 배치의 후속 승인으로 간주하지 않는다.

## 게시 대상

명시적으로 검토한 코드·테스트·공개 측정 요약·선정/실험/검토/전달 문서만 게시한다. 원본·프레임·표시용 영상·가중치·모델 원문·token IDs·NPY·환경·인증정보·SQLite·원시 로그·receipt는 Git 제외다. 기존 EXP1~7 보고서/출력/공식 라벨은 보존했다. 게시와 실제 서비스 반영은 위 게시 확인 기록의 원격 SHA 및 별도 receipt로 확인한다.
