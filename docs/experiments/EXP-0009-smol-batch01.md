# EXP-0009 — SmolVLM2-2.2B 첫 공통 VLM 배치 기준 설정

- 날짜/담당: 2026-10-28, slot2 Sol high. 총괄의 세션 관측은 gpt-6.1-sol/high이며 모델 자기소개와 구분한다.
- 상태: **실제 공통 큐 기준 실행 6/6 완료, 형식 6/6 통과, 행동 설명 효용 미확인·채택 보류**. 총괄은 이번 Smol 개선 실행을 하지 않기로 결정했다.
- 계약: [BATCH-0001](BATCH-0001-plan.md), [완료 절차](../orchestration/EXPERIMENT_DELIVERY.md), ADR-0012/0014. 독립 검토·등록·게시·실제 화면 확인은 총괄 담당이다.
- native Task `task_e56ab41484b8`, Dispatch `ctx_b06f6387b019`, Run `run_3d23462a014a`.
- 실제 실행 코드 SHA `92f447da9339d01a406e9c9b12d7a50966ba6789`, adapter 준비 커밋 `b23e216bad56e4cdff3e5f553f87cefa56c12567`.

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

두 샤드의 실제 다운로드 후 크기와 SHA256이 위 공식 값과 모두 일치했다. 공식 metadata 및 선택한 총15개 파일의 실제 크기/SHA256을 로컬 provenance에 저장했다. safetensors header 확인은 저장 dtype F32, tensor657개·parameter2,246,784,880개이며 이 준비 검사는 모델을 구성하지 않았다. 원본 가중치·원시 응답·미디어·환경·로컬 receipt는 Git 제외다.

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

## 실제 큐 실행과 무결성

총괄의 blocking native ask 응답으로 Qwen job 성공 및 공통 큐 go를 받았다. 같은 canonical 큐에서 Qwen 성공과 미해결/대기 작업 부재를 확인한 뒤 등록된 `vlm-batch01` 명령 하나를 enqueue하고 `Queue.run_once()`를 한 번 호출했다. 다른 GPU 실행 경로는 사용하지 않았다. 2026-10-28 08:55:34.422782~08:55:53.464330 UTC의 첫 attempt가 exit0/succeeded이며 execution retry0, OOM0, 개선 실행0이다. 큐 시작~종료 19.042초는 모델 생성만의 시간이 아니다.

- job `d3de9ab35e7c4ecbb5fdce28c2740c9d`, attempt `ef353740b07d46d79ddb030e8d22ecd5`, owner slot2, timeout900초.
- input hash `0242565dd158a78adfc67a924148ffee3ff11f0b178fc8c41276cad2ce8213d4`.
- config hash `f33570821128022d1adaa3c36113f48709fc30fe20126ebd5251953933da634c`.
- source hash `b6b5f2c0fd51b99c226cbef2d809401a4dad4edff97dec48334be47bca4ed138`.
- 고정 공통 prompt SHA256 `049ec4a6274443fcf8e3069914e53b2913aefa6f4a13ca049cc4001fa8def7a6`.

실제 호출은 위 코드 SHA의 `Queue.enqueue(job_key='BATCH-0001-EXP-0009-baseline', run_id=…, task_id=…, dispatch_id=…, owner='slot2', command='vlm-batch01', input_value=input_contract('smol'), config={'adapter':'smol','settings':SETTINGS}, timeout=900)` → `Queue.run_once()`다. 생략한 native IDs는 이 보고서 상단과 같다. 큐가 canonical lock을 상속하고 source/input/config를 검증한 offline runner만 실행한다. 완료 job을 다시 실행하지 않는다. 정확한 호출 인수와 queue/로컬 evidence mapping은 Git 제외 receipt에 남겼다.

실제 RTX3080에서 모든 parameter가 cuda:0·BF16이었고 model/text/vision attention이 모두 SDPA임을 기록했다. CPU offload·양자화 없음. 전체 입력1215토큰, visual810토큰, 실제10프레임/384×384, padding0을 여섯 클립 각각 확인했다. config의 use_cache=False와 generation_config의 use_cache=True를 별도 기록했으며 실행 전 설정을 바꾸지 않았다. generation의 실제 설정은 해당 Transformers generate 경로를 따른다.

## 정량 결과 — 실행·형식과 행동 의미 분리

| 클립 | NPY 로드 초 | 전처리 초 | 생성 초 | 출력 토큰 | strict / 허용후처리 |
| --- | ---: | ---: | ---: | ---: | --- |
| clip01 | 0.023030 | 0.073817 | 2.353774 | 47 | 통과 / 통과 |
| clip02 | 0.005988 | 0.067287 | 1.861021 | 58 | 통과 / 통과 |
| clip03 | 0.005240 | 0.056526 | 1.223821 | 47 | 통과 / 통과 |
| clip04 | 0.009274 | 0.060743 | 1.425304 | 47 | 통과 / 통과 |
| clip05 | 0.007580 | 0.050753 | 2.124995 | 70 | 통과 / 통과 |
| clip06 | 0.011636 | 0.055665 | 2.257860 | 86 | 통과 / 통과 |

모델+processor load 2.747829초, CUDA동기화 포함. 직전 다운로드·전체 해시로 파일 캐시가 데워졌으므로 cold-load benchmark가 아니다. 생성 평균1.874462초, p50 1.993008초, p95 2.329796초, 합11.246775초. p50/p95는 서로 다른 개발 클립 6개 각1회에 NumPy linear percentile을 적용한 설명 통계이며 반복실험 신뢰구간이 아니다. 출력 총355토큰은 종료토큰 포함 실제 생성ID 길이이고 384토큰 도달0/6이다.

전처리 평균0.060799초는 processor·토큰화·BF16변환·GPU전송·동기화이며 NPY 로드와 검수시트 생성은 제외한다. NPY 캐시 로드 평균0.010458초는 원본 영상의 최초 디코딩과 다르다. 생성 시간은 generate+GPU동기화만이며 출력 decode/저장·검수시트·사전클립확보·대기는 제외한다. 선택한5초 구간의 생성 시간을 사건 탐지 지연이나 실시간 FPS로 바꾸지 않는다.

load 시 peak allocated4,531,499,520bytes/reserved4,630,511,616bytes. 클립 시작별 reset 이후 전체 최고 allocated **4,851,788,288bytes(4.518580GiB)**, reserved **4,966,055,936bytes(4.625GiB)**로 모델을 포함한다. 장치 전체 nvidia-smi 약0.5초 polling28개는 **1566~6573MiB**, polling오류0이다. 이는 driver·다른 화면 작업까지 포함한 장치 관측이며 순간 최고를 놓칠 수 있다. 서로 다른 메모리 지표를 혼합하지 않는다.

엄격 JSON 전체 문자열과 정확한 키/타입/enum 검사 **6/6**, 허용후처리 검사 **6/6**다. JSON 표준의 바깥 공백은 strict 파서도 허용한다. 실제 후처리는 여섯 응답의 양끝 공백만 제거했으며 펜스·잘림 복구·enum 수정·의미 수정은 없다. 전체 허용 enum을 무조건 나열해도 이 구조 검사는 통과하므로 **형식6/6을 행동 정확도6/6으로 해석하지 않는다**. 실제 원문을 저장한 뒤 독립 재파싱으로 runner 결과와 대조했다.

공개 [metrics](../../records/EXP-0009/metrics.json)는 위 숫자와 원천 SHA256을 연결한다. 원시 파일 경로 대신 안전한 논리 provenance 참조를 사용하며 실제 로컬 mapping은 별도 artifact inventory에만 있다. 최종 행동 accuracy/F1 및 원본영상 최초 decode 시간은 null이다.

## 행동 설명 검토 — 기존 관찰 초안과 텍스트 대조

아래는 원문 전체를 게시하지 않은 정성 요약이다. [고정 manifest](../../configs/vlm_exp0007_manifest.json)와 [EXP-0007 관찰](EXP-0007-local-vlm-action-analysis.md)에 대조했으며 이번 클라우드 작업자가 실제 CCTV를 새로 시각 검수하지 않았다. 과거 관찰은 확정 사용자 GT가 아니다.

| 클립·기존 초안 | 응답의 공개 요약 | 부합·누락·추가 설명과 유보 |
| --- | --- | --- |
| 01 접근·대기 | 행동 범주는 통행/대기지만 근거는 경계 넘기 | 통행/대기는 부분 부합. 근거의 넘기는 접근 초안 대비 뒷받침되지 않으며 범주와도 충돌한다. 완료 미확인, 불확실은 추상적 표현뿐이다. |
| 02 문 위 몸 올리기·넘기 진행 | 통행/대기만 분류하고 근거도 같은 범주 이름 | 기존 초안의 핵심 몸 상승/넘기 진행을 누락한다. 완료 미확인은 유지하지만 불확실 필드는 비어 가림·중첩을 설명하지 못한다. 사람 로컬 검수 대상이다. |
| 03 원거리 보행·비이벤트 후보 | 통행/대기 범주와 경계 넘기 근거가 충돌 | 보행은 부분 부합하나 넘기 근거는 기존 초안 대비 뒷받침되지 않는다. 완료는 판단 불가지만 작은 사람 등의 구체 불확실은 없다. 확정 음성 GT로 평가하지 않는다. |
| 04 문에 몸/다리 올리기 | 통행/대기 범주, 근거는 경계 넘기 | 핵심 넘기 시도/진행을 올바른 범주로 구분하지 못하고 근거와 충돌한다. 넘기 단어 하나를 올바른 동작 이해로 인정하지 않는다. 완료 미확인·추상적 불확실만 남는다. |
| 05 또 다른 몸 올리기 | 허용 행동 다섯 개를 전부 열거, 근거는 통행/대기라는 범주 이름 | 실제 여러 행동을 관찰했다는 성공으로 세지 않는다. 경계/신체 자세 변화의 구체 근거 없이 모든 enum을 되풀이해 넘기 이해는 미확인이다. 유보 필드도 항목 이름 반복 수준이다. |
| 06 접촉 후보·차량/원거리 가림 | 허용 다섯 행동 전부 열거, 근거는 통행/대기라는 이름 | 접촉·넘기·판단 불가를 동시에 적었다고 적절한 유보로 세지 않는다. 가림·사람 크기의 구체 근거가 없어 판단 유보 효용은 미확인이다. 핵심 사람 로컬 검수 대상으로 남긴다. |

반대편 이동 완료를 observed로 단정한 응답0/6, 위법/권한/의도를 단정한 설명은 이번 텍스트에 없다. 그러나 이를 완료 판별 능력이나 환각률의 일반화 증거로 사용하지 않는다. 01/03의 근거 없는 넘기, 02의 핵심 누락, 04의 범주/근거 충돌, 05/06의 전 enum 반복을 실패로 보존한다. 특히 05의 넘기·06의 판단불가 enum을 의미 성공으로 계산하지 않는다.

## 보존·로컬 산출물·다음 결정

기존 두 환경의 package inventory와 12개 고정 입력 파일의 실행 전후 크기/SHA256이 모두 동일했다. 여섯 클립의 실제 resize RGB 해시도 실행 metadata와 모두 일치했고 clip별10개 고유 프레임을 확인했다. 공식 라벨·기존 EXP1~7 출력·CV코드·원본은 수정하지 않았으며 신규 가중치 한 모델과 새 환경/출력만 추가했다. 검증의 범위는 선택 입력 해시와 package inventory이며 모든 과거 원본/가중치 바이트의 재해싱을 주장하지 않는다.

로컬 전용으로 가중치 출처/해시, 환경·입력 보존 기준, CPU검증, frozen baseline, queue enqueue/종료 receipt, 원문·생성 token IDs·expanded prompt, clip별 metadata/측정치, 실제 resize RGB·입력 검수시트, 장치 polling, 측정 집계와 artifact inventory를 보존한다. 기존 source 영상과 실제 표본을 표시하는 비교 영상의 등록/재생·seek는 총괄의 별도 확인 대상이다. worker가 HTTP상태만으로 완료를 선언하지 않는다.

작업자 의견: 이번 기준은 RTX3080에서 실행 가능하고 구조화 형식은 준수하지만, 구체 동작 설명과 불확실성 처리의 효용은 확인하지 못해 **기본 연동/채택을 보류**한다. 공식 정사각 변형·작은 사람 정보 손실·whole-second timestamp는 입력 한계이나 오류의 인과 원인을 입증한 것은 아니다. 역순/단일프레임 대조도 하지 않아 시간 순서를 활용했다고 주장하지 않는다. 다른 모델보다 빠른 생성만으로 우수성을 주장하지 않으며 해상도·영상 토큰·출력 길이가 다르다.

총괄은 원문 확인 후, 일반적인 범주 반복과 근거 충돌에 대해 사후 prompt tuning 없이 효과를 귀속할 한 가지 개선을 정하기 어렵다고 판단해 **이번 Smol 개선 실험을 하지 않기로 결정**했다. 추가 GPU 작업 없이 제출한다. 독립 Astra 검토, 총괄의 report/metrics SHA 검토·등록, GitHub 게시 확인, 실제 로컬 담당 카드·보고서·그래프·영상·검토 표시 확인은 총괄 담당으로 아직 완료 선언하지 않는다. 전역 HANDOFF 갱신도 총괄이 통합한다.
