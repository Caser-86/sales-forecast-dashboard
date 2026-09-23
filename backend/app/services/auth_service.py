"""Local demo identities and server-side cookie sessions.

This is intentionally scoped to the isolated demo runtime. Production deployments
must use the existing API token or an external identity provider instead.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Cookie, Depends, Request

from app.core.config import settings
from app.core.exceptions import UnauthorizedError, ValidationError

SESSION_COOKIE = "demo_session"
ROLES = {"analyst", "approver", "admin"}
ROLE_LABELS = {"analyst": "分析员", "approver": "审批员", "admin": "管理员"}
_PBKDF2_ROUNDS = 120_000

# Fixed salted hashes keep demo credentials out of plaintext storage. These accounts
# are only available when DEMO_AUTH_ENABLED=true and are documented for local demos.
_DEMO_USERS = {
    "analyst": {
        "display_name": "演示分析员",
        "role": "analyst",
        "salt": "a1b2c3d4e5f60718",
        "password_hash": "c3fccc8b8ded6bd330adb04b3e82dbf96b8233511f0a8c51be97e925e7499557",
    },
    "approver": {
        "display_name": "演示审批员",
        "role": "approver",
        "salt": "b2c3d4e5f6071829",
        "password_hash": "194b6db1c2ae0a1576475e6d82ab1d6ce0d31ebe9a49b93131b2ae0aeb9ab707",
    },
    "admin": {
        "display_name": "演示管理员",
        "role": "admin",
        "salt": "c3d4e5f6071829a0",
        "password_hash": "3c8eb472f8fede9071edbe32eb81b6a0f7fc661843f1e5ce50429505fddf4696",
    },
}


@dataclass(frozen=True)
class DemoUser:
    username: str
    display_name: str
    role: str

    def to_dict(self) -> dict[str, str]:
        return {
            "username": self.username,
            "display_name": self.display_name,
            "role": self.role,
            "role_label": ROLE_LABELS.get(self.role, self.role),
        }


def _database_path() -> str:
    value = str(settings.DATABASE_URL)
    if value == ":memory:":
        return value
    if value.startswith("sqlite:///"):
        value = value[10:]
    return str(Path(value).expanduser().resolve())


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_schema() -> None:
    database = _database_path()
    if database != ":memory:":
        Path(database).parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database)) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS demo_sessions (
                session_hash TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked_at TEXT
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_demo_sessions_expiry ON demo_sessions(expires_at)"
        )
        connection.commit()


def auth_enabled() -> bool:
    return bool(settings.DEMO_AUTH_ENABLED)


def _verify_password(username: str, password: str) -> DemoUser:
    record = _DEMO_USERS.get(username.strip().lower())
    if not record or not password:
        raise UnauthorizedError("用户名或密码错误")
    candidate = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(record["salt"]),
        _PBKDF2_ROUNDS,
    ).hex()
    if not hmac.compare_digest(candidate, record["password_hash"]):
        raise UnauthorizedError("用户名或密码错误")
    return DemoUser(username=username.strip().lower(), display_name=record["display_name"], role=record["role"])


def login(username: str, password: str) -> tuple[str, DemoUser, datetime]:
    if not auth_enabled():
        raise ValidationError("本地演示认证未启用")
    user = _verify_password(username, password)
    _ensure_schema()
    raw_token = secrets.token_urlsafe(32)
    now = _now()
    expires = now + timedelta(seconds=settings.DEMO_SESSION_TTL_SECONDS)
    with closing(sqlite3.connect(_database_path())) as connection:
        connection.execute(
            "INSERT INTO demo_sessions(session_hash, username, role, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
            (hashlib.sha256(raw_token.encode("utf-8")).hexdigest(), user.username, user.role, now.isoformat(), expires.isoformat()),
        )
        connection.commit()
    return raw_token, user, expires


def _user_from_session(raw_token: str | None) -> DemoUser | None:
    if not raw_token or not auth_enabled():
        return None
    _ensure_schema()
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    with closing(sqlite3.connect(_database_path())) as connection:
        row = connection.execute(
            "SELECT username, role, expires_at, revoked_at FROM demo_sessions WHERE session_hash = ?",
            (token_hash,),
        ).fetchone()
    if row is None or row[3]:
        return None
    try:
        expires = datetime.fromisoformat(row[2])
    except ValueError:
        return None
    if expires <= _now():
        return None
    record = _DEMO_USERS.get(row[0])
    if not record or record["role"] != row[1]:
        return None
    return DemoUser(username=row[0], display_name=record["display_name"], role=row[1])


def current_user(session: str | None) -> DemoUser | None:
    return _user_from_session(session)


def revoke(session: str | None) -> None:
    if not session:
        return
    _ensure_schema()
    with closing(sqlite3.connect(_database_path())) as connection:
        connection.execute(
            "UPDATE demo_sessions SET revoked_at = ? WHERE session_hash = ?",
            (_now().isoformat(), hashlib.sha256(session.encode("utf-8")).hexdigest()),
        )
        connection.commit()


def require_user(request: Request, session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> DemoUser:
    """Resolve a request user; disabled demo auth keeps legacy local access open."""
    if not auth_enabled():
        return DemoUser(username="local", display_name="本地演示", role="admin")
    user = current_user(session)
    if user is None:
        raise UnauthorizedError("请先登录本地演示账号")
    request.state.demo_user = user
    return user


_DemoUserDependency = Depends(require_user)


def require_roles(*roles: str):
    invalid = set(roles) - ROLES
    if invalid:
        raise ValueError(f"未知角色: {sorted(invalid)}")

    def dependency(user: DemoUser = _DemoUserDependency) -> DemoUser:
        if user.role not in roles:
            raise UnauthorizedError("当前账号没有执行此操作的权限")
        return user

    return dependency
