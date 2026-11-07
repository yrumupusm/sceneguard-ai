# EXP-0066 — EVAD-B·EVAD-L·STMixer-B 별도 검출기 준비

**공식 AVA 가중치 3개를 실제 내려받아 CPU에서 모델 생성과 strict state load를 완료했다.** 누락/예상 밖 key는 모두 0개이며 17개 CPU 시험을 통과했다. 실제 모델 forward·GPU 모델 적재·추론은 0회다. GPU 적합성·사람 복원·CCTV 등반 정확도·처리시간은 미측정이다.

2026-11-07. 8후보 비교 중 joint person/action detector 3개만 담당한다. 나머지 후보를 제외하거나 다른 모델로 바꾸지 않았다. root가 canonical 큐·decoder/native PTS·환경 바인딩·실제 GPU GO를 담당한다. 기존 FCOS proposal/실행 trigger를 사용하지 않으며 기존 모델·원본45·영역·검수 DB·큐·production은 수정하지 않았다. 작업 시작 pending 조회는 성공했고 `requests=[]`였다. 새 terminal 시작 실패 task는 root 이력으로 남기고 현재의 새 native dispatch로 작업했다.

## 공식 소스와 정확한 가중치

[공식 EVAD 저장소와 model zoo](https://github.com/MCG-NJU/EVAD/blob/0efdb7e1156d4b0b419cd240555f8bbca45e4bf6/README.md#model-zoo), [공식 STMixer 저장소와 model zoo](https://github.com/MCG-NJU/STMixer/blob/2c3cd1de2623fc47ad93cfda3a8fcb9713736a55/README.md#model-zoo)의 해당 end-to-end AVA checkpoint를 사용했다. backbone 사전학습 파일로 대체하지 않았다. 모두 공개 Google Drive 링크에서 HTTP200으로 접근했고 원본 member를 내려받으며 SHA256을 계산했다. 다운로드·검증 기록은 로컬 `runtime/model-comparison/exp0066/joint/`에, 가중치는 Linux의 별도 joint weights 경로에 있다.

| 후보 | 공식 config | 실제 checkpoint bytes | SHA256 |
|---|---|---:|---|
| EVAD-B / VideoMAEv2 | `projects/evad/configs/ViT_B_16x4_KTP.yaml` | 741,630,239 | `c58dbffc3137638230a8a67a5bac1e2c5a9186ba653fb516ff7931e45389d645` |
| EVAD-L / VideoMAE | `projects/evad/configs/ViT_L_16x4_KTP.yaml` | 1,758,427,087 | `141d40fe36d9ccbe7792d62503358dc8b1eeaab3bf9006c2d94290744fb8ac93` |
| STMixer-B / VideoMAEv2 | `config_files/VMAEv2-ViTB-16x4.yaml` | 1,023,605,151 | `e9d6c69c47d7e13efc84d7147b3527c5cff9e21b148e18062cf66fec2101f6a1` |

EVAD commit은 `0efdb7e1156d4b0b419cd240555f8bbca45e4bf6`, STMixer commit은 `2c3cd1de2623fc47ad93cfda3a8fcb9713736a55`다. Detectron2는 `247691a1c292654867deb35cabb27f18d75a1363`에 고정했다. upstream 소스와 실제 설치된 Detectron2/timm/fvcore/iopath/yacs/torchvision Python source, 사용되는 native entry point 및 local adapter/test를 spec의 절대 경로→SHA256 map에 연결했다. EVAD spec은 각각 1,513개, STMixer spec은 494개 바인딩이다.

## 환경·호환 수정·실제 CPU 검증

기존 환경을 변경하지 않고 `.venv-exp0066-joint`를 새로 만들었다. 시스템 Python에 torch가 없어 기존 venv 파일을 임의 `.pth`로 끌어오지 않았다. 실제 설치된 조합은 Python3.10, torch2.5.1+cu124, torchvision0.20.1+cu124, timm0.4.12, numpy1.26.4, fvcore0.1.5.post20221221, iopath0.1.9, PyAV14.2.0, OpenCV-headless4.10.0.84다. 전체 고정 목록과 설치 로그를 보존했다.

EVAD는 torchvision 버전을 처음 세 글자의 float로 비교해 0.20을 0.2로 오해하고 제거된 `_new_empty_tensor`를 import하려 했다. 실제 import 실패 뒤 vendor의 두 버전 guard만 정수 major/minor 비교로 바꾸었다. 가중치·레이어·연산을 대체하지 않았다. 수정 diff·upstream/patched SHA는 준비 결과에 있다. STMixer에는 이 수정이 필요하지 않았다.

nvcc는 현재 없으므로 Detectron2 extension은 `CUDA_VISIBLE_DEVICES=''`, `MAX_JOBS=2`로 CPU 빌드했다. 해당 [공식 ROIAlign 구현](https://github.com/facebookresearch/detectron2/blob/247691a1c292654867deb35cabb27f18d75a1363/detectron2/layers/roi_align.py)은 실제 `torchvision.ops.roi_align`을 사용한다. 설치된 torchvision의 CUDA dispatcher에 그 연산의 kernel이 등록됨을 CPU에서 확인했다. 가짜 operator를 넣지 않았고 GPU kernel을 실행해 본 것은 아니다. 실제 GPU 동작·peak 메모리는 canonical 실행에서 확인해야 한다.

root의 별도 CPU 생성 승인 아래 `CUDA_VISIBLE_DEVICES=''`로 모델을 생성하고 `weights_only=True`, `map_location='cpu'`, mmap으로 읽은 checkpoint를 `load_state_dict(strict=True)`로 적재했다. 학습 전용 key를 임의 삭제하지 않았다. STMixer의 모든 key에 있는 동일한 `module.` prefix만 명시적으로 제거했다.

| 후보 | strict state keys | missing / unexpected | 실제 parameter 수 | CPU parameter bytes | forward |
|---|---:|---:|---:|---:|---:|
| EVAD-B / VideoMAEv2 | 529 | 0 / 0 | 185,359,636 | 741,438,544 | 0 |
| EVAD-L / VideoMAE | 793 | 0 / 0 | 439,535,220 | 1,758,140,880 | 0 |
| STMixer-B / VideoMAEv2 | 529 | 0 / 0 | 255,856,372 | 1,023,425,488 | 0 |

이 bytes는 실제 parameter tensor 합이다. activation/workspace·GPU allocator·전체 GPU peak를 측정한 값이 아니므로 10GB 카드 적합성을 이 수로 인증하지 않는다. 큰 모델이라는 이유나 upstream A100 실험 환경만으로 불가능하다고 판정하지 않았다. 실제 float32 OOM이 생기면 실패를 보존하고, 더 작은 모델이나 해상도로 자동 교체하지 않는다. AMP 조건은 별도 명시·검토할 수 있으나 이번 준비에서 실행하지 않았다.

## 입력·시간·원래 좌표 출력

root runner 인터페이스는 다음 두 함수다. 공개 standalone inference CLI는 만들지 않았고, 실제 forward는 root의 승인된 canonical runner가 호출한다.

```python
load_model(spec: dict, device: str)
infer_clip(model, frames_rgb: numpy.uint8_THWC, spec: dict)
```

root가 RGB 원본 16샘플을 native PTS로 준비한다. 16x4는 AVA의 30FPS 기준 **4/30초 간격**, 첫–마지막 2초다. 중심 anchor는 nominal index8이며 입력 범위는 약 anchor−1.066667초부터 anchor+0.933333초까지다. 3FPS 원본에서 native index stride4를 써서 20초 입력으로 바꾸지 않는다. 중복·경계 반복은 root가 실제 PTS/고유 관측 수와 함께 기록하며 adapter는 다시 샘플링하거나 보간하지 않는다. 미래 입력을 사용한 중심 시점을 알림 시각으로 기록하지 않고 마지막 입력 도착 시각을 구분한다.

EVAD는 short side288, STMixer는256의 공식 test resize를 따르며 전체 입력 시야를 보존한다. center crop은 없다. RGB/[0,1], mean0.45/std0.225이며 right/bottom으로 32배수에 맞춘 normalized-zero padding을 사용한다. EVAD는 vendor ImageList, STMixer는 공식 batch collator와 같은 padding 경로다. STMixer native resize가 max_size 인자를 실제 cap에 사용하지 않는 극단적 aspect ratio는 조용히 바꾸지 않고 명시적으로 거절한다. 별도 short-side 통제가 있다면 control label을 요구하고 결과 geometry에 남긴다.

실제 resize의 반올림 후 x/y scale과 padding, 원래/resize/pad 크기를 저장한다. 출력 `boxes`는 원래 입력의 pixel xyxy이고 퇴화 박스를 조용히 지우지 않고 validity flag를 보존한다. EVAD는 자체 learned query detection head, STMixer는 자체 spatial/temporal query head가 박스를 만든다. 기존 FCOS 박스나 oracle 사람 crop은 입력하지 않는다. 해당 구조는 [EVAD model source](https://github.com/MCG-NJU/EVAD/blob/0efdb7e1156d4b0b419cd240555f8bbca45e4bf6/projects/evad/models/video_model_builder.py), [STMixer detector source](https://github.com/MCG-NJU/STMixer/blob/2c3cd1de2623fc47ad93cfda3a8fcb9713736a55/alphaction/modeling/detector/stm_detector.py)에 고정했다.

기본 person 출력 필터 EVAD0.7/STMixer0.6을 0으로 두어 **100개 원래 query 전부의 점수와 80개 class score**를 남긴다. 이는 결과 저장 필터 제거이며 사람 100명을 검출했다는 뜻이나 임계값 튜닝이 아니다. person/action 점수를 서로 곱하지 않는다. 원래 objectness/action logits도 별도 보존한다. 실제 person 판정 임계값과 복원 정답은 root의 별도 개발자료/사람 검수 계약이다.

반환값은 `boxes`, `person_scores`, `action_scores`, `action_label_names`, raw logits, preprocessing geometry, 의미 범위·precision이다. `timing_seconds`는 preprocess/inference/postprocess/total을 제공하도록 작성했고 CUDA synchronize로 실제 forward 경계를 잰다. preprocess에는 CPU resize와 GPU 복사/pad, inference에는 vendor 전체 forward 및 그 안의 native head postprocess, adapter postprocess에는 좌표 역변환·CPU 전송·JSON list 변환이 포함된다. decode는 root가 별도 측정한다. 이번 준비에서 그 타이머를 실제 GPU forward로 실행한 측정값은 없다.

## AVA와 CCTV 등반 의미 분리

[Google의 공식 AVA v2.2 label map](https://research.google.com/ava/download/ava_action_list_v2.2.pbtxt)을 실제 내려받아 ID1–80의 이름을 연결했다. **ID20 `climb (e.g., a mountain)`은 존재한다.** 이를 CCTV 담장 넘기·같은 사람의 통과 완료·침입 확률로 이름만 바꾸지 않는다. `task_specific_climbing_head=false`는 CCTV 작업 전용 head가 없다는 의미이며 AVA의 generic climb class가 없다는 주장이 아니다.

모든 출력은 `AVA_v2.2_atomic_action_scores_not_CCTV_fence_climbing_or_intrusion_probability`다. 별도 사람/문 대응과 target head 검증 전 person recovery accuracy·CCTV climbing probability·침입 정확도는 null이다. 새 학습·보호45로의 기준 선택·기존 사건 상태 변경은 하지 않았다.

## 시험·실행 근거와 남은 단계

CPU 시험17개가 통과했다. landscape/portrait/반올림/padding 좌표 역변환, 시야 보존, 퇴화 query 보존, 잘못된/비유한 점수와 부분 class 벡터 거절, RGB/시간축 유지, 공식 EVAD·STMixer 전처리와 synthetic 입력의 일치, 잘못된 checkpoint/vendor 바인딩 거절, CPU forward 사전 거절을 확인했다. 실제 모델 forward를 합성 시험으로 대신했다고 하지 않는다.

실제 실행한 최종 준비 명령은 다음과 같다. 모든 validation은 CPU 생성/strict 적재 후 종료하며 forward를 호출하지 않는다.

```bash
CUDA_VISIBLE_DEVICES='' .venv-exp0066-joint/bin/python -m unittest discover -s tests -p 'test_exp0066_joint_models.py' -v
CUDA_VISIBLE_DEVICES='' .venv-exp0066-joint/bin/python scripts/exp0066_joint_models.py --write-specs
CUDA_VISIBLE_DEVICES='' .venv-exp0066-joint/bin/python scripts/exp0066_joint_models.py --cpu-validate runtime/model-comparison/exp0066/joint/specs-v2/evad_vitb_vmaev2.json --output runtime/model-comparison/exp0066/joint/evad_vitb_vmaev2-cpu-load-v2.json
```

L과 STMixer도 해당 spec/report 이름으로 같은 CPU 검증을 각각 완료했다. output은 exclusive write이므로 같은 경로를 덮어쓰지 않는다. 초기 spec/검증을 보존하고 실제 설치 소스 바인딩·동기화 타이머를 보완한 최종 `specs-v2`를 사용한다. root는 이 spec을 그대로 보존하면서 canonical queue용 파일 바인딩과 environment snapshot을 추가할 수 있다.

| 최종 spec | SHA256 | CPU strict report SHA256 |
|---|---|---|
| `evad_vitb_vmaev2.json` | `40ffbbbb04c44925751bebe5a90b98f0a177e9c30a50d17d0e17027bdf34f63c` | `9b350ed166d2fbd23eff31b2244b7c7fd97cb3d1817f98bb7b3e99708f305be3` |
| `evad_vitl.json` | `777f643aa20f1693d624fa5c4513c899d150ac7755e108fd9594473fb8b9b74d` | `02b5c4a926ecf0081d936ca092596f7e620a503df9bec30bdd6e2ae8a43fde3d` |
| `stmixer_vitb_vmaev2.json` | `ab3f9eda994774836e317f4ae8160d452d87a2937225a4d074b818efc90f27fe` | `b0cb9e57e772b09cd60a6ef5230c1e02995782ad70fe70b0a686cab26bef3ffd` |

로컬 준비 요약 `joint-preparation-result.json` SHA256은 `2303f6e710534bbd9582772d63177afbcb4b5338aaedc5ffafaae7ff9f6f8f14`다. adapter SHA256 `2562274f3a68ab78536b066dbb2eaafd7b8202609da0627f9250cd9bb05a2f17`, test SHA256 `fb140c907b2c4c75b1a0f56882598e6bb21ad0f18d4d7e2006e3ad5e5a14cef6`이다. 가중치·vendor·원본 경로·환경·로그는 로컬에 남긴다. 커밋/push·기존 환경 교체·중첩 작업자는 없다.

남은 것은 독립 검토와 root의 정확한 큐/환경/소스 승인, 실제 GPU forward와 메모리·지연·원래 사람 대응 확인이다. 이 문서는 준비 완료를 기록하며 모델 비교 성공·실제 박스 복원 완료·CCTV 등반 성능 충족을 선언하지 않는다.
