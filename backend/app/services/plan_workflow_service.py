"""Versioned plan workflow and audit events for the local demo."""
from __future__ import annotations

import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.exceptions import ConflictError, NotFoundError, UnauthorizedError
from app.services.auth_service import DemoUser
from app.services.plan_repository import PlanRepository

PLAN_STATUSES = {"draft", "submitted", "approved", "rejected", "cancelled"}


class PlanWorkflowService:
    def __init__(self, database: str | Path | None = None):
        self.repository = PlanRepository(database)
        self.database = self.repository.database
        self._ensure_schema()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS plan_workflow (
                    plan_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    parent_plan_id TEXT,
                    created_by TEXT NOT NULL,
                    updated_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS plan_events (
                    event_id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    from_status TEXT NOT NULL,
                    to_status TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    actor_username TEXT NOT NULL,
                    actor_role TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_plan_events_plan_created ON plan_events(plan_id, created_at DESC)"
            )
            connection.commit()

    def _require_plan(self, plan_id: str) -> None:
        if self.repository.get(plan_id) is None:
            raise NotFoundError(f"草案 {plan_id} 不存在")

    def ensure_plan(self, plan_id: str, actor: DemoUser | None = None, *, parent_plan_id: str | None = None, version: int = 1) -> dict[str, Any]:
        self._require_plan(plan_id)
        username = actor.username if actor else "system"
        now = self._now()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO plan_workflow(
                    plan_id, status, version, parent_plan_id, created_by, updated_by, created_at, updated_at
                ) VALUES (?, 'draft', ?, ?, ?, ?, ?, ?)
                """,
                (plan_id, version, parent_plan_id, username, username, now, now),
            )
            connection.commit()
        return self.get(plan_id)

    def get(self, plan_id: str) -> dict[str, Any]:
        self._require_plan(plan_id)
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT * FROM plan_workflow WHERE plan_id = ?", (plan_id,)).fetchone()
        if row is None:
            return self.ensure_plan(plan_id)
        return dict(row)

    def list_for(self, plan_ids: list[str]) -> dict[str, dict[str, Any]]:
        result = {}
        for plan_id in plan_ids:
            result[plan_id] = self.get(plan_id)
        return result

    @staticmethod
    def _allowed(status: str, action: str, role: str) -> tuple[str, bool]:
        if action == "submit" and status == "draft" and role in {"analyst", "admin"}:
            return "submitted", True
        if action == "approve" and status == "submitted" and role in {"approver", "admin"}:
            return "approved", True
        if action == "reject" and status == "submitted" and role in {"approver", "admin"}:
            return "rejected", True
        if action == "cancel" and status in {"draft", "submitted"} and role in {"analyst", "admin"}:
            return "cancelled", True
        return status, False

    def transition(self, plan_id: str, action: str, actor: DemoUser, expected_version: int, reason: str = "") -> dict[str, Any]:
        action = action.strip().lower()
        if action not in {"submit", "approve", "reject", "cancel"}:
            raise ConflictError("不支持的计划状态操作")
        state = self.get(plan_id)
        if int(state["version"]) != expected_version:
            raise ConflictError("计划已被其他操作更新，请刷新后重试")
        next_status, allowed = self._allowed(state["status"], action, actor.role)
        if not allowed:
            raise UnauthorizedError("当前角色不能执行此计划操作，或计划状态已变化")
        reason = str(reason or "").strip()[:500]
        if action == "reject" and not reason:
            raise ConflictError("驳回计划必须填写原因")
        now = self._now()
        next_version = int(state["version"]) + 1
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE plan_workflow
                SET status = ?, version = ?, updated_by = ?, updated_at = ?
                WHERE plan_id = ? AND status = ? AND version = ?
                """,
                (next_status, next_version, actor.username, now, plan_id, state["status"], expected_version),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                raise ConflictError("计划已被其他操作更新，请刷新后重试")
            connection.execute(
                """
                INSERT INTO plan_events(
                    event_id, plan_id, action, from_status, to_status, version,
                    actor_username, actor_role, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (f"event-{uuid.uuid4().hex}", plan_id, action, state["status"], next_status,
                 next_version, actor.username, actor.role, reason, now),
            )
            connection.commit()
        return self.get(plan_id)

    def create_revision(self, source_plan_id: str, actor: DemoUser, idempotency_key: str) -> dict[str, Any]:
        source_state = self.get(source_plan_id)
        if source_state["status"] != "rejected":
            raise ConflictError("只有已驳回计划可以创建新修订版")
        if actor.role not in {"analyst", "admin"}:
            raise UnauthorizedError("当前角色不能创建计划修订版")
        source = self.repository.get(source_plan_id)
        if source is None:
            raise NotFoundError(f"草案 {source_plan_id} 不存在")
        snapshot = dict(source.snapshot)
        snapshot["name"] = f"{snapshot.get('name', '补货草案')}（修订版）"
        saved = self.repository.save(idempotency_key, snapshot)
        self.ensure_plan(
            saved.plan_id,
            actor,
            parent_plan_id=source_plan_id,
            version=int(source_state["version"]) + 1,
        )
        return {"plan_id": saved.plan_id, "created": saved.created, "workflow": self.get(saved.plan_id)}

    def events(self, plan_id: str) -> list[dict[str, Any]]:
        self.get(plan_id)
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM plan_events WHERE plan_id = ? ORDER BY rowid ASC",
                (plan_id,),
            ).fetchall()
        return [dict(row) for row in rows]
