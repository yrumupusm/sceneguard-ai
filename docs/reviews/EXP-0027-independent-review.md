# EXP-0027 독립 검토

2026-10-29. 검토 Task `task_63595596a963` / Dispatch `ctx_d7395a014f84`. 최종 상태는 **기술 실행·진단 기록 검토 통과(`accepted_for_comparison`), 실제 인물 대응·라벨 의미 검수 미완료·기본 적용 보류(`adoption_on_hold`)**다. 기술 실행 성공과 사람별 시각 검수·채택 판단은 구별한다. 아래 대기 문장은 각 검토 시점의 이력이다.

## 범위와 초기 판단

[EXP-0027 계획](../experiments/EXP-0027-detection-low-confidence-diagnosis-plan.md), AGENTS, 프로젝트 목표·작업 계획·관련 ADR, [EXP-0026 결과](../experiments/EXP-0026-exploratory-person-finetune.md)와 기존 Detection 구현을 읽었다. 이번 진단은 기존 pretrained Detection과 고정 EXP-0026 best 각각에 대해 기존 native RGB/crop 7개를 재사용하고, 공식 predict의 `conf`만 0.25에서 0.05로 변경하는 최대14회다. 기존0.25 Results·라벨·가중치·환경·기본값을 보존한다. 이전 학습 종료 지시는 이 구체적 신규 진단 승인과 구별한다.

계획 자체에서 실행을 막는 모순은 발견하지 않았다. 다만 실제 실행 전에 새 소스·CPU 테스트·고정 입력/환경/체크포인트 SHA·commit·현재 담당 authorization·canonical queue lease/VRAM gate를 확인해야 한다. 정상 empty는 재시도 사유가 아니며 자동 재시도·추가 sweep·학습·새 프레임 디코딩은 범위 밖이다.

## 설치 API 독립 확인

검토 대상은 보존된 Ultralytics 8.4.192 설치 소스의 `Detect.postprocess/get_topk_index`, `DetectionPredictor.postprocess`, `non_max_suppression`이다. 설치된 함수의 AST를 그대로 추출하여 합성 CPU tensor로 실행했고 모델 생성·GPU 초기화는 하지 않았다. 파일 SHA와 검사 결과는 로컬 `review-installed-api.json`에 보관한다.

- end-to-end head는 먼저 anchor의 최대 class 점수로 top-k를 고르고, 남은 anchor/class 점수에서 다시 top-k를 고른다. 이 과정은 후속 person0 필터보다 먼저 일어난다. pretrained80과 best1 head의 후보 경쟁 조건이 같다고 가정하지 않는다.
- 최종 end-to-end 분기는 `score > conf`의 **엄격 비교**와 class mask를 적용한 뒤 기존 순서의 첫 `max_det`개를 반환한다. 이 분기는 일반 IoU NMS를 실행하지 않는다. 공식 warmup의 별도 처리까지 NMS 호출0으로 확대하지 않는다.
- 계획대로 새 출력에서 `>=0.25`를 선택하면 정확히0.25인 행은 기존 strict `>0.25` 결과와 달라질 수 있다. 합성 경계값으로 이를 확인했다. 경계값·위치·점수·행 순서·허용오차 비교를 별도 기록하고 실제 불일치를 수정해서 맞추지 않아야 한다.
- 0.05 Results는 head top-k와 confidence/class 필터를 거친 최종 출력이다. 빈 결과는 모든 내부 person 반응의 부재를 입증하지 않는다. 낮은 점수 박스의 증가도 실제 사람 복원·TP·recall·accuracy의 증거가 아니다.

## 라벨 의미와 남은 검토

113개 기존 패널은 사람 검수 자료다. people-jump-fence8행과 person polygon19행은 우선 목록을 만들되 중복 패널을 합산하지 않아야 한다. 사람 단위·신체 범위·누락 인물·C6 구도 유사성·변환 적합성은 모두 unknown/review_pending으로 유지한다. 독립 검토자의 주석 형식 의견은 시각 GT가 아니며 D0 통과나 학습 데이터 정답 확정으로 바꾸지 않는다.

검토자는 실행 코드·데이터를 수정하거나 GPU·모델 다운로드·미디어 업로드·커밋을 수행하지 않는다. 최종 결과의14회 계수·warmup·비용·기존0.25 대응·raw 해시·공개 집계·보고서의 정확한 바이트 결속은 후속 검토 대상이다.

## CPU 소스 사전 검토 — PASS

새 `exp27_detect` 경로와 전용 command·manifest·기존 queue의 추가 등록 diff를 검토했다. 기존 Detection runner를 재실행하지 않고 새 job key·출력 경로를 사용한다. 소스/입력/현재 담당/commit/승인 확인, canonical lock descriptor의 실제 inode·잠금과 살아 있는 부모·자식 identity, attempt1 한정·retry 거부, 실행 전6144MiB gate와 offline transport 차단이 유지된다. 각 조건의 시작 marker는 배타 생성하며 부분 실패 뒤 같은 조건을 다시 시작하지 않는다. 고정2모델×7입력 순서와 종료 시14 sample forward/별도2 warmup 검사를 확인했다.

검토자가 EXP-0027 CPU15개·기존 queue14개·EXP-0026 회귀10개, 총39개를 독립 실행해 모두 통과했다. 최초 검사에서 장치 기대값을 정수0으로 쓴 테스트1개가 실패했고, 이전 kwargs의 `cuda:0`을 유지하도록 **테스트 기대값만 수정**한 뒤 재검사했다. strict confidence·class mask·head top-k 합성 시험도 포함한다. 재검사 중 실행 소스 바이트는 같았으며 실패 기록도 보존했다.

기존7개 native PTS·RGB/crop 파일과 실제 crop 픽셀·체크포인트 SHA·14개 과거 native Results SHA를 읽기 전용 대조했다. 과거 Results를 CPU로 다시 파싱해 local/full offset1회 좌표와 summary의 행 순서·계수가 일치했다. 모델 파일을 CPU로만 읽어 pretrained80/best1 및 person0을 확인했다. 두 저장 checkpoint의 FP16은 실행 FP32와 구별한다. serialized pretrained head의 end2end 값은 false지만 공식 predictor가 `nms=False`에서 end2end를 fuse 전에 선택하는 경로이며, 실제 backend의 FP32/end2end/nc는 runner가 다시 확인한다. 검토 과정의 새 forward와 CUDA 초기화는0이다.

라벨 감사의113개 패널·354개 사람 행은 모든 의미 필드가 unknown/unclear이고 review_pending이다. class1 8행은3개 패널, person polygon19행은12개 패널이며 서로 겹치지 않아 우선순위는27행/15개 고유 패널이다. 원본 ZIP 및 준비 사본 전체1108파일을 독립 재해시해 보존을 확인했다. 이는 형식·provenance 의견이며 시각 GT나 D0 통과가 아니다.

**검토한 소스 바이트에 대한 CPU preflight PASS**다. source digest는 `6cc2e1f9facccacc9ed4b55f57ccfd3c17b6837068ccdbb48cac1a0470c41e52`, input contract digest는 `4653a95ef86e3a15b40a11523b891d8aa017a2642c82f8f02f3f108e7e2f6621`이다. 상세 결속은 로컬 `review-preflight.json`에 남겼다. 총괄이 같은 바이트를 commit·현재 authorization에 결속한 뒤 실제 lease/VRAM gate를 통과해야 하며, 이 PASS는 실행 결과·사람 복원·채택 판정이 아니다. 최종 결과 검토까지 작업을 유지한다.

후속으로 commit `f8360446b68a8807a4b07a7f8dad1c9b52ec7330`의41개 실행 소스 바이트가 사전 검토 목록과 모두 일치함을 확인했다. input digest도 동일하다. `review-execution-binding.json`에 해당 commit과 사전 receipt SHA를 결속했으며, 실행 시 승인·lease·VRAM gate는 그대로 필요하다.

## 실제 결과 독립 감사

canonical job `3eda4fd66f9c4fed9ef98997436362cb` / attempt `111e49f413a4446586e629cd65419721`의 성공·exit0·attempt1을 읽기 전용 queue에서 확인했다. 현재 담당과 사전 고정 commit/source/input/config 해시가 summary 및 queue와 일치한다. 실제 시작 free VRAM8622MiB, 두 모델 직전8622/8301MiB는6144MiB gate를 충족했다. 기존43개 jobs/attempts 전체 행은 그대로이고 신규1개씩만 추가됐다.

14개 native Results를 CPU에서 다시 읽어 유한 Nx6·person0·점수 범위·모든 행의 local/full 좌표와 offset1회·3개 bin을 독립 계산했다. 14개 시작 marker, 공식 profiler의 sample 시도/완료14회와 별도 warmup 시도/완료2회, 모델 load2회, retry0이 서로 일치한다. 각 실제 입력 tensor는 CUDA0/FP32/1×3×640×640이고 저장 hash가 일치하며, 같은 프레임의 두 모델 입력 tensor SHA도 같았다. 공식 backend FP32/end2end·head80/1·max_det300·고정 kwargs를 실제 기록에서 확인했다.

새0.05 출력의 `>=0.25` 부분은 **14조건 모두** 기존 raw Results와 박스·점수·class·행 순서가 정확히 일치했다. 허용오차 내 일치도14/14지만 정확 일치와 별도 판정했다. 정확히0.25인 경계 행은0개였고, 이를 맞추기 위한 정렬·재매칭·값 보정은 없다. 빈 조건의 일치는 새 검출 성공을 뜻하지 않는다.

| 고정 프레임 | pretrained0.05 출력 | best0.05 출력 |
|---|---:|---:|
| 03084초 | 5 | 4 |
| 03090초 | 6 | 1 |
| 03094초 | 0 | 0 |
| 03050초 | 2 | 2 |
| 03055초 | 2 | 2 |
| 00747.5초 | 0 | 0 |
| 00752.5초 | 2 | 2 |

90초 pretrained6행은 `[0.05,0.10)`3행과 `[0.10,0.25)`3행, best1행은 `[0.10,0.25)`이다. 이는 기존0.25 최종 Results에 없던 낮은 점수 출력이 존재한다는 근거다. **실제3명 복원·TP·중복 없는 사람 수·recall 개선을 확인한 것이 아니다.** 94초는 양쪽 모두0행이며 head top-k 이전의 모든 내부 반응 부재를 입증하지 않는다. 라벨 의미·도메인·학습 효과 중 특정 원인을 이 결과만으로 확정할 수 없다.

runner 전체27.240초, pretrained 단계1.408초/best 단계0.865초, PyTorch peak allocated191.832MiB/reserved212MiB를 원시값과 대조했다. 장치 전체105개 표본의 최대 사용1943MiB·최소 여유8111MiB이며 표본 오류0이다. 단계 시간은 profiler·동기화·첫 setup/warmup·결과 저장/과거 캐시 비교 영향을 포함하므로 연속 CCTV FPS나 fine-tuning의 속도 개선으로 해석하지 않는다.

7개 triptych와 단일 모델/원본 패널을 포함한28개 PNG의 hash·크기·파일 무결성을 확인했다. **이미지 내용이나 실제 사람 대응은 시각 판정하지 않았다.** 기존443파일 보존 snapshot 중438개가 그대로이며 바뀐5개는 승인 이력 문서3개·queue 추가 등록·assignment다. 기존 라벨/입력/가중치/실험 원시 자료 변경은 없다. 로컬 `review-outcome-audit.json`은 모든 새 산출물 SHA와 원시 summary SHA `68d3bc88789fdfb17c2669a6951e353128c89dca73d753f7254bf7916e5c548b`를 결속한다.

## 최종 보고서·공개 측정값 판단

[최종 보고서](../experiments/EXP-0027-detection-low-confidence-diagnosis.md)의14개 표 행에 대해 전체/bin 계수·소수6자리 최대 점수·과거 캐시 일치 표시를 원시 summary와 대조했다. [공개 측정값](../../records/EXP-0027/metrics.json)69개는 값과 출처 SHA가 모두 일치한다. 정확도·person recall·행동 F1은 null이며,7장 개발 자료를 독립 검증이나 사람별 TP로 바꾼 주장은 없다. 개인정보 이미지·raw 예측 좌표 배열·tensor·가중치·runtime는 공개 측정값에 들어 있지 않으며 Git 추적 대상에도 없다.

90초 낮은 점수 출력의 존재,94초 최종 출력0,라벨 전체 검수 대기,기본 채택 보류를 구분한 보고서 결론이 타당하다. 실제 사람 대응 확인을 다음 사람 검수로 남기는 권고를 수용한다. 미검수 라벨·도메인 차이·head class 경쟁 중 어느 하나를 인과적 원인으로 확정하지 않는다. 사용자 신규 이미지 답변은 이 검토 시점까지 미수신이며, 독립 검토자의 형식/provenance 의견이 시각 GT를 대신하지 않는다.

**최종 판정: `accepted_for_comparison` / `adoption_on_hold`.** 미해결 구현 blocker는 없다. 검토자는 GPU 추론·학습·새 모델 다운로드·미디어 업로드·커밋을 실행하지 않았다. 웹 완료 등록·실제 로컬 렌더와 GitHub 게시 확인은 총괄의 별도 전달 절차이며 이 검토가 그 완료를 주장하지 않는다. 추가 GPU 실행·임계값 탐색·학습·모델 기본 변경을 승인하거나 예약하지 않는다.

## 최종 바이트 결속

이후 보고서나 측정값이 바뀌면 아래 결속을 그대로 재사용하지 않는다. 검토 문서 자체와 로컬 감사 receipt의 hash는 `review-final-binding.json`에 보관한다.

| 검토 산출물 | SHA256 |
|---|---|
| 최종 진단 보고서 | `242718f4862ac9375615370179d9c8301048fb891460577f13f78190288a0cca` |
| 공개 측정값69개 | `56330c93b7476ad1b69ebb49c334afd5d865edb46db17ffe7757d42c7afcaf35` |
| 라벨 감사 보고서 | `a40d26ff50450bbc3d2cd53a6549fcb4880757234604b7dfca1ada5abdd9b6f2` |
| 실제 실행 summary(로컬) | `68d3bc88789fdfb17c2669a6951e353128c89dca73d753f7254bf7916e5c548b` |

로컬 근거는 `review-installed-api.json`, `review-fixed-inputs.json`, `review-weights-caches.json`, `review-cpu-tests.json`, `review-cpu-recheck.json`, `review-historical-regression.json`, `review-label-audit.json`, `review-preflight.json`, `review-execution-binding.json`, `review-outcome-audit.json`, `review-public-artifacts.json`에 보존했다. 초기 CPU 실패와 사전 승인 receipt를 최종 결과로 덮어쓰지 않았다.
