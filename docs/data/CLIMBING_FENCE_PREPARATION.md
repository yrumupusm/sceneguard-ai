# Climbing Fence v1 — 사람 bbox 잠정 변환

2026-10-29. **CPU 데이터 준비 완료, 사람 검수 대기, D0 미통과, 학습 미승인.** 사용자가 이번 준비에 한해 시각 검수 전에 잠정 변환하도록 명시했다. [BATCH-0007 계획](../experiments/BATCH-0007-roboflow-person-finetune-plan.md)의 검수 전 변환 금지를 이 준비 범위에서만 대체한다. 실제 학습·모델 추론·GPU 사용·모델 교체는 수행하지 않았다.

원출처는 [Roboflow Climbing Fence v1](https://universe.roboflow.com/osborne-rowland-r4w5m/climbing-fence/dataset/1)이며, 로컬 아카이브의 SHA256은 `92ee33df46b231e70a26d9901f361a67845c882ce0afd2f0c97e55dca7622549`다. 보관된 export의 클래스는 `fence`, `people-jump-fence`, `person-climbing-fence` 세 개다. 계획 단계의 공개 프로젝트 설명과 실제 export 구성을 구별한다. 공개 페이지의 CC BY 4.0 표시만으로 원 이미지별 권리 검토가 끝났다고 판단하지 않는다.

## 변환 결과와 가정

| 항목 | 수량 / 처리 |
| --- | --- |
| 이미지 / 원본 라벨 파일 | 247 / 247, 제외 이미지 0 |
| 기존 split | train 210 / valid 20 / test 17 유지 |
| 원본 주석 | 601행 |
| fence | 247행을 새 학습 라벨 사본에서 제거, 원본 보존 |
| 사람 bbox | 335행의 xywh 숫자 토큰 그대로 유지 |
| 사람 polygon | 19행을 행별 min/max 외접 bbox로 변환 |
| 잠정 person | 354행, 클래스 ID 0 |
| split별 잠정 person | train 279 / valid 24 / test 51 |
| 검수용 비교 PNG | 113장: 파일명 기준 107개 그룹의 대표본 + 모든 사람 polygon 19행·people 8행 포함 |

**원본 주석 한 행을 잠정 박스 하나로 대응**시킨다. `people-jump-fence`도 이번 준비에서는 동일하게 처리하되, 그룹 박스가 개인 박스라는 승인을 뜻하지 않는다. 원본 박스가 전신/부분 신체/복수 인물/장면 영역인지, polygon 외접 박스가 사람 검출 학습에 적합한지는 사람이 확인해야 한다. 사람 수를 추정해 나누거나 이미지를 제외하거나 좌표를 보정하지 않았다. 검수 이미지 생성은 의미 검수 완료가 아니다.

파일명 기준 107개 그룹은 독립 원본·카메라 수의 확정값이 아니다. 증강·유사 이미지의 분할 누수는 완전히 배제되지 않았으며, 기존 val/test를 독립 일반화 성능의 근거로 사용하지 않는다. 이미지별 원출처·권리와 누락 라벨도 검토 대기다.

## 재현 명령

저장소 루트에서 기존 `.venv-pose-batch03` 환경을 그대로 사용한다. `CLIMBING_ARCHIVE`는 사용자가 보관한 ZIP의 로컬 경로로 지정한다. 다운로드나 의존성 설치 단계는 없다.

```bash
.venv-pose-batch03/bin/python -m unittest discover -s tests_data -p 'test_prepare_climbing_fence.py' -v

.venv-pose-batch03/bin/python scripts/prepare_climbing_fence.py \
  --archive "$CLIMBING_ARCHIVE" \
  --output data/climbing_fence/person_bbox_draft_v1 \
  --overlays
```

실제 변환은 한 번 실행했다. 이미 결과 경로가 존재하면 다시 실행해도 덮어쓰지 않고 실패한다. 합성 테스트만 별도 임시 디렉터리에서 반복 실행한다. 기본 SHA256은 위 아카이브에 고정되어 있으며 `--expected-sha256`은 합성 자료의 재현 테스트에 사용한다.

새 로컬 데이터셋에는 기존 split의 이미지·새 bbox 라벨, `data.yaml`, `summary.json`, `manifest.json`, `provenance.jsonl`, `review/` 비교 PNG를 둔다. `source/`는 원본 이미지·라벨·설정·귀속 문서를 바이트 그대로 보관한다. ZIP의 동일한 `data.yaml` 세 항목은 내용 동일성을 확인한 뒤 한 파일로 보관하고, 원래 ZIP 내 세 인덱스는 manifest에 남긴다. 원본 ZIP 자체도 변경하지 않는다.

새 `data.yaml`의 `path`는 실제 로컬 결과 경로, `train`/`val`/`test`는 각각 `train/images`/`valid/images`/`test/images`이며, `nc: 1`, `names: [person]`이다. 구조가 로더와 호환된다는 사실은 학습 승인이 아니다. `usable_for_training: false`, `training_approved: false`, `D0_passed: false`, `status: review_pending`은 `summary.json`의 상태 기록이며 별도 trainer 실행을 기술적으로 차단하는 통합 기능은 구현하지 않았다. `manifest.json`에는 source 멤버·샘플·검수 이미지의 해시 목록을 기록한다.

## 검증 범위

합성 테스트 12개가 polygon min/max, bbox 값 보존, 클래스 재매핑, 혼합 행, 비정상 좌표·형식·경계, ZIP 경로/심볼릭 링크/중복 충돌, 기존 결과 비덮어쓰기를 검증했다. ZIP 경로·파일 종류·크기를 제한하고, 중복 이름은 동일 내용의 루트 `data.yaml` 최대 세 항목만 허용한다. 모든 주석은 유한값·정규화 범위·양의 박스 크기·박스 모서리 경계를 검사한다. 실패 행을 조용히 버리거나 clipping하지 않으며, 행 검증을 마치기 전에는 결과 디렉터리를 만들지 않는다.

변환기와 분리된 CPU 대조에서 원본 ZIP SHA, 전체 source 항목, 이미지 바이트, raw 라벨, 원래 split, 601개 행의 출처·SHA와 354개 출력 박스·경계를 확인했다. 기존 설치본 Ultralytics 8.4.192의 `verify_image_label`을 모델 없이 CPU에서 호출해 247쌍·354행을 확인했고, 누락·빈 라벨·손상·중복 제거 메시지는 0이었다. 설치·네트워크·CUDA 초기화를 사용하지 않았고, 검증 전후 데이터셋 파일 해시도 동일했다. 이는 형식 검증이며 사람별 bbox 정확도나 검출·행동 성능 검증이 아니다.

행 provenance는 원본 ZIP 멤버 인덱스·파일·행 번호·클래스·bbox/polygon 유형·raw 행과 SHA·출력 행 번호/내용/SHA·출력 라벨 파일 SHA를 로컬에 기록한다. fence 제거 행도 출처를 보존한다. 공개 문서에는 집계·가정·재현 코드만 포함하고, 원본 이미지·raw 라벨/좌표·provenance·오버레이·로컬 실행 증거는 게시하지 않는다. 다음 판단은 사람의 라벨 의미 검수와 D0 조건 확인이며 학습·추론은 별도 승인이 필요하다.
