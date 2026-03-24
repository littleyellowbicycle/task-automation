"""Configuration manager for WeChat Task Automation System."""

import os
import re
from pathlib import Path
from typing import Optional

import yaml
from pydantic import ValidationError

from .models import AppConfig


class ConfigManager:
    """
    Configuration manager that loads config.yaml and supports environment variable overrides.
    
    Environment variables are referenced in config.yaml using ${VAR_NAME} or ${VAR_NAME:-default}
    syntax. These are resolved at runtime.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the configuration manager.
        
        Args:
            config_path: Path to config.yaml. If None, looks for config/config.yaml
                        in the project root.
        """
        if config_path is None:
            # Look for config.yaml in project root or ./config/
            project_root = Path(__file__).parent.parent.parent
            possible_paths = [
                project_root / "config" / "config.yaml",
                project_root / "config.yaml",
                Path("config/config.yaml"),
                Path("config.yaml"),
            ]
            for path in possible_paths:
                if path.exists():
                    config_path = str(path)
                    break
            else:
                raise FileNotFoundError(
                    f"config.yaml not found in any of: {[str(p) for p in possible_paths]}"
                )
        
        self.config_path = config_path
        self._config: Optional[AppConfig] = None
        self._load()
    
    def _resolve_env_vars(self, value: str) -> str:
        """
        Resolve environment variables in a string.
        
        Supports ${VAR_NAME} and ${VAR_NAME:-default} syntax.
        """
        if not isinstance(value, str):
            return value
        
        # Pattern matches ${VAR} or ${VAR:-default}
        pattern = r'\$\{([^}:]+)(?::-([^}]*))?\}'
        
        def replacer(match):
            var_name = match.group(1)
            default = match.group(2) if match.group(2) is not None else ""
            return os.environ.get(var_name, default)
        
        return re.sub(pattern, replacer, value)
    
    def _resolve_dict(self, d: dict) -> dict:
        """Recursively resolve environment variables in a dictionary."""
        result = {}
        for key, value in d.items():
            if isinstance(value, dict):
                result[key] = self._resolve_dict(value)
            elif isinstance(value, str):
                result[key] = self._resolve_env_vars(value)
            elif isinstance(value, list):
                result[key] = [
                    self._resolve_env_vars(item) if isinstance(item, str) else item
                    for item in value
                ]
            else:
                result[key] = value
        return result
    
    def _load(self):
        """Load and validate the configuration."""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            raw_config = yaml.safe_load(f)
        
        # Resolve environment variables
        resolved_config = self._resolve_dict(raw_config)
        
        # Validate with Pydantic
        try:
            self._config = AppConfig(**resolved_config)
        except ValidationError as e:
            raise ValueError(f"Configuration validation failed: {e}")
    
    def reload(self):
        """Reload configuration from file."""
        self._load()
    
    @property
    def wechat(self):
        """Get WeChat configuration."""
        return self._config.wechat
    
    @property
    def llm(self):
        """Get LLM routing configuration."""
        return self._config.llm
    
    @property
    def opencode(self):
        """Get OpenCode configuration."""
        return self._config.opencode
    
    @property
    def feishu(self):
        """Get Feishu configuration."""
        return self._config.feishu
    
    @property
    def task_filters(self):
        """Get task filter configuration."""
        return self._config.task_filters
    
    @property
    def workflow(self):
        """Get workflow configuration."""
        return self._config.workflow
    
    @property
    def logging(self):
        """Get logging configuration."""
        return self._config.logging
    
    @property
    def health_check(self):
        """Get health check configuration."""
        return self._config.health_check
    
    @property
    def config(self):
        """Get the full configuration object."""
        return self._config


# Singleton instance
_instance: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """Get the global configuration instance."""
    global _instance
    if _instance is None:
        _instance = ConfigManager()
    return _instance
