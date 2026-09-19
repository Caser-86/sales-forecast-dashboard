# Repository Cleanup Design

**Date:** 2026-09-19

## Goal

Reduce repository and GitHub clutter without removing current V1 operating evidence, changing application behavior, or rewriting Git history.

## Current Findings

- The active delivery branch is `codex/task-001-v1-contract`.
- The remote branch `codex/formal-project-optimization` is fully reachable from `master`, has no pull request, and contains no commits that need to be preserved separately.
- The five August planning/specification documents are superseded by `docs/superpowers/plans/2026-09-15-project-audit-and-productization.md` and have no references from the active documentation set.
- The current CI workflow, active V1 evidence, release tags, `master`, and the active delivery branch remain relevant.

## Cleanup Scope

### Retain

- `README.md`
- `docs/product-v1.md`
- `docs/interview-demo.md`
- Current acceptance, browser, dependency, deployment, fresh-clone, recovery, and release documents under `docs/`
- `docs/evidence/`
- `docs/superpowers/plans/2026-09-15-project-audit-and-productization.md`
- `.github/workflows/ci.yml`
- `master`, `codex/task-001-v1-contract`, and existing release tags

### Remove From the Working Tree

- `docs/superpowers/plans/2026-08-24-formal-project-optimization.md`
- `docs/superpowers/plans/2026-08-27-interview-ready-mvp.md`
- `docs/superpowers/plans/2026-08-30-interview-delivery-polish.md`
- `docs/superpowers/specs/2026-08-24-formal-project-optimization-design.md`
- `docs/superpowers/specs/2026-08-27-interview-ready-mvp-design.md`

### Remove From GitHub

- Remote branch `codex/formal-project-optimization`

The GitHub repository, default branch, current delivery branch, workflow, tags, and commit history are not deleted or rewritten.

## Safety and Rollback

- Before deletion, verify the five paths are tracked and have no references from retained files.
- Delete the five files in one repository commit so the cleanup is reviewable and reversible.
- Delete only the confirmed obsolete remote branch after the repository commit is pushed.
- If rollback is needed, restore the file paths from the cleanup commit and recreate the remote branch from the preserved commit `b6c3fcf`.

## Validation

1. Confirm no retained file references a removed path or obsolete branch.
2. Run `git diff --check` and the full backend test suite with the repository coverage gate.
3. Run Ruff, frontend JavaScript syntax checks, and Docker Compose validation.
4. Push the cleanup commit and confirm the GitHub Actions Quality Gates and Dependency Audit jobs pass.
5. Confirm the local branch, remote branch, and CI run all point to the same cleanup commit; confirm the obsolete remote branch no longer exists.
