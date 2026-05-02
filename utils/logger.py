"""Loguru-based logger for DS Machine Analyzer.

One configured logger instance shared across the platform. Layers import
this module and use `log` directly:

    from utils.logger import log
    log.info("Cycle complete", machine_id="machine_001", cycle_ms=12345)

Log files rotate daily into `logs/`. Console output is colorized in dev
mode and plain in production (controlled by `DS_MA_LOG_PLAIN` env var).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from loguru import logger as log

_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)

log.remove()

_plain = os.getenv("DS_MA_LOG_PLAIN", "0") == "1"
_console_format = (
    "{time:HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
    if _plain
    else "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)

log.add(
    sys.stderr,
    level=os.getenv("DS_MA_LOG_LEVEL", "INFO"),
    format=_console_format,
    colorize=not _plain,
)

log.add(
    _LOG_DIR / "ds_machine_analyzer_{time:YYYY-MM-DD}.log",
    level="DEBUG",
    rotation="00:00",
    retention="30 days",
    compression="zip",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
)

__all__ = ["log"]
