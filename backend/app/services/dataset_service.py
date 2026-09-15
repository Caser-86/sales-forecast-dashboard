"""Validated, immutable sales dataset imports for the single-tenant V1."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.core.config import settings
from app.core.exceptions import DatasetValidationError

REQUIRED_SALES_COLUMNS = {
    "date",
    "product_id",
    "store_id",
    "product_name",
    "store_name",
    "category",
    "sales",
    "price",
}
_DATASET_ID_PATTERN = re.compile(r"^sales-[0-9a-f]{16}$")


def _fail(message: str) -> None:
    raise DatasetValidationError(message)


def validate_sales_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize the sales contract without writing anything."""
    missing = sorted(REQUIRED_SALES_COLUMNS - set(frame.columns))
    if missing:
        _fail(f"缺少必需列: {', '.join(missing)}")
    if frame.empty:
        _fail("销售数据为空")

    normalized = frame.copy()
    normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce")
    if normalized["date"].isna().any():
        _fail("存在非法日期")

    for column in ("product_id", "store_id"):
        values = pd.to_numeric(normalized[column], errors="coerce")
        if values.isna().any() or not np.isfinite(values).all() or (values <= 0).any() or (values % 1 != 0).any():
            _fail(f"{column} 必须是正整数")
        normalized[column] = values.astype("int64")

    for column in ("sales", "price"):
        values = pd.to_numeric(normalized[column], errors="coerce")
        if values.isna().any() or not np.isfinite(values).all():
            _fail(f"{column} 必须是有限数值")
        if column == "sales" and (values < 0).any():
            _fail("存在负销量，请先明确退货处理策略")
        if column == "price" and (values <= 0).any():
            _fail("price 必须大于 0")
        normalized[column] = values.astype("float64")

    for column in ("product_name", "store_name", "category"):
        if normalized[column].isna().any() or normalized[column].astype(str).str.strip().eq("").any():
            _fail(f"{column} 不能为空")

    key_columns = ["date", "product_id", "store_id"]
    if normalized.duplicated(subset=key_columns).any():
        _fail("存在重复的 date/product_id/store_id 记录")

    return normalized.sort_values(key_columns).reset_index(drop=True)


def _default_versions_dir() -> Path:
    return Path(settings.DATASET_VERSIONS_DIR)


def _default_active_file() -> Path:
    return Path(settings.ACTIVE_DATASET_FILE)


def _write_active_pointer(pointer_path: Path, dataset_id: str) -> None:
    pointer_path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{pointer_path.name}.",
        dir=pointer_path.parent,
    )
    temporary = Path(temporary_name)
    os.close(file_descriptor)
    try:
        temporary.write_text(
            json.dumps({"dataset_id": dataset_id, "manifest": "manifest.json"}, ensure_ascii=False),
            encoding="utf-8",
        )
        # Keep host-generated pointers readable by the container runtime user.
        os.chmod(temporary, 0o644)
        os.replace(temporary, pointer_path)
    finally:
        temporary.unlink(missing_ok=True)


def get_active_dataset_id(*, active_file: Path | None = None) -> str:
    """Return the active dataset ID, or the legacy ID before imports exist."""
    active_path = Path(active_file) if active_file is not None else _default_active_file()
    if not active_path.exists():
        return "legacy"
    try:
        pointer = json.loads(active_path.read_text(encoding="utf-8"))
        dataset_id = pointer["dataset_id"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        _fail("active 数据集指针无效")
    if not isinstance(dataset_id, str) or not _DATASET_ID_PATTERN.fullmatch(dataset_id):
        _fail("active 数据集 ID 无效")
    return dataset_id


def get_active_sales_path(
    *,
    active_file: Path | None = None,
    fallback: Path | None = None,
    versions_dir: Path | None = None,
) -> Path:
    """Resolve the active dataset safely, falling back to the legacy CSV."""
    active_path = Path(active_file) if active_file is not None else _default_active_file()
    fallback_path = Path(fallback) if fallback is not None else settings.SALES_CSV
    if not active_path.exists():
        return fallback_path

    try:
        dataset_id = get_active_dataset_id(active_file=active_path)
    except DatasetValidationError:
        raise
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        _fail("active 数据集指针无效")

    if not isinstance(dataset_id, str) or not _DATASET_ID_PATTERN.fullmatch(dataset_id):
        _fail("active 数据集 ID 无效")
    root = Path(versions_dir) if versions_dir is not None else active_path.parent / "versions"
    candidate = (root / dataset_id / "sales_data.csv").resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        _fail("active 数据集路径无效")
    if not candidate.is_file():
        _fail("active 数据集文件不存在")
    return candidate


def import_sales_dataset(
    source: Path,
    *,
    versions_dir: Path | None = None,
    active_file: Path | None = None,
    activate: bool = True,
) -> dict[str, Any]:
    """Validate and publish a sales CSV as an immutable dataset version."""
    source = Path(source)
    if not source.is_file():
        _fail(f"输入文件不存在: {source.name}")
    try:
        raw_bytes = source.read_bytes()
        frame = validate_sales_frame(pd.read_csv(source))
    except DatasetValidationError:
        raise
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        raise DatasetValidationError(f"无法读取销售数据: {exc}") from exc

    checksum = hashlib.sha256(raw_bytes).hexdigest()
    dataset_id = f"sales-{checksum[:16]}"
    target_root = Path(versions_dir) if versions_dir is not None else _default_versions_dir()
    target_dir = target_root / dataset_id
    target_dir.mkdir(parents=True, exist_ok=True)
    sales_path = target_dir / "sales_data.csv"
    manifest_path = target_dir / "manifest.json"
    frame.to_csv(sales_path, index=False, encoding="utf-8-sig")
    manifest = {
        "dataset_id": dataset_id,
        "source_name": source.name,
        "sha256": checksum,
        "rows": int(len(frame)),
        "date_start": frame["date"].min().date().isoformat(),
        "date_end": frame["date"].max().date().isoformat(),
        "product_count": int(frame["product_id"].nunique()),
        "store_count": int(frame["store_id"].nunique()),
        "columns": [str(column) for column in frame.columns],
        "created_at_utc": pd.Timestamp.now(tz=timezone.utc).isoformat(timespec="seconds"),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    if activate:
        pointer_path = Path(active_file) if active_file is not None else _default_active_file()
        _write_active_pointer(pointer_path, dataset_id)

    return {
        "dataset_id": dataset_id,
        "sales_path": str(sales_path),
        "manifest_path": str(manifest_path),
        "manifest": manifest,
        "active": activate,
    }


def activate_dataset(
    dataset_id: str,
    *,
    versions_dir: Path | None = None,
    active_file: Path | None = None,
) -> dict[str, Any]:
    """Validate an immutable dataset version and atomically make it active."""
    if not isinstance(dataset_id, str) or not _DATASET_ID_PATTERN.fullmatch(dataset_id):
        raise DatasetValidationError("数据集 ID 无效")

    root = Path(versions_dir) if versions_dir is not None else _default_versions_dir()
    version_dir = (root / dataset_id).resolve()
    try:
        version_dir.relative_to(root.resolve())
    except ValueError as exc:
        raise DatasetValidationError("数据集版本路径无效") from exc
    sales_path = version_dir / "sales_data.csv"
    manifest_path = version_dir / "manifest.json"
    if not sales_path.is_file() or not manifest_path.is_file():
        raise DatasetValidationError("数据集版本缺少 sales_data.csv 或 manifest.json")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        frame = validate_sales_frame(pd.read_csv(sales_path))
    except DatasetValidationError:
        raise
    except (OSError, json.JSONDecodeError, ValueError, pd.errors.ParserError) as exc:
        raise DatasetValidationError("数据集版本内容无效") from exc

    if not isinstance(manifest, dict) or manifest.get("dataset_id") != dataset_id:
        raise DatasetValidationError("数据集 manifest 与目录版本不匹配")
    expected = {
        "rows": len(frame),
        "product_count": frame["product_id"].nunique(),
        "store_count": frame["store_id"].nunique(),
        "date_start": frame["date"].min().date().isoformat(),
        "date_end": frame["date"].max().date().isoformat(),
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise DatasetValidationError("数据集 manifest 与内容校验不一致")

    pointer_path = Path(active_file) if active_file is not None else _default_active_file()
    _write_active_pointer(pointer_path, dataset_id)
    return {
        "dataset_id": dataset_id,
        "sales_path": str(sales_path),
        "manifest_path": str(manifest_path),
        "manifest": manifest,
        "active": True,
    }
