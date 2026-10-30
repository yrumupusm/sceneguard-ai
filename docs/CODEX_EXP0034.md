# EXP-0034 — 접근·이탈·소실 + 외형 비교 (최신 승인)

사용자는 기존 모델/영역을 유지하고 한 번 적용하는 데 동의했다. 화면·새 보고서에서는 **침입 의심 / 침입 확인 / 침입 아님 / 판단 불가**로 표현한다. 과거 결과·원시 모델 응답은 바꾸지 않는다. 방향의 ±90°는 보조 정보이며 강제 연결/침입 판정 조건이 아니다.

## 현재 구현과 미완료 범위

- `sceneguard/approach_disappearance.py`: 실제 관측만 읽는 CPU 분석기. 접근·같은 쪽 이탈·양측 관측·방향을 가진 가림 위치 소실을 분리한다. 파일 끝과 예측 박스는 소실 증거가 아니다. ±90° 내외 후보를 **모두 유지**하며, 각도를 원본 픽셀 좌표로 계산한다. 정지/짧은 경로/급격한 박스 크기 변동은 방향 불명 또는 약한 근거다.
- `sceneguard/appearance_support.py`: 기존 Qwen을 전달받아 **분리된 전후 이미지 1~3장씩**을 비교하는 어댑터와 응답 검사·일대일 연결 제안. 상의/하의/가방 중 공통으로 보이는 부분만 비교한다. 미관측은 차이도 일치도 아니다. 박스를 위아래로 기계적으로 자르지 않는다. 출력은 외형 호환성 제안이지 동일인 인증이 아니다.
- `tests/test_approach_disappearance.py`: 독립 Python 환경에서 **합성 테스트 32개 통과**. 실제 007/030 영상, 전체 저장소 회귀, pinned Qwen 다중 이미지 추론은 아직 미실행이다. 실제 결과/각도 적중률/성능 개선 주장은 없다.
- **남은 로컬 작업:** 현행 영역을 참조하는 scene 파일 작성, 저장 관측 대조 및 CPU 실행, 방향·소실 시각화, 원본 crop 준비, 기존 canonical GPU 큐에 외형 비교 단계 연결·제한 실행, 기존 화면 등록. 문서 추가만으로 완료 처리하지 않는다.

## 확정할 처리 방식

1. 실제로 같은 쪽으로 나가는 모습을 관측했고 중간 침입/불분명한 공백이 없으면 해당 접근 에피소드를 `침입 아님`으로 표시.
2. 접근 이력·침입 쪽 이동 방향·알려진 가림 위치에서 소실이 함께 있으면 **반대편 재등장 없이도 `침입 의심` 생성**. 오래 안 보인다는 이유로 `침입 확인`으로 승격하지 않는다.
3. 제자리 소실·다른 위치 소실·방향 불명·영상 종료는 `판단 불가`. 기존 경보는 지우지 않는다.
4. 재등장이 있으면 시간·거리로 연결 후보를 만들고 ±90° 여부를 표시만 한다. 기존 ID 단절 가능성을 함께 표시한다. 후보가 없으면 VLM을 호출하지 않는다.
5. VLM은 침입 여부를 판정하지 않는다. **공통으로 보이는 외형**만 비교한다. 호환성이 있어도 여러 후보가 경쟁하면 연결 보류. raw ID/기존 chain/기존 경보는 덮어쓰지 않는다.
6. `침입 확인`은 이번 자동 규칙의 기본 출력이 아니다. 검토자의 확인 상태와 자동 의심을 구분한다.

## 로컬 입력 (기존 자료만)

030: `outputs/exp0028/practical-v1/track030/gap/frames.jsonl`, 원본 `data/TS_침입/E01_030.mp4`, 현재 영역 `outputs/exp0029_region_review/030-inside-user-v1/regions030-inside-expanded.json`.

007: `outputs/exp0029/replay007/gap/frames.jsonl`, 원본 `data/TS_침입/E01_007.mp4`, 현재 영역 `runtime/EXP-0029/regions007.json`.

원본 해시·프레임 크기·PTS·cache_index·observed bbox를 기존 EXP-0030 검증 함수 또는 동일 계약으로 대조한다. 검출/추적 재실행·새 학습은 하지 않는다. 좌표와 모든 원본/크롭은 로컬에만 둔다.

`runtime/EXP-0034/scene030.json`, `scene007.json`을 다음 키로 만든다:

- `source_size`: 원본 [width,height].
- `line`: 기존 카메라 경계선 두 점. 수정하지 않는다.
- `approach_polygon`: 기존 CV ROI 사각형을 polygon으로 표현. 사용자의 기존 영역을 덮어쓰지 않는다.
- `zones`: 현행 사용자 `outside`, `inside` polygon을 그대로 참조·복사.
- `directions`: 기존 감시 방향. 양방향이면 outside_to_inside, inside_to_outside 모두 기록.
- `occlusions`: 각 항목의 `id`, `from_side`, `to_side`, `polygon`. **마지막으로 보이는 가림 입구 위치**를 표시하는 별도 보조 주석. 기존 안/밖 영역 수정이나 A/B 실험이 아니다. 로컬 원본의 정적 문/기둥/장애물 위치로만 소수 지정하고, 결과를 맞추기 위해 넓히지 않는다. 확인할 수 없으면 빈 배열과 제한 사항을 남긴다. 원격의 예시 좌표를 임의로 만들지 않는다.

소실 대기 1초, 방향 창 1초, 재등장 후보 6초 등의 기본값은 **초기 heuristic**이다. 일관된 한 구성으로 실행하고 파라미터 sweep은 하지 않는다. 실제 검출 간격이 길면 정상 확인으로 잘못 처리하지 않는다.

```bash
.venv/bin/python -m unittest discover -s tests -p test_approach_disappearance.py -v
.venv/bin/python -m sceneguard.approach_disappearance \
  --frames outputs/exp0028/practical-v1/track030/gap/frames.jsonl \
  --scene runtime/EXP-0034/scene030.json --output outputs/exp0034/030-v1.json
.venv/bin/python -m sceneguard.approach_disappearance \
  --frames outputs/exp0029/replay007/gap/frames.jsonl \
  --scene runtime/EXP-0034/scene007.json --output outputs/exp0034/007-v1.json
```

## ±90° 확인과 외형 비교 (한 번씩만)

CPU 출력으로 마지막 실제 관측점, 직전 실제 이동 경로, 방향 화살표·±90° 부채꼴, 소실 위치, 재등장 후보를 표시한다. Kalman 예측은 다른 선으로 표시하고 실제 방향 근거에서 제외한다. **예측 박스가 예측 방향으로 가는 것을 검증 성공으로 세지 않는다.**

실제 재등장 쌍의 `same/different/unknown` 수기 검수 라벨로 `angle_audit`를 호출하거나 `--human-pair-labels` JSON을 사용한다. unknown 및 끝내 안 보인 사람은 적중률 분모에서 제외하고 건수를 따로 남긴다. VLM이 호환된다고 답한 것을 human-confirmed로 바꾸지 않는다.

VLM 실험은 시간 제한을 고려해 **최대 6쌍, 각 1회 생성**으로 제한한다: 연결 후보 2~3쌍, 명확히 다른 사람 1~2쌍, 가림/두 사람 혼합 1쌍. 후보가 적으면 억지로 채우지 않는다. ±90° 밖 후보를 이유 없이 삭제하지 않으며, 검수 정답이나 각도는 VLM 질문에 넣지 않는다. 실제 `pair_id`, raw ID, PTS, bbox/원본 해시와 익명 A/B의 결속을 기록한다.

전후 대표는 접근 중 잘 보였던 순간도 포함한다. 상체만 보인 박스를 전신처럼 반으로 자르지 않고, 원래 대상 crop 전체를 각각 별도 이미지로 제공한다. 혼합 crop은 혼합 가능성을 검수로 표시하고 unknown이 허용되게 한다. 같은 색만으로 연결하지 않는다.

**로컬 큐 연결은 아직 별도 작업이다.** 기존 `mvp-0001` 실행 경로의 작은 신규 phase를 추가해 `compare_images(existing_qwen_analyzer, before_rgb_list, after_rgb_list)`를 호출한다. 기존 GPU lease/모델 해시/로컬 전용 실행을 유지하며 새 큐나 새 모델은 만들지 않는다. `compare_images` 자체도 GPU 사용 전에 기존 lease를 검증한다. pinned processor의 `images_kwargs` 호환성을 CPU에서 먼저 확인하고, 불일치 시 동등한 이미지 예산 전달 방식만 수정한다. 영상 질문/`parse_pair`를 재사용하지 않고 전용 `parse_comparison`을 사용한다. JSON 오류를 정상으로 바꾸지 않는다.

VLM 결과는 `link_proposals`로 일대일 후보로 정리한다. 일대일 제안의 before/after가 다른 안정된 영역에 관측됐으면 추가 **침입 의심 근거**로 붙일 수 있지만, 외형 답변만으로 침입 확인/기존 ID 병합은 하지 않는다. 같은 쪽 재등장은 ID 단절 가능성으로 기록하고 이미 생성된 의심 기록은 덮어쓰지 않는다.

## 산출물·종료

기존 담당3 화면에 원본/관측/방향·소실·상태/외형 비교를 같이 표시한다. 기존 경보를 보존하고 신규 의심을 별도 reason/source로 추가한다. UI와 새 문서는 침입 용어로만 간결하게 표현한다. 실제 재생·seek를 확인하고 결과/검토/전달 문서를 GitHub에 남긴다. 원본과 crop·좌표·raw 응답은 비공개 로컬 유지.

보고할 것은 정상 접근을 침입으로 잘못 올렸는지, 007 가림 소실을 의심으로 잡았는지, 각도 보조가 실제 연결 후보에 유용했는지, 외형 비교가 다른 사람을 섞었는지다. 단순 후보 증가·테스트 통과·높은 모델 자기 점수를 실제 성능으로 보고하지 않는다. 새 모델/학습/영역 수정 탐색으로 자동 확대하지 않는다.
