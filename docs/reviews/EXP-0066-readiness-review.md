# EXP-0066 encoder 출처·평가 준비 독립 검토

2026-11-07. **최종 준비 판정: 아래 정확한 소스·명세의 R3D18 및 네 새 encoder는 총괄이 canonical 큐에서 첫 smoke를 실행할 준비 검토를 통과했다.** 공식 가중치·구조·CPU strict load·고정 입력과 큐 계약을 확인했으며, 실제 GPU smoke 성공이나 전구간 실행·행동 성능을 인증한 것은 아니다. 세 joint detector adapter와 새 작업별 head는 이 판정에 포함하지 않는다. encoder 특징, 다른 데이터셋의 분류 점수, 사람 검출 회복과 CCTV 넘기 성능을 각각 구분한다.

배정은 `task_9f18fd4d6a2b` / `ctx_89c7e3ad6575`다. 새 preamble, 전체 task, comparison spec, AGENTS와 EXP-0065 최신 검수 반영을 읽었다. 웹 `pending --include-acknowledged`는 성공했고 `requests=[]`였다. 원래 EXP-0065 아홉 답변은 제한된 입력/대상 관찰이며 전체 의미 정답으로 확대하지 않는다. 특히 공식 stand와 실제 넘기의 충돌 및 다른 사례의 박스/시각 불확실성을 보존한다.

검토자가 작성한 범위는 이 문서와 `runtime/model-comparison/exp0066/encoders/`, `weights/model-comparison/exp0066/encoders/`뿐이다. 네 공식 파일을 내려받고 metadata/CPU import를 검사했지만 모델 forward·GPU·학습·설치·운영 코드·큐/DB 변경·commit/push는 하지 않았다. 모델 실행은 총괄이 검토된 canonical 큐로 별도 수행한다.

## 공식 출처와 실제 파일

| 모델 | 고정 소스 | 실제 파일 바이트 | SHA256 |
|---|---|---:|---|
| InternVideo-Next-S2-L | GitHub `3965eef16e2dadd0ea6c8d0cc29c8a3039df52e3`; HF `b14495944fe821fbc2fbdd7f01404508ba0d5a6f` | 622,102,256 | `538d64384706e96b7b01844bd9debc8fe8f9e3c86ee0162d8d0cb51c28fea51d` |
| V-JEPA2-L | `204698b45b3712590f06245fbfba32d3be539812` | 5,127,726,842 | `5346856ec9df69487fe72a25bf2632aaa8112df33fb67708e3f7374edc1f7012` |
| V-JEPA2.1-L | 같은 V-JEPA 고정 소스 | 5,151,198,524 | `7ea9b7cb4a75d10644a8a8d42cff9e177b10dca8f02173f0eaf2b0bed82838c6` |
| VideoMAEv2-B | GitHub `29eab1e8a588d1b3ec0cdec7b03a86cca491b74b`; HF `706cc172d65ebd4dedbee3f9c0183a93df9fa125` | 173,574,417 | `8141a6955e0700d11bf15928fe6d61e5cfe482606fed8cfdddb1b922c0fd88ec` |
| 보존 R3D18 epoch6 | 기존 EXP-0063/0064 `best.pt` | 398,140,440 | `8b4e2eb74bee656f651a172403e4ddfe1e1ce8f9a4438d70c76b5a1b17825b73` |

InternVideo는 [공식 GitHub](https://github.com/OpenGVLab/InternVideo/tree/3965eef16e2dadd0ea6c8d0cc29c8a3039df52e3/InternVideo-Next)가 연결한 [OpenGVLab collection](https://huggingface.co/collections/OpenGVLab/internvideo-next-693013a466697c325f576028)에 있는 저자 `revliter`의 large 모델이다. 별도 stage1 checkpoint와 구분한다. [고정 HF 코드/설정](https://huggingface.co/revliter/internvideo_next_large_p14_res224_f16/tree/b14495944fe821fbc2fbdd7f01404508ba0d5a6f)을 저장했고 다른 InternVideo2/giant 모델로 바꾸지 않았다.

V-JEPA 두 파일은 [공식 README](https://github.com/facebookresearch/vjepa2/blob/204698b45b3712590f06245fbfba32d3be539812/README.md)가 연결한 [V2 large](https://dl.fbaipublicfiles.com/vjepa2/vitl.pt)와 [V2.1 distilled large](https://dl.fbaipublicfiles.com/vjepa2/vjepa2_1_vitl_dist_vitG_384.pt)다. HTTP 길이와 수신 바이트를 확인하고 자체 SHA를 계산했다. publisher SHA가 제공된 것으로 꾸미지 않는다. InternVideo와 VideoMAE는 HF LFS SHA/크기와 실제 수신 바이트가 모두 같다. 모든 다운로드는 첫 시도 완료했고 모델 코드를 실행하지 않았다.

VideoMAEv2-B는 [공식 model zoo](https://github.com/OpenGVLab/VideoMAEv2/blob/29eab1e8a588d1b3ec0cdec7b03a86cca491b74b/docs/MODEL_ZOO.md)의 K710 distilled Base다. [정확한 파일](https://huggingface.co/OpenGVLab/VideoMAE2/blob/706cc172d65ebd4dedbee3f9c0183a93df9fa125/distill/vit_b_k710_dl_from_giant.pth)을 선택했으며 EVAD backbone이나 giant로 대체하지 않았다.

## 실제 구조·출력·의존성

아래 출력 모양은 소스와 실제 checkpoint tensor 구조로 검토한 계약이다. forward 실행 결과는 아니다. 공통 입력은 RGB `B,C,T,H,W`; 정규화 전 0–1이다. 네 새 encoder의 실제 preprocessing은 ImageNet mean/std를 사용하며 R3D는 기존 별도 mean/std를 보존한다. 감시영역을 완전히 보존하는 resize/pad와 공식 center crop 조건을 혼동하지 않는다.

| 모델 | 생성/가중치 계약 | 16프레임 기본 입력의 출력 계약 |
|---|---|---|
| InternVideo-Next | `InternVideoNextBackbone`, patch14/tubelet1, 24층·1024차원·16heads; safetensors `model.` prefix | 224²에서 `projected=False`는 4096×1024 patch tokens, `projected=True`는 768차원; CCTV head 없음 |
| V-JEPA2 | `src.models.vision_transformer.vit_large`, `target_encoder` 292tensors, patch16/tubelet2/RoPE | 256²에서 2048×1024 tokens; predictor/optimizer는 encoder feature에 사용하지 않음 |
| V-JEPA2.1 | `app.vjepa_2_1.models.vision_transformer.vit_large`, `ema_encoder` 302tensors, image/video modality·image patch embed·4norms 포함 | 384²에서 `training=False`는 4608×1024 tokens; hierarchical 출력과 구분 |
| VideoMAEv2-B | `vit_base_patch16_224(all_frames=16,num_classes=710)`, checkpoint `module`, 162tensors | `forward_features`는 mean-pool+fc_norm 768차원, 원래 head는 710 Kinetics logits |
| R3D18 | `torchvision.models.video.r3d_18`, 기존 512→2 head | 기존 학습은 실제 8프레임/3Hz·112² actor-context; full-frame 입력은 별도 분포 |

InternVideo 실제 파일은 tensor 332개와 metadata 항목 1개이고 `patch_embed.proj.weight=[1024,3,1,14,14]`다. 초기 메시지의 header 항목 333개를 tensor 수와 구분한다. VideoMAE는 `[768,3,2,16,16]`와 `[710,768]` head를 확인했다. 두 V-JEPA는 `torch.load(weights_only=True,map_location='meta',mmap=True)`로 tensor 구조만 읽었다. R3D 실제 SHA는 보존됐지만 최초 엄격 loader가 NumPy RNG metadata의 `_reconstruct`를 거절했다. 실패와 정적 pickle global 목록을 남겼고 무조건 `weights_only=False`로 재시도하지 않았다.

원래 `.venv-cv-batch02`에는 torch2.5.1+cu124/torchvision0.20.1+cu124/transformers5.1.0/safetensors0.8.0이 있지만 timm/einops/flash_attn/decord가 없다. 최초 V-JEPA 두 직접 CPU import는 timm 부재로 실패했다. 이후 총괄이 새 `.venv-exp0066-encoders`에 timm0.4.12/einops0.8.1/transformers4.48.3 등을 설치했고, 아래 별도 CPU strict load를 통과했다. 기존 환경을 고치거나 실패를 삭제하지 않았다.

## 조기에 전달한 실행 차단 사항

1. 고정 V-JEPA `src/hub/backbones.py`의 실제 기본 URL이 `http://localhost:8300`이다. `torch.hub`의 mutable 원격 실행을 사용하지 않고 위 직접 공식 파일·고정 코드를 연결해야 한다.
2. V-JEPA2.1 eval YAML이 참조하는 legacy wrapper는 옛 `src` 구조로 shape 불일치를 현재 random 값으로 바꾸고 `strict=False`로 넘긴다. 2.1의 실제 `app` 구조와 EMA 전체를 정확히 로드하고 누락/초과/shape mismatch를 실패로 처리해야 한다.
3. InternVideo HF 소스는 flash_attn·fusedMLP·fusedRMSNorm을 무조건 import하고 세 fused flag를 함께 켠다. 비융합 경로를 쓴다면 명시적 호환 patch와 원본 대비 수치/구조 검토가 필요하다. 가짜 모듈로 조용히 대체하지 않는다. 비기본 시간/공간 positional interpolation에는 `.cuda()`가 하드코딩되어 있어 장치 선택도 확인해야 한다.
4. VideoMAE 생성자 인자는 `num_frames`가 아니라 `all_frames`다. 실제 dataset의 ImageNet 정규화가 `default_cfg`의 0.5 표기와 다르다. 구조 API와 실제 전처리를 모두 고정한다.
5. 같은 16개 입력이라도 16×4/30은 첫/끝 2.0초, 공원 원본의 16개 연속 3Hz는 5.0초다. 8개를 반복해 16개 실제 관측이라고 하지 않는다. 마지막 입력 도착 전 경보를 사용할 수 있다고 계산하지 않는다.

정확한 기계 판독 계약은 `encoder-source-contract-v2.json` SHA `6f04c0d40a2bd3a5d8beecacc33f0a0412c92e5242c346d3df0395558176d2b0`다. v1은 잘못 적은 VideoMAE keyword를 정정하기 전 이력으로 보존한다. 최종 코드가 이 문서와 달라지면 새 해시로 검토해야 한다.

## 작업별 head의 자료 가능성과 한계

**기존 공식 참조 라벨은 있으므로 head가 없다는 이유로 학습 자체가 불가능하다고 결론 내리지 않는다.** 기존 release는 manifest SHA `72912fab027a068d0e6043f328d86a2c7d15a239afa751d126984c5c10498931`에 연결된 actor-context 8프레임 계약이며 full-frame/16프레임용 자동 승인이 아니다. 기존 release SHA는 `7305b347f9783ca29d1055c3002cc6135ad41144e75874f153031d0d2fa3635b`, split은 `bfb0f9fcd570794036cc6d2eaad46f988679b612996e21282a34821203ad5499`다.

별도 독립 스크립트로 train/validation 798원본의 실제 라벨 SHA와 4,310개 actor-event를 읽었다. test 라벨과 학교45는 읽거나 학습 데이터에 넣지 않았다. 양쪽 frame origin의 모든 annotation·고유 actor/object/class·유효 박스·사건 겹침·source 전체 동시 wall annotation/event를 확인했다.

| 공식 참조 후보 | train 양성 | train 명시 음성 | validation 양성 | validation 명시 음성 |
|---|---:|---:|---:|---:|
| 기존 8프레임 중심 재현 | 1,571 | 2,014 | 411 | 314 |
| 16연속 프레임 중심의 라벨 조건 충족 | 887 | 1,645 | 141 | 312 |

16프레임 후보는 아직 실제 native decode를 확인하지 않았고 새 training release도 아니다. 같은 full-frame native window를 중복 제거하면 8프레임 3,999개, 16프레임 2,753개이며 같은 창의 양/음성 충돌은 0이다. 이 수를 독립 사건/사람 수로 바꾸지 않는다. train/val/test의 event group·source ID·source SHA 교집합과 보호45 SHA 교집합은 모두 0이다. 기존 원본의 재인코딩 전수 독립성까지 새로 인증한 검사는 아니다.

학습 가능한 구체적 제안은 다음과 같다. 원래 train/val 그룹을 고정하고 새 full-frame 또는 사전 고정 감시영역의 native 관측/ROI/정규화/encoder SHA를 새 manifest에 묶는다. full-frame 중복 창을 제거하고 명시 양성과 명시 음성만 사용하며 동시 wall·상충·불확실 라벨은 제외한다. encoder를 eval/frozen으로 고정하고 고정 pooling 뒤 2-class linear head만 학습한다. head 초기 seed·loss·epoch/선택 규칙을 점수 전에 고정하고 원래 validation만 선택에 쓴다. 학교45·기존 test·EXP-0065 추가 보강 미검수 후보는 학습/임계값 선택에서 제외한다. smoke도 train/val만 사용한다.

이 head는 새 입력에 대한 **공식 annotation-reference proxy**이며 사람 기준 CCTV 넘기 head 성능으로 발표할 수 없다. validation 음성은 여전히 sitting뿐이고 정상 접근·걷기·문 앞 대기 오탐 수준을 선택할 충분한 검수 구간이 없다. 최근 test의 stand 의미 충돌은 train/val 전체가 틀렸다는 증거도, 전체가 검수됐다는 증거도 아니다. 보호 test를 옮기지 말고 별도 train/val 의미 표본과 새 native 입력을 검증해야 한다. 같은 2초에 16개 독립 관측을 요구하는 경우 3Hz 학습 원본으로 그 조건을 충족하지 못하므로 다른 실제 자료 또는 명시적으로 다른 시간 계약이 필요하다.

## 실행 준비와 성능 판정의 범위

총괄의 실제 adapter·queue runner·고정 input manifest·환경과 smoke 선택을 읽고 아래 CPU 계약 시험과 source/key/shape 검사를 완료했다. 검토자의 모델 forward/GPU 결과는 0이며 encoder만으로 박스 기반 person recovery 지표는 제공하지 못한다. 전체45의 저장 검출 목록 감사와 전체 가시 사람의 누락 정답 완성은 다르다. 사람/문 대응 미확정과 공개 수치의 미측정을 유지하고, 실행 실패/입력부족을 분모에서 빼지 않는다.

## 실제 CPU strict load와 입력 계획 추가 확인

총괄 adapter `scripts/exp0066_encoders.py` SHA `ed2a0b84756b665d8865346ff4d243346f88df600aa5dfbea1f2fc8180b7a679`에서 다섯 모델을 CPU에 생성하고 실제 가중치를 strict 로드했다. V-JEPA2 292개, V-JEPA2.1 302개, VideoMAE162개, InternVideo332개와 R3D122개 tensor key가 일치했다. R3D는 명시적인 NumPy `_reconstruct`/ndarray/dtype allowlist를 사용하며 epoch6·2×512 head를 확인했다. forward·GPU는 실행하지 않았다. 모델이 eval 상태인 것과 향후 head 학습 시 `requires_grad=False`로 동결하는 것은 별개이며 head 구현은 아직 없다.

InternVideo 비융합 복사본 SHA `3208dd9eb80d28a08a6bdefef217c072c5657a3259d407c7f3c679d9b151126e`와 원본 SHA `d7d516675ba15d4538cae6dd3432f4d9ae52f8c336cb3af4852a18639dec4e72`의 모든 class/function AST가 정확히 같다. 두 optional flash import만 guard로 감쌌고 세 fused flag를 false로 명시해 원래 비융합 분기를 사용한다. CPU strict load는 통과했지만 융합/비융합 forward의 수치 동등성이나 GPU 메모리 적합성을 시험한 것은 아니다.

실제 cohort manifest SHA `480b1410c568b9a038c7be6d124f7be1890b3b7375cbed43e87b165346a2aa18`, smoke SHA `8ee64caa28fed6b756aecf39c5d392c6b544f204ad12ed39ed617d727a3481c0`의 전체 45영상·184,300 native PTS를 읽어 모든 6,177정규+42추가 창의 가장 가까운 native index/동률·경계/반복 mask·관측 수·마지막 입력 시각을 독립 대조했다. 7smoke는 고정 계획의 정확한 부분집합이다. 원시 영상을 다시 읽거나 전체 detector FN 정답을 만든 검사가 아니다.

초기 runner에서는 NaN timestamp가 검증을 통과하는 반례를 재현했다. 추가42창을 읽지 않는 경로, 빈 실행에도 성공을 쓰는 경로, 시작 검사 후 입력/소스 변경을 완료 시 확인하지 않는 문제, 현재 source와 실제 canonical 성공 attempt에 연결되지 않은 smoke JSON 재사용 위험도 전달했다. 총괄이 수정했고 아래 최종 소스에서 재검토했다. 최초 반례와 후속 증거는 `initial-runner-adversarial-probe.json`, `cohort-native-plan-independent-audit.json`, `strict-cpu-loads-summary.json`, `r3d18-strict-cpu-load.json`, `internvideo-nonfused-source-audit.json`에 있다.

## 최종 큐 계약·시험·정확한 준비 버전

최종 구현은 원래 canonical GPU lock inode와 상속 FD, 실제 running job/attempt·감독 프로세스·live Orca 배정, GPU0, 자원 조건, 검토된 소스의 실제 committed 바이트와 승인 context를 확인한다. 독립 GPU 실행이나 임의 retry 경로를 추가하지 않는다. command allowlist는 기존 항목을 유지한 채 추가하며 migration은 기존 잠금·backup·트랜잭션을 사용한다.

cohort/smoke SHA를 상수로 고정했고 6,177정규+42추가/7smoke 개수, 전구간45/184,300 native 프레임 완료를 확인한다. NaN/Infinity PTS는 거절하며 끝 프레임 반복은 실제 관측 수에 포함하지 않는다. 완료 직전에 소스·입력·환경 명세를 다시 확인하고 실제 windows 출력 SHA를 결과에 저장한다. queue 영수증은 결과 SHA를 저장하며 exit0인데 결과가 없으면 실패한다.

전구간 단계는 동일 model/cohort/input/source의 실제 성공한 canonical smoke job/attempt와 영수증·결과·windows SHA를 요구한다. 실패한 DB attempt에 성공 JSON만 붙이거나 옛 소스의 smoke를 사용하면 거절한다. 서로 다른 무관한 문서 commit이 존재할 수 있으므로 소스 바이트 동일성과 각 실행의 committed provenance를 구분한다. 이번 준비 판정만으로 전구간 실행의 smoke 선행 조건을 충족했다고 하지 않는다.

독립 실행한 비교/기존 action-inference 회귀 **17개**와 별도 반례 계약 **8개**, 합계 **25개**가 통과했다. 별도 8개는 정상 canonical smoke 통과, 실패한 실제 attempt, 변경된 출력, 옛 소스, 바뀐 queue 입력, 0개 smoke, 비유한 시각, 달라진 import 경로를 다룬다. 기존 migration 시험의 backup 수는 이미 등록된 schema에는 0, 신규에는 1로 구분하며 원래 job/attempt 보존 검증은 유지한다. 운영 DB를 시험 fixture로 변경하지 않았다.

| 최종 실행 소스 | SHA256 |
|---|---|
| orchestration/model_comparison_command.py | `b161ae77f2953d0c1aeea542726875f01727f7d44cab15ef14d7f5ed8dff5f49` |
| orchestration/queue.py | `234d292450d458a3ce66853c2469208ed9a3ee853b5ee9c7757e0fdefbb7b39d` |
| scripts/run_model_comparison.py | `efac1fa13cd027dee80f641972639a6d0c8252a45a0afa00e35f7be215fdb98b` |
| scripts/exp0066_encoders.py | `ed2a0b84756b665d8865346ff4d243346f88df600aa5dfbea1f2fc8180b7a679` |
| scripts/prepare_model_comparison.py | `6a574e6f09afebea1202cec138775917592c5887469ca5ec4e534be643032014` |
| tests_orca/test_model_comparison.py | `05389cbcdf277b82a0d3cd13083b2d43e3f1c3fc581d41697b9cb49511befb70` |
| docs/experiments/EXP-0066-protocol.md | `c1f90abd510a70836b5e647d9915799df3f810a884641d6979159467c0b10a8f` |

| model-specs-v1 명세 | SHA256 |
|---|---|
| r3d18_exp0064.json | `42fd653f6727348ee843323d32b873179cffadb6272d565f2429b239821d9fe4` |
| vjepa2_l.json | `206e0e07a6313ee48e72b3eed25753dbe7eda517ed5a4387c116c24bd049c3e7` |
| vjepa2_1_l.json | `63c6133ab0bf2d94dbe648dac90dc82f58f612a927309a40007a0ed820d6f847` |
| videomaev2_b.json | `4cafaae8e57e5fc67948b3317c4dcab3645dc55fd673dc7c2c5318ea6d1f5935` |
| internvideo_next_s2_l.json | `dd983c9877da65bc5aaf843fe315fd215e05447276ca6914780faaaf06f603b6` |

최종 준비 evidence는 `runtime/model-comparison/exp0066/encoders/smoke-readiness-v1.json` SHA `d03365fcc1ecc8692302a32f71ee73f7dd8dcca9edd049557016f7d56535a268`이다. 모든 실제 명세의 vendor/config/environment binding을 대조했고 현재 환경 package 버전과 import 경로가 snapshot과 같았다. 원시 모델 파일의 SHA는 최초 다운로드/보존 감사 및 strict CPU load에 연결하며 불필요하게 모든 원본 미디어를 재해시하지 않았다. 실험 시작 보호 파일 6개와 canonical jobs/attempts 각100행의 저장 순서·직렬화 SHA는 준비 검토 시점까지 그대로였다.

총괄은 이 정확한 바이트를 commit하고 기존 승인 context로 실제 smoke를 실행할 수 있다. 모델별 OOM/실패/미지원은 보존하고 다른 크기나 head로 몰래 바꾸지 않는다. 첫 smoke에서 실제 feature shape·finite 출력·GPU 메모리·시각/전처리 조건을 확인한 후에만 동일 소스의 전구간 실행으로 진행한다. 새 head/전체 의미 라벨·동일인 회복·정밀 행동 성능·실제 웹 전달은 별도 후속 결과가 필요하다.
