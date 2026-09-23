"""Local demo login and role/session introspection."""
from __future__ import annotations

from fastapi import APIRouter, Cookie, Response

from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.schemas import AuthLoginRequest
from app.services import auth_service

router = APIRouter()


@router.get("/auth/config", summary="查看演示认证配置")
def get_auth_config():
    return {"enabled": auth_service.auth_enabled(), "session_ttl_seconds": settings.DEMO_SESSION_TTL_SECONDS}


@router.post("/auth/login", summary="登录本地演示账号")
def login(payload: AuthLoginRequest, response: Response):
    raw_token, user, expires = auth_service.login(payload.username, payload.password)
    response.set_cookie(
        key=auth_service.SESSION_COOKIE,
        value=raw_token,
        max_age=settings.DEMO_SESSION_TTL_SECONDS,
        expires=expires,
        httponly=True,
        samesite="lax",
        secure=settings.is_prod,
    )
    return {"user": user.to_dict(), "expires_at": expires.isoformat()}


@router.get("/auth/me", summary="查看当前演示身份")
def get_current_user(session: str | None = Cookie(default=None, alias=auth_service.SESSION_COOKIE)):
    if not auth_service.auth_enabled():
        return {"authenticated": True, "user": {"username": "local", "display_name": "本地演示", "role": "admin", "role_label": "管理员"}}
    user = auth_service.current_user(session)
    if user is None:
        raise UnauthorizedError("请先登录本地演示账号")
    return {"authenticated": True, "user": user.to_dict()}


@router.post("/auth/logout", summary="退出本地演示账号")
def logout(response: Response, session: str | None = Cookie(default=None, alias=auth_service.SESSION_COOKIE)):
    auth_service.revoke(session)
    response.delete_cookie(auth_service.SESSION_COOKIE)
    return {"authenticated": False}
