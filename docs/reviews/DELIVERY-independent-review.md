# Independent experiment-delivery review

- Date: 2026-10-28.
- Verdict: **needs_revision**. Review execution succeeded; this is not approval of delivery, model comparison, or experiment execution.
- Reviewed baseline: `1c618b5`; implementation frozen at `7f41e0a9be5eedf70c3ccfc3222daa21124fbe21` on `review/experiment-delivery`.
- Supplemental scope: read-only review of coordinator commit `b8f7c082d76ace03a2eab8c2af982db282ee03f9` using `git show`; it was not applied to this worktree. Line references below refer to frozen `7f41e0a`.
- Authority: native task `task_c57455ecf1f8`, dispatch `ctx_2155bbec2e41`. Only this report is modified; integration and any recheck belong to the coordinator.

## Release findings

These are gaps in the approved delivery contract, not requests for additional architecture. P2 means a concrete correctness problem requiring revision before accepting this delivery implementation; none requires running an experiment to repair or verify.

### F1 — P2: changing the attempt bypasses partial-registration immutability

**Source:** `orchestration/complete.py:310–334`, especially the attempt-specific binding path at line 312 and lookup at line 317.

The first write records an immutable binding under an experiment-plus-attempt filename. If the final catalog write fails, the experiment has no catalog row. A retry with a different `attempt_id` looks up a different binding, so it can register a changed package for the same experiment even though the previous partial registration exists. This contradicts COMPLETE_CLI's explicit promise to reject changed payloads after partial failure. The shared lock does not prevent sequential retries from doing this.

**Local validation:** instantiated `tests_orca.test_complete.CompletionTests` in its temporary TEST repository; patched `complete.atomic` to raise only for the catalog write; then retried with `attempt_id='different-attempt'` and a changed summary. The retry returned `registered`, and two binding files existed. No repository records or media were touched. The existing same-attempt retry fixtures do not cover this case.

**Required repair:** persist or discover an experiment-level pending registration identity before accepting another attempt, under the existing lock. Preserve the original binding and allow an identical retry; reject a changed attempt/payload without writes, unless a separately specified recovery operation explicitly authorizes replacement. Add a fixture for interruption followed by changed attempt plus changed package.

### F2 — P2: browser acceptance does not bind the served review to the reviewed local version

**Source:** `orchestration/verify_delivery.py:127–135`, `146–161`; browser probe at `103–104`. Compare the local snapshot checks at `35–43`.

Browser preflight compares only experiment ID, slot, report/metrics hashes, and execution status. A different service repository can serve the same report/metrics with a different review, binding, review status, or native assignment and still claim internally current integrity. The probe requires only nonempty report/review text, and the final snapshot rechecks only local files. Thus the returned local source fingerprints can certify a browser that displayed another review version. This matters when the CLI's config and the running server point at different worktrees, an explicitly relevant acceptance boundary.

**Local validation:** reused the isolated `SeparateAcceptance` fixture, mocked the HTTP response to return a different `review_path`, `review_sha256`, review status, and review body, and mocked a successful browser CLI receipt. `verify_browser` returned `passed=True`. This demonstrates the missing Python comparison; the CLI receipt was deliberately mocked and is not evidence of real browser success. Source inspection confirms the JavaScript performs no expected-review comparison either.

**Required repair:** compare the served review and binding identity/hashes, review/decision state, and assigned lifecycle IDs against the same local snapshot used in the receipt. Verify the selected rendered content belongs to that expected response/version, and recheck the relevant served version after the browser operation. Add negative fixtures with matching report/metrics and a different valid review/assignment. Do not treat `review_integrity='current'` alone as identity with the local snapshot.

### F3 — P2: cards keep their previous observed state during catalog failure

**Source:** `webapp/app.js:232–250`, particularly rendering only inside the fulfilled catalog branch at `239–248`; native freshness predicate at `141–148`.

When a previous successful poll rendered an observed worker, a subsequent catalog request failure prevents both slot and choice cards from rerendering. This remains true when the status request also fails, despite `statusData` being reset and the global status label changing to unverified. The old observed card can remain visible indefinitely during an outage, beyond the native observation's freshness window. The pure `nativeObservation` predicate is appropriately strict but is not applied to the existing cards in this path.

**Local validation:** executed the actual application source in a Node VM, supplied an existing catalog and previous connected status, replaced rendering functions with counters, and made both fetches fail. After `refresh()`, the global label was unverified, while the card render count was zero. The current card fixture tests the selector but not refresh failure behavior.

**Required repair:** refresh task-state presentation using the last available catalog and the current status failure/freshness result even when the new catalog cannot be fetched. Preserve selected media nodes. Add a regression for a previously observed card followed by status/catalog outage and expiration, asserting both slot and result-choice states become unverified.

### F4 — P2: the browser receipt claims a report was opened while it remains collapsed

**Source:** `webapp/app.js:126–134`; `orchestration/verify_delivery.py:103–104,118`.

The report is rendered inside a newly created `<details>` element without `open`. The probe checks the hidden `.original-report` element's `textContent` but never opens its parent details or checks visibility, then returns `report_opened:true`. A normal successful selection therefore satisfies this assertion while the report itself remains hidden. DOM presence is useful evidence but is not the reported action or the contract's actual screen confirmation.

**Validation:** direct source tracing of report creation and the complete browser probe; no real browser was opened by this reviewer. The supplemental `b8f7c08` patch adds a refresh before selection, but does not open this details element or change the unconditional receipt claim.

**Required repair:** expand the selected report's details and verify its visible content before recording `report_opened:true`; otherwise name the observation as DOM presence and leave actual report opening unverified. Add a browser/probe fixture that fails when the report stays collapsed. The coordinator's manual screen observation can be retained separately, but does not make this automatic receipt assertion accurate.

## Checks and boundaries that held

- Registration leaves GitHub and browser acceptance unverified, and status also leaves native lifecycle and artifact availability unverified. Execution, review, and adoption status remain separate fields. Failed/inconclusive experiments can be recorded without being described as successful execution.
- Supplied report/metrics SHA256 values are checked against actual bytes and must occur in the separate review. Existing completed IDs and identical-attempt bindings reject conflicts; identical retries preserve bytes. Failure before catalog publication and exact retries are covered by fixtures. This establishes source linkage, not independent review quality or authentication of the coordinator role.
- The registrar validates evidence IDs/kinds and files beneath the configured allow root, rejects symlinks/traversal/hidden components/special files, and checks media metadata without copying or reading media contents. Public document reads are bounded; duplicate JSON keys and nonfinite measurements are rejected. The existing viewer serves only allowlisted media referenced by the catalog and disables Markdown links/images and raw HTML.
- Historical importer guards run before historical source reads or writes and reject active assignments, nonhistorical results, malformed guards, and symlinks. Its documented offline/nonconcurrent use remains a prerequisite; concurrent historical import was not treated as a newly authorized workflow.
- Native observation selection requires an exact run/task/dispatch match, one matching worker, connected status, and a fresh timestamp. Worker completion is labeled separately from recorded experiment success. F3 concerns applying these checks during polling failure, not the predicate itself.
- GitHub verification checks the expected remote branch commit and compares the target catalog row, assignment, and document bytes against that commit. Its receipt does not claim browser acceptance. Browser verification checks served JavaScript, table values, graph-group counts, registered video playback/seek, and media-node retention; F2 and F4 limit what its current success receipt proves.
- Conservative public text filtering is explicitly not a complete secret scanner. Trusted coordinator publication review remains required. No new credential scanner, native role authentication, automatic model execution, or remote media upload is requested by this review.

## Validation performed

1. Read project instructions, README, project charter, work plan, relevant orchestration/delivery ADRs, EXPERIMENT_DELIVERY, COMPLETE_CLI, DELIVERY_VIEW, all changed implementation files, and relevant fixture/support code.
2. Ran the requested Python command in the existing Orca laboratory environment, bounded with `timeout 90s`: `python -m unittest discover -s tests_orca`. The first sandboxed run showed error/failure markers and timed out with exit 124 before a final traceback summary; it is not counted as a pass. Repeated the same bounded command with approved local socket access: **61 tests passed in 6.898 seconds**, exit 0. A FastAPI/Starlette httpx deprecation warning was emitted; nothing was installed.
3. Ran `timeout 90s node tests_orca/test_cards.js`: **passed**, exit 0.
4. Ran the three bounded synthetic/mocked reproductions described in F1–F3; all demonstrated the stated missing checks. F4 is source-inspection evidence, not an observed browser session.
5. Reviewed supplemental `b8f7c08` by `git show`: refreshing catalog state before selection addresses delayed discovery of newly registered results; preserving typed CLI failures improves diagnosis without printing the complete expression. Its additional fixture and the coordinator's reported five-fixture pass were not rerun against that commit in this frozen worktree. The patch does not resolve F1–F4.
6. Checked the diff for whitespace errors before committing this report. The review creates no code changes, fixture files, or public TEST registrations.

## Delivery accounting and next decision

| Area | This review's conclusion |
| --- | --- |
| Code implementation | Reviewed; needs revision for F1–F4 |
| Actual experiment execution | Not performed; no model, GPU comparison, training, or download |
| GitHub publication | Not verified and no push performed; coordinator-owned |
| Local browser acceptance | Not performed or inferred from fixtures; coordinator-owned |
| Private artifacts | No data, outputs, weights, credential files, or private runtime files read; no cloud image tool used |

The coordinator acknowledged F1–F3 for repair and requested completion of this original review followed by a separate narrow recheck. Retain this report as the frozen-commit finding record; do not silently upgrade its verdict after fixes. A recheck should verify all four repairs with targeted fixtures, then the coordinator should separately retain actual TEST browser and publication receipts, clearly distinguished from the still-unexecuted experiment.
