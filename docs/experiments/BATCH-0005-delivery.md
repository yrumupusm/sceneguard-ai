# BATCH-0005 전달 기록

2026-10-29 KST. [승인 계획](BATCH-0005-c6-pose-roi-comparison-plan.md)에 따른 EXP-0023 고정 C6 비교다. 실제 추론·관절 품질·행동 판단·웹 표시·GitHub 게시를 별도로 확인한다.

## 보존과 담당 배정

main `9b01003a829c2a7cd77db4bf8c738a03d21109b8`의 clean 상태를 확인하고 사용자 지침 `83d4e9d2c295273e6688612ed0c9b358961d3f58`까지 fast-forward했다. reset/stash/강제 덮어쓰기를 하지 않았다. 기존 40 jobs/40 attempts와 374 tracked 파일의 해시를 로컬 보존 기준으로 기록했다.

기존 Run `run_3d23462a014a`·총괄·canonical 단일 GPU 큐를 사용했다. Sol 담당 Task `task_000a7c6dec59` / Dispatch `ctx_f85d0a3a38de`는 native launch 및 live provider에서 `gpt-6.1-sol/high`, 독립 검토 Task `task_3cd0dbe78c11` / Dispatch `ctx_08870623c7d2`는 `gpt-6-astra/high`를 확인했다. 새 총괄/큐를 만들지 않았다. 리뷰 작업 시작 시 잘못된 CLI 계층의 `Unknown command: worker-start` 한 건은 시작 전 인자 오류였고, 올바른 `orchestration worker-start`로 실제 작업자 한 명만 생성했다. GPU 실행/재시도와 무관하다.

기존 COMPLETE_CLI로 EXP-0023을 담당3 카드에 배정했고 실제 브라우저에서 제목, ‘진행 중’, 실효 Sol/high와 ‘결과가 아직 등록되지 않았습니다’를 확인했다. 이는 모델 실행 성공을 뜻하지 않는다.

## 고정 소스와 실행 전 검토

`62fe072bdd70f4e3eeb8c51a4984b96f221fea41`에 코드·입력 계약·테스트·배정을 commit/push했다. 실행 의존24개 파일의 현재 bytes/readiness/Git 객체 일치를 총괄이 확인했다. source digest는 `c6de4151fe1c836a8c607db1979e058154368461dc823b3be8187d2cf82f8a16`, manifest는 `a7c01d94d70aafeb6910ec0958fadc8ad5b461005224eaf68fe83c59d553f045`다.

담당의 CPU 검사23개와 독립 리뷰의 관련 합성 검사7개가 통과했다. 중복 검사를 예측 수나 품질 지표로 합산하지 않는다. 고정 C6 crop/color/offset/unknown 처리, exact native PTS/cache hash, 공식 API, 예측5개 한도, 기존 queue 보존을 확인했다. 독립 preflight PASS 후에만 실행을 허가했다.

초기 여유8152MiB였으나 준비 도중3532–3945MiB로 줄어 기존6144MiB 기준 아래에서 enqueue하지 않았다. 사용자가 자원 확보를 알린 뒤 실제8252MiB free를 확인하고 exact5를 허가했다. 다른 GPU 프로세스를 종료하거나 기준을 낮추지 않았다. 이 대기는 추론 오류/retry가 아니다. child 실행은 기존 live resource/lease 검사를 다시 통과해야 한다.

원본·RGB·native Results/관절 좌표·tensor·비교 이미지·weights·runtime/DB/로그/receipt는 로컬 전용이다. 결과·독립 검토·화면·원격 게시의 최종 증거는 아래에 추가한다.

## 실제 비교 완료

기존 canonical queue의 job `7c366be9bf694ce7a476a47119419ca2` / attempt `90784d50902748b9956101771e27662b`는 succeeded다. 실행 직전 free8262MiB, 한 모델 로드·public predict5·sample forward5·별도 warmup forward1, 오류/OOM/retry0이다. summary SHA256은 `1c08d87413a2bc399c2a426f63b865e7f3e2f817c8fc35801781ef206d67c46a`다. 새5조건과 cached90full1개를 구분했다.40개 과거 jobs/attempts row 전체 및 보호된 과거 파일/결과·환경을 보존했다.

84초 full2행/24관절 추정→C6 3행/38추정,90초 full0/0(재사용)→C6 1/12,94초 full/C6 모두0/0이다. 실제 신체 대응 검수와 다른 출력 통계다. 세 원본/full/C6 triptych와9개 패널을 로컬 생성하고, 세 시점의 새 이미지 검수만 한 번 묶어 요청했다. 사용자 답변 전에는 관절 품질을 미확정으로 유지한다. 추가 GPU 작업은 없다.

실제 비용은 [EXP-0023](EXP-0023-c6-pose-roi-comparison.md)와52개 metrics에 기록했다. run-entry6.352339초/queue attempt9.631618초이며 범위가 다르다. 기존 cache 결과를 신규 비용에 더하지 않았고 계측된5장으로 영상 FPS나 관절 정확도를 만들지 않았다.

## 독립 결과 검토와 등록

Astra high는 실제5회/재사용1회/warmup1회,52개 metric source pointer, 신규27artifact와cached6artifact 해시, 원래40개 jobs/attempts 및 보호된 과거108파일을 확인했다. 결과는 **기술 실행·제한된 보고의 PASS**이며 실제 신체/관절 대응·행동 성능의 PASS가 아니다.

report `0978d472573ac037a268483b8b358b8d8b5b359f7557c372fc621f9a1dab1e36`, metrics `1143c6d5e7f6587a63047edcf7a711564f7eed5ddb42118c489b4de89ce18070`, 총괄 요약 `a197b5247ae9202f65234996304e5ca1c6a18d283a36581d7cbc4808ecf4d910`에 독립 검토를 묶었다. review SHA는 `821d16917c385fcd64ddc01522971da55ca7833cfac48b1d0dcf7258601ce28b`, 완료 binding SHA는 `d85cc51c6dda4e7b06016e7c4f735b303ced1bd9b5186f9b6e2bda184058ee7d`다.

기존 완료 명령으로 EXP-0023 담당3에 `succeeded / accepted_for_comparison / adoption_on_hold`를 등록했다. 기존22개 catalog 결과는 그대로 유지했다. 완료 등록을 영상 품질 검수나 GitHub 게시 증거로 대신하지 않았다.

## 실제 기존 화면 확인

2026-10-29 05:53 UTC, 기존 `http://127.0.0.1:8765/`에서 담당3 → EXP-0023 → 보고서/52개 지표/그래프2개/독립 검토를 펼쳤다. 원본/full/C6 triptych3개가 각각5760×1145로 decode/render되고 polling 뒤에도 유지되는 것을 실제 브라우저 DOM으로 확인했다. 각 HTTP 이미지 응답 bytes도 로컬 파일 해시와 일치했다.

| 로컬 artifact ID | 이미지 SHA256 |
| --- | --- |
| `exp0023-030-084-c6-comparison` | `e827fadc1f17fba81f898bcd288569393f40f0d523a3455df81f3dd53b43a0c2` |
| `exp0023-030-090-c6-comparison` | `c25235570f16faf04698f209591676182f10ab5df4698b2adc3286fb3047d7b5` |
| `exp0023-030-094-c6-comparison` | `9159f3e50ae10fc86f96f2fe04b794e2f5d33512966fb57f2bac73efd2705d22` |

서비스가 읽은 report/metrics/review/binding은 위 검토 bytes와 일치했다. JS SHA256은 기존 `cae122f859102f7a6f0dd3255d9e4a7ec5491814f340dc9a4e28fff6ba8b9fcd`로 웹 기능/디자인 변경이 없다. 정지 이미지 실험이므로 **동영상 재생/seek는 해당 없음**이다. 이미지 전용 로컬 검사로 확인했으며 CCTV 픽셀을 클라우드에 전달하거나 사람 관절 정합성이 확인된 것으로 기록하지 않았다. 실제 receipt는 로컬 `runtime/BATCH-0005/delivery/browser-images.json`에 보관했다.

## GitHub 게시와 종료 확인

최종 결과14개 공개 코드/문서/집계 파일을 `f934e3afbecb3abb89930fcb7f909a679c5314e9`로 정상 commit/push했다. staged 경로·diff와 Git 제외 규칙을 확인해 원본/프레임/오버레이·native Results/관절 원시값·tensor·weights·환경·runtime/DB/log/receipt는 포함하지 않았다. 2026-10-29 05:55 UTC에 origin/main SHA 및 Git 객체의 report/metrics/review/binding bytes가 위 독립 검토·실제 로컬 서비스 해시와 같은지 별도 검증해 PASS했다. 실제 GitHub receipt는 로컬 `runtime/BATCH-0005/delivery/github-results.json`이다.

두 native 작업자는 각자의 정확한 Task/Dispatch로 worker_done succeeded를 제출했고 총괄이 수용 후 해당 터미널만 worker-release했다. 종료 뒤 실제 화면에서 EXP-0023 succeeded/accepted_for_comparison/기본 채택 보류·3개 이미지 유지와 담당3의 진행 중 표시 해제를 확인했다. 과거 실패 표시는 다른 보존된 실험 이력이며 이번 실패가 아니다. reclaimable worker0, canonical queue37 succeeded/4 failed, queued/running0이다. 다른 사용자 작업자는 종료하지 않았다.

| 커밋 | 내용 |
| --- | --- |
| `62fe072` | 고정 C6 비교 구현·입력·CPU 테스트·담당 배정 |
| `f934e3a` | 신규5회/캐시1개 실측·3시점 해석·독립 검토·웹 등록·최신 작업 문서 |

이 전달 증거 문단은 별도 문서 커밋으로 게시하고 최종 HEAD를 다시 원격 검증한다. 공개 보고서/metrics/review/binding은 수정하지 않는다. 최종 검증 receipt는 로컬에만 보관한다.

**종료 판정:** 구현·CPU 검사·승인된5회 실제 추론·독립 기술/보고 검토·기존 웹 이미지 표시·GitHub 게시 확인은 완료했다. 실제 bbox/관절 대응은 요청한 세 이미지의 사용자 답변 전 미확정이며, 행동 성능은 이번에 평가하지 않았다. ROI 출력 증가만으로 복원 성공을 선언하거나 기본 모델을 교체하지 않는다. 기존 결과와 라벨을 보존했고 새 GPU/추적/규칙/자동 후속 실험은 예약하지 않았다.
