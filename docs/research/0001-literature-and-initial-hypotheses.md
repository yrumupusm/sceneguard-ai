# R-001 — 산업안전 영상 분석 선행연구 및 설계 가설

- 작성: 2026-10-26
- 성격: 문헌 조사 / 자체 데이터 검증·실험 **미실행**
- 목적: 산업안전 CCTV의 위험행동 감지에서 CV, 시간 분석, VLM의 역할을 연구 사례로 구분

## 해결할 문제
공개 CCTV 영상에서 시각적으로 관찰 가능한 안전 이벤트 후보를 감지하고 근거 장면과 설명을 제공한다. 영상만으로 권한 여부, 규정상 허용 하중을 자동 확정하지 않는다.

## A. Unsafe-Net — 객체 선별 + 시간적 행동 분류
- Önal & Dandıl, *Unsafe-Net: YOLO v4 and ConvLSTM based computer vision system for real-time detection of unsafe behaviours in workplace* (2024 온라인 공개).
- 원문: https://link.springer.com/article/10.1007/s11042-024-19276-8
- 방식: YOLOv4로 분석할 관련 객체와 프레임을 선별하고 ConvLSTM으로 프레임들의 시공간 정보를 이용해 행동 분류.
- **논문 보고:** 위험행동 분류 정확도 95.81%, 행동 분류 단계 평균 0.14초. 전처리까지 포함한 전체 지연과 분류 단계 지연은 다르게 다뤄야 한다.
- 제약: 단일 공장·소수 카메라, 제한된 행동 클래스, 외부 환경 일반화 여부 미확인.
- 시사점: 위험행동 탐지를 꼭 단일 이미지나 VLM만으로 해결할 필요는 없다. *그렇다고 YOLO와 ConvLSTM을 반드시 따라야 한다는 뜻도 아니다.*

## B. iSafetyBench — 산업환경에서 범용 VLM 평가
- Abdullah et al., ICCV Workshop 2025
- 논문: https://openaccess.thecvf.com/content/ICCV2025W/VISION%2725/html/Abdullah_iSafetyBench_A_video-language_benchmark_for_safety_in_industrial_environment_ICCVW_2025_paper.html
- 코드·데이터: https://github.com/iSafetyBench/data
- 산업안전 영상 1,100개와 8개 VLM을 **zero-shot** 평가.
- **논문 보고 예시:** Qwen2.5-VL-7B-Instruct의 위험 동영상 *16지선다 단일 정답 행동 인식* 정확도 33.6%.
- 이 수치를 위험/정상 이진 감지 정확도나 우리 데이터셋의 모델 정확도로 해석하면 안 된다.
- 시사점: 세밀한 행동 및 시각적 맥락 판단을 VLM 하나에 맡기기 전 별도 검증이 필요.

## C. Context-aware VLM Agent — 도메인 적응 기반 안전 분석
- Chan et al., *Context-aware vision-language model agent enriched with domain-specific ontology for construction site safety monitoring* (2025)
- https://doi.org/10.1016/J.AUTCON.2025.106305
- 작업 안전 도메인의 데이터·온톨로지·프롬프트·모델 적응을 함께 사용한 연구.
- 현장 맞춤 VLM의 가능성을 보여주지만 '범용 VLM에 질문만 넣는 단독 방식'과 다르다.

## D. CV 검출과 VLM 역할 분리형
- Sivanraj et al., *Real-time safety detection on construction sites using a vision-language and NLP-based model* (2026)
- https://www.sciencedirect.com/science/article/pii/S1474034625007827
- YOLO 계열로 물체/안전 관련 위치 검출, VLM으로 장면 맥락 설명, NLP로 안전 준수 검토를 구성.
- 객체 위치 인식과 장면 해석의 역할을 나누는 설계 사례. 우리 위험행동 데이터에 대한 직접적인 우수성 증거는 아님.

## E. LAVAD — 언어를 이용한 영상 이상 탐지
- Zanella et al., *Harnessing Large Language Models for Training-free Video Anomaly Detection* (CVPR 2024)
- https://arxiv.org/abs/2404.01014
- 프레임 설명과 언어모델의 시간적 통합으로 이상을 분석. 산업안전 전용 검증은 아님.
- 시간 정보는 반드시 객체 추적으로만 처리해야 하는 것이 아니다.

## 메인 데이터 후보와 원 출처
- 연구 데이터: *Video dataset for the detection of safe and unsafe behaviours in workplaces* (Data in Brief, 2024), https://www.sciencedirect.com/science/article/pii/S235234092400756X
- 배포: https://huggingface.co/datasets/Voxel51/Safe_and_Unsafe_Behaviours
- 문헌에 따르면 691개 MP4와 8개 행동 클래스, 영상 단위 정답이 제공되는 것으로 기술. **실제 배포 파일·라벨·접근·라이선스는 Codex가 직접 확인할 것.**

## 고려할 대안
| 접근 | 기대 용도 | 주요 우려 |
| --- | --- | --- |
| VLM 영상 단독 분류 | 빠른 분석·자연어 설명 | 세밀한 위험 구분, 영상 길이, 지연, 환각 |
| CV+시계열 행동 인식 | 정의된 행동의 자동 탐지 | 학습/라벨 작업, 새로운 장면 일반화 |
| CV/ROI/필요 시 추적 + VLM 설명 | 위치/움직임 감지와 사람에게 읽히는 설명 분리 | 앞단 오류 전파, 처리 구성 복잡성 |
| VLM 프레임 설명 + 시간 통합 | 추적 없는 비디오 의미 분석 | 프레임 샘플링/비용/판단 오류 |

## 잠정 설계 원칙 (확정 아님)
1. 이벤트 **감지**와 증거 기반 **설명**은 별도 책임으로 검토한다.
2. 추적이 필요한지는 실제 영상과 목표 사건에 따라 정한다.
3. VLM은 설명과 검토 후보로 고려하되 출력을 정답으로 가정하지 않는다.
4. ONNX/TensorRT 최적화는 추론 병목을 실제로 측정한 다음 결정한다.
5. 논문 간 데이터/평가 지표가 다르면 정확도를 직접 비교하지 않는다.

## 다음 단계
소량 샘플 영상과 공식 라벨·이용 조건 검증 → '통로 이탈/패널 개방' 등 시각적으로 관찰 가능한 이벤트 우선 후보 검토 → 문제·평가 단위 확정 → 새 ADR에서 기술 선택.
