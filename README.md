# 销售数据预测与可视化大屏

基于 LSTM + LightGBM 集成模型的销售预测系统，配备暗紫色科技风可视化大屏。

[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/Tests-61%20passed-brightgreen)]()
[![License](https://img.shields.io/badge/License-MIT-yellow)]()

---

## 目录

- [项目简介](#项目简介)
- [技术栈](#技术栈)
- [目录结构](#目录结构)
- [快速开始](#快速开始)
- [环境变量说明](#环境变量说明)
- [数据库说明](#数据库说明)
- [测试说明](#测试说明)
- [构建说明](#构建说明)
- [部署说明](#部署说明)
- [API 文档](#api-文档)
- [用户使用说明](#用户使用说明)
- [管理员说明](#管理员说明)
- [故障排查](#故障排查)
- [常见问题](#常见问题)
- [已知限制](#已知限制)
- [版本说明](#版本说明)
- [后续维护建议](#后续维护建议)

---

## 项目简介

面向中小零售运营团队的**内部数据可视化系统**。提供历史销量分析、未来 30 天销售预测、库存分级与采购建议。

### 核心业务流程

1. **数据初始化**：生成模拟销售数据（20 SKU × 5 门店 × 181 天）
2. **模型训练**：LSTM（时序）+ LightGBM（表格）集成，MAPE ≈ 9.91%
3. **大屏加载**：KPI / 趋势图 / 库存热力图 / 品类占比 / Top 10 排行
4. **商品切换**：查看单 SKU 历史销量与未来预测
5. **采购决策**：基于 ABC 分级与建议采购量

### 正式用户

- **主要**：零售运营经理 / 商品采购员（只读查看大屏）
- **次要**：数据工程师（维护模型与数据）

---

## 技术栈

| 层 | 技术 | 版本 |
|---|---|---|
| 后端 | Python / FastAPI / Pydantic | 3.11 / 0.115 / 2.10 |
| 机器学习 | PyTorch (LSTM) / LightGBM / scikit-learn | 2.5 / 4.5 / 1.6 |
| 配置管理 | pydantic-settings | 2.7 |
| 数据处理 | Pandas / NumPy | 2.2 / 1.26 |
| 前端 | 原生 HTML/CSS/JS + ECharts 5 | 5.x |
| 部署 | Docker / docker-compose / nginx | - |
| 测试 | pytest / pytest-asyncio / httpx | 8.3 / 0.25 / 0.28 |

---

## 目录结构

```
销售数据预测与可视化大屏/
├── backend/
│   ├── app/
│   │   ├── core/              # 配置 / 日志 / 异常 / 中间件 / 健康 / 安全
│   │   ├── api/               # 路由：products / sales / forecast / dashboard
│   │   ├── services/          # 业务服务：data / forecast / inventory
│   │   ├── config.py          # 兼容层（重新导出 app.core.config）
│   │   ├── main.py            # FastAPI 应用入口
│   │   └── schemas.py         # Pydantic 响应模型
│   ├── ml/                    # 机器学习
│   │   ├── data_generator.py  # 模拟数据生成
│   │   ├── feature_engineering.py
│   │   ├── lstm_model.py
│   │   ├── lightgbm_model.py
│   │   ├── trainer.py         # 训练脚本
│   │   ├── predictor.py       # 预测器
│   │   └── saved_models/      # 已训练模型（不入库）
│   ├── data/                  # 数据目录（不入库）
│   │   ├── raw/               # sales_data.csv
│   │   └── processed/         # features.csv / evaluation_report.json
│   ├── tests/                 # 测试套件（61 个用例）
│   ├── logs/                  # 运行时日志（不入库）
│   ├── .env.example
│   ├── Dockerfile
│   ├── pytest.ini
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── css/dashboard.css
│   ├── js/
│   │   ├── api.js             # 接口封装
│   │   ├── dashboard.js       # 主逻辑
│   │   └── charts/            # 5 个 ECharts 图表
│   └── Dockerfile
├── scripts/
│   ├── init_data.py           # 数据初始化
│   ├── train_models.py        # 模型训练
│   ├── verify_deployment.sh   # 部署后验证
│   └── deploy.sh              # 部署脚本
├── .dockerignore
├── .gitignore
├── docker-compose.yml
├── nginx.conf
└── README.md
```

---

## 快速开始

### 前置要求

- Python 3.11+
- pip 23+
- （可选）Docker 20+ / docker-compose

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 初始化数据与训练模型

```bash
# 从项目根目录运行
python scripts/init_data.py       # 生成 sales_data.csv（18100 行）
python scripts/train_models.py    # 训练 LSTM + LightGBM，保存到 saved_models/
```

### 3. 配置环境变量

```bash
cd backend
cp .env.example .env
# 按需修改 .env
```

### 4. 启动后端

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

访问 http://localhost:8000/docs 查看 API 文档。

### 5. 启动前端

```bash
cd frontend
python -m http.server 3000
```

访问 http://localhost:3000 查看大屏。

---

## 环境变量说明

所有配置通过 `.env` 文件或环境变量管理。参考 [backend/.env.example](backend/.env.example)。

| 变量 | 默认值 | 说明 |
|---|---|---|
| `ENV` | `development` | 运行环境：`development` / `production` / `test` |
| `DEBUG` | `false` | 调试模式，生产必须 `false` |
| `HOST` | `0.0.0.0` | 监听地址 |
| `PORT` | `8000` | 监听端口 |
| `CORS_ORIGINS` | `http://localhost:3000,...` | CORS 白名单，逗号分隔 |
| `API_TOKEN` | （空） | 可选 API Token，留空则不启用认证 |
| `API_TOKEN_HEADER` | `X-API-Token` | Token 请求头名 |
| `LOG_LEVEL` | `INFO` | 日志级别：`DEBUG`/`INFO`/`WARNING`/`ERROR` |
| `LOG_DIR` | `logs` | 日志目录 |
| `LOG_FILE_MAX_BYTES` | `10485760` | 单个日志文件最大字节数 |
| `LOG_FILE_BACKUP_COUNT` | `5` | 保留日志文件数 |
| `FORECAST_DAYS` | `30` | 预测天数 |
| `LSTM_SEQ_LEN` | `14` | LSTM 输入序列长度 |
| `RATE_LIMIT_ENABLED` | `true` | 启用限流 |
| `RATE_LIMIT_REQUESTS` | `100` | 限流请求数 |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | 限流时间窗口 |

**重要**：生产环境务必修改 `CORS_ORIGINS` 为实际域名，避免使用 `*`。

---

## 数据库说明

当前项目**未启用数据库**，使用 CSV 文件存储数据：

- `backend/data/raw/sales_data.csv`：原始销售数据（18100 行）
- `backend/data/processed/features.csv`：特征工程结果（16700 行）
- `backend/data/processed/evaluation_report.json`：模型评估报告

`DATABASE_URL` 配置项保留为扩展点，未来如需数据库可平滑迁移。

### 数据初始化

```bash
python scripts/init_data.py
```

生成 20 商品 × 5 门店 × 181 天的模拟数据，包含周末效应、促销效应、节假日效应。

---

## 测试说明

### 运行所有测试

```bash
cd backend
python -m pytest tests/ -v
```

### 测试覆盖

| 测试文件 | 用例数 | 覆盖范围 |
|---|---|---|
| `test_health.py` | 4 | 健康检查与根路径 |
| `test_products.py` | 4 | 商品列表接口 |
| `test_sales.py` | 6 | 历史销量 + 错误场景 |
| `test_forecast.py` | 6 | 预测接口 + ABC 分级 |
| `test_dashboard.py` | 9 | 大屏聚合 + 库存 + KPI |
| `test_security.py` | 7 | CORS + 中间件 + 错误处理 |
| `test_config.py` | 9 | 配置系统 |
| `test_data_generator.py` | 16 | ML 数据生成器 |
| **合计** | **61** | **全部通过** |

### 测试策略

- **集成测试**：使用 FastAPI TestClient，无需启动真实服务器
- **错误场景**：覆盖 404、422、缺失参数、非法 ID
- **ML 单元测试**：验证数据生成可复现性、字段完整性、边界值

---

## 构建说明

### Docker 构建

```bash
# 构建后端镜像
docker build -t sales-backend:latest ./backend

# 构建前端镜像
docker build -t sales-frontend:latest ./frontend

# 或一键构建
docker-compose build
```

### 镜像优化

- 使用 `python:3.11-slim` 基础镜像
- 多阶段安装依赖
- 非 root 用户运行
- `.dockerignore` 排除测试/日志/缓存

---

## 部署说明

### Docker Compose 部署（推荐）

```bash
# 1. 准备环境变量
cp backend/.env.example backend/.env
# 编辑 .env，设置 ENV=production、CORS_ORIGINS 等

# 2. 启动服务
docker-compose up -d --build

# 3. 验证部署
bash scripts/verify_deployment.sh http://localhost:8000

# 4. 查看日志
docker-compose logs -f backend

# 5. 停止
docker-compose down
```

### 裸机部署

```bash
# 后端（推荐用 gunicorn 或 systemd 托管）
cd backend
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000

# 前端（用 nginx 提供静态文件）
sudo cp -r frontend/* /var/www/dashboard/
sudo cp nginx.conf /etc/nginx/conf.d/dashboard.conf
sudo nginx -s reload
```

### 回滚方案

```bash
# Docker 回滚到上一版本
docker-compose down
docker tag sales-backend:latest sales-backend:rollback
docker pull sales-backend:previous
docker-compose up -d

# 裸机回滚
git checkout <previous-commit>
pip install -r backend/requirements.txt
sudo systemctl restart sales-backend
```

### 部署后验证

```bash
bash scripts/verify_deployment.sh http://<部署地址>:8000
```

脚本检查 9 个端点（含 1 个错误场景），全部通过才算部署成功。

---

## API 文档

启动后端后访问 http://localhost:8000/docs 查看交互式文档。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 根路径状态 |
| GET | `/health` | 深度健康检查（含依赖检查） |
| GET | `/api` | API 端点列表 |
| GET | `/api/products` | 商品列表 |
| GET | `/api/sales` | 历史销量（参数：product_id, store_id, days） |
| GET | `/api/forecast` | 30 天预测（参数：product_id, store_id） |
| GET | `/api/dashboard` | 大屏聚合数据 |
| GET | `/api/inventory` | 库存热力图数据 |
| GET | `/api/kpi` | KPI 指标 |

### 统一错误响应格式

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "商品 999 或门店 1 不存在",
    "detail": "有效商品 ID: [1, ..., 20]"
  }
}
```

错误码：`NOT_FOUND` / `VALIDATION_ERROR` / `UNAUTHORIZED` / `SERVICE_UNAVAILABLE` / `INTERNAL_ERROR`

---

## 用户使用说明

1. 打开浏览器访问大屏地址（默认 http://localhost:3000）
2. 顶部 KPI 卡片展示总览指标
3. 左上角下拉框选择商品与门店
4. 销量趋势图展示历史与预测（含置信区间）
5. 库存热力图按风险等级红黄绿着色
6. 品类占比与 Top 10 排行辅助决策
7. 大屏每 5 分钟自动刷新

---

## 管理员说明

### 启用 API Token 认证

1. 编辑 `backend/.env`，设置 `API_TOKEN=your-secret-token`
2. 重启服务
3. 所有 `/api/*` 请求需在请求头添加 `X-API-Token: your-secret-token`

### 重新训练模型

```bash
python scripts/train_models.py
# 训练完成后会自动评估，输出 MAPE / RMSE
```

### 查看日志

```bash
# 本地
tail -f backend/logs/app.log

# Docker
docker-compose logs -f backend
```

### 查看模型评估

```bash
cat backend/data/processed/evaluation_report.json
```

预期：ensemble MAPE ≈ 9.91%（准确率 90.09%）

---

## 故障排查

### 问题：启动后端报 `Port 8000 is in use`

```bash
# 查找占用进程
lsof -i :8000          # Linux/Mac
netstat -ano | findstr 8000   # Windows

# 杀掉进程后重启
```

### 问题：大屏显示「数据加载失败」

1. 检查后端是否运行：访问 http://localhost:8000/health
2. 检查 CORS 配置：`CORS_ORIGINS` 是否包含前端地址
3. 查看后端日志：`backend/logs/app.log`

### 问题：`/health` 返回 `degraded`

检查 `checks` 字段，定位缺失的依赖：
- `sales_data` missing → 运行 `python scripts/init_data.py`
- `lstm_model` / `lightgbm_model` missing → 运行 `python scripts/train_models.py`

### 问题：预测接口返回 500

查看日志中是否出现 `KeyError`，通常是特征文件与模型不匹配。重新训练：

```bash
python scripts/init_data.py
python scripts/train_models.py
```

### 问题：LightGBM 模型加载失败

LightGBM C 库不支持中文路径。本项目通过 `model_to_string` 绕过，确保 `lightgbm_model.py` 的 `save_model` / `load_model` 使用字符串方式。

---

## 常见问题

**Q: 为什么用 CSV 而不是数据库？**
A: 项目数据规模小（18100 行）、只读场景，CSV 完全胜任。引入数据库会增加部署复杂度而收益有限。`DATABASE_URL` 配置保留为扩展点。

**Q: 可以用真实数据替换模拟数据吗？**
A: 可以。将真实数据按 `sales_data.csv` 的字段格式保存到 `backend/data/raw/`，重新运行 `python scripts/train_models.py` 即可。

**Q: 预测准确率能再提升吗？**
A: 当前 MAPE 9.91%。可尝试：调整 LSTM/LightGBM 集成权重、增加特征工程、使用更长历史数据。

**Q: 支持多用户登录吗？**
A: 第一版不支持。作为内部工具，单租户足够。如需多用户，可扩展 `API_TOKEN` 为 JWT 认证。

---

## 已知限制

1. **数据为模拟生成**：真实部署需替换为实际销售数据
2. **单进程预测**：预测器使用 `lru_cache`，多 worker 部署时缓存不共享
3. **无持久化用户系统**：仅支持可选 API Token
4. **无实时数据更新**：数据更新需重新运行初始化脚本
5. **无监控告警**：未集成 Prometheus/Grafana（保留扩展点）
6. **CORS 配置需手动修改**：生产部署必须更新 `CORS_ORIGINS`

---

## 版本说明

### v1.0.0（当前）

- 完成核心业务功能：数据生成、模型训练、预测、大屏
- 完成正式化改造：配置、日志、错误处理、安全、测试、部署、文档
- 61 个测试用例全部通过
- 集成 MAPE 9.91%（准确率 90.09%）

---

## 后续维护建议

1. **真实数据接入**：替换 `data_generator.py` 为真实数据导入接口
2. **数据库迁移**：当数据量超过 10 万行时，考虑迁移到 PostgreSQL
3. **模型再训练**：建议每月用最新数据重新训练，保持预测准确率
4. **监控接入**：集成 Prometheus + Grafana 监控 API 延迟与错误率
5. **CI/CD**：参考 `.github/workflows/` 模板，配置自动化测试与部署
6. **限流生产化**：当前 `RATE_LIMIT_*` 配置已就位，生产环境需根据流量调参

---

## License

MIT
