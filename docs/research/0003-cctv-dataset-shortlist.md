# R-003 — 산업현장 CCTV용 데이터셋 후보 재조사

- 조사일: 2026-10-27
- 상태: **공개 자료/논문/데이터 카드 조사만 완료, 로컬 샘플 검증 전**
- 목적: 노타 AI의 CCTV·영상 관제 분야와 유사한 **실제 고정형 카메라**를 우선하되, 안전 관련 **행동/사건/시간 정답**과 실제 데이터 접근성을 분리하여 판단
- 주의: **이 문서는 데이터셋 선정 ADR이 아니다.** 기존 프로젝트/제품 목표는 실제 데이터를 검수한 후 재검토한다.
- 문제 정리: iSafetyBench는 다중 행동 영상 분석에 유용하지만, 사용자 검수 영상 `3hOGpHBJ0e4_trim_0.mp4`처럼 근거리 세로 일반 촬영이 섞여 있어 CCTV 환경 대표성을 주장할 수 없음.

## 후보 비교

| 후보 | 실제 카메라/현장 | 주석 특성 | 공개 영상 접근성 | 제약 | 다음 판단 |
| --- | --- | --- | --- | --- | --- |
| **ACCIDENT (CVPRW 2026)** | 실제 **도로 CCTV** 사고 영상, 산업안전 현장은 아님 | 실제 2,027 / 합성 2,211 클립. 사고 **시각·화면 위치·충돌 유형** 주석; 시간/공간/유형 3과제. CV/VLM baseline 제공 | 공식 Kaggle `picekl/accident`를 인증된 Kaggle CLI로 다운로드(직접 샘플 미검증) | 연구 전용 제한·클립 원 출처 라이선스/개별 재게시 조건·Kaggle 로그인 확인 필요. 프로젝트를 **교통 CCTV**로 바꾸면 주제 변경 | **강력 대안**: 산업안전 주제를 유지할지, 교통 CCTV 사고 관제로 바꿀지 사용자 결정 후 검증 |
| **SteelBench (2026)** | 실제 제철소 64대 고정 CCTV / 16개 구역 | 1,345개 15초 클립, 작업자 행동 25종, PPE, 안전규칙, 가림·조명, 검수 출처 기록 | **전체 영상 공개 아님. MP4 샘플 50개(594MB), 그중 정답 JSON 47개. 전체는 8프레임/클립 JPG와 정답·매니페스트 중심** | CC BY-NC 4.0, 원 제철소 영상의 research-only 사용 계약·프라이버시 조건 확인 필요. 전부 장시간 비디오 정답 아님 | **우선 검토**: sample/의 주석 대응 클립 소량을 실제 다운로드·재생. 학습용 전체 영상으로 오인하지 말 것 |
| **CMA (Construction Meta Action, 2023)** | 실제 건설현장 영상, 고정 CCTV 여부 **미확인** | 1,595개 짧은 작업 행동 클립, 7종 행동 | Baidu Netdisk(공식 Github에서 코드 제공). 국내 다운로드 가능 여부 미확인 | 연구용, 비상업 사용. 사건 발생 시점/객체 주석 수준 확인 필요 | **2차 검토**: Baidu 접근과 구도·주석 샘플을 먼저 확인 |
| **MEVA (2021)** | 현실적인 다중 고정 카메라와 일부 드론/다른 촬영 데이터 | 사람/차량 행동, 공개 시간적 행동 탐지 주석 | AWS 공개 S3, 지상 카메라 328시간(516GB) 중 **소량 선택 가능성 확인 필요** | **산업 안전 특화 아님**, 대부분 시나리오 연출·도심 테스트시설 | 시간 구간 자동 탐지/오탐 측정 목적의 **보조 데이터 후보** |
| **VIRAT (2011)** | 고정형 야외 감시 카메라 | 8.5시간 HD stationary ground video / 12개 활동 주석(릴리스 2.0) | 공식 배포, 현재 링크 접근/조건 재확인 필요 | 산업재해가 아닌 사람·차량 상호작용 | 작은 감시 영상 사건 탐지 baseline 후보 |
| **AI-Hub 고소작업 현장 실시간 영상 데이터** | CCTV·안전모 카메라·액션캠 혼합 및 연출 시나리오 | 371시간 원 영상으로 구축한 **JPG 687,895개**, bbox/keypoints JSON, 안전고리·안전모·난간 관련 클래스 | 국내 데이터 신청·로그인/이용정책, 공개 목록의 주 산출물은 **이미지** | 실제 CCTV 영상만 분리 가능한지/연속 영상 공개 여부 미확인 | CV 검출/산업안전 이미지 보조 후보 |
| **SARD (2026-10)** | 건설 현장 작업·사람-객체 상호작용, CCTV 고정형인지 미확인 | 코어 748 비디오/11 활동, 세부 9개 비디오 주석(67,098 프레임) | Zenodo는 주석/사전 추출 특징을 공개하나 원 영상 재배포 제한 명시 | 원 영상 권리·실행 접근 장애 | 주력 후보 아님. 영상 접근성 확인 시에만 재검토 |
| **기존 Safe and Unsafe Behaviours** | 실제 공장 2대 IP CCTV, 691개 클립 | 8개 영상 단위 클래스, 객체/시간 주석 없음 | 이미 8개 로컬 감사 | 패널 단순 상태 중심, 권한/과적의 시각 판정 한계 | 감사·코드 보존, 메인 MVP 패널은 ADR-0002에서 제외 |
| **기존 iSafetyBench** | 실제 웹 클립 혼합 (고정 CCTV를 보장하지 않음) | 1,100개, 행동 다중 태그/캡션, 시간·객체 GT 없음 | 이미 8개 로컬 감사 | 촬영 환경 이질·라벨 의미 모호·유튜브 권리 | VLM 행동 이해 보조평가 후보 |

## 중요한 사실 (재검증 필요)
1. **SteelBench의 핵심 제약:** 논문은 1,345개 15초 CCTV 클립 기반 연구를 보고하지만, 현재 Hugging Face 배포 안내는 **전체 MP4 1,345개가 공개된 것처럼 다운로드 가능하지 않음**을 명시. `sample/clips`의 MP4 50개만 직접 공개하고 `sample/annotations` 정답은 47개임. 그 외 1,345개는 JPEG 프레임(각 8장)과 정답 데이터 중심. 50개 전체 다운로드 이전에 sample index/샘플별 권리 및 용량 검사.
2. **SteelBench 어노테이션을 사건 시간 GT로 오인하지 말 것:** 클립/작업자별 분류·안전 규칙 판단은 근거가 있지만 정확한 행동 시작·종료 구간 라벨이 있는지 별도 확인. 논문에서 VLM 어시스트 라벨의 편향 가능성을 제기했으므로 라벨 출처 별 품질이 중요.
3. **CMA는 영상 규모는 충분하지만 고정형 카메라 여부와 중국 링크 접근이 미확인**. 자료명을 'construction'이라 해서 CCTV라 추정하지 말 것.
4. **MEVA는 CCTV 동작 탐지 쪽 기반이 강하지만 산업안전 이벤트 정확도로 바꿔 말하면 안 됨**. 라벨 시간 경계 수준과 다운로드 단위를 직접 검증.
5. **AI-Hub 고소작업 데이터셋은 웹페이지에 자료 유형을 이미지/JPG로 표기**. 구축에 사용한 371시간 영상이 곧 다운로드 가능한 연속 MP4를 의미하는 건 아니다.
6. **실제 제품 포트폴리오**: 데이터 라이선스가 CC BY-NC / 연구 전용이면 공개 데모/미디어 업로드 또는 상업적 사용은 별도 검토. CCTV 촬영 대상 프라이버시 주의.

## 다음 검증 제안(구현·다운로드는 아직 안 함)

**우선 결정 질문:** 산업안전 CCTV를 유지한다면 SteelBench → CMA 순서, **교통 CCTV 사고 탐지로 전환해도 된다면 ACCIDENT를 별도 최우선 후보**로 감사한다. 서로 다른 도메인의 성능을 혼합 평가하지 않는다.

**1단계: SteelBench** 데이터 카드·manifest·sample 목록·GT JSON을 고정 revision에서 확인. 실제 다운로드는 권리 조건 확인 후 정답 매핑되는 4~6개 MP4만 로컬로; 카메라 구도, 작업자 크기, 행동/안전 태그, 주석 모호성, 근거 구간 표시 가능성 평가. 50개 전량/전체 JPG 다운로드 금지.

**2단계: CMA** 배포 접근 가능 여부, CCTV와 비CCTV 영상 비율, 행동 클래스·실제 정답을 파일 샘플로 확인. 접근 불가 시 MEVA/VIRAT으로 전환.

**3단계: 문제 정의 확인** CCTV 실시간 경보가 핵심인가, 녹화된 CCTV에서 이벤트 후보를 검출해 검토 지원하는 것이 핵심인가? 두 경우에 요구하는 정답(연속 영상의 시간 GT / 클립 행동 GT)이 다름. 사용자와 Gate에서 확정. 모델 구현은 이후.

## 출처
- ACCIDENT CVPRW 2026 (2,027 real + 2,211 synthetic / time, location, collision GT): https://openaccess.thecvf.com/content/CVPR2026W/AUTOPILOT/html/Picek_ACCIDENT_A_Benchmark_Dataset_for_Vehicle_Accident_Detection_from_Traffic_CVPRW_2026_paper.html
- ACCIDENT 프로젝트/공식 코드/다운로드: https://accidentbench.github.io/ ; https://github.com/accidentbench/ACCIDENT ; https://www.kaggle.com/datasets/picekl/accident
- ACCIDENT 공개 주석/영상 권리 설명(논문 보충자료): https://openaccess.thecvf.com/content/CVPR2026W/AUTOPILOT/supplemental/Picek_ACCIDENT_A_Benchmark_CVPRW_2026_supplemental.pdf
- SteelBench (데이터 카드, 배포 범위 및 조건): https://huggingface.co/datasets/steelbench/SteelBench
- SteelBench 2026 논문: https://arxiv.org/abs/2607.05264
- CMA 공식 연구 저장소: https://github.com/S1mpleyang/ConstructionActionRecognition
- CMA 연관 현장 연구: https://www.mdpi.com/2075-5309/15/22/4205
- MEVA: https://mevadata.org/ ; https://registry.opendata.aws/mevadata/
- VIRAT: https://viratdata.org/
- AI-Hub 고소작업: https://aihub.or.kr/aihubdata/data/view.do?currMenu=115&dataSetSn=507
- SARD (annotation/features, copyright restrictions): https://zenodo.org/records/23457780
- 기존 감사: ../data/SAMPLE_AUDIT.md / ../data/ISAFETYBENCH_SAMPLE_AUDIT.md
