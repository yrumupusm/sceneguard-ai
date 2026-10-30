# EXP-0031 독립 검토

2026-10-30 KST. Task `task_5783e6670319` / Dispatch `ctx_5dbe5e128611`. Orca의 실제 Dispatch receipt에서 `gpt-6-astra`, effort `high`를 확인했다. **최종 판정: 실행·수치·자료 provenance와 제한된 결론은 `accepted_for_comparison`, 기본 적용은 `adoption_on_hold`다.** 미해결 실행·기록 blocker는 없다. 월장 전후 동일인 복원 개선은 입증되지 않았으며, 아래 정확한 최종 보고서/metrics bytes만 이 판정에 결속한다.

[실행 계약](../CODEX_EXP0031.md), AGENTS.md, 프로젝트 목표와 작업 계획을 기준으로 코드·수치·출처·주장만 독립 검토했다. 검토자는 CCTV 이미지를 클라우드에 올리거나 시각적으로 인물 정체를 판정하지 않았다. 로컬 디코딩·전처리 배열·해시 대조는 수행했지만 이를 독립 시각 검수로 표현하지 않는다. 총괄의 시각 초안과 사용자 확정 정답은 별개이며, 이 검토는 동일인·단일인 crop·오연결 여부를 새 정답으로 인증하지 않는다.

실행 전 원래 FCOS cache의 source SHA·native PTS·bbox·score와 ByteTrack 관측을 대조하고, 원래 tracklet·대표 선택·associations 전체를 정확히 재구성했다. 030은 480프레임/8 tracklet, 007은 1,710프레임/20 tracklet이다. 모든 기존 특징은 512차원이고 입력·설정·weight binding이 일치한다. 기존 5초 제한·0.65 외형 임계값과 나머지 LinkSettings는 그대로이며, 영역 파일은 실행 입력으로 읽지 않는다. 보호 검사에서 polygon 파일의 bytes만 해시하며 영역 효과 비교는 하지 않았다.

기존 대표는 1초 창에서 `score * sqrt(area)`를 사용한다. 대안은 2초 창과 geometry 경고 우선순위를 함께 바꾸는 묶음 비교다. 최대 3개 표본은 관측 개수 기준 시간순 bin에서 선택되므로 정확히 같은 시간 길이의 bin이라는 주장은 하지 않는다. 경고가 없다는 사실은 단일 인물 crop의 증거가 아니며, 박스 겹침·크기 변화 경고도 혼합 정답이 아니다.

타이밍 추가 diff에는 선택·연결 설정 변경이 없다. 검토자가 16개 합성 테스트와 CLI help를 실행했고, HEAD의 계측 전 runner와 현재 runner를 합성 입력으로 비교해 특징값·crop JPEG bytes·기존 counter가 같음을 확인했다. 새 hook은 입력 batch 크기만 기록하고 반환값으로 모델 입력을 바꾸지 않는다. 설치된 공식 ReID·AutoBackend·ONNXBackend 경로와 pinned SHA를 확인한 뒤 총괄에 한 번씩의 CPU 실행을 위한 GO 의견을 전달했다. 실제 실행 승인은 총괄이 별도로 내렸다.

| 실제 실행·비용 | 030 | 007 |
|---|---:|---:|
| 승인된 실제 실행 | 1 | 1 |
| 선택 endpoint 슬롯 / 고유 crop | 48 / 33 | 120 / 91 |
| 기존 특징 재사용 슬롯 / 고유 crop | 29 / 19 | 62 / 44 |
| 새 고유 crop / 실제 모델 forward | 14 / 14 | 47 / 47 |
| 알고리즘 accepted 연결, 기존 → 대안 | 0 → 0 | 1 → 2 |
| geometry 경고 없는 endpoint / 전체 | 13 / 16 | 31 / 40 |
| 전체 CLI wall seconds | 5.100877 | 7.966272 |
| 전체 자식 프로세스 CPU seconds | 6.493405 | 13.711619 |
| encoder 초기화 wall seconds | 1.939024 | 0.959934 |
| crop encoder 호출 wall seconds | 0.140050 | 0.355391 |

두 명령 모두 exit 0, 오류·재시도 0이다. 공식 CPU encoder는 `CPUExecutionProvider`만 사용했고 FP32/448×448, dynamic batch 설정을 유지했다. 관측된 61회 forward는 모두 batch 1이며 detector/tracker forward·GPU 추론은 0이다. 초기화 이후 hook count와 별개로, 검토한 생성자에는 warmup forward가 없고 추가 warmup도 없었다. 초기화 비용은 import·session 준비 등을 포함하며, crop 호출 비용은 디코딩·JPEG 쓰기를 제외한다. runner 내부 비교 시간은 최종 결과 쓰기 전에 끝나므로 위 전체 CLI 시간과 구분한다. CPU 시간에는 작업 thread가 포함돼 wall보다 클 수 있다. 실행 기록의 `RUSAGE_CHILDREN` peak RSS는 누적 자식 프로세스 high-water이므로 독립된 영상별 메모리 측정으로 사용하지 않는다.

재사용은 기존 특징을 다시 정규화한 벡터의 정확한 재사용이다. 원래 저장된 JSON vector bytes와 새 직렬화 bytes가 같다고 주장하지 않는다. 원래 특징 파일은 byte 단위로 보존된다. 검토자는 대안 대표·audit, 원래/대안 associations, 모든 paired/Q 유사도·결정과 raw ID 외형 경고를 저장 특징에서 다시 계산해 일치시켰다. 같은 crop key를 여러 endpoint가 사용할 때 특징도 정확히 같고, 새 crop·고유 재사용·슬롯 계수가 서로 일치한다.

Q01–Q03은 030, Q04–Q08은 007이다. Q01–Q05는 기존과 대안 모두 rejected이며 Q06/Q07은 5초 제한 밖이다. Q08은 같은 raw ID의 1.2초 공백 연결로 두 조건 모두 accepted이며 cosine은 0.712956 → 0.676284다. Q02는 0.305041 → 0.329985로 여전히 rejected다. Q01–Q08의 결정은 하나도 바뀌지 않았다. 007의 추가 accepted 한 쌍은 Q 범위 밖의 t0014→t0016이며 별도 A01로 검토 자료에 포함했다. 0.580951 → 0.678615라는 점수 변화와 accepted 증가만으로 올바른 동일인 연결 증가·오연결 없음·행동 성능을 입증할 수 없다.

원본 EXP-0029/0030과 입력·현행 설정 등을 포함한 보호 461파일의 SHA를 직접 다시 확인했다. 기존 canonical 큐의 jobs 45행·attempts 45행 모든 필드도 사전 snapshot과 같았다. 실행 freeze의 코드·설정·입력 SHA도 유지됐다. 검토자는 새 모델을 생성하거나 forward를 실행하지 않았고, 구현 수정·commit·push·등록을 하지 않았다.

비교 renderer는 설치된 공식 `ReID._crop_detections`와 `_crops_to_tensor`를 변환 전용으로 호출한다. gain 1.02/pad 10, BGR→RGB, FP32 `/255`, bilinear 448×448 및 `align_corners=False`를 사용한다. tight JPEG와 실제 encoder 전처리 재구성을 분리 표시하며, 재구성 PNG를 과거 추론 때 저장된 tensor라고 주장하지 않는다. 검토자가 9개 자료 테스트를 통과시켰고, 81개 asset을 정확한 native frame에서 로컬 재구성해 원본 BGR SHA·tensor SHA·input448 PNG pixels·expanded crop pixels를 모두 대조했다. 520개 산출 파일 SHA, 13개 사례의 특징 행렬·대표 순서도 일치한다. Q 8개, 새 accepted A01 1개, 사전 선택된 동시 관측 control 4개를 포함하며 총 26개 비교판이다.

control은 동시 관측되는 서로 다른 raw ID를 먼저 고른 검토 후보이며, raw ID가 다르다는 이유로 서로 다른 실제 사람 정답을 만들지 않는다. head 대표는 서로 다른 PTS일 수 있고 동시 원본 문맥은 따로 제공된다. 시간 중첩 때문에 원래 연결 후보가 될 수 없으므로 이들에서 연결이 없다는 사실은 ReID 오연결률 검증이 아니다. 자동 생성 수기 양식의 13사례는 모두 unknown이며 baseline/alternative 단일인 crop 의미와 endpoint 상세를 구분한다.

검토 증거는 로컬 `runtime/EXP-0031/independent-preflight.json`, `independent-instrumentation-equivalence.json`, `independent-output-audit.json`, `independent-material-audit.json`에 보존한다. 자료 manifest SHA256은 `8e9158b2ec67e396fbd10b3f428046444544d3d80eaa6edf4fd7018700c7fe5f`다. 이미지·좌표·특징·tensor는 공개 문서에 넣지 않는다.

추가 risk 부록은 원래 자료 manifest를 덮어쓰지 않고 별도로 저장됐다. 검토자는 표시된 156개 슬롯의 위험 값을 같은 고정 정책으로 다시 계산해 일치시켰다. Q02 새 대표 6개의 경고 없음, Q08 source 3개의 overlap 경고 및 target의 경고 없음도 숫자로 확인했다. 이와 별개인 총괄의 시각 의심/복수 인물 관찰을 geometry 정답으로 치환하지 않는다. 81개 tight PNG pixels도 원본에 결속된 확장 crop에서 다시 대조했고, 고유 native frame 수 78개를 확인했다. 해당 감사는 `independent-appendix-audit.json`에 별도 결속한다.

최종 [보고서](../experiments/EXP-0031-representative-quality-comparison.md)는 모든 Q 유사도·상태, A01의 0.580951→0.678615, 4개 control의 유사도, 실행/재사용/비용/보존/자료 계수를 실제 출력과 일치하게 기록한다. 총괄의 별도 수기 기록 13사례는 모두 `coordinator_visual_draft_not_user_ground_truth` 범위이며 사용자 정체 정답 생성은 false다. A01 연속 확인에 사용한 4개 native PTS와 당시 raw ID는 보존 tracking 기록에 일치한다. 검토자는 연속판의 장면 의미를 독립 시각 판정하지 않았다.

총괄은 A01을 일반 보행자의 제한적 동일인 연결 초안 1개, 새 명백한 오연결 관찰 0개, Q08을 기존 accepted이나 한 사람 대응 미확정 1개로 기록했다. Q01/Q03의 주된 인물이 같아 보인다는 초안과 미연결도 따로 남긴다. 이는 범위가 명시된 사례 기록이지 검증된 정체 정확도·오연결률이나 오류 부재의 보증이 아니다. Q02의 첫 의심 대표 유지, Q08의 복수 인물 crop, 가림/부분 박스와 월장 복원 미충족을 함께 남기며 기본 적용을 보류한 결론은 근거 수준에 맞는다. 수기 기록의 endpoint 상세 unknown은 별도 판정하지 않은 항목으로 보존한다.

공개 [metrics](../../records/EXP-0031/metrics.json) 14항목 모두 source SHA256·JSON pointer·값을 독립 대조해 정확히 일치했다. 초안의 프레임 수가 반복 측정 수로 읽힐 위험을 지적했고, 총괄이 최종 동결 전에 모든 항목을 `sample_n=1` 및 고정 영상 구간 실행 1회라는 `sampling_unit`으로 명확히 했다. 실제 실행은 영상별 1회이고 비용 값은 그 실행의 합계다. 표본 단위 정정은 실측값을 바꾸지 않았으며 수정 후 다시 대조했다. 이 범위를 벗어난 통계적 반복성·실시간 지연 주장은 검토하지 않았다.

실행 담당 로컬 보고서의 질문 수를 영상마다 4개라고 쓴 문장은 잘못이며, 실제는 030의 3개와 007의 5개, 총 8개다. 총괄이 원래 보고서를 보존하면서 `coordinator-errata.md`에 정정을 남겼고 최종 공개 보고서/실제 출력은 올바르다. 추가 실행이나 데이터 수정은 필요하지 않았다.

자료 담당의 별도 읽기 전용 검증 첫 호출은 `sceneguard` 모듈 검색 경로 오류로 import 단계에서 끝났다. 보존 로그와 import 순서를 확인했으며 디코딩·모델 forward 전 오류다. 경로를 보완한 검증 성공과 한 번 수행한 renderer/모델 실행을 구분한 최종 보고서 표현은 타당하다.

최종 보고서와 metrics는 아래 SHA256으로 동결한다. bytes가 바뀌면 이 검토를 그대로 재사용하지 않고 변경 부분과 결속을 다시 검토해야 한다. 로컬 `runtime/EXP-0031/independent-final-binding.json`에 이 문서 및 모든 독립 감사 receipt도 함께 결속한다. 웹 등록·실제 브라우저 표시·GitHub 확인은 총괄의 별도 전달 기록 대상이며, 이 검토가 이를 대신하거나 새 실험·모델·영역·임계값 변경을 승인하지 않는다.

| 최종 검토 대상 | SHA256 |
|---|---|
| `docs/experiments/EXP-0031-representative-quality-comparison.md` | `9e943f4c1ec31c4344d4b453ffae145170df5c4933124ada2d769382d1fc8d2a` |
| `records/EXP-0031/metrics.json` | `2efdc1c140004632c83beec5a6e07700ab8e4f3e60209b16d43ef88018d018ca` |
