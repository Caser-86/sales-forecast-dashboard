# Project Context

> 这是当前项目状态的单一入口。已验证事实以代码、测试和 `docs/releases/v1-acceptance.md` 为准；生成数据的指标不代表真实业务效果。

## 项目目标

把历史销售、未来 30 天需求预测、ABC 优先级和透明补货建议串成一条可复现的零售决策演示链路，帮助面试官和开发者理解业务口径、模型选择和工程边界。

## 当前状态

- 面试版 V1 已完成验收，可以通过 Docker Compose 或本地 FastAPI + 静态前端运行。
- 默认使用可重复生成的 Demo 销售与库存数据，不是 ERP/WMS 生产数据接入。
- V1 是单租户、单服务实例、人工导入/训练/激活/回滚模式。
- V1 验收、浏览器、Docker、依赖和恢复证据集中在 `docs/`；发布结论见 `docs/releases/v1-acceptance.md`。
- 下一目标为本地完整演示版 V2，M1/T1 与 M1/T2 共享壳已完成，当前进入 T3，详细路线见 [`docs/local-demo-plan.md`](docs/local-demo-plan.md)。

## 已完成功能

- 销售 CSV 和库存快照的 schema 校验、版本目录、active 指针和 CLI 导入。
- LSTM、LightGBM、7 日季节性基线及同口径 30 天滚动回测；允许基线或单模型胜出。
- 模型包 manifest、checksum、特征 schema、数据/模型版本和原子激活/回滚。
- FastAPI 商品、门店、销量、预测、Dashboard、库存、质量、元数据和补货草案 API。
- Dashboard 的筛选、趋势、KPI、Top 商品、品类、库存风险、空态、部分失败、重试和窄屏交互。
- 基于库存事实和策略参数的可解释补货建议，以及 SQLite 草案保存、幂等重试、重启恢复和 CSV 导出。
- 可选 API Token、限流、结构化日志、liveness/readiness、Docker Compose 同源部署。
- Python 测试、Ruff、前端语法检查、Compose 校验、镜像启动、Chromium E2E 和依赖审计门禁。

## 当前正在开发

当前处于本地完整演示版 V2 执行阶段。M1/T1 与 M1/T2 共享壳已完成，T3 持久化任务正在实现；数据中心、预测、库存、计划和模型操作等后续页面能力仍按路线图实现。详细范围、任务依赖、拟修改文件和验收标准见 [`docs/local-demo-plan.md`](docs/local-demo-plan.md)，未完成项索引见 `TODO.md`。

## 未完成任务

见 [`TODO.md`](TODO.md)。V2 的新增任务不改变已经验收的 V1 能力；生产化事项延后到本地演示闭环完成之后。

## 当前技术栈

- 后端：Python 3.11、FastAPI、Pydantic Settings、pandas、NumPy、PyTorch、LightGBM、scikit-learn。
- 前端：原生 HTML/CSS/JavaScript、ECharts、Playwright Chromium。
- 持久化：版本化 CSV/JSON/模型文件；补货草案使用 SQLite。
- 工程：Docker Compose、GitHub Actions、pytest、pytest-cov、Ruff、pip-audit。

## 核心架构

```text
CSV 生成/导入 -> schema 校验 -> immutable dataset version
离线训练/回测 -> model package + manifest -> active model pointer
FastAPI -> data/model/inventory metadata -> shared forecast service
       -> ABC/replenishment rules -> SQLite draft/export
前端 Dashboard -> same-origin API -> loading/empty/partial/error states
```

## 关键目录

- `backend/app/`：FastAPI 路由、配置、鉴权、健康检查和领域服务。
- `backend/ml/`：数据生成、特征工程、未来特征、训练、回测、模型包和预测。
- `backend/common/`：ABC 分级和补货规则。
- `backend/tests/`：API、领域规则、模型辅助函数、部署和前端契约测试。
- `frontend/`：Dashboard、ECharts 图表、Playwright smoke 和 nginx 反代。
- `scripts/`：初始化、导入、训练、激活、恢复、部署和容量基线命令。
- `docs/`：当前产品、部署、恢复、验收和证据文档；历史审查报告在 `docs/archive/`。

## 关键技术决策

- V1 预测周期固定为未来 30 天，时间切分使用 60/20/20；策略选择只使用 validation，test 只做最终评估。
- 模型复杂度不是发布标准；同口径回测允许 seasonal-naive 基线胜出。
- `情景范围` 不称为统计置信区间，除非未来补充校准目标、覆盖率和样本量证据。
- 数据集和模型不原地覆盖，通过 immutable version + active pointer 保证可回滚。
- 补货建议只生成需要人工确认的草案，不调用 ERP、WMS 或供应商下单接口。
- 不引入 Agent、RAG、聊天助手、微服务、消息总线或 Kubernetes 来解决当前 V1 问题。

## 已知问题

- Demo 数据由脚本生成，模型指标不能外推为真实业务效果。
- 尚未接入真实 ERP/WMS、增量同步、定时训练、模型注册、漂移监控或自动回滚。
- 当前是单租户 Token 认证，不是多用户登录、RBAC 或生产密钥托管。
- 当前服务按单实例设计，没有队列化推理、分布式限流或完整可观测性平台。
- 已有容量证据来自受限本机环境，不能替代目标生产环境的 SLA 验证。
- `docs/fresh-clone-walkthrough-2026-09-15.md` 等带日期文件是历史证据快照，不应被误读为当前实时状态。

## 下一步

1. 按本地演示计划 T1–T2 建立独立演示环境、Windows 一键启动和统一导航。
2. 按 T3–T8 补齐数据/模型界面操作、预测分析、补货试算、计划审批与审计。
3. 按 T9–T10 完成异常场景、备份恢复、离线复演和验收，再评估生产化需求。
