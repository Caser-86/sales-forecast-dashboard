"""Versioned, single-pointer runtime snapshots for local demo serving."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ml.artifacts import get_active_model_id, list_model_versions, validate_model_package

from app.core.config import settings
from app.core.exceptions import AppError, RuntimeSnapshotError
from app.services.dataset_service import (
    get_active_dataset_id,
    list_dataset_versions,
    validate_dataset_version,
)
from app.services.inventory_dataset_service import (
    get_active_inventory_id,
    list_inventory_versions,
    validate_inventory_version,
)
from app.services.runtime_state import get_active_runtime_snapshot

RUNTIME_POLICY_VERSION = "policy-v1"
_SNAPSHOT_ID_PATTERN = re.compile(r"^runtime-[0-9a-f]{16}$")


def _write_json_atomically(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    os.close(descriptor)
    try:
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _version_error(message: str, exc: Exception) -> RuntimeSnapshotError:
    if isinstance(exc, AppError):
        return RuntimeSnapshotError(message, detail=exc.message)
    return RuntimeSnapshotError(message, detail=str(exc))


def validate_runtime_versions(
    *,
    data_version: str,
    model_version: str,
    inventory_version: str,
    data_versions_dir: Path | None = None,
    model_versions_dir: Path | None = None,
    inventory_versions_dir: Path | None = None,
) -> dict[str, Any]:
    """Validate component versions and reject data/model mismatches."""
    if data_version == "legacy":
        if not Path(settings.SALES_CSV).is_file():
            raise RuntimeSnapshotError("legacy 销售数据不存在")
        data_manifest: dict[str, Any] = {"dataset_id": "legacy"}
    else:
        try:
            data_manifest = validate_dataset_version(data_version, versions_dir=data_versions_dir)
        except Exception as exc:
            raise _version_error("销售数据版本不可用", exc) from exc

    if inventory_version == "legacy":
        inventory_manifest: dict[str, Any] = {"inventory_id": "legacy"}
    else:
        try:
            inventory_manifest = validate_inventory_version(
                inventory_version,
                versions_dir=inventory_versions_dir,
            )
        except Exception as exc:
            raise _version_error("库存版本不可用", exc) from exc

    if model_version == "legacy":
        model_manifest: dict[str, Any] = {"model_id": "legacy", "data_version": "legacy"}
    else:
        try:
            model_manifest = validate_model_package(model_version, versions_dir=model_versions_dir)
        except Exception as exc:
            raise _version_error("模型版本不可用", exc) from exc
        if model_manifest.get("data_version") != data_version:
            raise RuntimeSnapshotError(
                "模型与销售数据版本不兼容",
                detail=(
                    f"model={model_manifest.get('data_version')!r}, "
                    f"data={data_version!r}"
                ),
            )
    return {
        "data_manifest": data_manifest,
        "model_manifest": model_manifest,
        "inventory_manifest": inventory_manifest,
    }


def _snapshot_id(data_version: str, model_version: str, inventory_version: str, policy_version: str) -> str:
    value = "|".join((data_version, model_version, inventory_version, policy_version))
    return f"runtime-{hashlib.sha256(value.encode()).hexdigest()[:16]}"


def publish_runtime_snapshot(
    *,
    data_version: str,
    model_version: str,
    inventory_version: str,
    policy_version: str = RUNTIME_POLICY_VERSION,
    activate: bool = False,
    snapshots_dir: Path | None = None,
    active_file: Path | None = None,
    data_versions_dir: Path | None = None,
    model_versions_dir: Path | None = None,
    inventory_versions_dir: Path | None = None,
) -> dict[str, Any]:
    """Create a validated candidate snapshot and optionally activate one pointer."""
    validated = validate_runtime_versions(
        data_version=data_version,
        model_version=model_version,
        inventory_version=inventory_version,
        data_versions_dir=data_versions_dir,
        model_versions_dir=model_versions_dir,
        inventory_versions_dir=inventory_versions_dir,
    )
    snapshot_id = _snapshot_id(data_version, model_version, inventory_version, policy_version)
    root = Path(snapshots_dir) if snapshots_dir is not None else Path(settings.RUNTIME_SNAPSHOT_DIR)
    target = root / snapshot_id
    manifest = {
        "snapshot_id": snapshot_id,
        "schema_version": 1,
        "data_version": data_version,
        "model_version": model_version,
        "inventory_version": inventory_version,
        "policy_version": policy_version,
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "components": {
            "data": validated["data_manifest"],
            "model": validated["model_manifest"],
            "inventory": validated["inventory_manifest"],
        },
    }
    target.mkdir(parents=True, exist_ok=True)
    _write_json_atomically(target / "manifest.json", manifest)
    if activate:
        pointer_path = Path(active_file) if active_file is not None else Path(settings.ACTIVE_RUNTIME_SNAPSHOT_FILE)
        _write_json_atomically(pointer_path, {"snapshot_id": snapshot_id, "manifest": "manifest.json"})
        _clear_runtime_caches()
    return {**manifest, "active": activate}


def sync_current_runtime_snapshot(*, activate: bool = True) -> dict[str, Any]:
    """Materialize a snapshot from the current component pointers."""
    return publish_runtime_snapshot(
        data_version=get_active_dataset_id(),
        model_version=get_active_model_id(),
        inventory_version=get_active_inventory_id(),
        activate=activate,
    )


def get_runtime_snapshot(snapshot_id: str) -> dict[str, Any]:
    if not isinstance(snapshot_id, str) or not _SNAPSHOT_ID_PATTERN.fullmatch(snapshot_id):
        raise RuntimeSnapshotError("运行快照 ID 无效")
    root = Path(settings.RUNTIME_SNAPSHOT_DIR).resolve()
    manifest_path = (root / snapshot_id / "manifest.json").resolve()
    try:
        manifest_path.relative_to(root)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise RuntimeSnapshotError("运行快照不存在或 manifest 无效") from exc
    if not isinstance(manifest, dict) or manifest.get("snapshot_id") != snapshot_id:
        raise RuntimeSnapshotError("运行快照 manifest 无效")
    validate_runtime_versions(
        data_version=manifest["data_version"],
        model_version=manifest["model_version"],
        inventory_version=manifest["inventory_version"],
    )
    return manifest


def activate_runtime_snapshot(snapshot_id: str) -> dict[str, Any]:
    """Atomically switch the serving pointer after revalidating every component."""
    manifest = get_runtime_snapshot(snapshot_id)
    pointer_path = Path(settings.ACTIVE_RUNTIME_SNAPSHOT_FILE)
    _write_json_atomically(pointer_path, {"snapshot_id": snapshot_id, "manifest": "manifest.json"})
    _clear_runtime_caches()
    return {**manifest, "active": True}


def list_runtime_snapshots() -> list[dict[str, Any]]:
    root = Path(settings.RUNTIME_SNAPSHOT_DIR)
    snapshots: list[dict[str, Any]] = []
    if not root.is_dir():
        return snapshots
    for directory in sorted(root.iterdir(), reverse=True):
        if not directory.is_dir() or not _SNAPSHOT_ID_PATTERN.fullmatch(directory.name):
            continue
        try:
            snapshots.append(get_runtime_snapshot(directory.name))
        except RuntimeSnapshotError:
            continue
    active = get_active_runtime_snapshot()
    active_id = active.get("snapshot_id") if active else None
    return [{**snapshot, "active": snapshot["snapshot_id"] == active_id} for snapshot in snapshots]


def list_dataset_catalog() -> dict[str, Any]:
    """Return one bounded catalog used by the data-center page."""
    active = get_active_runtime_snapshot()
    return {
        "active_runtime": active,
        "active": {
            "data_version": get_active_dataset_id(),
            "model_version": get_active_model_id(),
            "inventory_version": get_active_inventory_id(),
        },
        "sales": list_dataset_versions(),
        "inventory": list_inventory_versions(),
        "models": list_model_versions(),
        "runtime_snapshots": list_runtime_snapshots(),
    }


def _clear_runtime_caches() -> None:
    from app.services import data_service, forecast_service

    data_service.clear_data_caches()
    forecast_service.clear_forecast_cache()
