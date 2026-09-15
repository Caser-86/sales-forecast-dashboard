"""Liveness and readiness endpoints."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.services.dataset_service import get_active_sales_path

router = APIRouter(tags=["健康检查"])


def _file_status(path: Path) -> str:
    """Return a safe status without exposing the local path to callers."""
    try:
        return "ok" if path.is_file() and path.stat().st_size > 0 else "missing"
    except OSError:
        return "unreadable"


def _report_status(path: Path) -> str:
    status = _file_status(path)
    if status != "ok":
        return status
    try:
        with path.open("r", encoding="utf-8") as report_file:
            report = json.load(report_file)
        return "ok" if isinstance(report, dict) and isinstance(report.get("ensemble"), dict) else "invalid"
    except (OSError, ValueError, TypeError):
        return "invalid"


def _model_runtime_status() -> str:
    """Load the active predictor once so readiness means more than file presence."""
    try:
        from predictor import ForecastPredictor

        ForecastPredictor.get()
        return "ok"
    except Exception:
        return "unreadable"


def _readiness_payload() -> Dict[str, Any]:
    try:
        from artifacts import get_active_model_dir

        models_dir = get_active_model_dir()
    except Exception:
        models_dir = None
    try:
        sales_path = get_active_sales_path()
    except Exception:
        sales_path = None

    def model_file(name: str) -> str:
        return _file_status(models_dir / name) if models_dir is not None else "unreadable"

    def scaler_status(json_name: str, legacy_name: str) -> str:
        if models_dir is None:
            return "unreadable"
        json_status = _file_status(models_dir / json_name)
        return json_status if json_status == "ok" else _file_status(models_dir / legacy_name)

    checks: Dict[str, Dict[str, str]] = {
        "sales_data": {"status": _file_status(sales_path) if sales_path is not None else "unreadable"},
        "features": {"status": _file_status(settings.FEATURES_CSV)},
        "evaluation_report": {"status": _report_status(settings.REPORT_JSON)},
        "lstm_model": {"status": model_file("lstm_model.pth")},
        "lightgbm_model": {"status": model_file("lightgbm_model.txt")},
        "lstm_scaler_x": {"status": scaler_status("lstm_scaler_x.json", "lstm_scaler_x.joblib")},
        "lstm_scaler_y": {"status": scaler_status("lstm_scaler_y.json", "lstm_scaler_y.joblib")},
    }

    assets_ready = all(check["status"] == "ok" for check in checks.values())
    checks["model_runtime"] = {"status": _model_runtime_status() if assets_ready else "skipped"}
    all_ok = assets_ready and checks["model_runtime"]["status"] == "ok"
    return {
        "status": "healthy" if all_ok else "degraded",
        "env": settings.ENV,
        "version": settings.APP_VERSION,
        "auth_enabled": settings.auth_enabled,
        "checks": checks,
    }


@router.get("/live", summary="存活检查")
def liveness_check() -> Dict[str, str]:
    """Confirm that the process is serving requests, without checking dependencies."""
    return {"status": "alive", "env": settings.ENV, "version": settings.APP_VERSION}


@router.get("/health", summary="就绪检查")
@router.get("/ready", summary="就绪检查")
def health_check() -> JSONResponse:
    """Return 503 until every required runtime dependency is usable."""
    payload = _readiness_payload()
    status_code = 200 if payload["status"] == "healthy" else 503
    return JSONResponse(status_code=status_code, content=payload)
