# V1 Release Acceptance

## Decision

**Status: READY FOR V1 INTERVIEW RELEASE**

This document is the current sign-off record for the interview-ready V1 branch. The V1 acceptance gate is closed; this is not a claim of production readiness because the project still uses generated demo data and retains production-only work outside the V1 boundary.

## Verified baseline

- Verified code/image commit: `d3cded008385a47e6cc062a4f7a8a316eccf9edc` (real Chrome 200% verifier and evidence)
- Fresh-clone walkthrough evidence commit: `00f2de80c8adcc38d0fd6592171a420259cb93ea`
- Current branch head: `14cbe707c49eefbb39148a18d81a998119db5e34` (evidence-driven cleanup)
- Local full suite: `163 passed`, coverage `90.71%`
- Fresh Python 3.11 clone: `160 passed`, coverage `90.54%`, `pip check` clean
- Fresh clone runtime: `/health=200`, `/ready=200`, 30-point forecast, plan save `201`, idempotent retry `200`, export `200`, restart reopen and SQLite restore verified
- No P0 has been confirmed in the current audit
- Remote GitHub Actions CI: [run 35060519865](https://github.com/Caser-86/sales-forecast-dashboard/actions/runs/35060519865) completed successfully for the current branch head; Quality Gates and Dependency Audit both passed, including the committed Chromium smoke suite (2 tests)
- Local browser evidence for partial failures, XSS, delayed scope changes, timeout/retry/API failure/empty states, and trend interval rendering is recorded in [`docs/browser-acceptance-2026-09-15.md`](../browser-acceptance-2026-09-15.md)
- Real Google Chrome 200% evidence: [`browser-zoom-200-2026-09-16.json`](../evidence/browser-zoom-200-2026-09-16.json) and [`browser-zoom-200-2026-09-16.png`](../evidence/browser-zoom-200-2026-09-16.png)
- Docker, image-content, outage, dependency, and constrained performance evidence is recorded in [`docs/deployment-performance-2026-09-15.md`](../deployment-performance-2026-09-15.md) and [`docs/dependency-audit-2026-09-15.md`](../dependency-audit-2026-09-15.md)

## Open exceptions

No open exceptions remain for the interview-ready V1 scope. Production-only items remain governed by [`docs/product-v1.md`](../product-v1.md).

## Release gate

The interview-ready V1 gate is satisfied by the acceptance matrix and attached evidence. This approval does not claim production readiness or authorize automatic purchasing actions.

## Rollback and recovery evidence

The local recovery path is accepted independently of the release decision:

- Sales dataset rollback: `scripts/activate_dataset.py` validates the immutable package and atomically switches the active pointer.
- Model rollback: `scripts/activate_model.py` validates manifest checksums before activation.
- Draft restore: `scripts/restore_plans.py` validates SQLite integrity and atomically replaces the target database.
- Operator walkthrough: [`docs/recovery-runbook.md`](../recovery-runbook.md)
- Fresh clone walkthrough: [`docs/fresh-clone-walkthrough-2026-09-15.md`](../fresh-clone-walkthrough-2026-09-15.md)
- Browser acceptance evidence: [`docs/browser-acceptance-2026-09-15.md`](../browser-acceptance-2026-09-15.md)
