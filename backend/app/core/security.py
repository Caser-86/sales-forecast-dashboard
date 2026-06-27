"""可选 API Token 认证。

启用方式：在 .env 中设置 API_TOKEN=xxx
禁用方式：API_TOKEN 留空（默认）
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


# 依赖对象，供路由直接使用: dependencies=[Depends(verify_token)] 或路由级
TokenDependency = Depends(verify_token)
