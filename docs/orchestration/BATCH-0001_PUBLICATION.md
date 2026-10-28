# BATCH-0001 게시와 서비스 확인

2026-10-28. **코드 구현·실제 GPU 실행·결과 등록·GitHub 게시·main 서비스의 실제 브라우저 확인을 각각 완료했다.** 두 후보의 채택 보류와 배치 종료는 [비교 결론](../experiments/BATCH-0001-vlm-comparison.md), 역할/큐/복구/오류는 [전달 기록](BATCH-0001_DELIVERY.md)을 따른다. 모델·조건을 추가 실행하지 않는다.

## 게시 버전과 서비스 버전

검증한 실험 게시 커밋은 `6acb3abbae5ba6f907cba921961b9e6971eadbce`, tree는 `07c45b39f3a015ed31d16035708c268834cdc928`다. 기존 `4f55e81` 위에 작업 단위21개를 GitHub connector로 작성하고 expected-head 조건의 fast-forward로 main을 갱신했다. 각 원격 tree와 로컬 작업 tree가 정확히 같음을 확인했다. force/reset/stash는 사용하지 않았다. API가 작성한 commit metadata 때문에 로컬/원격 SHA가 달라 아래에 대응을 보존한다.

로컬 main은 깨끗한 상태에서 fetch + merge --ff-only로 같은 원격 커밋을 받았다. 기존 web/projection만 stop한 후 기존 runtime/config에 새 artifact allowlist를 보존해 main 저장소에서 start했다. 새로운 서비스/큐를 병렬로 만들지 않았다. 시작 상태는 connected, 실제 두 PID의 cwd는 main 저장소이며 `/assets/app.js` HTTP bytes와 저장소 파일 SHA256 `cae122f859102f7a6f0dd3255d9e4a7ec5491814f340dc9a4e28fff6ba8b9fcd`가 일치했다. 실행 코드·실험 문서·카탈로그의 게시 버전과 읽는 버전을 따로 확인한 것이다.

이 파일은 위 검증 뒤 추가한 **게시 확인 문서만의 후속 커밋**이다. 그 후속 커밋은 실험 소스/측정값/등록 미디어/웹 코드/설정을 바꾸지 않는다. 아래 receipt의 기준 SHA를 자기 자신을 포함한 최신 커밋으로 소급 바꾸지 않는다. 최종 전달 시 최신 원격/로컬 HEAD와 서비스 소스 동일성을 다시 확인하며 원래 receipt도 보존한다.

## 실제 화면 확인

주소: **http://127.0.0.1:8765/**. 담당1에서 EXP-0008/0010, 담당2에서 EXP-0009를 선택한다. 담당3/미배정 카드와 기존 EXP1~7은 보존한다. 두 담당의 완료 상태는 일치하는 native dispatch의 최근 관측이며 실험 채택을 뜻하지 않는다.

| 결과 | GitHub 파일/해시 | main 브라우저 | 입력 시트 |
|---|---|---|---|
| EXP-0008 | report/metrics/review/binding 일치 | 보고서·검토 펼침, 그래프2개, 영상6개 재생·seek 통과 | 6개 로딩·크기 확인, 각1536×2390 |
| EXP-0009 | report/metrics/review/binding 일치 | 보고서·검토 펼침, 그래프2개, 영상6개 재생·seek 통과 | 6개 로딩·크기 확인, 각768×2070 |
| EXP-0010 | report/metrics/review/binding 일치 | 보고서·검토 펼침, 그래프2개, 영상6개 재생·seek 통과 | 6개 로딩·크기 확인, 각2240×3190 |

영상은 각5초(clip03은 native FPS로5.005초),1280×414의 원본 연속/2fps 표본 비교다. 모든 등록 영상에서 재생 시간이 증가하고1.5초 seek와 프레임 decode가 확인됐다. 15초 polling 이후에도 같은 플레이어가 유지됐다. 본문 수치와 그래프가 동일 metrics에서 나오고 정확도/F1을 미측정으로 표시하는 것도 확인했다. 공식 전처리 결과 시트는 별도로 eager load 후 completed/naturalWidth/naturalHeight를 확인했다.

이는 로컬 브라우저의 DOM·재생·decode 상태 검증이며, 픽셀/스크린샷을 클라우드에 전송한 의미 검수가 아니다. clip02/06은 사람 확인 우선 항목으로 남는다. iframe/링크만 존재하거나 HTTP200인 것으로 재생 성공을 대신하지 않았다. 세 결과 모두 원문 보고서와 총괄 검토가 실제로 펼쳐졌고 형식·행동·실행·채택 상태를 구분한다.

## 로컬 검증 receipt의 SHA256

아래 파일은 통합 worktree의 Git 제외 `runtime/vlm-batch01/`에 보존한다. 내용/절대 artifact 경로/DB/원시 로그는 게시하지 않는다. GitHub와 browser receipt는 별개이며 각자의 확인만 주장한다.

| receipt | SHA256 |
|---|---|
| `exp8-github-main.json` | `8d3cd065406e7d6331458048d81ee5db28e23630b335df7928159570711431bb` |
| `exp8-browser-main.json` | `82b2458931e89d33cd82bdb7ff589a696aaeaf227c1a1f074d06a785cacc20f0` |
| `exp8-images-main.json` | `928c389fa09d60b29201528fa4cfddbd129d10c8e50d9e2597fbe49e847572a9` |
| `exp9-github-main.json` | `3079a55a0f00717d9d48124d423b79aa4f4426138a57427f1dc6cbf4ab031115` |
| `exp9-browser-main.json` | `933fff98e7ac968130cdc2bc3e4eaf1675be68cf8d13b61826c316450a87820c` |
| `exp9-images-main.json` | `cb25fedcb3bca47d71e55c9338804145f9b1b043e6a8de55b99b5d8f9e3e791d` |
| `exp10-github-main.json` | `f19a7ab8fa0c5a2b9378c984bd309372e835447b7e782b46205fdc61c87eb105` |
| `exp10-browser-main.json` | `a116d728362996217b330a08fba5e45ddd659b8bc54a76217561b42e888f4d67` |
| `exp10-images-main.json` | `28567ef9ce61b9808b12ef9f431c975daa4386e5279a4072001a5c939fd25362` |
| `main-service-version.json` | `2e84b0171fa66a9871089eb70a45f4bcfb7d2f957f884f5b12d4d8adc21f2545` |
| `main-service-start.json` | `17943cb6c85d192390e235391648528a39c32f0b4f9c73c9ec136df513da3db7` |
| `publication-audit.json` | `060b09b3f5f3a26f06a935b3c48e7aa7de92be50a9eda2f04c78b5c84047e844` |
| `preservation-final.json` | `8a6264f9b9f8e952ec5787eefeb5efda727ee648433c70875a33ebeab9a2d284` |
| `queue-final-preserved.json` | `65dae2982038bb7a8411f2551d5e64e0616e599c6ed25b0a89d56a4be97e79f1` |

초기 통합 worktree의 브라우저 receipt, 이미지 탭 복구 receipt, 최초 담당 진행 카드 관측도 삭제하지 않았다. 최종 main 검증과 이전 세팅/TEST mock을 혼동하지 않는다. 새3개 실제 job은 종료했고 추가 queued/running/unknown 작업이 없다. 담당3명(교대)과 독립 검토의 worker_done 수락·release·idle 확인·자기 탭 정리를 완료했다. 총괄과 읽기 전용 웹만 유지하며 배치를 멈춘다.

## 작업 단위별 커밋 대응

| 로컬 commit | 게시 commit | 작업 |
|---|---|---|
| `019825a8720a149bee2c1e0dfde2fb8d4ae0a716` | `d9351ad94a0321e41dc25a02b98ca80312823cb7` | docs: freeze first VLM batch scope and shared evaluation contract |
| `b25e5f85e75047068876f4b250810c5440520de8` | `08d87c93b51a21caaf2cd8bb08fd07f496c2c224` | feat(vlm): define common strict and fence-only parsing policy |
| `13298359f62c51c4365e07f4c453fff02c1bef86` | `a97ee29be55cc757f1f55bdb0974dbcfd1b7f863` | docs(vlm): record two-model choice and test shared output policy |
| `d7b6acc6019c83d91aaa5d8c8e9e5ae1d6aff74f` | `5ce3f5790b51120619dcfe23832cdfec2c2f35d3` | feat(vlm): assign real batch owners and prepare local input comparison videos |
| `5f317d414b65622139d93f25b91c04ec966cd2ee` | `9c0c094d820bf6c3240f391f9f565b89cf83f913` | chore(vlm): exclude isolated batch environment |
| `f33c439058d23fdb91b05ece1b6462d6c8cf6418` | `851dbc09aa5c02102091ebb54610af38da2b33bc` | Add fixed offline VLM batch command to shared GPU queue |
| `92f447da9339d01a406e9c9b12d7a50966ba6789` | `1d7b198dd01337578bbdf5c42d9af12414af421d` | feat(vlm): prepare pinned Smol native-video batch baseline |
| `5d6ef40c9b54241c57316cb5ff969940622a970e` | `383a4068b6bb5f2bb3c2cb7e9fe832a8f68ba494` | docs(vlm): freeze one Qwen pixel-budget contrast after baseline failures |
| `2af0ec904802436fb65eeca196c57f5ed77710bb` | `dc60421fbf97d23d65d3f7533e1044f918deb03f` | docs(vlm): compare baseline evidence separately from JSON compliance |
| `e0401dd717b7b40fd8d601974d256f817034b22c` | `ecc566928c93b9240b2188a039b9671f24a18e5d` | Record EXP-0008 queued Qwen baseline and measured limitations |
| `73fcfc048c9ecbf114d22a6ad138fb13e064c7fe` | `2b04b1b86c878a4adc4172c17e3d20857e63162d` | feat(delivery): register first real Qwen result and assign pixel contrast |
| `cdfee87a2e8457367736588d73bfa11769ef562c` | `259e6a12a8bfde76b96bc4aad8075c4ebaa8f7f0` | feat(vlm): register one frozen Qwen high-pixel contrast |
| `38cbcb0e7e5439847537fbcd22fdf2715e7642ad` | `351c6732dfad632c373770637d0e01370e3d0410` | docs(vlm): conclude three-condition batch with both candidates on hold |
| `fd607c9d5c5f7611dc3dda86faab774c1b912b8b` | `5be19f98b1e3c511a9bb3cbd3925783fba8e2a04` | docs(vlm): record Smol batch baseline measurements and limitations |
| `d8514c7cabc822d3eac14cd84e560e1bcfd42f2c` | `9d35b06b2653030c2bc75789299d048dfe7c2dfa` | docs(vlm): record queued Qwen pixel-budget contrast and limitations |
| `c357beee2a268eb6a3a71658c0a595fa2015dd72` | `aafbeba44f3c977f273895ecb7a1e2bef7c40ecc` | docs: hand off completed VLM batch and stop further automatic experiments |
| `e15903c79fcbd9d74a9653ed782299af30adbbd0` | `5f01eba425b47a5ff06dad40668cc11118dc36fd` | fix(metrics): bind Smol device memory peak to exact sample |
| `faac4ffdd45773264ca0a86d88deed59e00cac66` | `6fab96e8ef2e36c3b2143eefff512f67be3e73ff` | test(records): preserve historical checks after real result registration |
| `31413919e081a4ab08da150f2d68188b27751e31` | `d85612d2e7eeb0697653ada3b8131d86c89516cf` | feat(delivery): register reviewed Smol and Qwen contrast results |
| `3cc409a324b2f6b389542f2db85d5e21d9aad7b7` | `3f7db593891ea59ea589dcd4931c487d294a0ba9` | docs(review): verify first VLM batch evidence and retain adoption hold |
| `93dede8078f6acbc7029f1c9e7b53c9c6c577b85` | `6acb3abbae5ba6f907cba921961b9e6971eadbce` | docs(delivery): record real GPU batch lifecycle and verification scope |

게시 전 변경42개 파일을 검토했고 미디어/가중치/환경/runtime/원시 결과/인증정보는 제외했다. 최종 확인 문서는 이42개 중 기존 게시 준비 문서 하나만 갱신한다. 실제 배치 실험은 종료됐으며 문서 게시를 위해 모델을 다시 실행하지 않았다.
