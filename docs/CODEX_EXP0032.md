# EXP-0032 — 월장 사건 단위 제한된 평가 (최신 승인)

2026-10-30. 이번 작업은 기존 SceneGuard의 월장 후보가 실제 **시도/진행 구간과 검수된 정상 구간**을 얼마나 포함하는지 평가한다. 새 모델 탐색/튜닝이 아니다. 코드만 게시하거나 정답을 추측해 성공이라고 쓰지 않는다.

## 평가 계약

1. **모델·설정 고정.** 원래 사전학습 FCOS COCO_V1 + 기존 ByteTrack gap(3초 유지, 원래 dwell/cooldown) + 카메라별 기존 경계선을 사용한다. EXP-0030 사건 피드·현행 사용자 수정 outside/inside polygon·EXP-0031 ReID·과거 결과는 그대로 둔다. YOLO26m 파인튜닝/새 모델/추적기/threshold sweep 없음.
2. 모든 주평가 영상에서 동일한 gap/events.jsonl의 **실제 출력 시각(emitted_at_pts)**을 사용한다. EXP-0030의 region 후보·strict 이벤트·사후 ReID 같은 ID 제안은 보조 설명일 뿐 주평가 후보로 추가하지 않는다. 2초 이내 연속 경계 후보를 하나의 **사건 검토 episode**로 묶되 모든 원래 후보를 보존한다. 사람별 ID나 물리적 완료를 확정하지 않는다.
3. **정량 평가의 유일한 사람 확인 라벨:** 사용자 확인이 완료된 007 [47.5,52.5) 정상 접근(q02), [52.5,57.5) 정상 접근(q03), [62.5,67.5) 월장 시도/진행(q04). 실제 분석 영상이 48초부터이므로 첫 창은 확인된 범위의 부분집합 [48,52.5)로 제한한다. 007 [0,5), 030 [50,55), [155,160)는 이번 캐시 범위 밖이므로 점수화하지 않는다.
4. 030 [88.933,96.933), 001 [60.867,95.133) 공식 이벤트는 **거친 참고 시각**, 031 [33,46)은 접촉/시도 불확실, 006 [119,132)은 **검증 전 정상 후보**다. 이 네 구간은 provisional이므로 정량 분모·FP에 넣지 않는다. 특히 006/007은 같은 C3 카메라 그룹이며 독립 test가 아니다.
5. 완전한 사건 정답이 없으므로 full-event recall/precision/F1/완료 정확도는 null. 정량 출력은 확인된 짧은 창에서 후보가 있었는지와 확인된 정상 시간에서 오경보 검토 episode 수다. 정상 검수 시간 5분 미만에서는 시간당 FP를 보고하지 않는다. 출력이 없는 미확인 시간을 TN으로 채우지 않는다. 실제 신호 시각 대신 사후 candidate_pts로 진단 창 안쪽 TP를 만들지 않는다.

## 대상 영상과 캐시

| 영상 | 현재 입력 PTS 창 | 기존/신규 캐시 | 후보 평가 역할 |
|---|---|---|---|
| E01_030 | [84,100) | 기존 outputs/cv_phase2d/cache030 + outputs/exp0028/practical-v1/track030 gap | 거친 공식 양성 참고, 미확정 |
| E01_007 | [48,105) | 기존 outputs/exp0029/cache007 + outputs/exp0029/replay007 gap | **확인된 정상2창·시도1창** |
| E01_006 | [117,133.67) | 기존 outputs/cv_phase2d/cache006 → 새 CPU gap replay | 정상 후보 119~132, 미확정 |
| E01_031 | [30,46) | 기존 outputs/cv_phase2d/cache031 → 새 CPU gap replay | 접촉/시도, 완료 미확정 |
| E01_001 | [58,98) | 이미 완전한 동등 캐시가 없으면 **기존 FCOS GPU 추론 1회** → CPU replay | 공식 양성 범위 참고, 미확정 |

EXP-0004/0005 기록에 006/031 완전한 FCOS 캐시가 있다. 001은 아직 확인된 연속 캐시가 없어서 한 번 추가하는 대상이다. 기존 동등한 입력/모델/설정/PTS 캐시가 이미 있다면 새 GPU 실행0으로 대체할 수 있다.

## 로컬 Codex 실행 순서

1. 기존 결과·로컬 C3/C6/C7·사용자 polygon·가중치·공식 라벨을 절대 덮어쓰지 말고 main을 동기화한다. 기존 canonical GPU queue·Orca Run·독립 검토 및 free VRAM gate를 재사용한다. 신규 총괄/큐/학습/가중치 다운로드 없음. 학습/정답 라벨을 model/tracker/경계 설정에 입력하지 않는다.
2. 사전 고정 configs/exp0032_incident_windows.json을 읽고, 순수 stdlib 평가기 sceneguard/incident_evaluation.py 및 tests/test_incident_evaluation.py를 확인한다. 평가기는 기존 FCOS cache/meta의 video/sha/시간, replay의 입력 sha, 원 이벤트 개수 및 emission PTS를 검사한다. 실제 데이터가 없으면 실행 성공이라고 주장하지 않는다.
3. **001의 카메라 C1 경계가 로컬에 없는 경우:** 원본 PTS0의 정적 배경만 보고 유한 경계선/ROI를 data/cv_phase2a/configs/C1.json에 한 번 설정한다. docs/design/CV_BASELINE_CLI.md의 필수 schema를 따른다. 원격의 인공 좌표를 복사하지 않는다. band .005, dwell .1, max gap .1, min_iou .3, cooldown1, score .5, 양방향 설정을 유지한다. 원본/배경/경계 설정 SHA를 **후보 보기 전에 freeze**하고 모델 출력을 보고 선을 수정하지 않는다. 정적 장면으로 경계를 정의할 수 없으면 001은 unassessable로 별도 보고한다.
4. **001 FCOS 새 추론:** 기존 공식 pretrained fcos800 checkpoint와 run_cv --cache-person을 이용해 [58,98) 구간 **한 번만** 생성한다. 반드시 기존 canonical GPU 큐를 통해 enqueue/exe하며 워커 직접 중복 GPU 실행 금지. 예상 명령:

       .venv/bin/python -m sceneguard.run_cv \
         --detector fcos800 --cache-person --device cuda \
         --video data/TS_침입/E01_001.mp4 \
         --config data/cv_phase2a/configs/C1.json \
         --output outputs/exp0032/cache001 --start 58 --end 98

5. **CPU replay:** 기존 재생기의 run(cache_path,output_path,3.0)을 호출한다. 030/007은 재실행하지 않는다. 원본 cache006/cache031과 새 cache001의 해시를 보존하고 각 경로 outputs/exp0032/replay006, replay031, replay001에 **각1회** strict+gap 재생한다.

       .venv/bin/python - <<'PY'
       from sceneguard.replay_gap_tracking import run
       run("outputs/cv_phase2d/cache006","outputs/exp0032/replay006",3.0)
       run("outputs/cv_phase2d/cache031","outputs/exp0032/replay031",3.0)
       run("outputs/exp0032/cache001","outputs/exp0032/replay001",3.0)
       PY

6. **정량 평가:** 위 모든 결과가 준비되고 source/meta/원본행/binding이 맞을 때만 실행. 이전 평가를 덮어쓰지 않는 새 local 경로다.

       .venv/bin/python -m unittest discover -s tests -p test_incident_evaluation.py -v
       .venv/bin/python -m sceneguard.incident_evaluation \
         --manifest configs/exp0032_incident_windows.json \
         --output outputs/exp0032/evaluation-v1.json

7. **원본 시각 검수:** 007 Q02/Q03 정상, Q04 시도(완료 미확인), 70.133초가 검수 5초 창 **밖의 후속 후보**라는 점을 확인한다. 030 90초대, 001 공식 거친 창, 031 접촉/미완료 가림, 006 경계 부근 보행은 원본과 추적 오버레이/후보 시각으로 보되 평가 라벨은 provisional 유지한다. 후보가 **0개인 구간도 원본 검수 영상**을 만든다. 기존 EXP-0030/EXP-0005 렌더러와 같은 로컬 뷰어를 재사용한다. 총괄 시각 초안과 이전 사용자 확인 정답은 구분한다. Q02/Q03/Q04 사용자 확인을 다시 묻지 않는다.
8. **결과/검증:** 5영상 후보/2초 episode 수, 확인된 양성 창 후보 여부, 확인된 음성 창 FP episode 수·총 확인 초, 미확인 후보 수, 처리 비용과 설명 가능한 오탐/미탐, 임시/미완료/공식 시각의 제한을 하나로 보고한다. 독립 검토가 원본/가중치/FCOS 캐시/정책/새 후보/모든 보호 파일/기존 jobs를 확인한다.
9. 기존 담당3에 EXP-0032 비식별 보고서/metrics/검토/비식별 근거 미디어를 등록하고, 실제 브라우저에서 play/seek/표시를 검증한다. GitHub에는 코드, 테스트, 비식별 결과만; 원본 CCTV·인물 크롭·원시 검출·C1 config/영역 좌표·official 원시 라벨·weights/DB/로그는 로컬에만 둔다.

이번 단계는 **실제 로컬 영상 평가 결과**가 있어야 완료다. GPU 또는 라벨 조건 때문에 001이 막히면 이미 확보된 030/007/006/031에 대한 정직한 부분 결과와 실패 이유를 남긴다. 모델·폴리곤·threshold를 결과에 맞춰 다시 조정하거나 후속 대형 실험을 자동 시작하지 않는다.
