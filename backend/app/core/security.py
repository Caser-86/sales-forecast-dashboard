"""可选 API Token 认证。

启用方式：在 .env 中设置 API_TOKEN=xxx
禁用方式：API_TOKEN 留空（默认）

注意：当前 API 路由尚未挂载认证依赖（TokenDependency），
认证中间件已就绪但默认不启用，保持服务对前端大屏开放。
如需启用，可在 router 或 app.include_router 中加入：
    dependencies=[security.TokenDependency]
"""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status

from app.core.config import settings


def verify_token(
    x_api_token: str | None = Header(default=None, alias=settings.API_TOKEN_HEADER),
) -> str:
    """验证 API Token。

    - 若未配置 API_TOKEN，跳过校验（开放访问）。
    - 若已配置 API_TOKEN，请求头必须匹配。
    """
    if not settings.auth_enabled:
        return "anonymous"

    if not x_api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"缺少认证头: {settings.API_TOKEN_HEADER}",
            headers={"WWW-Authenticate": settings.API_TOKEN_HEADER},
        )

    if x_api_token != settings.API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 API Token",
        )

    return "authenticated"


# 预构造的依赖对象，供后续在路由上启用认证时使用。
# 当前未被任何路由引用（默认开放），保留以保证认证扩展能力。
TokenDependency = Depends(verify_token)
