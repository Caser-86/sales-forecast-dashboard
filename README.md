# 销售数据预测与可视化大屏

基于 LSTM + LightGBM 集成模型的销售预测系统，提供实时可视化大屏。

## 技术栈

- **后端**: Python 3.11 / FastAPI / Pydantic / Uvicorn
- **机器学习**: PyTorch (LSTM) / LightGBM / Pandas / Scikit-learn
- **前端**: ECharts 5 / HTML5 / CSS3
- **部署**: Docker / Docker Compose / Nginx

## 功能特性

- **预测模型**: LSTM + LightGBM 集成，MAPE 9.91%
- **数据生成**: 基于真实业务逻辑的模拟销售数据（含周末/促销/节假日效应）
- **特征工程**: 时间序列特征（lag/rolling）、类别编码、价格弹性特征
- **可视化大屏**: 5 个 ECharts 图表（销量趋势、库存热力图、品类饼图、KPI 卡片、Top 排行）
- **工程化**: pydantic-settings 配置、结构化日志、全局异常处理、CORS 安全控制、API 认证（可选）

## 项目结构

```
sales-forecast-dashboard/
├── backend/              # 后端服务
│   ├── app/             # FastAPI 应用
│   │   ├── core/        # 核心模块（配置/异常/健康检查/日志/中间件/安全）
│   │   ├── api/         # API 路由（商品/销量/预测/大屏/库存/KPI）
│   │   └── services/    # 业务服务（数据/预测/库存）
│   ├── ml/              # 机器学习模块（数据生成/特征工程/模型/训练/预测）
│   ├── data/            # 数据文件（原始数据/处理后数据）
│   ├── tests/           # 测试用例（10 个文件，67 个测试）
│   └── requirements.txt
├── frontend/            # 前端大屏
│   ├── index.html
│   ├── css/
│   └── js/
├── scripts/             # 部署脚本（数据初始化/模型训练/部署/验证）
├── docker-compose.yml
├── nginx.conf
└── .dockerignore
```

## 快速开始

### 本地运行

```bash
# 启动后端
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 启动前端（新终端）
cd frontend
python -m http.server 3000
```

访问地址：
- 前端大屏: http://localhost:3000
- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health

### Docker 部署

```bash
docker-compose up --build -d
```

---

## Docker 部署详细步骤

### 1. 环境准备

确保已安装 Docker 和 Docker Compose：

```bash
# 检查 Docker
docker --version
docker-compose --version

# 如未安装（Ubuntu/Debian）：
curl -fsSL https://get.docker.com | sh
systemctl start docker
systemctl enable docker

# 安装 Docker Compose
curl -L "https://github.com/docker/compose/releases/download/v2.32.4/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
```

### 2. 构建并启动

```bash
# 进入项目目录
cd sales-forecast-dashboard

# 构建并启动（后台模式）
docker-compose up --build -d

# 查看容器状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f backend
docker-compose logs -f frontend
```

### 3. 验证服务

```bash
# 健康检查
curl http://localhost:8000/health

# 验证 API
curl http://localhost:8000/api/dashboard

# 验证前端
curl http://localhost:3000
```

### 4. 停止服务

```bash
# 停止并删除容器（保留数据卷）
docker-compose down

# 停止并删除容器及数据卷（谨慎使用，会丢失数据）
docker-compose down -v

# 仅停止容器（不删除）
docker-compose stop

# 重新启动已停止的容器
docker-compose start
```

### 5. 更新部署

```bash
# 拉取最新代码
git pull origin master

# 重新构建并启动
docker-compose up --build -d
```

### 6. 生产环境配置

在生产环境中，建议：

1. **设置 API Token 认证**：
   ```bash
   # 在 docker-compose.yml 中取消注释并设置
   # - API_TOKEN=your-secret-token-here
   ```

2. **配置 CORS 白名单**：
   ```bash
   # 设置环境变量
   export CORS_ORIGINS=http://your-domain.com
   docker-compose up --build -d
   ```

3. **配置 Nginx 反向代理**（可选，推荐）：
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;

       location / {
           proxy_pass http://localhost:3000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }

       location /api/ {
           proxy_pass http://localhost:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

---

## API 接口

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 根路径 | GET | `/` | 欢迎信息 |
| API 列表 | GET | `/api` | API 路由列表 |
| 健康检查 | GET | `/health` | 深度健康检查 |
| 商品列表 | GET | `/api/products` | 返回所有商品及品类 |
| 历史销量 | GET | `/api/sales?product_id=1&store_id=1&days=90` | 返回历史销量数据 |
| 预测结果 | GET | `/api/forecast?product_id=1&store_id=1` | 返回 30 天预测 |
| 大屏聚合 | GET | `/api/dashboard` | 返回所有商品汇总指标 |
| 库存热力图 | GET | `/api/inventory` | 返回 ABC 分级热力图数据 |
| KPI 指标 | GET | `/api/kpi` | 返回核心指标卡片数据 |

### 接口示例

```bash
# 获取商品列表
curl http://localhost:8000/api/products

# 获取历史销量（最近 30 天）
curl "http://localhost:8000/api/sales?product_id=1&store_id=1&days=30"

# 获取预测（商品ID=1，门店ID=1）
curl "http://localhost:8000/api/forecast?product_id=1&store_id=1"

# 获取大屏聚合数据
curl http://localhost:8000/api/dashboard
```

---

## 测试

```bash
cd backend

# 运行全部测试（67 个用例）
pytest tests/

# 运行特定测试文件
pytest tests/test_dashboard.py -v

# 代码检查
ruff check app tests ml

# 生成测试报告（需要安装 pytest-html）
pytest tests/ --html=report.html
```

---

## 模型评估结果

| 模型 | MAPE | RMSE |
|------|------|------|
| LSTM | 19.46% | 31.91 |
| LightGBM | 8.60% | 21.94 |
| 集成模型 (0.4/0.6) | **9.91%** | **16.15** |

---

## 环境变量完整列表

### 应用配置

| 变量 | 说明 | 默认值 | 有效值 |
|------|------|--------|--------|
| APP_NAME | 应用名称 | 销售数据预测与可视化大屏 API | 任意字符串 |
| APP_VERSION | 应用版本 | 1.0.0 | 任意版本号 |
| ENV | 运行环境 | development | development / production / test |
| DEBUG | 调试模式 | false | true / false |
| HOST | 绑定地址 | 0.0.0.0 | 任意 IP |
| PORT | 监听端口 | 8000 | 1-65535 |

### 安全配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| CORS_ORIGINS | CORS 允许的源，多个用逗号分隔 | http://localhost:3000,http://127.0.0.1:3000,http://localhost:5500 |
| API_TOKEN | API Token 认证，留空则不启用 | 空 |
| API_TOKEN_HEADER | Token 请求头名称 | X-API-Token |

### 日志配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| LOG_LEVEL | 日志级别 | INFO |
| LOG_DIR | 日志目录 | backend/logs |
| LOG_FILE_MAX_BYTES | 单文件最大字节数 | 10485760 (10MB) |
| LOG_FILE_BACKUP_COUNT | 保留备份数 | 5 |

### 数据路径配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| DATA_RAW_DIR | 原始数据目录 | backend/data/raw |
| DATA_PROCESSED_DIR | 处理后数据目录 | backend/data/processed |
| MODELS_DIR | 模型保存目录 | backend/ml/saved_models |
| DATABASE_URL | 数据库连接（保留扩展点） | sqlite:///backend/dashboard.db |

### API 配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| API_PREFIX | API 路径前缀 | /api |

### 业务参数配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| FORECAST_DAYS | 预测天数 | 30 |
| LSTM_SEQ_LEN | LSTM 序列长度 | 14 |
| ENSEMBLE_WEIGHTS | 集成权重 (LSTM, LightGBM) | (0.4, 0.6) |

### 限流配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| RATE_LIMIT_ENABLED | 是否启用限流 | true |
| RATE_LIMIT_REQUESTS | 限流窗口内最大请求数 | 100 |
| RATE_LIMIT_WINDOW_SECONDS | 限流窗口秒数 | 60 |

### 使用 .env 文件

在 `backend/` 目录创建 `.env` 文件：

```env
# 应用配置
ENV=production
DEBUG=false
HOST=0.0.0.0
PORT=8000

# 安全配置
CORS_ORIGINS=http://your-domain.com
API_TOKEN=your-secret-token

# 日志配置
LOG_LEVEL=INFO

# 业务参数
FORECAST_DAYS=30
ENSEMBLE_WEIGHTS="(0.4, 0.6)"
```

---

## 故障排查指南

### 常见问题

#### 1. 端口被占用

**现象**：启动后端时提示端口 8000 被占用

**解决方案**：

```bash
# 查找占用端口的进程（Windows）
Get-NetTCPConnection -LocalPort 8000 | Select-Object OwningProcess

# 终止进程（Windows）
Get-NetTCPConnection -LocalPort 8000 | Stop-Process -Id $_.OwningProcess -Force

# 查找占用端口的进程（Linux/Mac）
lsof -i :8000

# 终止进程（Linux/Mac）
kill -9 $(lsof -t -i :8000)
```

#### 2. LightGBM 模型保存失败（中文路径问题）

**现象**：训练时提示 `Model file ... is not available for writes`

**原因**：LightGBM C 库不支持中文路径

**解决方案**：项目已通过 `model_to_string()` + Python 文件 IO 写入的方式绕过此问题，无需手动处理。

#### 3. 数据生成/特征工程失败（pandas 3.x 兼容性）

**现象**：`IndexError: Too many levels: Index has only 1 level, not 2`

**原因**：pandas 3.x 中 `rolling()` 结果 `reset_index()` 的行为变化

**解决方案**：项目已使用 `transform()` 替代 `reset_index()`，无需手动处理。

#### 4. 预测结果不准确（LSTM/LightGBM 样本未对齐）

**现象**：集成评估 MAPE 异常高（如 34%+）

**原因**：LSTM 需要 14 天历史序列，导致部分样本缺失，与 LightGBM 预测样本未对齐

**解决方案**：项目已通过 DataFrame 合并对齐样本，仅对两者都有预测的样本进行集成，无需手动处理。

#### 5. 前端语法错误

**现象**：浏览器控制台提示 `Unexpected token ')'`

**原因**：JavaScript 代码语法错误

**解决方案**：检查 `frontend/js/` 目录下的 JS 文件，特别是排序逻辑部分。

### 调试技巧

#### 查看后端日志

```bash
# 本地运行时查看控制台输出
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Docker 运行时查看日志
docker-compose logs -f backend

# 查看日志文件
cat backend/logs/app.log
```

#### 健康检查

```bash
# 基础健康检查
curl http://localhost:8000/health

# 完整健康检查（包含依赖检查）
curl http://localhost:8000/health | python -m json.tool
```

#### API 调试

```bash
# 使用 curl 调试
curl -v http://localhost:8000/api/dashboard

# 使用 FastAPI 文档（本地环境）
# 打开 http://localhost:8000/docs
```

### 数据问题排查

```bash
# 检查数据文件是否存在
ls -la backend/data/raw/
ls -la backend/data/processed/

# 检查模型文件是否存在
ls -la backend/ml/saved_models/

# 查看数据内容
head backend/data/raw/sales_data.csv
head backend/data/processed/features.csv
```

---

## GitHub

- 仓库: https://github.com/Caser-86/sales-forecast-dashboard
- 版本: v1.2.2
