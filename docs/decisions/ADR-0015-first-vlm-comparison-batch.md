# ADR-0015 — 두 소형 VLM의 독립 행동 분석 비교

- 일자: 2026-10-28
- 상태: 개발 배치 실행 승인; 기본 파이프라인 채택 결정과 별개
- 계약: [BATCH-0001](../experiments/BATCH-0001-plan.md)

## 문제와 선택

EXP-0007은 Qwen3-VL-2B가 작은 CCTV 사람의 넘기 행동을 놓치거나, 보이지 않는 문 열기 등을 설명할 수 있음을 보였다. 형식 실패도 있었지만 JSON 형식 준수와 행동 이해는 다른 평가다. 같은 6개 개발 클립에서 기존 Qwen과 **SmolVLM2-2.2B 한 모델만 추가**해 비교한다. 세 번째 후보는 이번 예산에서 선택하지 않는다.

| 항목 | Qwen3-VL-2B-Instruct | SmolVLM2-2.2B-Instruct |
|---|---|---|
| 공식 배포 | Qwen/Qwen3-VL-2B-Instruct | HuggingFaceTB/SmolVLM2-2.2B-Instruct |
| revision | `89644892e4d85e24eaac8bacfd4f463576704203` | `482adb537c021c86670beed01cd58990d01e72e4` |
| 라이선스 | Apache-2.0 | Apache-2.0 |
| 파일 용량 | 4,255,140,312 bytes, 기존 확보 | 8,987,224,056 bytes, 공식 F32 두 shard |
| 실행 우선 조건 | BF16, SDPA, 비양자화, batch1, CUDA0 | BF16 변환 로드, SDPA, 비양자화, batch1, CUDA0 |
| 이유 | 기존 실패를 같은 새 질문으로 재측정 | 다른 경량 계열의 공식 영상 입력, 작은 GPU에서 실행 가능한 후보 |

공식 [Qwen 모델 카드](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct), [Smol 모델 카드](https://huggingface.co/HuggingFaceTB/SmolVLM2-2.2B-Instruct), [Transformers 4.57.1 SmolVLM 문서](https://huggingface.co/docs/transformers/v4.57.1/en/model_doc/smolvlm)를 확인했다. Smol 카드의 영상 메모리 약 5.2GB는 **제작자 보고**이며 현재 장비 실측이 아니다. 다운로드 파일 크기도 GPU 사용량을 뜻하지 않는다. 공식 README 예제의 flash-attn을 필수로 가정하지 않고, 설치 버전의 SDPA 경로와 공식 processor를 확인한다.

실행 전 RTX 3080은 총 10,240MiB 중 사용 1,914MiB, 여유 8,140MiB였다. 다른 프로세스와 WSL/화면 점유로 변할 수 있으므로 작업 시작 때 다시 기록한다. 각 job은 공통 GPU 큐에서만 실행하며 시간 제한 900초, 실행 오류 재시도 최대1회다. OOM을 모델 크기만으로 배제하지 않는다.

Smol의 공식 언어가 영어이므로 **두 모델에 같은 영어 질문**을 미리 고정했다. EXP-0007의 한국어 질문 결과와는 모델 외 조건도 달라져 정확 재현·언어 효과의 분리 실험이 아니다. 새 두 후보 간 비교에서도 공식 전처리/시각 토큰량 차이를 기록하고 아키텍처 하나의 효과로 단정하지 않는다.

## 가중치 무결성

- Qwen `model.safetensors`: `7de1838c87a5349b016c26a1c3f7d2bc400a3d485f95ef39a7059ffd734977a0`
- Smol shard1: `7c88a90e78f567460b2369a0369cc4dafbfda5607c9cb090b30fa4437b0282f2`
- Smol shard2: `cf3d0958a8240f71054a6812038f2a6bfbe2e5124573a3b363f6b120c9a52657`

위 값은 공식 pinned 배포 metadata 기준이다. 다운로드 후 실제 파일 해시·환경 freeze·사용 장치·정밀도는 실행 provenance로 대조한다. 기존 CV 및 VLM 환경은 변경하지 않고 필요하면 별도 VLM 배치 환경을 만든다.

## 판단과 번복 조건

넘기 누락, 근거 없는 동작/완료 설명, 불확실성 처리, 형식, 비용을 따로 검토한다. 담당 Sol high와 독립 Astra high가 공개 요약과 원문·측정 근거를 확인하되 CCTV 픽셀을 클라우드 에이전트로 전송하지 않는다. 영상 의미가 불확실한 사례는 로컬 웹의 사람 확인 대상으로 유지한다. 6개 클립은 개발 자료이며 정밀 정답·독립 테스트가 아니다.

기준 결과의 구체적 실패가 있을 때만 후보당 개선 조건 하나를 총괄이 사전 고정한다. 프롬프트를 특정 답에 맞춰 반복 수정하지 않는다. 실행·등록·웹 확인 성공은 모델 채택 근거가 아니며, 두 후보 모두 채택 보류할 수 있다. 실제 출력에서 근거 있는 행동 구분이 지속적으로 가능하고 추가 독립 검수가 확보될 때 다음 개발 후보를 재검토한다.
