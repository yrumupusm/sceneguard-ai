# MVP-0002 — 기존 로컬 MVP의 3조건 개발·연속 처리 계획

2026-10-28. 실행 조건은 GPU 자원 차단 전 이미 고정한 [MVP-0001 계획](MVP-0001-plan.md)에서 바꾸지 않았다. 이 문서는 그 동일 조건의 재개 결과를 공개하기 위해 정리한 보조 기록이다. 기존 coordinator Run과 단일 GPU 큐, 새 Task/Dispatch `task_e09cc6304b35` / `ctx_0da6354a652f`를 사용했다. 허용 가중치는 기존 Qwen3-VL-2B와 CV 결과 캐시뿐이다. 세 큐 job의 공개 결과는 통합 비교 EXP-0013 한 건으로 기록한다.

| 구성 | 비교 자료 | 입력 차이 |
|---|---|---|
| A: cached CV/ByteTrack | EXP-0005/6 existing output only | No new detector/tracker or shared accuracy ranking against action language. |
| B: whole-frame Qwen | three complete originals 007/030/013; prior six-clip B output preserved | Existing full-frame Qwen. |
| C: fixed-ROI Qwen | same six development clips and same three complete originals | Same Qwen, fixed PTS0 background ROI for C3/C6/C7; C1/C4 remain full-frame fallback. |

No more than three configurations, no learned weights, and no prompt/score/view adjustment after output. The existing BATCH-0001 Qwen pixel-budget comparison consumes the only planned B improvement. C has no improved setting in this bounded execution. Source list remains the frozen 007/030/013. E01_013 was previously exposed to audit and shares the C4 group with excluded 039/045; no blind/new-site claim or tuning on 013.

Use original PTS, 5-second windows, 2.5-second stride, nominal 2fps, the common prompt/parser/generation config, and no CV gating. If a final window has too few actual samples, preserve it as insufficient rather than fabricate frames. Do not provide event times, official JSON/captions/labels, prior answers, or person/event-specific crops to the analyzer. Save outputs and evidence locally. Run each condition through the common queue, sequentially, with 6144 MiB minimum prelaunch free memory and at most one execution-error retry per job. Retain every attempt and do not start a second condition until the previous attempt is terminal.

**Evaluation is three separate gates:** automated tests; full-source function integration to actual EOF with candidates/unknowns/evidence; and human-reviewed action distinction. Candidate words/counts, schema, output format, or a broad time overlap are not behavioral success. Unknown, parse failure and insufficient EOF input are not normal. Without verified ground truth, do not calculate accuracy, F1, hourly false positives, or event completion rates. Any local human review questions should be limited to 007's general-approach anchor and 030's climbing/EOF uncertainty. Registration, GitHub publication and actual local page viewing are separate checks after the result is reviewed.
