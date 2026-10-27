# EXP-0001 — 최소 CV baseline 첫 로컬 진단

- 날짜/담당: 2026-10-27 / Codex.
- 승인: [ADR-0006](../decisions/ADR-0006-limited-cv-baseline-prototype.md). 모델 근거: [ADR-0007](../decisions/ADR-0007-phase2a-detector.md).
- 추론 코드 커밋: `2208857a8e01b5a720dc1a8248e1be6abec87b09`. 실행별 run.json에 실제 두 코드 파일 SHA256도 기록. 후속 문서/검사 스크립트가 작성 중이어서 일부 run의 git_dirty는 true이며, 추론 코드 변경 여부는 파일 해시로 별도 확인한다.
- 상태: 실행 결과는 아래 측정 표 참조. **개발 표본 진단이며 최종 정답 성능 평가가 아니다.**

## 가설과 목적

사전학습 사람 검출 1개 + 인접 IoU 연결 + 카메라별 경계 양측 관측으로 사건 후보를 기록할 수 있는지 확인한다. 등장/접촉만으로 이벤트를 만들지 않는 인공 테스트와 실제 CCTV에서의 검출 누락·ID 단절을 분리한다. SSDLite320의 고정 저해상도 입력이 작은/가려진 사람을 놓칠 가능성을 첫 실패 가설로 둔다. 학습·복잡한 tracker·VLM은 도입하지 않는다.

## 데이터·설정

- 기존 로컬 `data/TS_침입/E01_006/007/030/031.mp4` 네 개발 영상만 사용. 신규 데이터 다운로드 없음. 공식 JSON·사용자 검수는 추론에서 읽지 않는다. 원문/미디어/박스/결과 이미지 모두 로컬 전용.
- 006/007은 같은 카메라 그룹 C3, 030은 C6, 031은 C7인 시각 구도 후보. 서로 독립인 장소라는 뜻이 아니며 train/test 분할을 만들지 않았다.
- 006의 약 119~132초는 비이벤트 후보일 뿐 검수된 음성 정답이 아니다. 실제 4006 vs JSON 4011 프레임 차이 보존. 이번 해당 영상 추론은 PTS 117~133.67초 구간만 수행한다.
- 001/007/030의 첫 등장과 넘기 시작을 동일하게 사용하지 않는다. 031은 사용자가 확인한 접촉·미완료 종료를 유지하며, 예측의 완료/법적 판단은 모두 unknown이다.
- 배경 PTS 0 프레임만 보고 출입문/울타리의 선분·직사각형 ROI를 수동 설정. 기존 영상 내용을 이미 검토한 개발 설정이지 블라인드 설정은 아니다. **첫 추론 전에 설정을 고정했고 이후 후보 수에 맞춰 바꾸지 않았다.**
- 로컬 설정 `data/cv_phase2a/configs/{C3,C6,C7}.json`. 정규화 거리 band=0.005, 양측 dwell=0.1s, 최대 인접 PTS gap=0.1s, IoU≥0.3, person score≥0.5, 같은 방향 중복 억제=1s, 양방향 허용. 한 프레임 누락/모호한 연결도 새 ID로 분리하는 보수적 규칙.

| config | 추론 전 고정 SHA256 |
| --- | --- |
| C3 | `94036e497248198687b714f4334ac2df60eaa204e0f43323db1977a51119c41e` |
| C6 | `feea6703d31f21a1aa7f45a6843fe938f8887b7a8ba729a5be62f6a07785509b` |
| C7 | `71a56055e0cf318ae4c5896339ebaffdf3e6fac2ba8bd7c03cc914a10e350275` |

실제 좌표는 위 로컬 config에 보관한다. 재현은 동일 원본/config/가중치 해시를 사용해야 한다. CLI 문서의 좌표 예시는 인공 예시로 실제 실험 설정을 대체하지 않는다.

## 환경·모델

- WSL2 Ubuntu 22.04 / Linux 6.6.87.2-microsoft-standard-WSL2 / Python 3.10.12.
- NVIDIA GeForce RTX 3080, nvidia-smi 총 10,240 MiB. 드라이버 보고 610.57.01, KMD 610.88. nvidia-smi CUDA UMD 13.3은 드라이버 능력 표기이며 실제 torch runtime은 **CUDA 12.4**.
- 격리 `.venv`, torch **2.5.1+cu124**, torchvision **0.20.1+cu124**, PyAV **16.0.1**, NumPy **2.2.6**, Pillow **12.3.0**. 공식 CUDA wheel index + PyPI의 필요 의존성만 설치. `data/cv_phase2a/environment-freeze.txt`에 전이 의존성 26개 실제 버전 보관.
- GPU tensor 합산과 CUDA available 확인 성공. 기존 시스템 Python에 torch/torchvision/av는 없었다. 별도 시스템 CUDA toolkit을 설치하지 않았다. 모델 설치는 약 14MB지만 torch wheel 866.2MiB·cuDNN wheel 634.0MiB 등 CUDA 전이 의존성은 훨씬 크다(설치 로그 값). 데이터셋 다운로드와 구분한다.
- 모델: `ssdlite320_mobilenet_v3_large.COCO_V1`, **3,440,060 parameters**, **14,069,355 bytes (약 13.42 MiB)**. [공식 가중치](https://download.pytorch.org/models/ssdlite320_mobilenet_v3_large_coco-a79551df.pth).
- SHA256: `a79551df90c79834bcd3bb3845ef9d966b5449a3a9b2833ae8404778ca5d65d2`. 공식 hash prefix 확인 후 로컬 state_dict를 weights_only로 로드. 한 모델만 설치·추론, 학습 없음.
- TorchVision 코드 BSD-3-Clause, 사전학습 모델의 데이터 유래 조건은 별도라는 공식 안내를 [ADR-0007](../decisions/ADR-0007-phase2a-detector.md)에 기록. 가중치·원 학습 데이터의 공개/상용 배포 허가를 주장하지 않는다.
- 입력은 원본 1920×1080 RGB → 모델 내부 고정 320×320. FP32, batch=1, CPU/PyAV threads=2, seed=0, cudnn benchmark 및 TF32 비활성. 원본 PTS·모든 구간 내 프레임 유지; FPS 보간·프레임 샘플링 없음.
- GPU는 Windows 디스플레이 사용 환경이며 다른 OS 작업 부하를 완전히 통제하지 않았다. 이 속도를 RTX 3080의 보편적인 모델 벤치마크로 보지 않는다.

## 실행 명령

환경 설치·CLI 계약: [CV_BASELINE_CLI](../design/CV_BASELINE_CLI.md).

```bash
python3 -m unittest discover -s tests -v
.venv/bin/python -m sceneguard.run_cv --video data/TS_침입/E01_030.mp4 --config data/cv_phase2a/configs/C6.json --output outputs/cv_phase2a/smoke030 --start 84 --end 100 --download-weights
.venv/bin/python -m sceneguard.run_cv --video data/TS_침입/E01_006.mp4 --config data/cv_phase2a/configs/C3.json --output outputs/cv_phase2a/smoke006 --start 117 --end 133.67
.venv/bin/python -m sceneguard.run_cv --video data/TS_침입/E01_007.mp4 --config data/cv_phase2a/configs/C3.json --output outputs/cv_phase2a/smoke007 --start 48 --end 68
.venv/bin/python -m sceneguard.run_cv --video data/TS_침입/E01_031.mp4 --config data/cv_phase2a/configs/C7.json --output outputs/cv_phase2a/smoke031 --start 30 --end 46
.venv/bin/python -m sceneguard.run_cv --video data/TS_침입/E01_007.mp4 --config data/cv_phase2a/configs/C3.json --output outputs/cv_phase2a/full007
python3 scripts/check_cv_runs.py outputs/cv_phase2a/smoke030 outputs/cv_phase2a/smoke006 outputs/cv_phase2a/smoke007 outputs/cv_phase2a/smoke031 outputs/cv_phase2a/full007
```

각 출력 경로는 새 디렉터리여야 한다. 기존 실행 덮어쓰기 금지. 짧은 smoke는 start에서 ID 상태를 새로 시작하고, full007은 시작부터 끝까지 유지한다. smoke와 full 수치를 독립 영상처럼 합산하지 않는다.

## 정량 결과 — 실행 후 자동 집계 표

| 실행 | 실제 PTS 범위(s) | 처리 프레임 | 사람 검출 프레임 / bbox | 후보 | wall(s) | 처리 FPS | 전체 p50 / p95(ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| smoke030 | 84.000000–99.966667 | 480 | 1 / 1 | 0 | 53.082 | 9.043 | 99.359 / 185.306 |
| smoke006 | 117.016900–133.666867 | 500 | 0 / 0 | 0 | 55.950 | 8.937 | 109.492 / 163.355 |
| smoke007 | 48.000000–67.966667 | 600 | 96 / 173 | 0 | 53.019 | 11.317 | 75.945 / 143.595 |
| smoke031 | 30.000000–45.966667 | 480 | 0 / 0 | 0 | 42.001 | 11.428 | 78.598 / 149.445 |
| full007 | 0.000000–139.000000 | 4,171 | 312 / 407 | 0 | 433.766 | 9.616 | 94.599 / 174.800 |

표는 5회 단일 실행 결과다. 4개 영상에서 총 6,231회 프레임 추론(007 smoke/full 중복 포함), 실제로 서로 다른 추론 프레임은 5,631개다. 모델 초기화/warmup 추론은 이 수에서 제외했다.

| 실행 | decode mean(ms) | preprocess mean(ms) | detector mean(ms) | rules mean(ms) | output mean(ms) |
| --- | --- | --- | --- | --- | --- |
| smoke030 | 3.422 | 9.997 | 96.581 | 0.359 | 0.199 |
| smoke006 | 1.788 | 9.957 | 99.568 | 0.377 | 0.184 |
| smoke007 | 2.354 | 8.874 | 76.637 | 0.320 | 0.155 |
| smoke031 | 2.070 | 10.328 | 74.572 | 0.314 | 0.190 |
| full007 | 2.324 | 10.770 | 90.395 | 0.350 | 0.139 |

모든 실행의 PyTorch peak allocated **85.35 MiB**, peak reserved **108.00 MiB**(warmup 후 peak 통계 리셋). GPU 전체 사용 메모리가 아니다. full007에서 detector p50/p95 **80.808/159.587ms**, 전체 p50/p95 **94.599/174.800ms**로 이 실행의 시간 대부분이 detector 구간에 있었다. 커널별 원인은 아직 프로파일링하지 않았다.


시간 측정은 warmup 10프레임 제외, GPU 동기화, 단일 프로세스 순차 실행이다. 전체 throughput은 디코딩·RGB/텐서 전처리·검출·규칙·JSON·주기적 JPG·flush를 포함한 처리 loop wall time. 모델 준비·warmup·smoke 전 디코딩·첫 프레임 디코딩·최종 summary는 제외. 단계 통계에는 첫 프레임 디코딩도 포함하므로 wall/단계 합계는 정확히 같지 않다. 이 차이를 포함한 측정 범위를 명시하며 실시간성은 주장하지 않는다.

**정답 기반 Precision/Recall/F1/FP-hour/감지 시작 오차: 산출하지 않음.** 검수된 음성 시간·사람별 시작·완료·평가 manifest 미확정 때문이다. 표의 검출 프레임·후보 수는 탐색적 출력 통계다. 양성/음성 정확도나 사람 검출 recall이 아니다.

## 실패·관찰 사례

1. **030, PTS 89초:** 로컬 근거 이미지에서 여러 사람이 문에 몸을 올리지만 score≥0.5 사람 bbox는 없다. smoke 480프레임 중 단 1프레임(86.366667초)에 bbox 1개, score 약 0.507. 연결이 형성되지 않아 후보 0개. 우선 검출 누락 사례이며 경계 규칙의 정확성을 평가할 수 없다.
2. **007 smoke, PTS 49.566667~53.666667:** 접근 인물 일부만 검출. 600프레임 중 96프레임/173 bbox, 새 ID 22개, 모호 연결 검출 18건, 최대 ID 유지 범위 약 2.3초. 문 앞/넘기 구간에서는 관찰 프레임상 인물이 있지만 검출이 이어지지 않는다. 22개 ID를 실제 사람 22명이나 정답 ID-switch 수로 해석하지 않는다.
3. **006, PTS 약 122.022초:** 먼 경계 옆 보행자가 보이나 사람 검출 0개. 보행 위치는 설정한 가까운 출입문 유한 선분/ROI의 범위 밖이기도 하다. **후보 0은 정상 판별 성공이 아니라 검출·감시 범위의 한계**다. 119~132초를 verified_non_event로 승격하지 않았다.
4. **031, PTS 35초:** 울타리 옆 사람과 동작은 보이나 smoke 480프레임 사람 검출 0개. 작은 크기·차량/나무 가림이 있는 사례. 저해상도/가림이 원인이라는 것은 가설이며 별도 해상도 비교 실험 전 확정하지 않는다. 이번 smoke는 30~46초여서 영상 종료 행동을 새로 검증한 것은 아니다. 사용자가 기록한 종료까지 미완료 상태는 그대로 유지한다.

본 설정으로 양측 통과를 안정적으로 관측했다고 결론내릴 근거가 없다. 인공 시퀀스에서의 규칙 통과와 실제 CCTV 후보 생성 실패를 구분한다. bbox 하단 중심은 물리적 발점/착지의 정답이 아니며 접촉·올라타기·완료 구별은 이 baseline 범위 밖이다.

5. **007 full, PTS 95초:** 앞쪽 보행자 두 명에 bbox가 그려지는 것을 로컬 이미지에서 확인했다. 전체 4,171프레임 중 312프레임/407 bbox, 새 ID 45개·연결 단절 45개, 최대 ID 유지 범위 약 2.3초, 후보 0개. 주기적 이미지에서 문을 넘는 구간의 검출 누락과 가까운 보행자의 간헐 검출을 확인했다. 전체 영상을 사람이 연속 검수한 결과는 아니다. 검출/연결이 되는 일부 프레임만으로 전체 행동 탐지 성공을 주장할 수 없다.

## 실행 검증

- 인공 회귀 테스트 **11개 통과**: 양측 지속/방향/평행 보행/접촉/유한 선분/ROI/누락/PTS 간격/모호 ID/중복 억제/입력 오류.
- 5회 실행의 처리 프레임 수와 모든 PTS를 이전 독립 FFmpeg 감사 manifest와 대조해 일치. 최대 차이 약 **0.000000334초**는 감사 JSON 반올림 수준. full007은 처음 0초부터 마지막 139초까지 4,171개 전부 일치. 006 smoke도 PTS 기반 500개 일치하며 원본 4006을 4011로 보정하지 않았다.
- 공식 JSON 45개와 이번 MP4 4개의 실행 전후 SHA256 동일. 추론 코드 두 파일 및 3개 config 해시는 고정값과 일치. 명령/실행 로그는 `outputs/cv_phase2a/`, 환경·설정·무결성 기준은 `data/cv_phase2a/`에 보존.
- 추론 입력에서 공식/사용자 정답을 읽지 않는 구조를 유지했다. 결과 checker는 추론 종료 뒤 원본 미디어 감사 PTS와 해시만 비교하며 공식 이벤트 정답을 생성하지 않는다.
- 실제 설치 패키지의 라이선스 메타데이터: torch BSD-3-Clause, torchvision BSD(공식 LICENSE는 BSD-3-Clause), PyAV BSD-3-Clause, NumPy BSD 계열 및 번들 고지, Pillow MIT-CMU, NVIDIA runtime은 NVIDIA Proprietary Software. 패키지 코드/번들 라이선스와 모델·원본 영상 사용 조건은 별개다. [설치 버전 목록](EXP-0001-environment.txt)에 26개 버전을 기록했다. PyAV는 libavcodec 62.11.100 / libavformat 62.3.100을 보고하며 이전 감사 FFmpeg 바이너리와 다른 디코더 라이브러리다.

## 오류와 해결

- 공식 CUDA wheel 설치가 UV 기본 30초 다운로드 제한에 걸려 실패. `UV_HTTP_TIMEOUT=180`으로 **동일 공식 경로** 재시도 후 성공. 다른 모델/비공식 미러/인증 우회 없음.
- 첫 인공 통과 테스트에서 bbox가 한 번에 이동하며 IoU 0.091로 설정 하한 0.1보다 작아 ID가 끊겼다. 실제 의도와 다른 fixture였으므로 연결 가능한 bbox 폭으로 수정했다. 별도 누락/모호 ID 테스트는 유지했다. 알고리즘의 IoU 하한을 결과에 맞춰 낮춘 것이 아니다.
- 낮은 검출 수를 해결하기 위한 임계값 낮추기·경계 재설정·사후 ROI crop·두 번째 모델 설치는 이번 실행에 추가하지 않았다. 고정 설정의 실패 기록을 보존한다.

## 다음 선택

먼저 작은 사람·가림에 대한 **검출 해상도/검출기 대안**을 검토할 근거가 생겼다. SSDLite320은 파이프라인 진단용으로 실행됐지만 현재 설정을 메인 감지 모델로 채택하지 않는다. tracker를 복잡하게 만들어 검출이 없는 프레임을 사실처럼 채우지 않는다. 006 감시 경계의 범위와 검수된 음성 시간, 007 등의 사람별 시점, 031 미완료 주체와 카메라 분할은 별도 검수 과제로 남긴다.
