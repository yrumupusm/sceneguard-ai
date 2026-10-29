# EXP-0026 독립 검토

2026-10-29. 검토 Task `task_1d31f20f14b2` / Dispatch `ctx_556f3729a9e7`. 최종 상태: **기술 실행·비교 기록 검토 통과(`accepted_for_comparison`), 핵심 누락 지속·채택 보류(`adoption_on_hold`)**. 사람 라벨·새 박스의 의미 검수와 Gate D0는 미완료다. 아래 사전 검토 대기 문장은 진행 이력이다.

사용자의 최신 학습 지시와 [탐색 학습 계획](../experiments/EXP-0026-exploratory-training-plan.md)을 이번 범위의 근거로 삼는다. [준비 기록](../data/CLIMBING_FENCE_PREPARATION.md)의 학습 미승인은 당시 이력이며 원본을 변경하지 않는다. 미검수 라벨의 의미·누락·복수 인물 여부와 split 독립성은 미확정이고 **Gate D0 미통과**다. 검토자는 CCTV 이미지를 외부로 전송하거나 시각 정답을 만들지 않는다.

## 초기 계획 판단

COCO YOLO26m Detection 기준 모델과 새로 로드한 동일 pretrained 파일의 단일 학습 실행, train210/valid20 및 test17 미사용, 고정 CCTV 7개 입력은 탐색 범위에 부합한다. COCO80→person1로 출력 공간이 달라진다. 설치본의 `cls_remap=True`는 이름이 맞고 shape가 호환되는 person class-logit 행을 공식 경로로 옮기므로, 실제 transfer 로그 확인 전 분류 head 재초기화를 단정하지 않는다. 일반 사람 자료 혼합이 없어 기존 사람 검출 성능의 저하 가능성은 남는다. valid 수치는 제공된 잠정 라벨과의 일치 진단이며 CCTV 검출 정확도·일반화·행동 성능을 입증하지 않는다.

## 설치 API에서 확인한 실행 전 해결 항목

검토 대상은 기존 환경의 Ultralytics 8.4.192 설치 소스다. [공식 train API](https://docs.ultralytics.com/modes/train/)와 [YOLO26 Detection 문서](https://docs.ultralytics.com/models/yolo26/)를 교차 확인했고, 버전별 실제 동작 판단은 설치 소스를 우선했다.

1. `engine/trainer.py`는 첫 epoch 메모리 오류에서 batch를 줄이고 최대3회 내부 재시도를 한다. 이번 고정 batch/자동 재시도 금지에 맞게 **재구축·다음 forward 전에 종료하는 관측 guard와 CPU 오류 시험**이 필요하다. 학습 알고리즘이나 private trainer 메서드를 교체하는 수정은 요구하지 않는다.
2. 같은 trainer는 NaN/Inf loss 또는 fitness 발생 시 `last.pt`를 다시 읽고 epoch를 재실행한다. 이 자동 복구도 실행 전에 차단하고 비유한 값 실패를 보존해야 한다.
3. 명시적 AdamW에서 기본 `warmup_bias_lr=0.1`은 자동으로 0이 되지 않는다. 계획의 lr0=0.0001과 별개로 1,000배 큰 초기 bias LR이 될 수 있으므로 작은 고정 warmup LR을 명시해야 한다. nominal `nbs=64`이면 batch2의 accumulate32 및 warmup 동안의 변화를 기록한다. 내부 validation dataloader는 batch4다.
4. HSV/기하 증강을 0으로 해도 선택적 Albumentations 기본 Blur/Gray/CLAHE는 남을 수 있다. 공개 `augmentations=[]`로 추가 변환을 끄고 실제 변환 경로를 확인한다.
5. `cache=False`여도 label cache를 생성하므로 원본 준비 사본이 아닌 별도 실행 사본을 사용한다. FP32 학습과 checkpoint의 FP16 저장은 구분하며, 매 epoch validation 외에 종료 시 best checkpoint validation이 추가됨을 계수한다.

위 항목은 구현 담당/총괄에게 전달한 초기 요구사항이다. 아래 후속 검사에서 실제 kwargs, offline callback/네트워크 차단, source/input/weight SHA, 기존 canonical queue의 lease·free VRAM≥6144MiB 검사 경로, CPU 회귀와 소스 동결을 확인했다. 결과를 받은 뒤 성공 epoch·실제 비용·제공 라벨 진단·사람 박스 품질 미검수를 분리하여 이 문서에 최종 검토를 추가한다.

## 구현·CPU 사전 검토

초기 지적은 실제 구현에서 해소됐다. `warmup_bias_lr=0`, `nbs=64`, `augmentations=[]`가 고정됐다. `RejectRecovery`는 설치본의 OOM batch 축소 경고 및 NaN/Inf 복구 경고에서 예외를 발생시켜 다음 pipeline 재구축·checkpoint 재로드 이전에 종료한다. upstream 메서드 교체나 private retry counter 쓰기는 없다. 원래 오류와 거부 경고를 로컬에 남긴다. 마지막 best validation을 학습 epoch21로 잘못 세던 초안도 수정됐다.

검토자가 Detection CPU 테스트10개와 평가 준비 테스트9개를 독립 실행해 모두 통과했다. Detection 시험 전후 소스 바이트가 같았다. 공식 kwargs 파싱, 정상 empty/비유한 값/pose 거부, crop offset1회, lease 없는 직접 실행 거부, 6144MiB gate, 기존 queue 행 보존 migration, 자동 retry 거부, 최종 validation 중복 계수가 포함된다. 담당자의 기존 queue 회귀14개 통과 로그도 확인했다. 별도 파일·픽셀 대조에서 지정7장의 native PTS, 원본/RGB/crop SHA 및 C6/C3 고정 영역이 일치했다. 이 검사는 시각 정답 검수가 아니다.

원본 데이터 전체 snapshot 및 독립 byte copy의 train210/valid20를 `input_contract`로 확인했다. 실행 사본에는 test 파일과 YAML test 항목이 없다. 공식 Detection checkpoint SHA는 `401cea9ab23ad19246ff7744859816bc599f350e93c9dd30367b6f0a0745d0b7`이고, 담당자의 offline CPU audit은 detect/80클래스/person0/unfused/FP32/CPU와 CUDA 미초기화를 확인했다. 새 학습 인스턴스를 pretrained 파일에서 다시 만들며 baseline에서 fuse된 인스턴스를 재사용하지 않는다.

실행 경로는 source/input/config 해시, root가 확인한 Run/Task/Dispatch와 commit, canonical lock descriptor의 inode·실제 잠금, 살아 있는 부모/자식 프로세스와 queue row를 모델 로딩 전에 검사한다. GPU 진입 시 여유 메모리 검사는 동적으로 남아 있다. 네트워크 transport 차단과 별도 설정 디렉터리의 외부 integration 비활성화를 확인했다. 로컬 font alias는 다운로드를 피하기 위한 기록된 파일 복사이며 모델/학습 알고리즘 수정이 아니다.

**판정: 검토한 소스 내용의 제한된 탐색 실행에 대한 CPU 사전 PASS.** 현재 해결되지 않은 구현 blocker는 없다. 정확한 소스 목록·digest·input contract는 로컬 `runtime/BATCH-0007/training/review-preflight.json`에 보관한다. 총괄이 같은 바이트를 commit하고 해당 commit·입력에 실행 승인을 binding해야 하며, 그 확인 전에는 GPU 실행 승인이 완료된 것으로 읽지 않는다. 학습 성공, 제공 라벨 일치 수치, 실제 사람 박스 품질, 일반화와 채택은 모두 후속 판단이다.

후속 commit 대조에서 `1a0a647427dcb8e9fe51edd38a51a747d4485a24`의 전체 실행 소스가 검토한 파일 SHA와 일치했다. source digest는 `6a51ea5171e16e161eb47151cb0d2df96c94e784daef16a9b152a61aabe09520`, input contract digest는 `51c20e7a77c992df5bbe38b02599fe66a39856b73cbce0cc3e1098e2e6c83646`이다. **이 commit·입력의 preflight PASS를 확정**한다. 총괄의 실제 실행 승인과 실행 시 live lease/VRAM 검사는 그대로 필요하다. 검토자는 GPU를 실행하지 않았다.

## 실제 실행 및 최종 독립 판단

검토한 commit·source·input으로 canonical attempt `616f05a480c7434f82253e90ae7a096e`가 한 번 성공했다. queue의 exit0/attempt1과 실행 summary의 train1회·20 epoch·validation21회·전후7개씩 native Results·retry0이 일치한다. 시작 free VRAM8684MiB는6144MiB 기준을 충족했다. 학습223.544초, runner241.128초, allocator peak allocated1373.003MiB/reserved1984MiB, 장치1662개 표본의 최대 사용3760MiB·최소 여유6294MiB를 원시 수치와 대조했다. 로딩·warmup·fuse·저장을 포함하는1.520초/0.830초의 전후 단계를 속도 개선이나 연속 영상 FPS로 해석하지 않은 보고서가 타당하다.

실제 파라미터는 FP32·unfused·person1이고 optimizer 그룹은 lr0.0001, weight decay0.0005, BN/bias decay0이다. 생성자 defaults가 실제 그룹 값을 덮어썼다고 오독하지 않았다. 공식 로그의 person1/1 class 행 remap과768/768 items 전이를 확인했다. 검토자가 best/last를 **CPU로만** 읽어 파일 SHA·크기·person1 head·유한 파라미터·실제 FP16 저장을 확인했다. 공식 strip 이후 epoch=-1/optimizer=None인 checkpoint를 epoch 완료 증거로 오해하지 않고, 연속1–20 CSV와 epoch 기록을 사용했다. best는 고정 validation fitness 최대인 epoch5이며 CCTV 출력으로 선택하지 않았다.

14개 native Results를 CPU에서 다시 파싱해 보고된 박스 수·로컬 좌표와 원본 offset1회 결과가 일치함을 확인했다. 7개 비교 PNG는 SHA·크기·파일 무결성을 검사했으며 **이미지의 실제 사람 대응을 시각 판정하지 않았다**. 전후 박스 수는030의84초3→1,90초0→0,94초0→0,50초1→0,55초2→1,007의47.5초0→0,52.5초2→2다. 90·94초에서 새 검출 근거를 얻지 못했고 다른 프레임의 감소도 있어 채택 보류가 타당하다. 이는 정밀 GT 기반 recall 저하의 정량 입증과는 구별한다. 84초의 접근 장면 표현은 총괄이 전달한 과거 EXP-0003/0004 사용자 관찰에 근거하며 새 모델 출력에서 행동 라벨을 만든 것이 아니다.

최종 best validation의 precision0.8835/recall0.9484/mAP50=0.9411/mAP50–95=0.6200은 **미검수 valid20/24박스에 대한 일치 진단**이다. 별도 pretrained validation mAP 비교를 실행하지 않았으므로 mAP 향상을 주장할 수 없다. train loss 감소, 사람이 있는 CCTV의 검출 개선, 일반 사람 검출 유지와 행동 성능은 서로 다른 판단이다. 라벨 범위·누락·소규모 데이터·도메인 차이 중 어느 것이 결과의 원인인지 이 실행으로 확정하지 않는다.

원본 준비 사본의 전체 snapshot, 기존42 jobs/42 attempts를 바이트/행 단위로 보존했고 신규1 job/1 attempt만 추가됐다. 사전 보존 목록424파일 중419개는 그대로이며 나머지5개는 승인 이력 문서3개·추가 queue 등록·담당 assignment의 승인된 변경이다. 공개 측정값26개는 원시 summary의 값·출처 SHA와 일치한다. 결과 집계 helper는 저장 summary/CSV를 읽어 공개 집계와 로컬 loss 그래프만 만들며 모델·미디어를 읽지 않는다. PNG1800×600의 파일 무결성과 CSV20행·loss 시작/종료값도 확인했다.

**최종 판정: 기술 실행과 기록은 비교 자료로 수용, 실제 사람 박스 품질·일반화·기본 적용은 보류.** 미해결 구현 blocker는 없으며, 탐색 학습 승인으로 D0를 통과시켰다는 주장도 없다. 검토자는 GPU 초기화·학습·추론·미디어 업로드·커밋을 수행하지 않았다. 웹 완료 등록·실제 로컬 화면·GitHub 게시 확인은 총괄의 별도 전달 절차이며 이 검토에서 완료했다고 주장하지 않는다. 추가 GPU 실행·튜닝을 승인하거나 예약하지 않는다.

## 최종 바이트 결속

다음 바이트를 검토했다. 이후 보고서·측정값이 변경되면 이 결속을 그대로 재사용하지 않는다.

| 산출물 | SHA256 |
|---|---|
| [최종 보고서](../experiments/EXP-0026-exploratory-person-finetune.md) | `5f5395eaee1af10925bd1577700b01014a4a4a8d8618a5095a08bad2bfc991f2` |
| [공개 측정값](../../records/EXP-0026/metrics.json) | `259ecefb9dd2f1daf6b12d68ff54b7b2334468a51d6e37c0b133b12bebe29848` |
| 실제 실행 summary (로컬) | `ba1fdb049f2c030576817b7d781ff6180e9337a077ffd148679ee1ddd044cc99` |
| 결과 집계 helper | `24ada70ba05fb94479a8368ed745e88b9b4f46e0725e352e4ec0259948f07dab` |
| loss PNG (로컬) | `ba213fb4351956f99fcb760402a806743a85066e45cbb0b5fb379642a31c58da` |

로컬 상세 증거는 `review-detection-tests.json`, `review-evaluation-cpu.json`, `review-preflight.json`, `review-execution-binding.json`, `review-outcome-audit.json`, `review-final-binding.json`에 남겼다. 사전 승인에 쓰인 preflight receipt는 최종 결과로 덮어쓰지 않았다.
