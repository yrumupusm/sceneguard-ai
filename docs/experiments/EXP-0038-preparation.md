# EXP-0038 — 8B NF4 실행 준비 기록

2026-10-31. **가중치 준비·큐 연결·CPU 입력 검증 완료 / GPU 여유 부족으로 실제 모델 적재/6쌍 비교 미실행.** 이 문서는 성능 결과 보고서나 채택 결정이 아니다. [실행 지침](../CODEX_EXP0038.md)과 [선정 근거](../decisions/ADR-0024-qwen8b-nf4-appearance.md)를 따른다.

## 기존 작업 보존과 구현

깨끗한 main `600ea46`에서 `8d57d65`까지 fast-forward했다. reset/stash/덮어쓰기를 사용하지 않았다. 기존 canonical `mvp-0001` 큐에 `appearance-8b` phase만 추가했다. 기존 2B constructor·단일 shard 경로와 분리하고 기존 MVP 기본 설정·의심·카드·검토 저장 기능은 유지한다.

새 phase는 실제 활성 Orca 배정, 부모/자식 프로세스, 상속 lease, 정확한 job ID, 소스·환경·전체 가중치/입력 해시를 검증한다. 모델 한 번 적재·6회 생성·추가 warmup 0회·greedy 192토큰이다. NF4는 언어 Linear에만 적용하고 시각부/임베딩/untied head는 BF16, 전체 CUDA0, offload 없음이다. 로딩/검증/요청별 전처리·생성 시간과 allocator/전체 장치 메모리를 따로 기록한다. 일부 생성 후 실패하면 원 응답과 진단을 보존하고 미실행을 unknown 응답으로 만들지 않는다.

기존 환경은 torch2.5.1+cu124, Transformers4.57.1, bitsandbytes0.48.1, Accelerate1.11.0이다. 설치나 업그레이드 없이 보존된 환경 파일19,041개의 해시를 검증했다. HF 공식 revision은 `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`; `scripts/prepare_exp0038_checkpoint.py`로 전체15파일17,545,914,364바이트를 받은 뒤 공식 LFS SHA256 또는 Git blob ID와 대조했다. 가중치 파일 준비와 GPU 적재 성공은 별개다.

실측 다운로드1,380.247초, 공식 파일 검증12.874초다. 일시적인 Xet DNS 오류 후 같은 다운로드가 진행됐고 모델/전송 방식을 교체하지 않았다. 별도 작은 파일 선취득과 CDN 연결 확인 요청이 있어 이 시간은 모든 네트워크 준비를 합산한 총계가 아니다. 최초 metadata 정리 중 CPU API 사용 오류는 수정했으며 GPU 실행 오류가 아니다. 최종 큐 입력 계약 재검증은14.088초였고 receipt SHA는 `fe7587fc2afd8707958c0c963b2967657c64eef895e013a59f5937c00eccca04`, 입력 계약 SHA는 `d553135dd9848058bd273508b0bdbce144f4c6fba3382ec7926e3087b6486409`다. **job/attempt 추가0, 모델 적재0, 생성0**이며 로딩/생성 시간과 peak GPU 메모리는 미측정이다.

## 실제 CPU 검증

- 원래 manifest SHA `996ecdb638b624d69c54a70ff0e44027c95a3d2dd04a78efa00a69856af3ec90`, 6쌍/27슬롯(5/5/5/4/4/4)을 유지했다. 모든 크롭이 원본의 정확한 native PTS·관측 bbox·RGB와 일치했다. 새 박스/라벨은 만들지 않았다.
- 8B 공식 processor로 실제 6쌍을 CPU 준비했다. 입력 토큰은 618/620/623/555/539/546이며 이미지 추가/삭제 없이 A/B 순서를 유지했다. 이는 실제 모델 생성 검증이 아니다.
- 구현 담당의 관련 테스트81개, 독립 Astra의 별도 CPU 검사95개가 통과했다. 중복된 검사가 있으므로 합산하지 않는다. 전체 저장소 테스트나 실제 NF4 적재 성공을 의미하지 않는다.
- 독립 검토가 발견한 비활성 옛 `384토큰/6144MiB` summary 혼동을 실행 전에 수정했다. 새 phase에는 실제 `192토큰/8192MiB` 설정만 기록하며 구 phase는 유지했다.
- 기존3,174보호 파일·48jobs/48attempts 보존을 입력 담당이 확인했다. 모델 응답 파일은 해시만 읽었고, 기존 2B 응답 내용은 새 생성 종료 후 대조하도록 격리했다.

기존 Run에서 Sol high 구현/입력 담당과 Astra high 독립 검토의 실제 실효 설정을 확인했다. 기존 웹 담당3에는 EXP-0038 배정이 표시됨을 확인했으나, 이를 실제 모델 실행이나 완료 결과 등록으로 보고하지 않는다. 코드/CPU 검증에 대한 독립 검토는 로컬 `runtime/EXP-0038/preflight-review.json`에 있다. 그때 미완료였던 가중치 검증은 총괄이 이후 완료했고, GPU 실행 자원 확인과 실행 후 별도 독립 검토는 남아 있다.

## 실행 재개 조건

전체 공식 파일 검증, 검토된 소스/입력/현재 배정에 결속된 실행 기록, **GPU 여유8192MiB 이상**이 필요하다. 마지막 확인값6,118MiB는 이 기준을 충족하지 않았다. 사용률이 낮더라도 남은 GPU 메모리가 부족하면 실행하지 않는다. 다른 프로세스를 종료하거나 기준/이미지 예산을 낮추지 않았다. 사용자에게 메모리 확보를 요청했고, 승인된6회 생성 예산은 전부 미사용 상태다. 무인 백그라운드 실행을 예약하지 않는다.

실제 비교가 없으므로 완료 catalog/binding을 만들지 않았다. 기존 담당 카드의 배정 확인과 실제 결과 등록은 구분한다. GPU 여유 확보 후 새 활성 실행 배정으로 소스/체크포인트/입력/HEAD를 재검증해 실행 기록을 결속한다. 현재 CPU 담당의 종료된 배정이나 준비 당시 HEAD를 실행 권한으로 재활용하지 않는다. 이후 원 응답 비교·실측 보고서·독립 검토·기존 화면의 최종 결과 등록·GitHub 결과 게시가 남아 있다.

CPU 재현:

```bash
.venv-vlm-batch02/bin/python scripts/prepare_exp0038_checkpoint.py
.venv-vlm-batch02/bin/python -m unittest discover -s tests_mvp -p 'test_exp0038*.py' -v
.venv-vlm-batch02/bin/python -m mvp.cli --help
```

실제 큐 진입은 기존 절대 runtime에 `enqueue --phase appearance-8b --view full_frame`과 현재 유효한 Run/Task/Dispatch/owner를 전달한 뒤, 반환된 job만 `run-once --job-id`로 실행한다. 완료된 옛 배정이나 EXP-0034 실행 승인을 복사하지 않는다. 정확한 실행 명령·job/attempt와 실측은 실제 실행 후 결과 보고서에 추가한다.

원본/실제2B 입력 검수 자료는 로컬 `outputs/exp0038/input-review/`에 준비했다. `scripts/exp0038_compare_results.py`는 새6회 생성 완료를 확인한 뒤에만 2B 응답을 읽어 원본/2B/8B 실제 입력 비교판을 만든다. 새 동일인 정답을 만들거나 입력을 모델 결과에 맞춰 바꾸지 않는다. 영상·이미지·원시 응답·가중치·환경/큐DB·실행 로그는 로컬에만 둔다.
