# EXP-0068 독립 검토

2026-11-08. 검토 담당은 구현·GPU 실행을 수행하지 않는다. 작업 범위는 YOLO26m의 확정 사람 라벨 소량 5epoch 학습과 동일 검증 25프레임의 전후 비교다. YOLO26m/l/x·EVAD-B/L·STMixer의 전체 비교 범위를 취소하지 않으며, 학교 성능 개선이나 행동·신원 정답을 뜻하지 않는다.

현재 단계: 실제 단일 5epoch 학습과125 optimizer 업데이트, 체크포인트·원시 출력·큐 보존을 독립 확인했다. 검증 TP/FP/FN은31/0/0→6/0/25로 악화됐다. root 최종 보고서·공개 지표22개·비교 영상·누락 진단의 정확한 해시 검토까지 완료했다. 실행·결과 검토의 미해결 차단 사유는 없다.

## 데이터와 사용자 답변

작업 시작 시 `docs/WEB_REVIEW_WORKFLOW.md`를 읽고 실제 `pending --include-acknowledged`를 조회했으며 결과는 빈 목록이었다. 실제 저장소의 EXP-0067 세 요청을 별도로 읽고 등록 바인딩도 검증했다. 세 답변은 모두 `version=4`, `answer_version=1`, `status=applied`이며, 각 25프레임의 표시된 모든 박스와 보이는 사람에 수정할 곳이 없다는 명시적 답변이다. 기존 확인을 반복 질문하지 않았다.

독립 검사 `runtime/model-comparison/exp0068/reviewer/audit_dataset.py`와 `dataset-audit.json`은 다음을 확인했다.

- 확정 manifest SHA256 `1bda84cc3421bcfc1b528bfb4e4092c02e9ec22d4a09c41907ff46211381ad18`와 75 PNG·75 라벨 파일 해시, 디코딩 RGB, native PTS/프레임 식별자 보존.
- 표시된 제안과 182 확정 좌표가 동일하며 COCO 내보내기도 동일. YOLO 좌표 역변환 최대 오차는 `1.4106251455814345e-07` 픽셀.
- 원래 학습 50프레임/151박스/2사건과 검증 25프레임/31박스/1사건 분할 보존. 사건·원본 해시가 양쪽에 겹치지 않음.
- 기존 split manifest의 배정과 정확히 일치. 학교45와 보호 시험296개 원본 해시와의 중복0이며 보호 원본 픽셀을 읽지 않음.
- 사람 완전성만 확인됐고 행동·신원 정답은 계속 미확인. 불변 EXP67의 `training_release=false`는 라벨 부족을 뜻하지 않으며 새 실행 프로토콜과 승인 바인딩으로 분리한다.

## 사전학습 person 보존

기존 로컬 환경에서 GPU를 숨기고 공식 `weights/yolo26m.pt`(SHA256 `401cea9ab23ad19246ff7744859816bc599f350e93c9dd30367b6f0a0745d0b7`)를 CPU에 로드했다. forward나 학습 없이 실제 `adapt_person`의 state dict를 독립 대조했다. `cv3` 및 `one2one_cv3` 각각 세 스케일의 최종 weight/bias 12개만 COCO class0 행으로 축소되었고, 해당 값은 비트 단위로 동일하다. 나머지756개 텐서는 동일하며 두 헤드의 hidden width256은 보존된다. 무작위 분류층 초기화가 없다. 근거는 `adaptation-audit.json`이다.

학습 전 공식80클래스와 적응1클래스의 원시 회귀·class0 출력을 양쪽 헤드와 검증25프레임에서 비교하는 코드를 읽었다. 클래스 간 top-k 경쟁이 바뀌므로 공식80클래스의 최종 검출 목록과 단일클래스 목록을 동일하다고 주장하지 않는다. 전후 비교는 같은 적응1클래스의 초기 상태와 고정 마지막5epoch 상태를 사용한다.

## 실행·평가 코드 검토

초기 검토한 trainer는 FP32·640·batch2·AdamW LR1e-4·무증강 직접 학습 루프로, 각 epoch의50프레임을 한 번씩 사용하고125 optimizer step을 요구한다. 초기/최종 native model, 전체 state dict와 optimizer 상태를 저장하며 EMA나 검증 성능에 따른 best 선택을 사용하지 않는다. 유한 loss/gradient/state, 실제 파라미터 변경을 검사한다. 최종 실행 후보와 소스 해시 고정 뒤 재확인했다.

평가기 `scripts/evaluate_person_detector_pair.py`를 읽고8개 시험을 독립 실행해 모두 통과했다. 고정 person confidence≥0.5 및 IoU≥0.5의 프레임별 최대 개수 일대일 매칭이며 AP가 아니다. 중복 검출은 FP로 남고 다른 사람 검출이 누락을 지우지 않는다. 픽셀/시각/프레임 집합이 달라지면 거절한다. GT별 회복·새 누락은 해당 프레임의 매칭 결과이며 사람 신원 추적을 뜻하지 않는다.

## 해석 범위와 별도 전달 확인

실제 학습 결과와 root 최종 보고서·공개 지표 검토는 아래에서 완료했다. 웹 등록·실제 브라우저·게시·작업자 정리는 조정자의 별도 전달 확인 범위다. 검증은 단 한 사건의25프레임으로 서로 상관되며 YOLO26x 제안 기원 선택 편향이 남는다. 이 범위를 학교45 또는 독립 일반화 성능으로 확장하지 않는다.

## 정확한 실행 후보 승인

`7a41f9f0779fbc327eae654924f498ded33d6ba8`의 14개 소스 바이트를 commit 및 현재 작업 파일과 대조했다. 프로토콜·trainer·queue hook·평가 코드·웹 답변 확인 경로가 포함된다. 최종 후보 `candidate-063cdad81f66a033.json` SHA256은 `a252a61074b66f8849e7a4cc1dffe58e93680bb56b72040022e7e924e135b825`다. 실제 입력 계약을 새로 계산해 `ba83b2fc4e76df6ba5e3f72cc8c753ddcdb31cb81338b223452d83839a14bc26`와 대조했고, 현재 웹 답변 바인딩·환경/모델·실행자·Orca 활성 배정과 기존144 jobs/144 attempts의 동일성 및 유휴 상태를 확인했다.

기존 실제 모델 CPU state 보존 검사와 추가 학습8/평가9 시험 통과를 근거로 `runtime/model-comparison/exp0068/reviewer/execution-release.json`을 작성했다. SHA256 `4b873e61576f25dfd87acec03e0e7c0d289b2b8af31f727aca073dc6e89a8552`이며, 오직 해당 후보의 단일 학습 실행을 독립 승인한다. root GO나 실제 결과 수용을 대리하지 않는다. 시험의 초기 오류는 스케일2 문자열을 최종층2로 오인한 시험 oracle이었으며 구현 담당이 shape 기준 비교로 수정한 뒤17개를 재실행해 모두 통과했다.

### 최초 후보 승인 폐기 — 실행 전 발견

구현 담당이 GO 전에 Ultralytics8.4.192의 `loss_items` 반환값이 tensor가 아닌 named-scalar dict임을 발견했다. 최초 검토에서 이 로깅 불일치를 놓쳤으며, 원래 코드는 첫 optimizer step 뒤 로그 작성에서 실패했을 것이다. root GO·enqueue가 없는 시점에 기존 `execution-release.json`을 사용 불가로 통지했다. 기존 후보와 승인 파일은 이력으로 보존하며 `release-superseded.json`에 폐기 이유를 남긴다. 설정·데이터·학습 예산 변경이나 GPU 재시도는 없다.

### 수정 후보 승인

최소 named-scalar 로그 수정과 실제 native `E2ELoss` 합성 raw head의 loss/backward·epoch gain 시험을 읽고 학습10/평가9 시험을 독립 실행해19개 모두 통과했다. 기존 데이터 검토를 반복하지 않고 변경된2개 소스와 전체 고정 source map·실제 입력·현재 답변·실행자·기존144큐 행·활성 배정을 확인했다.

새 commit `40c434a70fd50a03b4698a7d18780a3febc2f8c0`, 후보 `candidate-a31fa76996a526a3.json` SHA256 `71e1e1433414147deaeb97d7ac3befa9a34800e9a0dfd2c868a15f7dd6bf76df`를 승인한다. 유효한 독립 승인 파일은 `execution-release-v2.json` SHA256 `7b45f43877dfa10cc4f80caa30d13ca55ce1f3014870c44fc6c537f50bef5adc`이며 최초 승인 파일을 명시적으로 대체한다.

## 실제 결과 독립 확인

단일 canonical job `1d01c841d451418cbb68f8fca4be2b16`, attempt `47adf16ca4fa4145b50e0ee150106c38`는 exit0으로 완료했다. read-only 실제 DB와 승인·receipt·result를 대조해 기존144 jobs/144 attempts의 모든 행이 동일하고, 각1개만 추가되어145/145이며 큐가 유휴임을 확인했다. child와 supervisor 모두 종료된 실제 process identity다. 재시도0. 근거: `queue-result-audit.json`.

`audit_actual.py`는 GPU·forward 없이 초기/최종 full checkpoint를 CPU에 읽었다. 초기 state는 공식 사전학습 person 적응 상태와 비트 단위로 같다. 최종 모델의396개 학습 파라미터가 모두 변경되고 유한하며,396개 optimizer 상태의 step은 각각125다. backbone 첫 블록3개, 실제 detector one-to-many box24/classifier42, one-to-one box24/classifier42의 변경도 별도로 확인했다. BN buffer 변경만을 학습 증거로 사용하지 않았다. 전체125개 로그의 gradient norm은 양수·유한하며 각 epoch에서 학습50프레임을 정확히 한 번씩 사용했다. 실제 원시 회귀·person logit 초기 적응 차이는 두 헤드·25프레임 모두0.0이다.

전후 각각25×8400×5 원시 anchor 배열이 유한하고,0.05 유지·상위300·유효 박스 필터로 얻은 JSON 행이 원시 배열과 동일함을 확인했다. 실제 프레임ID·픽셀 해시·시각도 일치한다. 평가기의 augmenting-path 구현과 별개인 subset-DP 매칭으로 각 프레임의 최대 일대일 매칭 수를 계산해 모든 행의 TP/FP/FN과 일치함을 확인했다.

| 고정 person≥0.5 / IoU≥0.5 | TP | FP | FN | 재현율 | F1 |
|---|---:|---:|---:|---:|---:|
| 적응1클래스 학습 전 |31|0|0|1.000000|1.000000|
| 마지막5epoch 학습 후 |6|0|25|0.193548|0.324324|

둘 다 검출6, 새 누락25, 회복0, 둘 다 누락0이다. 정밀도는 양쪽1.0이지만 학습 후 출력은6건뿐이다. 낮아진 학습 loss(2.107138→1.076205)를 검출 성능 개선으로 해석하지 않는다. **실제 학습 실행은 성공했고, 이 고정 검증 결과는 악화됐다.** 추가 학습·임계값 변경·best 선택 없이 결과를 보존하며 기본 모델 교체를 권하지 않는다.

| 실제 근거 | SHA256 |
|---|---|
| result.json | `cca006fd4d57ee83dba32e614ef4528f336670b3697038e6c0dfa4f3789b7aff` |
| canonical receipt | `c76fd3f300488760f7b8de9605c6a3ead41251f8ecbd5f54cf9d748b7c44a15c` |
| initial.pt | `436426a56cb2699c7be3391b3dc1e4c06b268b357b330e3b1cf13409ee01ef53` |
| last.pt | `42c348982b4788c23fe731ede7117a40098b2fb3c995d6f4faee3687fc5544b9` |
| executor paired-evaluation.json | `5065df51571eba5256b092ddcaa2413b1d632a632620d979c3e0ae6249977d2a` |

실제 출력9개 파일의 모든 해시를 대조했고 상세 목록은 `actual-output-audit.json`에 남겼다. 학교45/EXP64시험·행동·신원 성능은 측정하지 않았다. 이번 검증은 한 사건의 상관된25프레임이고 검수된 YOLO26x 제안 기원의 선택 편향이 있으므로 독립 일반화 결과가 아니다.

## 최종 보고서·공개 집계·비교 영상 수용

root의 최종 결과 보고서와 공개 결과 JSON을 실제 result·평가·진단·preview에 필드별 대조했다. 공개 지표22개의 값·출처 해시도 모두 확인했다. 실행 성공과 성능 악화, 기본 미채택, 학교/행동 미측정, 검증 한 사건과 제안 기원 편향, 메인6모델 범위 유지가 명시되어 실제 근거와 일치한다. 수치와 해석을 수용하며 추가 튜닝을 승인하는 검토가 아니다.

누락 진단 코드를 읽고25개 누락 GT를 저장된 원시 anchor로 독립 재계산했다. 모두 IoU≥0.5 후보가 있지만 그중 최고 person score가0.5미만이며 범위는 `7.94734717146639e-07–0.43162697553634644`다. 독립 float64 IoU와 기록값 최대 차이는 `1.551001326260959e-07`이다. 이는 출력 현상만 입증하며 점수 하락의 학습 원인을 확정하거나 임계값 변경을 정당화하지 않는다.

로컬 영상 전체를 PyAV로 디코딩해25프레임·3FPS·2880×640과 원래 프레임/PTS 순서, 정답31/전31/후6의 박스 합계를 확인했다. 렌더 코드를 읽고 실제 디코딩 RGB에서68개 박스의 좌우·하단 경계 좌표를 샘플링했으며, 모두 청록/주황 테두리와 압축 허용 범위 내에서 일치했다. 영상의 새 행동·신원 정답을 만들거나 클라우드 이미지 도구로 전송하지 않았다. 이 검사는 로컬 미디어 바인딩·오버레이 배치 확인이며 실제 웹 브라우저 재생 검증과 구분한다.

| 최종 수용 자료 | SHA256 |
|---|---|
| `docs/experiments/EXP-0068-results.md` | `1d2b55cc19b16aef7f2df3c2842a592b01801785aa89e69977d341e6229e5192` |
| `records/EXP-0068/results.json` | `343f2808a94bb80fa5608617c8ff59a2935e248201616c26c5e7d78c2df57fe6` |
| `records/EXP-0068/metrics.json` | `a8819dd38a7943244091ad856e31a69125b461d55f6cada34c7efe0ef25f70ba` |
| `docs/experiments/EXP-0068-execution.md` | `4c75a9b89007c82689273333d90ab28af37ebf9769b307e856472c8956107e40` |
| `miss-diagnosis-v1.json` | `6b7d5059f00efb9c9b6d7c397bdbea0beb9d6ca0e4f80175ddbb0465c4a47212` |
| `preview-v1/manifest.json` | `82207e3b7a85fc6529d5245bf4455ee827fec3b5189023fe1acc9ef92f07dd78` |
| `validation-before-after.mp4` | `58a1e198075141a2e936a85d4bb2a9ac6bbf9c41e2d2548d6b45dd1797bc7ca4` |

최종 기계 확인은 `runtime/model-comparison/exp0068/reviewer/final-artifact-audit.json`, 상세 독립 증거는 같은 폴더의 `actual-output-audit.json`, `queue-result-audit.json`, `diagnosis-audit.json`, `preview-audit.json`, `overlay-pixel-audit.json`에 보존한다. 리뷰 담당은 구현·GPU 실행·원본 라벨 변경을 하지 않았다. 이번 독립 실행·결과 검토는 완료이며, 웹·브라우저·게시 전달 완료 여부는 root의 전달 기록을 따른다.
