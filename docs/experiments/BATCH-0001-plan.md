# BATCH-0001 — 첫 실제 VLM 비교 배치 실행 전 계약

2026-10-28 사용자 승인. 기존 Qwen부터 공통 GPU 큐에서 실행하고 담당 카드·완료 자료를 함께 확인한다. 기존 EXP1~7/CV/공식 라벨/원본과 환경을 보존한다. 새 총괄/큐/대시보드 기능을 만들지 않는다.

## 예산과 표본

- 이번 선택은 Qwen/Qwen3-VL-2B-Instruct와 HuggingFaceTB/SmolVLM2-2.2B-Instruct **두 후보**. 신규 모델은 Smol 한 개. 셋을 채우지 않는다.
- 후보별 기준 설정1개, 실패 근거에 따른 총괄의 개선 결정 최대1개. 개선 전 별도 설정/가설을 고정한다. 실행 오류는 같은 queue job의 명시적 retry 최대1회. 해소되지 않으면 중단/차단 기록. 의미상 나쁜 답/파싱 실패는 실행 재시도 사유가 아니다.
- baseline EXP-0008(Qwen), EXP-0009(Smol), 개선을 결정할 때만 새 EXP 번호를 배정한다. 실험마다 queue attempt UUID와 출력 폴더를 따로 사용한다. 6클립 생성 후 종료, 무인 반복/추가 모델 없음. job wall timeout 900초, max_new_tokens384, batch1.
- EXP7의 같은 clip01~06 및 원본 표본 10프레임/2fps를 재사용한다. 순서와 원본 PTS/input.json 해시를 확인한다. 클립별 5초, 실제 표본 마지막은 약4.5초. 추가 sampling·resize·padding을 실제 계측한다. 임의 장면 연결/정답 크롭 없음.
- 기존 manifest의 관찰은 평가 전용 초안이다. 모델 입력에는 원본 RGB·익명 clip ID·공통 질문만 전달한다. 공식 JSON/관찰 설명/기존 답변/파일명 단서/CV 표시를 넣지 않는다.

## 공통 과제와 평가

`configs/vlm_batch01_prompt.txt`를 실행 전에 고정한다. Smol 공식 언어가 영어이므로 두 후보 모두 같은 중립 영어 질문과 출력 키를 사용한다. 기존 한국어 EXP7과는 프롬프트/스키마가 다르므로 재현이나 언어만의 효과로 해석하지 않는다. 클립별 독립 대화, seed0, greedy, repetition_penalty1.0, 384토큰. 공식 모델 전처리는 허용하되 동일 토큰량/해상도라고 가정하지 않는다. BF16/SDPA/비양자화/cuda:0를 우선 사용하고 모델 전체가 GPU에 있는지 기록한다.

평가 단위는 6개 개발 클립의 **기존 관찰 초안 대비 비교**다. 행동 부합(부합/부분/불일치/미확정), 실제 넘기 누락(clip02/04/05, 관찰 초안), 근거 없는 동작·완료·의도 설명, 적절한 판단 유보(특히06)를 구분한다. 현재 클라우드 에이전트는 영상을 전송받아 재검수하지 않는다. 과거 기록과 응답의 불일치를 공개 가능한 요약으로 대조하며 의미가 불확실한 핵심02/06은 로컬 입력자료를 사람 확인 대상으로 남긴다. 사용자 확정 GT/정확도/F1/일반화/최적모델이라고 부르지 않는다.

원문 형식 준수는 JSON 전체 문자열과 정확한 키/타입/enum을 검사한다. 공통 후처리는 **문자열 양끝 공백 및 전체를 감싼 단일 ```json 또는 ``` 펜스만 제거**한다. 내부 텍스트 수정, 잘린 JSON 복구, enum 치환/번역, 의미 수정, regex 답 추출은 하지 않는다. strict와 후처리 parse를 별도 보고하며 형식 개선을 행동 개선으로 세지 않는다. 원문·token IDs·실패는 로컬에 보존한다.

비용은 모델 load, 클립별 decode/전처리, generation, 출력 토큰, torch peak allocated/reserved, GPU 전체 polling, error/OOM을 구분한다. 사전 선택된 클립 확보 시간 및 작업자/큐 대기를 generation 지연과 혼동하지 않는다. 캐시 입력 추출 재사용으로 최초 원본 디코딩은 별도 미측정/기존 준비로 기록한다.

## 최소 코드 연결 계약

기존 canonical runtime `sceneguard-orca-lab/runtime/orca-lab/gpu-queue`와 inherited flock을 사용한다. 기존 CPU mock job/attempt를 보존하고 등록된 `vlm-batch01` 명령 하나만 추가한다. 임의 shell/모델/경로/추가 GPU 프로세스 실행은 허용하지 않는다. 등록 source/input/config hash 검증, timeout, 최대1retry, 유일 run/attempt 출력 유지. migration 필요 시 기존 SQLite backup과 원자적 보존 테스트 후 수행한다. 실제 inference는 큐 밖에서 실행하지 않는다.

공통 runner는 `vlm_batch.run`이며 model adapter 계약은 아래와 같다. 모델 담당자는 `Adapter(model_dir, settings)`를 구현한다. `.model`/`.processor`를 소유하고 `prepare(rgb, source, prompt, clip_id)`에서 `(inputs, metadata, actual_rgb_frames)`를 반환한다. inputs는 모델 tensor dict/BatchFeature, metadata는 실제 frame/grid/token/PTS/resize/padding 근거, actual_rgb_frames는 T×H×W×3 uint8 RGB 또는 처리가 여러 patch면 이를 명시한 자료다. 모델은 local_files_only=True, 원본 비식별화 유지, media 도구 전송 없음. runner가 한 번 load하고 같은6클립을 순서대로 generation/측정/저장한다.

Qwen 기준은 EXP7과 같은 영상 처리 예산(10프레임, shortest_edge16384/longest_edge3584000)이다. Smol 기준은 공식 영상 processor의 전체 화면 방식과 10프레임 순서를 사용하며 전처리 세부값을 최초 생성 전 기록·고정한다. 모델 파일/processor 검토는 추론 재시도가 아니며 weights를 읽어 생성하는 GPU 실행은 큐에서만 한다.

## 완료 조건

Sol high 담당 native IDs를 배정/등록하고 실제 진행 카드 확인. 보고서·metrics·입력 시트/원본 시간 클립은 각각 공개 요약/로컬 artifact로 저장. 총괄 및 Astra high 독립 검토가 같은 report/metrics SHA를 확인한다. complete 등록→GitHub 및 실제 서비스 버전 별도 확인→카드에서 보고서/그래프/등록 입력자료/검토 열람. 입력 영상은 사람이 보는 원본 5초 참고이며 실제 모델 샘플 시트와 구분한다. 이번 배치를 마친 뒤 자동 다음 배치를 시작하지 않는다.
