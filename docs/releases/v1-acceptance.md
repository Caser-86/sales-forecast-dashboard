# V1 Release Acceptance

## Decision

**Status: NOT READY FOR RELEASE**

This document is the current sign-off record for the interview-ready V1 branch. It is intentionally not a release approval: the acceptance matrix still contains a browser-zoom evidence gap.

## Verified baseline

- Verified code/image commit: `50900f6f32d4eb2ca1afbcfee8ad3a759d9068b5`
- Fresh-clone walkthrough evidence commit: `00f2de80c8adcc38d0fd6592171a420259cb93ea`
- Local full suite: `163 passed`, coverage `90.67%`
- Fresh Python 3.11 clone: `160 passed`, coverage `90.54%`, `pip check` clean
- Fresh clone runtime: `/health=200`, `/ready=200`, 30-point forecast, plan save `201`, idempotent retry `200`, export `200`, restart reopen and SQLite restore verified
- No P0 has been confirmed in the current audit
- Remote GitHub Actions CI: [run 34990694495](https://github.com/Caser-86/sales-forecast-dashboard/actions/runs/34990694495) completed successfully for commit `50900f6`; Quality Gates and Dependency Audit both passed, including the committed Chromium smoke suite (2 tests)
- Local browser evidence for partial failures, XSS, delayed scope changes, timeout/retry/API failure/empty states, and trend interval rendering is recorded in [`docs/browser-acceptance-2026-09-15.md`](../browser-acceptance-2026-09-15.md)
- Docker, image-content, outage, dependency, and constrained performance evidence is recorded in [`docs/deployment-performance-2026-09-15.md`](../deployment-performance-2026-09-15.md) and [`docs/dependency-audit-2026-09-15.md`](../dependency-audit-2026-09-15.md)

## Open exceptions

| Acceptance | Owner | Rationale | Target release | Evidence needed |
|---|---|---|---|---|
| AC-038 | Frontend QA | Desktop/mobile screenshots and a CSS-zoom proxy pass, but the required 200% OS/browser zoom run is not proven | Before first V1 tag | Execute the 200% zoom run on the target browser matrix and attach repeatable screenshots/output |

## Release gate

Do not create a V1 tag or claim production readiness while any row above remains open. A release approver may change the decision only after updating the acceptance matrix with repeatable evidence, the owner’s disposition, and the exact commit or image digest tested.

## Rollback and recovery evidence

The local recovery path is accepted independently of the release decision:

- Sales dataset rollback: `scripts/activate_dataset.py` validates the immutable package and atomically switches the active pointer.
- Model rollback: `scripts/activate_model.py` validates manifest checksums before activation.
- Draft restore: `scripts/restore_plans.py` validates SQLite integrity and atomically replaces the target database.
- Operator walkthrough: [`docs/recovery-runbook.md`](../recovery-runbook.md)
- Fresh clone walkthrough: [`docs/fresh-clone-walkthrough-2026-09-15.md`](../fresh-clone-walkthrough-2026-09-15.md)
- Browser acceptance evidence: [`docs/browser-acceptance-2026-09-15.md`](../browser-acceptance-2026-09-15.md)
