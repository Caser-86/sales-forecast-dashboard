"""配置兼容层。

正式配置已迁移至 app/core/config.py。
本文件保留旧导入路径，确保已验证的 ML 模块不被破坏。
"""
from __future__ import annotations

# 所有常量从新配置模块重新导出
from app.core.config import (  # noqa: F401
    ACTIVE_DATASET_FILE,
    ACTIVE_MODEL_FILE,
    API_PREFIX,
    BACKEND_DIR,
    DATA_PROCESSED_DIR,
    DATA_RAW_DIR,
    DATABASE_URL,
    DATASET_VERSIONS_DIR,
    FEATURES_CSV,
    LGBM_PATH,
    LSTM_PATH,
    MODEL_VERSIONS_DIR,
    MODELS_DIR,
    PROJECT_ROOT,
    REPORT_JSON,
    SALES_CSV,
    settings,
)
