# 销售数据预测与可视化大屏

一个面向零售补货决策的销售预测 MVP。它把“历史销量、未来 30 天预测、ABC 分级和采购建议”串成一条可演示、可测试、可解释的链路，适合用来展示数据分析、机器学习和全栈工程能力。

> **项目定位**：这是一个使用生成数据的面试演示项目，不是已经接入真实 ERP/WMS 的生产系统。文档会明确区分已验证能力和后续生产化工作。

## 一句话介绍

业务人员选择商品和门店后，可以查看历史销量与未来预测；管理者可以按商品/门店筛选经营范围，观察 KPI、品类结构、Top 商品以及库存风险，并在页面上看到模型和输入数据是否处于可用状态。

## 业务问题

- **补货节奏不稳定**：只看历史销量，无法提前准备未来需求。
- **指标口径容易漂移**：商品预测按门店返回，但大屏 Top 商品需要汇总所有门店。
- **模型结果缺少证据**：只有一个准确率数字，无法解释数据范围、切分方式和基线。
- **Demo 难以复现**：缺少启动命令、健康检查、错误状态和自动化测试。

本项目的 MVP 目标不是追求复杂模型，而是形成一条完整的决策链路：

```text
销售明细 -> 特征工程 -> LSTM + LightGBM -> 30 天预测 -> ABC/采购建议 -> Dashboard
```

## 当前可演示能力

- 预测模型：LSTM + LightGBM 集成，默认权重为 `0.4 / 0.6`。
- 预测评估：MAPE、RMSE，以及“前一周同日”的 7 日季节性朴素基线。
- 数据质量：行数、时间范围、商品/门店数量、缺失值、重复键、日期断档、负销量。
- 大屏交互：商品范围、门店范围、趋势图下钻、刷新按钮、加载/错误/空结果状态。
- 经营视图：KPI、品类销售占比、Top 商品、ABC 库存风险热力图。
- 工程能力：FastAPI、Pydantic Settings、统一异常响应、结构化日志、可选 Token、Docker Compose、自动化测试。

## 架构

```mermaid
flowchart LR
    A[生成或导入销售 CSV] --> B[特征工程]
    B --> C[时间切分 70/15/15]
    C --> D[LSTM]
    C --> E[LightGBM]
    D --> F[集成评估与报告]
    E --> F
    F --> G[FastAPI 服务]
    A --> G
    G --> H[ECharts Dashboard]
```

### 关键设计决策

1. **时间切分而不是随机切分**：避免未来信息进入训练集，训练、验证、测试按日期分为 70%/15%/15%。
2. **保留可比较基线**：模型指标必须和前一周同日基线放在同一份报告里，避免只展示对模型有利的数字。
3. **统一聚合口径**：商品级 Top 预测由所有门店预测结果求和；KPI 的历史销量和预测销量使用同一时间窗口。
4. **批量预测受控并发**：预测服务使用有上限的线程池，并保持商品/门店输入顺序稳定；单个组合失败不会拖垮整个大屏。
5. **数据和模型状态可见**：`/api/data-quality` 与 `/api/model-info` 让页面和面试演示都能回答“这批结果能不能信”。

## 快速开始

### 方式一：Docker Compose（推荐演示）

Docker Compose 会把本机的 `backend/data` 和 `backend/ml/saved_models` 挂载到容器中。首次从 GitHub 克隆时，这些产物不会在仓库里，需要先生成：

```bash
python -m pip install -r backend/requirements-dev.txt
python scripts/init_data.py
python scripts/train_models.py
```

如果这些产物已经存在，可以跳过上面的步骤，直接启动：

```bash
cp .env.example .env
docker compose up --build -d
docker compose ps
```

Windows PowerShell 对应命令为 `Copy-Item .env.example .env`。如果不需要修改配置，也可以直接执行 `docker compose up --build -d`；`.env` 只用于覆盖默认值，不应提交真实 Token。

访问（模板默认 `ENV=development`，便于面试演示）：

- Dashboard：http://localhost:3000
- API 文档：http://localhost:8000/docs（仅非 production 环境开放）
- 健康检查：http://localhost:8000/health
- 模型信息：http://localhost:8000/api/model-info
- 数据质量：http://localhost:8000/api/data-quality

停止服务：

```bash
docker compose down
```

更完整的启动、验收和面试前检查见 [`docs/deployment-checklist.md`](docs/deployment-checklist.md)。

### 方式二：本地运行

Python 3.11 是推荐版本。首次运行或需要重建产物时：

```bash
python -m pip install -r backend/requirements.txt
python scripts/init_data.py
python scripts/train_models.py
```

启动后端：

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

另开终端启动前端：

```bash
cd frontend
python -m http.server 3000
```

### 受控导入销售 CSV

生产或外部样例数据不要直接覆盖 `backend/data/raw/sales_data.csv`。使用导入脚本先校验必需列、类型、重复键、有限数值和负销量策略，再写入不可变版本目录；默认校验成功后切换 active 数据集：

```bash
python scripts/import_sales.py path/to/sales.csv
```

只生成版本、不切换当前 active 数据集：

```bash
python scripts/import_sales.py path/to/sales.csv --no-activate
```

导入销售数据后需要重新生成特征并训练与该数据集匹配的模型。当前模型包版本绑定和原子回滚将在后续成品化任务中补齐；在此之前不要把新导入数据直接用于生产预测。

前端如果不在 `3000` 或 `5500` 端口运行，可以在加载 `js/api.js` 前设置：

```html
<script>window.API_BASE_URL = "http://localhost:8000/api";</script>
```

## 推荐演示路径

1. 打开 Dashboard，先说明默认全量范围和 KPI 口径。
2. 选择一个商品和门店，展示趋势图中的历史、预测和情景范围（不是统计置信区间）。
3. 修改顶部商品/门店范围，说明 KPI、Top 商品、品类和库存热力图同步变化。
4. 点击“刷新数据”，展示按钮忙状态、更新时间和错误提示设计。
5. 打开 `/api/model-info`，解释时间切分、特征数、集成权重和基线。
6. 打开 `/api/data-quality`，解释数据完整性检查和生产环境接入点。
7. 最后主动说明当前边界和下一步，而不是回避 Demo 属性。

正式面试前可直接照着 [`docs/deployment-checklist.md`](docs/deployment-checklist.md) 做一次启动、接口和浏览器验收；完整讲稿见 [`docs/interview-demo.md`](docs/interview-demo.md)。

## 模型评估

本次在仓库生成数据上重新训练得到以下结果；后续重新训练后应以 `backend/data/processed/evaluation_report.json` 和 `/api/model-info` 为准：

| 模型 | MAPE | RMSE |
|---|---:|---:|
| LSTM | 23.55% | 33.40 |
| LightGBM | 8.60% | 21.94 |
| 集成模型（0.4/0.6） | **11.95%** | **16.84** |
| 前一周同日基线 | 35.53% | 79.32 |

这些指标来自生成数据，只能证明当前训练/评估流程可运行，不能直接外推为真实业务效果。真实项目还需要按商品、门店、节假日和促销场景分层评估，并监控预测漂移。

## API 摘要

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 深度健康检查，包含数据、特征、报告和模型文件 |
| GET | `/api/products` | 商品目录 |
| GET | `/api/sales?product_id=1&store_id=1&days=90` | 历史销量 |
| GET | `/api/forecast?product_id=1&store_id=1` | 单商品/门店未来 30 天预测 |
| GET | `/api/dashboard` | 默认全量 Dashboard 聚合 |
| GET | `/api/dashboard?product_id=1&store_id=1` | 指定范围 Dashboard 聚合 |
| GET | `/api/inventory` | 默认全量库存风险热力图 |
| GET | `/api/inventory?product_id=1&store_id=1` | 指定范围库存风险 |
| GET | `/api/model-info` | 模型状态、切分、指标和集成权重 |
| GET | `/api/data-quality` | 输入销售数据完整性检查 |
| GET | `/api/stores` | 轻量门店目录，不触发预测 |
| GET | `/api/metadata` | 数据、模型、库存版本与新鲜度 |
| POST | `/api/plans` | 幂等保存补货草案（需要 `Idempotency-Key`） |
| GET | `/api/plans/{plan_id}` | 查看不可变补货草案 |
| GET | `/api/plans/{plan_id}/export` | 导出补货草案 CSV |

## 测试与质量门禁

```bash
# 全部后端测试
python -m pytest backend/tests -q

# 代码检查
python -m ruff check backend/app backend/common backend/ml backend/tests scripts

# 前端脚本语法检查
# macOS/Linux
find frontend/js -name '*.js' -print0 | xargs -0 -n1 node --check

# Windows PowerShell
Get-ChildItem frontend/js -Recurse -Filter *.js | ForEach-Object { node --check $_.FullName }

# Docker 配置检查
docker compose config --quiet
```

新增能力的测试重点：模型报告兼容旧格式、基线计算使用前一周数据、筛选结果的范围一致性、前端关键控件契约和 API 错误可见性。

## CI

`.github/workflows/ci.yml` 会在 push 和 pull request 中执行以下质量门禁：

- 从空工作区重新生成被 Git 忽略的演示数据、特征和模型产物。
- 运行后端测试与 Ruff 检查。
- 检查 `frontend/js` 下所有 JavaScript 文件的语法。
- 验证 Docker Compose 配置可以解析。

远程是否通过以 GitHub Actions 页面中的实际运行结果为准；本地检查通过不等于已经完成公开部署。

## 项目结构

```text
sales-forecast-dashboard/
├── backend/
│   ├── app/                 # FastAPI、路由、服务、配置、异常和健康检查
│   ├── ml/                  # 数据生成、特征工程、LSTM、LightGBM、训练和预测
│   ├── data/                # raw/processed 数据与评估报告
│   └── tests/               # API、业务聚合、模型辅助函数和前端契约测试
├── frontend/                # HTML、CSS、ECharts 图表和交互逻辑
├── scripts/                 # 数据初始化、训练和部署辅助脚本
├── docs/interview-demo.md   # 5 分钟面试演示稿
├── docker-compose.yml
└── README.md
```

## 诚实的生产化边界

当前未实现或未声称实现：

- 真实 ERP/WMS 数据接入、增量同步和数据库存储。
- 定时训练、模型注册、灰度发布和回滚。
- 预测漂移、数据漂移和分层业务告警。
- 多用户登录、权限模型和生产密钥托管；V1 使用单租户 API Token。
- 多副本部署、队列化推理和完整可观测性平台。

下一阶段可以按风险优先级推进：先接入真实数据并建立数据契约，再补定时训练与漂移监控，最后完善鉴权、队列和部署可观测性。

## 环境变量

后端配置位于 `backend/app/core/config.py`。本地直接运行 FastAPI 时可使用 `backend/.env` 或环境变量覆盖；使用 Docker Compose 时，根目录 `.env` 会由 Compose 注入容器。可以从 `.env.example` 开始：

| 变量 | 默认值 | 用途 |
|---|---|---|
| `ENV` | `development` | 运行环境 |
| `DEBUG` | `false` | 调试开关 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `CORS_ORIGINS` | 本地前端地址 | CORS 白名单 |
| `API_TOKEN` | 空 | 开发环境可为空；生产环境必须配置并保护 API 路由 |
| `API_TOKEN_HEADER` | `X-API-Token` | Token 请求头名称 |
| `FORECAST_DAYS` | `30` | 预测周期 |
| `FORECAST_WORKERS` | `4` | 批量预测最大并发数 |

## 版本信息

- 仓库：[Caser-86/sales-forecast-dashboard](https://github.com/Caser-86/sales-forecast-dashboard)
- 当前文档对应分支：`codex/formal-project-optimization`
