# Interview-Ready MVP Implementation Plan

> **For the implementer:** Follow this plan task by task. Keep each change small, run the focused test after each red/green step, and do not rewrite unrelated user changes.

**Spec:** `docs/superpowers/specs/2026-08-27-interview-ready-mvp-design.md`

## Goal

Make the sales forecast dashboard interview-ready without pretending the generated-data MVP is a production system.

## Tasks

### 1. Lock the model/data contracts with failing tests

- Add tests for the seasonal-naive helper, model-info response, data-quality response, and report fallback behavior.
- Run the focused test file and confirm the new expectations fail before implementation.

### 2. Implement model/data credibility

- Add a 7-day seasonal-naive evaluator to `backend/ml/trainer.py`.
- Persist report metadata while keeping legacy metric keys compatible.
- Add data-quality and model-info service/API schemas and routes.
- Update the training summary script for metadata-bearing reports.

### 3. Lock Dashboard filters and frontend contracts with failing tests

- Add API tests for product/store filtering on Dashboard and inventory.
- Add source-contract tests for scope controls, refresh state, and system-status API calls.
- Run focused tests and confirm the new expectations fail before implementation.

### 4. Implement Dashboard interaction states

- Add optional product/store filters to aggregation services and endpoints.
- Add scope controls, refresh behavior, system status, and visible loading/error/empty states.
- Keep the existing trend selectors and default full-scope behavior.

### 5. Rewrite project communication

- Rewrite README around the business case, architecture, model evaluation, honest limitations, and startup steps.
- Add `docs/interview-demo.md` with a 5-minute walkthrough and likely interviewer questions.

### 6. Verify and package

- Run pytest, Ruff, JavaScript syntax checks, `git diff --check`, Docker Compose validation, and live endpoint checks.
- Review the diff for compatibility, privacy, and unsupported claims.
- Commit and push only after the verification evidence is available.
