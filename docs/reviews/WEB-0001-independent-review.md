# WEB-0001 independent review

2026-11-02. Independent source and regression review of the experiment-first results UI. This reviewer owns only this document; implementation belongs to the frontend and backend workers. No commit, model/GPU work, browser operation, live review-DB write, or service restart was performed by this reviewer.

## Review verdict

**Pass for the reviewed implementation, with extraction coverage limits disclosed below.** The identified status, semantic-preservation, and reference-context regressions are fixed. Source review, final endpoint integration, and focused regressions pass for the generic experiment library, presentation adapter, and source-bound EXP-0049 editorial comparison. This is a code/data-contract review, not browser verification or certification that every report has been editorially rewritten. No unresolved blocking implementation finding remains.

## Findings sent to implementation owners

| Finding | Reproduction / consequence | State |
|---|---|---|
| Review-binding warning disappeared | The catalog report/metric hashes can both match while the independently owned review binding is stale. Removing `review_html` removed the only visible warning for this case. | Fixed: the UI now checks `review_integrity` independently; DOM fixture passed. |
| Selected pending status stopped refreshing | A pending detail initially showing a fresh native status kept it after stale/disconnected/failed polling because only the list refreshed. | Fixed: the pending-status node updates in place without replacing media or review drafts; connected→stale and failed-poll fixtures passed. |
| Semantic inline values disappeared | `_plain` discarded every inline-code token, including `False`, `human_verified=false`, comparisons, and numeric literals. | Fixed: direct regressions preserve those values and inline `0`, `0.125`, and `1234567`. |
| Numeric text mistaken for hashes | `정밀도는 0.1234567 이다. 표본은 1234567 개다.` became `정밀도는 0. 이다. 표본은 개다.` | Fixed: the hash filter preserves numeric measurements/counts. |
| Reference application contexts falsely described as absent | Every reference had an “application context not recorded” fallback, including EXP-0005's explicit description of vendoring the linked official ByteTrack modules. | Fixed: applicable same-paragraph prose is labeled original context; otherwise the adapter says it did not extract a context. It does not verify the external source or independently certify application. |
| Most purpose/change fields unavailable | Across 52 catalog reports, initial extraction returned unavailable purpose for 36 and change for 24; recent unheaded reports such as EXP-0049 contain relevant prose. | Addressed with broader explicit section patterns and labeled source introductions. Missing extraction is now stated neutrally; coverage limitations remain below. |
| Document title captured worker metadata | A title containing “setup” or “fixed input” made following worker/date metadata become the change excerpt. | Fixed: H1 titles do not assign synopsis fields; explicit regression passed. |

## Evidence checked

- The current catalog has 52 unique registered experiments and 46 unique assignments. MVP-0006 is pending; the library includes assignments without results and does not require a role/slot selection.
- Metrics retain their original values, units, sample sizes, and scopes in the full measurement disclosure. The default view graphs up to four recorded metrics individually; null values remain “unmeasured,” distinct from zero. EXP-0049's explicit same-video comparison is reviewed separately below.
- New prose, titles, reference labels, and evidence descriptions use DOM `textContent`; the frontend no longer inserts report/review HTML. Reference destinations have an HTTP(S)/local-path guard, and media uses encoded artifact IDs with the existing server allowlist.
- Playback/review implementation bodies remain unchanged by the UI refactor. The backend change adds a read-only presentation projection to the existing experiment endpoint; existing review-binding checks, media handling, incident endpoints, and DB behavior remain present.
- A byte-for-byte comparison of all **326 tracked files** under `records`, `docs/experiments`, and `docs/reviews` against HEAD found **zero changes**. This includes pre-existing reports, catalog/assignments/metrics, and review bindings. This is repository preservation evidence, not a claim about live runtime DB bytes.

## Content coverage and remaining limits

The generic adapter was exercised against every one of the 52 registered reports. Purpose has 16 direct section excerpts, 32 labeled introductions, and four explicit extraction fallbacks (EXP-0002, EXP-0015, EXP-0038, MVP-0002). Change has 29 direct excerpts, three labeled introductions, and 20 explicit extraction fallbacks; when both fields lack sections, the introduction appears only once, under purpose. These counts describe extraction coverage, not substantive confirmation of purpose or change.

There are 14 external references, seven with explicit original application context. The others state that automatic extraction did not establish context. Short excerpts can omit conditions; the adapter's note makes that limitation explicit. Existing sources remain unchanged and source access/publication belongs to the coordinator. Most experiments are conservative source excerpts, not individually authored narratives.

The coordinator's additional EXP-0049 editorial entry binds to report SHA256 `5a7dd42983f42f8b2267b7e480bcdc2421e276fd70b1d95d0f21d277f0fbe855`. Its purpose/change/limitations match that report. Both 007 and 030 have **2→1 event cards** for EXP-0048→EXP-0049 in the same selected interval; these are separately labeled per-video comparisons, not combined populations or accuracy. The unchanged individual evidence decisions, three-second observation closure, unresolved actual release performance, and risk of false observations prolonging events are supported by the report. Direct checks passed for matching source, changed-source fallback, wrong-experiment fallback, and no input mutation.

The final API integration was tested with actual EXP-0049 repository sources through FastAPI TestClient and a temporary runtime configuration. It returns two editorial comparisons plus all 40 original metrics with current source/review integrity. Mocking a changed report omits the editorial comparison and preserves `report_match=false` / `review_integrity=stale`. A separate DOM check renders two proportional 2→1 graphs while retaining all 40 metric rows. No live DB was used by these checks.

## Executed regressions

Using `/home/jhc7484/dev/sceneguard-orca-lab/.venv-orca-lab/bin/python` with `PYTHONPATH=.:tests`:

```text
python -m unittest tests_orca.test_web tests_orca.test_incident_web \
  test_exp0046_web test_exp0047_web test_exp0048_web test_exp0049_web \
  test_mvp_registration
```

Result: **35 tests passed**. After the final adapter fixes, the same command with `tests_orca.test_presentation` added passed **46 tests**. After final editorial/API integration and path cleanup, adding `tests_orca.test_editorial` passed **47 tests**. These cover presentation semantics/source preservation, safe files/markup, stale review bindings, artifact range serving, registrations, causal state projections, notification claims, review authorization/concurrency/history, and isolated fixture databases. An initial invocation without `tests` on `PYTHONPATH` produced four test-module import errors; the corrected invocation passed without implementation changes. No whole-repository test-pass claim is made.

Eight Node fixture suites passed:

```text
tests_orca/test_experiment_library.js
tests_orca/test_cards.js
tests_orca/test_mvp_web.js
tests_orca/test_incident_web.js
tests_orca/test_incident_review.js
tests_orca/test_exp0047_web.js
tests_orca/test_exp0048_web.js
tests_orca/test_exp0049_web.js
```

The eight suites passed again after the final generic adapter fixes. An additional transient Node DOM check used the real catalog and verified 52 registered cards plus pending MVP-0006, hostile strings remaining text, rejection of `javascript:`/`data:` reference anchors, separate metric graphs, and preservation of null versus zero.

These are DOM/logic fixtures, not a real-browser replay. Browser/service/publication validation and preservation checks for the live review DB and notification receipts belong to the coordinator.

## Reviewed implementation identity

Final review completed 2026-11-02 around 06:21 UTC. `git diff --check` passed. Implementation SHA256 values at this checkpoint:

```text
webapp/app.js           7ee98b0c1941518cd7c3109becd42b51bdb7a439ebb4599e0a8d424abf405a4d
webapp/app.py           4997e3ccfeb07e948f52e121c36ec062471d0dfd9857b39c83bf5f5a643597b5
webapp/presentation.py  d3d6e9b65c6b56be02676f1c4fa426007c135623d4cb7b5ac8816b17f9018aa6
webapp/editorial.py     5405d7363c88c05af9e655dedcd60fa95eedefb6fe27ad44484e49c8ab6d2595
webapp/index.html       89976397c1fc2756eaa7a3ea3e4eaa0ca2926dd2623aaac1a1d201dc361e7aab
webapp/style.css        a55683899ac4f703f1e0a3721060b8302207d14e04097cdf6b3c0b9936d41d4b
```
