# Local Demo V2 验收记录

日期：2026-09-22。分支：`codex/task-001-v1-contract`。本记录只汇总本机实际执行过的证据，不替代生产性能验收。

## 已验证

| 范围 | 实际证据 |
| --- | --- |
| 后端质量门禁 | `217 passed`，覆盖率 `85.81%`，Ruff 通过 |
| 默认浏览器回归 | `11 passed, 1 skipped`；跳过项是仅在显式鉴权模式运行的审批 E2E |
| 本地角色审批 | Playwright 鉴权用例 `1 passed`：分析员创建/提交，审批员批准，管理员查看 `submit`/`approve` 审计 |
| 场景与恢复 | 缺货场景可切换；库存过期场景的 `/api/inventory` 返回 `503`；恢复备份后场景回到 `standard` |
| 本地启动 | `scripts/start_demo.ps1 -Root .demo-runtime -BackendPort 18005 -FrontendPort 13005`，启动到 `/health=healthy` 为 `8.40s` |
| API 基线 | Windows 11、Python 3.14.6：`/api/model-info` 100 请求并发 10，成功 `100/100`，p50 `25.52ms`，p95 `138.25ms`，max `144.83ms` |
| 导出基线 | 现有草案 CSV 导出实测 `0.03s` |
| 内存观测 | 同一运行进程工作集约 `386.7MB`；不是固定 4 核/8GB 容器结果 |
| 离线资源 | `python scripts/verify_offline_demo.py --root .demo-runtime` 返回 `ready=true`、无非本机远程引用；资源包包含 15 个生成资源文件 |
| Windows 启动 | GitHub Actions 新增 `Windows Demo Startup`：在 `windows-latest` 准备资源、启动 PowerShell 服务、探活 API/前端并停止 |

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

- 尚未在固定 4 核/8GB 参考机上重新跑完整容量和长期内存趋势。
- 尚未在完全断开外网的机器上执行从首次启动到完整演示的人工复演；当前证据是静态离线依赖检查和无 CDN 资源检查。
- 真实 ERP/WMS、生产身份、定时训练、漂移监控、多实例和队列仍不在 Local Demo V2 范围内。
