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
- API 文档地址为 <http://localhost:8000/docs>。

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
- `/api/model-info` 的 `status` 为 `ready`，且包含集成模型与 7 日基线指标。
- `/api/data-quality` 的 `status` 为 `healthy`，当前生成数据应为 18,100 行。
- 筛选后的 Dashboard 只返回商品 1，库存接口只返回商品 1、门店 1。

Linux/macOS 或 Git Bash 还可以运行已有的部署验证脚本：

```bash
bash scripts/verify_deployment.sh http://localhost:8000
```

## 4. 浏览器演示

按以下顺序演示，控制在 60-90 秒：

1. 打开 <http://localhost:3000>，确认页面显示“服务在线”和模型摘要。
2. 先展示全量 KPI、销售趋势、Top 商品和库存风险热力图。
3. 选择一个商品和门店，点击“刷新数据”。
4. 确认 KPI、Top 商品、品类占比和库存热力图同步缩小到筛选范围。
5. 打开 `/api/model-info`，说明时间切分、集成权重和基线。
6. 打开 `/api/data-quality`，说明缺失值、重复、日期断档和负销量检查。
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
- 模型是离线训练，尚未接入定时训练、漂移监控、模型注册和回滚。
- 当前 API 路由默认开放；`API_TOKEN` 是预留扩展点，尚未挂载到路由依赖，不应把它描述成已完成的生产鉴权。
- 公网 URL、域名、TLS、密钥托管、远程监控和 GitHub Actions 实际运行结果需要外部基础设施，本仓库本地检查未覆盖。

停止本地服务：

```bash
docker compose down
```
