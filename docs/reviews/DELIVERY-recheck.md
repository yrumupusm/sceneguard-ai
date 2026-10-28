# Experiment-delivery F1–F4 recheck

- Date: 2026-10-28.
- Review execution: **succeeded**. Narrow code-review verdict: **F1–F4 resolved; accepted within this recheck scope**. This is not actual browser acceptance, GitHub publication verification, or authorization/evidence of an experiment.
- Exact integrated source: `2d886565a19f7550db009c91137c1699112069f4`.
- Checked worktree HEAD before this report: `daacdc345f75e3c62d1c083c84a6921fa2883b1b`. `git diff --stat 2d88656 HEAD` was empty; both commits have tree `c4bf84cdf2118d44734bbf8c440ee8c4c6648ffa`. All source line references below refer to that identical tree.
- Supplemental read-only inspection: `1f89f920bbc2999238f4d57b0f626cdd1c2b8d51` and `a639352a67428422fe27af7e91ed4fff6f9f9839`, inspected through `git show` after coordinator follow-ups; not applied to this worktree or included in the baseline test counts.
- Native authority: Task `task_178adb28e83c`, Dispatch `ctx_13c04199fc39`, Run `run_3d23462a014a`.
- Ownership: create and commit only this document. Preserve [the original needs_revision review](DELIVERY-independent-review.md); no code, test, HANDOFF, setup-report, or public result edits. Integration and publication remain coordinator-owned.

## Findings and evidence

### F1 — Resolved: immutable reservation survives changed-attempt partial retry

`orchestration/complete.py:310–336` uses the stable `docs/reviews/{experiment_id}.binding.json` path under the existing lock. Its registration digest includes assignment, the entire package (including attempt), artifact mapping, and review hash. A conflicting existing binding is rejected before any binding/config/catalog write; catalog publication remains last. Changing an attempt therefore cannot select a new reservation filename after interruption.

**Locally executed evidence:** `tests_orca.test_complete.CompletionTests.test_catalog_last_partial_failure_and_safe_retry` injects catalog-write failure, checks the result is unregistered, rejects changed attempt plus changed summary with a byte-preservation assertion, and completes the identical retry (`tests_orca/test_complete.py:195–209`). `test_partial_binding_then_config_failure_retry` separately injects config-write failure, rejects changing only the attempt, and permits the original retry (`211–221`). Both passed, along with idempotence, existing-result conflict, and concurrent same-registration fixtures. This resolves the originally reproduced sequential bypass; it does not define an operation to replace completed results or migrate old orphan bindings.

### F2 — Resolved: served and rendered versions are checked against the local snapshot

`orchestration/verify_delivery.py:24–54` snapshots the report, metrics, review, binding, and assignment, including matching native Run/Task/Dispatch IDs. Browser preflight now compares every catalog item field except evidence (compared separately), including review/binding paths, review/decision state and native IDs, with that item. It separately requires the complete four-document `current_source_sha256` map to equal the snapshot fingerprints and requires current integrity (`140–148`).

The server hashes the same report/review/binding sources and metric bytes it reads for the response (`webapp/app.py:138–178`). Selection copies that response's hashes into `detail.dataset.sourceHashes` (`webapp/app.js:77–84`), and the actual probe compares that map to the expected snapshot before report/media acceptance (`orchestration/verify_delivery.py:98–104`). After the browser operation, both the local snapshot and the served experiment response must still equal their initial values (`181–185`).

**Locally executed evidence:** the six `tests_orca.test_verify_delivery` tests passed, including rejection of another server review hash before browser invocation. A supplementary inline Python check reused the temporary `SeparateAcceptance` fixture and added an assigned result: eight individually changed fields (`review_path`, `review_binding_path`, `review_sha256`, `review_status`, `decision_status`, `run_id`, `task_id`, `dispatch_id`) and two individually changed source hashes (review, binding) were all rejected before the mocked browser call. An unchanged mocked receipt reached success; a second served response with changed review status was rejected with `Result changed during browser check`. A separate inline Node VM execution of the real `BROWSER_JS` rejected mismatched rendered `sourceHashes` before report/media checks.

These are synthetic/mocked checks and source tracing, not a real browser receipt. They close the specific cross-worktree review/version gap. The before/after checks are observations, not a transactional lock preventing transient external edits throughout browser execution.

### F3 — Resolved: failed polls invalidate cards without replacing selected media

`webapp/app.js:233–256` now rerenders both slot and result-choice cards from the retained catalog on catalog failure, clears the native status, and labels the retained list as unverified. With a successful catalog and failed status request, the ordinary rendering branch also receives an empty status. Freshness is reevaluated by `nativeObservation` (`142–149`); card rendering applies that predicate (`169–202`). The catalog-failure branch does not rebuild the selected registered result's detail/media. An unchanged successful catalog similarly leaves that detail in place (`224–231`).

**Locally executed evidence:** `node tests_orca/test_cards.js` passed its selector and failed-refresh assertions. Because its refresh fixture replaces renderer functions with counters, a supplementary inline Node VM check exercised the actual `renderSlots`, `renderChoices`, and `refresh` functions against a minimal synthetic DOM with a previously observed assigned result and a retained playing video object. All four cases—both requests fail, catalog alone fails, status alone fails, and successful requests with an expired observation—changed the slot to `미확인`, the choice to `unverified`, and retained the identical selected video object. This proves the code paths and object retention in a fixture, not browser decoding or uninterrupted real playback.

### F4 — Resolved: report disclosure must open before report_opened

`orchestration/verify_delivery.py:105–110` obtains the selected report's disclosure, clicks its summary if closed, scrolls the report into view, and waits for an open disclosure and positive report height. A failed opening throws before the `report_opened:true` receipt at line 126.

**Locally executed evidence:** `node tests_orca/test_browser_probe.js` runs the real extracted probe in an isolated DOM fixture. The opening case returns `report_opened:true`; a summary that leaves the disclosure closed rejects with `Report remains hidden` (`tests_orca/test_browser_probe.js:9–25`). Both assertions passed. Visibility here is the implemented disclosure/layout check; no human visual review or actual browser session was performed by this reviewer.

**Coordinator-requested supplement:** commit `1f89f920bbc2999238f4d57b0f626cdd1c2b8d51` changes only the video readiness line from waiting for `loadedmetadata` to setting `preload='auto'` and waiting for `loadeddata` before `play()`. Commit `a639352a67428422fe27af7e91ed4fff6f9f9839` then strengthens the advancement predicate to `currentTime >= Math.min(.2, duration/2)` while preserving positive width/duration checks and the timeout. Read-only diff inspection confirms both leave the F4 disclosure/open-height guard and F2 version checks intact; no new F1–F4 issue was identified in those two changes. Their real playback effect was not independently measured here, and baseline fixture counts must not be attributed to these supplemental commits.

## Requested validation

Each invocation below was independently bounded by `timeout 90s`; no installation or download was performed. Python denotes the existing `/home/jhc7484/dev/sceneguard-orca-lab/.venv-orca-lab/bin/python`.

| Command after timeout wrapper | Observed final result |
| --- | --- |
| `python -m unittest tests_orca.test_complete -v` | 24 tests passed, 0.576 s, exit 0 |
| `python -m unittest tests_orca.test_verify_delivery -v` | 6 tests passed, 0.010 s, exit 0 |
| `python -m unittest tests_orca.test_web -v` | 8 tests passed, 0.280 s, exit 0, approved local TestClient access |
| `node tests_orca/test_cards.js` | Card-state and failed-poll assertions passed, exit 0 |
| `node tests_orca/test_browser_probe.js` | Report-disclosure acceptance assertions passed, exit 0, approved subprocess access |

The successful requested Python runs total **38 tests**. The supplemental F2 Python and F2/F3 Node checks described above each ran inline under a separate 90-second bound and exited 0; no helper/test files were added.

Failures are retained in this accounting: the first sandboxed web run stalled on `test_fifo_rejected_without_blocking` and ended at its 90-second bound with exit 124, so it is not a pass. The first sandboxed browser-probe fixture exited 1 with `spawnSync python3 EPERM`; the same bounded command passed after approved subprocess access. The web retry emitted the existing Starlette/httpx TestClient deprecation warning. The first sandboxed Orca guide call failed with `UtilBindVsockAnyPort ... socket failed 1`; the same selected CLI worked through approved WSL interop without restarting or resetting Orca.

## Remaining acceptance and handoff

| Domain | This recheck's conclusion |
| --- | --- |
| F1–F4 implementation | Resolved at the exact source SHA above; no unresolved finding within this narrow review |
| Actual experiment | No CV/VLM execution, GPU comparison, training, model download, or new result registration |
| Actual browser acceptance | **Unverified by this reviewer**; coordinator reports successful readiness-adjusted TEST and poll-outage checks, while final-version receipts remain coordinator-owned |
| GitHub publication | **Unverified by this reviewer**; no network publication check or push |
| Private artifacts | No existing private outputs, media, runtime files, credentials, or raw logs read; requested tests used temporary synthetic fixtures |

The dispatch brief reports that actual TEST browser playback passed once before final checks, then later Orca browser playback was immediately paused at time zero without an observed JavaScript pause call. Follow-ups report that waiting for decoded data allowed playback and that an isolated TEST browser acceptance subsequently passed report opening, graph/table, decode/play, seek to 1.5 seconds, retained media node, and matching source/review hashes. The final follow-up also reports actual browser poll-outage invalidation of both cards with the existing video node retained. These are **coordinator-provided observations**, not independently reproduced results or private receipts read by this reviewer. The stronger advancement predicate is now committed as noted above; retain a successful actual browser receipt against the intended final probe/served version before claiming final current browser acceptance. Fixtures above do not substitute for that check.

Next coordinator actions are to integrate this review document, finish and retain final actual browser acceptance, and independently verify the intended GitHub commit/files. Keep implementation acceptance, experiment execution, publication, and local browser confirmation separate in the final delivery message. The original review remains the immutable historical finding record.
