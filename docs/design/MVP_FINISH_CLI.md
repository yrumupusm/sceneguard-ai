# 로컬 영상에서 사건 카드까지

저장소 루트와 기존 `.venv`에서 실행한다. 첫 버전은 **명시적으로 선택한 기존 C3/C6, 원본 30fps, PTS 시작0** 영상만 지원한다. 영상 경로/파일명으로 카메라를 추정하지 않는다. C3/C6에 맞는 실제 고정 카메라 영상인지 선택자가 확인해야 하며, 해상도만 같다고 다른 카메라를 지원하는 것은 아니다. 원본·가중치·사용자 영역·scene은 로컬에 이미 있어야 한다.

기존007 개발 영상의48–105초:

```bash
.venv/bin/python -m sceneguard.video_cards \
  --video data/TS_침입/E01_007.mp4 --camera C3 \
  --start 48 --end 105 --cache outputs/exp0029/cache007 \
  --output outputs/exp0037/video007-v4
```

기존030 개발 영상의84–100초:

```bash
.venv/bin/python -m sceneguard.video_cards \
  --video data/TS_침입/E01_030.mp4 --camera C6 \
  --start 84 --end 100 --cache outputs/cv_phase2d/cache030 \
  --output outputs/exp0037/video030-v3
```

`--start/--end`는 원본 영상의 초 단위 PTS이며 끝은 제외한다. 둘 대신 `--whole`을 주면 원본 전체 구간을 요청한다. 기존 캐시가 전체를 덮지 않으면 부분 결과를 전체 분석으로 표시하지 않는다. 첫 실행은 새 `outputs/` 하위 경로를 사용한다. 위 결과가 이미 있으면 같은 명령은 완료 단계의 바이트를 검증하고 재사용한다.

캐시는 원본 SHA, 명시적 카메라의 기존 설정, 고정 pretrained FCOS COCO_V1 가중치 SHA, model input/postprocess, FP32/batch1/seed0/무샘플링, 실제 native PTS/time_base, 범위, 행 수와 파일 SHA를 검증한다. `--cache`를 생략하면 로컬 `outputs/`에서 조건에 맞는 완료 캐시를 먼저 찾는다. 유효한 기존 검출을 다시 추론하지 않는다.

흐름은 기존 `run_cv` 검출 캐시 → 기존 ByteTrack gap3초/경계 모듈 → `approach_disappearance` → `relaxed_suspicion` → `incident_cards` → 원본 근거 H264다. 알고리즘·영역·의심 생성 조건은 기존 그대로다. EXP-0037 고정 감사는 실제007/030에서 알림 감소0이므로 **후처리 미채택**이며 새 CLI도 기존 의심을 유지한다. VLM/학습/ReID는 호출하지 않는다.

## 새 검출과 큐

새 원본 검출은 **기존 canonical GPU 큐**의 `video-cards` 등록 명령만 사용한다. 큐 경로를 임의로 지정하거나 `run_cv`를 별도 subprocess로 실행하는 우회 옵션은 없다. 기존 Run과 현재 활성 Task/Dispatch/담당 터미널이 모두 일치해야 한다.

```bash
.venv/bin/python -m sceneguard.video_cards \
  --video /absolute/local/camera-video.mp4 --camera C3 \
  --start 45 --end 48 --output outputs/local-analysis/new-session \
  --run-id CURRENT_RUN --task-id CURRENT_TASK \
  --dispatch-id CURRENT_DISPATCH --owner CURRENT_TERMINAL
```

위 대문자는 실행 환경의 실제 활성 식별자로 대체한다. 예시는 새 영상 실행을 증명하는 기록이 아니며 실제 실행 영수증은 `runtime/EXP-0037/`과 해당 `outputs/`에 둔다. 유효한 캐시가 없고 식별자도 없으면 `status.json`에 `blocked`/새 검출 미검증/호출0을 기록하고 종료코드2를 반환한다. GPU가 부족하면 모델 로드 전에 실패한다. 새 서버/큐/다운로드/가중치/학습/자동 재시도는 없다. 다른 대기 중 작업을 대신 실행하지 않는다.

부모 큐는 실제 상속 GPU lock·parent/child process identity·입력/설정/소스 SHA·Git HEAD를 검증한다. 자식은 원래 `.venv`에서 동일 lease와 현재 Orca 배정을 다시 검증하고 실제 freeVRAM≥6144MiB를 확인한 뒤 기존 `run_cv.run`을 호출한다. 원래10회 zero warmup은 sample 추론과 구분한다. 오류 시 새 조건으로 자동 축소/재시도하지 않는다.

## 산출물과 기존 서비스 등록

| 파일 | 의미 |
|---|---|
| `request.json` | 원본/설정/scene/사용자 영역/코드 SHA, 명시적 카메라/구간, 고정 정책과 큐 문맥 |
| `status.json` | 진행·실패·차단·완료 상태, 새 검출/저장 캐시 구분, 이번 실행 비용/재사용 단계 |
| `tracking/frames.jsonl` | 기존 gap 추적의 실제 관측과 별도 예측 상태 |
| `tracking/events.json` | 기존 경계 의심을 보존한 별도 목록 |
| `analysis/analysis.json` | 기존 접근/소실+완화 의심 결과와 source pointers |
| `analysis/cards.json` | 기존 EXP-0036 사건 카드 스키마와 동일한 `events/cards/timeline/counts` |
| `evidence/original.mp4` | 선택한 전체 구간의 원본 시야, 오버레이 없이 H264 재인코딩 |
| `evidence/incident-….mp4` | 카드 첫 알림3초 전부터 마지막 알림3초 후까지, 선택 구간 내 원본 근거 |
| `evidence/source-frames.json` | native PTS/time_base ↔ 상대 재생초 대응 |
| `registration.json` | 기존 서비스 등록용 경로/SHA/세션/카메라/미디어 계약 |
| 각 단계의 `stage.json` | 완료된 단계 산출물 전체 SHA와 비용, 입력 결속 |
| `queue-job.json` | 새 검출을 실제 등록했을 때 canonical job 영수증 |

기존 서비스에 한 번에 등록하려면 명령 끝에 `--register-config /absolute/existing/runtime/local_config.json --registration-id NEW_LOCAL_ID`를 추가한다. 기존 `completion.lock` 아래에서 현재 설정을 다시 읽고 새 bundle/media ID만 원자적으로 추가한다. 기존 EXP-0037 배정, 저장소/outputs allowroot, 완료 상태, bundle/analysis/원본 근거 SHA를 검증한다. 설정 백업과 `service-registration.json`을 보존한다. 다른 내용으로 등록된 ID는 덮어쓰지 않는다. 같은 내용의 재등록은 허용한다. 알림 수신 영수증/검토 DB/공개 카탈로그는 변경하지 않고 서비스도 재시작하지 않는다.

실제 개발 시연의 추가 등록 옵션은 각각 다음과 같다. CLI 등록은 기존 최초 알림/무음 갱신과 영수증 기반 중복 억제를 활성화한다. 저장 영상의 재생 알림이며 실시간 분석 지연을 측정한 결과가 아니다. 비교 baseline/proposed는 별도로 알림 비활성 상태를 유지한다.

```bash
--register-config /home/jhc7484/dev/sceneguard-orca-lab/runtime/orca-lab/local_config.json \
--registration-id exp37-cli-007-final

--register-config /home/jhc7484/dev/sceneguard-orca-lab/runtime/orca-lab/local_config.json \
--registration-id exp37-cli-030-final
```

`registration.json` 필수 계약:

- `cards_path`, `cards_sha256`, `analysis_path`, `analysis_sha256`: 로컬 절대 경로와 실제 바이트 SHA.
- `session_id`, `camera_id`, `gate_id`, `video_id`, `counts`: 카메라를 명시하고 세션을 source/request SHA에 결속한다. 새 bundle에 예전 수동 검토 결과를 복사하지 않는다.
- `analysis_mode`: `saved_cache` 또는 `new_detector_canonical_queue`. 전자는 **저장 검출 결과 사용**이며 CPU 추적/후처리/영상 생성은 이번에 실행할 수 있다. 후자는 최초 새 검출의 계보이며 resume의 실제 새 추론 수는 `status.json.detector_frames_this_execution`에서 별도로 본다.
- `requested_window`, `source_window`, `analysis_scope`, `source_pts_origin`, `playback_pts_origin`: 요청 끝 제외와 실제 마지막 프레임을 구별한다. 예를 들어007 원본 PTS70초는48초 시작 clip에서 재생22초다.
- `media[]`: `key`, `path`, `sha256`, `file`, `incident_id`, `source_start_pts`, `source_last_pts`, `source_end_exclusive`, 재생 길이/프레임 수/코덱. `key=original`은 선택 구간 전체이고 나머지는 카드 ID다.
- `source_path`, `source_sha256`, `request_sha256`, `source_frames_path`, `local_only=true`: 원본과 출처 결속. 등록 이후에도 서버가 실제 SHA/허용 경로를 검증한다.

등록 설정의 `incident_bundles`에는 기존 방식대로 outputs 상대 `path`, `sha256`, `media_artifact_id`, `experiment_id`, `session_id`, `source_label`, `view_label`, `provenance_label`을 사용한다. 자동 카드의 status와 수동 검토 status는 별도다.

## 중단과 재실행

같은 출력의 동시 실행은 파일 lock으로 거부한다. 성공한 단계는 새 임시 디렉터리에서 만들고 완료 때 한 번만 게시한다. 실패한 부분 자료는 보존하고 다음 실행은 완료 단계만 검증해 재사용한다. 완료 파일의 추가/누락/변경, 원본/설정/scene/코드 SHA 변경은 재사용을 거부한다. 입력이나 구현이 바뀌면 새 출력 디렉터리를 사용한다.

근거 영상은 원본 native PTS와 정확히 대응하는 모든 프레임을 디코딩하고, 출력 H264의 프레임 수와 상대 PTS도 다시 검증한다. 재인코딩은 압축을 포함하므로 원본 파일의 비트 동일 사본은 아니다. 원본 파일은 SHA와 경로로 별도 보존한다. 영상 의미·실제 침입 정확도는 이 검증의 대상이 아니다.

관련 계약 테스트:

```bash
.venv/bin/python -m unittest discover -s tests -p test_video_cards.py -v
.venv/bin/python -m unittest discover -s tests -p test_mvp_finish.py -v
.venv/bin/python -m unittest discover -s tests_orca -p test_queue.py -v
```

실제007/030은 개발 영상이다. 소수 영상의 카드/프레임/테스트 수를 정확도나 정답 사람 수로 해석하지 않는다. 새 독립 정상/침입 평가, 일반화, 실시간 동작은 별도 미평가다. 모든 영상·좌표·응답·DB·검토 메모·로그는 로컬 전용이며 Git에 포함하지 않는다.
