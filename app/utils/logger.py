"""
app/utils/logger.py
Loguru-based structured logging.
Creates logs/ dir automatically.
"""
import sys
from pathlib import Path
from loguru import logger

Path("logs").mkdir(exist_ok=True)

# Remove default handler
logger.remove()

# Human-readable console output
logger.add(
    sys.stdout,
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> — "
        "<level>{message}</level>"
    ),
    level="INFO",
    colorize=True,
)

# Rotating file log
logger.add(
    "logs/app.log",
    rotation="10 MB",
    retention="7 days",
    level="DEBUG",
    serialize=False,
)

__all__ = ["logger"]
