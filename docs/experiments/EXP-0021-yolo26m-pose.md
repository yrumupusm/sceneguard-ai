# EXP-0021 — YOLO26m-Pose smoke 기술 실패·진단 미실행

2026-10-29 KST. **실제 queue smoke 두 attempt가 모두 구현 호환성 오류로 실패했고, 허용된 논리적 retry 1회를 소진했다. 모델 load는 2회, 성공한 예측 결과는 0개다. remaining265·관절 품질 평가·규칙은 실행하지 않았다.** 이는 YOLO의 사람/관절/행동 성능이 나빴다는 결과가 아니라, 이번 adapter의 기술 실행 실패다. 기본 CV/VLM 적용은 바꾸지 않는다.

승인·평가 범위는 [BATCH-0003](BATCH-0003-yolo26-pose-plan.md), [실행 계약](BATCH-0003-execution-contract.md), [ADR-0020](../decisions/ADR-0020-yolo26m-pose.md)를 따른다. 공개 측정은 [comparison](../../records/EXP-0021/comparison.json), [costs](../../records/EXP-0021/costs.json), [metrics](../../records/EXP-0021/metrics.json), 저장 실패만 읽는 [CPU builder](../../scripts/summarize_exp0021_failure.py)에 연결한다.

## 고정한 입력·모델·환경

공식 `ultralytics8.4.192` / tag `v8.4.192` / commit `922563eab42b778445e55a2edbabb6974eed8e4b`, Python3.10.12, Torch2.5.1+cu124/Torchvision0.20.1+cu124를 새 `.venv-pose-batch03`에 설치했다. pip check·CPU import·공식 source byte parity·CUDA 미초기화를 확인한 뒤 환경 전체 파일을 고정했다. 기존 환경 5개를 수정하지 않았다. 유일한 공식 checkpoint는49,036,866bytes, SHA256 `2fbf16367022256a226035695c5c389384c6706e8bb8ab8fcd0e7976f05443c4`이며 추가 가중치는 없다. 라이선스/공개 범위는 ADR을 따른다.

원본 전체 화면·640 square LetterBox114/rectFalse/FP32/batch1/conf>0.25/end2endTrue/max_det300/NMSFalse/augmentationFalse 한 조건이다. 관절 confidence>=0.5는 보존 추정치 기준일 뿐 GT가 아니며 낮거나 누락된 관절은 unknown으로 설계했다. 실제 pose가 없어 이 출력 계약의 모델 결과 검증은 완료하지 못했다.

기존 EXP-0019의 exact native PTS/RGB11개와 사전 고정 다섯 연속창을 deduplicate해267개 고유 입력을 동결했다. 창별 원본 PTS 간격은0.1초 이상이고 원본/배치 한도를 통과했다. manifest SHA256은 `6ea2fe8d692611f7808b1109a591fedff9cd8c901f13cc43474246324927883d`로 두 실행에서 같다.

| 고정 창 | 원본 PTS [start,end) | 준비한 프레임 | 예측 완료 |
| --- | --- | ---: | ---: |
| climb030 | [88,94) | 60 | 0 |
| climb007 | [62.5,67.5) | 50 | 0 |
| approach007 | [47.5,52.5) | 50 | 0 |
| approach030 | [50,55) | 50 | 0 |
| rope004 | [60,65) | 50 | 0 |

smoke는030_090/007_064 두 입력, 성공 시 remaining265 한 번이었다. 실제로는030_090에 대한 두 번째 attempt의 바깥 모델 호출만 한 번 시도됐고 결과가 반환되지 않았다. 007_064와 remaining은 예측을 시도하지 않았다. 준비한267개가 처리됐다고 표현하지 않는다.

## 두 실제 실패와 보존된 provenance

기존 canonical GPU queue와 Run `run_3d23462a014a`, Task `task_7c8a851c6d27`, Dispatch `ctx_b15556efe8cd`, 상속 lock·실제 parent/child·source/input/config hash·6144MiB gate를 사용했다. 독립 preflight와 총괄의 exact source commit/authorization 이후에만 각 attempt를 실행했다.

| 사실 | 최초 smoke | 유일한 correction retry |
| --- | --- | --- |
| 실행 commit | `b52ac221a2e43924f86efd8fbd32a0df4973ceec` | `1b12d85c20ba922de5062148045281849055ef9e` |
| attempt | `152d45f0113f4c94b44c69961a677023` | `070b7d4885154095bb84299b8f5916b8` |
| 결과 | architecture/end2end guard 실패 | `BaseModel.predict()`의 `visualize` 인자 TypeError |
| load 전 free VRAM | 7172MiB | 7169MiB |
| 모델 구성/load | 0.347499초 | 0.368981초 |
| initial validation | 3.801766초 | 3.732527초 |
| run-entry wall | 5.162014초 | 5.193570초 |
| queue attempt wall | 9.210638초 | 9.182453초 |
| load allocator allocated peak | 98,152,448bytes | 98,152,448bytes |
| load allocator reserved peak | 98,566,144bytes | 98,566,144bytes |
| 성공 반환/pose 출력 | 0 / 없음 | 0 / 없음 |

최초 실패 summary SHA256은 `593ebd605f6555dba9f426b81d6499878e03a8adfad0686ea5602bd3cb33eadb`, correction summary는 `2acff1ceae9d44e1ad2cc7acfb90ee3ffea25375ec22926963d9a04ed682ccf8`다. 최초38개 job/38개 attempt row와 실패 원문은 변경하지 않았다. correction은 별도 고정 key `batch0003-exp0021-pose-smoke-retry1`로 등록했고, stage/config/manifest/입력/모델은 동일했다. 현재 pose job2개 모두 failed이고 remaining job은 없다. 세 번째 smoke·실패 후 성공 프레임 재생성·추가 모델은 실행하지 않는다.

최초 결합 assertion은 조건별 attribute를 기록하지 않아 최초 실패의 정확한 항을 런타임 증거로 단정하지 않았다. correction에서는 실제 `person0/kpt_shape17x3/stride32`, `_end2end` 부재·getterFalse를 기록했고 공식 `inner.end2end=True` setter 후 True로 바뀌는 것을 관측했다. 이는 correction 환경에서 head 선택 초기화 차이를 확인한 것이며 최초 로그를 사후 수정하는 근거가 아니다.

이후 남은 `visualize=False`가 현재 공식 `BaseModel.predict(self,x,profile=False,augment=False,embed=None)`와 맞지 않았다. AST 정적 감사로 `visualize`만 미지원이며 `embed`는 지원됨을 확인했다. TypeError는 `BaseModel.forward`에서 `predict`의 Python 인자를 바인딩할 때 발생하므로 바깥 `nn.Module` 호출 1회는 시도됐지만 `predict` 본문/네트워크 `_predict_once`의 완료 결과는 없다. summary의 `forward_count=0`은 성공 반환 횟수이며 호출 시도0이라는 뜻이 아니다. 추가 model construction이나 GPU 검증으로 이를 재확인하지 않았다.

## 측정 범위와 테스트의 한계

두 load 합계는0.716481초, queue attempt 합계18.393090초다. load 시간은 checkpoint·FP32·CUDA 이동/동기화를 포함한다. run-entry는 lease/input 검증 전부터 시작하지만 Python/module 시작과 마지막 summary 저장은 제외한다. queue attempt에는 부모 검증·자식 시작이 포함되고, enqueue와 sourcefreeze 준비 전체 wall은 아니다. CPU 준비의 decode/RGB변환·저장·hash는 별도 costs에 기록했다.

두 번째 attempt는 CUDA 입력 이동과 shape/dtype 검사 경로에 도달했지만 실제 tensor 저장 단계는 성공 추론 뒤에 있어 tensor artifact가 남지 않았다. 별도 저장된 실제 tensor/pose 결과가 있다고 주장하지 않는다. 입력 처리·추론·후처리·저장 단계의 실패 구간별 시간과 full-process/input/generation peak는 보존되지 않아 null이다. 표의 allocator peak는 **load 직후** 값이며 두 번째 입력 할당 이후 peak나 장치 전체 VRAM으로 확대하지 않는다. 처리 FPS와 사람/관절 검출 개수는 미측정이다.

CPU 계약 테스트는 최초68run/67pass/1existing skip, 수정 후70run/69pass/1existing skip이었다. 공식 source parity, synthetic LetterBox·NMS-free threshold·좌표 변환, queue 보존/lease·unknown 관절 계약은 통과했지만 실제 inner-model 호출 signature 감사가 빠졌다. CPU 테스트 통과를 추론 호환성으로 확대했던 preflight 한계와 구현 오류를 기록한다. signature 감사는 실패 후 AST만 사용했고 모델을 구성하지 않았다.

## 품질·규칙·전달 판정

- 기술 실행: **failed**, 두 load/두 오류/논리 retry1/성공 예측0. warmup0, 추가 학습0, 새 checkpoint1.
- 사람·관절 품질: **미측정**, 관절 GT·사람 대응·시간 변화·소형 인물 복원 모두 미확인. bbox/관절 개수는 null이며 정상0검출로 대체하지 않는다.
- 행동 구분: **미측정**, 규칙·tracker 미실행. 관절이 본질적으로 부족하다는 모델 성능 결론이 아니라 기술 한도 소진으로 평가에 진입하지 못했다. 기존 경계의 fence-top/far-side 해석도 검증되지 않았다.
- 독립 검토: preflight와 correction source 검토를 받았으며 최종 실패 report/metrics의 별도 검토·등록은 총괄 전달 기록을 따른다.
- 웹/GitHub: 보고서와 비용 그래프·기존 원본 참고를 등록할 수 있으나 실제 브라우저/seek·원격 byte 확인은 총괄이 별도 증거로 확인해야 한다. 본 문서만으로 완료 선언하지 않는다.

pose 출력이 없어 원본/pose 오버레이 비교·5개 pose 동영상은 만들지 않았다. 기존 q04 원본 참고 영상을 재사용하고, 030[88,94)의 저장 원본60개로 **INPUT REFERENCE ONLY — NO POSE OUTPUT** 표시의 CPU 동영상만 준비했다. native PTS60개와 재생 시간축을 decode로 대조했다. 이는 모델 결과/영상 seek 실제 브라우저 검증이 아니며 미디어는 로컬 전용이다.

재현은 `python3 scripts/summarize_exp0021_failure.py`로 저장된 두 실패와 정확한 queue receipt만 읽어 public comparison/costs/metrics를 다시 만든다. 원본·좌표·이미지·영상·가중치·환경·raw logs/receipts는 Git 제외다. inference source13개는 수정 sourcefreeze 그대로 두며, 이 배치에서 추가 GPU 작업이나 자동 후속 실행을 하지 않는다.
