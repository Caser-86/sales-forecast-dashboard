# 部署与面试前检查清单

这份清单用于在面试前从干净状态启动并验证项目。它只证明本机 Docker Compose 可运行，不代表项目已经完成公网部署。

## 1. 启动前准备

确认以下条件：

- Docker Desktop 正在运行，`docker version` 能返回 Server 版本。
- 仓库根目录是当前目录。
- 如果数据或模型产物不存在，先执行：

```bash
python -m pip install -r backend/requirements-dev.txt
python scripts/init_data.py
python scripts/train_models.py
```

这一步是 GitHub 新克隆场景必需的，因为生成数据和模型文件被 `.gitignore` 排除，且 Compose 会把本机目录挂载进后端容器。

其中 `init_data.py` 会生成并激活 100 个商品/门店组合的 Demo 库存快照；真实数据应使用 `scripts/import_inventory.py`，不要把 Demo 库存当作生产库存证据。

首次需要覆盖 Compose 配置时复制环境模板；不要把生成的 `.env` 提交到 Git：

```bash
# macOS/Linux
cp .env.example .env

# Windows PowerShell
Copy-Item .env.example .env
```

## 2. 启动服务

```bash
docker compose up --build -d
docker compose ps
```

预期结果：

- `sales-backend` 状态包含 `healthy`。
- `sales-frontend` 状态为 `Up`。
- Dashboard 地址为 <http://localhost:3000>。
- API 文档地址为 <http://localhost:8000/docs>（默认 development；production 会关闭文档）。

## 3. API 验收

Windows PowerShell 可以执行：

```powershell
$base = "http://localhost:8000"
Invoke-RestMethod "$base/health" | ConvertTo-Json -Depth 5
Invoke-RestMethod "$base/api/model-info" | ConvertTo-Json -Depth 5
Invoke-RestMethod "$base/api/data-quality" | ConvertTo-Json -Depth 5
Invoke-RestMethod "$base/api/dashboard?product_id=1&store_id=1" | ConvertTo-Json -Depth 5
Invoke-RestMethod "$base/api/inventory?product_id=1&store_id=1" | ConvertTo-Json -Depth 5
```

检查这些结果：

- `/health` 的 `status` 为 `healthy`。
- `/api/model-info` 的 `status` 为 `ready`，且包含发布策略、候选模型、30 天回测与 7 日基线指标。
- `/api/data-quality` 的 `status` 为 `healthy`，当前生成数据应为 18,100 行。
- 筛选后的 Dashboard 只返回商品 1，库存接口只返回商品 1、门店 1。

Linux/macOS 或 Git Bash 还可以运行已有的部署验证脚本：

```bash
bash scripts/verify_deployment.sh http://localhost:8000
```

## 4. 浏览器演示

按以下顺序演示，控制在 60-90 秒：

1. 打开 <http://localhost:3000>，确认页面显示服务状态、版本摘要和模型摘要。
2. 先展示全量 KPI、销售趋势、Top 商品和库存风险热力图。
3. 选择一个商品和门店，点击“刷新数据”。
4. 确认 KPI、Top 商品、品类占比和库存热力图同步缩小到筛选范围。
5. 打开 `/api/metadata`，说明数据、模型版本和库存新鲜度。
6. 打开 `/api/model-info` 与 `/api/data-quality`，说明 60/20/20 时间切分、验证集选择策略、最终 test 回测、基线和数据质量检查。
7. 如果面试官追问失败场景，说明页面会显示错误提示或空结果状态，而不是静默展示旧数据。

## 5. 出错时的最小回退

先收集事实，不要直接点 Docker Desktop 的“Reset to factory defaults”：

```bash
docker compose ps
docker compose logs --tail=100 backend
docker compose logs --tail=100 frontend
```

如果只是服务进程未就绪，可以重启 Compose：

```bash
docker compose restart backend frontend
```

如果健康检查提示数据或模型缺失，重新生成被 Git 忽略的本地产物：

```bash
python scripts/init_data.py
python scripts/train_models.py
docker compose up -d --force-recreate backend
```

## 6. 生产边界

以下内容不由本地检查证明，面试时应主动说明：

- 当前数据由脚本生成，尚未接入真实 ERP/WMS 或数据库。
- 模型是离线训练，尚未接入定时训练、漂移监控和自动回滚；当前提供已发布模型包的手动回滚基础。
- development 默认可不配置 Token；production 必须设置 `API_TOKEN`，当前单租户 API 路由已挂载 Token 依赖。
- 公网 URL、域名、TLS、密钥托管、远程监控和 GitHub Actions 实际运行结果需要外部基础设施，本仓库本地检查未覆盖。

停止本地服务：

```bash
docker compose down
```

## 7. Local Demo V2 最终门禁

Local Demo V2 使用独立的 `.demo-runtime`，不依赖 Docker Desktop。以下命令需要按顺序单独执行，每条命令都会启动并停止自己的服务；完整训练回归会占用 CPU 数分钟。

```powershell
python scripts/prepare_demo.py --root .demo-runtime
scripts\verify_offline_demo.ps1 -Root .demo-runtime -RunBrowserE2E
scripts\verify_offline_demo.ps1 -Root .demo-runtime -RunModelRecoveryE2E
scripts\verify_offline_demo.ps1 -Root .demo-runtime -RunModelStabilityE2E
scripts\verify_offline_demo.ps1 -Root .demo-runtime -RunModelConsistencyE2E
scripts\verify_offline_demo.ps1 -Root .demo-runtime -RunRuntimeRollbackE2E
# 鉴权完整业务回放：错误/有效 CSV、预测、补货、审批、场景、备份恢复和诊断
scripts\verify_offline_demo.ps1 -Root .demo-runtime -RunFullReplayE2E
scripts\benchmark_demo.ps1 -Root .demo-runtime -CpuCores 4 -MemoryBudgetGB 8
# 参考机长期容量/内存趋势（显式关闭限流，输出 working_set_samples）
scripts\benchmark_demo.ps1 -Root .demo-runtime -CpuCores 4 -MemoryBudgetGB 8 -DurationSeconds 300 -DisableRateLimit
# T10 参考机证据包：严格硬件门禁、完整回放和 300 秒容量证据
scripts\run_t10_acceptance.ps1 -Root .demo-runtime
```

预期证据：默认浏览器回归、完整业务回放、失败重试、完整训练期间服务稳定性、候选激活后的跨页面版本一致性和运行快照回滚分别输出明确的 Playwright `passed`；静态离线检查输出 `ready=true` 且 `remote_references=[]`；性能基线输出 `under_memory_budget=true`，长期模式另输出请求持续时间和 `working_set_samples`。`-RunFullReplayE2E` 会在启动前恢复独立演示目录的 `standard` 场景，允许从上次中断状态直接重跑。`run_t10_acceptance.ps1` 会将硬件、回放、容量日志和未填写的人工记录模板集中写入 `.demo-runtime\logs\t10-acceptance`，硬件不匹配时先失败并保留报告。这些命令不能替代固定 4 核/8GB 机器和完全断网人工演示。

## 8. T10 现场门禁

在与目标参考机一致的 Windows 环境执行，详细记录模板见 [`docs/t10-manual-evidence-template.md`](t10-manual-evidence-template.md)：

1. 联网时先在新的受控目录执行严格硬件检查和 `prepare_demo.py`，记录 `demo-manifest.json` SHA-256；准备过程不计入断网人工复演。
2. 断开外网后执行 `verify_offline_demo.py` 静态检查，再用 `start_demo.ps1 -Offline -WithAuth` 启动；从浏览器完成总览、错误/有效 CSV、预测下钻、库存试算、计划审批、过期库存阻止、备份恢复和诊断包全链路。
3. 停止并重启服务，确认活动版本、计划和审计仍可读取；整个 M-01 至 M-10 期间不安装依赖、不下载模型、不访问外部服务。
4. 在服务停止后执行 `benchmark_demo.ps1 -DurationSeconds 300 -DisableRateLimit` 和 `run_t10_acceptance.ps1`，记录启动时间、API p50/p95、工作集峰值和长期采样趋势。
5. 使用 `.demo-runtime\logs\t10-acceptance\manual-replay.md` 逐项记录人工复演、断网方式和证据编号；未完成上述证据前，不将 T10 标记为完成。

参考机开始前先执行严格硬件检查：

```powershell
scripts\check_reference_machine.ps1 -ExpectedLogicalProcessors 4 -ExpectedMemoryGB 8 -Strict
```

当前开发机不满足该严格条件时，命令应失败；这正是预期行为，不能用 affinity 模式的基线替代物理参考机证据。
