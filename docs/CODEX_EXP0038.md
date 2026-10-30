# EXP-0038 — 기존 6쌍으로 Qwen 8B의 외형 비교·속도·메모리 확인

사용자 최신 승인(2026-10-31): 파인튜닝·새 데이터 수집·박스 작성 없이, 기존 자료로 더 큰 VLM을 시험한다. 기존 MVP는 그대로 두고 **8B NF4의 비교 품질과 실제 비용**을 확인한다. 이전 실험의 종료 지시는 당시 범위 종료이며 이번 승인을 막지 않는다.

## 현재 준비 상태

- `mvp/exp0038.py`: 로컬 체크포인트 검증, NF4 로더, 기존 6쌍 루프 재사용, 시간/형식 통계와 사후 2B 비교 코드.
- `tests_mvp/test_exp0038.py`: 격리된 CPU 합성 테스트 **24개 통과**. 실제 가중치/Transformers/NF4 적재·실제 CCTV 추론·기존 큐 통합 시험은 **아직 미수행**.
- **기존 큐의 새 phase 등록과 로컬 체크포인트 준비는 아래 절차에 따라 구현해야 한다.** 현재 파일을 단독 실행해 GPU 검증을 우회하지 않는다. 코드 준비를 실험 완료로 보고하지 않는다.

## 비교 조건

| 항목 | 이번 고정 조건 |
|---|---|
|모델|`Qwen/Qwen3-VL-8B-Instruct` (Thinking 아님)|
|모델 revision|`0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`|
|양자화|언어 Linear만 NF4, double quant, BF16 compute, uint8 storage|
|비양자화|시각 부분·임베딩·출력 head BF16; 실제 8B의 untied head를 보존|
|실행|CUDA0, SDPA, batch 1, seed 0, CPU/disk offload 없음|
|입력|EXP-0034의 **동일 6쌍·27 이미지 슬롯**, A/B 각각 원래 1–3장|
|질문·파서|`sceneguard.appearance_support.PROMPT`, `prepare_images`, `parse_comparison` 그대로|
|이미지 예산|원래 min 65,536px / max 262,144px; 이미지 수·크롭·순서 변경 없음|
|생성|greedy, max_new_tokens 192, 추가 warmup 생성 없음|
|로드/호출|모델 **한 번 적재**, 원래 순서대로 **6회 생성**|
|기준선|EXP-0034의 저장된 **2B BF16** 6쌍 응답. 4B는 같은 6쌍 실험이 없으므로 직접 비교했다고 쓰지 않음|

이것은 모델 크기뿐 아니라 시각 인코더와 양자화도 다른 **실제 배포 구성 비교**다. BF16 대비 NF4의 효과를 독립적으로 측정한 실험은 아니다. 기존 의심 생성·카드 묶음·검토 저장·영역·ID는 변경하지 않는다. `침입 확인` 자동 승격이나 인물 ID 자동 병합은 하지 않는다.

## 1. 로컬 환경·가중치 준비 (CPU / 외부 전송 없음)

기존 로컬 변경을 보존하면서 최신 main을 반영한다. 이전 4B용 `.venv-vlm-batch02`의 torch/transformers/bitsandbytes 조합을 먼저 확인하고, 호환되면 재사용한다. 기존 환경을 무조건 업그레이드하지 않는다. 필요한 변경은 별도 환경에 한정하고 실제 버전을 기록한다.

공식 Hugging Face의 위 revision에서만 체크포인트를 새 `weights/Qwen3-VL-8B-Instruct/`에 준비한다. NF4로 적재하더라도 다운로드 원본은 BF16이며 공식 저장소는 약 **17.5GB**다. 디스크·호스트 RAM을 먼저 확인하고, 전체 원본 4개 safetensors shard 및 index·processor/tokenizer/config를 보존한다. 파일명만 바꾸어 4B를 8B처럼 쓰지 않는다. 학습/새 데이터 다운로드는 없다.

모델 정보는 `HfApi.model_info(MODEL_ID, revision=REVISION, files_metadata=True)` 등의 공식 metadata로 검증한다. LFS SHA-256과 다운로드 바이트를 대조하고, 작은 파일도 동일 revision에서 가져와 크기·SHA를 기록한다. HF 캐시 symlink 그대로가 아니라 별도 로컬 파일로 준비한다. 생성할 `runtime/EXP-0038/checkpoint.json`의 형식:

```json
{
  "model_id": "Qwen/Qwen3-VL-8B-Instruct",
  "revision": "0c351dd01ed87e9c1b53cbc748cba10e6187ff3b",
  "files": {"각 실제 파일명": {"bytes": 0, "sha256": "실제 다운로드 바이트의 SHA256"}}
}
```

위 bytes/hash는 **설명용**이며 그대로 실행하지 않는다. 실제 모든 필수 파일을 채우고 큐 input contract에 이 receipt와 모든 파일 hash를 포함한다. `verify_checkpoint()`는 로컬 바이트를 검사할 뿐 receipt의 공식 출처를 대신 인증하지 않으므로 다운로드 단계의 공식 metadata 대조도 기록한다.

공식 자료:
- https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct/tree/0c351dd01ed87e9c1b53cbc748cba10e6187ff3b
- https://huggingface.co/docs/transformers/v4.57.1/quantization/bitsandbytes

## 2. 입력은 다시 만들지 않는다

`runtime/EXP-0034/appearance_manifest.json`과 기존 원본 `.npy` 크롭을 읽기 전용으로 재사용한다. 기대 manifest SHA는 `996ecdb638b624d69c54a70ff0e44027c95a3d2dd04a78efa00a69856af3ec90`. 6쌍의 이미지 슬롯은 순서대로 **5/5/5/4/4/4**다.

`mvp.exp0034_appearance.bind_inputs()`와 `verify_native_crops()`로 원본 PTS·RGB·관측 결속을 CPU에서 확인한다. EXP-0034의 `IDENTITY`/옛 실행 승인을 재사용하지 않고 **자료만** 재사용한다. 현재 모델에게 이전 답변·검수 의견·영상 ID·정답을 프롬프트로 주지 않는다.

비교 기준 응답은 로컬 `outputs/mvp0001/EXP-0034/565b65a15fee492a8aea0e29bde1cb4e/appearance_results.json`의 6개 `completed` 행이다. 실제 경로와 원문을 확인하고 보고서 표를 응답 파일 대신 사용하지 않는다. 사후 비교용이며 8B 생성이 끝난 후에만 답변을 읽는다.

8B 자체의 공식 processor/tokenizer를 사용하되 이미지 예산·A/B 순서는 유지한다. 실제 processor 이미지·grid·확장 질문·입력 토큰을 저장해 기준선과 대조한다. 모델별 tokenizer 차이를 숨기거나 2B processor를 억지로 이식하지 않는다. 동일하지 않으면 차이를 보고한다.

## 3. 기존 큐에 새 phase만 연결

새 큐/서버를 만들지 말고 기존 `mvp-0001`에 **`appearance-8b`** phase를 추가한다. 기존 `appearance-compare`의 기본 모델·승인·결과 경로는 건드리지 않는다.

필요한 제한된 통합:

1. `orchestration/mvp_command.py`: PHASES, source binding, 8B 전용 input contract, 분리 환경의 interpreter, output `outputs/mvp0001/EXP-0038/<attempt>/` 선택을 추가한다. **기존 2B 단일 shard 검사 경로를 8B에 적용하지 않는다.** config/settings가 실제 192토큰·NF4 조건과 맞도록 분리하고, wrapper의 옛 384토큰 값을 실제 설정처럼 보고하지 않는다.
2. `mvp/runner.py`: 기존 lock/부모 프로세스/실제 task·dispatch 검사 후 새 phase를 `mvp.exp0038.run_six_pairs()`에 연결한다. 기존 2B `QwenAnalyzer`를 먼저 적재하지 않는다. 현재 활성 Run/Task/Dispatch는 로컬에서 실제 값으로 조회하고, EXP-0034의 종료된 ID를 복사하지 않는다.
3. 코드 결속에는 새 모듈뿐 아니라 재사용하는 `mvp.exp0034_appearance`, `sceneguard.appearance_support`, `batch02_vlm.runner.inventory`, 양자화 정의와 실제 실행 환경을 포함한다. 다운로드/전체 입력 검증/모델 적재 비용과 요청별 생성 비용을 분리한다. 무거운 환경 전체 검증을 각 이미지 쌍의 추론 시간에 합치지 않는다.
4. 기존 exact-job 실행과 canonical lease를 사용한다. 한 job/한 model load/6 generate다. GPU free gate는 이번 시작값 **8,192MiB**이고 충분한 실제 여유가 있는지 확인한다. 이 gate 통과가 8B 적재 성공 보장은 아니다. 무관한 사용자 프로세스를 강제 종료하지 않는다.

`load_analyzer()`는 기존 lease를 확인한 뒤 실제 NF4 module/quant-state/vision/head dtype과 전체 CUDA0 배치를 점검한다. CPU/disk 자동 offload, GGUF 대체, 다른 모델 다운로드, 프레임 축소/저해상도 fallback은 이번 범위에 없다. OOM/부족 시 해당 stage와 실제 메모리를 기록하고 멈춘다. 오류로 생긴 미실행을 `판단 불가` 응답이나 정확도 실패로 계산하지 않는다.

GPU 호출 전 구현/테스트를 완료한다. 실행 전 어댑터 호환 오류는 수정할 수 있지만, 결과를 본 후 프롬프트·입력·모델을 바꿔 좋은 답을 고르는 재실험은 하지 않는다. 일부 생성 후 실패하면 완료된 응답은 보존하고 미완료를 분리해 보고한다.

## 4. 실제 실행·비교·화면 등록

CPU에서 먼저:

```bash
python -m unittest discover -s tests_mvp -p test_exp0038.py -v
```

이후 새 phase·기존 큐 회귀, 다중 이미지 processor CPU 준비 검사를 수행하고 승인된 6쌍을 한 번 실행한다. 전용 phase는 로컬에서 연결한 실제 CLI에 등록하고 실행 명령을 결과 문서에 남긴다. **존재하지 않는 enqueue 명령을 문서만 보고 실행했다고 쓰지 않는다.**

실측 보고에는 다음을 구분한다.

- 다운로드/검증 시간, 모델 적재·양자화 시간, 첫 비교 생성 시간, 나머지 5쌍의 개별 생성·전처리 시간, 전체 loop·queue wall.
- 생성된 토큰 수, token limit 도달 여부, peak allocated/reserved, 전체 장치 사용량 및 CPU offload 여부. 첫 입력과 다른 입력의 차이가 있으므로 5쌍 중앙값을 반복 측정 p95/운영 SLA처럼 쓰지 않는다.
- 파서 성공률, 모델이 **실제로 선택한** unknown/unavailable, 이전 오류의 유지/개선 여부. 파싱 오류의 대체 unknown은 실제 보류와 분리한다.
- 상의/하의/가방의 공통 가시성을 지켰는지, P5 혼합을 단일인 호환으로 단정하는지, P2/P6에서 보이지 않는 하의를 차이로 쓰는지. 명확히 다른 의복 P3/P4 구분을 잃었는지도 같이 본다. 어려운 입력을 모두 unknown으로 만드는 것만으로 성능 향상이라고 하지 않는다.

기존 원본/processor 비교판을 재사용해 2B와 8B 결과를 나란히 보여준다. 새 실사용자 라벨 작업이나 바운딩박스 제작을 요구하지 않는다. 기존 사용자 관찰과 로컬 검수 초안을 구분하고, 불명확한 정체는 계속 미확정으로 남긴다. 6쌍은 독립 성능 시험이 아니며 공식 벤치마크가 우리 정확도가 아니다.

기존 담당3에 EXP-0038 보고서·비교표·속도/메모리·이미지를 등록하고 실제 화면에서 확인한다. 원본·인물 이미지·가중치·runtime/DB·인증정보·원시 응답은 로컬에 두고 GitHub에는 코드·비식별 결과만 게시한다. 영상 파일을 외부 API에 올리지 않는다.

## 종료 판단

**질문 1:** 같은 자료에서 2B의 가림·혼합 처리 오류가 줄었는가?  
**질문 2:** 한 번 적재한 뒤 필요한 비교를 감당할 시간·메모리인가?

성공하면 8B를 보조 의견 모델의 도입 후보로 제안한다. 이번 승인만으로 기존 MVP 모델을 자동 교체하거나 의심 경보를 VLM 답변까지 지연시키지 않는다. 적재 성공만으로 이미지 해석 향상을 주장하지 않고, 형식만 좋아졌다면 그대로 보고한다. 실패해도 기존 의심·카드·검토 저장은 유지한다.

**이번 원격 단계는 코드/합성 시험/실행 지침 준비. 로컬 큐 연결과 실제 GPU 결과가 있어야 EXP-0038 실행 완료다.**
