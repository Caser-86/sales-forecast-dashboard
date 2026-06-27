"""深度健康检查端点。

检查项:
- 数据文件是否存在
- 模型文件是否存在
- 评估报告是否可用
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["健康检查"])


@router.get("/health", summary="深度健康检查")
def health_check() -> Dict[str, Any]:
    """返回服务与依赖组件的健康状态。"""
    checks: Dict[str, Dict[str, Any]] = {}

    # 数据文件检查
    sales_ok = settings.SALES_CSV.exists()
    features_ok = settings.FEATURES_CSV.exists()
    report_ok = settings.REPORT_JSON.exists()

    # 模型文件检查
    lstm_ok = settings.LSTM_PATH.exists()
    lgbm_ok = settings.LGBM_PATH.exists()

    checks["sales_data"] = {"status": "ok" if sales_ok else "missing", "path": str(settings.SALES_CSV)}
    checks["features"] = {"status": "ok" if features_ok else "missing", "path": str(settings.FEATURES_CSV)}
    checks["evaluation_report"] = {"status": "ok" if report_ok else "missing", "path": str(settings.REPORT_JSON)}
    checks["lstm_model"] = {"status": "ok" if lstm_ok else "missing", "path": str(settings.LSTM_PATH)}
    checks["lightgbm_model"] = {"status": "ok" if lgbm_ok else "missing", "path": str(settings.LGBM_PATH)}

    # 整体状态
    all_ok = all(c["status"] == "ok" for c in checks.values())
    overall = "healthy" if all_ok else "degraded"

    return {
        "status": overall,
        "env": settings.ENV,
        "version": settings.APP_VERSION,
        "auth_enabled": settings.auth_enabled,
        "checks": checks,
    }
