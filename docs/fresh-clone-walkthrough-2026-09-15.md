# Fresh Clone Walkthrough

这份历史快照证明非作者可以从远程分支开始，按 README 完成初始化、导入、训练、预测、保存、导出和恢复。记录只覆盖本地 Python 运行路径，不替代 Docker 镜像和容器级验收；当前分支的最新测试和 CI 结果以 `docs/releases/v1-acceptance.md` 为准。

## 环境与来源

- Remote branch: `codex/task-001-v1-contract`
- Verified commit: `00f2de80c8adcc38d0fd6592171a420259cb93ea`
- Python: `3.11.15`（临时 Conda 环境）
- Dependency source: `backend/requirements-dev.txt`
- `pip check`: `No broken requirements found.`
- Working copy: fresh `git clone` in a temporary directory; no repository runtime artifacts were reused

## Initialization

```text
python scripts/init_data.py
sales rows: 18100
inventory rows: 100
python scripts/import_sales.py backend/data/raw/sales_data.csv
dataset_id: sales-3211d6464d9c09ab
python scripts/train_models.py
model_id: model-a05f7d2030ad4dc9
```

The generated inventory snapshot was activated as `inventory-5d77f69b6e94a714`. The model package was trained and published against the imported dataset version.

## Automated Gates

```text
python -m pytest backend/tests -q --cov=backend/app --cov=backend/common --cov-fail-under=85
160 passed in 16.73s
Total coverage: 90.54%
python -m ruff check backend scripts
All checks passed!
```

## Runtime Walkthrough

The fresh clone was started with the Python 3.11 environment and a local frontend server:

```text
GET /health                         -> 200, status=healthy
GET /ready                          -> 200
GET /api/forecast?product_id=1&store_id=1 -> 200, 30 forecast points
GET /api/metadata                   -> data=sales-3211d6464d9c09ab, model=model-a05f7d2030ad4dc9, inventory=fresh
GET frontend /                      -> 200
```

A real inventory cell was converted to the documented plan payload:

```text
POST /api/plans                    -> 201
same Idempotency-Key               -> 200, same plan_id=plan-fe1fa90e96424c5fa780dff69c534da5
GET /api/plans/{plan_id}/export    -> 200, CSV downloaded (656 bytes)
```

After creating a second plan, the backend process was stopped and started again. The first plan reopened with its name and one item intact. A historical SQLite copy was then restored with `scripts/restore_plans.py`:

```text
restore_plans.py                    -> plan_count=1
restored first plan                 -> 200
second plan after restore           -> 404
GET /api/plans                      -> 1 plan
```

This is the evidence for AC-045. Docker build/start and injected browser failure scenarios remain separate acceptance items and are not implied by this local walkthrough.
