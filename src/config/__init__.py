from .config_manager import ConfigManager
from .logging_config import configure_logging

__all__ = ["ConfigManager", "configure_logging"]

# Initialize with defaults when imported (best-effort)
_config = ConfigManager()
try:
    # If a global logging level is configured, apply it
    lvl = getattr(_config, 'get', lambda s,k,d=None: d)  # dummy access to avoid lint
    configure_logging()
except Exception:
    pass
