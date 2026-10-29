# EXP-0029 독립 검토

2026-10-30 KST. Task `task_a02335239430` / Dispatch `ctx_b89d5ccb076d`. **최종 판정: 실제 실행·비교 기록은 `accepted_for_comparison`, 기본 적용은 `adoption_on_hold`다.**030은 수락 연결0이고007의 수락1개는 같은 raw ID의 분할 재결합이며, 넘기 전후 동일 인물 복원 성공은 입증되지 않았다. 최종 보고서/metrics는 마지막 표의 바이트에 한정해 검토한다.

[현재 사용자 범위](../CODEX_TRACKLET_LINKING.md), [사전 계획](../experiments/EXP-0029-tracklet-linking.md), [EXP-0028 사용자 검수](../experiments/EXP-0028-user-tracking-review.md), 프로젝트 목표·작업 계획과 연구/Orca/전달 ADR을 읽었다. 이전 배치의 추가 실행 금지는 이 새 승인 범위를 막지 않는다. 검토자는 소스 수정·모델 추론·GPU 작업·미디어 시각 검사/업로드·커밋을 하지 않았다. 실제 장면의 의미 해석은 총괄의 로컬 검수와 기존 사용자 관찰을 구분해 인용한다.

## 연결 코드와 표시 검토

runner는 원본 영상·캐시·tracking SHA 및 native PTS/time_base를 대조하고, 관측의 cache index로 원래 bbox/score를 검증한다. 예측·미확인 행을 tracklet·대표 crop·영역 판단에서 제외한다. raw ID는 보존하고 t 구간과 p 연결 ID를 별도로 붙인다. 시간 공백은 0초 초과~5초 이하이며 동시 구간을 연결하지 않는다. 같은 raw ID의 매끄러운 오연결과 동시 중복 박스는 이 방법으로 해결되지 않는다.

끝/시작 대표 특징의 cosine 중앙값, 시간·거리·크기 gate 및 외형 경쟁 margin을 사용한다. 모호한 연결을 유보하고 일대일 assignment에 미연결 대안을 둔다. 정답 사람/사건 시각이나 파일명 기반 정체 규칙은 입력하지 않는다. 임계값은 개발 설정이며 확률·정체 보증이 아니다.

같은 polygon·동일 영역 규칙을 연결 전 tracklet과 연결 후 chain에 모두 적용한다. 누락 시간을 dwell로 계산하지 않으며, bbox 내부 대리점이 실제 발·지면 좌표라는 주장도 없다. `confirmed_at`은 영상상의 확인 관측 시각이고 `available_after_pts`는 전체 입력 끝이다. 표시에는 원본 PTS, 원래 raw ID, t/p ID, 같은 영역의 두 후보 수와 오프라인 가용 시각을 넣는다. 앞 프레임의 p ID는 사후 표시다.

문서의 bare `.venv` 명령은 cv2 부재로41개 중3개 오류가 났다. 기존 EXP28 dependency overlay를 명시하면 원래41개가 모두 통과했다. H264/yuv420p·faststart·native-rate 표시, overwrite 거부 및 feature coverage 검증이 추가된 현재43개 테스트도 검토자가 독립 통과시켰다. 새 환경 설치나 모델 재추론은 하지 않았다.

feature binding은 원본/캐시/tracking/metadata·가중치·설정에 결속된다. 추가된 검증은 eligible 구간 및 head/tail key, 대표 수, 유한·비영벡터와 공통 차원을 확인한다. 추출 구현은 최초030 소스 사본과 실행 summary SHA, 설치된 encoder 호환성 기록으로 별도 보존한다.007에는 추출 구현 SHA와 실제 CPU provider/448/FP32 정보도 feature 파일에 기록했다. 표시 확대나 추가 계측으로 최초030 출력의 이력을 덮어쓰지 않았다. 이런 기술 검증은 실제 사람 대응 정답을 확인한 것이 아니다.

## 007 FCOS 확장 사전 검토

새 wrapper는 canonical queue의 상속 lock inode·실제 예약 상태와 live supervisor/child identity, Run/Task/Dispatch·commit·소스/설정/입력 hash를 확인한 뒤 모델을 import한다. 기존 free VRAM 6144 MiB gate를 유지한다. 기존 `run_cv.run`·FCOS/추적 구현을 변경하지 않고68–105초의1,110 실제 프레임을 처리한다. 기존 방식의 zero warmup10회는 실제 입력1,110회와 별도다.

원본600프레임 캐시를 byte prefix로 재사용하고1,110개 확장 행을 붙여1,710개를 만든다. native PTS는 step512/time_base1/15360이며 접합은1043968→1044480이다. tracking 출력은 이어붙이지 않고48초부터 새 연속 replay를 수행하며, 최초600행이 기존 strict/gap 각각과 정확히 같아야 완료된다. 원본·확장 입력이 처리 중 바뀌지 않았는지도 확인한다.

검토자가10개 확장 CPU 테스트를 독립 통과시켰다. 실제44 jobs/44 attempts의 복사본에서 schema migration 보존, 잘못된 권한/설정/입력 거부, 직접 실행 거부, native 중복·누락 거부, byte 보존과 연속 replay를 확인했다. 검토자는 canonical queue를 변경하지 않았다. 한 고정 job과 별도 검토된 실행 오류 retry 최대1회를 허용하며 자동 retry는 없다.

실제 freeze의 소스와 전체 입력 계약을 재계산해 일치했다. 사전 검토 receipt는 `runtime/EXP-0029/review-extension-preflight.json`이다.

| 사전 검토 결속 | SHA256 |
|---|---|
| 소스 집합 | `01be31017d5419c0152e5c2272db594f00a7f370c7a41a195b85441408edc166` |
| 입력 계약 | `53fe07cf68d37da182016825e727fa00fc397acdcbeb337db4a5ad087fa4a1aa` |
| freeze 파일 | `119127fca87d140d7cc760f2a04dff8e6c523459c52e23ee58a82b3760479be8` |

이는 한 고정 확장의 실행 준비 판정이며, GPU 실행·캐시 완성·행동 품질 판정이 아니다.

## 실제030 저장 출력 감사

원본/cache/tracking SHA,480프레임의 시각과700개 실측행 대응을 검증했다. 저장 특징만 사용해 tracklet·대표 선택·연결·동일 영역의 두 사건 출력을 다시 계산했고 모두 정확히 일치했다.8개 구간이 모두 eligible이며 대표40개/encoder 호출35회가 선택된 cache index와 일치한다. 각 대표 특징은512차원이다. 모델을 다시 실행하지 않았다.

시간 조건에 들어온12개 연결은 모두 cosine0.65 gate에서 거절됐고 값은0.203837–0.441206이다. accepted0/deferred0, 연결 전/후 영역 후보0/0이다. 따라서 이번 설정이 전후 동일 인물을 연결했다는 근거가 없다. 새 accepted 오연결0은 accepted 자체가0이라는 제한된 진술일 뿐, 기존 raw track 내부 오연결·중복이 없다는 뜻이 아니다.

원본/설정·산출물/실행 코드 hash와 재계산 결과는 `runtime/EXP-0029/review-030-outcomes.json`에 결속했다. 비교 MP4 hash는 summary와 일치한다. 검토자는 사람별 대응을 직접 시각 판정하지 않았으며, 총괄의 로컬 해석을 독립 정답으로 승격하지 않는다. 후보0을 접근/넘기 구분 성공으로 해석하지 않는다.

## 실제007 확장 및 보존 감사

canonical job `b2a97b5347504349920a599a08097247`, attempt `999f941ff0574fdd9f1c72ba5f7fb1c9`가 succeeded/exit0/attempt1이다. 실행 source/input hash는 위 사전 검토와 정확히 같다. 과거44 jobs/44 attempts의 모든 필드가 기존 snapshot과 같고 신규1 job/1 attempt만 추가됐으며 foreign key 오류가 없다. free VRAM은8335 MiB였다.

실제 새1,110행은68.000–104.966667초이며600개 원본 행과 이어진1,710프레임은48.000–104.966667초다. merged cache가 원본 bytes+확장 bytes와 정확히 같고, 정수 native PTS의 연속성을 직접 확인했다. 새 strict/gap replay의 각각 최초600행도 기존 EXP28 파일의 byte prefix와 정확히 같다. 두 replay의 전1,710프레임 관측을 cache index·bbox/score·native timing과 대조했다.

별도10회 zero warmup을 확인했다. 확장 post-warmup loop68.024866초는 모델 setup·preroll·warmup·최종 요약 등을 제외하며, wrapper83.891253초는 추론과 CPU merge/replay를 포함한다. 이를 실시간 추적 성능이나 두 구간 통합 추론 FPS로 바꾸지 않는다. `runtime/EXP-0029/review-extension-outcomes.json`에 실제 queue manifest·receipt SHA와 보존 근거를 결속했다.

구 EXP27 회귀 테스트의 실패를 별도로 재현했다. 실제 확장 전44행 DB의 읽기 전용 backup을 임시 디렉터리에 복사한 뒤 **수정하지 않은** `test_migration_copy_preserves_all_43_historical_jobs_attempts_and_finish`를 실행하면 `0 != 1`이 난다. 입력에 이미 EXP27 schema가 있어 idempotent migration이 새 backup을 만들지 않는데, 과거 테스트가 backup1개를 요구하기 때문이다. 이 테스트의 뒤쪽 finish/retry 부분은 그 assertion 이후여서 해당 실행에서 도달하지 않았다. 전체 회귀가 모두 통과했다고 보고하지 않는다. 검토자는 canonical DB·테스트 소스를 바꾸지 않았으며 `review-regression-qualification.json`에 재현 근거를 보존했다.

## 실제007 연결 수치 감사

저장된1,710프레임/3,471실측행을 기반으로20개 eligible 구간·대표 선택·특징·연결·두 영역 사건 출력을 다시 계산했다. 모든 결과가 저장 산출물과 정확히 같다.106개 고유 crop/104 encoder 호출,512차원 특징과 CPUExecutionProvider·448/FP32 기록을 확인했다. 검토자가 encoder를 재실행하지 않았다.

유일한 accepted 연결은 `t0007→t0008`이며 공백1.2초, cosine0.712956이다. 두 구간의 원래 raw ID는 모두9다. 이는1초 분할 조건으로 나뉜 기존 같은 숫자 구간을 외형 gate로 다시 연결한 제안이며, 다른 raw ID의 전후 사람 복원이나 울타리 통과 증거가 아니다. 나머지는 spatial gate13개·appearance gate15개 거절이고 deferred는0이다.

같은 영역 규칙의 연결 전/후 후보는 모두0이다. outside1,395/inside14/unknown2,062 관측을 독립 재계산했다.14 inside 관측은 t0006에만 있고 그 구간에 outside 관측이 없어 두 쪽 전이를 성립시키지 않는다.030은 outside285/inside0/unknown415다. 따라서 영역/박스 근거 부족을 연결 성공과 분리해야 하며,007 약56.7초 접근뿐 아니라 약66초 이후에도 후보가 없다는 한계를 함께 기록해야 한다. 저장 수치 감사는 `runtime/EXP-0029/review-007-outcomes.json`에 결속했다.

## 공개 보고서·측정값과 최종 판단

[최종 결과](../experiments/EXP-0029-results.md)의 수치와 사례 해석을 실제 저장 결과 및 [기존 사용자 검수](../experiments/EXP-0028-user-tracking-review.md), 총괄의 로컬 시각 관찰 메모와 대조했다. 총괄 메모는 검토자의 독립 시각 정답이 아니다.030 흰옷 인물의 누락 연결과007 기둥 뒤 재등장 대응은 관찰 출처와 불확실성을 유지한다.007 accepted 쌍은 두 사람이 겹친 crop이므로 단일 인물 정합성을 확정하지 않고, 기존 raw track 대상 이동 의심도 새 연결 단계의 오연결로 잘못 계수하지 않는다.

확장된 기존 gap 선 규칙은007에서70.133333초 후보1개를 내지만, 같은 영역의 연결 전/후 후보는0/0이다. 선 규칙과 polygon 규칙이 다른 비교를 ID 연결의 효과로 주장하지 않는다. 해당 기존 후보의 실제 몸 올림 대응은 총괄의 로컬 관찰이며 완료·정체 성공의 검증이 아니다. 접근 후보0과 실제 넘기 미출력을 함께 기록하고 일반화 정확도·오탐률을 만들지 않는 결론이 타당하다.

[공개 metrics](../../records/EXP-0029/metrics.json)의32항목 중28개는 source SHA·명시적 source pointer·값을 모두 독립 대조하여 정확히 일치했다. 메모리2항목의 bytes→MiB는 divisor1,048,576을 명시하고 변환값도 일치한다. 나머지 identity accuracy/IDF1/HOTA/physical crossing accuracy4개는 미측정 null이다. `runtime/EXP-0029/review-public-metrics.json`에 결속했다.

기존82개 보호 대상 파일과 EXP28 보고서·review·records8개도 보존 hash에 모두 일치한다(`review-preservation.json`). 실제 모델/소스/입력·원래ID/좌표·native 접합·같은 영역 control·오프라인 시각·기존 결과 보존 계약을 확인했고, **비교 기록을 막는 미해결 구현 blocker는 없다.** 검출 공백·부분/혼합 신체 박스·동시 중복·5초 제한·영역 coverage 및 사람 정체 불확실성은 남는다. 기술 실행 성공을 행동 성능이나 채택 성공으로 바꾸지 않는다.

웹 등록·브라우저 실제 재생/seek·GitHub 원격 확인은 총괄의 별도 [전달 기록](../experiments/EXP-0029-delivery.md) 대상이다. 검토자는 영상의 기술 hash와 renderer 계약을 확인했지만 실제 미디어를 시각 검사하거나 브라우저를 검증하지 않았다. 모델/GPU/학습·미디어 업로드·커밋은 수행하지 않았다. 이 검토는 추가 실험·튜닝·모델 교체를 승인하거나 예약하지 않는다.

최종 report/metrics 및 검토 receipt의 hash는 `runtime/EXP-0029/review-final-binding.json`에 보존한다. 보고서나 metrics가 바뀌면 이 결속을 그대로 재사용하지 않는다.

| 최종 검토 대상 | SHA256 |
|---|---|
| `docs/experiments/EXP-0029-results.md` | `35570b46bb4f13172631acc02ae484d22f09d51d74e71bd1af81f5e21b5dd177` |
| `records/EXP-0029/metrics.json` | `22329c20fa14147777ef65f61d55ce1b4ac60a4f21fdb9799c7091d0c0728baf` |
