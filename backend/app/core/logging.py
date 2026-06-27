"""结构化日志配置。

- 控制台彩色输出（开发友好）
- 文件轮转（生产可追溯）
- JSON 格式可选（未来对接 ELK）
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import settings

_CONFIGURED = False


class _ColorFormatter(logging.Formatter):
    """控制台彩色格式化器。"""

    COLORS = {
        "DEBUG": "\033[36m",     # cyan
        "INFO": "\033[32m",      # green
        "WARNING": "\033[33m",   # yellow
        "ERROR": "\033[31m",     # red
        "CRITICAL": "\033[41m",  # red bg
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        record.levelname = f"{color}{record.levelname:<7}{self.RESET}"
        return super().format(record)


def setup_logging() -> None:
    """初始化全局日志配置。幂等，可重复调用。"""
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    root = logging.getLogger()
    root.setLevel(log_level)
    # 清除已有 handler（避免 uvicorn 多次初始化导致重复日志）
    root.handlers.clear()

    # 控制台 handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(log_level)
    console.setFormatter(_ColorFormatter(fmt, datefmt))
    root.addHandler(console)

    # 文件 handler（轮转）
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=settings.LOG_FILE_MAX_BYTES,
        backupCount=settings.LOG_FILE_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(fmt, datefmt))
    root.addHandler(file_handler)

    # 降低第三方库噪声
    for noisy in ("uvicorn.access", "matplotlib", "PIL"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True
    logging.getLogger(__name__).info(
        "日志系统初始化完成 | env=%s | level=%s | file=%s",
        settings.ENV, settings.LOG_LEVEL, log_file,
    )


def get_logger(name: str) -> logging.Logger:
    """获取 logger，自动确保已初始化。"""
    if not _CONFIGURED:
        setup_logging()
    return logging.getLogger(name)
