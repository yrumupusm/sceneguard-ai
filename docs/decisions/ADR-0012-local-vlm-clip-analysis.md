# ADR-0012 — 독립 로컬 VLM 한 모델의 사전 선택

2026-10-28 / 사용자 승인: 기존 VLM 금지는 이번 독립 행동 분석에만 해제. CV 자동 연결·재학습·새 detector/tracker/UI 금지 유지. EXP-0006 기본 적용 보류.

선정: **Qwen/Qwen3-VL-2B-Instruct**, revision `89644892e4d85e24eaac8bacfd4f463576704203`. 공식 [모델 카드](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct), [Qwen 영상 입력 예제](https://github.com/QwenLM/Qwen3-VL#quickstart), [Transformers 4.57.1 문서](https://huggingface.co/docs/transformers/v4.57.1/model_doc/qwen3_vl) 확인. Apache-2.0(HF 공식 메타데이터), safetensors 4,255,140,312 bytes, 공식 LFS SHA256 `7de1838c87a5349b016c26a1c3f7d2bc400a3d485f95ef39a7059ffd734977a0`. 영상 배열과 timestamp metadata 지원. 이미지 한 장 모드가 아니다.

2B Instruct는 제한된 10GB GPU에서 첫 실행을 시도할 작은 모델이며 짧은 구조화 응답 목적에 맞는다. 더 큰 모델/Thinking/양자화 모델을 추가로 다운로드하지 않는다. 모델 크기만으로 실행 가능성을 보장하지 않는다. 시작 nvidia-smi 10240MiB 중1247MiB 사용, 여유8993MiB. 배치1 BF16 비양자화, CUDA:0, SDPA, CPU offload 없이 시도한다. FlashAttention 별도 빌드와 서버는 설치하지 않는다.

기존 CV `.venv`는 그대로 두고 `.venv-vlm` 사용. torch2.5.1+cu124/torchvision0.20.1+cu124는 새 환경에 독립 설치, transformers4.57.1/accelerate1.11.0/av16.0.1/Pillow12.3.0/NumPy2.2.6. 실제 전체 의존성 lock과 장치/메모리는 결과에 기록한다. 공식 Transformers가 직접 영상 배열을 지원하므로 qwen-vl-utils/torchcodec는 불필요하다. PyAV로 PTS를 통제해 원본을 읽고 공식 processor에 한 video tensor로 전달한다. 외부 추론 API/업로드 없음; 로딩/실행 local_files_only 및 offline 환경.

## 실행 전 고정

`configs/vlm_exp0007_manifest.json`의 6개5초 구간 및 별도 prompt 파일을 고정한다. manifest의 행동/파일명/보고서/JSON/CV출력은 모델에 전달하지 않는다. 익명 clip ID와 공통 질문+원본 RGB 프레임만 전달한다. 전체 화면/기존 비식별화 유지. 결과 보고 구간/프레임/질문 수정 금지.

원본 PTS 기준 start+k*.5초(k=0..9) 이상 첫 프레임을 선택, 순서/중복 검사. 영상별10프레임, processor 추가 sampling 끔. processor resize 한 번: size shortest_edge=16384, longest_edge=3584000(10×448×800의 총 pixel 예산). 실제 결과 해상도/grid/영상 토큰/temporal patch padding은 계측으로 확인한다. 원본 PTS와 모델 상대 timestamp를 모두 저장한다. 전체 화면이 작아져 작은 사람 행동이 사라질 수 있다는 한계 포함.

독립 대화, greedy(do_sample=False), seed0, max_new_tokens=384, repetition_penalty=1.0, 배치1. 출력 파싱 실패/원응답 보존, 정답 유도 예시 없음. 공식 기본 sampling과 다른 실험 생성 설정임을 명시한다.

첫 clip01로 실행 가능성을 확인하고 같은 조건으로 나머지5개 실행한다. OOM이면 한 번만 공통 pixel 예산을 절반으로 줄여 전체 조건을 새 run으로 재시작할 수 있으며 실패/이유/차이를 기록한다. 추가 모델이나 무제한 재시도 금지. OOM이 아니면 입력 예산을 조정하지 않는다.

사람이 미리 고른 클립의 사후 분석이다. CV 경계 후보와 출력 단위가 다르며 같은 정확도로 직접 비교하지 않는다. 검수 초안≠사용자 확정 정답, VLM응답≠새 라벨. loading/preprocess/generation 시간·실제 GPU 메모리를 분리하고 생성 시간만 실시간 탐지 지연으로 보고하지 않는다. 기본 파이프라인 미연결.
