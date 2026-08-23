# Formal Project Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修正销售预测大屏的业务口径和性能问题，并建立可在 GitHub 上持续验证的正式项目交付门禁。

**Architecture:** 新增独立的共享 ABC 纯函数，预测器负责门店粒度需求分级，数据服务负责商品粒度需求聚合，Dashboard API 负责跨门店预测聚合。批量预测通过受控线程池并行执行但按输入顺序返回，前端通过显式配置或同源规则解析 API 基地址。

**Tech Stack:** Python 3.11, FastAPI, Pandas, PyTorch, LightGBM, pytest, Ruff, GitHub Actions, 原生 JavaScript。

**Spec:** `docs/superpowers/specs/2026-08-24-formal-project-optimization-design.md`

## Global Constraints

- 保持现有 FastAPI 响应字段和 Docker/Nginx 部署方式不变。
- ABC 使用原始销售数据最近 30 天需求量，A/B/C 累计占比阈值为 70%/90%。
- 批量预测必须限制最大并发数，单项失败不能阻断其他商品和门店。
- CI 必须从干净 checkout 生成数据、训练模型、运行 Ruff 和全部 pytest。
- 不提交原始数据、处理数据、模型文件、日志、密钥或本地环境目录。

---

### Task 1: 添加共享 ABC 分类领域函数

**Files:**
- Create: `backend/common/__init__.py`
- Create: `backend/common/abc.py`
- Test: `backend/tests/test_abc.py`

**Interfaces:**
- Consumes: `Mapping[Hashable, float]` 和可选的累计占比阈值。
- Produces: `classify_abc(values) -> dict[Hashable, str]`，返回与输入键一一对应的 A/B/C 映射。

- [ ] **Step 1: Write the failing tests**

```python
from common.abc import classify_abc


def test_classify_abc_uses_cumulative_thresholds():
    result = classify_abc({"a": 70, "b": 20, "c": 10})
    assert result == {"a": "A", "b": "B", "c": "C"}


def test_classify_abc_handles_zero_and_negative_values():
    assert classify_abc({"a": 0, "b": -1}) == {"a": "C", "b": "C"}


def test_classify_abc_matches_by_key_when_values_are_equal():
    result = classify_abc({"first": 10, "second": 10, "third": 10})
    assert result["first"] == "A"
    assert result["second"] == "A"
    assert result["third"] == "C"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `C:\Users\MR\miniconda3\envs\salesdash\python.exe -m pytest backend/tests/test_abc.py -q`

Expected: FAIL because `common.abc` does not exist.

- [ ] **Step 3: Write the minimal implementation**

Implement `classify_abc` with non-negative normalization, deterministic descending sort, cumulative ratio thresholds, and an all-C result for zero total.

- [ ] **Step 4: Run tests to verify they pass**

Run: `C:\Users\MR\miniconda3\envs\salesdash\python.exe -m pytest backend/tests/test_abc.py -q`

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/common backend/tests/test_abc.py
git commit -m "feat: add deterministic ABC classification"
```

### Task 2: Correct predictor ABC semantics and concurrent batch service

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/ml/predictor.py`
- Modify: `backend/app/services/forecast_service.py`
- Test: `backend/tests/test_predictor.py`
- Test: `backend/tests/test_forecast_service.py`

**Interfaces:**
- Consumes: `common.abc.classify_abc`, `Settings.FORECAST_WORKERS`, existing predictor and forecast service interfaces.
- Produces: stable per-store `abc_class`, stable ordered `get_forecast_all`, isolated per-item failures, and thread-safe predictor singleton initialization.

- [ ] **Step 1: Write tests for the new behavior**

```python
def test_forecast_all_preserves_product_store_order(monkeypatch):
    import app.services.forecast_service as service

    def fake_get_forecast(product_id, store_id):
        return {
            "total_predicted": product_id * 100 + store_id,
            "suggested_purchase": product_id * 100 + store_id + 1,
            "abc_class": "A",
            "forecast": [],
        }

    monkeypatch.setattr(service, "get_forecast", fake_get_forecast)
    products = [
        {"product_id": 2, "product_name": "P2", "category": "服装"},
        {"product_id": 1, "product_name": "P1", "category": "家居"},
    ]
    stores = [
        {"store_id": 2, "store_name": "S2"},
        {"store_id": 1, "store_name": "S1"},
    ]

    result = service.get_forecast_all(products, stores)

    assert [(item["product_id"], item["store_id"]) for item in result] == [
        (2, 2), (2, 1), (1, 2), (1, 1)
    ]


def test_forecast_all_isolates_single_item_failure(monkeypatch):
    import app.services.forecast_service as service

    def fake_get_forecast(product_id, store_id):
        if product_id == 2:
            raise RuntimeError("model unavailable")
        return {
            "total_predicted": 10,
            "suggested_purchase": 11,
            "abc_class": "B",
            "forecast": [],
        }

    monkeypatch.setattr(service, "get_forecast", fake_get_forecast)
    products = [
        {"product_id": 1, "product_name": "P1", "category": "服装"},
        {"product_id": 2, "product_name": "P2", "category": "家居"},
    ]
    stores = [{"store_id": 1, "store_name": "S1"}]

    result = service.get_forecast_all(products, stores)

    assert result[0]["total_predicted"] == 10
    assert result[1]["error"] == "model unavailable"
    assert result[1]["total_predicted"] == 0
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `C:\Users\MR\miniconda3\envs\salesdash\python.exe -m pytest backend/tests/test_predictor.py backend/tests/test_forecast_service.py -q`

Expected: FAIL because the service has no controlled worker setting/order regression tests yet.

- [ ] **Step 3: Implement configured concurrency and predictor changes**

Add `FORECAST_WORKERS` constrained to 1..16, guard predictor singleton creation with a lock, precompute raw recent-demand totals keyed by `(product_id, store_id)`, and classify through the shared function. Replace the serial batch loop with a bounded `ThreadPoolExecutor`, collect each future by key, and emit results in the original product/store order.

- [ ] **Step 4: Run focused tests and existing forecast tests**

Run: `C:\Users\MR\miniconda3\envs\salesdash\python.exe -m pytest backend/tests/test_predictor.py backend/tests/test_forecast_service.py backend/tests/test_forecast.py -q`

Expected: all focused tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/config.py backend/ml/predictor.py backend/app/services/forecast_service.py backend/tests/test_predictor.py backend/tests/test_forecast_service.py
git commit -m "perf: parallelize batch forecasts safely"
```

### Task 3: Make dashboard metrics consistent across stores

**Files:**
- Modify: `backend/app/services/data_service.py`
- Modify: `backend/app/api/dashboard.py`
- Test: `backend/tests/test_dashboard.py`

**Interfaces:**
- Consumes: all-store forecast list and product recent-demand aggregation.
- Produces: Top Product `predicted`/`suggested_purchase` summed across stores and SKU-level ABC distribution based on the documented rule.

- [ ] **Step 1: Add regression assertions**

```python
def test_dashboard_top_product_forecast_is_all_store_sum(client, monkeypatch):
    from app.api import dashboard

    products = [{
        "product_id": 1,
        "product_name": "P1",
        "category": "服装",
        "base_price": 10.0,
    }]
    stores = [
        {"store_id": 1, "store_name": "S1"},
        {"store_id": 2, "store_name": "S2"},
    ]
    forecasts = [
        {
            "product_id": 1,
            "product_name": "P1",
            "category": "服装",
            "store_id": 1,
            "store_name": "S1",
            "total_predicted": 10,
            "suggested_purchase": 11,
            "abc_class": "A",
            "forecast": [],
        },
        {
            "product_id": 1,
            "product_name": "P1",
            "category": "服装",
            "store_id": 2,
            "store_name": "S2",
            "total_predicted": 20,
            "suggested_purchase": 22,
            "abc_class": "B",
            "forecast": [],
        },
    ]
    monkeypatch.setattr(dashboard.data_service, "get_products", lambda: products)
    monkeypatch.setattr(dashboard.data_service, "get_stores", lambda: stores)
    monkeypatch.setattr(dashboard.data_service, "get_total_sales_last_n", lambda days: 30)
    monkeypatch.setattr(dashboard.data_service, "get_recent_product_demand", lambda days: {1: 30})
    monkeypatch.setattr(dashboard.data_service, "load_report", lambda: {"ensemble": {"mape": 10}})
    monkeypatch.setattr(dashboard.data_service, "get_top_products", lambda n: [{
        "product_id": 1, "product_name": "P1", "category": "服装", "sales": 100,
    }])
    monkeypatch.setattr(dashboard.data_service, "get_category_sales", lambda: [{
        "category": "服装", "sales": 100, "ratio": 1.0,
    }])
    monkeypatch.setattr(dashboard.forecast_service, "get_forecast_all", lambda p, s: forecasts)

    result = dashboard.get_dashboard()

    assert result["top_products"][0]["predicted"] == 30
    assert result["top_products"][0]["suggested_purchase"] == 33
```

- [ ] **Step 2: Run the focused dashboard test to verify it fails**

Run: `C:\Users\MR\miniconda3\envs\salesdash\python.exe -m pytest backend/tests/test_dashboard.py -q`

Expected: FAIL against the old store-1-only implementation.

- [ ] **Step 3: Implement product-level aggregation**

Add a cached data-service function for recent product demand, compute product ABC from the shared function, aggregate every successful forecast by `product_id`, and use the aggregate values in Top Product and KPI output while preserving response fields.

- [ ] **Step 4: Run dashboard and inventory tests**

Run: `C:\Users\MR\miniconda3\envs\salesdash\python.exe -m pytest backend/tests/test_dashboard.py -q`

Expected: all dashboard and inventory tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/data_service.py backend/app/api/dashboard.py backend/tests/test_dashboard.py
git commit -m "fix: aggregate dashboard forecasts across stores"
```

### Task 4: Make frontend API base resolution configurable

**Files:**
- Modify: `frontend/js/api.js`
- Modify: `README.md`
- Test: `backend/tests/test_frontend_config.py`

**Interfaces:**
- Consumes: optional `window.API_BASE_URL` and browser location.
- Produces: normalized API base ending in `/api` without duplicate slashes, with explicit configuration taking priority.

- [ ] **Step 1: Add static contract tests**

```python
def test_frontend_supports_explicit_api_base_url():
    source = Path("frontend/js/api.js").read_text(encoding="utf-8")
    assert "API_BASE_URL" in source
    assert "file:" in source
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `C:\Users\MR\miniconda3\envs\salesdash\python.exe -m pytest backend/tests/test_frontend_config.py -q`

Expected: FAIL because the current file has no explicit override.

- [ ] **Step 3: Implement resolution and document it**

Read `window.API_BASE_URL`, trim trailing slashes, retain same-origin fallback, add the `file:` fallback, and document a script-level override example in README.

- [ ] **Step 4: Run the focused test**

Run: `C:\Users\MR\miniconda3\envs\salesdash\python.exe -m pytest backend/tests/test_frontend_config.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/js/api.js README.md backend/tests/test_frontend_config.py
git commit -m "fix: make frontend API endpoint configurable"
```

### Task 5: Add CI, lint configuration, and current metric documentation

**Files:**
- Create: `pyproject.toml`
- Create: `backend/requirements-dev.txt`
- Create: `.github/workflows/ci.yml`
- Modify: `README.md`

**Interfaces:**
- Consumes: existing data initialization and model training scripts.
- Produces: a clean-checkout CI job that generates required artifacts, runs Ruff and pytest, and documented local commands.

- [ ] **Step 1: Add CI configuration and local dev dependency file**

Configure Python 3.11, install runtime and dev dependencies, run `python scripts/init_data.py`, `python scripts/train_models.py`, `ruff check backend/app backend/ml backend/tests scripts`, and `pytest backend/tests -q`.

- [ ] **Step 2: Run the same lint command locally and fix findings**

Run: `C:\Users\MR\miniconda3\envs\salesdash\python.exe -m ruff check backend/app backend/ml backend/tests scripts`

Expected: 0 violations.

- [ ] **Step 3: Update README metrics and CI instructions**

Replace stale fixed metric claims with the current evaluated example and state that generated data/model metrics can change after retraining.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml backend/requirements-dev.txt .github/workflows/ci.yml README.md
git commit -m "ci: add reproducible quality gates"
```

### Task 6: Full verification and GitHub delivery

**Files:**
- Modify: any files needed to resolve verification failures only.

- [ ] **Step 1: Run the full test suite**

Run: `C:\Users\MR\miniconda3\envs\salesdash\python.exe -m pytest backend/tests -q`

Expected: all tests pass with no failures.

- [ ] **Step 2: Run static checks**

Run: `C:\Users\MR\miniconda3\envs\salesdash\python.exe -m ruff check backend/app backend/ml backend/tests scripts`

Expected: 0 violations.

- [ ] **Step 3: Verify runtime endpoints and frontend**

Run the backend and frontend servers, then check `/health`, `/api/products`, `/api/dashboard`, `/api/inventory`, `/api/kpi`, `/api/forecast`, and frontend `/` with HTTP requests. Record status codes and ensure dashboard values are non-empty.

- [ ] **Step 4: Inspect repository for forbidden artifacts**

Run: `git status --short; git diff --check; git ls-files backend/data backend/ml/saved_models backend/logs`

Expected: only intended source, documentation, tests, and CI files are tracked; no generated data, model, log, secret, or whitespace errors.

- [ ] **Step 5: Commit verification fixes if needed**

```bash
git add <only-files-related-to-verification-fixes>
git commit -m "test: finalize project verification"
```

- [ ] **Step 6: Push the feature branch and verify remote state**

```bash
git push -u origin codex/formal-project-optimization
git ls-remote --heads origin codex/formal-project-optimization
```

Expected: the remote branch points to the final local commit.
