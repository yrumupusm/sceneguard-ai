# EXP-0012 — 원본 전체 영상의 연속 로컬 MVP 통합

- 날짜/담당: 2026-10-28, Sol high 통합 담당. 총괄이 실제 Codex session의 gpt-6.1-sol/high를 확인했다는 native 메시지에 근거한다. 모델 자기소개를 실효 모델 증거로 쓰지 않는다.
- 관련 계획/결정: [MVP-0001](MVP-0001-plan.md), [로컬 CLI 계약](../design/MVP_LOCAL_CLI.md), ADR-0012/0014/0015 및 방법 담당의 이번 ROI ADR.
- 상태: **CPU 구현·기능 준비 완료 / 실제 원본 전체 모델 실행 resource_blocked·unstarted**. 총괄이 GPU 자원 차단을 수락하여 이 dispatch의 실제 모델 목표는 미완료로 종료한다. 모델 실행·행동 평가·독립/총괄 최종 검토·웹 등록·GitHub 게시·화면 확인을 이 기록으로 완료 선언하지 않는다.
- 코드: 최초 CPU 구현 `6fb7f44`(총괄 통합 `d6bf473`), 후보 근거·실패 진단 수정 `8f3ae85`, baseline byte-binding fixture `276bd0d`; 최종 변경은 자원 차단 상태 기록뿐이다. 로컬 CPU receipt에 실제 소스 SHA256을 기록했고 실제 run은 Git SHA와 개별 소스 SHA256을 run.json에 기록한다.

## 가설과 목적

사건 시각을 입력하지 않고 원본 처음부터 EOF까지 주기적 창을 생성하여, CV 후보와 무관하게 행동 분석·유보·병합·원본 맥락 근거 저장을 연결할 수 있는지 확인한다. 전체 화면 Qwen 기준과 사전 고정 카메라 ROI 대조의 행동 품질은 기능 통합과 따로 판단한다. BATCH-0001의 채택 보류는 유지한다.

## 데이터와 평가

전체 실행 예정은 개발 E01_007/C3, E01_030/C6, 설정 선택에 쓰지 않는 E01_013/C4다. C4는 고정 ROI가 없어 full-frame fallback이며 그 결과를 ROI 일반화 개선으로 해석할 수 없다. 013은 과거 장면/공식 구간 감사 이력이 있어 완전 blind test가 아니다. 원본·공식 라벨·환경·과거 결과를 보존한다.

source/camera 설정에는 파일 ID·경로·해시와 배경 기반 ROI만 사용하고 analyzer에는 측정 PTS/익명 창 ID·고정 ROI와 원본 RGB만 전달한다. 평가 문서의 사건 시각/관찰/공식 JSON은 입력이 아니다. 인간 관찰·미확정·기존 메타데이터를 구분하며 모델 출력을 정답으로 사용하지 않는다. 정밀 GT와 검수된 전체 음성 구간이 없으므로 최종 accuracy/precision/recall/F1/시간당 오탐은 미산출이다.

## 환경과 실행 고정

기존 `.venv-vlm`의 CPU Python/PyAV16.0.1/NumPy2.2.6으로 합성 테스트만 수행했다. 환경 설치·새 가중치·모델/GPU inference·외부 미디어 전송은 하지 않았다. 실제 GPU 조건/로드/메모리는 실제 실행 후에만 기입한다.

5초 창,2.5초 stride,2fps 실제 native PTS 표본, 실제 프레임 최소2, batch1, 근거 앞뒤2초, 겹치는 같은 행동 병합 gap0을 고정한다. 원본 전체 흐름과 EOF 잔여를 처리하고 실제 부족 표본은 `insufficient_data`로 남긴다. 세부 출력과 타이밍 정의는 CLI 계약에 고정했다. 실제 실행은 기존 canonical GPU queue에서만 수행하며 실행 오류 job별 재시도 최대1회, 자동 재설정/무인 반복은 없다.

## 로컬 CPU 정량 결과

| 지표 | 실제 값 | 분모·측정 방식 | 조건 |
|---|---:|---|---|
| 합성 CPU 테스트 | 22 통과 | unittest22개, skip0, exit0 | official processor CPU 준비 포함; 실행 보고4.539초, CUDA 미초기화 |
| 8초 합성 원본 decode | 80프레임 | 10fps64×48 CPU MP4 | 생성 fixture; CCTV 성능 아님 |
| 같은 합성 표본/창 | 16개/4개 | 실제 원본 PTS,5초/2.5초/2fps | 창당10/10/6/1; 마지막1은 모델 생략 |
| 같은 합성 sampled buffer 최대 | 10장 | decoder stats | 모델 입력용 현재 창 stack 별도 |
| 합성 MP4 근거 duration | 3.5초 | 실제 출력 container duration;35프레임 | 요청0.5~1.5초+맥락2초를0~3.5초로 clip |

테스트 시간은 모델 처리 시간이나 GPU FPS가 아니다. CPU 테스트는 의도적 오류 후 partial result, unknown≠normal, 완료만으로 crossing 후보 생성 금지, 같은 행동 overlap 병합과 raw 유지, VFR/native PTS/분수FPS/누락 타임스탬프 실패, EOF/미래 프레임 누출, 안전 output·덮어쓰기 금지, queue-only CLI를 확인했다.

후속 검토에서 실제 pipeline이 쓴 top-level result.json의 정확한 bytes/SHA를 고정해 읽는 C4 reuse 회귀와 현재 창 token 진단 보존을 추가했다. official Qwen CPU processor에 pipeline이 생성한 분수FPS/VFR gap/홀수 EOF 표본을 직접 전달했고, 단일 표본 tail은 generation 없이 유보했다. 실제 가중치 로드·model.generate·CUDA 초기화가 없다. CPU fixture에서 baseline 성공 proof를 mock한 것은 실제 native baseline 성공 증거가 아니다.

총괄의 별도 **원본 CPU decode/window-only 감사**는 구현 통합 `d6bf473`에서 수행했다. native 입력·EOF·표본의 구조만 확인한 결과다.

| 소스 | decode 프레임 | 고유 표본 | 시간창 | 실제 EOF | sampled buffer 최대 | decode/window wallclock |
|---|---:|---:|---:|---|---:|---:|
| E01_007 | 4,171 | 279 | 56 | 확인 | 10 | 13.073512초 |
| E01_030 | 4,802 | 321 | 65 | 확인 | 10 | 19.880557초 |
| E01_013 | 3,781 | 253 | 51 | 확인 | 10 | 13.635824초 |

030의 마지막 단일 표본 창1개는 향후 실제 실행에서도 insufficient_data이며 정상 판정이 아니다. 세 영상 native source 끝은 각각139.033333/160.066667/126.033333초다. 이 감사에는 analyzer·모델·후보·행동 품질·근거 영상 저장이 없으므로 **원본 전체 모델 통합 성공은 미확인**이다. 공개 metrics 각 실제 값에는 로컬 원문 receipt의 상대 참조·SHA256·source pointer·검증 상태를 연결했다. raw PTS 목록과 receipt 본문은 로컬에 보존한다.

## 실제 원본 실행·행동 품질·비용

**resource_blocked / unstarted. 모델 job0·attempt0·실행 오류 retry0**. 원본 whole007/030/013의 모델 분석 EOF, Bfull/선택 ROI 차이, 창별 실제 raw/parse·표본 coverage, loading/preprocess/generation/save/file wallclock·CPU/GPU 메모리는 아직 측정하지 않았다. 새 모델 성능이나 실시간 검출 성공으로 표현하지 않는다. C4의 동일 입력 재사용은 성공한 B attempt와 원본/설정/창별 semantic input 해시 일치 후에만 허용하며 재사용 generation 시간은 null로 남긴다.

## 실패·한계와 남은 결정

준비 중 인터페이스 검토에서 익명 ID와 VFR 시간/실제 frame ordinal 분리 필요가 확인되어 전체 창 ID를 w000001로 통일하고 native PTS·ordinal·elapsed를 따로 보존했다. EOF의 가용 source time은 마지막 도착 PTS와 별개로 실제 frame coverage 끝까지 기다린 것으로 기록한다. raw/첫 후보는 즉시 flush하고 최종 병합/근거 저장은 나중 시각으로 구분한다.

총괄의 2026-10-28 10:55:17 UTC native 메시지 `msg_f11a79c3e683`는 새 GPU 관측이 free1,561MiB/utilization99%이며 동결 minimum free6,144MiB에 못 미친다고 보고하고 **bounded resource blocker를 수락**했다. 이 숫자는 총괄 관측이며 통합 담당이 재측정한 값이 아니다. 외부 GPU 작업을 중단하거나 큐를 우회하지 않았고 모델 job·attempt를 시작하지 않았다. CPU 구현 성공과 실제 모델 목표 미완료를 분리하여 worker_done outcome은 failed로 제출한다.

현재 구현은 고정 표본 사이의 짧은 동작을 놓칠 수 있고, 시간창 묶음은 사람 동일성 추적이 아니다. sampled RGB 메모리는 제한하지만 사건·측정 metadata는 창 개수에 따라 증가한다. CPU 기능 통과는 행동 품질·추론 실행 가능성·단일 GPU 자원 확보를 보장하지 않는다. 이번 dispatch는 자원 차단/미실행을 기록하고 멈춘다. 독립/총괄 최종 검토·기존 완료 등록·게시·실제 화면 확인은 총괄 소관이며 이 worker가 수행한 것으로 표현하지 않는다. 후속 모델 실행은 자동 예약하지 않으며 별도 총괄 작업 범위와 자원 GO를 따라야 한다.
