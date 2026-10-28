# EXP-0009 — SmolVLM2-2.2B 첫 공통 VLM 배치 기준 설정

- 날짜/담당: 2026-10-28, slot2 Sol high. 총괄의 세션 관측은 gpt-6.1-sol/high이며 모델 자기소개와 구분한다.
- 상태: **가중치 해시·CPU 준비 검증 완료, 실제 큐 실행 대기**. GPU 실험 성공이나 모델 채택을 뜻하지 않는다.
- 계약: [BATCH-0001](BATCH-0001-plan.md), [완료 절차](../orchestration/EXPERIMENT_DELIVERY.md), ADR-0012/0014. 독립 검토·등록·게시·실제 화면 확인은 총괄 담당이다.
- native Task `task_e56ab41484b8`, Dispatch `ctx_b06f6387b019`, Run `run_3d23462a014a`.

## 가설과 입력·평가

공식 영상 입력을 지원하는 작은 VLM 한 개가 같은 개발 클립의 경계 접촉·넘기·판단 유보를 얼마나 설명하는지, 형식 준수와 실행 비용을 분리해 확인한다. Qwen과 동일 전처리 예산이나 언어만의 효과를 가정하지 않는다. 새 학습·CV 연동·자동 채택은 없다.

기존 EXP-0007의 익명 clip01~06, 각 5초 구간에서 원본 PTS로 고른 전체 화면 RGB 10개를 순서대로 재사용한다. 목표는 2fps이며 clip03은 원본 29.97002997002997fps라 실제 상대 PTS가 0, 0.5005, …, 4.5045초다. 다른 다섯 클립은 0, 0.5, …, 4.5초다. 원본 PTS·time_base·상대 인덱스·입력 해시를 보존한다. 기존 입력 추출/원본 디코딩 시간은 이번 추론 시간으로 재측정하지 않는다.

평가는 6개 개발 클립의 **기존 관찰 초안 대비 비교**다. 모델 입력은 원본 RGB 한 video, 익명 Clip ID, 고정 영어 공통 질문뿐이다. manifest 관찰·공식 라벨·이전 응답·파일명 단서는 입력하지 않는다. 02/06 등 핵심 의미는 사람의 로컬 검수 대상으로 남긴다. 모델 응답은 정답이 아니며 확정 GT 기반 accuracy/F1/일반화 성능은 미측정이다.

## 공식 출처와 가중치

[공식 모델 카드](https://huggingface.co/HuggingFaceTB/SmolVLM2-2.2B-Instruct/tree/482adb537c021c86670beed01cd58990d01e72e4)는 영어·Apache-2.0과 영상 입력을 명시한다. [Transformers 4.57.1 문서](https://huggingface.co/docs/transformers/v4.57.1/model_doc/smolvlm)는 영상 및 SDPA 지원을 표시한다. 카드의 GPU 용량·벤치마크 수치를 SceneGuard 실측으로 사용하지 않는다.

로컬 HF 공식 API 확인: revision `482adb537c021c86670beed01cd58990d01e72e4`, license `apache-2.0`, language `[en]`. 다운로드는 이 한 모델의 고정 revision 파일만 허용한다. 샤드가 F32로 배포되는 것과 BF16 실행을 구분한다.

| 공식 샤드 | bytes | 공식 LFS SHA256 |
| --- | ---: | --- |
| model-00001-of-00002.safetensors | 4,959,390,584 | `7c88a90e78f567460b2369a0369cc4dafbfda5607c9cb090b30fa4437b0282f2` |
| model-00002-of-00002.safetensors | 4,027,833,472 | `cf3d0958a8240f71054a6812038f2a6bfbe2e5124573a3b363f6b120c9a52657` |

두 샤드의 실제 다운로드 후 크기와 SHA256이 위 공식 값과 모두 일치했다. 공식 metadata 및 선택한 총15개 파일의 실제 크기/SHA256을 로컬 provenance에 저장했다. safetensors header만 읽어 저장 dtype과 tensor 수를 별도 확인하며 모델을 구성하지 않는다. 원본 가중치·원시 응답·미디어·환경·로컬 receipt는 Git 제외다.

## 실행 전 고정과 실제 전처리

공통 runtime 설정은 seed0, greedy, max_new_tokens384, repetition_penalty1.0, batch1, 비양자화 BF16, SDPA, cuda:0다. 새 격리 batch 환경에 Python3.10.12, torch2.5.1+cu124, torchvision0.20.1+cu124, transformers4.57.1 등 기존 lock을 설치하고 num2words0.5.14/docopt0.6.2만 추가했다. 총 44개 패키지이며 `requirements-vlm-batch-lock.txt`가 기존 lock을 포함한다. FlashAttention 설치는 없다. 기존 두 환경의 package inventory와 12개 입력 파일 해시를 실행 전 보존 기준으로 저장했다.

총괄은 생성 전에 아래 공식 video 기준을 수락했다. `vlm_batch.smol.Adapter(model_dir, settings)`가 local_files_only로 processor/model을 로드하고 `prepare`가 입력·metadata·로컬 검수용 RGB를 반환한다. 실제 모델 로드는 공통 큐에서만 수행한다.

```json
{"do_sample_frames": false, "do_resize": true, "size": {"longest_edge": 384}, "do_pad": true}
```

로컬 공식 4.57.1 구현과 CPU 합성 영상으로 확인한 처리:

- 한 `<video>`를 공식 영상 template으로 확장한다. 열 개 독립 이미지 대화로 바꾸지 않는다. 추가 sampling·반복·프레임 순서 변경·정답 crop은 없다.
- 1080×1920 전체 화면 → 216×384 → 384×384. 공식 video processor는 image splitting을 사용하지 않는다. **전체 화면은 남지만 종횡비가 변형된다.** LANCZOS 요청에 대한 공식 torch fallback은 BICUBIC이며 antialias를 사용한다.
- rescale1/255, mean/std 각0.5. pixel_values `[1,10,3,384,384]`, mask `[1,10,384,384]` 전체1, 추가 padding0. 정규화된 pixel_values만 BF16으로 변환하며 토큰/마스크는 정수형을 유지한다. 로컬 검수 RGB는 BF16 변환 전 공식 uint8 resize를 복원한다.
- 14px vision patch의 27×27 grid와 scale3 병합으로 프레임당81, 전체810 visual tokens. 공통 질문의 전체 입력 토큰은 실제 실행마다 기록한다.
- VideoMetadata는 원본 fps와 상대 인덱스를 사용해 정확한 상대 시각을 전달한다. **공식 텍스트 확장은 초 미만을 버려 00:00, 00:00, 00:01, 00:01, …로 표시한다.** 같은 시각 문자열은 프레임 복제를 뜻하지 않는다. 세밀한 시각과 원본 native PTS는 별도 metadata에 보존한다.

재현용 CPU 명령은 환경에서 해석한 로컬 모델 디렉터리와 새 receipt 파일을 인수로 받는다. 모델을 구성하거나 CUDA를 초기화하지 않는다.

```sh
python -m vlm_batch.smol --model-dir "$LOCAL_MODEL_DIR" --prompt configs/vlm_batch01_prompt.txt --output "$CPU_RECEIPT"
```

## 준비 검증과 실패 기록

CPU 합성 검증 11항목 통과: 한 native video, 열 개 고유 프레임의 순서, sampling 호출 금지, 사방 경계 보존, 평가 metadata의 텍스트 유출 없음, 공식 timestamp10개, 공통 prompt 보존, visual tokens810, 중복 index 거부, 29.97fps native PTS 보존, CUDA 미초기화. 이는 실제 CCTV 행동 결과나 GPU 성공이 아니다.

초기 준비 코드가 정확한 0.5초 간격만 요구해 원본 29.97fps 입력을 거부할 수 있었다. 총괄이 실행 전에 지적했고, 원본 native PTS/index/fps 일치와 목표 sampling에서 한 native frame 이내 오차를 검사하도록 수정했다. 원본 PTS를 반올림하거나 입력을 다시 추출하지 않았으며 GPU retry를 소비한 오류가 아니다.

## 정량 결과와 다음 단계

실제 모델 load/generation 지연·출력 토큰·VRAM·JSON 준수·행동 비교·OOM은 아직 미측정이다. 공통 큐 명령/source·input·config 무결성 검증과 Qwen baseline 종료 후 총괄의 명시적 go를 기다린다. 실행 오류는 job당 명시적 retry 최대1회이며 메모리 실패 시 자동 설정 변경 없이 총괄에게 보고한다. 실행 후 실패를 포함한 실측·정성 한계·공개 metrics와 로컬 artifact 목록을 제출한다. 독립 검토·웹 등록·GitHub 게시·브라우저 재생 확인은 현재 미완료다.
