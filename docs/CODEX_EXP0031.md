# EXP-0031 — 대표 이미지 품질 개선 + raw ID 혼합 점검 (실행 지시)

2026-10-30 사용자 승인. **이 문서가 새 작업의 우선 실행 계약**이다. 코드와 합성 테스트는 이미 GitHub에 추가했고, **실제 로컬 CCTV·공식 ONNX 재추론 결과는 아직 없다**. 이미 끝난 EXP-0030의 사건 검토 MVP는 그대로 보존한다.

## 목표 및 고정 조건

- 목표는 E01_030/007 월장 전후의 **실제 동일 인물 연결 개선 가능성**을, 새로운 모델 없이 한 번만 확인하는 것이다. 성공 기준은 연결 수가 아니라 **올바른 연결과 새 오연결이 없는지**다. 사람이 불분명하면 unknown으로 남긴다.
- **사용자 수정 outside/inside polygon을 그대로 유지**한다. 영역 수정 전후 A/B·새 polygon 튜닝·영역 검증 실험은 하지 않는다. EXP-0031은 영역을 전혀 읽거나 수정하지 않는다.
- 기존 FCOS 측정, ByteTrack gap, Tracklet 구성, 5초 제한, ReID 모델 yolo26n-reid.onnx와 외형 연결 임계값 0.65, 원래 Q01~Q08과 EXP-0030 후보·근거 영상 모두 유지한다. 자체 파인튜닝·새 검출기·새 추적기·새 임베더·임계값 sweep·GPU 추론은 금지.
- 새 실험은 **대표 선택 묶음 비교**다: 기존 처음/끝 1초에서 점수×박스면적으로 선택하는 대신 처음/끝 2초에서 프레임별 다른 박스와 겹침, 급격한 박스 폭/높이 변동, 상대적으로 작은 박스 경고를 우선 반영해 시간 분산 최대3개를 선정한다. 이것은 다중 인물 여부의 정답이 아니다. 모두 경고 박스라면 삭제/성공 주장 대신 경고를 남긴다. 선택 시간창과 위험 순위가 함께 달라져 각각의 인과를 따로 주장하지 않는다.
- 원본 crop key (frame_index,cache_index)가 기존 대표와 같으면 기존 512D 특징을 그대로 재사용한다. 새 대표만 **기존 공식 CPU ReID**로 임베딩한다. bbox·PTS·원본 SHA를 검사하며 모델/API가 다르면 중단한다.

## 추가된 파일

- 코드: sceneguard/exp0031_quality.py, sceneguard/run_exp0031_quality.py
- 합성 단위 테스트: tests/test_exp0031_quality.py 12개 및 tests/test_run_exp0031_quality.py 4개. 12개는 독립 컨테이너에서 실제 모듈을 테스트했고, 4개는 격리 모의 의존성으로 runner의 adapter 경계를 테스트했다. **로컬 저장소 전체/공식 모델 실행을 검증했다는 뜻은 아니다.**
- 출력: selected_representatives.json, selection_audit.json, alternative_features.local.json, alternative_associations.json, raw_id_appearance_warnings.json, paired_comparison.json, question_comparison.json, summary.json, provenance.json, 새 대표 crop JPEG.
- 새 association은 **실험 비교용**이며 EXP-0029/EXP-0030에서 확정된 raw/chain ID를 바꾸지 않는다. accepted가 발생하더라도 실제 인물 연결을 자동 승인하지 않는다.

## 실행: 로컬 Codex에게 바로 지시

1. 최신 main을 기존 변경·로컬 사용자가 편집한 polygon을 보존하며 반영한다. EXP-0030·EXP-0029 결과 및 기존 run_tracklet_linking.py, tracklet_linking.py, mvp_review_quality.py의 저장 결과를 확인한다.
2. 아래 16개 합성 테스트와 CLI 도움말을 실행한다. 실제 저장소 의존성 호환성이 다르면 **동작 오류만 수정하고 재테스트**하되 설정/결과에 맞춘 최적화는 하지 않는다. 기존 테스트/결과는 덮어쓰지 않는다.
3. EXP-0029 원본 데이터와 저장 특징을 확인한 뒤 E01_030과 E01_007을 **각 한 번씩** CPU 실행한다. 새 ReID forward 수·기존 feature 재사용 수를 기록하고, 원본/feature/bbox 해시를 보존한다. 카메라 영역은 실행 입력에 넣지 않는다.
4. Q01~Q08 각각에서 기존/새 대표 실제 사람 crop·원본 문맥과 유사도·선택 위험 표시를 나란히 보여주는 로컬 비교판을 만든다. **Q02의 첫 raw11 대표 혼합 우려, Q08의 두 사람이 한 crop에 담기는 문제**를 우선 확인한다. 추가로 같은 시각의 서로 다른 사람 쌍을 소수 선정해 잘못된 연결도 검토한다. 번호가 같다는 이유로 동일인 정답을 자동 생성하지 않는다.
5. 각 사례에 same_person: yes/no/unknown, before_single_person_crop: yes/no/unknown, after_single_person_crop: yes/no/unknown, raw_id_mix_suspected: yes/no/unknown, reason을 수기 검수 항목으로 남긴다. 미확인 항목은 unknown이다. **사람 정답 없이 개선된 연결 수만으로 성공이라고 쓰지 않는다.**
6. 결과 문서에는 원래/새 연결 수, **검수된** 올바른 연결·오연결·미연결, Q01~Q08 각각의 전후 차이, 혼합/가림이 남아 있어 불가능한 사례, CPU 비용, 기존 파일 보존을 함께 보고한다. 기존 웹 결과 뷰어가 있다면 새 로컬 검수판을 링크하되 대규모 UI 추가는 하지 않는다.
7. 실제 원본·crop·feature·좌표·weights·polygon은 Git 제외. GitHub에는 소스와 비식별 결론, 테스트/전달 상태만 게시하고 종료한다.

기존 ENV를 유지한 저장소 루트에서:

    export PYTHONPATH="$PWD/runtime/EXP-0028/reid-deps:$PWD/.venv-pose-batch03/lib/python3.10/site-packages"
    export YOLO_AUTOINSTALL=false OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4
    .venv/bin/python -m unittest discover -s tests -p 'test_*exp0031_quality.py' -v

    .venv/bin/python -m sceneguard.run_exp0031_quality \
      --cache outputs/cv_phase2d/cache030 \
      --tracks outputs/exp0028/practical-v1/track030/gap/frames.jsonl \
      --video data/TS_침입/E01_030.mp4 \
      --prior outputs/exp0029/track030/v1 \
      --output outputs/exp0031/track030/v1

    .venv/bin/python -m sceneguard.run_exp0031_quality \
      --cache outputs/exp0029/cache007 \
      --tracks outputs/exp0029/replay007/gap/frames.jsonl \
      --video data/TS_침입/E01_007.mp4 \
      --prior outputs/exp0029/track007/v1 \
      --output outputs/exp0031/track007/v1

출력 디렉터리는 기존 파일이 없을 때만 생성되며 실패해도 기존 출력은 삭제하지 않는다. 중단·재실행할 때 새 ID/경로와 원인 기록을 사용한다.

## 다음 결정의 기준

- **검증된 동일 인물 연결이 늘고, 잘못된 인물 연결은 늘지 않으면** 소규모 MVP 적용 후보로 검토한다. 이 실험의 모델 score/코사인은 정체 확률이 아니며 두 CCTV의 개발 구간 결과를 일반 CCTV의 성공률로 확대하지 않는다.
- **깨끗한 한 사람 crop을 구할 수 없거나, 깨끗한 crop에서도 연결이 안 된다면** 결과를 한계로 확정하고 이 조합의 탐색을 멈춘다. 추가 파인튜닝·새 모델·임계값 변경을 자동 시작하지 않는다.
- EXP-0030의 기존 월장 동작 후보(030 약90초,007 약70.13초)는 삭제하지 않는다. 사용자 수정 영역도 유지한다.

**이번 승인 범위는 코드/합성 시험 + 로컬 두 영상 비교 + 사람 검수용 자료 및 결론이다. 실제 로컬 실행 없이 문서만 게시한 것을 EXP-0031 완료라고 쓰지 말 것.**
