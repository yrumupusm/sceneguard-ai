# MVP 1.0 실제 통합 결과 — 현재 실행 태그 MVP-0002

2026-11-01. `CODEX_MVP_FINALIZE.md` 승인 범위에서 원본과 검증된 FCOS 검출을 새 출력으로 처리했다. 현재 파이프라인의 `MVP-0002` 태그이며, 과거 동명의 계획/EXP13 기록을 대체하지 않는다. CPU 분석·재사용·등록 결과다. 기본 화면/브라우저/서비스 재시작의 최종 검증은 담당 웹 작업 및 릴리스 보고서와 구분한다.

## 실제 입력과 결과

|입력|원본 프레임|후보 → 사건|첫 의심|첫 확인|문 주변 관찰|의심/확인 알림 의도|
|---|---:|---:|---:|---:|---|---:|
|007 48–105초, 개발 회귀|1,710|18 → 1|55.633333|72.133333|74.566667초 종료, 확인 유지|1 / 1|
|030 84–100초, 개발 회귀|480|20 → 1|86.033333|92.733333|끝까지 open, 마지막 문 관측98.3초|1 / 1|
|007 84–104초, 기존 검수 일반 통행|600|0 → 0|없음|없음|새 사건 없음|0 / 0|
|007 45–48초, EXP37에서 이미 사용한 기술 검증 구간|90|0 → 0|없음|없음|새 사건 없음|0 / 0|

007/030의 새 판정이 완료된 뒤 EXP49를 **비교 기준으로만** 읽었다. 원래 후보 payload 전체의 다중집합, 모든 개별 근거의 자동 상태·시작/변경/확인/해제 시각, 사건별 주요 시각·상태·집계가 모두 일치했다. 세션/사건 ID는 새 요청으로 생성됐으며 과거 결과를 새 실행 입력에 넣지 않았다. 007 확인 근거2개·미결16개, 030 확인3개·미결17개를 유지한다. 사건 확인을 개별 미결 근거 전체에 전파하지 않는다.

두 정상/기술 구간은 검출0건이 아니다. 실제 박스는 각각8,354개/362개이며 후보0건이 정상 완료됐다. 84–104초의 기존 사용자 관찰을 재사용하며 정밀 사람 수나 새로운 독립 정답으로 확장하지 않는다. 45–48초는 원본과 byte 동일한 로컬 사본을 사용해 원본 손상 없이 소스 변경 거부도 확인했다.

## 고정 설정과 실행

기존 `.venv-cv-batch02`, FCOS COCO_V1 FP32/batch1/native30fps 캐시, 기존 ByteTrack을 사용했다. C3는 승인된007 inside scene과 EXP46 최종 C3 polygon, C6는 기존 scene과 EXP46 최종 C6 polygon이다. CPU 특징점의 seed scene은 EXP42와 같은 기존 base scene이며 `TransitionPolicy` 기본값을 바꾸지 않았다. 실제 프로필/설정 해시는 로컬 `runtime/MVP-0002/camera-profiles.local.json`에 있다. 카메라는 명시적으로 선택하며 파일명 예외가 없다.

실제 성공한 단일 분석·재사용·등록 명령 예:

```bash
.venv-cv-batch02/bin/python -m sceneguard.mvp_pipeline \
  --video data/TS_침입/E01_007.mp4 --camera C3 \
  --scene runtime/region-revisions/007-inside-20261101-v1/scene007.json \
  --portal runtime/portal-regions/exp0046/C3.json \
  --cache outputs/exp0029/cache007 --start 48 --end 105 \
  --output outputs/mvp-v1/007-acceptance-v2 \
  --register-config "$SCENEGUARD_LAB_CONFIG" \
  --registration-id mvp-v1-007-acceptance \
  --registration-python ../sceneguard-orca-lab/.venv-orca-lab/bin/python
```

030은 C6, `runtime/EXP-0034/scene030.json`, `runtime/portal-regions/exp0046/C6.json`, `outputs/cv_phase2d/cache030`,84–100초, `outputs/mvp-v1/030-acceptance-v2`다. 정상 구간은 같은 C3 설정/캐시로84–104초, `outputs/mvp-v1/007-normal84-104-v2`다. 추가 구간은 `runtime/MVP-0002/source-invalidation-copy007.mp4`, 기존 EXP37 캐시 `outputs/exp0037/detector/e852959a32d84224a96e795f16545233/cache`,45–48초, `outputs/mvp-v1/007-priorused45-48-v2`다. 네 등록 ID는 차례로 `mvp-v1-007-acceptance`, `mvp-v1-030-acceptance`, `mvp-v1-007-normal`, `mvp-v1-007-extra`이며 등록 시 외부 알림은 비활성이다.

## 실측 비용과 재실행

|입력|전체 경과초|전체 CPU초|이미지 경로 경과/CPU초|규칙 경과초|최종 근거 인코딩 경과초|
|---|---:|---:|---:|---:|---:|
|007 개발|222.768|516.074|118.814 / 403.796|6.683|44.652|
|030 개발|110.595|225.954|50.099 / 162.430|4.350|33.079|
|007 일반 통행|103.561|195.098|48.877 / 140.877|1.292|18.598|
|007 추가 기술 구간|20.855|31.851|9.880 / 20.785|0.046|5.190|

총 새 CPU 이미지 경로2,880프레임·새 추적2,880프레임이며 새 검출/GPU job/VLM/학습/외부 픽셀 전송은0이다. 실행은 일부 병행했고 기존 frontend 근거 인코딩도 포함하므로 합산 wall time이나 영상 길이 비율을 실시간 처리 성능으로 부르지 않는다. AMD Ryzen7 9800X3D, OpenCV5.0.0, OpenCV threads16에서 측정했으며 CPU초는 프로세스 누적 시간이다. `time -v`와 stage별 영수증도 로컬에 보존했다.

동일 CLI 재실행과 실제 등록에서 네 실행 모두 paths/decisions/media를 재사용하고 새 추적/이미지 경로/검출 프레임0을 보고했다. stage의 파일 해시와 binding을 검사했고 완료 manifest는 변경되지 않았다. 별도 사본의 한 바이트 변경은 stage 시작 전에 `Source/configuration/code changed; choose a new output directory`로 거부했으며 사본을 정확히 복구했다. 원본·과거 산출물·검토DB·알림 영수증은 초기화하지 않았다.

## 통합 수정과 검증

`mvp_pipeline.py`는 기존 replay 함수의0회 호출 수를 **규칙 단계**로 한정하고 현재 실행/원본 계보를 표시한다. 새 CPU 계산을 flow0으로 오인하지 않도록 실제 프레임·CPU 비용을 기록한다. 최종 캐시 변조 검사, 서비스 전용 Python을 통한 명시적 등록 CLI 옵션을 추가했다. 방향/소실/영역/관측·사건 임계값은 변경하지 않았다.

`tests.test_mvp_pipeline`46개와 `tests.test_video_cards`19개, 총65개가 통과했다. 실제 RuleBackend의 검출0건, 기본 후보0건+문 후보있음, 관찰 종료≠해제, 영상 끝에서 가짜 종료 없음, 재실행/소스 변경 거부와 캐시 변경 시 완료 manifest 발행 거부를 포함한다. 합성 규칙 시험은 영상 정확도 평가와 별개다.

첫 실제007 v1은 기존 CV 환경에 `lap`이 없어 추적 전 실패했다. `requirements-tracking.txt`에 이미 고정된 `lap0.5.12`, `cython-bbox0.1.5`, `Cython3.3.0`을 같은 환경에 설치하고 성공한 v2를 새 출력으로 분리했다. 실패 상태/로그도 보존했다. 첫 병합 시험 실행에서 가짜 모듈의 package attribute가 이미 import된 실제 모듈과 충돌한 시험 격리 결함을 수정한 뒤65개를 다시 통과했다. 알고리즘 fallback은 없다.

## 제한과 증거

실제 바깥 이탈에 의한 의심 해제 사례는0건이며 **실제 해제 성능은 null/미검증**이다. 정상 통행 무경보와 관찰 종료를 해제 성공으로 세지 않는다. 사용하지 않은 같은 카메라 구간은 보유 호환 캐시에서 찾지 못했다. 전체007 캐시는 다른 SSD 모델이어서 거부했고006은 native30fps 지원 조건을 충족하지 않았다. 독립 구간을 채우기 위한 새 검출은 수행하지 않았다. 정확도/F1/일반화/실시간·외부 경보 전달은 검증하지 않았다.

공개 집계는 [metrics.json](../../records/MVP-0002/metrics.json)이다. 원시 영상·좌표·관측은 Git 제외이며 로컬 증거는 `runtime/MVP-0002/execution-summary.json`, `exp49-comparison.json`, `source-invalidation-receipt.json`, `*-initial-status.json`, `*-resume-register.stdout.json` 및 각 출력 stage 영수증에 있다. 브라우저/기본 보기/재시작·수동 검토 유지의 완료 여부는 별도 최종 릴리스·독립 검토를 따른다.
