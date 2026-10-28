# EXP-0016 delivery record

Date: 2026-10-28. This note records registration and local viewer checks separately from the frozen execution report.

## Result registration

- Status: `inconclusive` / `blocked` / `adoption_on_hold`.
- Assigned worker: Run `run_3d23462a014a`, Task `task_305549d14771`, Dispatch `ctx_65256d02af82`, effective `gpt-6.1-sol/high`.
- Registered with the existing local completion CLI in slot3. `complete status` reports assignment and registration present, source and review integrity current.
- Final Astra binding addendum: [EXP-0016-final-binding-review](../reviews/EXP-0016-final-binding-review.md). It validates the exact current report/metrics hashes and the blocked-before-inference record only; it is not an output or performance review.
- The web card accurately reports the native worker as failed because preflight stopped at 1590 MiB free (<6144 MiB). No GPU job, model load or inference occurred.

## Actual local viewer check

- Existing page: http://127.0.0.1:8765/ (local only).
- `verify_delivery browser` passed at 2026-10-28T14:45:10Z on browser page `13133f9b-bfcc-49ee-bfac-3f14e95f8472`.
- Confirmed slot3 card, report opened, review opened, six metrics (including unmeasured fields), two graphs, and all four v01–v04 source clips played, sought to 1.5 s and decoded. Video playback remained available after the page's polling refresh.
- The clips are user-reviewed original-only reference inputs, not model outputs or a comparison montage. Local receipt: ignored `runtime/EXP-0016/browser-local.json`.
- This verifies the current local application and local repository data only; it does not establish GitHub publication or behavioral performance.

## Performance state

The prompt change is implemented and software-tested, but behavioral comparison, generation cost, latency, peak VRAM, q/v model responses, and formal behavior metrics remain unmeasured. Keep adoption on hold. Resume only in a new attempt after the unchanged canonical GPU memory gate is satisfied.

## GitHub publication

The standard `git push origin main` could not authenticate in this WSL terminal. The exact local commit trees were published through the connected GitHub Git Data API using a fast-forward update guarded by the previously fetched main SHA. The remote tree matched the local final tracked tree. `verify_delivery github` then passed for remote `main`, independently checking the registered report, metrics, final review and binding SHA-256 values. Its local-only receipt is ignored at `runtime/EXP-0016/github-local-r2.json`. GitHub publication does not indicate local browser verification or behavior performance; those are reported separately above.
