# BATCH-0007 잠정 person bbox 준비 독립 검토

2026-10-29. 상태: **잠정 변환 구현·출력·문서 PASS / 사람 검수 대기 / D0 미통과 / 학습 미승인**.

사용자는 이번 준비 작업에 한해 사람/그룹 의미 검수 이전의 잠정 변환을 명시적으로 승인했다. 원 주석 한 행을 잠정 박스 한 개로 취급하며 사람 한 명의 정답으로 승인하지 않는다. **D0 미통과, 사람 검수 대기, 학습 미승인**이다.

독립 검토자는 원본 ZIP을 읽기 전용으로 검사했다. 이미지 표시·업로드, 모델 로딩·학습·추론·GPU, 의존성 설치, 큐 변경 및 Git 작업을 하지 않았다. 이전 검사 보고서의 집계만 인용하지 않고 ZIP member와 모든 라벨을 별도로 파싱하고 Decimal 연산으로 polygon 변환 기대값을 계산했다.

| 확인 항목 | 독립 감사 결과 |
| --- | --- |
| 원본 ZIP SHA256 | `92ee33df46b231e70a26d9901f361a67845c882ce0afd2f0c97e55dca7622549` |
| ZIP CRC | 통과 |
| 이미지 / 라벨 파일 | 각각 247개 |
| train / valid / test | 각각 210 / 20 / 17쌍 |
| 원 주석 | 총 601행 |
| 보존 대상 person bbox | 335행 |
| min/max 변환 대상 person polygon | 19행 |
| 제거 대상 fence | 247행: bbox 52 + polygon 195 |
| 잠정 person 출력 기대값 | 354행, 모두 class 0 |
| 중복 ZIP member | `data.yaml`만 3개, 내용 SHA 동일 |
| 위험 member / 비정상 좌표 | 발견 0 |
| 교차 split 동일 이미지 bytes / 파일명 기반 그룹 | 발견 0 / 0, 실제 분할 독립성 보증 아님 |
| 기존 canonical 큐 | baseline의 42 jobs / 42 attempts와 모든 row 동일 |

train은 person bbox 264 + polygon 15 = 279행, valid는 21 + 3 = 24행, test는 50 + 1 = 51행이다. bbox의 좌표 4개는 그대로 유지하고 polygon은 각 축 min/max에서 중심·너비·높이를 계산하는 것만 검증한다. 박스의 실제 사람 대응, 그룹 여부, 부분 신체, 누락 라벨, 증강본의 의미적 누수, 원 이미지별 권리 조건은 이번 감사로 해결되지 않는다.

전체 source member SHA와 행 단위 기대값은 비공개 로컬 검토 receipt에 보관했다. 변환기를 import하지 않는 별도 검증기로 실제 출력 전부를 대조했다. 원본 ZIP, 복사된 source의 497개 고유 항목, 학습 형식 사본의 이미지 247개와 원래 split membership을 보존했다. 동일 이름의 YAML 세 항목은 한 파일로 저장하되 세 원본 ZIP 인덱스를 manifest에 남기며, 원 ZIP은 그대로다. 사람 bbox 335행의 숫자 토큰이 정확히 같고 polygon 19행은 Decimal min/max 기대값과 같으며, 출력은 모두 class 0의 5필드 354행이다. fence 247행은 새 라벨에서만 빠졌고 원본과 provenance에 남는다.

601개 모든 provenance 행에서 원본 member/index/행 번호/클래스/유형/raw/SHA, 출력 순서/행/SHA, 출력 라벨 SHA를 확인했다. manifest의 source·sample·overlay SHA를 대조했고 비교 PNG 113개의 바이트 해시만 확인했다. 비교 PNG의 실제 사람·박스 대응은 보지 않았다. 새 YAML의 로컬 path 및 train/val/test 경로, 단일 `person` 클래스도 확인했다.

코드 검토에서 ZIP 경로·심볼릭 링크·특수 파일·파일/디렉터리 충돌·과대 입력 차단, ZipInfo별 읽기, 동일한 루트 YAML만 허용하는 중복 예외, 모든 행의 사전 검증, 새 출력 디렉터리 및 `xb` 파일 생성에 의한 기존 파일 보존을 확인했다. 이번 고정 입력과 로컬 실행 범위의 검토이며 모든 임의 archive에 대한 보안 인증은 아니다. 실패 중간 산출물의 자동 덮어쓰기/재개 기능은 없고, 완성 상태는 summary/manifest 및 실제 해시 대조로 확인한다.

독립 실행한 합성 CPU 테스트 **12개 PASS**: min/max 변환, 두 사람 클래스의 bbox 토큰 보존, fence 검증 후 제거, 비정상 좌표·경계·주석 형식, mixed rows, 원본·이미지 보존, 그룹/fence-only 표본 보존, YAML 중복/충돌, 경로·링크·특수 항목, 기존 결과 비덮어쓰기, hash·mapping·pairing 오류 거부를 포함한다. Python bytecode 생성을 끄고 별도 로컬 임시 영역에서 실행했다.

담당자가 실행한 설치본 `verify_image_label` CPU 검증은 스크립트와 결과 receipt를 읽어 별도로 검토했다. 247쌍/354행, 누락·빈 라벨·손상 메시지 0, 데이터셋 검증 전후 SHA 동일, CUDA 초기화 없음이 기록돼 있다. 이는 담당자 실행 증거이며 독립 검토자가 같은 loader를 재실행했다고 주장하지 않는다. 독립 검토자는 별도 원본/출력 전수 대조와 12개 테스트를 직접 실행했다.

기준에 기록된 tracked 파일 420개 중 417개가 동일하다. 변경 3개는 총괄이 이번 승인 기록을 반영한 `AGENTS.md`, `docs/CODEX_NEXT_TASK.md`, `docs/HANDOFF.md`이며 총괄의 예상 변경 목록과 일치한다. canonical 큐 42 jobs/42 attempts의 전체 row가 기준과 같고 신규 job은 없다. 모델/학습/추론 및 환경 설치를 수행하는 경로는 이번 준비 코드에 없다.

검토 중 발견한 문서 결함은 학습 미승인 상태 필드가 `manifest.json`에 있다는 표현이다. 담당자가 `summary.json`으로 정정했고 최종 bytes에서 확인했다. 코드·테스트·데이터 변경 없이 정정됐으며 변환 결과 자체의 결함은 발견하지 않았다. 미해결 구현 결함은 없다.

**판정 범위:** 명시 승인된 검수 전 잠정 데이터 준비만 PASS다. `D0_passed: false`, `human_review: pending`, `training_approved: false`, `usable_for_training: false`, `semantic_person_approval: false`를 실제 결과에서 확인했다. 상태 플래그는 별도 trainer 실행을 막는 기술적 잠금이 아니다. 사람 의미·권리·누수 검토와 D0 판단이 남아 있으며, 학습·추론·모델 적용을 승인하거나 자동 예약하지 않는다.

최종 검토 대상 SHA256은 다음과 같다. 로컬 산출물은 해시만 기록하며 원시 데이터·좌표·provenance 내용은 공개 문서에 포함하지 않는다.

| 대상 | SHA256 |
| --- | --- |
| `scripts/prepare_climbing_fence.py` | `1fe1cec3acaf0cd0904eb61f552dd1088be922a6c3548dbe523991095a35595f` |
| `tests_data/test_prepare_climbing_fence.py` | `6502714077e56384e6fd8d46d62734520590e3adfdedcc3eda417b4eb15c0276` |
| `docs/data/CLIMBING_FENCE_PREPARATION.md` | `fcad8fea274682af349b8200760ea49e5f6bac44efb7e8561287533b0e9f6e90` |
| 출력 `summary.json` | `4d252ac4e7800d99feb5cd586f27c6eca0004cd7dfdb12eedd8fcc8273168a43` |
| 출력 `manifest.json` | `8377744fda3e1fcdd29ce1ea74926a3deb45bf98c7477498734ebe6f8141bb61` |
| 출력 `provenance.jsonl` | `25b6c789d531105034b3dc96d1403dc5bb816cd90844de5f84de14acb90e53c4` |
| 출력 `data.yaml` | `95d17fbb5af65b6452f61e9e39da67776d9a78e4458239b71a9014e455ea3f4a` |

검토 문서 자체의 SHA는 자기 참조를 피하기 위해 로컬 final binding receipt와 총괄 완료 메시지에 별도로 남긴다. 총괄은 정정 문서와 불변 코드/출력 확인을 조건으로 이 검토의 수락을 전달했으며 해당 조건을 확인했다.
