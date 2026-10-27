# Phase 2A 로컬 CLI

이 CLI는 개발 영상 진단용이며 이벤트 정답 평가기가 아니다. 원본 JSON/캡션을 읽지 않는다. 기본 모델은 [ADR-0007](../decisions/ADR-0007-phase2a-detector.md)의 SSDLite320 COCO_V1이다. 추가 비교용 FCOS COCO_V1은 [ADR-0008](../decisions/ADR-0008-fcos-detector-comparison.md)에 따른다.

## 환경 준비

```bash
uv venv .venv --python python3
UV_HTTP_TIMEOUT=180 uv pip install --python .venv/bin/python torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu124
uv pip install --python .venv/bin/python av==16.0.1 numpy==2.2.6 pillow==12.3.0
.venv/bin/python -m unittest discover -s tests -v
```

CUDA 없는 환경은 명시적으로 `--device cpu`를 지정해야 한다. 자동 CPU 전환으로 GPU 결과를 혼동하지 않는다. CUDA 드라이버와 PyTorch 번들 runtime 버전은 다를 수 있다. 의존성/가중치는 격리 환경·로컬 weights에만 둔다.

## 로컬 경계 설정

`data/cv_phase2a/configs/`에 JSON을 둔다. 아래는 **인공 예시**이며 실제 CCTV 설정이 아니다. 선분은 방향 있는 두 끝점, ROI는 `[xmin,ymin,xmax,ymax]`, 모두 원본 너비/높이로 정규화한다. 경계 거리는 정규화 영상 공간에서 계산한다. 가림 영역을 포함한 실제 발점·경계의 물리적 일치를 보장하지 않는다.

```json
{
  "version": "example-only",
  "camera_group": "synthetic",
  "boundary_id": "line-1",
  "line": [[0.5,0.2],[0.5,0.8]],
  "roi": [0.1,0.1,0.9,0.9],
  "band": 0.005,
  "dwell_seconds": 0.1,
  "max_gap_seconds": 0.1,
  "min_iou": 0.3,
  "cooldown_seconds": 1.0,
  "score_threshold": 0.5,
  "directions": ["negative_to_positive", "positive_to_negative"]
}
```

양측 모두 실제 검출이 최소 dwell 시간 동안 지속돼야 한다. 한 프레임이라도 검출이 없으면 인접 연결이 끊긴다. max_gap은 입력 PTS 간격 상한이며 누락 프레임을 예측해 채우는 기능이 아니다. 매칭 후보가 복수이면 연결을 거부한다. 같은 ID가 계속 한쪽에 있는 동안 반복 경보가 없고, 실제 반대 방향으로 돌아오면 별도 후보가 가능하다.

## 실행

```bash
# 이미 감사한 개발 영상만 사용. 최초 실행에만 공식 13MB급 가중치 다운로드 허용.
.venv/bin/python -m sceneguard.run_cv --video data/TS_침입/E01_030.mp4 --config data/cv_phase2a/configs/C6.json --output outputs/cv_phase2a/smoke030 --start 84 --end 100 --download-weights
# 전체 클립: 상태를 처음부터 유지. 출력 경로는 기존 경로 재사용 금지.
.venv/bin/python -m sceneguard.run_cv --video data/TS_침입/E01_030.mp4 --config data/cv_phase2a/configs/C6.json --output outputs/cv_phase2a/full030
```

`--start/--end`는 smoke 범위를 제한하며 start에서 추적 상태를 새로 시작한다. 이전 프레임은 시각 확인을 위해 디코딩만 하고 추론하지 않는다. 본 진단은 전체 클립 모드로 실행해 cold-start 영향과 구분한다. 프레임 샘플링·PTS 리셋·고정 FPS 보간 없음. PyAV `pts*time_base`와 원본 정수 PTS/유리수 time_base를 함께 보관한다.

## 결과와 시간 측정

- `frames.jsonl`: 원본 PTS, bbox/score/임시 ID/실제 관측 여부. 사람 class만 저장.
- `events.jsonl`: 양측 관측·추정 통과 구간/시각·출력 시각·방향·모델/config/code SHA·불확실성과 로컬 영상/시각 참조. 완료·법적 판단 unknown.
- `run.json`: 모델/영상/config/code 해시, 환경, 프레임 수, 단계별 평균/p50/p95, throughput, CUDA peak allocated/reserved, 연결 단절, 종료 미확정 상태.
- `native_pts.json`, `timings_ms.json`, 약 5초 간격 및 경보 시점 JPG는 로컬에만 저장.
- batch=1, FP32, warmup 10프레임 제외, CUDA 단계 동기화. 전처리는 RGB 변환/텐서 전송, detector는 내부 resize/정규화/네트워크/NMS, rules는 출력 전송/person 필터/연결/경계, output은 JSON·선택 JPG 포함.
- 처리 FPS는 warmup 후 반복 전체 wall time 기준. 모델 로딩/다운로드·warmup·smoke 이전 디코딩·최종 summary 생성 및 첫 프레임 디코딩은 제외한다. 시작 시 첫 프레임 decode 시간은 단계 통계에는 포함된다. 실시간 경보 성능이나 영상 FPS와 같지 않다.
- 기록은 프레임 출력 파일 flush까지 포함하지만 디스크 fsync 지연은 측정하지 않는다. GPU peak는 PyTorch allocator 기준이며 전체 디스플레이/GPU 프로세스 메모리와 다르다.
- 실패 시 처리된 프레임 수와 오류를 run.json에 기록한다(모델 준비 이전 실패는 CLI 오류로 남음). 실패 실행의 일부 출력을 완료 결과로 합치지 않는다.

전체 precision/recall/F1/FP-hour 계산은 하지 않는다. 006의 후보 비이벤트·프레임 수 차이, 006/007 같은 카메라, 031의 미완료 종료를 그대로 유지한다. 임계값·경계는 추론 전에 정하고 출력에 맞춰 수정하지 않는다.


## FCOS 소규모 비교

`--detector fcos800`으로 선택한다. 생략하면 기존 `ssdlite320`이다. 가중치 경로는 선택 모델에 맞게 자동 결정하며 최초 다운로드는 `--download-weights`로 명시한다. 두 모델 모두 공식 hash prefix를 확인한다. 기존 출력 디렉터리를 재사용하지 않는다.

FCOS는 min_size=800/max_size=1333, 모델 내부 resize/padding 실제 크기는 `model_input_observed`에 저장한다. ROI·추적·임계값은 그대로다. 코드 구조가 달라진 모델 비교이며 해상도 단독 효과 실험이 아니다. 새 실험은 EXP-0001의 네 짧은 구간만 사용한다.

```bash
.venv/bin/python -m sceneguard.run_cv --detector fcos800 --video data/TS_침입/E01_030.mp4 --config data/cv_phase2a/configs/C6.json --output outputs/cv_phase2b/fcos030 --start 84 --end 100 --download-weights
.venv/bin/python scripts/compare_cv_runs.py --old outputs/cv_phase2a/smoke030 --new outputs/cv_phase2b/fcos030 --video data/TS_침입/E01_030.mp4 --output outputs/cv_phase2b/review030
```

비교 스크립트는 영상/config/추적 코드 해시 및 모든 PTS 일치를 검사하고, 2초 간격의 가까운 원본 프레임을 로컬 이미지로 저장한다. 정답 생성이나 정확도 계산 기능은 없다.


## FCOS 읽기 전용 후보 계측 (EXP-0003)

`--diagnose-fcos`는 FCOS 전용이다. 원래 후처리 반환값은 그대로 쓰고 별도 shadow에서 내부 단계·NMS 억제 관계를 기록한다. 계측 시간은 기존 성능 측정과 비교하지 않는다. 현재 상세 raw 저장 시점은 E01_030의 84/88/90/92/94/96초로 고정되어 있으며 모든 처리 프레임의 단계 집계와 후처리 일치 검사는 수행한다.

`--start 84 --end 96.000001`은 exclusive end 규칙으로 96초까지 포함한다. 기존 config/모델/입력/필터를 바꾸지 않으며, 새 출력 디렉터리를 지정한다. 재현 명령·사람 위치 대응 방식·로그 형식·제한은 [EXP-0003](../experiments/EXP-0003-fcos-candidate-diagnostics.md)을 따른다. 검수 위치는 진단 표시만 위한 것이며 crop 추론이나 정답 입력으로 사용하지 않는다.


## EXP-0004 반환 person 캐시와 점수 기준 재생

`run_cv --cache-person`은 모델 내부 후처리/NMS/global cap 이후, 프로젝트 마지막 person 점수 기준 이전의 person 박스·점수·원본 PTS를 로컬 `person_cache.jsonl`에 보존한다. 기존 최종 출력은 그대로이며 캐시 기록 시간은 기존 추론 속도와 비교하지 않는다.

`python -m sceneguard.replay_thresholds --cache <cache-dir> --baseline <EXP2-run> --output <new-dir>`는 0.5/0.4/0.3/0.25를 각각 새 tracker로 재생한다. stage/schema/hash와 고정 설정, 수집 및 재생 0.5의 기존 결과 완전 일치를 검사한다. 내부에서 탈락한 후보를 복원하거나 NMS를 다시 적용하지 않는다. 출력 t050/t040/t030/t025의 config·summary에 실제 기준과 캐시 해시를 기록한다. 재생 FPS는 모델 FPS가 아니다.

`render_threshold_review.py`는 기존 35검수 PTS를 원본 위에 네 조건으로 표시하고, `summarize_threshold_review.py`는 동일 PTS/앵커 ID의 span을 진단한다. 출력은 로컬 전용이고 ID는 검증된 사람 정체가 아니다. 실행 명령과 경로는 [EXP-0004](../experiments/EXP-0004-fcos-score-threshold-comparison.md)를 따른다.


## EXP-0005 ByteTrack 캐시 재생

`uv pip install --python .venv/bin/python -r requirements-tracking.txt` 후 `python -m sceneguard.replay_tracking 030 006 007 031`로 기존 EXP-0004 캐시를 A/B/C 재생한다. detector/가중치를 로드하지 않는다. 출력은 `outputs/cv_phase2e/track{ID}/{A,B,C}`이며 이미 존재하면 실패한다.

B/C의 `detections`는 confirmed 실제 관측이다. bbox는 캐시 원본 정규화 좌표, filter_bbox는 Kalman 위치, cache_index는 원시 캐시 대응이다. states에는 unconfirmed/observed=false lost_prediction을 따로 보존한다. 예측 bbox는 경계 입력에 쓰지 않는다. `ObservedBoundary`는 외부 track_id를 그대로 사용하고 한 프레임 미관측 또는 PTS gap>.1초에서 경계 상태를 reset한다. A의 기존 IoU 연결/출력은 회귀 검증으로 보존한다.

`audit_tracking_replay.py`는 실제 관측·후보 연속성을 검증하고, `render_tracking_review.py`는 네 연속 비교 영상·35개 고정 이미지·후보 주변 표시용 확대 카드를 만든다. 공식 ByteTrack 출처/고정 설정/최소 호환 수정/테스트/실패는 [EXP-0005](../experiments/EXP-0005-bytetrack-cache-comparison.md)와 ADR-0010 참조. 캐시 처리 시간은 전체 추론 FPS가 아니다.
