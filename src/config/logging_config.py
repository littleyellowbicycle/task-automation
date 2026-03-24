import logging
from logging.handlers import RotatingFileHandler


def configure_logging(level: int = logging.INFO, log_file: str = "logs/app.log") -> None:
    logger = logging.getLogger()
    if logger.handlers:
        return
    logger.setLevel(level)
    # Ensure log directory exists
    import os
    log_dir = os.path.dirname(log_file) or "."
    os.makedirs(log_dir, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    fh = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3)
    fh.setFormatter(fmt)
    logger.addHandler(fh)
