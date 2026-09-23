"""Versioned model package publishing and active-model resolution."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.exceptions import ModelArtifactError
from app.services.runtime_state import get_active_runtime_component

CORE_MODEL_FILES = (
    "lstm_model.pth",
    "lightgbm_model.txt",
    "lightgbm_model.txt.meta.json",
    "lstm_scaler_x.json",
    "lstm_scaler_y.json",
    "category_encoder.json",
    "feature_schema.json",
)
REQUIRED_MODEL_FILES = CORE_MODEL_FILES + (
    "model_selection.json",
    "evaluation_report.json",
)
MODEL_SELECTION_FILES = CORE_MODEL_FILES + ("model_selection.json",)
LEGACY_MODEL_FILES = CORE_MODEL_FILES
_MODEL_ID_PATTERN = re.compile(r"^model-[0-9a-f]{16}$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _default_versions_dir() -> Path:
    return Path(settings.MODEL_VERSIONS_DIR)


def _default_active_file() -> Path:
    return Path(settings.ACTIVE_MODEL_FILE)


def _validate_source(source_dir: Path) -> dict[str, str]:
    missing = [name for name in REQUIRED_MODEL_FILES if not (source_dir / name).is_file()]
    if missing:
        raise ModelArtifactError(f"缺少模型产物: {', '.join(missing)}")
    empty = [name for name in REQUIRED_MODEL_FILES if (source_dir / name).stat().st_size <= 0]
    if empty:
        raise ModelArtifactError(f"模型产物为空: {', '.join(empty)}")
    return {name: _sha256(source_dir / name) for name in REQUIRED_MODEL_FILES}


def _write_json_atomically(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    os.close(file_descriptor)
    try:
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        # The pointer is read by the runtime user after host-side publishing.
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _read_pointer(active_file: Path) -> str | None:
    if not active_file.exists():
        return None
    try:
        pointer = json.loads(active_file.read_text(encoding="utf-8"))
        model_id = pointer["model_id"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ModelArtifactError("active 模型指针无效") from exc
    if not isinstance(model_id, str) or not _MODEL_ID_PATTERN.fullmatch(model_id):
        raise ModelArtifactError("active 模型 ID 无效")
    return model_id


def _validate_package(model_dir: Path) -> dict[str, Any]:
    manifest_path = model_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelArtifactError("模型 manifest 无效") from exc
    files = manifest.get("files")
    checksums = manifest.get("checksums")
    allowed_file_lists = (
        list(REQUIRED_MODEL_FILES),
        list(MODEL_SELECTION_FILES),
        list(LEGACY_MODEL_FILES),
    )
    if files not in allowed_file_lists or not isinstance(checksums, dict):
        raise ModelArtifactError("模型 manifest 文件清单无效")
    for filename in files:
        path = model_dir / filename
        if not path.is_file() or path.stat().st_size <= 0:
            raise ModelArtifactError(f"模型版本缺少产物: {filename}")
        if checksums.get(filename) != _sha256(path):
            raise ModelArtifactError(f"模型产物校验失败: {filename}")
    return manifest


def _read_optional_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def publish_model_package(
    source_dir: Path,
    *,
    versions_dir: Path | None = None,
    active_file: Path | None = None,
    activate: bool = True,
    data_version: str = "legacy",
) -> dict[str, Any]:
    """Publish a complete model package, then optionally switch active atomically."""
    source_dir = Path(source_dir)
    checksums = _validate_source(source_dir)
    digest_input = data_version + "|" + "".join(checksums[name] for name in REQUIRED_MODEL_FILES)
    digest = hashlib.sha256(digest_input.encode()).hexdigest()
    model_id = f"model-{digest[:16]}"
    root = Path(versions_dir) if versions_dir is not None else _default_versions_dir()
    target_dir = root / model_id
    root.mkdir(parents=True, exist_ok=True)

    if target_dir.exists():
        existing_manifest = _validate_package(target_dir)
        if existing_manifest.get("data_version") != data_version:
            raise ModelArtifactError("模型版本已存在，但 data_version 不一致")
    else:
        temporary = Path(tempfile.mkdtemp(prefix=f".{model_id}.", dir=root))
        try:
            for filename in REQUIRED_MODEL_FILES:
                shutil.copy2(source_dir / filename, temporary / filename)
            manifest = {
                "model_id": model_id,
                "data_version": data_version,
                "files": list(REQUIRED_MODEL_FILES),
                "checksums": checksums,
                "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            (temporary / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            _validate_package(temporary)
            os.chmod(temporary, 0o755)
            os.replace(temporary, target_dir)
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise

    # Published packages must be traversable by the non-root serving user.
    os.chmod(target_dir, 0o755)

    pointer_path = Path(active_file) if active_file is not None else _default_active_file()
    if activate:
        _write_json_atomically(pointer_path, {"model_id": model_id, "manifest": "manifest.json"})
    return {
        "model_id": model_id,
        "data_version": data_version,
        "model_dir": str(target_dir),
        "manifest_path": str(target_dir / "manifest.json"),
        "active": activate,
    }


def get_active_model_id(*, active_file: Path | None = None) -> str:
    """Return the active model ID, or legacy when no version has been published."""
    if active_file is None:
        runtime_model = get_active_runtime_component("model_version")
        if runtime_model is not None:
            return runtime_model
    return _read_pointer(Path(active_file) if active_file is not None else _default_active_file()) or "legacy"


def get_active_model_dir(
    *,
    active_file: Path | None = None,
    versions_dir: Path | None = None,
    fallback: Path | None = None,
) -> Path:
    """Resolve and verify the active package, falling back to legacy flat files."""
    pointer_path = Path(active_file) if active_file is not None else _default_active_file()
    model_id = get_active_model_id() if active_file is None else _read_pointer(pointer_path)
    if model_id in (None, "legacy"):
        return Path(fallback) if fallback is not None else Path(settings.MODELS_DIR)
    root = Path(versions_dir) if versions_dir is not None else _default_versions_dir()
    candidate = (root / model_id).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ModelArtifactError("active 模型路径无效") from exc
    if not candidate.is_dir():
        raise ModelArtifactError("active 模型版本不存在")
    _validate_package(candidate)
    return candidate


def get_active_model_manifest() -> dict[str, Any] | None:
    """Return the verified active manifest, or ``None`` for legacy flat files."""
    if get_active_model_id() == "legacy":
        return None
    model_dir = get_active_model_dir()
    return _validate_package(model_dir)


def activate_model(model_id: str, *, versions_dir: Path | None = None, active_file: Path | None = None) -> dict[str, Any]:
    """Validate a published package and atomically make it active."""
    if not isinstance(model_id, str) or not _MODEL_ID_PATTERN.fullmatch(model_id):
        raise ModelArtifactError("模型 ID 无效")
    root = Path(versions_dir) if versions_dir is not None else _default_versions_dir()
    model_dir = root / model_id
    manifest = _validate_package(model_dir)
    pointer_path = Path(active_file) if active_file is not None else _default_active_file()
    _write_json_atomically(pointer_path, {"model_id": model_id, "manifest": "manifest.json"})
    return {"model_id": model_id, "model_dir": str(model_dir), "manifest": manifest, "active": True}


def validate_model_package(
    model_id: str,
    *,
    versions_dir: Path | None = None,
) -> dict[str, Any]:
    """Validate and return a published model manifest without changing pointers."""
    if not isinstance(model_id, str) or not _MODEL_ID_PATTERN.fullmatch(model_id):
        raise ModelArtifactError("模型 ID 无效")
    root = Path(versions_dir) if versions_dir is not None else _default_versions_dir()
    model_dir = (root / model_id).resolve()
    try:
        model_dir.relative_to(root.resolve())
    except ValueError as exc:
        raise ModelArtifactError("模型版本路径无效") from exc
    if not model_dir.is_dir():
        raise ModelArtifactError("模型版本不存在")
    return _validate_package(model_dir)


def list_model_versions(*, versions_dir: Path | None = None) -> list[dict[str, Any]]:
    """List valid published model packages for the model center and snapshots."""
    root = Path(versions_dir) if versions_dir is not None else _default_versions_dir()
    versions: list[dict[str, Any]] = []
    if not root.is_dir():
        return versions
    for directory in sorted(root.iterdir(), reverse=True):
        if not directory.is_dir() or not _MODEL_ID_PATTERN.fullmatch(directory.name):
            continue
        try:
            manifest = _validate_package(directory)
        except ModelArtifactError:
            continue
        evaluation = _read_optional_json(directory / "evaluation_report.json")
        selection = _read_optional_json(directory / "model_selection.json")
        metrics = {
            name: {
                "mape": value.get("mape"),
                "rmse": value.get("rmse"),
            }
            for name, value in evaluation.items()
            if isinstance(value, dict) and "mape" in value and "rmse" in value
        }
        checksums = manifest.get("checksums", {})
        package_checksum = hashlib.sha256(
            "".join(str(checksums.get(name, "")) for name in manifest.get("files", [])).encode()
        ).hexdigest()
        versions.append({
            "model_id": directory.name,
            "data_version": manifest.get("data_version", "legacy"),
            "created_at_utc": manifest.get("created_at_utc"),
            "selected_strategy": selection.get("strategy"),
            "metrics": metrics,
            "package_checksum": package_checksum,
            "artifact_count": len(manifest.get("files", [])),
        })
    return versions
