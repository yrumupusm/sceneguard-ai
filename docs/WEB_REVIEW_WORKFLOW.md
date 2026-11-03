# 실험별 웹 검수와 작업 시작 절차

상단의 공통 영상 검수 탭 대신 실험 상세 오른쪽 **영상 검수로 이동**을 사용한다. 주소는 `/#video-review?experiment=EXP-0044`처럼 실험을 지정한다. 해당 실험에 등록된 사건 자료 또는 대표 영상·이미지만 표시한다. 돌아가기 버튼은 같은 실험을 선택한다.

## 사용자 흐름

1. 실험 카드의 **! 검수 필요 N건** 또는 상세 버튼을 누른다.
2. 요청된 질문과 연결된 근거를 확인하고 답변을 선택하거나 직접 작성한다. 검토자를 입력하고 필요하면 메모한다.
3. **검수 완료**를 누르면 답변·메모·수정 이력이 로컬에 저장된다. 채팅에서 “검수했어”라고 알려도 된다.
4. 저장 직후에는 **검수 완료 · AI 확인 대기**다. AI가 내용을 읽으면 **반영 검토 중**, 실제 작업에 반영하거나 이유를 남겨 보류하면 각각 **반영 완료 / 반영 보류**로 표시한다.

답변을 수정하면 새 답변 버전이 생성되고 AI 확인 대기로 돌아간다. 이전 반영 내역은 이력에 남는다. 질문이 없는 실험은 **검수 요청 없음**이며 완료를 뜻하지 않는다. 예전 자유 메모는 보존하지만 자동으로 요청 완료나 정답으로 전환하지 않는다. 질문 답변과 기존 사건 판단·박스 품질·누락 검수는 별도로 저장한다.

15초 자동 갱신은 상태 표시만 바꾼다. 작성 중인 답변과 재생 화면은 재생성하지 않는다. 질문·처리 이력은 버튼으로 새로고침하며, 저장 전 입력이 있으면 새로고침을 막고 저장을 안내한다. 다른 실험으로 이동하거나 브라우저를 닫기 전에는 답변을 저장해야 한다. 다른 창에서 수정된 버전을 덮어쓰려 하면 저장이 거절된다. 이 경우 입력을 복사하고 새로고침해 최신 이력을 확인한다.

## AI 작업 시작 시

SceneGuard 작업을 시작하거나 재개할 때 다음 읽기 전용 명령으로 새 답변 및 확인 후 미처리 답변을 조회한다. 기존 서버 가상환경을 사용하며 새 의존성 설치는 필요 없다.

```bash
cd /home/jhc7484/dev/sceneguard-ai
/home/jhc7484/dev/sceneguard-orca-lab/.venv-orca-lab/bin/python scripts/review_requests.py \
  --config /home/jhc7484/dev/sceneguard-orca-lab/runtime/orca-lab/local_config.json \
  pending --include-acknowledged
```

- `answered`: 질문·답변·연결된 실험/영상/시각·이력을 실제로 읽는다. 현재 작업과 관련 있는 근거를 우선 반영하고, 읽은 답변의 정확한 `version`과 `answer_version`으로 `acknowledge`한다.
- `acknowledged`: 이전 세션에서 읽었지만 끝내지 않은 처리다. 실제 반영 내용을 확인하고 이어서 처리한다.
- 질문에 묶인 기존 보고서·측정치·미디어는 수정하지 않는다. 검수 반영은 새 후속 문서·새 결과 또는 작업 코드에 기록하고 처리 메모에 연결한다. 원문을 바꾸면 바인딩이 달라져 이전 요청의 처리를 완료할 수 없다.
- 실제 반영 후 `resolve --outcome applied --note ...`, 적용하지 못하면 구체적인 이유를 적어 `deferred`로 기록한다. 읽었다는 이유만으로 반영 완료 처리하지 않는다.
- 범위가 다른 답변을 무조건 소비하거나 재검수를 요구하지 않는다. 기존 사용자 검수와 함께 출처를 유지한다. 자유 메모를 임의 정답·자동 학습·판정 규칙 변경으로 사용하지 않는다.
- 명령 실패는 검수 없음이 아니다. 조회 실패를 기록하고 관련 검수 확인을 완료했다고 말하지 않는다.

서버가 AI를 자동 실행하는 방식이 아니다. 웹은 답변을 저장하고, 작업 시작 절차로 연결된 에이전트가 읽고 처리한다. DB가 없으면 읽기만으로 DB를 생성하지 않는다.

## 검수가 필요할 때 요청 등록

다시 확인할 필요가 있는 장면만 질문으로 만든다. 원본/실험 ID와 질문을 명확히 하고, 이미 확인된 검수는 재사용한다. 실제 질문이 있을 때만 로컬 JSON 명세를 작성해 다음 CLI로 등록한다. 아래 명세의 값은 형식 설명이며 실제 요청으로 등록하지 않는다.

```json
{
  "experiment_id": "EXP-0044",
  "title": "짧은 검수 제목",
  "question": "이 구간에서 확인할 구체적인 질문",
  "options": ["관찰 1", "관찰 2", "판단 어려움"],
  "bundle_id": "해당 실험에 등록된 bundle ID",
  "source_label": "영상 이름",
  "source_time": 64.0,
  "end_time": 74.0
}
```

```bash
# 위 작업 시작 명령과 같은 Python 및 --config를 사용한다.
python scripts/review_requests.py --config CONFIG create --spec-file LOCAL_QUESTION.json
python scripts/review_requests.py --config CONFIG pending --include-acknowledged
python scripts/review_requests.py --config CONFIG acknowledge REQUEST_ID \
  --expected-version VERSION --answer-version ANSWER_VERSION --note '읽은 내용과 확인 범위'
# acknowledge가 반환한 새 version을 사용한다.
python scripts/review_requests.py --config CONFIG resolve REQUEST_ID \
  --expected-version NEW_VERSION --answer-version ANSWER_VERSION \
  --outcome applied --note '실제 반영 위치와 내용'
```

`bundle_id` 대신 같은 실험의 등록된 `artifact_id`를 사용할 수 있다. 원본 시각은 재생 시계가 등록된 bundle의 `source_window` 안에 있어야 한다. artifact만 연결하는 질문은 시각 없이 등록한다. 이미지·자료의 시각을 추측해 넣지 않는다. 질문 등록은 CLI만 제공하고 웹은 답변 저장만 제공한다. 임의 파일 경로·다른 실험의 자료를 받지 않는다. 등록된 원문·미디어가 바뀌면 예전 질문의 답변/처리를 거절한다. 변경 자료에는 별도 요청을 생성해야 한다.

## 데이터 보존과 범위

새 저장소는 공통 runtime의 `review-requests.sqlite3`다. 기존 `incident-reviews.sqlite3`, `saved-result-assessments.sqlite3`, 알림 영수증은 초기화하거나 마이그레이션하지 않는다. DB와 답변 원문·영상은 로컬 전용이다. 모델/GPU 실행이나 자동 정답 생성 기능이 아니다. 검수 배지는 명시적으로 등록된 요청 기준이며 과거 모든 실험의 검수 완료 여부를 소급 판정하지 않는다.
