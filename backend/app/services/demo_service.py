"""Deterministic local-demo scenarios, backups, diagnostics, and packaging."""
from __future__ import annotations

import gc
import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.services import data_service, runtime_snapshot_service
from app.services.dataset_service import get_active_dataset_id, get_active_sales_path, import_sales_dataset
from app.services.inventory_dataset_service import (
    get_active_inventory_id,
    get_active_inventory_path,
    import_inventory_snapshot,
)
from app.services.runtime_state import get_active_runtime_snapshot

SCENARIO_DEFINITIONS = {
    "standard": {
        "label": "标准演示",
        "description": "活动运行快照和库存输入均为标准可演示状态。",
        "expected_status": "healthy",
    },
    "stockout": {
        "label": "缺货风险",
        "description": "保持销售和模型版本不变，将可用库存降为 0，突出补货风险。",
        "expected_status": "risk_high",
    },
    "stale_inventory": {
        "label": "库存过期",
        "description": "库存快照使用确定性的历史日期，库存试算应被服务端阻止。",
        "expected_status": "inventory_stale",
    },
    "insufficient_history": {
        "label": "历史不足",
        "description": "只保留最近 7 天销售记录，预测页面应展示历史不足或不可用状态。",
        "expected_status": "insufficient_history",
    },
    "import_error": {
        "label": "导入错误",
        "description": "不切换活动运行快照，展示固定 CSV 行级错误和可恢复提示。",
        "expected_status": "import_rejected",
    },
}

_SCENARIO_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,40}$")
_ARTIFACT_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,120}\.zip$")
_REDACT_PATTERN = re.compile(
    r"(?i)(api[_-]?token|token|password|secret|session|cookie)(\s*[:=]\s*)[^\s,;]+"
)


def _root() -> Path:
    if not settings.DEMO_ROOT:
        raise ValidationError("演示场景和备份操作必须运行在独立 DEMO_ROOT 下")
    root = Path(settings.DEMO_ROOT).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _state_path() -> Path:
    return _root() / "demo-scenario.json"


def _backups_dir() -> Path:
    path = _root() / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _files_identical(source: Path, target: Path) -> bool:
    """Avoid replacing an unchanged file, which matters for Windows file locks."""
    try:
        return target.is_file() and source.stat().st_size == target.stat().st_size and _sha256(source) == _sha256(target)
    except OSError:
        return False


def _safe_relpath(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValidationError("演示文件路径越界") from exc
    return candidate


def _scenario_payload(name: str, *, active_snapshot: str | None = None, error: dict[str, Any] | None = None) -> dict[str, Any]:
    definition = SCENARIO_DEFINITIONS[name]
    return {
        "name": name,
        **definition,
        "active_snapshot_id": active_snapshot,
        "last_error": error,
    }


def _read_state() -> dict[str, Any]:
    path = _state_path()
    if not path.is_file():
        active = get_active_runtime_snapshot()
        return {
            "schema_version": 1,
            "active": "standard",
            "base_snapshot_id": active.get("snapshot_id") if active else None,
            "updated_at_utc": None,
            "scenario": _scenario_payload("standard", active_snapshot=active.get("snapshot_id") if active else None),
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError("演示场景状态文件无效") from exc
    if not isinstance(payload, dict) or payload.get("active") not in SCENARIO_DEFINITIONS:
        raise ValidationError("演示场景状态文件无效")
    return payload


def list_scenarios() -> dict[str, Any]:
    state = _read_state()
    return {
        "active": state["active"],
        "scenario": state["scenario"],
        "scenarios": [
            _scenario_payload(name, active_snapshot=state.get("base_snapshot_id"))
            for name in SCENARIO_DEFINITIONS
        ],
    }


def _component_versions() -> tuple[str, str, str]:
    active = get_active_runtime_snapshot()
    if active:
        return active["data_version"], active["model_version"], active["inventory_version"]
    return get_active_dataset_id(), "legacy", get_active_inventory_id()


def _active_inventory_frame() -> pd.DataFrame:
    path = get_active_inventory_path()
    if path is None:
        raise ValidationError("当前没有可用于场景切换的库存快照")
    return pd.read_csv(path)


def _write_temp_csv(frame: pd.DataFrame, prefix: str) -> Path:
    directory = Path(settings.JOBS_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=prefix, suffix=".csv", dir=directory)
    os.close(descriptor)
    path = Path(name)
    frame.to_csv(path, index=False)
    return path


def _publish_inventory_scenario(name: str) -> dict[str, Any]:
    data_version, model_version, _ = _component_versions()
    frame = _active_inventory_frame()
    if name == "stockout":
        for column in ("on_hand", "confirmed_inbound", "reserved"):
            frame[column] = 0
    else:
        frame["as_of_date"] = (pd.Timestamp("2020-01-01")).date().isoformat()
    source = _write_temp_csv(frame, f"scenario-{name}-")
    try:
        imported = import_inventory_snapshot(source, activate=False)
    finally:
        source.unlink(missing_ok=True)
    return runtime_snapshot_service.publish_runtime_snapshot(
        data_version=data_version,
        model_version=model_version,
        inventory_version=imported["inventory_id"],
        activate=True,
    )


def _publish_insufficient_history() -> dict[str, Any]:
    source_path = get_active_sales_path()
    frame = pd.read_csv(source_path)
    frame["date"] = pd.to_datetime(frame["date"])
    cutoff = frame["date"].max() - timedelta(days=6)
    short = frame[frame["date"] >= cutoff].copy()
    source = _write_temp_csv(short, "scenario-insufficient-history-")
    try:
        imported = import_sales_dataset(source, activate=False)
    finally:
        source.unlink(missing_ok=True)
    _, _, inventory_version = _component_versions()
    return runtime_snapshot_service.publish_runtime_snapshot(
        data_version=imported["dataset_id"],
        model_version="legacy",
        inventory_version=inventory_version,
        activate=True,
    )


def switch_scenario(name: str, *, confirm: bool = False) -> dict[str, Any]:
    if not isinstance(name, str) or not _SCENARIO_PATTERN.fullmatch(name) or name not in SCENARIO_DEFINITIONS:
        raise ValidationError("未知演示场景")
    if not confirm:
        raise ValidationError("切换演示场景需要 confirm=true")

    current = _read_state()
    base_snapshot_id = current.get("base_snapshot_id")
    if not base_snapshot_id:
        active = get_active_runtime_snapshot()
        base_snapshot_id = active.get("snapshot_id") if active else None
    if name == "standard":
        if base_snapshot_id:
            runtime_snapshot_service.activate_runtime_snapshot(base_snapshot_id)
        active = get_active_runtime_snapshot()
        scenario = _scenario_payload("standard", active_snapshot=active.get("snapshot_id") if active else None)
    elif name in {"stockout", "stale_inventory"}:
        snapshot = _publish_inventory_scenario(name)
        scenario = _scenario_payload(name, active_snapshot=snapshot["snapshot_id"])
    elif name == "insufficient_history":
        snapshot = _publish_insufficient_history()
        scenario = _scenario_payload(name, active_snapshot=snapshot["snapshot_id"])
    else:
        scenario = _scenario_payload(
            "import_error",
            active_snapshot=get_active_runtime_snapshot().get("snapshot_id") if get_active_runtime_snapshot() else None,
            error={"row": 2, "column": "sales", "message": "存在负销量，请先明确退货处理策略"},
        )
    state = {
        "schema_version": 1,
        "active": name,
        "base_snapshot_id": base_snapshot_id,
        "updated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scenario": scenario,
    }
    _write_json(_state_path(), state)
    return list_scenarios()


def _database_path() -> Path:
    value = str(settings.DATABASE_URL)
    if value.startswith("sqlite:///"):
        value = value[10:]
    path = Path(value).expanduser().resolve()
    if path == Path(":memory:"):
        raise ValidationError("演示备份不支持内存数据库")
    return path


def _sqlite_backup(target: Path) -> None:
    source_path = _database_path()
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(source_path)
    target_connection = sqlite3.connect(target)
    try:
        source.backup(target_connection)
    finally:
        target_connection.close()
        source.close()


def _validate_sqlite(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValidationError("演示数据库 integrity_check 失败")
        connection.execute("SELECT 1 FROM plan_drafts LIMIT 1").fetchone()
    except sqlite3.Error as exc:
        raise ValidationError("演示数据库结构无效") from exc
    finally:
        connection.close()


def _backup_files(root: Path, stage: Path) -> list[Path]:
    files: list[Path] = []

    def add(path: Path) -> None:
        if path.is_file() and path not in files:
            files.append(path)

    for path in (
        root / "demo-manifest.json",
        root / "demo-scenario.json",
        Path(settings.ACTIVE_DATASET_FILE),
        Path(settings.ACTIVE_INVENTORY_FILE),
        Path(settings.ACTIVE_MODEL_FILE),
        Path(settings.ACTIVE_RUNTIME_SNAPSHOT_FILE),
        Path(settings.SALES_CSV),
        Path(settings.FEATURES_CSV),
        Path(settings.REPORT_JSON),
        Path(settings.DATA_RAW_DIR) / "inventory_snapshot.csv",
    ):
        add(path)
    active = get_active_runtime_snapshot()
    if active:
        snapshot_manifest = Path(settings.RUNTIME_SNAPSHOT_DIR) / active["snapshot_id"] / "manifest.json"
        add(snapshot_manifest)
    for directory in (
        Path(settings.DATASET_VERSIONS_DIR) / get_active_dataset_id(),
        Path(settings.INVENTORY_VERSIONS_DIR) / get_active_inventory_id(),
    ):
        if directory.is_dir():
            for path in directory.iterdir():
                add(path)
    model_id = active.get("model_version") if active else "legacy"
    if model_id != "legacy":
        model_dir = Path(settings.MODEL_VERSIONS_DIR) / model_id
        if model_dir.is_dir():
            for path in model_dir.iterdir():
                add(path)
    database_stage = stage / "dashboard.db"
    _sqlite_backup(database_stage)
    add(database_stage)
    return files


def create_backup(*, artifact_name: str | None = None) -> dict[str, Any]:
    root = _root()
    with tempfile.TemporaryDirectory(prefix="demo-backup-stage-") as temporary:
        stage = Path(temporary)
        files = _backup_files(root, stage)
        entries: list[dict[str, str]] = []
        for path in files:
            relative = "dashboard.db" if path == stage / "dashboard.db" else str(path.resolve().relative_to(root))
            entries.append({"path": relative, "sha256": _sha256(path)})
        manifest = {
            "schema_version": 1,
            "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "scenario": _read_state().get("active", "standard"),
            "files": entries,
        }
        (stage / "backup-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        name = artifact_name or f"demo-backup-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.zip"
        if not _ARTIFACT_PATTERN.fullmatch(name):
            raise ValidationError("备份文件名无效")
        output = _backups_dir() / name
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(stage / "backup-manifest.json", "backup-manifest.json")
            for entry in entries:
                path = _safe_relpath(stage if entry["path"] == "dashboard.db" else root, entry["path"])
                archive.write(path, entry["path"])
    return {"artifact_name": output.name, "path": str(output), "file_count": len(entries), "scenario": manifest["scenario"]}


def list_artifacts() -> dict[str, list[str]]:
    root = _backups_dir()
    return {
        "backups": sorted(path.name for path in root.glob("demo-backup-*.zip")),
        "diagnostics": sorted(path.name for path in root.glob("diagnostic-*.zip")),
    }


def _extract_backup(artifact_name: str) -> tuple[Path, Path, dict[str, Any]]:
    if not _ARTIFACT_PATTERN.fullmatch(artifact_name):
        raise ValidationError("备份文件名无效")
    artifact = _safe_relpath(_backups_dir(), artifact_name)
    if not artifact.is_file():
        raise ValidationError("备份文件不存在")
    stage = Path(tempfile.mkdtemp(prefix="demo-restore-stage-"))
    try:
        with zipfile.ZipFile(artifact) as archive:
            for info in archive.infolist():
                candidate = (stage / info.filename).resolve()
                try:
                    candidate.relative_to(stage.resolve())
                except ValueError as exc:
                    raise ValidationError("备份包含路径穿越条目") from exc
            archive.extractall(stage)
        manifest_path = stage / "backup-manifest.json"
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValidationError("备份 manifest 缺失或无效") from exc
        if payload.get("schema_version") != 1 or not isinstance(payload.get("files"), list):
            raise ValidationError("备份 manifest 无效")
        for entry in payload["files"]:
            relative = entry.get("path", "")
            path = _safe_relpath(stage, relative)
            if not path.is_file() or _sha256(path) != entry.get("sha256"):
                raise ValidationError(f"备份文件校验失败: {relative}")
        _validate_sqlite(stage / "dashboard.db")
        return artifact, stage, payload
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def restore_backup(artifact_name: str) -> dict[str, Any]:
    root = _root()
    _, stage, manifest = _extract_backup(artifact_name)
    targets: list[tuple[Path, Path, bytes | None]] = []
    try:
        runtime_snapshot_service._clear_runtime_caches()
        gc.collect()
        manifest_paths = {entry["path"] for entry in manifest["files"]}
        for entry in manifest["files"]:
            relative = entry["path"]
            source = _safe_relpath(stage, relative)
            target = _database_path() if relative == "dashboard.db" else _safe_relpath(root, relative)
            targets.append((source, target, target.read_bytes() if target.is_file() else None))
        managed_paths = {
            "demo-scenario.json",
            str(Path(settings.ACTIVE_DATASET_FILE).resolve().relative_to(root)),
            str(Path(settings.ACTIVE_INVENTORY_FILE).resolve().relative_to(root)),
            str(Path(settings.ACTIVE_MODEL_FILE).resolve().relative_to(root)),
            str(Path(settings.ACTIVE_RUNTIME_SNAPSHOT_FILE).resolve().relative_to(root)),
        }
        for relative in managed_paths - manifest_paths:
            target = _safe_relpath(root, relative)
            if target.is_file():
                targets.append((Path(), target, target.read_bytes()))
        try:
            for source, target, _ in targets:
                if source == Path():
                    target.unlink(missing_ok=True)
                elif _files_identical(source, target):
                    continue
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    temporary = target.with_name(f".{target.name}.restore.tmp")
                    shutil.copy2(source, temporary)
                    os.replace(temporary, target)
            runtime_snapshot_service._clear_runtime_caches()
            if get_active_runtime_snapshot() is not None:
                runtime_snapshot_service.list_runtime_snapshots()
        except Exception:
            for _, target, previous in targets:
                if previous is None:
                    target.unlink(missing_ok=True)
                else:
                    target.write_bytes(previous)
            runtime_snapshot_service._clear_runtime_caches()
            raise
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return {"artifact_name": artifact_name, "restored": True, "scenario": manifest.get("scenario", "standard")}


def _tail_redacted(path: Path, limit: int = 200) -> str:
    if not path.is_file():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
    return "\n".join(_REDACT_PATTERN.sub(r"\1\2REDACTED", line) for line in lines)


def create_diagnostic_package(*, artifact_name: str | None = None) -> dict[str, Any]:
    _root()
    name = artifact_name or f"diagnostic-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.zip"
    if not _ARTIFACT_PATTERN.fullmatch(name):
        raise ValidationError("诊断包文件名无效")
    state = list_scenarios()
    try:
        from app.core.health import _readiness_payload

        health = _readiness_payload()
    except Exception as exc:
        health = {"status": "error", "message": str(exc)}
    try:
        quality = data_service.get_data_quality()
    except Exception as exc:
        quality = {"status": "error", "message": str(exc)}
    payload = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scenario": state["scenario"],
        "health": health,
        "quality": quality,
        "runtime": get_active_runtime_snapshot(),
        "excluded": ["API_TOKEN", "passwords", "sessions", "database", "user-uploaded source files"],
    }
    output = _backups_dir() / name
    with tempfile.TemporaryDirectory(prefix="demo-diagnostic-stage-") as temporary:
        stage = Path(temporary)
        (stage / "diagnostic.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        logs = stage / "logs"
        for source in (Path(settings.LOG_DIR) / "app.log", Path(settings.LOG_DIR) / "backend-error.log"):
            content = _tail_redacted(source)
            if content:
                target = logs / source.name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in stage.rglob("*"):
                if path.is_file():
                    archive.write(path, str(path.relative_to(stage)))
    return {"artifact_name": output.name, "path": str(output), "excluded": payload["excluded"]}


def package_demo(*, output: Path) -> dict[str, Any]:
    root = _root()
    output = Path(output).expanduser().resolve()
    allowed = [
        root / "demo-manifest.json",
        root / "data" / "raw" / "sales_data.csv",
        root / "data" / "processed" / "features.csv",
        root / "data" / "processed" / "evaluation_report.json",
        root / "data" / "inventory" / "active_inventory.json",
        root / "data" / "inventory" / "inventory_snapshot.csv",
        root / "ml" / "saved_models" / "active_model.json",
    ]
    active_model = root / "ml" / "saved_models"
    for filename in ("lstm_model.pth", "lightgbm_model.txt", "lightgbm_model.txt.meta.json", "lstm_scaler_x.json", "lstm_scaler_y.json", "feature_schema.json", "category_encoder.json", "model_selection.json", "evaluation_report.json"):
        allowed.append(active_model / filename)
    active = get_active_runtime_snapshot()
    if active:
        allowed.append(root / "runtime" / "active_runtime.json")
        allowed.append(root / "runtime" / "versions" / active["snapshot_id"] / "manifest.json")
        if active["data_version"] != "legacy":
            allowed.extend([
                root / "data" / "raw" / "versions" / active["data_version"] / "sales_data.csv",
                root / "data" / "raw" / "versions" / active["data_version"] / "manifest.json",
            ])
        if active["inventory_version"] != "legacy":
            allowed.extend([
                root / "data" / "inventory" / "versions" / active["inventory_version"] / "inventory.csv",
                root / "data" / "inventory" / "versions" / active["inventory_version"] / "manifest.json",
            ])
        if active["model_version"] != "legacy":
            model_root = root / "ml" / "saved_models" / "versions" / active["model_version"]
            if model_root.is_dir():
                allowed.extend(model_root.iterdir())
    files = [path for path in allowed if path.is_file()]
    if not files:
        raise ValidationError("演示包没有可用资源")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, str(path.relative_to(root)))
    return {"path": str(output), "file_count": len(files), "excluded": ["dashboard.db", "logs", "jobs", "uploads", "sessions"]}
