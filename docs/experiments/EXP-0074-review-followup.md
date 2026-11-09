# EXP-0074 추가 세 프레임 검수 반영

2026-11-09. 사용자 대화의 **“검수완료”**와 P01 편집기에 저장된 세 프레임의 1차 수정본을 함께 반영했다. 추가학습은 실행하지 않았다. 원래 등록된 EXP-0074 보고서·지표·검수 근거와 개발75 결과는 변경하지 않고 이번 개발78 결과를 별도로 보존한다.

## 승인 근거와 실제 반영

원본56.000·58.333·61.667초 모두 저장된 사람 박스2개, `confirmed=true`였고 메모는 없었다. 상태 선택은 `draft`로 남아 있었다. 과거 초안을 자동 승인한 것이 아니라, **이번 대화에서 명시한 완료 확인과 각 프레임에 저장된 모든 사람 확인을 결합**했다. 편집기 DB의 상태·좌표·revision은 변경하지 않았다. 대화 원문을 웹 질문에 전사할 때도 “사용자 대화 전달·에이전트 전사”라고 표시하며 사용자가 웹에서 직접 답했다고 기록하지 않는다.

적용은 이 세 프레임·6개 박스에 한정한다. P01의 나머지21프레임이나 다른 미확정 보완본에 승인을 확대하지 않는다. 기존 승인5박스·배경 제거·야간23.333초 제외는 유지한다. 다시 확인을 요청하지 않았다.

새 목록은 `outputs/model-comparison/exp0074/person-data-v2/manifest.json`이다. 기존197프레임의 행·이미지·좌표는 그대로이고, P01의 개발 예약01에만 세 장을 추가했다. 원본 SHA·촬영 그룹·예약의 학습/개발 교차0, 학교45·EXP64 시험 보호 자료 미포함을 확인했다. 개발 자료이며 실제 촬영 독립성이나 독립 시험 인증은 아니다.

| 자료 | 프레임 | 사람 박스 행 | A TP | A FP | A FN |
|---|---:|---:|---:|---:|---:|
| 학습, 변경 없음 | 122 | 333 | 288 | 9 | 45 |
| 기존 개발 | 75 | 56 | 56 | 0 | 0 |
| 새 P01 개발 | 3 | 6 | 6 | 0 | 0 |
| 합친 개발 | 78 | 62 | 62 | 0 | 0 |

기존197개 예측은 그대로 재사용했고, 새 세 프레임만 같은 YOLO26m step0 초기 가중치로 CPU 평가했다. FP32/640 letterbox/one2one top300/추가 NMS 없음/confidence0.5/IoU0.5를 유지했다. 모델 상태 불변·CUDA 미초기화를 확인했다. 집계는 프레임별 박스 행이며62명이나62사건이라는 뜻이 아니다.

개발 정답의 입력640 기준 크기는 작은2·중간32·큰28이며 모두 검출됐다. 명시적 빈 배경25프레임의 FP도0이다. 새 P01 세 장은 같은 촬영의 대표 프레임이고 새 독립 사건3개로 세지 않는다. 무주석을 빈 배경으로 사용하지 않았다.

## 첫 비교 준비의 현재 상태

기존 검출 유지·새 누락·오검출 비교는 준비됐다. **누락 회복의 개발 분모는 여전히0**이므로 B/C의 회복 성능은 미측정으로 남긴다. 새 검수 완료나 개발100%를 성능 개선으로 보고하지 않는다. 학습 자료의45FN을 개발 성능으로 옮기지 않는다.

개발 목록만 새 버전으로 고정한 B/C 계획을 `runtime/model-comparison/exp0074/review-followup-v1/bc-plan.json`에 저장했다. 학습122프레임/333박스, 초기값, 설정, epoch별 순서와305step 계획이 이전과 정확히 같다. B는 BN 통계 갱신, C는 통계 고정·affine 학습 가능 조건을 유지한다. 실제 학습·큐 등록·재시도는0이다. 기존 큐145 jobs/145 attempts도 그대로다.

검출 유지 비교를 시작하기 위해 이번 세 장을 재검수할 필요는 없다. 누락 회복까지 검증하려면 같은 학습 촬영과 분리된 작은 사람·강한 가림·월담 자세의 개발 사례를 더 확보하고, 모든 보이는 사람을 검수한 뒤 A가 실제로 놓치는지 확인해야 한다. 시험 자료 확보는 별도이며 이번에 학습을 시작하지 않았다.

## 재현과 검증

```bash
python3 scripts/import_exp0074_review.py \
  --evidence runtime/model-comparison/exp0074/review-followup-v1 \
  --output NEW_PERSON_DATA_DIRECTORY
CUDA_VISIBLE_DEVICES='' .venv-pose-batch03/bin/python scripts/evaluate_exp0074_baseline.py \
  --manifest NEW_PERSON_DATA_DIRECTORY/new-frames-only.json --output NEW_P01_BASELINE_DIRECTORY
python3 scripts/summarize_exp0074_review.py \
  --manifest NEW_PERSON_DATA_DIRECTORY/manifest.json \
  --old outputs/model-comparison/exp0074/baseline-v1 \
  --new NEW_P01_BASELINE_DIRECTORY --output NEW_COMBINED_BASELINE_DIRECTORY
python3 scripts/prepare_person_bn_comparison.py prepare \
  --manifest NEW_PERSON_DATA_DIRECTORY/manifest.json --output NEW_PLAN_JSON
```

이번 출력은 각각 `person-data-v2`, `baseline-p01-v2`, `baseline-combined-v2`다. 입력 검수 패키지, 정확한 편집기 revision, 대화 승인 원문과 처리 이력은 로컬에 보존한다. 각 명령은 기존 출력을 덮어쓰지 않는다. 검수 승인 범위5개 시험과 기존 라벨/평가20개 시험, 합계25개가 통과했다. 불확실·미확인 프레임, 변경된 revision과 과거 메모만으로 완료시키는 경우를 거절한다.

| 고정 자료 | SHA256 |
|---|---|
| 새200프레임 목록 | `22ee2a361eaf613e63a1d8af74b6b530530814935796b86313dc7a1024497f09` |
| 합친 A 집계 | `23e34a1ddd30fe9db3b41fa2cb45d4a22f7ca100601c5cf1ac0a80686624144c` |
| 새 B/C 준비 계획 | `013220537294e5aae995ccc9f7e427c5004dbe948343c3387bbc915efbb9ad6f` |

원래 웹 지표는 개발75의 동결 결과를 유지한다. 새 개발78 결과는 이 후속 보고서와 해당 검수 요청의 반영 메모로 구분해 전달한다. 원본 영상·좌표·DB·가중치는 로컬 전용이며 공개 GitHub에는 코드·집계·후속 보고서만 게시한다.
