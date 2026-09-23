"""Read-only access to the active runtime snapshot.

This module intentionally has no imports from dataset, inventory, or model
services. Those services can consult it without creating an import cycle.
"""
from __future__ import annotations

import json
import re
from contextvars import ContextVar, Token
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.exceptions import RuntimeSnapshotError

_SNAPSHOT_ID_PATTERN = re.compile(r"^runtime-[0-9a-f]{16}$")
_RUNTIME_UNSET = object()
_REQUEST_RUNTIME: ContextVar[object] = ContextVar("request_runtime_snapshot", default=_RUNTIME_UNSET)


def _read_active_runtime_snapshot() -> dict[str, Any] | None:
    """Read and verify the process-wide serving pointer."""
    pointer_path = Path(settings.ACTIVE_RUNTIME_SNAPSHOT_FILE)
    if not pointer_path.exists():
        return None
    try:
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        snapshot_id = pointer["snapshot_id"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise RuntimeSnapshotError("active 运行快照指针无效") from exc
    if not isinstance(snapshot_id, str) or not _SNAPSHOT_ID_PATTERN.fullmatch(snapshot_id):
        raise RuntimeSnapshotError("active 运行快照 ID 无效")

    root = Path(settings.RUNTIME_SNAPSHOT_DIR).resolve()
    manifest_path = (root / snapshot_id / "manifest.json").resolve()
    try:
        manifest_path.relative_to(root)
    except ValueError as exc:
        raise RuntimeSnapshotError("active 运行快照路径无效") from exc
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeSnapshotError("active 运行快照 manifest 无效") from exc
    if not isinstance(manifest, dict) or manifest.get("snapshot_id") != snapshot_id:
        raise RuntimeSnapshotError("active 运行快照 manifest 与指针不匹配")
    return manifest


def bind_request_runtime_snapshot() -> Token:
    """Pin the active snapshot for one request until its response completes."""
    return _REQUEST_RUNTIME.set(_read_active_runtime_snapshot())


def reset_request_runtime_snapshot(token: Token) -> None:
    _REQUEST_RUNTIME.reset(token)


def get_active_runtime_snapshot() -> dict[str, Any] | None:
    """Return the request-pinned snapshot, or the verified process pointer."""
    request_value = _REQUEST_RUNTIME.get()
    if request_value is not _RUNTIME_UNSET:
        return request_value  # type: ignore[return-value]
    return _read_active_runtime_snapshot()


def get_active_runtime_component(name: str) -> str | None:
    """Return one component version from the active snapshot."""
    snapshot = get_active_runtime_snapshot()
    if snapshot is None:
        return None
    value = snapshot.get(name)
    return value if isinstance(value, str) and value else None
