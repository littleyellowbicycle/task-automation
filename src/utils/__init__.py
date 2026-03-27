"""Logging utilities using loguru."""

import sys
from pathlib import Path
from typing import Optional

from loguru import logger

# Global logger configuration state
_configured = False


def setup_logger(
    log_dir: str = "./logs",
    log_level: str = "INFO",
    rotation: str = "100 MB",
    retention: str = "7 days",
    format_string: Optional[str] = None
) -> None:
    """
    Setup the global logger with file rotation and proper formatting.
    
    Args:
        log_dir: Directory for log files
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, etc.)
        rotation: Log rotation size (e.g., "100 MB", "1 GB", "1 hour")
        retention: Log retention period (e.g., "7 days", "1 month")
        format_string: Custom format string for log messages
    """
    global _configured
    
    # Remove default handler
    logger.remove()
    
    # Create log directory if it doesn't exist
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Default format string
    if format_string is None:
        format_string = (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        )
    
    # Add console handler (stderr)
    logger.add(
        sys.stderr,
        format=format_string,
        level=log_level,
        colorize=True,
    )
    
    # Add file handler with rotation
    logger.add(
        log_path / "wechat_automation_{time:YYYY-MM-DD}.log",
        format=format_string,
        level=log_level,
        rotation=rotation,
        retention=retention,
        compression="zip",
        encoding="utf-8",
    )
    
    _configured = True


def get_logger(name: Optional[str] = None):
    """
    Get a logger instance.
    
    If setup_logger has not been called, it will be called automatically
    with default settings.
    
    Args:
        name: Optional name for the logger (for component identification)
    
    Returns:
        A logger instance
    """
    if not _configured:
        setup_logger()
    
    if name:
        return logger.bind(name=name)
    return logger


# Auto-setup on import with defaults
setup_logger()
