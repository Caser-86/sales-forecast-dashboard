"""Validated immutable inventory snapshot imports."""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.core.config import settings
from app.core.exceptions import InventoryValidationError

REQUIRED_INVENTORY_COLUMNS = {
    "as_of_date",
    "product_id",
    "store_id",
    "on_hand",
    "confirmed_inbound",
    "reserved",
    "lead_time_days",
    "review_period_days",
    "safety_stock",
    "pack_size",
    "minimum_order_quantity",
}
_INVENTORY_ID_PATTERN = re.compile(r"^inventory-[0-9a-f]{16}$")


def _fail(message: str) -> None:
    raise InventoryValidationError(message)


def validate_inventory_frame(frame: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(REQUIRED_INVENTORY_COLUMNS - set(frame.columns))
    if missing:
        _fail(f"缺少必需列: {', '.join(missing)}")
    if frame.empty:
        _fail("库存快照为空")

    normalized = frame.copy()
    normalized["as_of_date"] = pd.to_datetime(normalized["as_of_date"], errors="coerce")
    if normalized["as_of_date"].isna().any():
        _fail("存在非法 as_of_date")
    for column in ("product_id", "store_id"):
        values = pd.to_numeric(normalized[column], errors="coerce")
        if values.isna().any() or not np.isfinite(values).all() or (values <= 0).any() or (values % 1 != 0).any():
            _fail(f"{column} 必须是正整数")
        normalized[column] = values.astype("int64")
    for column in ("on_hand", "confirmed_inbound", "reserved", "safety_stock"):
        values = pd.to_numeric(normalized[column], errors="coerce")
        if values.isna().any() or not np.isfinite(values).all() or (values < 0).any():
            _fail(f"{column} 必须是大于等于 0 的有限数值")
        normalized[column] = values.astype("float64")
    for column in ("lead_time_days", "review_period_days", "pack_size", "minimum_order_quantity"):
        values = pd.to_numeric(normalized[column], errors="coerce")
        if values.isna().any() or not np.isfinite(values).all() or (values < 0).any() or (values % 1 != 0).any():
            _fail(f"{column} 必须是非负整数")
        if column == "pack_size" and (values <= 0).any():
            _fail("pack_size 必须大于 0")
        normalized[column] = values.astype("int64")

    if normalized.duplicated(subset=["as_of_date", "product_id", "store_id"]).any():
        _fail("存在重复的 as_of_date/product_id/store_id 记录")
    return normalized.sort_values(["as_of_date", "product_id", "store_id"]).reset_index(drop=True)


def get_active_inventory_id(*, active_file: Path | None = None) -> str:
    active_path = Path(active_file) if active_file is not None else Path(settings.ACTIVE_INVENTORY_FILE)
    if not active_path.exists():
        return "legacy"
    try:
        inventory_id = json.loads(active_path.read_text(encoding="utf-8"))["inventory_id"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise InventoryValidationError("active 库存指针无效") from exc
    if not isinstance(inventory_id, str) or not _INVENTORY_ID_PATTERN.fullmatch(inventory_id):
        raise InventoryValidationError("active 库存 ID 无效")
    return inventory_id


def get_active_inventory_path(
    *,
    active_file: Path | None = None,
    versions_dir: Path | None = None,
) -> Path | None:
    """Resolve the active snapshot, returning ``None`` before first import."""
    active_path = Path(active_file) if active_file is not None else Path(settings.ACTIVE_INVENTORY_FILE)
    inventory_id = get_active_inventory_id(active_file=active_path)
    if inventory_id == "legacy":
        return None
    root = Path(versions_dir) if versions_dir is not None else active_path.parent / "versions"
    candidate = (root / inventory_id / "inventory.csv").resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise InventoryValidationError("active 库存路径无效") from exc
    if not candidate.is_file():
        raise InventoryValidationError("active 库存快照不存在")
    return candidate


def load_active_inventory_snapshot() -> pd.DataFrame | None:
    path = get_active_inventory_path()
    if path is None:
        return None
    return validate_inventory_frame(pd.read_csv(path))


def import_inventory_snapshot(
    source: Path,
    *,
    versions_dir: Path | None = None,
    active_file: Path | None = None,
    activate: bool = True,
) -> dict[str, Any]:
    source = Path(source)
    if not source.is_file():
        _fail(f"输入文件不存在: {source.name}")
    try:
        raw_bytes = source.read_bytes()
        frame = validate_inventory_frame(pd.read_csv(source))
    except InventoryValidationError:
        raise
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        raise InventoryValidationError(f"无法读取库存快照: {exc}") from exc

    checksum = hashlib.sha256(raw_bytes).hexdigest()
    inventory_id = f"inventory-{checksum[:16]}"
    root = Path(versions_dir) if versions_dir is not None else Path(settings.INVENTORY_VERSIONS_DIR)
    target = root / inventory_id
    target.mkdir(parents=True, exist_ok=True)
    snapshot_path = target / "inventory.csv"
    manifest_path = target / "manifest.json"
    frame.to_csv(snapshot_path, index=False, encoding="utf-8-sig")
    manifest = {
        "inventory_id": inventory_id,
        "source_name": source.name,
        "sha256": checksum,
        "rows": int(len(frame)),
        "as_of_date": frame["as_of_date"].max().date().isoformat(),
        "product_count": int(frame["product_id"].nunique()),
        "store_count": int(frame["store_id"].nunique()),
        "columns": [str(column) for column in frame.columns],
        "created_at_utc": pd.Timestamp.now(tz=timezone.utc).isoformat(timespec="seconds"),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    if activate:
        pointer_path = Path(active_file) if active_file is not None else Path(settings.ACTIVE_INVENTORY_FILE)
        pointer_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = pointer_path.with_name(f".{pointer_path.name}.tmp")
        temporary.write_text(json.dumps({"inventory_id": inventory_id}), encoding="utf-8")
        os.replace(temporary, pointer_path)
    return {
        "inventory_id": inventory_id,
        "snapshot_path": str(snapshot_path),
        "manifest_path": str(manifest_path),
        "manifest": manifest,
        "active": activate,
    }
