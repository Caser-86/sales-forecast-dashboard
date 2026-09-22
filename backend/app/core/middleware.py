"""全局异常处理与请求日志中间件。"""
from __future__ import annotations

import time
import uuid
from typing import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging import get_logger

logger = get_logger(__name__)


def _with_cors_headers(request: Request, response: StarletteResponse) -> StarletteResponse:
    origin = request.headers.get("Origin")
    if origin and origin in settings.cors_origin_list:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"
    return response


class CatchAllMiddleware(BaseHTTPMiddleware):
    """捕获未处理异常，统一错误响应格式。"""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[StarletteResponse]]
    ) -> StarletteResponse:
        try:
            return await call_next(request)
        except AppError as e:
            logger.warning("AppError %s: %s", e.code, e.message)
            return _with_cors_headers(request, JSONResponse(
                status_code=e.http_status,
                content=e.to_response(include_detail=settings.DEBUG),
            ))
        except Exception as e:
            # 未预期异常：记录完整堆栈，但只给客户端通用提示
            logger.exception("未处理异常: %s", e)
            return _with_cors_headers(request, JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "服务器内部错误，请联系管理员" if settings.is_prod else str(e),
                    }
                },
            ))


class RequestLogMiddleware(BaseHTTPMiddleware):
    """请求访问日志与耗时记录。"""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[StarletteResponse]]
    ) -> StarletteResponse:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        start = time.perf_counter()

        # 健康检查不打日志，避免噪音
        path = request.url.path
        is_health = path in ("/", "/health", "/api")

        if not is_health:
            logger.info(
                "→ %s %s (rid=%s)",
                request.method, path, request_id,
            )

        try:
            response: Response = await call_next(request)
        except Exception:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error(
                "✗ %s %s 500 %.1fms (rid=%s)",
                request.method, path, elapsed, request_id,
            )
            raise

        elapsed = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-ms"] = f"{elapsed:.1f}"

        if not is_health:
            logger.info(
                "← %s %s %d %.1fms (rid=%s)",
                request.method, path, response.status_code, elapsed, request_id,
            )

        return response
