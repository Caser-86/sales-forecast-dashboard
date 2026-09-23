# T10 人工断网复演记录

> 这是现场记录模板，不是验收结论。只有在目标机器上实际执行并填写每一项证据后，才可以将 T10 标记为完成。

## 现场信息

| 字段 | 记录 |
| --- | --- |
| 操作人 | |
| 执行日期/时区 | |
| 机器名 | |
| Windows 版本/build | |
| 项目 commit | |
| `demo-manifest.json` SHA-256 | |
| 浏览器版本 | |
| Python 版本 | |
| 网络断开方式 | |

## 现场执行顺序

以下命令只用于把现场状态准备到可记录状态；最终结论仍必须来自人工复演记录和目标机器证据。

### 断网前准备

从仓库根目录执行。在目标参考机联网时，使用新的、受控的演示目录完成准备，不把依赖下载或模型训练计入断网复演：

```powershell
scripts\check_reference_machine.ps1 -ExpectedLogicalProcessors 4 -ExpectedMemoryGB 8 -Strict
python scripts\prepare_demo.py --root .demo-runtime-t10
Get-FileHash .demo-runtime-t10\demo-manifest.json -Algorithm SHA256
$evidenceRoot = ".demo-runtime-t10\logs\t10-acceptance"
New-Item -ItemType Directory -Force $evidenceRoot | Out-Null
Copy-Item -LiteralPath docs\t10-manual-evidence-template.md -Destination (Join-Path $evidenceRoot "manual-replay.md")
```

记录 manifest SHA-256 后，断开外网并在整个 M-01 至 M-10 期间保持断网。不要在断网后运行 `pip install`、`npm install`、模型下载或其他依赖准备命令。

### 断网后启动和复演

```powershell
python scripts\verify_offline_demo.py --root .demo-runtime-t10
scripts\start_demo.ps1 -Root .demo-runtime-t10 -BackendPort 18026 -FrontendPort 13026 -Offline -WithAuth
```

浏览器打开 `http://127.0.0.1:13026`，按下方 M-01 至 M-10 逐项操作，并在复演过程中持续填写证据目录中的 `manual-replay.md`。完成诊断包后停止并重启服务，再打开页面确认计划、审计和活动版本仍可读取；确认后再次停止服务：

```powershell
scripts\stop_demo.ps1 -Root .demo-runtime-t10
scripts\start_demo.ps1 -Root .demo-runtime-t10 -BackendPort 18026 -FrontendPort 13026 -Offline -WithAuth
# 浏览器确认重启后的状态后，再停止服务
scripts\stop_demo.ps1 -Root .demo-runtime-t10
```

人工记录路径为 `.demo-runtime-t10\logs\t10-acceptance\manual-replay.md`。完成并保存人工记录后执行一次 T10 runner；它会运行完整自动回放和 300 秒 benchmark，并将新日志写入同一目录。runner 会保留已存在的人工记录，只在文件不存在时复制空白模板。若目标目录或端口不同，必须在记录中写明实际值。

## 自动门禁

| 检查 | 命令/证据 | 结果 |
| --- | --- | --- |
| 物理 4 核/8GB | `scripts\check_reference_machine.ps1 -ExpectedLogicalProcessors 4 -ExpectedMemoryGB 8 -Strict`；附 `reference-machine.json` | 未填写 |
| T10 runner | `scripts\run_t10_acceptance.ps1 -Root .demo-runtime-t10 -BackendPort 18026 -FrontendPort 13026`；附 `report.json`、`full-replay.log`、`benchmark.log` | 未填写 |
| 外网不可达 | 断网前后记录受控探测结果，不把进程 affinity 当作断网证据 | 未填写 |
| 离线资源 | `python scripts/verify_offline_demo.py --root .demo-runtime-t10`，要求 `ready=true`、`remote_references=[]` | 未填写 |

## 人工业务复演

| 编号 | 操作 | 预期结果 | 实际证据/截图编号 | 结果 |
| --- | --- | --- | --- | --- |
| M-01 | 从干净 `.demo-runtime-t10` 启动本地服务 | 前端、后端健康；无外网依赖 | | 未填写 |
| M-02 | 打开总览并说明业务日期、数据版本、模型版本 | 版本来源明确且页面无伪造实时状态 | | 未填写 |
| M-03 | 上传错误 CSV 并执行预检 | 行级错误可见，上传按钮被阻止，活动版本不变 | | 未填写 |
| M-04 | 上传有效 CSV | 预检通过并保存候选版本，活动版本仍可追溯 | | 未填写 |
| M-05 | 进入预测分析 | 30 天历史与 30 天预测、商品/门店来源和指标口径一致 | | 未填写 |
| M-06 | 进入库存决策并执行 what-if | 原建议、调整数量、原因、策略版本可见 | | 未填写 |
| M-07 | 创建计划并完成角色流转 | 分析员提交、审批员批准、管理员可查看审计事件 | | 未填写 |
| M-08 | 切换 `stale_inventory` 场景 | 库存过期被服务端阻止，不显示假成功 | | 未填写 |
| M-09 | 恢复标准场景和备份 | 恢复后场景、活动版本和计划状态可解释 | | 未填写 |
| M-10 | 生成脱敏诊断包并停止/重启服务 | 诊断包排除敏感信息；重启后数据和计划可恢复 | | 未填写 |

## 性能与收尾

| 项目 | 记录 |
| --- | --- |
| 300 秒 benchmark 报告路径 | |
| API 成功率、p50、p95、峰值工作集 | |
| `working_set_samples` 是否持续增长 | |
| 完整人工复演是否从首次启动开始 | 是 / 否 |
| 是否发生过外网访问或依赖下载 | 是 / 否；如是，说明原因 |
| 操作人签名 | |
| 复核人签名 | |

## 最终结论

- [ ] 物理 4 核/8GB 已由机器检查器和现场配置共同证明。
- [ ] 从首次启动到完整人工演示在完全断网环境完成。
- [ ] 自动化报告、命令输出和人工记录已归档。
- [ ] 未将 affinity、容器限额或脚本回放当作物理/人工验收替代证据。

最终结论：`未填写`
