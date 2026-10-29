# BATCH-0004 전달 기록

2026-10-29 KST. [사용자 승인 계획](BATCH-0004-yolo26-pose-recovery-plan.md)에 따른 EXP-0022 기록이다. 실제 추론, 관절 품질, 행동 해석, 웹 등록과 GitHub 게시를 별도로 확인한다.

## 시작 상태와 역할

main `e0840a2`의 clean 상태를 확인하고 `73e2b733f668c681f1844444ed50f0cdc2968897`까지 fast-forward했다. reset/stash/강제 덮어쓰기를 하지 않았다. 기존 BATCH-0003의 두 실패와 267개 입력·가중치·환경을 보존하며 신규 결과만 별도 경로에 둔다.

기존 Run `run_3d23462a014a`와 canonical GPU 큐를 재사용한다. Sol 담당 Task `task_5df19346a61c` / Dispatch `ctx_9a8df3d90186`의 실효 모델은 `gpt-6.1-sol/high`, 독립 검토 Task `task_656ab1d8e0c9` / Dispatch `ctx_633012716c3a`는 `gpt-6-astra/high`다. native launch receipt와 live provider 상태로 확인했다. 총괄을 추가하지 않았다.

EXP-0022를 기존 담당2 카드에 배정했다. 실제 브라우저에서 `진행 중`, `결과가 아직 등록되지 않았습니다`, 실효 Sol/high 표시를 확인했다. 이는 추론 성공을 뜻하지 않는다. 초기 GPU 여유는7671MiB였으며 실행 직전 기존6144MiB 기준을 다시 확인한다.

## 실행 전 판정 기준

공식 public `YOLO.predict` 경로의 전체 인자와 설치 버전을 CPU에서 확인하고, 코드·입력을 고정해 독립 검토한 뒤 두 native frame만 먼저 실행한다. 공식 predictor의 fuse/첫 warmup은 기존 실패 경로와 다르게 기록한다. 정상0명 반환은 기술 오류로 재시도하지 않는다.

두 이미지에서 실제 인물과 손목·엉덩이·무릎·발목의 대응이 확인돼야 remaining265로 확대한다. 픽셀·관절 원시값을 클라우드 에이전트에 보내지 않으며, 필요한 사람 확인은 두 로컬 비교 이미지로 묶어 요청한다. 신뢰도·관절 개수만으로 이 품질 조건을 통과시키지 않는다.

원본·오버레이·원시 좌표·가중치·환경·DB·로그·receipt는 로컬 전용이다. 다음은 실제 확인된 결과다.

## 고정 소스와 실제 smoke

코드·계약·배정은 `7c281e34bc12bd9b53f7cebe73f313f801f870e2`에 commit/push했다. 실행 의존15개 파일의 Git 객체·현재 bytes·readiness hash 일치를 확인했고, 구현16+기존 queue14의30 CPU 검사가 통과했다. 독립 검토는 별도15 검사와 핵심 회귀3개를 수행했다. 중복되는 테스트를 합산한 성능 숫자는 만들지 않는다.

실행 전 실제 public kwargs 전체와 downstream signature를 확인했다. 계측기가 decorated 함수의 공통 wrapper를 메서드로 잘못 식별할 수 있던 문제도 `inspect.unwrap` 및 예외/정상 반환 회귀 검사로 수정했다. 기존 inference 소스나 실패 결과를 덮어쓰지 않았다. exact-source 사전 검토 PASS 후 총괄은 smoke2만 허가했다.

기존 canonical queue의 job `c99e0da0610348e7a74bf38d66d19801`, attempt `6509c805b40e4d7a8137f770cfa04a05`가 **succeeded**다. 실행 전 free7864MiB, 정상 public Results2개·sample forward2회·warmup forward1회, 오류0/retry0이다. 실제 summary SHA256은 `84905e3841a7394f0e3a0e214f7298746f33226fdaa3fafb703c3ded40cf5cde`다. 원래39 jobs/39 attempts와 protected historical files의 보존, 고정267입력/환경, 실제12artifact 해시를 검증했다.

030:90은 정상 empty Results(사람/관절0),007:64는2행/관절 추정23개다. 두 비교 PNG는 실제 반환에서 생성했다. 030은 기존 사용자 관찰에 사람이 있지만 관절 근거가 없으므로 remaining265는 enqueue하지 않았다. 007의 새 위치 검수만 두 로컬 자료를 묶어 한 번 요청했고, 답변 전에는 미확정으로 유지한다. 이 질문은 추가 실행 승인이 아니며,007이 양호해도030의 누락을 해결하지 않는다. 규칙·추적·추가 모델/학습·추론은 없다.

## 독립 결과 검토·등록

독립 Astra는 실제 smoke/계측/보존 및27개 metric pointer(22실측·5null)를 확인했다. **기술 실행과 제한된 해석에 PASS**이며,007의 실제 관절 품질이나 행동 성능의 PASS가 아니다. 최종 공개 자료에 실제 로컬 절대 경로·raw 좌표·미디어·weights가 없음을 검토했다. 최종 검토 SHA256은 `66eb0d7422fb587eb55b162685c3fb0411d9ef9993f8df3188ccff630dd501a9`다.

검토는 report `d7a988aafae7b14a184b128ef1f240d85944a4f48ec31d0ecb04257b4347ae3f`, metrics `c75ef5f7ebca3698e1ec37601492a808daffe4956dc08ad447733b2e91f29e71`, 총괄 요약 `d6d2fe9983a98d10f3b018d897ea8ca378c9b72afc13daa470cf64f777919b20`에 묶였다. 실제 완료 메시지를 수용한 두 worker는 succeeded로 정리하고 native worker-release로 해당 터미널만 해제했다. 새 총괄/큐/worker를 추가하지 않았다.

기존 COMPLETE_CLI로 EXP-0022 담당2에 `succeeded / accepted_for_comparison / adoption_on_hold`를 등록했다. 실행 성공과 관절 품질/행동 보류가 함께 보이도록 작성했다. binding SHA256은 `8093870e8b312027ebebc6104e183784b7f4092b415a26b1657c4629b9d3d14b`다.

## 실제 로컬 화면 확인

2026-10-29 04:52 UTC에 기존 loopback 결과 화면에서 EXP-0022의 실제 보고서/독립 검토를 펼치고27개 측정 항목·기존 그래프2개·두 comparison PNG의 decode와 render를 확인했다. 두 PNG 모두3840×1120이며 polling 후 이미지 요소가 유지됐다. 서비스가 읽는 report/metrics/review/binding bytes는 위 해시와 일치했다.

이미지 artifact ID는 `exp0022-030-090-pose-comparison`, `exp0022-007-064-pose-comparison`이다. 각각의 HTTP 응답 bytes가 실제 로컬 PNG SHA256 `9a2d55712a117fbf68ebef3a72bde23d1a5ce9b85505c7df3619f9441e11bf11`, `618ca08af41083b5085ce5a8b4262675eaf8f127f457cb88f853ea04bf4eff06`와 같았다. 픽셀을 클라우드에 전송하거나 시각 품질을 확인한 것으로 간주하지 않는다.

영상 없는2프레임 결과이므로 **영상 재생/seek는 해당 없음**이다. 검증을 통과하려고 가짜 영상을 만들지 않았다. 기존 영상용 검증 함수 대신 로컬의 이미지 decode/render 검사로 확인했고 웹 기능/디자인은 변경하지 않았다. 서비스 JS SHA256은 기존 `cae122f859102f7a6f0dd3255d9e4a7ec5491814f340dc9a4e28fff6ba8b9fcd`와 같다. 실제 증거는 로컬 `runtime/BATCH-0004/delivery/browser-images.json`에 남긴다.

GitHub 최종 결과 게시와 원격 byte 확인은 로컬 화면 확인과 별도로 수행해 후속 기록한다.
