"""SQLite-backed immutable replenishment plan snapshots."""
from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
import tempfile
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, PlanValidationError


@dataclass(frozen=True)
class SavedPlan:
    plan_id: str
    created_at: str
    snapshot: dict[str, Any]
    created: bool


class PlanRepository:
    """Store immutable snapshots for the single-tenant V1 deployment."""

    def __init__(self, database: str | Path | None = None, *, backup_path: str | Path | None = None):
        self.database = self._resolve_database(database)
        self.backup_path = Path(backup_path) if backup_path is not None else self._default_backup_path()
        if self.database != ":memory:":
            Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    @staticmethod
    def _resolve_database(database: str | Path | None) -> str:
        value = str(database or settings.DATABASE_URL)
        if value == ":memory:":
            return value
        if value.startswith("sqlite:///"):
            value = value[10:]
        if value.startswith("sqlite://"):
            raise ValueError("仅支持 sqlite 文件路径或 sqlite:///")
        return str(Path(value).expanduser().resolve())

    def _default_backup_path(self) -> Path | None:
        if self.database == ":memory:":
            return None
        return Path(self.database + ".bak")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _ensure_schema(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS plan_drafts (
                    plan_id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    payload_hash TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.commit()

    @staticmethod
    def _canonical_snapshot(snapshot: dict[str, Any]) -> str:
        return json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _validate_snapshot(snapshot: dict[str, Any]) -> None:
        coverage = snapshot.get("coverage") or {}
        if coverage.get("status") != "ok" or coverage.get("failed", 0) != 0:
            raise PlanValidationError("预测覆盖不完整，不能保存补货草案")
        if coverage.get("requested") != coverage.get("succeeded"):
            raise PlanValidationError("预测覆盖数量不一致，不能保存补货草案")
        if not snapshot.get("items"):
            raise PlanValidationError("补货草案至少需要一条明细")
        for item in snapshot["items"]:
            suggested = int(item.get("suggested_purchase", 0))
            adjustment = int(item.get("adjustment_quantity", 0))
            if suggested + adjustment < 0:
                raise PlanValidationError("人工调整后数量不能为负数")
            if adjustment and not str(item.get("adjustment_reason", "")).strip():
                raise PlanValidationError("存在人工调整时必须填写原因")

    def save(self, idempotency_key: str, snapshot: dict[str, Any]) -> SavedPlan:
        key = idempotency_key.strip()
        if not key or len(key) > 200:
            raise PlanValidationError("Idempotency-Key 不能为空且长度不能超过 200")
        self._validate_snapshot(snapshot)
        canonical = self._canonical_snapshot(snapshot)
        payload_hash = __import__("hashlib").sha256(canonical.encode("utf-8")).hexdigest()
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")

        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT plan_id, created_at, payload_hash, snapshot_json FROM plan_drafts WHERE idempotency_key = ?",
                (key,),
            ).fetchone()
            if existing:
                if existing["payload_hash"] != payload_hash:
                    raise ConflictError("Idempotency-Key 已用于另一份草案")
                return SavedPlan(
                    plan_id=existing["plan_id"],
                    created_at=existing["created_at"],
                    snapshot=json.loads(existing["snapshot_json"]),
                    created=False,
                )

            plan_id = f"plan-{uuid.uuid4().hex}"
            connection.execute(
                "INSERT INTO plan_drafts(plan_id, idempotency_key, payload_hash, snapshot_json, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (plan_id, key, payload_hash, canonical, now),
            )
            connection.commit()

        self._write_backup()
        return SavedPlan(plan_id=plan_id, created_at=now, snapshot=json.loads(canonical), created=True)

    def get(self, plan_id: str) -> SavedPlan | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT plan_id, created_at, snapshot_json FROM plan_drafts WHERE plan_id = ?",
                (plan_id,),
            ).fetchone()
        if row is None:
            return None
        return SavedPlan(
            plan_id=row["plan_id"],
            created_at=row["created_at"],
            snapshot=json.loads(row["snapshot_json"]),
            created=False,
        )

    def list(self, limit: int = 50) -> list[SavedPlan]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT plan_id, created_at, snapshot_json FROM plan_drafts "
                "ORDER BY created_at DESC, plan_id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            SavedPlan(
                plan_id=row["plan_id"],
                created_at=row["created_at"],
                snapshot=json.loads(row["snapshot_json"]),
                created=False,
            )
            for row in rows
        ]

    def export_csv(self, plan_id: str) -> str:
        plan = self.get(plan_id)
        if plan is None:
            raise NotFoundError(f"草案 {plan_id} 不存在")

        columns = [
            "plan_id", "created_at", "name", "as_of_date", "inventory_as_of_date",
            "data_version", "model_version", "inventory_version", "policy_version",
            "product_id", "store_id", "product_name", "store_name", "predicted_sales",
            "suggested_purchase", "original_suggested_purchase", "adjustment_quantity", "adjustment_reason", "risk_level",
            "on_hand", "confirmed_inbound", "reserved", "lead_time_days", "review_period_days",
            "safety_stock", "pack_size", "minimum_order_quantity",
        ]
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        snapshot = plan.snapshot
        for item in snapshot["items"]:
            row = {
                "plan_id": plan.plan_id,
                "created_at": plan.created_at,
                "name": snapshot["name"],
                "as_of_date": snapshot["as_of_date"],
                "inventory_as_of_date": snapshot["inventory_as_of_date"],
                "data_version": snapshot["data_version"],
                "model_version": snapshot["model_version"],
                "inventory_version": snapshot["inventory_version"],
                "policy_version": snapshot["policy_version"],
                **item,
            }
            writer.writerow({key: self._safe_csv_value(value) for key, value in row.items()})
        return output.getvalue()

    @staticmethod
    def _safe_csv_value(value: Any) -> Any:
        if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
            return "'" + value
        return value

    def _write_backup(self) -> None:
        if self.backup_path is None or self.database == ":memory:":
            return
        self.backup_path.parent.mkdir(parents=True, exist_ok=True)
        source = sqlite3.connect(self.database)
        target = sqlite3.connect(str(self.backup_path))
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()


def _check_sqlite_database(path: Path) -> int:
    if not path.is_file():
        raise ValueError(f"SQLite 文件不存在: {path}")
    connection = None
    try:
        connection = sqlite3.connect(path)
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise ValueError(f"SQLite integrity_check 失败: {integrity}")
        connection.execute("SELECT 1 FROM plan_drafts LIMIT 1").fetchone()
        return int(connection.execute("SELECT COUNT(*) FROM plan_drafts").fetchone()[0])
    except sqlite3.Error as exc:
        raise ValueError(f"SQLite 备份结构无效: {exc}") from exc
    finally:
        if connection is not None:
            connection.close()


def restore_database(backup: str | Path, database: str | Path) -> dict[str, object]:
    """Validate a plan backup and atomically replace the target SQLite file."""
    backup_path = Path(backup).expanduser().resolve()
    resolved_database = PlanRepository._resolve_database(database)
    if resolved_database == ":memory:":
        raise ValueError("恢复目标必须是 SQLite 文件")
    database_path = Path(resolved_database)
    if backup_path == database_path:
        raise ValueError("备份文件和目标数据库不能是同一个文件")

    plan_count = _check_sqlite_database(backup_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{database_path.name}.restore.",
        suffix=".tmp",
        dir=database_path.parent,
    )
    temporary = Path(temporary_name)
    os.close(descriptor)
    try:
        source = sqlite3.connect(backup_path)
        target = sqlite3.connect(temporary)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
        restored_count = _check_sqlite_database(temporary)
        if restored_count != plan_count:
            raise ValueError("恢复后草案数量与备份不一致")
        os.replace(temporary, database_path)
        if _check_sqlite_database(database_path) != plan_count:
            raise ValueError("替换后草案数量与备份不一致")
    finally:
        temporary.unlink(missing_ok=True)
    return {"backup": str(backup_path), "database": str(database_path), "plan_count": restored_count}
