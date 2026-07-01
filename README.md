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
│   ├── ml/              # 机器学习模块
│   ├── data/            # 数据文件
│   ├── tests/           # 测试用例
│   └── requirements.txt
├── frontend/            # 前端大屏
│   ├── index.html
│   ├── css/
│   └── js/
├── scripts/             # 部署脚本
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

## API 接口

| 接口 | 方法 | 路径 |
|------|------|------|
| 健康检查 | GET | `/health` |
| 商品列表 | GET | `/api/products` |
| 历史销量 | GET | `/api/sales` |
| 预测结果 | GET | `/api/forecast` |
| 大屏聚合 | GET | `/api/dashboard` |
| 库存热力图 | GET | `/api/inventory` |
| KPI 指标 | GET | `/api/kpi` |

## 测试

```bash
cd backend
pytest tests/          # 运行全部测试（67 个用例）
ruff check app tests ml # 代码检查
```

## 模型评估结果

| 模型 | MAPE | RMSE |
|------|------|------|
| LSTM | 19.46% | 31.91 |
| LightGBM | 8.60% | 21.94 |
| 集成模型 (0.4/0.6) | **9.91%** | **16.15** |

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| ENV | 运行环境 | development |
| DEBUG | 调试模式 | true |
| LOG_LEVEL | 日志级别 | DEBUG |
| CORS_ORIGINS | CORS 白名单 | http://localhost:3000 |
| API_TOKEN | API 认证 Token | 空 |
| FORECAST_DAYS | 预测天数 | 30 |

## GitHub

- 仓库: https://github.com/Caser-86/sales-forecast-dashboard
- 版本: v1.2.0
