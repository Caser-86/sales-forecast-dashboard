"""本地演示账号和服务端会话测试。"""
from __future__ import annotations


def test_demo_auth_config_is_disabled_by_default(client):
    response = client.get("/api/auth/config")

    assert response.status_code == 200
    assert response.json()["enabled"] is False


def test_demo_auth_login_me_and_logout(monkeypatch, client, tmp_path):
    from app.core.config import settings

    monkeypatch.setattr(settings, "DEMO_AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{(tmp_path / 'auth.db').as_posix()}")

    denied = client.post("/api/auth/login", json={"username": "analyst", "password": "wrong"})
    assert denied.status_code == 401
    assert denied.json()["error"]["code"] == "UNAUTHORIZED"

    login = client.post("/api/auth/login", json={"username": "analyst", "password": "demo-analyst"})
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "analyst"
    assert "demo_session" in login.headers.get("set-cookie", "")

    current = client.get("/api/auth/me")
    assert current.status_code == 200
    assert current.json()["user"]["username"] == "analyst"

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 200
    assert client.get("/api/auth/me").status_code == 401
