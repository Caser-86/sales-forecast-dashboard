# Local Demo V2 验收记录

日期：2026-09-22。分支：`codex/task-001-v1-contract`。本记录只汇总本机实际执行过的证据，不替代生产性能验收。

## 已验证

| 范围 | 实际证据 |
| --- | --- |
| 后端质量门禁 | `226 passed`，覆盖率 `85.94%`，Ruff 通过 |
| 默认浏览器回归 | `13 passed, 5 skipped`；跳过项是两条显式鉴权审批、模型恢复、普通完整训练一致性和运行快照回滚 E2E |
| T2 页面分页 | 数据中心版本清单、预测商品目录、库存风险清单、模型版本/任务和计划历史均有分页；库存页真实浏览器回归完成第 1/5 页与第 2/5 页切换，空态/刷新重置有契约覆盖 |
| T6/T7 页面回归 | 默认离线浏览器回归中的预测/库存用例通过：商品目录分页、30 天历史与预测、MAPE 口径、安全 CSV、风险筛选和服务端包装/MOQ 试算均有真实页面断言 |
| T7 策略审计 | `plan_events` 保存 `policy_version`；旧事件表迁移回填策略版次，计划详情、导出和审批事件保持同一不可变策略来源 |
| 本地角色审批 | Playwright 鉴权用例 `1 passed`：分析员创建/提交，审批员批准，管理员查看 `submit`/`approve` 审计 |
| T8 并发审批 | Playwright 鉴权用例 `2 passed`：双审批页读取同一版次，一个批准后另一个驳回收到乐观锁冲突；重复批准不重复写审计事件 |
| 场景与恢复 | 缺货场景可切换；库存过期场景的 `/api/inventory` 返回 `503`；恢复备份后场景回到 `standard` |
| 本地启动 | `scripts/start_demo.ps1 -Root .demo-runtime -BackendPort 18005 -FrontendPort 13005`，启动到 `/health=healthy` 为 `8.40s` |
| API 基线 | Windows 11、Python 3.14.6：`/api/model-info` 100 请求并发 10，成功 `100/100`，p50 `25.52ms`，p95 `138.25ms`，max `144.83ms` |
| 导出基线 | 现有草案 CSV 导出实测 `0.03s` |
| 内存观测 | 同一运行进程工作集约 `386.7MB`；不是固定 4 核/8GB 容器结果 |
| 离线资源 | `python scripts/verify_offline_demo.py --root .demo-runtime` 返回 `ready=true`、无非本机远程引用；资源包包含 15 个生成资源文件 |
| Windows 启动 | GitHub Actions 新增 `Windows Demo Startup`：在 `windows-latest` 准备资源、启动 PowerShell 服务、探活 API/前端并停止 |
| 离线运行时冒烟 | `scripts/verify_offline_demo.ps1` 在 Windows 本机通过；进程内外部 DNS 被守卫阻断，健康、商品、模型、库存和前端探活均通过；追加 `-RunBrowserE2E` 后浏览器回归 `13 passed, 5 skipped` |
| 训练恢复浏览器回归 | `scripts/verify_offline_demo.ps1 -RunModelRecoveryE2E` 在进程级离线守卫下通过 `1 passed (58.1s)`；真实 worker 首次失败、第二次进入候选训练并完成候选模型人工激活；使用显式非生产 `smoke` 训练档案 |
| 普通完整训练版本一致性 | `scripts/verify_offline_demo.ps1 -RunModelConsistencyE2E` 通过 `1 passed (3.6m)`；页面真实完成完整 CPU 训练、候选激活后，总览、数据、预测、库存和系统页展示同一模型版本 |
| 普通完整训练稳定性 | `scripts/verify_offline_demo.ps1 -RunModelStabilityE2E` 通过 `1 passed (3.7m)`；训练期间持续探测健康、模型、商品、库存和元数据接口，活动模型版本保持不变 |
| 运行快照发布/回滚 | `scripts/verify_offline_demo.ps1 -RunRuntimeRollbackE2E` 通过 `1 passed (12.1s)`；候选发布/激活、回滚和回滚后跨页面活动版本一致性均通过 |
| T8 持久化与来源保护 | `test_persistence_migration.py`、`test_plan_workflow.py` 通过；旧版 `plan_drafts` 迁移前生成 `.migration.bak`，工作流/会话可在服务重载后恢复，过期库存或版本漂移审批返回 `409 CONFLICT` |
| 4 核亲和性基线 | `scripts/benchmark_demo.ps1` 使用 4 核 CPU affinity：启动 `8.75s`，API `100/100`，p50 `23.96ms`，p95 `150.15ms`，工作集 `413.1MB`，低于 8GB 观测预算 |
| 参考机物理条件前置检查 | 当前开发机实测 `16` 逻辑处理器、`23.29GB` 内存；`scripts/check_reference_machine.ps1 -Strict` 按预期以退出码 `1` 拒绝，未把 affinity 观测冒充物理 `4 核/8GB` 验收 |

## 2026-09-23 补充证据

- 全量后端回归：`230 passed`，覆盖率 `86.00%`，Ruff、96 个前端 JavaScript 文件语法检查、Compose 配置和离线资源检查均通过。
- 鉴权完整回放：在保留历史计划且先切换到 `stale_inventory` 的运行目录上执行 `scripts\verify_offline_demo.ps1 -RunFullReplayE2E`，脚本自动恢复 `standard` 场景，Playwright `1 passed (12.4s)`；输出 `offline_guard=true`、健康状态 `healthy`、20 个商品和 100 个库存单元。随后使用独立端口重跑，Playwright `1 passed (12.5s)`，服务自动停止且未留下 `demo-process.json`。
- 当前开发机 affinity 短基线：4 核 affinity、100 请求/10 并发，成功 `100/100`，p50 `29.89ms`，p95 `133.41ms`，峰值工作集 `412.7MB`，启动 `8.05s`。这仍是进程/亲和性观测，不是物理参考机验收。
- 当前开发机 300 秒 affinity 趋势：4 核 affinity、`92,723/92,723` 请求成功，错误率 `0`，p50 `31.96ms`、p95 `36.47ms`、max `202.91ms`，启动 `7.58s`，峰值工作集 `424.1MB`，`under_memory_budget=true`。采样期间工作集从 `414.1MB` 稳定到 `424.1MB`；这仍是进程/亲和性观测，不是物理参考机验收。
- T10 证据入口：`scripts\run_t10_acceptance.ps1` 已验证会在物理条件不匹配时先停止；当前主机报告 `ready=false`、16 逻辑处理器、23.29GB 内存，报告保存于 `.demo-runtime\logs\t10-acceptance\report.json`。
- 容器隔离补充 smoke：`scripts\run_container_isolation_smoke.ps1` 在 Docker internal network 中启动独立前后端，前端容器页面响应 `28020` 字节、后端健康返回 `healthy`、演示认证状态为 `enabled=true`，后端访问 `https://example.com` 以退出码 `6` 被阻断；两个容器的 Docker 限额均为 `4 CPU / 8 GiB`。该证据不包含宿主机浏览器回放，也不关闭物理参考机或人工完全断网门禁。

## 面试现场入口

```powershell
python scripts/prepare_demo.py --root .demo-runtime
scripts\start_demo.ps1 -Root .demo-runtime
# 需要演示角色审批时：
scripts\stop_demo.ps1 -Root .demo-runtime
scripts\start_demo.ps1 -Root .demo-runtime -WithAuth
```

角色账号见 [README](../README.md)。系统页可以切换五种确定性场景，创建/恢复备份并生成脱敏诊断包；`scripts/package_demo.py` 生成的资源包不包含数据库、日志、任务和会话。

## 尚未宣称

- 当前机器是 8 核/16 线程、23.29GB 内存；已完成 4 核 affinity 和 8GB 进程工作集预算观测，但尚未在物理固定 4 核/8GB 参考机上重新跑完整容量和长期内存趋势。
- 已完成进程级离线网络守卫下的本地运行时冒烟；尚未在完全断开外网的机器上执行从首次启动到完整人工演示，首次安装依赖的完全离线分发也不在本轮范围。
- 真实 ERP/WMS、生产身份、定时训练、漂移监控、多实例和队列仍不在 Local Demo V2 范围内。
