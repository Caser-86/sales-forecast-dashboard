"""FastAPI 应用入口。

正式化改造点:
- 基于 pydantic-settings 的配置管理
- 结构化日志（控制台 + 文件轮转）
- 全局异常处理中间件
- 请求访问日志
- CORS 收紧为可配置白名单
- 深度健康检查 /health
- 可选 API Token 认证
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import dashboard, datasets, forecast, jobs, models, plans, products, quality, replenishment, sales, stores
from app.core.config import settings
from app.core.health import router as health_router
from app.core.logging import setup_logging
from app.core.middleware import CatchAllMiddleware, RequestLogMiddleware
from app.core.rate_limit import RateLimitMiddleware
from app.core.security import TokenDependency
from app.services import runtime_state
from app.services.job_repository import JobRepository


def validate_runtime_security() -> None:
    """Reject an unprotected production process before serving requests."""
    if settings.is_prod and not settings.auth_enabled:
        raise RuntimeError("生产环境必须配置 API_TOKEN，或在受信任网关后运行")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化日志、目录。"""
    validate_runtime_security()
    setup_logging()
    settings.ensure_dirs()
    JobRepository().recover_interrupted()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="基于 LSTM + LightGBM 集成模型的销售预测服务",
    version=settings.APP_VERSION,
    docs_url="/docs" if not settings.is_prod else None,
    redoc_url="/redoc" if not settings.is_prod else None,
    lifespan=lifespan,
)


@app.middleware("http")
async def pin_runtime_snapshot(request, call_next):
    """Keep all component reads in one request on the same runtime version."""
    token = runtime_state.bind_request_runtime_snapshot()
    try:
        return await call_next(request)
    finally:
        runtime_state.reset_request_runtime_snapshot(token)

# ---------- 中间件（注册顺序：后注册先执行） ----------

# CORS - 收紧为可配置白名单
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# API 限流：V1为单进程部署，生产扩容时应迁移到网关或共享限流存储。
app.add_middleware(RateLimitMiddleware)

# 请求访问日志
app.add_middleware(RequestLogMiddleware)

# 全局异常捕获
app.add_middleware(CatchAllMiddleware)


# ---------- 路由 ----------

app.include_router(health_router, tags=["健康检查"])
app.include_router(
    products.router,
    prefix=settings.API_PREFIX,
    tags=["商品"],
    dependencies=[TokenDependency],
)
app.include_router(
    stores.router,
    prefix=settings.API_PREFIX,
    tags=["门店"],
    dependencies=[TokenDependency],
)
app.include_router(
    sales.router,
    prefix=settings.API_PREFIX,
    tags=["历史销量"],
    dependencies=[TokenDependency],
)
app.include_router(
    forecast.router,
    prefix=settings.API_PREFIX,
    tags=["预测"],
    dependencies=[TokenDependency],
)
app.include_router(
    dashboard.router,
    prefix=settings.API_PREFIX,
    tags=["大屏"],
    dependencies=[TokenDependency],
)
app.include_router(
    quality.router,
    prefix=settings.API_PREFIX,
    tags=["质量与模型"],
    dependencies=[TokenDependency],
)
app.include_router(
    plans.router,
    prefix=settings.API_PREFIX,
    tags=["补货草案"],
    dependencies=[TokenDependency],
)
app.include_router(
    jobs.router,
    prefix=settings.API_PREFIX,
    tags=["后台任务"],
    dependencies=[TokenDependency],
)
app.include_router(
    datasets.router,
    prefix=settings.API_PREFIX,
    tags=["数据中心"],
    dependencies=[TokenDependency],
)
app.include_router(
    models.router,
    prefix=settings.API_PREFIX,
    tags=["模型中心"],
    dependencies=[TokenDependency],
)
app.include_router(
    replenishment.router,
    prefix=settings.API_PREFIX,
    tags=["补货试算"],
    dependencies=[TokenDependency],
)


@app.get("/", tags=["健康检查"])
def root():
    """根路径简易状态。"""
    return {"status": "ok", "service": "sales-forecast-dashboard", "version": settings.APP_VERSION}


@app.get("/api", tags=["健康检查"], dependencies=[TokenDependency])
def api_root():
    """API 端点列表。"""
    return {
        "endpoints": [
            "/health",
            "/api/products",
            "/api/sales",
            "/api/forecast",
            "/api/dashboard",
            "/api/inventory",
            "/api/kpi",
            "/api/model-info",
            "/api/data-quality",
            "/api/stores",
            "/api/metadata",
            "/api/plans",
            "/api/jobs",
            "/api/datasets",
            "/api/models",
            "/api/replenishment/preview",
        ]
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG and not settings.is_prod,
    )
