# EXP-0027 — 라벨 의미 검수를 위한 CPU 감사 준비

2026-10-29. **형식·출처·보존 검증 완료 / 의미 검수 대기 / D0 미통과.** [EXP-0027 계획 A](../experiments/EXP-0027-detection-low-confidence-diagnosis-plan.md)의 CPU 준비 결과다. 원본·잠정 라벨·이미지·기존 검수 PNG·summary·provenance를 변경하지 않았다. 별도 주석 감사 의견은 **`format/provenance verified; semantics pending`**이며 실제 사람 검수 의견은 아직 없다.

## 바이트·변환 출처 검증

원본 ZIP의 SHA256은 기존 준비 기록의 `92ee33df46b231e70a26d9901f361a67845c882ce0afd2f0c97e55dca7622549`와 같았다. EXP-0026 dataset freeze 자체의 SHA256 `26bee37c0508d86d0f08b3bbd1be348cf8916c54aa1b094710e7b96be50f2606`도 고정값과 대조했다. 해당 목록의 **1,108개 준비 파일 전체**를 실행 전·감사 후·산출물 생성 후 다시 해시 검증했고, 파일 추가·누락·변경은 0이다.

ZIP의 파일 항목 499개와 로컬 source 고유 항목 497개를 대조했다. 차이 2개는 준비 때 내용 동일성을 확인해 보존한 루트 설정 파일의 ZIP 내 중복 항목이다. 모든 ZIP 멤버 인덱스와 SHA, source 바이트, 이미지 사본, 원본·변환 라벨, 기존 비교 PNG 113개의 해시가 일치했다. 원본 601행을 다시 읽어 독립적인 Decimal 계산으로 bbox 값 보존·polygon min/max 외접 변환·클래스 매핑을 확인하고, provenance의 원본 행 번호/해시·출력 행 번호/해시와 대조했다. 이미지는 바이트만 읽었으며 디코딩하거나 내용을 판정하지 않았다.

| 항목 | 확인 결과 |
| --- | ---: |
| 이미지 / 라벨 쌍 | 247 |
| split 유지 | train 210 / valid 20 / test 17 |
| 원본 주석 행 | 601 |
| 제외된 fence 행 | 247, 원본 보존 |
| 사람 bbox 유지 | 335행: people-jump-fence 8 + person-climbing-fence 327 |
| 사람 polygon 외접 bbox 변환 | 19행, 모두 person-climbing-fence |
| 잠정 person 행 | 354: train 279 / valid 24 / test 51 |
| 기존 검수 패널 | 113 |
| 이미지 제외 / 원본 변경 | 0 / 0 |

EXP-0026 기록상 test17은 학습·검증에 미사용이다. 이번 감사에서 기존 test 이미지의 바이트·주석·패널 목록을 읽은 것은 모델의 test 평가가 아니다. 준비 당시 summary의 `training_approved:false` 등은 과거 준비 상태로 그대로 보존했으며, 이후 별도 승인된 EXP-0026 학습 이력을 취소하거나 덮어쓰지 않는다.

## 우선 검수 목록과 중복 제거

검수 단위는 원본 **주석 행**, **이미지**, **패널**을 구분한다. 사람 수를 추정해 행을 나누지 않았다. 우선 집합은 아래 두 위험 요소의 합집합이며, 같은 원본 라벨 파일·행 번호는 한 번만 포함한다. 여러 행이 있는 패널도 패널 목록에는 한 번만 나온다.

| 집합 | 원본 행 수 | 고유 이미지 | 고유 패널 |
| --- | ---: | ---: | ---: |
| people-jump-fence | 8 | 3 | 3 |
| 사람 polygon | 19 | 12 | 12 |
| 두 집합 교집합 | 0 | 0 | 0 |
| 중복 제거 우선 집합 | 27 | 15 | 15 |

8행과 19행은 원본 라벨 유형에 따른 **검수 우선순위**이며, 27명의 사람이나 27건의 오류를 뜻하지 않는다. 전체 113패널은 파일명 기반 후보 107그룹의 대표본과 모든 우선 대상의 기존 선택 결과다. 후보 107그룹은 독립 원본·카메라·장소 수로 입증되지 않았고, 증강·유사 이미지의 split 누수를 배제하지 못한다.

## 로컬 검수 자료와 상태

새 산출물은 Git에서 제외되는 `runtime/EXP-0027/label-audit/`에만 두었다. 새 패널·원본 이미지 사본·웹 기능은 만들지 않았다. 로컬 Markdown 인덱스는 기존 비교 PNG와 raw source 이미지·원본 라벨·변환 라벨을 직접 연결한다. 우선 15패널과 전체 113패널을 각각 탐색할 수 있다. 전체를 지금 사람에게 검수해 달라고 요청하지 않았다.

| 로컬 파일 | 내용 |
| --- | --- |
| `manifest.local.json` | 113패널과 원본/변환 행 provenance 연결, 전체 입력의 감사 전후 해시 |
| `priority.local.json` | 중복 제거 27행·15패널 및 사유·교집합 집계 |
| `index.local.md` | 우선 패널과 전체 패널의 기존 로컬 파일 링크 |
| `review-schema.local.json` | 허용값·초기값과 행/패널 단위 구분 |
| `panel-review-template.local.csv` / `.json` | 전체 113패널의 검수 기록 빈 양식 |
| `row-review-template.local.csv` / `.json` | 전체 잠정 사람 354행의 개별 검수 빈 양식 |
| `counts.local.json` | 비식별 집계와 미검수 상태 |
| `preservation.local.json` | ZIP·freeze·전체 입력의 최종 보존 증거, 산출물 해시 |

패널 단위 항목은 화면 전체 메모이고, 각 라벨이 무엇을 감쌌는지는 행 단위 양식에 따로 기록한다. 전체 354행 중 기존 패널에 없는 이미지의 행은 `panel_id`가 비어 있다. 해당 빈칸은 기존 검수 패널이 없다는 의미이며 새 이미지를 만들거나 자동 판정하지 않는다.

| 필드 | 허용값 / 초기값 |
| --- | --- |
| `representation` | one_person / multiple_people / scene / **unknown** |
| `extent` | whole_body / visible_body_part / fence_included / **unclear** |
| `unlabelled_people` | yes / no / **unknown** |
| `c6_gate_similarity` | yes / no / **unknown** |
| `c6_distant_similarity` | yes / no / **unknown** |
| `c6_occlusion_similarity` | yes / no / **unknown** |
| `converted_bbox_fit` | suitable / unsuitable / **unknown** |
| `reviewer`, `reviewdate`, `note` | 빈칸, 사람이 검수할 때 기록 |
| `review_pending` | **true** |

현재 상태는 **113패널 전부 review_pending, 검수 완료 0**, 사람 행도 **354행 전부 review_pending**이다. 모든 이미지 내용은 UNKNOWN이다. `extent:unclear`는 스키마의 미확정 초기값이며 가림·불량을 관찰했다는 뜻이 아니다. C6 철제문·원거리·가림 유사성, 미라벨 사람, 개인/복수/장면 표현, 변환 bbox 적합성을 기계적으로 채우지 않았다.

## 재현·검증과 한계

추가 설치 없이 표준 Python으로 실행한다. `CLIMBING_ARCHIVE`는 기존 원본 ZIP의 로컬 경로다. 산출물이 이미 있으면 덮어쓰기를 거부하므로 기존 검수 양식을 수정·초기화하지 않는다.

```bash
python3 -m unittest discover -s tests_data -p 'test_exp0027_labels.py' -v
python3 scripts/audit_exp0027_labels.py --archive "$CLIMBING_ARCHIVE"
```

CPU 합성 테스트 **13개 통과**: 행/이미지/패널의 교집합과 합집합 중복 제거, 패널 대응·누락, 미검수 enum/state 유지, 원본 ZIP/freeze/이미지/라벨/패널/metadata 변조 및 파일 추가·누락 거부, 독립 provenance 대조, 입력·산출물 덮어쓰기와 symlink/경로 우회 거부를 확인했다. 실제 이미지 입력 없이 테스트가 통과하며 이미지 디코딩 라이브러리를 사용하지 않는다.

이 감사는 원본 한 주석을 잠정 박스 하나로 옮긴 준비 과정의 형식·바이트·출처만 확인한다. 실제 사람별 정답, bbox 의미·누락·학습 적합성·원 이미지별 권리, 독립 일반화, EXP-0026 결과의 원인은 미확정이다. **D0 통과나 학습 성공·기본 채택의 근거가 아니다.** 이 담당 작업의 GPU/추론/학습/모델 다운로드/새 프레임 디코딩은 모두 0이며, EXP-0027의 별도 낮은 점수 추론 결과를 대신하지 않는다. 원본 수정·리라벨·삭제와 후속 실험은 수행하지 않았다.
