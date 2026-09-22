"""Prepare an isolated, reproducible local demo runtime."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))


def _configure_console_output() -> None:
    """Keep demo preparation logs portable across Windows console encodings."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


_configure_console_output()

if TYPE_CHECKING:
    from app.core.config import Settings

MANIFEST_NAME = "demo-manifest.json"
DEMO_SEED = 42


def _file_status(path: Path) -> str:
    try:
        return "ok" if path.is_file() and path.stat().st_size > 0 else "missing"
    except OSError:
        return "unreadable"


def _active_model_status(settings: "Settings") -> str:
    if _file_status(Path(settings.ACTIVE_MODEL_FILE)) != "ok":
        return "missing"
    try:
        from ml.artifacts import get_active_model_dir

        model_dir = get_active_model_dir()
        required = ("manifest.json", "lstm_model.pth", "lightgbm_model.txt")
        return "ok" if all(_file_status(model_dir / name) == "ok" for name in required) else "invalid"
    except Exception:
        return "invalid"


def check_demo_assets(settings: "Settings") -> dict[str, Any]:
    """Return a safe, non-mutating readiness report for a demo runtime."""
    checks = {
        "sales_data": _file_status(settings.SALES_CSV),
        "features": _file_status(settings.FEATURES_CSV),
        "evaluation_report": _file_status(settings.REPORT_JSON),
        "active_model": _active_model_status(settings),
        "inventory_snapshot": _file_status(Path(settings.ACTIVE_INVENTORY_FILE)),
    }
    missing = [name for name, status in checks.items() if status != "ok"]
    return {"ready": not missing, "checks": checks, "missing": missing}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_manifest(settings: Settings, readiness: dict[str, Any]) -> Path:
    root = Path(settings.DEMO_ROOT).resolve()
    manifest_path = root / MANIFEST_NAME
    manifest = {
        "manifest_version": 1,
        "source": "generated-demo",
        "seed": DEMO_SEED,
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "checks": readiness["checks"],
        "files": {
            "sales_data": str(settings.SALES_CSV.relative_to(root)),
            "features": str(settings.FEATURES_CSV.relative_to(root)),
            "evaluation_report": str(settings.REPORT_JSON.relative_to(root)),
            "inventory_pointer": str(Path(settings.ACTIVE_INVENTORY_FILE).relative_to(root)),
            "model_pointer": str(Path(settings.ACTIVE_MODEL_FILE).relative_to(root)),
        },
    }
    for key, relative_path in manifest["files"].items():
        path = root / relative_path
        if path.is_file():
            manifest.setdefault("checksums", {})[key] = _sha256(path)

    root.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".demo-manifest.", dir=root)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, manifest_path)
    finally:
        temporary.unlink(missing_ok=True)
    return manifest_path


def prepare_demo(root: Path, *, force: bool = False) -> dict[str, Any]:
    """Generate demo data and models under ``root`` when needed."""
    root = Path(root).expanduser().resolve()
    os.environ["DEMO_ROOT"] = str(root)
    from app.core.config import settings

    settings.ensure_dirs()
    readiness = check_demo_assets(settings)
    if readiness["ready"] and not force:
        return {"status": "ready", "manifest": str(root / MANIFEST_NAME), **readiness}

    from app.services.inventory_dataset_service import import_inventory_snapshot
    from ml import data_generator, feature_engineering
    from ml.trainer import train_all

    raw_path = data_generator.generate_sales_data(output_path=str(settings.SALES_CSV))
    feature_engineering.build_features(raw_path=raw_path, output_path=str(settings.FEATURES_CSV))
    inventory_path = data_generator.generate_inventory_snapshot(
        sales_path=raw_path,
        output_path=str(Path(settings.DATA_RAW_DIR) / "inventory_snapshot.csv"),
    )
    import_inventory_snapshot(Path(inventory_path))
    train_all()

    readiness = check_demo_assets(settings)
    if not readiness["ready"]:
        raise RuntimeError(f"演示资源准备失败: {', '.join(readiness['missing'])}")
    manifest_path = _write_manifest(settings, readiness)
    return {"status": "prepared", "manifest": str(manifest_path), **readiness}


def main() -> int:
    parser = argparse.ArgumentParser(description="准备隔离的本地演示数据和模型")
    parser.add_argument("--root", default=os.environ.get("DEMO_ROOT", str(PROJECT_ROOT / ".demo-runtime")))
    parser.add_argument("--force", action="store_true", help="重新生成数据并训练模型")
    args = parser.parse_args()
    result = prepare_demo(Path(args.root), force=args.force)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
