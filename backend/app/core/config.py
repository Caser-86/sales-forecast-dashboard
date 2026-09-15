"""应用配置 - 基于 pydantic-settings，支持 .env 与环境变量。"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py → 项目根目录
APP_DIR = Path(__file__).resolve().parent.parent    # backend/app
BACKEND_DIR = APP_DIR.parent                        # backend
PROJECT_ROOT = BACKEND_DIR.parent                   # sales-forecast-dashboard


class Settings(BaseSettings):
    """应用配置。

    优先级：环境变量 > .env 文件 > 默认值。
    """

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------- 应用 ----------
    APP_NAME: str = "销售数据预测与可视化大屏 API"
    APP_VERSION: str = "1.0.0"
    ENV: str = Field(default="development", description="运行环境: development / production / test")
    DEBUG: bool = Field(default=False, description="调试模式（生产环境必须为 False）")
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ---------- 安全 ----------
    # CORS 允许的源。生产环境应配置为前端实际域名，多个用逗号分隔。
    # 示例: "http://localhost:3000,http://dashboard.example.com"
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5500"
    # 可选 API Token 认证。留空则不启用认证。
    API_TOKEN: str = ""
    API_TOKEN_HEADER: str = "X-API-Token"

    # ---------- 日志 ----------
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = str(BACKEND_DIR / "logs")
    LOG_FILE_MAX_BYTES: int = 10 * 1024 * 1024   # 10 MB
    LOG_FILE_BACKUP_COUNT: int = 5

    # ---------- 数据路径 ----------
    DATA_RAW_DIR: str = str(BACKEND_DIR / "data" / "raw")
    DATA_PROCESSED_DIR: str = str(BACKEND_DIR / "data" / "processed")
    MODELS_DIR: str = str(BACKEND_DIR / "ml" / "saved_models")
    MODEL_VERSIONS_DIR: str = str(BACKEND_DIR / "ml" / "saved_models" / "versions")
    ACTIVE_MODEL_FILE: str = str(BACKEND_DIR / "ml" / "saved_models" / "active_model.json")
    DATASET_VERSIONS_DIR: str = str(BACKEND_DIR / "data" / "raw" / "versions")
    ACTIVE_DATASET_FILE: str = str(BACKEND_DIR / "data" / "raw" / "active_dataset.json")

    # ---------- 数据库（保留扩展点，当前未启用）----------
    DATABASE_URL: str = f"sqlite:///{(BACKEND_DIR / 'dashboard.db').as_posix()}"

    # ---------- API ----------
    API_PREFIX: str = "/api"

    # ---------- 业务参数 ----------
    FORECAST_DAYS: int = 30
    LSTM_SEQ_LEN: int = 14
    ENSEMBLE_WEIGHTS: tuple = (0.4, 0.6)  # (LSTM, LightGBM)
    FORECAST_WORKERS: int = Field(
        default=4,
        ge=1,
        le=16,
        description="批量预测最大并发数",
    )

    # ---------- 限流 ----------
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # ---------- 派生属性 ----------
    @property
    def cors_origin_list(self) -> List[str]:
        """将逗号分隔的 CORS 字符串转为列表。"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_prod(self) -> bool:
        return self.ENV.lower() == "production"

    @property
    def auth_enabled(self) -> bool:
        return bool(self.API_TOKEN)

    @field_validator("ENV")
    @classmethod
    def _normalize_env(cls, v: str) -> str:
        v = v.lower()
        if v not in {"development", "production", "test"}:
            raise ValueError(f"ENV 必须是 development / production / test, 实际: {v}")
        return v

    def ensure_dirs(self) -> None:
        """确保运行时目录存在。"""
        Path(self.LOG_DIR).mkdir(parents=True, exist_ok=True)
        Path(self.DATA_RAW_DIR).mkdir(parents=True, exist_ok=True)
        Path(self.DATA_PROCESSED_DIR).mkdir(parents=True, exist_ok=True)
        Path(self.MODELS_DIR).mkdir(parents=True, exist_ok=True)
        Path(self.MODEL_VERSIONS_DIR).mkdir(parents=True, exist_ok=True)
        Path(self.DATASET_VERSIONS_DIR).mkdir(parents=True, exist_ok=True)

    # ---------- 兼容旧代码的路径常量 ----------
    @property
    def SALES_CSV(self) -> Path:
        return Path(self.DATA_RAW_DIR) / "sales_data.csv"

    @property
    def FEATURES_CSV(self) -> Path:
        return Path(self.DATA_PROCESSED_DIR) / "features.csv"

    @property
    def REPORT_JSON(self) -> Path:
        return Path(self.DATA_PROCESSED_DIR) / "evaluation_report.json"

    @property
    def LSTM_PATH(self) -> Path:
        return Path(self.MODELS_DIR) / "lstm_model.pth"

    @property
    def LGBM_PATH(self) -> Path:
        return Path(self.MODELS_DIR) / "lightgbm_model.txt"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """单例获取配置。"""
    s = Settings()
    s.ensure_dirs()
    return s


# 兼容旧代码的快捷别名（其他模块可直接 from app.core.config import settings）
settings = get_settings()

# 模块级路径常量（保持向后兼容）
DATA_RAW_DIR = Path(settings.DATA_RAW_DIR)
DATA_PROCESSED_DIR = Path(settings.DATA_PROCESSED_DIR)
DATASET_VERSIONS_DIR = Path(settings.DATASET_VERSIONS_DIR)
ACTIVE_DATASET_FILE = Path(settings.ACTIVE_DATASET_FILE)
SALES_CSV = settings.SALES_CSV
FEATURES_CSV = settings.FEATURES_CSV
REPORT_JSON = settings.REPORT_JSON
MODELS_DIR = Path(settings.MODELS_DIR)
MODEL_VERSIONS_DIR = Path(settings.MODEL_VERSIONS_DIR)
ACTIVE_MODEL_FILE = Path(settings.ACTIVE_MODEL_FILE)
LSTM_PATH = settings.LSTM_PATH
LGBM_PATH = settings.LGBM_PATH
DATABASE_URL = settings.DATABASE_URL
API_PREFIX = settings.API_PREFIX
