from __future__ import annotations

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


def setup_file_logger(
    name: str = "JW8507",
    log_dir: str = "logs",
    filename: str | None = None,
    backup_count: int = 30,
) -> logging.Logger:
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    if filename is None:
        filename = f"{name}.log"

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger

    file_handler = TimedRotatingFileHandler(
        filename=str(log_path / filename),
        when="midnight",
        interval=1,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.suffix = "%Y-%m-%d.log"
    file_handler.namer = lambda path: path.replace(".log.", "_") if ".log." in path else path
    file_handler.setFormatter(
        logging.Formatter(
            fmt="[%(asctime)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(file_handler)
    return logger
