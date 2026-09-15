# 恢复与回滚手册

本文面向单租户 V1 的值班开发者。所有恢复操作都必须先停止写入服务、保留当前版本信息，再执行校验和原子切换。不要直接编辑 `active_*.json`，也不要在服务运行时覆盖 SQLite 文件。

## 0. 操作前检查

在仓库根目录执行：

```powershell
git rev-parse HEAD
Get-Content backend/data/raw/active_dataset.json
Get-Content backend/ml/saved_models/active_model.json
Get-Content backend/data/inventory/active_inventory.json
```

记录输出和当前服务地址。Docker Compose 部署先停后端写入：

```powershell
docker compose stop backend
```

本地 `uvicorn` 进程也必须先停止。恢复完成后再启动服务，并按每个步骤末尾的检查命令核验。

## 1. 销售数据回滚

销售数据版本位于 `backend/data/raw/versions/<dataset_id>`，每个版本包含 `sales_data.csv` 和 `manifest.json`。先列出可用版本并查看 manifest：

```powershell
Get-ChildItem backend/data/raw/versions -Directory
Get-Content backend/data/raw/versions/sales-0123456789abcdef/manifest.json
```

使用已发布的版本 ID 回滚：

```powershell
python scripts/activate_dataset.py sales-0123456789abcdef
```

该命令会重新校验目录、CSV schema、行数、商品/门店数量和日期范围，校验通过后使用原子替换切换 active 指针；失败时不会替换旧指针。然后启动后端并核验：

```powershell
docker compose start backend
Invoke-RestMethod "http://localhost:8000/api/metadata" | ConvertTo-Json -Depth 5
Invoke-RestMethod "http://localhost:8000/api/data-quality" | ConvertTo-Json -Depth 5
Invoke-RestMethod "http://localhost:8000/ready" | ConvertTo-Json -Depth 5
```

确认 `metadata.data_version` 与目标 `dataset_id` 一致，数据质量状态可解释，`/ready` 返回 200 后再恢复流量。旧版本目录不得删除，便于再次回退。

## 2. 模型回滚

模型版本位于 `backend/ml/saved_models/versions/<model_id>`。只使用包含完整 `manifest.json` 和校验文件的已发布目录：

```powershell
Get-ChildItem backend/ml/saved_models/versions -Directory
Get-Content backend/ml/saved_models/versions/model-0123456789abcdef/manifest.json
python scripts/activate_model.py model-0123456789abcdef
```

`activate_model.py` 会校验模型包清单和每个产物的 SHA-256，然后原子替换 active 模型指针。模型文件缺失、为空或校验失败时命令失败，之前的 active 模型保持不变。恢复后核验：

```powershell
Invoke-RestMethod "http://localhost:8000/ready" | ConvertTo-Json -Depth 5
Invoke-RestMethod "http://localhost:8000/api/model-info" | ConvertTo-Json -Depth 8
```

确认 `model_version` 与目标 `model_id` 一致，且 readiness 和模型状态均为可用。模型回滚只回滚模型包，不会自动回滚销售数据；如果两者必须匹配，应先确认目标模型 manifest 的 `data_version`。

## 3. 补货草案备份恢复

`PlanRepository` 每次成功保存草案后，会用 SQLite Online Backup API 更新数据库旁的备份文件：

```text
<DATABASE_URL 对应文件>.bak
```

默认本地路径是 `backend/dashboard.db.bak`。恢复前必须停止后端，并先保留当前库：

```powershell
Copy-Item backend/dashboard.db backend/dashboard.db.before-restore.bak
python scripts/restore_plans.py backend/dashboard.db.bak --database backend/dashboard.db
```

恢复脚本会执行 SQLite `integrity_check`、检查 `plan_drafts` 表、通过 SQLite backup API 写入临时文件、关闭连接后原子替换目标文件，并再次校验草案数量。成功输出包含 `plan_count`；备份无效或数量不一致时不会报告成功。

启动服务并用恢复前记录的 `plan_id` 核验：

```powershell
docker compose start backend
Invoke-RestMethod "http://localhost:8000/api/plans" | ConvertTo-Json -Depth 6
Invoke-RestMethod "http://localhost:8000/api/plans/plan-0123456789abcdef0123456789abcdef" | ConvertTo-Json -Depth 8
```

确认草案名称、明细数量以及 `data_version`、`model_version`、`inventory_version` 和 `policy_version` 与备份记录一致。若恢复结果不符合预期，停止服务并使用 `backend/dashboard.db.before-restore.bak` 按同一脚本恢复。

## 4. 恢复后记录

每次操作至少记录：

- 操作时间、执行人、Git commit 和目标版本 ID。
- 恢复前后的 `data_version`、`model_version`、`inventory_version` 和 `plan_id`。
- `/ready`、`/api/metadata`、`/api/data-quality` 和草案详情的核验结果。
- 失败原因、是否保留原 active 指针，以及是否产生新的人工复核事项。

不要把 `.env`、API Token、运行时数据库、生成数据、模型产物或备份文件提交到 Git。该手册只覆盖当前单机/单租户 V1；远程对象存储、跨主机灾备和容器编排级恢复仍需要部署平台的独立方案。

## 5. 已验证证据

2026-09-15 在 Windows 本地执行了数据版本激活、模型激活和 SQLite 草案恢复回归：

```text
pytest backend/tests/test_dataset_import.py backend/tests/test_plans.py -q
14 passed

CLI walkthrough: dataset rollback active_after_rollback=sales-4cd794ef1e29df51
CLI walkthrough: model=model-ca38ff63a4d80b3d
CLI walkthrough: restore_plan_count=1, restored_summary=before-restore
```

其中包含：损坏 manifest 不切换 active、有效旧版本可重新激活、SQLite 备份完整性校验、数据库原子替换、恢复后草案可读取。Docker 容器级停止/启动演练未在本机完成，因为 Docker Desktop daemon 当前不可用。
