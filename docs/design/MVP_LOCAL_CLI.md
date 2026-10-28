# MVP-0001 로컬 CLI 계약

2026-10-28. [고정 계획](../experiments/MVP-0001-plan.md)을 구현하는 모델 독립 실행 흐름이다. 웹·기존 CV는 수정하지 않는다. CPU 합성 검증과 실제 행동 성능, 원본 전체 실행, 게시·화면 확인은 별도로 기록한다.

`mvp.pipeline.run_video(video: Path, camera: dict, analyzer, output: Path, run_context: dict, settings: dict) -> dict`는 큐 실행기 내부에서만 실제 모델과 연결한다. 테스트에서는 fake analyzer를 사용한다. CLI에는 직접 모델 실행·모델 선택·프롬프트·사건 시각·임의 출력 경로 인수가 없다. `python -m mvp.cli --help`는 모델을 로드하지 않는다.

## 큐 명령

기존 환경과 공통 canonical queue를 사용한다. 아래 환경변수는 해당 PC의 이미 검증된 interpreter와 큐의 절대 경로다. 이 문서는 새 큐 초기화나 실제 실행 GO를 대신하지 않는다.

```bash
"$MVP_PYTHON" -m mvp.cli --runtime "$MVP_QUEUE_RUNTIME" status
"$MVP_PYTHON" -m mvp.cli --runtime "$MVP_QUEUE_RUNTIME" enqueue \
  --phase full --view full_frame --job-key "$MVP_JOB_KEY" \
  --run-id "$MVP_RUN_ID" --task-id "$MVP_TASK_ID" \
  --dispatch-id "$MVP_DISPATCH_ID" --owner "$MVP_OWNER"
# 총괄 code/data/resource GO 이후, 기존 단일 큐에서 한 job만 실행
"$MVP_PYTHON" -m mvp.cli --runtime "$MVP_QUEUE_RUNTIME" run-once
```

`dev`는 `fixed_roi`만 허용하며, `full`은 전체 화면 기준과 고정 ROI를 별도 순차 job으로 등록한다. CLI는 registry의 정확한 입력 해시·고정 설정을 검증하고 기존 `Queue.enqueue`/`Queue.run_once`를 호출한다. `run-once`는 공통 큐에서 대기 순서대로 최대 한 job을 실행하므로 특정 job만 고르는 우회 수단이 아니다. 실행 오류 재시도는 기존 큐의 명시적 retry 최대1회만 사용한다. CLI는 자동 재시도·재실험을 하지 않는다.

## 입력·표본과 시간

원본 처음부터 EOF까지 순서대로 디코딩한다. 첫 실제 PTS를 기준으로 5초 창/2.5초 간격/약2fps의 전역 표본 목표를 고정한다. 목표 이상으로 처음 도착한 프레임을 선택하며, 큰 PTS 간격에서는 목표를 건너뛰고 같은 프레임을 중복 관측으로 만들지 않는다. 입력 창은 실제 PTS가 `[window_start,window_end)` 안인 표본만 포함한다. 창을 닫기 위해 읽은 경계 이후 프레임은 마지막 도착 시각으로 기록하며 이전 창 입력에는 넣지 않는다.

native PTS 또는 time_base 부재·비증가·해상도 변경은 실행 실패다. FPS만으로 시간을 합성하지 않는다. EOF의 실제 끝은 마지막 원본 프레임 PTS+그 프레임 duration이며, duration 부재 때만 source FPS 한 프레임 길이를 쓰고 그 값을 기록한다. EOF 잔여 창은 확보된 원본 표본만 사용한다. 실제 표본2개 미만은 `insufficient_data`로 남기고 analyzer를 호출하지 않는다. official processor가 마지막 프레임을 반복한다면 analyzer가 그 수를 별도 기록한다. 파이프라인은 미래 PTS를 추가하지 않는다.

analyzer 호출은 `analyze(rgb, source, window_id, roi)` 또는 같은 callable이다. RGB는 원본 `uint8[N,H,W,3]`이다. source에는 `fps`, `pts_seconds`, `native_pts`, 프레임별 rational string `time_base`, `source_size=[w,h]`, 창 시작/실제 끝/명목 끝, 마지막 입력·디코딩 PTS, EOF 상태와 표본 SHA256이 있다. `decoded_indices`는 원본 디코딩 ordinal 정수, `relative_indices`는 첫 선택 프레임 ordinal을 뺀 정수이며 `elapsed_pts_seconds`는 실제 native PTS 차이다. VFR에서는 ordinal/FPS와 실제 경과 시간이 다를 수 있으므로 둘을 혼동하지 않는다. method의 공식 processor 시간 좌표/표시 정밀도·padding은 별도 `input_metadata`에 기록한다.

source에는 파일명·공식 JSON·관찰·정답·과거 답변을 전달하지 않는다. 익명 `w000001`과 고정 ROI만 제공한다. 설정·camera·run_context는 로컬 provenance로 저장하며 analyzer에는 그 설명을 전달하지 않는다. camera ROI는 정규화된 원본 xyxy이며 카메라 설정의 full-frame fallback을 그대로 보존한다.

## 상태·병합·근거

analyzer 반환은 `{raw_response, parsed, parse, timing, input_metadata, output_tokens, gpu_memory}`다. 반환 전체를 먼저 디스크에 flush/fsync한 뒤 행동을 해석한다. `parsed.observed_actions`의 넘기/줄 넘기만 `candidate`, 접촉은 `contact_review`, 판단 불가는 `indeterminate`, 형식/스키마 실패는 `parse_failed`다. `crossing_completion=observed`만으로 후보를 만들지 않는다. `passage_or_waiting`은 `observed_other`이며 검수된 정상 정답을 뜻하지 않는다. 판단 불가나 파싱 실패를 정상으로 바꾸지 않는다.

같은 실행 소스·카메라·상태·행동에서 시간창이 엄격히 겹치는 경우만 병합한다. 단순히 맞닿거나 gap이 있는 창은 합치지 않는다. 원래 창·raw 결과·최초 emission은 보존한다. 이 묶음은 사람의 동일성을 주장하지 않는다. 사건별·영상별 예외가 없다.

최종 후보의 각 constituent에는 window/result 경로와 모델이 말한 visible_evidence·uncertainties·crossing_completion을 연결한다. 모델 주장임을 명시하고 정답이나 사람의 관찰로 승격하지 않는다. wrapper 아래 실제 analyzer의 진단을 창마다 초기화하며 실패 시 현재 창의 생성 token IDs/가능한 입력 metadata와 prompt를 보존한다. 이전 성공 창의 진단을 실패 창에 복사하지 않는다.

각 창 결과와 최초/갱신 후보는 즉시 순차 기록한다. EOF/중단 이후 최종 병합과 근거 저장을 따로 수행한다. 최종 이벤트 구간 앞뒤2초를 원본의 실제 도착 범위에 clip하고 원래 전체 시야의 MP4를 재인코딩한다. crop/오버레이/표본 반복으로 근거를 대체하지 않는다. native 첫/마지막 PTS, 실제 source bounds, source duration, 인코딩된 MP4 duration과 저장 시각을 sidecar에 남긴다. 실패 실행의 근거는 중단까지 도착한 범위까지만 사용한다.

사건 추정 구간, 최초/최신 마지막 입력 PTS, 마지막 도착 PTS, `available_at_source_time`, UTC와 monotonic 최초 emission, 최종 병합·근거 저장 시각은 독립 필드다. EOF 결과의 available source time은 실제 끝까지 기다린 것으로 기록한다. 오프라인 파일 wallclock을 실시간 감지 지연으로 보고하지 않는다. 실시간 지연은 null이다.

재사용 응답의 `output_tokens`는 원래 응답 길이이고 `newly_generated_tokens=0`이다. 현재 재사용의 generation/prepare 비용은 null로 남기고 reuse 검증 시간은 따로 측정한다. summary도 응답 길이와 실제 새 생성 토큰을 분리하며 generation/prepare 합산은 실제 새 실행에서 측정된 값만 사용한다. 과거 생성 시간을 이번 처리 비용으로 재사용하지 않는다.

## 로컬 저장·실패

등록 실행기의 고정 로컬 output root 아래 새 attempt/source 디렉터리만 허용한다. pipeline은 절대 경로·root 포함·symlink 부재·기존 디렉터리 부재를 검사하며 근거 파일은 exclusive create한다. 기존 결과는 덮어쓰지 않는다. CPU 테스트만 임시 safe root를 명시한다.

로컬 결과는 `run.json`, 갱신되는 `summary.json`, `windows.jsonl`, `emissions.jsonl`, 최종 `events.jsonl`, `windows/w000001/{input,result,window}.json`, `evidence/event000001.{mp4,json}`이다. RGB는 원본과 PTS/해시로 재구성할 수 있고 창마다 중복 배열 파일은 저장하지 않는다. sampled RGB buffer는 최대10장 수준이고 모델 입력 stack은 현재 창 한 개뿐이다. 사건/측정 metadata 크기는 창 개수에 따라 증가한다. raw 응답·원본 경로·로컬 receipt와 이 출력들은 Git 제외다.

decode/analyzer 오류는 `failure.json`, 완료된 창과 해당 창의 가능한 오류 결과를 보존하고 실패 summary를 반환한다. 근거 인코딩 오류도 functional_success를 false로 만든다. `functional_success`/EOF 통과는 행동 정확도를 뜻하지 않는다. 행동 품질은 별도 사람이 검수하고 정밀 GT 없는 최종 F1/accuracy/오탐률은 산출하지 않는다.

## CPU 검증

```bash
"$MVP_PYTHON" -m unittest discover -s tests_mvp -v
```

합성 MP4와 CPU fake analyzer로 시간창/짧은 영상/VFR·분수FPS/native PTS/EOF/미래 프레임 미사용, 상태와 병합, raw 조기 저장, 근거 duration/경계, 안전 경로, partial failure, CLI의 common queue 경로를 검사한다. 실제 모델·GPU inference·외부 미디어 도구를 호출하지 않는다.
