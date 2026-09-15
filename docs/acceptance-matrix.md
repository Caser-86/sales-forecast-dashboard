# V1 Acceptance Matrix

This matrix is the execution checklist for `docs/product-v1.md`. A row is accepted only when the evidence column contains a repeatable test, command output, or manual evidence artifact. A passing unit test that does not exercise the stated boundary is insufficient.

| ID | Area | Acceptance statement | Planned evidence | Current status |
|---|---|---|---|---|
| AC-001 | Scope | V1 is documented as single-tenant demand forecasting and replenishment assistance with human confirmation | `docs/product-v1.md` review | Passed: contract section 1-2 |
| AC-002 | Scope | Automatic ordering, ERP/WMS sync, Agent/RAG, microservices, and multi-tenant roles are explicitly out of scope | Product contract review | Passed: contract section 6 |
| AC-003 | Data | Valid sales CSV passes schema, finite-value, positive-ID, and unique-key validation | `tests/test_dataset_import.py` | Passed: validator and valid import tests |
| AC-004 | Data | Invalid sales input is rejected without changing the active dataset | Import integration test with active-version sentinel | Passed: previous pointer remains unchanged |
| AC-005 | Data | Valid inventory snapshot exposes stock, inbound, reserved, lead-time, policy, and freshness fields | `tests/test_inventory_import.py` | Partial: snapshot contract, immutable import, active pointer, and freshness date are validated; dedicated metadata API remains |
| AC-006 | Data | Sparse product/store combinations are represented as absent or unavailable, never fabricated by a cross product | Dataset and forecast service test | Passed: import manifest preserves source row count |
| AC-007 | Metrics | Quantity is labeled as quantity; monetary value is only shown after quantity-times-price calculation with currency | API schema and frontend contract test | Passed: quantity labels and `unit: "units"` |
| AC-008 | Metrics | Historical 30-day and forecast 30-day windows expose explicit start/end dates and as-of date | API response test | Passed: KPI window contract and regression test |
| AC-009 | Metrics | Top products, category totals, and KPI use one documented time window or clearly state different windows | Aggregation fixtures and UI review | Not started |
| AC-010 | ABC | ABC population is fixed before scope filtering, with deterministic ties and threshold-boundary tests | `tests/test_abc.py`, dashboard fixture | Passed: single-item, dominant-item, tie, zero, and scoped-population tests |
| AC-011 | ABC | ABC is presented as demand priority and is not used alone as stockout risk | Schema/UI copy test | Partial: UI copy and domain wording pass; inventory risk formula remains TASK-016 |
| AC-012 | Forecast | A product/store pair with insufficient history returns unavailable, not zero demand | Forecast API test | Not started |
| AC-013 | Forecast | Forecast recursion updates all required future features from origin-known or previously predicted values | `tests/test_future_features.py` | Partial: shared helper covers calendar/lag/rolling recursion and predictor uses it; feature schema and retraining evidence remain |
| AC-014 | Forecast | Backtest uses identical origins, horizons, scopes, and eligible sample keys for models and baselines | `tests/test_backtest.py` | Partial: leakage-safe rolling kernel and matched model/baseline key tests pass; real model as-of adapter remains |
| AC-015 | Forecast | Report includes horizon, origin count, sample count, per-horizon metrics, and segment metrics | Model report contract test | Not started |
| AC-016 | Forecast | Model complexity does not override a stronger baseline | Model selection test and report review | Not started |
| AC-017 | Intervals | Statistical intervals include target coverage, empirical coverage, calibration window, and sample size | Prediction interval report test | Not started |
| AC-018 | Intervals | If interval calibration is insufficient, UI uses scenario-range wording or hides the interval | Frontend copy test and manual screenshot | Passed: API `range_type=scenario`, UI label, and non-statistical copy are covered |
| AC-019 | Replenishment | Suggested quantity follows net available, lead time, review period, safety stock, pack size, and MOQ | `tests/test_replenishment.py` hand-calculated fixtures | Partial: domain formula and active-snapshot inventory integration pass; user-facing explanation fields remain |
| AC-020 | Replenishment | Missing or stale inventory inputs block a suggestion and identify the missing input | Domain/API test | Partial: import validation rejects missing/invalid fields and domain rejects missing inputs; stale-age enforcement/API error surface remains |
| AC-021 | Replenishment | Lead-time plus review window beyond forecast horizon is rejected | Boundary test | Passed: domain rule rejects a window beyond the forecast horizon |
| AC-022 | Plans | A replenishment draft can be saved, reopened after restart, and exported with immutable version metadata | `tests/test_plans.py` and restore run | Not started |
| AC-023 | Plans | Repeating an idempotency key does not create duplicate drafts | API integration test | Not started |
| AC-024 | Failure semantics | Negative input is `422`, unknown resource is `404`, unavailable dependency is `503`, and all failed forecasts are not represented as zero | API error tests | Passed: forecast/dashboard regression tests |
| AC-025 | Failure semantics | Partial prediction includes requested/succeeded/failed counts and prevents saving an incomplete draft | Service/API/UI tests | Partial: coverage and UI warning pass; save gate is TASK-017 |
| AC-026 | Readiness | Liveness can be healthy while readiness fails for missing, corrupt, or incompatible data/model artifacts | Health tests and container probe | Partial: app tests cover missing/runtime failure; container probe pending Docker daemon |
| AC-027 | Versioning | A dataset/model activation is atomic; interrupted activation leaves the previous active version usable | Artifact lifecycle integration test | Partial: model package validation, atomic active pointer, and failed publish preservation pass; interruption/process-restart evidence remains |
| AC-028 | Versioning | Cache keys and saved results include data/model/policy versions | Cache and plan snapshot test | Partial: forecast cache includes data/model versions; saved plan/policy snapshot is TASK-017 |
| AC-029 | Security | Configured API authentication protects real routers, not only an unused helper | Auth integration tests | Passed: missing token 401 and correct token 200 on `/api/products` |
| AC-030 | Security | Rate limiting has a real enforcement point and returns a documented response when exceeded | Repeated-request integration test | Passed: configured zero limit returns 429 with `Retry-After` |
| AC-031 | Security | No real env file, token, logs, test data, or model artifacts enter the production image | Image content inspection | Pending: Docker Desktop Linux daemon unavailable; context rules pass |
| AC-032 | Security | Untrusted model artifacts are rejected; dependencies are scanned and applicable high-severity findings are handled | Artifact negative test plus dependency report | Partial: tampered package rejection and safe Torch weights loading pass; dependency audit and joblib hardening remain |
| AC-033 | Security | Product/store text is rendered as text or safely escaped in tooltips and exports | XSS fixture test | Partial: all dashboard tooltip paths use shared HTML escaping and static contract tests pass; browser XSS execution evidence remains |
| AC-034 | Frontend | Fast scope changes cannot let an older response overwrite a newer scope | Delayed-request browser test | Partial: dashboard/trend/heatmap request IDs and cancellation guards are implemented; delayed browser evidence remains |
| AC-035 | Frontend | Timeout, CDN failure, API failure, empty data, partial data, stale data, and retry have visible states | Browser E2E test and screenshots | Partial: API timeout classification, cancellation, busy cleanup, and existing empty/partial/error states pass static contracts; browser E2E/CDN evidence remains |
| AC-036 | Frontend | Trend chart handles empty history and draws the intended lower/upper interval band | Chart unit/browser test | Partial: empty-history guard and lower-plus-width band are covered by frontend contract/static checks; browser rendering evidence remains |
| AC-037 | Accessibility | Core selection, refresh, save, and export flow is keyboard reachable and labeled | Browser keyboard test | Partial: controls have labels, visible focus styles, and chart aria labels; browser keyboard evidence remains |
| AC-038 | Responsive | 1920x1080, 1366x768, 390x844, and 200% zoom preserve access to core actions | Browser screenshots and checklist | Partial: mobile stacking/scroll CSS and chart minimum heights are implemented; four-viewport screenshot evidence remains |
| AC-039 | Performance | On a fixed 4-core/8GB reference environment, warm read API P95 <=500ms and cold full dashboard <=10s | Benchmark script output | Not started |
| AC-040 | Performance | Ten concurrent users for five minutes keep error rate below 1% without unbounded memory growth | Load test report | Not started |
| AC-041 | Deployment | Clean clone can install, validate, build, start, and verify without hidden local artifacts | Deployment transcript | Not started |
| AC-042 | Deployment | Readiness failure and backend outage make deployment verification exit non-zero | Fault-injected deployment test | Not started |
| AC-043 | Recovery | Dataset/model rollback and replenishment-draft backup/restore are each exercised once | Recovery runbook evidence | Not started |
| AC-044 | Tests | Core domain/data branches reach at least 85% coverage and critical failure paths are present | Coverage report plus test list | Not started |
| AC-045 | Docs | A non-author developer follows README to import, forecast, save, export, and recover a draft | Fresh-environment walkthrough | Not started |
| AC-046 | Release | No P0/P1 remains open; all exceptions have owner, rationale, and target release | Release sign-off in `docs/releases/` | Not started |

## Current Baseline Evidence

The following are facts from the audit before TASK-001 implementation:

- 82 backend tests passed in 10.33 seconds.
- Ruff, JavaScript syntax checks, Compose config validation, and `pip check` passed.
- No coverage report, browser E2E report, load-test report, complete dependency audit, clean image-content report, or remote CI result has been recorded.
- Read-only fault injection reproduced: configured token without a request header returned 200; missing assets returned HTTP 200 with `degraded`; negative forecast ID returned 500; all forecasts failing returned a normal dashboard with predicted total 0.

These baseline results are retained as evidence for the work items that must change them. They are not acceptance of the corresponding V1 rows.

## Release Gate

The release gate is closed until every `AC-001` through `AC-046` is either evidenced as passed or explicitly removed from V1 by a reviewed update to `docs/product-v1.md`. A status of `Planned`, `Not started`, or `Cannot confirm` is not a pass.
