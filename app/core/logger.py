import logging
import logging.handlers
from pathlib import Path
from typing import Optional

from app.core.config import settings

LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "app.log"


def configure_logging(level: Optional[int] = None) -> None:
    """Configure root logging for the application.

    - Creates `logs/` dir if missing.
    - Adds a stream handler and rotating file handler.
    - Sets uvicorn loggers to use the same handlers.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level or (logging.DEBUG if settings.DEBUG else logging.INFO))

    # Formatter
    fmt = "%(asctime)s %(levelname)-8s %(name)s:%(lineno)d - %(message)s"
    formatter = logging.Formatter(fmt)

    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    ch.setLevel(root.level)

    # Rotating file handler
    fh = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    fh.setFormatter(formatter)
    fh.setLevel(root.level)

    # Avoid duplicate handlers on reconfigure
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        root.addHandler(ch)
    if not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root.handlers):
        root.addHandler(fh)

    # Make uvicorn use the same handlers
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = root.handlers
        logger.setLevel(root.level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
