# EXP-0028 독립 검토

2026-10-30 KST. Task `task_869138bf556d` / Dispatch `ctx_e77401504991`. **최종 판정: 실제 strict/gap·조건부 ReID 실행 및 비교 기록은 `accepted_for_comparison`, 기본 적용은 `adoption_on_hold`다.** 030의 핵심 전후 ID 단절과007 접근 후보 재발이 남으며 실제 인물 대응·물리 통과는 미확정이다. 아래 사전 검토·대기 문장은 각 단계의 이력이며, 최종 바이트 결속은 마지막 표를 따른다.

AGENTS, [현재 지시](../CODEX_PRACTICAL_TRACKING.md), [EXP-0028 계획](../experiments/EXP-0028-practical-tracking.md), 프로젝트 목표·작업 계획·추적 ADR과 [EXP-0005 집중 검수](../experiments/EXP-0005-candidate-focus-review.md), [EXP-0006](../experiments/EXP-0006-candidate-box-consistency.md)를 읽었다. 검토자는 소스 수정·GPU 실행·원시 미디어 업로드·커밋을 하지 않는다. 검토용 코드·receipt는 로컬 `runtime/EXP-0028/review*`에 둔다.

## strict/gap 코드와 실제 출력

기존 ByteAdapter는 cache index에 대응하는 실제 bbox를 관측으로 내보내며 Kalman 좌표는 별도 필드다. confirmed 관측만 경계 입력으로 사용하고 예측 행에는 bbox가 없다. GapTolerantBoundary는 ID별 실제 관측의 마지막 시점으로 메모리를 만료하며, 예측·미확인 관측은 TTL이나 dwell을 늘리지 않는다. 관측 누락 뒤 첫 재관측 간격은 dwell에 포함하지 않고 다음 연속 관측부터 합산한다. 기존 쪽의 상태·ROI/유한선 검사는 유지하되 dwell .2초·최소3회·양방향 cooldown2초·90프레임 tracker buffer를 함께 적용한다. 이는 구성 비교이며 3초 메모리 단독 효과가 아니다.

검토자가 기존 gap 합성 테스트27개를 독립 실행하여 통과했다. 실제 저장 결과1080프레임을 별도 감사하여 strict의 모든 frames 객체·재관측 목록이 과거 EXP-0005 C와 정확히 같고, events도 condition 이름만 제외하면 정확히 같음을 확인했다. strict/gap의 모든 관측 bbox·점수는 cache_index로 원본 캐시와 정확히 일치한다. 원본 native PTS/time_base와 실수 PTS도 일치하며, 저장된 실제 관측만으로 경계 코드를 재생한 후보가 모든 저장 이벤트와 정확히 일치한다. 이 검사는 새 detector 추론이나 새 tracker 비교 실행이 아니다.

| 구간 | strict→gap 실제 관측 행 | 관측 ID | 재관측 | 후보 | gap 연결 후보 |
|---|---:|---:|---:|---:|---:|
| 030, 480프레임 | 700→700 | 8→8 | 12→12 | 2→2 | 0 |
| 007, 600프레임 | 1252→1279 | 9→9 | 8→11 | 2→0 | 0 |

030은480프레임 모두 관측 객체까지 strict/gap이 같으며 예측 행만333→775로 증가했다. #3/#4 후보 emission은 strict90.3초에서 gap90.4/90.666667초로 늦어졌다. 두 후보 모두 실제 연속 관측으로 확인되며 gap을 넘겨 발생한 후보가 아니다. 007은364/600프레임의 관측 객체가 같고 예측 행246→634, #9의 관측3→51과 #8의313→292처럼 연결 배분도 바뀐다. 관측 증가27행은 신규 실제 인물27명이나 정확한 재연결27건이 아니다.

## 의미·해석의 제한

이전 집중 검수에서007은 접근·서기 중 박스의 상체→긴 신체 범위 변화가 주요 설명이었고,030은 실제 상승 동작과 박스 범위 변화가 섞였다. 이전 검수는 전 구간의 확정 인물 ID 정답이 아니다. EXP-0006의 추가 일관성 검사는 네 후보 모두 유보/근거 부족으로 만들어 기본 적용되지 않았다. 새 gap 규칙에는 신체 범위 식별이나 이 일관성 검사가 추가되지 않았다.

따라서007 후보2→0을 이번 국소 기존 후보 억제로 보고할 수 있지만 오탐률 개선·정상 판별 성능으로 확대하지 않는다. 030의 두 후보도 사람별 물리 통과 성공2건이 아니다. 실제 전후 ID 단절은 tracker 식별자 단절과 같은 사람의 정답 대응을 구별해야 하며, 예측 ID 유지가 관측 복원이나 신원 확인을 뜻하지 않는다. 현재 gap 출력에서 gap 연결 후보는0이므로 누락 중 통과 복원 성공을 주장할 근거가 없다.

실제 캐시 감사는 로컬 `review-actual-replay.json`에 원본·산출물 SHA 및 재계산 근거를 결속했다. 원시 미디어 내용을 모델 도구로 열거나 새 의미 시각 검수를 수행하지 않았다. 연속 비교 영상의 기술 검증·사람의 실제 대응 검수·보고서 결론·웹 전달은 각각 별도 확인한다.

## 조건부 ReID 사전 검토 — PASS

총괄은 실제 strict/gap 연결 단절 근거로 사용자 승인에 포함된 한 개 ReID 구성을 활성화했다. 검토 대상은 기존 Ultralytics8.4.192의 BOTSORT와 공식 `yolo26n-reid.onnx`를 명시적 CPU에서 실행하는 새 adapter/runner다. [공식 추적 문서](https://docs.ultralytics.com/modes/track/#enabling-re-identification-reid)는 이 ONNX encoder 경로를 지원하며, [공식 라이선스 안내](https://www.ultralytics.com/license)의 AGPL-3.0 공개 연구 범위와 모델 metadata의 AGPL-3.0을 확인했다. 상용 배포 적합성을 판정한 것은 아니다.

가중치9,873,245바이트 SHA는 `8529c383197ae4c468eda535d1b165f8b4162cf17bf5fbcff49c7cb6455bc0bb`로 보존된 공식 release API digest와 같다. ONNX를 정적으로 읽어 MSMT17-v1 사전학습을 명시한 metadata, 동적 입력과 export448×448 설정을 확인했다. 이 사전학습 출처 표기는 모델 metadata의 주장이지 자체 학습 감사나 CCTV 품질 검증이 아니다. 공식 ReID의 padded crop(gain1.02/pad10), BGR→RGB, 0–1 및 bilinear448 처리와 공식 association을 사용한다. 표준 생성자의 동적 크기 fallback224 대신448을 고정하고 CPU backend의 thread 옵션을 공급하는 지역 subclass를 쓴 차이를 명시했다.

공식 tracker는 high/low 분리 후 idx를 전체 입력 배열 index로 복원한다. 새 adapter는 그 index로 raw cache bbox를 찾아 경계 입력에 쓰므로 Kalman 좌표가 관측을 대신하지 않는다. 원본 SHA 및 native PTS/time_base 확인 뒤 원본 BGR을 임베더에 제공하고, empty/비유한/zero-norm feature는 조용한 geometry-only fallback 대신 오류다. low의 공식 `>.25`와 기존 `>=.25` 차이를 지적했고 두 캐시에 정확히.25인 행0개를 독립 확인했다.

공식 구현의 proximity.5는 IoU<.5에서 appearance 비용을 배제한다. 비용 결합은 minimum이므로 외형 불일치가 허용되는 기하학적 연결을 반드시 거부하지도 않는다. 따라서 먼 재등장 복구·오연결 방지를 보장하지 않으며 Kalman/association까지 달라지는 구성 비교다. 기본값과 다른 high.5/low.25/new.6/buffer90/GMC none은 기존 캐시 비교를 위한 고정 조건이고 결과를 본 후 조정하지 않는다.

검토자의 첫 테스트는 pose환경에 lap이 없어11개 중10개만 통과했다. 담당자가 기록한 `.venv`+명시적 읽기 전용 Ultralytics/새 dependency overlay로 바로잡은 뒤 **11개 모두 통과**했다. 실제 공식 BOTSORT의 high/low full-index·빈 입력·재관측·합성 crop 전달도 포함한다. 검토자는 모델 세션 생성이나 forward를 하지 않았다. 별도 renderer5개 테스트도 통과했다. 검토 소스·설치 코드·가중치·실패/재검사 범위는 로컬 `review-reid-preflight.json`에 결속했다. 이 PASS는 **한 고정 CPU 비교 실행 준비의 기술 판정**이며 실제 결과·신원 연결 성공·채택을 뜻하지 않는다.

## 실제 ReID 결과 독립 감사 — 기술 계약 PASS

두 실제 결과1080프레임의 관측·예측 구분, 모든 관측의 cache_index/원본 bbox/점수, native PTS, 매 프레임 누적 encoder 호출/crop 수, 경계 후보 재생, 재관측 목록과 요약 계수를 독립 재계산했다. 원본 MP4 SHA를 검증하고 전1080프레임을 로컬 BGR로 다시 디코딩하여 실행 당시 누적 이미지 SHA와 정확히 같음을 확인했다. 임베더나 detector를 다시 실행하지 않았다. 실제 manifest의 실행 코드 SHA는 사전 검토 결속과 일치하고 CPUExecutionProvider 단독·torch CUDA 미초기화·448 crop·고정 설정이 기록됐다.

| 실제 ReID 진단 | 030 | 007 |
|---|---:|---:|
| 프레임 | 480 | 600 |
| confirmed 관측 행 / 관측 ID | 677 / 9 | 1278 / 11 |
| 예측 행 | 852 | 570 |
| 공백 뒤 재관측 | 9 | 12 |
| 후보 / gap 표시 후보 | 2 / 1 | 1 / 0 |
| encoder 호출 / crop·유효 embedding | 771 / 2837 | 1152 / 4041 |
| setup·decode·ReID·추적·출력·hash 포함 시간(초) | 18.594520 | 22.591157 |

030 #3 후보는 gap과 같은90.4초다. #5의 첫 반대편 관측은90.466667초이며90.466667→90.666667과90.7→91.0의 공백을 거쳐91.166667초에 출력한다. **gap 표시는 반대편 확인 누적 중 누락을 유지했다는 뜻이며 candidate interval 안의 보이지 않는 실제 통과를 복원했다는 뜻이 아니다.** 이 후보는 gap #4와 같은 전/후 관측 구간을 갖지만 출력이.5초 더 늦다. 030의 초기 ID와95/97초 이후 ID 단절은 남는다.

007 #2는56.633333초 뒤에도 낮은 점수의 짧은 박스 대안을 연결하여.2초 반대편 확인을 충족하고56.733333초 후보를 만든다. 같은 시각 gap #2는 더 긴 고득점 박스를 선택하여 반대편 pending을 중단했다. 두 입력 모두 같은 원본 캐시의 서로 다른 행이며 새 detector 복원이 아니다. 이전 접근·서기 관찰에 비추어 이 후보를 성공한 월장으로 바꿀 수 없다. 장시간 이어진 ReID ID가 여러 gap ID의 cache 행을 포함하는 것은 실제 동일 사람 연결 성공·다른 사람 오연결 중 어느 하나를 자동 확정하지 않는다.

raw cache·native image·후보·요약의 정확한 계약은 통과했다. **기술 실행 성공 / 실제 인물 정합성 미확정 / 기본 채택 보류**가 타당하다. 로컬 `review-reid-outcomes.json`에 산출물·원본 이미지 재디코딩 감사 근거를 보존했다. detector 재추론·자체 학습·GPU 작업은 이 CPU 비교에 없다.

## 연속 영상 기술 확인

strict/gap 렌더러의 emission 시각 표시·실제 관측과 자홍 점선 예측의 분리·원본 패널·표시용 crop을 검토했다. 기존4개와 추가 원본/gap/ReID4개, **총8개 MP4**를 검토자가 모두 재디코딩하여030 각480프레임,007 각600프레임과 상대 native 시각이 정확히 일치함을 확인했다. 원본·캐시·과거 출력·핵심 소스 보존 hash도 일치하며 strict frames는 과거 C와 바이트까지 동일하다. 최초4개 renderer SHA는 보존된 초기 소스, 추가4개는 현재 소스와 결속된다. `review-video-audit.json`과 `review-reid-video-audit.json`은 기술 확인이고 새 사람별 의미 시각 검수나 브라우저 재생 확인을 대신하지 않는다.

## 최종 공개 보고서·측정값 판단

[종합 결과](../experiments/EXP-0028-results.md), [ReID 결과](../experiments/EXP-0028-reid-comparison.md), [공개 metrics](../../records/EXP-0028/metrics.json)를 실제 산출물 및 이전 국소 검수의 출처와 대조했다. 공개58개 중54개 실측값은 모든 source hash와 원시값에 정확히 일치하며, 나머지4개 정확도·IDF1·행동F1·시간당 오탐은 미측정 null이다. cache 행 공유표도 독립 재계산해 일치했다. 007 strict→gap 변화는20행 ID재배정·gap전용28행·strict전용1행이며 순증27행을 사람 복원으로 바꾸지 않았다.

보고서는 030의 미해결 전후 ID 단절,007의 후보2→0→1 및 부분 박스 선택 차이, 같은 숫자 ID의 장시간 유지와 참 인물 연결의 구별, 관측·예측과 후보·확정 사건의 구별을 유지한다. ReID의 공백 표시가 확인 누적 중 누락이라는 점과 strict/gap 시간 대 ReID 전체 시간의 범위 차이도 명시했다. 박스 수·ID 수·embedding 수만으로 품질 개선을 주장하지 않고 기본 적용을 보류하는 결론이 타당하다.

ReID 상세 문서의 마지막 렌더 진행 표현은 담당자가 결과를 넘겼던 시점의 이력으로 보존한다. 최신 종합 결과와 이번 검토가8개 영상 생성·재디코딩 완료를 확인하며, 최종 전달 상태는 총괄의 별도 기록을 따른다.

**남은 구현 blocker는 없다.** 이 판정은 비교 자료의 기술·기록 무결성이며, 실제 동일인 연결 성공·침입 판정·일반화·상용 적합성의 승인이 아니다. 총괄이 요청한 제한된 영상 의미 질문은 이 시점 미응답이며 이번 기술 실행의 진행 조건으로 바꾸지 않는다. 검토자는 GPU·detector·ReID forward·학습·미디어 업로드·커밋을 수행하지 않았다. 웹 등록·실제 브라우저 재생/seek·GitHub 원격 반영은 총괄의 별도 전달 기록으로 확인해야 하며 이 문서에서 완료를 대신 선언하지 않는다. 추가 구성·모델·설정 탐색을 승인하거나 예약하지 않는다.

최종 공개 및 로컬 검토 근거의 SHA를 `runtime/EXP-0028/review-final-binding.json`에 결속한다. 이후 보고서·측정값이 바뀌면 기존 결속을 재사용하지 않는다.

| 최종 검토 대상 | SHA256 |
|---|---|
| 종합 결과 | `96f98bbf0f7c91206cfdc542fab4ef51f7e2a2e01b08a3ca24158b59c0d70fb9` |
| ReID 상세 결과 | `ecfd082a87d572d91c3a9a66a9a699eace7d7fcd2690c22d5325e8d0793ade9d` |
| 공개58개 metrics | `60e5555573767f7a446794af2c7be712e111d6cea49c441f30e53657f91004b5` |

로컬 독립 근거는 `review-actual-replay.json`, `review-reid-preflight.json`, `review-reid-outcomes.json`, `review-video-audit.json`, `review-reid-video-audit.json`, `review-public-artifacts.json`이다. 검토 문서 자체와 해당 receipt들의 hash는 최종 결속에 포함했다.
