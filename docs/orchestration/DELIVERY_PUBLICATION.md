# 실험 전달 절차 게시 이력

2026-10-28. 검토한 로컬 작업 단위 12개를 GitHub connector로 순서대로 게시했다. GitHub는 커밋 작성 메타데이터를 새로 부여하므로 commit SHA는 달라지지만, 각 단계의 **tree SHA가 정확히 일치**함을 확인한 뒤 main을 force 없이 갱신했다. 원격 main 예상값 `1c618b59cfad47c4144f7cdb2e7c2b32d2154d89`를 조건으로 사용했다. 로컬 main은 이후 fast-forward로 동기화했다.

| 로컬 source | GitHub commit | 작업 |
| --- | --- | --- |
| `587085a` | [f708eb6](https://github.com/yrumupusm/sceneguard-ai/commit/f708eb6bb40289603263939ec998b38995ab8f7a) | docs: define end-to-end experiment delivery contract |
| `aabe2ab` | [c2eb522](https://github.com/yrumupusm/sceneguard-ai/commit/c2eb522fbb50f642263f2c1f04bd0d48dbfd8fd9) | Add coordinator result registration and safe retry contract |
| `fc5824b` | [4c15cdb](https://github.com/yrumupusm/sceneguard-ai/commit/4c15cdb8d5eaa83d0c7008b54d8a4c953b3b0708) | Connect delivery cards to assignments and Orca observations |
| `7f41e0a` | [c0e596e](https://github.com/yrumupusm/sceneguard-ai/commit/c0e596e3e55d35c178685c116615938d0fab24b9) | feat: verify publication and browser delivery separately |
| `b8f7c08` | [71824a1](https://github.com/yrumupusm/sceneguard-ai/commit/71824a16796405d94cba1922a52f7f16bbf3c73e) | fix(orchestration): refresh browser acceptance and preserve CLI errors |
| `379a1d0` | [3e06988](https://github.com/yrumupusm/sceneguard-ai/commit/3e069888f4f703d710c6bd9bcd40f7e9b25c6238) | fix(orchestration): bind partial completion and verify current review |
| `226df16` | [abe9945](https://github.com/yrumupusm/sceneguard-ai/commit/abe99454e43298f97cf54ddc3c273499561ed5c8) | docs(review): record independent delivery findings |
| `2d88656` | [c83d1d0](https://github.com/yrumupusm/sceneguard-ai/commit/c83d1d076ed20729dec868d20236db7ae31adb1c) | fix(orchestration): verify visible report and served result after playback |
| `1f89f92` | [8905863](https://github.com/yrumupusm/sceneguard-ai/commit/8905863d095cd300868d278c3cfba89292b2e332) | fix(orchestration): wait for decoded video data before playback check |
| `a639352` | [20f9eac](https://github.com/yrumupusm/sceneguard-ai/commit/20f9eacd1eeef60d9c282c26f64e03820dc8a2eb) | test(orchestration): require sustained video playback in acceptance |
| `75f1e48` | [fc10126](https://github.com/yrumupusm/sceneguard-ai/commit/fc1012662cbf19aa2c4060f391ca30ada7230b83) | docs: recheck delivery findings F1 through F4 |
| `2cbc512` | [5bca66b](https://github.com/yrumupusm/sceneguard-ai/commit/5bca66beb03dd82bec937df8731a0b9a0edbe433) | docs(orchestration): require assignment through verified experiment delivery |

게시된 코드·운영 기록 묶음의 마지막 SHA는 `5bca66beb03dd82bec937df8731a0b9a0edbe433`, 동일 tree는 `9ddcee7b2ec9f85521a97e0aebbdeabf2737a436`다. 커밋 메시지의 Local-Source-Commit/Source-Tree로도 대조할 수 있다. 초기 검토 needs_revision과 수정 후 재검토를 모두 보존했다.

`verify_delivery github`는 이 원격 main과 EXP5의 게시 report/metrics/review/binding 및 catalog 항목이 일치함을 확인했다. 이 사실은 브라우저 성공을 뜻하지 않으며 receipt의 `browser_verified`는 false다. 별도 `verify_delivery browser`가 같은 자료의 원문 펼침·그래프·두 비교 영상 재생/seek를 확인했다. 실제 확인 범위와 한계는 [DELIVERY_VALIDATION](DELIVERY_VALIDATION.md)을 따른다.

이 문서와 게시 이후 서비스 반영 기록은 후속 문서 커밋으로 게시한다. 그 마지막 커밋은 완료 메시지와 원격 main에서 확인하며, 테스트한 코드나 EXP1~7 자료를 변경하지 않는다. 원시 receipt·config·TEST fixture·미디어는 Git 제외 로컬 경로에 보존한다.
