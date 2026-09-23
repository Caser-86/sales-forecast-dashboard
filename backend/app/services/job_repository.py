"""SQLite-backed training job state and recovery records."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError

JOB_STATUSES = {"queued", "running", "succeeded", "failed", "interrupted"}
_SENSITIVE_VALUE = re.compile(
    r"(?i)\b(api[_-]?token|authorization|password|secret)\b\s*[:=]\s*[^\s,;]+"
)


def sanitize_error_text(value: Any, *, limit: int) -> str:
    """Redact common credential-shaped values before persisting worker errors."""
    text = str(value or "")
    text = _SENSITIVE_VALUE.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    text = text.replace("Bearer ", "Bearer [REDACTED] ")
    if len(text) > limit:
        return text[: max(0, limit - 3)] + "..."
    return text


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    kind: str
    status: str
    phase: str
    input_data_version: str
    input_model_version: str
    candidate_root: str
    idempotency_key: str
    attempt: int
    created_at: str
    started_at: str | None
    finished_at: str | None
    heartbeat_at: str | None
    pid: int | None
    result: dict[str, Any] | None
    error_code: str | None
    error_message: str | None
    error_detail: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "kind": self.kind,
            "status": self.status,
            "phase": self.phase,
            "input_data_version": self.input_data_version,
            "input_model_version": self.input_model_version,
            "candidate_root": self.candidate_root,
            "attempt": self.attempt,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "heartbeat_at": self.heartbeat_at,
            "pid": self.pid,
            "result": self.result,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "error_detail": self.error_detail,
        }


@dataclass(frozen=True)
class JobSubmission:
    job: JobRecord
    created: bool


class JobRepository:
    """Persist job transitions with SQLite transactions and one active writer."""

    def __init__(self, database: str | Path | None = None):
        self.database = self._resolve_database(database)
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

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _ensure_schema(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS app_schema_migrations "
                "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    payload_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    input_data_version TEXT NOT NULL,
                    input_model_version TEXT NOT NULL,
                    candidate_root TEXT NOT NULL,
                    attempt INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    heartbeat_at TEXT,
                    pid INTEGER,
                    result_json TEXT,
                    error_code TEXT,
                    error_message TEXT,
                    error_detail TEXT
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_status_created "
                "ON jobs(status, created_at DESC)"
            )
            connection.execute(
                "INSERT OR IGNORE INTO app_schema_migrations(version, applied_at) VALUES (?, ?)",
                (1, self._now()),
            )
            connection.commit()

    @staticmethod
    def _payload_hash(data_version: str, model_version: str) -> str:
        payload = json.dumps(
            {"kind": "training", "data_version": data_version, "model_version": model_version},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> JobRecord:
        return JobRecord(
            job_id=row["job_id"],
            kind=row["kind"],
            status=row["status"],
            phase=row["phase"],
            input_data_version=row["input_data_version"],
            input_model_version=row["input_model_version"],
            candidate_root=row["candidate_root"],
            idempotency_key=row["idempotency_key"],
            attempt=int(row["attempt"]),
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            heartbeat_at=row["heartbeat_at"],
            pid=int(row["pid"]) if row["pid"] is not None else None,
            result=json.loads(row["result_json"]) if row["result_json"] else None,
            error_code=row["error_code"],
            error_message=row["error_message"],
            error_detail=row["error_detail"],
        )

    def _get_from_connection(self, connection: sqlite3.Connection, job_id: str) -> JobRecord | None:
        row = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return self._row_to_record(row) if row is not None else None

    def create_training(
        self,
        *,
        idempotency_key: str,
        data_version: str,
        model_version: str,
        candidate_root: str | Path,
    ) -> JobSubmission:
        key = idempotency_key.strip()
        if not key or len(key) > 200:
            raise ValidationError("训练任务必须提供长度不超过 200 的 Idempotency-Key")
        if not data_version or not model_version:
            raise ValidationError("训练任务必须锁定数据版本和模型版本")
        payload_hash = self._payload_hash(data_version, model_version)
        now = self._now()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM jobs WHERE idempotency_key = ?", (key,)
            ).fetchone()
            if existing:
                if existing["payload_hash"] != payload_hash:
                    raise ConflictError("Idempotency-Key 已用于另一份训练输入")
                return JobSubmission(self._row_to_record(existing), False)

            job_id = f"job-{uuid.uuid4().hex}"
            connection.execute(
                """
                INSERT INTO jobs(
                    job_id, kind, idempotency_key, payload_hash, status, phase,
                    input_data_version, input_model_version, candidate_root,
                    attempt, created_at
                ) VALUES (?, 'training', ?, ?, 'queued', 'queued', ?, ?, ?, 1, ?)
                """,
                (
                    job_id,
                    key,
                    payload_hash,
                    data_version,
                    model_version,
                    str(Path(candidate_root).expanduser().resolve()),
                    now,
                ),
            )
            connection.commit()
            row = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return JobSubmission(self._row_to_record(row), True)

    def get(self, job_id: str) -> JobRecord | None:
        with closing(self._connect()) as connection:
            return self._get_from_connection(connection, job_id)

    def list(self, limit: int = 50) -> list[JobRecord]:
        if limit < 1 or limit > 100:
            raise ValidationError("任务列表 limit 必须在 1 到 100 之间")
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC, job_id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def _require(self, connection: sqlite3.Connection, job_id: str) -> JobRecord:
        job = self._get_from_connection(connection, job_id)
        if job is None:
            raise NotFoundError(f"任务 {job_id} 不存在")
        return job

    def claim(self, job_id: str) -> JobRecord:
        """Claim a queued job unless another training job is already running."""
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            job = self._require(connection, job_id)
            if job.status == "running":
                return job
            if job.status != "queued":
                return job
            active = connection.execute(
                "SELECT 1 FROM jobs WHERE status = 'running' AND job_id <> ? LIMIT 1", (job_id,)
            ).fetchone()
            if active:
                return job
            now = self._now()
            connection.execute(
                "UPDATE jobs SET status='running', phase='starting', started_at=COALESCE(started_at, ?), "
                "heartbeat_at=?, error_code=NULL, error_message=NULL, error_detail=NULL "
                "WHERE job_id = ? AND status = 'queued'",
                (now, now, job_id),
            )
            connection.commit()
            return self._require(connection, job_id)

    def attach_pid(self, job_id: str, pid: int) -> JobRecord:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            job = self._require(connection, job_id)
            if job.status not in {"queued", "running"}:
                return job
            connection.execute("UPDATE jobs SET pid = ?, heartbeat_at = ? WHERE job_id = ?", (pid, self._now(), job_id))
            connection.commit()
            return self._require(connection, job_id)

    def update_phase(self, job_id: str, phase: str) -> JobRecord:
        phase = sanitize_error_text(phase, limit=80)
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            job = self._require(connection, job_id)
            if job.status != "running":
                raise ConflictError(f"任务 {job_id} 当前状态不能更新阶段")
            connection.execute(
                "UPDATE jobs SET phase = ?, heartbeat_at = ? WHERE job_id = ?",
                (phase, self._now(), job_id),
            )
            connection.commit()
            return self._require(connection, job_id)

    def succeed(self, job_id: str, result: dict[str, Any]) -> JobRecord:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            job = self._require(connection, job_id)
            if job.status != "running":
                raise ConflictError(f"任务 {job_id} 当前状态不能标记成功")
            now = self._now()
            connection.execute(
                "UPDATE jobs SET status='succeeded', phase='completed', finished_at=?, heartbeat_at=?, "
                "result_json=?, pid=NULL WHERE job_id = ?",
                (now, now, json.dumps(result, ensure_ascii=False, sort_keys=True), job_id),
            )
            connection.commit()
            return self._require(connection, job_id)

    def fail(
        self,
        job_id: str,
        error_code: str,
        error_message: str,
        *,
        detail: str | None = None,
    ) -> JobRecord:
        safe_code = sanitize_error_text(error_code, limit=80) or "JOB_FAILED"
        safe_message = sanitize_error_text(error_message, limit=500) or "任务失败"
        safe_detail = sanitize_error_text(detail, limit=2000) if detail else None
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._require(connection, job_id)
            now = self._now()
            connection.execute(
                "UPDATE jobs SET status='failed', phase='failed', finished_at=?, heartbeat_at=?, pid=NULL, "
                "error_code=?, error_message=?, error_detail=? WHERE job_id = ?",
                (now, now, safe_code, safe_message, safe_detail, job_id),
            )
            connection.commit()
            return self._require(connection, job_id)

    def retry(self, job_id: str, candidate_root: str | Path) -> JobRecord:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            job = self._require(connection, job_id)
            if job.status not in {"failed", "interrupted"}:
                raise ConflictError("只有失败或中断任务可以重试")
            connection.execute(
                "UPDATE jobs SET status='queued', phase='queued', attempt=attempt + 1, "
                "candidate_root=?, started_at=NULL, finished_at=NULL, heartbeat_at=NULL, pid=NULL, "
                "result_json=NULL, error_code=NULL, error_message=NULL, error_detail=NULL WHERE job_id = ?",
                (str(Path(candidate_root).expanduser().resolve()), job_id),
            )
            connection.commit()
            return self._require(connection, job_id)

    def recover_interrupted(self) -> int:
        """Mark abandoned workers as interrupted without implying success."""
        now = self._now()
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "UPDATE jobs SET status='interrupted', phase='interrupted', finished_at=?, heartbeat_at=?, pid=NULL, "
                "error_code='WORKER_INTERRUPTED', error_message=?, error_detail=NULL WHERE status='running'",
                (now, now, "服务重启时任务仍在运行，未视为成功；可显式重试"),
            )
            connection.commit()
            return cursor.rowcount
