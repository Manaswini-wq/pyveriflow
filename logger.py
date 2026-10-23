"""Logging utilities with color-coded console output."""

import logging
import sys
from pathlib import Path

COLORS = {
    "DEBUG": "\033[36m",     # Cyan
    "INFO": "\033[32m",      # Green
    "WARNING": "\033[33m",   # Yellow
    "ERROR": "\033[31m",     # Red
    "CRITICAL": "\033[35m",  # Magenta
    "RESET": "\033[0m",
}


class ColorFormatter(logging.Formatter):
    """Formatter that adds ANSI color codes to log level."""

    def __init__(self, fmt: str | None = None, datefmt: str | None = None) -> None:
        super().__init__(fmt or "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
                         datefmt or "%Y-%m-%d %H:%M:%S")

    def format(self, record: logging.LogRecord) -> str:
        color = COLORS.get(record.levelname, "")
        reset = COLORS["RESET"]
        record.levelname = f"{color}{record.levelname}{reset}"
        return super().format(record)


def get_logger(
    name: str,
    level: int = logging.INFO,
    log_file: Path | None = None,
) -> logging.Logger:
    """Create a configured logger with console and optional file handlers."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(level)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(ColorFormatter())
    logger.addHandler(console)

    if log_file:
        from logging.handlers import RotatingFileHandler
        fh = RotatingFileHandler(log_file, maxBytes=10_000_000, backupCount=5)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"))
        logger.addHandler(fh)

    return logger
