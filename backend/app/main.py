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

from app.api import dashboard, forecast, products, quality, sales
from app.core.config import settings
from app.core.health import router as health_router
from app.core.logging import setup_logging
from app.core.middleware import CatchAllMiddleware, RequestLogMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化日志、目录。"""
    setup_logging()
    settings.ensure_dirs()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="基于 LSTM + LightGBM 集成模型的销售预测服务",
    version=settings.APP_VERSION,
    docs_url="/docs" if not settings.is_prod else None,
    redoc_url="/redoc" if not settings.is_prod else None,
    lifespan=lifespan,
)

# ---------- 中间件（注册顺序：后注册先执行） ----------

# CORS - 收紧为可配置白名单
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# 请求访问日志
app.add_middleware(RequestLogMiddleware)

# 全局异常捕获
app.add_middleware(CatchAllMiddleware)


# ---------- 路由 ----------

app.include_router(health_router, tags=["健康检查"])
app.include_router(products.router, prefix=settings.API_PREFIX, tags=["商品"])
app.include_router(sales.router, prefix=settings.API_PREFIX, tags=["历史销量"])
app.include_router(forecast.router, prefix=settings.API_PREFIX, tags=["预测"])
app.include_router(dashboard.router, prefix=settings.API_PREFIX, tags=["大屏"])
app.include_router(quality.router, prefix=settings.API_PREFIX, tags=["质量与模型"])


@app.get("/", tags=["健康检查"])
def root():
    """根路径简易状态。"""
    return {"status": "ok", "service": "sales-forecast-dashboard", "version": settings.APP_VERSION}


@app.get("/api", tags=["健康检查"])
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
