# EXP-0029 — 007 연속 검출 캐시 확장 구현

2026-10-30. EXP-0029의 007 입력 확장에 관한 별도 기술 기록이다. 전체 사람 연결/영역 후보의 결과 보고서는 총괄 기록을 따른다. **독립 사전 검토와 총괄의 실행 결속 후 실제 canonical GPU 실행 1회·병합·연속 replay를 완료했다. 오류/OOM/retry는 모두 0회이며 추가 GPU 작업을 시작하지 않는다.**

기존 사전학습 FCOS COCO_V1의 `sceneguard.run_cv.run`을 변경 없이 호출한다. 원본 `.venv`의 Torch 2.5.1+cu124 / TorchVision 0.20.1+cu124 / PyAV 16.0.1 / NumPy 2.2.6, 원래 full-frame RGB→FP32 입력, min800/max1333, 모델 후처리 score0.2/topk1000/NMS0.6/global100, batch1/seed0/threads2/별도0입력 warmup10회를 유지한다. 가중치 다운로드·학습·새 모델·기본 설정 교체는 없다.

`exp29-cache007` 하나를 기존 canonical GPU 큐에 등록한다. 원래 48–68초의 600행을 재추론하지 않고 68–105초의 1,110행만 새로 생성한다. CPU에서 원본 영상의 실제 native PTS와 기존 캐시를 대조했으며, 병합 후 48–105초의 1,710행이 연속되어야 한다. 원본 캐시 JSONL의 바이트를 그대로 prefix로 붙이고 새 segment의 바이트를 뒤에 붙인다. 표시 FPS로 PTS를 다시 만들지 않는다.

새 캐시의 집계 metadata는 기존 segment의 시간·후보·추적 통계를 전체 구간의 수치로 복사하지 않는다. segment별 실행 metadata는 별도로 보존한다. 병합 캐시에서 기존 `replay_gap_tracking.run`을 48초부터 새로 실행해 strict와 gap3초 관측을 만들고, 앞 600행이 EXP-0028 관측과 정확히 같은지도 확인한다. 68초에서 tracker 상태를 초기화한 출력은 연속 관측으로 사용하지 않는다.

실행 전에는 입력/가중치/원래 캐시 해시, 원본 디코딩 PTS 목록, 원래 네 패키지의 설치 파일 해시, 실행 소스별 SHA256와 HEAD를 동결한다. 총괄이 독립 사전 검토 후 같은 Run/Task/Dispatch·소스·입력·한도를 결속한 authorization을 발급해야 enqueue가 가능하다. child는 상속된 canonical GPU lock, 정확한 live supervisor/child identity와 queue row hash를 다시 확인하며, 기존 free VRAM≥6,144 MiB gate 이전에는 모델을 import/load하지 않는다. 네트워크 연결/DNS/UDP를 차단한다. 오류 재시도는 자동화하지 않고 첫 실행 오류에 대한 총괄의 별도 결속이 있어야 최대 한 번 허용한다.

신규 CPU 테스트 10개는 정확한 PTS 결합, 중복·누락·잘못된 시간 거부, 원본 바이트와 두 입력 segment 보존, 실제 CPU strict/gap replay, 입력·소스·권한·HEAD 결속, 직접 실행 차단, 동일 VRAM gate, 44개 과거 jobs/attempts의 disposable backup migration, retry 제한을 확인한다. 기존 queue 14개를 합쳐 **24개가 통과**했다. 합성 캐시의 replay 성공과 실제 사람 연결 성공은 별도다. 기존 EXP-0027 회귀 한 건은 이미 EXP27 스키마인 canonical DB 사본에서도 새 EXP27 backup을 기대하는 오래된 assertion 때문에 실패했다. 이 테스트와 과거 결과는 변경하지 않았고 실제 실패 로그를 로컬에 보존했다.

실제 실행 결과:

| 항목 | 결과 |
| --- | --- |
| 사전 여유 VRAM | 8,335 MiB, 기존 6,144 MiB 기준 통과 |
| 신규 원본 프레임 | 68.0–104.966667초, 정확히 1,110개 |
| 기존 재사용 + 병합 | 600 + 1,110 = 1,710행, 48.0–104.966667초 |
| 원본 캐시 보존 | 기존 JSONL 바이트 전체를 정확한 prefix로 유지 |
| 연속 tracker 검증 | strict/gap 각각 앞 600행이 EXP-0028과 JSON 전체 일치 |
| 신규 추론 loop | 68.024866초, 별도 warmup 0.816837초 |
| wrapper 전체 | 83.891253초, 입력 검증·추론·CPU 병합/replay 포함 |
| CPU 병합 후 replay/검증 | 1.527514초 |
| 기존 경계 규칙의 후보 | strict 3개 / gap 1개, 실제 사람·넘기 성공 수가 아님 |
| canonical 큐 | 기존 44 jobs/44 attempts 보존, 신규 1 job/1 attempt 추가 |

추론 loop 시간은 원래 `run_cv`가 기록한 post-warmup decode/conversion/inference/rules/JSON/previews/flush 범위다. 전체 wrapper 비용과 다르며 기존 600행의 과거 비용을 새 1,710행의 FPS로 환산하지 않는다. 새 후보 수와 영상 의미 검수·동일인물 연결 여부는 별개다.

실행 관련 source/input freeze·테스트 로그·authorization·receipt는 Git 제외 `runtime/EXP-0029/`에 보존한다. 새 segment, 병합 캐시와 연속 replay는 각각 Git 제외 `outputs/exp0029/extension007/`, `cache007/`, `replay007/`에 둔다. 이 기록은 행동 정확도·동일인물 연결·넘기 완료·실시간 성능을 확정하지 않는다.
