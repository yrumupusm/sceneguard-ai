# R-002 — iSafetyBench VLM 산업안전 영상 벤치마크 분석

- 작성: 2026-10-26
- 구분: 문헌 요약·SceneGuard 설계 시사점. **프로젝트 자체 실험은 미수행.**
- 서지: Abdullah, Rawat, Vyas, *iSafetyBench: A video-language benchmark for safety in industrial environment*, ICCV Workshop 2025
- 원문: https://openaccess.thecvf.com/content/ICCV2025W/VISION%2725/html/Abdullah_iSafetyBench_A_video-language_benchmark_for_safety_in_industrial_environment_ICCVW_2025_paper.html
- 자료: https://github.com/iSafetyBench/data

## 연구 질문
별도 파인튜닝 없이 일반 VLM이 산업현장의 일상 행동과 위험 행동을 정확히 이해할 수 있는지 평가. 새로운 모델 개선법보다 **벤치마크와 오류 유형 분석**이 목적.

## 데이터와 평가
- 온라인 산업/안전 영상 클립 1,100개 (정상 680, 위험 420); 4~8초 정도.
- 정상 98종·위험 67종 행동 태그. 복수 행동 가능.
- 8개 모델을 zero-shot으로 시험.
- 단일 정답 문제: 16개 선택지 중 정확한 행동 하나 선택 → Accuracy.
- 복수 정답 문제: 해당 행동들 선택 → Precision/Recall/F1.

## 논문에 보고된 결과 (해당 실험 조건)
| 모델 | 정상 16지선다 정확도 | 위험 16지선다 정확도 | 위험 복수정답 F1 |
| --- | ---: | ---: | ---: |
| Ovis2-8B | 47.3% | 40.3% | 46.2% |
| InternVL2.5-8B-MPO | 42.2% | 38.3% | 49.0% |
| Qwen2.5-VL-7B-Instruct | 46.9% | 33.6% | 41.7% |
| GPT-4o | 40.3% | 37.3% | 45.1% |

- 일부 명확한 시각적 위험보다 사람·물체 상호작용/행동 맥락 이해에서 어려움이 관찰됨.
- 제시 사례에는 물체를 놓는 행동을 찢는 행동으로 혼동하거나 위험에서 피하는 행동을 잘못 해석한 경우 등이 있음.

## 해석 시 지켜야 할 제한
- 33.6%는 **16지선다 행동 분류** 결과지 '위험 여부 감지 성공률'이 아니다.
- 이 논문은 CV+VLM이 VLM 단독보다 낫다는 비교를 직접 검증하지 않는다.
- 실시간 지연/FPS/VRAM 요구량을 입증하지 않는다.
- 2025년 사용한 모델 버전과 프롬프트/실험 설정에 한정되며 2026년 최신 모델까지 일반화 불가.
- Unsafe-Net의 95.81%와 iSafetyBench 33.6%는 **데이터·문제·지표가 달라 직접 비교 금지**.

## SceneGuard에 적용할 가설 (논문 결론이 아닌 우리 해석)
1. 안전 행동 분류·안전 맥락 설명의 품질을 **따로** 평가할 필요가 있다.
2. 통로 이탈처럼 위치·시간 흐름이 중요한 행동은 CV+영역 분석, 시간 인식 모델, 필요시 추적 중 무엇이 유리한지 검토한다.
3. VLM의 설명은 정답이 아니라 근거 영상에 대한 **검수 대상**이다.
4. 모델을 하나로 고정하지 않고 소량 데이터 감사와 성능 요구사항을 보고 필요한 역할을 정한다.

## 다음 실무 작업
실제 Safe and Unsafe Behaviours 영상의 내용, 공식 라벨, 이벤트 발생 구간과 외부 권한 정보 의존성을 확인. 이를 바탕으로 첫 MVP 사건과 평가 단위를 결정하고 새 ADR을 작성.
