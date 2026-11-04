# EXP-0058 — 재출현 유예·접근 확인 결합 시험 전달

2026-11-04.0056과0057을 함께 적용해013·015의 공식 확인 매칭이 기본/0057의1/2에서2/2, 누락1→0으로 바뀌었다.01365.50초·01566.80초이며 기존 공식 사건 손실0, 새015매칭1이다.013의 원래65.566667초 보조 확인 근거는 사라졌고 새 접근·소실 근거로 같은 사건을 확인했다. 개별 근거 보존으로 표현하지 않는다. [결과](EXP-0058-results.md) · [사전 계획](EXP-0058-protocol.md).

## 검토·등록·게시·실제 화면

관련397시험과 독립50방법, 실제 저장 결과 및40측정의 원천·표본 범위를 검토했다. 기존 완료 CLI로 보고서·측정값·독립 검토·binding을 등록했고 execution succeeded, review accepted_for_comparison, decision adoption_on_hold로 구분했다. 첫 두 영상의 성공이며 전체 성능이나 실제 행동 시각 적절성은 미검증이다.

결과 커밋 [ce79cdd](https://github.com/yrumupusm/sceneguard-ai/commit/ce79cdd3709d65e696ef8f482a9ed2da22b07008)을 origin/main에 게시했다. verify_delivery github로 원격 커밋·카탈로그·배정·등록 원문 바이트를 확인했다. 이 전달 문서와 HANDOFF의 후속 커밋은 등록 원문을 바꾸지 않으며 최종 원격 영수증을 별도로 남긴다.

실제 로컬 브라우저에서 진행 중 카드를 확인한 뒤, 등록 후 EXP-0058을 선택해 완료·채택 보류·결과 요약을 확인했다. 상세 측정40행의 표시명·값·표본 수가 API와 같고15초 주기를 넘어도 선택 결과가 유지됐다. 서버의 보고서/측정값/검토/binding 및 viewer 코드 해시도 현재 파일과 일치한다. 이번 비교 그래프0·등록 미디어0이며 영상 재생 검증은 아니다. 기존 통합 browser 명령은 영상 필수 조건으로 미통과했고 별도 실제 기록 화면 검사는 통과했다. browser-media-contract.json과 browser-completed-record.json에 범위를 구분했다.

등록 보고서 SHA256은70e6e26707f598cbdc3a10511d7e4b029e693df50e6a9640c327424be062a5bf, 측정값은74568f5ff96a32a7840432f347e2b591ef2910ec7365212daa0825a55e721122, 검토문은e45fe113a35b22e9563d4babf0fe794d81a3fae91f634873d9bab4f24c3c7395다. 등록 후 해당 원문은 불변으로 보존한다.

## 코드·자료·실행 보존

결합 코드는 [별도 패치](patches/EXP-0058-combined-hold-approach.patch)로 보존하며 기본 운영 코드에는 합치지 않았다. 패치 SHA256은83d885c85b43733edb13df664968cb5433cd1d7496bab70de64b6a2399235fe4다. 기준bc4906e0153b4fcd2c80fffc7575d172e6dd572a의 격리 Git 인덱스에 적용해 고정85모듈 및96시험 파일 manifest와 같음을 확인했다. 후보85 manifest는0bbc027070af9f981b6e0aa1257e2251f97729c3e7821796bc9003d37d87bece, 운영85는970c3ed94ae96b168bcf752f7202f23b4ee53e2c7d711b44f61d8c9f468a46cc 그대로다.

기존 공개375파일과60카탈로그 행·54배정을 보존하고 EXP-0058 한 행씩만 추가했다. 원본·정답·이전 결과·검수DB는 유지하며 미디어·원시 결과·로그·영수증은 로컬 전용이다.0055/56/57의 두 영상씩 기존 출력54개는 해시 검증해 재사용했고 과거 재생0회다. 결합 후보만 각1회 실행했고 새 검출·추적·flow·VLM/GPU호출·분석 실패·재시도는0이다. 초기 코드 시험과 실행파일명 오류,0055 전체 집계를 사용했던 요약 초안은 보존하고 두 영상 집계로 정정했으며 실제 분석은 반복하지 않았다.

구현·평가 Task task_eaef6676cc84와 독립 검토 Task task_854e4e56ae92의 정확한 완료를 받고 두 담당 터미널을 반환했다. 최종 남은 반환 대상0이며 사용자 유지 작업은 그대로다. 웹 pending --include-acknowledged 조회는 성공·답변0이었다. 근거는 runtime/combined-hold-approach-v1 및 outputs/validation/combined-hold-approach-v1/run-001에 보존한다. 추가9/45영상이나 후속 튜닝은 실행하지 않았다.
