# EXP-0038 — Qwen 8B NF4 외형 비교 실제 결과

2026-10-31 KST. **실제 1회 적재·6쌍 생성 완료 / 원문 형식 개선 / 가림 대응 일부 개선 가능성 / 사람 혼합 오류 유지 / 채택 보류.** 기존 MVP·의심 생성·사건 카드·수동 검토·사용자 영역·검출/추적·2B 결과는 그대로 유지한다. 새 학습·박스·데이터 수집·후속 추론은 없다.

## 실행과 비교 조건

실행 코드 `eb6e6fb1f88649a5a2a46126a4c3cb99e5a44ef1`, 기존 Run `run_3d23462a014a`, Sol high 실행 Task `task_144932ec63a8` / Dispatch `ctx_95618a8e831d`, Astra high 독립 검토 Task `task_cae376586829` / Dispatch `ctx_8abdfb34093e`다. 총괄은 기존 Orca 총괄을 재사용했다. canonical `mvp-0001` 큐 job `1b0a11e9be66448885dc023f5d543d11`, attempt `2045864aebe541f6bda49875a03efc6e`가 exit0으로 종료했다. 1job/1attempt/1load/6generate, retry0, warmup0, offload0이다.

모델 `Qwen/Qwen3-VL-8B-Instruct`, revision `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`, Apache-2.0. [ADR-0024](../decisions/ADR-0024-qwen8b-nf4-appearance.md)의 공식 출처를 사용했다. 15파일 17,545,914,364바이트를 공식 metadata와 대조했고 로컬 checkpoint receipt SHA256은 `fe7587fc2afd8707958c0c963b2967657c64eef895e013a59f5937c00eccca04`다. 4개 원본 BF16 shard는 로컬 전용이다.

기존 `.venv-vlm-batch02`를 변경 없이 사용했다: Python3.10.12, torch2.5.1+cu124, transformers4.57.1, bitsandbytes0.48.1, accelerate1.11.0, numpy2.2.6, av16.0.1, safetensors0.8.0. 실제252개 언어 Linear가 NF4/double quant/BF16 compute/uint8 storage이며 시각부·임베딩·untied 출력 head는 BF16이다. 전체 CUDA0(RTX3080 10GB), SDPA, batch1, seed0, greedy192토큰이다. 전체 parameter/buffer/quant-state의 CUDA 배치를 검사했다.

EXP-0034 같은6쌍·27슬롯(5/5/5/4/4/4), 원본 PTS·A/B 순서·크롭·질문·파서·min65536/max262144px를 유지했다. 원본 및 실제 processor RGB27개와 grid·shape·예산, 확장 질문6개가 저장2B와 정확히 일치했다. 실제 입력 토큰 수는618/620/623/555/539/546이다. 모델마다 자기 공식 processor를 썼으며 token ID나 내부 표현 동일성까지 주장하지 않는다. 옛 답변은 8B6회 생성 종료 후에만 읽었다.

기준2B는 EXP-0034 저장 BF16 결과이며 재추론하지 않았다. 모델 크기·시각 인코더·양자화가 함께 달라진 배포 구성 비교다. NF4 단독 효과, 4B 대비 개선 또는 범용 성능 비교가 아니다.

## 쌍별 비교와 원본 근거의 한계

아래 시각 설명은 EXP-0034 원본/processor 검수 초안을 재사용한 총괄 분석이다. 새 사용자 동일인 정답이나 클라우드 이미지 판독을 만들지 않았다. 원본 전체 맥락과 실제 입력은 기존 로컬 패널 및 새 2B/8B 비교판으로 함께 제공한다. 외형 호환은 동일인 확정이 아니며, unknown은 정상이나 침입 아님을 뜻하지 않는다.

|쌍 / 기존 raw ID|기존 원본 관찰 초안|2B 상의/하의/가방 → 결론|8B 상의/하의/가방 → 결론|판단|
|---|---|---|---|---|
|P1 030 1→9|밝은 겉옷·밝은 바지·검은 배낭, 후반 다리 일부만 가시|match/match/match → compatible|동일|호환 후보 유지. 세 부위·동일인 정답 확정 아님|
|P2 030 9→11|흰옷 인물 후보, 앞쪽 부분 박스와 가려진 하의 불명확|match/different/match → different|match/match/match → compatible|불확실한 하의를 unavailable로 남긴 것이 아니라 match로 변경. 가림 복원 성공 미확정|
|P3 030 3→9|서로 다른 의복 대조, 가방 근거 제한|different/different/different → different|different/different/unavailable → unknown|가방 유보는 신중해졌으나 의복 차이에도 최종 거부를 잃음|
|P4 030 4→7|서로 다른 의복 대조, 가방 정확한 비교는 미확정|different/different/different → different|different/different/different → unknown|항목 모두 다르다고 하면서 최종 유보. 의미적 일관성 문제|
|P5 007 9→9 분할|두 사람이 섞임. 옆 가방과 배낭이 서로 다른 몸에 대응|match/match/match → compatible|동일|핵심 혼합 오류 유지. raw ID 같다는 이유로 동일인 정답으로 삼지 않음|
|P6 007 13→15|문/표지에 가림, 공통 하의·가방 근거 부족|match/different/match → different|different/unavailable/unavailable → unknown|하의 차이 단정 대신 유보한 점은 초안과 부합. 상의 판단 변화·동일성은 미확정|

확인 가능한 개선은 **원문 형식과 P6 비가시 항목의 유보**다. P2를 성공으로 세지 않으며 P3/P4의 거부 손실과 P5 혼합 실패를 함께 고려하면 전체 품질 개선은 확인되지 않았다. 입력 자체의 부분 박스·가림·복수 인물을 모델 확대만으로 해결하지 못했다. 정밀 동일인 정답이 없으므로 정확도/F1은 null이다. 미비교 경쟁24쌍은 그대로이며 자동 연결/ID 병합/침입 확인은0이다.

## 형식과 비용

|측정|저장2B BF16|새8B NF4|
|---|---:|---:|
|원문 strict JSON|0/6(코드 fence)|6/6|
|동일 기존 파서 통과|6/6|6/6|
|호환 / 다름 / 명시적 unknown|2 / 4 / 0|3 / 0 / 3|
|unavailable 항목|0|3|
|총 출력 토큰|132|111|
|적재(8B는 양자화 포함)|10.178초|9.313초|
|6회 생성 합|5.722초|9.991초|
|첫 생성|1.795초|1.939초|
|나머지5개 생성 중앙값|0.756초|1.579초|
|전처리 합|0.08574초|0.07120초|
|생성 peak allocated|4,390,882,816bytes (4.089GiB)|7,518,737,920bytes (7.002GiB)|
|생성 peak reserved|4,427,087,872bytes (4.123GiB)|7,614,758,912bytes (7.092GiB)|
|전체 장치 사용량 표본 최대|5,793MiB /62표본|9,191MiB /87표본|

파싱 실패 대체 unknown0, 토큰 상한 도달0, OOM0이다. strict 형식 개선을 외형 이해 향상으로 계산하지 않는다. 생성 합은 이번6쌍에서 약1.75배, allocated는 약1.71배다. 다른 시점·다른 길이의 출력이고 반복 측정이 아니므로 적재 우열·p95·실시간 SLA를 주장하지 않는다. 전체 장치 표본에는 다른 프로세스가 포함되며 정확한 순간 최대가 아니다.

|쌍|2B 생성초|8B 전처리초|8B 생성초|8B 토큰|
|---|---:|---:|---:|---:|
|P1|1.795195|0.024356|1.938899|18|
|P2|0.996072|0.008831|1.578699|18|
|P3|0.771605|0.010392|1.486642|19|
|P4|0.656595|0.009701|1.329151|18|
|P5|0.746038|0.008493|1.622301|18|
|P6|0.756043|0.009428|2.035112|20|

별도 준비 비용: 가중치 다운로드1380.247초, 공식 바이트 검증12.874초(소규모 사전 probe까지 합친 총 네트워크 시간 아님). 다운로드 중 일시 DNS 재시도는 원래 다운로드에서 복구했고 모델/전송 방식 변경은 없었다. 실행 때 enqueue검증66.665초, 큐 자식 계약검증11.540초, 원본 검증13.097초, 체크포인트 검증8.100초, 6쌍 loop(저장 포함)14.004초, 함수 전체47.852초, queue attempt69.211초, 바깥 CLI wall71.235초다. 서로 포함 관계이므로 더하지 않는다. 기존2B 생성 시간에 이 검증 비용을 섞지 않는다.

실제 적재 직전 free8374MiB로8192MiB gate를 통과했다. 적재 후 전체 사용/여유8868/1186MiB, 실행 중 최소 표본 여유863MiB다. 적재 peak allocated/reserved는7,238,658,048/7,272,923,136bytes. 성공했지만 다른 GPU 작업과 함께 안정적으로 운용할 여유를 보장하지 않는다.

## 재현과 보존

기존 큐 CLI의 실제 실행 경로는 다음이다. 아래 ID는 종료된 실행의 기록이며 복사해 재실행하지 않는다. 후속 재실행은 새 활성 배정과 별도 승인이 필요하다. `CANONICAL_RUNTIME`은 기존 로컬 설정의 GPU runtime을 의미한다.

```bash
.venv-vlm-batch02/bin/python -m mvp.cli --runtime "$CANONICAL_RUNTIME" enqueue --phase appearance-8b --view full_frame --job-key exp0038-appearance-8b-v1 --run-id run_3d23462a014a --task-id task_144932ec63a8 --dispatch-id ctx_95618a8e831d --owner term_0bdcc883-9ff8-4f61-aa53-454f600ed090
.venv-vlm-batch02/bin/python -m mvp.cli --runtime "$CANONICAL_RUNTIME" run-once --job-id 1b0a11e9be66448885dc023f5d543d11
.venv/bin/python scripts/exp0038_compare_results.py --attempt-dir outputs/mvp0001/EXP-0038/2045864aebe541f6bda49875a03efc6e --output outputs/exp0038/comparison-v1
```

마지막 명령은 이미 만든 패널의 생성 기록이다. 기존 출력 위 덮어쓰기는 하지 않는다. 실제 출력은 위 attempt 디렉터리, 원본/실제 입력 비교판은 `outputs/exp0038/comparison-v1/`, 원래 전체 프레임·입력 근거는 `outputs/exp0034/pairs-v1/`에 로컬 보관한다. raw 답변/processor arrays/가중치/runtime/DB/로그는 게시하지 않는다. 공개 측정값은 [metrics](../../records/EXP-0038/metrics.json)에 원본 해시·JSON pointer로 결속한다.

CPU 구현81개와 독립 준비 검토95개 검사가 통과했다(중복 합산 금지). 실제 실행 후 독립 아티팩트 감사106개 검사가 통과했다. 보호3174파일/기존48jobs·48attempts/실행소스29파일이 불변이고 새job·attempt각1개만 추가됐다. 실제 실행 성공과 외형 품질 충족은 별개다.

## 결정 및 전달

**8B 기본 적용 보류.** 가림에서 유보하는 작은 이득과 원문 형식은 개선됐지만 혼합 입력의 호환 단정은 남고 다른 의복 대조의 최종 구분은 약화됐다. 더 높은 비용을 감수할 품질 근거가 부족하다. 기존 MVP를 유지하고 이번 승인 범위는 종료한다. 새로운 모델·질문·입력·추론 실험을 자동 시작하지 않는다.

[독립 검토](../reviews/EXP-0038-independent-review.md)는 코드/원시 출력/수치/결론의 별도 감사이며 새 사용자 동일인 검수는 아니다. [전달 기록](EXP-0038-delivery.md)에서 GitHub와 실제 웹 화면을 별도 확인한다. 담당3의 immutable 최초 배정은 CPU 준비 Task `task_5e783fa73799` 이력이고, 이번 활성 GPU 실행 Task와 다르다. 기존 카드를 덮어쓰거나 GPU 실행 중 카드가 새 담당을 표시했다고 주장하지 않는다. 완료 결과·실측 그래프·12개 원본/입력 이미지·검토를 기존 화면에 연결하며 웹 기능은 변경하지 않는다.
