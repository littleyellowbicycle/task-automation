from __future__ import annotations

import os
from typing import Any, Dict
import yaml


class ConfigManager:
    """Minimal configuration manager with YAML + environment variable overrides."""

    def __init__(self, config_path: str | None = None) -> None:
        self.config_path = config_path or os.path.join("config", "config.yaml")
        self._config: Dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        # Load YAML config if present
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                try:
                    data = yaml.safe_load(f) or {}
                except Exception:
                    data = {}
        else:
            data = {}
        if not isinstance(data, dict):
            data = {}
        self._config = data

        # Merge environment overrides
        self._merge_env("WECHAT_DEVICE_ID", path=["wechat"], key="device_id")
        self._merge_env("OLLAMA_BASE_URL", path=["llm"], key="ollama_base_url")
        self._merge_env("ANTHROPIC_API_KEY", path=["llm"], key="anthropic_api_key")
        self._merge_env("OPENAI_API_KEY", path=["llm"], key="openai_api_key")
        self._merge_env("FEISHU_APP_ID", path=["feishu"], key="app_id")
        self._merge_env("FEISHU_APP_SECRET", path=["feishu"], key="app_secret")
        self._merge_env("FEISHU_TABLE_ID", path=["feishu"], key="table_id")

    def _merge_env(self, env_key: str, path: list[str], key: str) -> None:
        if env_key in os.environ:
            ref = self._config
            for p in path[:-1]:
                ref = ref.setdefault(p, {})
            ref[path[-1]] = os.environ[env_key]

    def get(self, section: str, key: str, default: Any = None) -> Any:
        return self._config.get(section, {}).get(key, default)

    # Convenience accessors
    @property
    def wechat_device_id(self) -> str:
        return self.get("wechat", "device_id", "")

    @property
    def ollama_base_url(self) -> str:
        return self.get("llm", "ollama_base_url", "")

    @property
    def anthropic_api_key(self) -> str:
        return self.get("llm", "anthropic_api_key", "")

    @property
    def openai_api_key(self) -> str:
        return self.get("llm", "openai_api_key", "")

    @property
    def feishu_app_id(self) -> str:
        return self.get("feishu", "app_id", "")

    @property
    def feishu_app_secret(self) -> str:
        return self.get("feishu", "app_secret", "")

    @property
    def feishu_table_id(self) -> str:
        return self.get("feishu", "table_id", "")
