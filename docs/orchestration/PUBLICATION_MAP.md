# Orca 세팅 게시 커밋 대응

기준 main: `83ce1b56ba4d9e73bae5f1c48856d73a4c371d83`.

연결된 GitHub 도구로 작업 단위별 커밋을 게시한다. 커밋 메타데이터가 달라 로컬 SHA와 GitHub SHA는 다르지만, 각 단계의 Git tree SHA가 정확히 같은지 확인했다. GitHub 커밋 메시지의 `Local-Source-Commit`과 `Source-Tree`도 이 대응을 기록한다. 검토 보고서의 frozen SHA는 로컬 검토 대상을 가리키며 아래 대응으로 게시본을 찾을 수 있다. 기존 main 이력을 지우거나 force push하지 않는다.

| 작업 단위 | 로컬 커밋 | GitHub 커밋 |
| --- | --- | --- |
| setup: add historical result contracts and local lab lifecycle tools | `42d47e4` | [574b4f6](https://github.com/yrumupusm/sceneguard-ai/commit/574b4f62065f156df1e4322035bac66e193f189b) |
| Add local read-only experiment viewer | `c03be71` | [4dc2366](https://github.com/yrumupusm/sceneguard-ai/commit/4dc23668b1882a29564631d31a73edc9136dd482) |
| Add shared CPU mock queue with supervised lock recovery | `18d920b` | [000909e](https://github.com/yrumupusm/sceneguard-ai/commit/000909e93d5b03886c2be73dd1ad04a8a4ebbbf3) |
| fix: align viewer cards and preserve report review provenance | `d0a6fdd` | [242b4b9](https://github.com/yrumupusm/sceneguard-ai/commit/242b4b979afeafb0e1a6666d6becc6184511b8a3) |
| test: exercise shared queue and independent viewer restart | `a2f867c` | [1b8c6e2](https://github.com/yrumupusm/sceneguard-ai/commit/1b8c6e2b59bd403b6052bea449ad06bc82f1f9e6) |
| docs: independently review frozen Orca setup | `2f66e6c` | [9447f88](https://github.com/yrumupusm/sceneguard-ai/commit/9447f8831145ac69d2d3b6e97da937cc0d7802a0) |
| fix: bind reviews to sources and verify both lab services | `9ec289d` | [4557e11](https://github.com/yrumupusm/sceneguard-ai/commit/4557e11998c6c3b2f3925d015aeb31eeed23ab60) |
| docs: independently recheck Orca setup fixes and smoke evidence | `312b8d5` | [94ba50a](https://github.com/yrumupusm/sceneguard-ai/commit/94ba50aca255932779c14fdc8a044a6173f5f759) |
| fix: require live overlap evidence in service restart smoke | `b05c6a8` | [88954d2](https://github.com/yrumupusm/sceneguard-ai/commit/88954d225d89fb2a0695061d4a0d52aabe45eddf) |
| docs: close R4 with narrow smoke evidence review | `49a124c` | [aa5ea07](https://github.com/yrumupusm/sceneguard-ai/commit/aa5ea07ed34edd69922c5f0787d62e0f6a284827) |

이 표와 LOCAL_SETUP_REPORT/HANDOFF/NEXT 갱신은 별도의 마지막 문서 커밋에 포함한다. 마지막 게시 커밋은 `git log -1 origin/main` 및 사용자 완료 메시지로 확인한다. 실제 원격 ref 갱신은 예상 이전 SHA를 대조하는 non-force 작업이며, 이후 fetch한 main과 로컬 통합본의 tree를 다시 비교한다. 로컬 setup 브랜치의 검토 이력도 보존한다.
