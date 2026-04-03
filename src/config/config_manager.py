from __future__ import annotations

import os
from typing import Any, Dict, List
import yaml
from types import SimpleNamespace


class ConfigManager:
    """Minimal configuration manager with YAML + environment variable overrides."""

    def __init__(self, config_path: str | None = None) -> None:
        self.config_path = config_path or os.path.join("config", "config.yaml")
        self._config: Dict[str, Any] = {}
        self.load()

    def load(self) -> None:
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
        self.set_defaults()
        self._merge_env("WECHAT_DEVICE_ID", path=["wechat"], key="device_id")
        self._merge_env("WECHAT_HOOK_TOKEN", path=["wechat", "webhook"], key="token")
        self._merge_env("OLLAMA_BASE_URL", path=["llm"], key="ollama_base_url")
        self._merge_env("ANTHROPIC_API_KEY", path=["llm"], key="anthropic_api_key")
        self._merge_env("OPENAI_API_KEY", path=["llm"], key="openai_api_key")
        self._merge_env("FEISHU_APP_ID", path=["feishu"], key="app_id")
        self._merge_env("FEISHU_APP_SECRET", path=["feishu"], key="app_secret")
        self._merge_env("FEISHU_TABLE_ID", path=["feishu"], key="table_id")

    def _merge_env(self, env_key: str, path: List[str], key: str) -> None:
        if env_key in os.environ:
            ref = self._config
            for p in path:
                ref = ref.setdefault(p, {})
            ref[key] = os.environ[env_key]

    def set_defaults(self) -> None:
        defaults = {
            "wechat": {
                "listener_type": "uiautomation",
                "platform": "wework",
                "device_id": "",
                "ip": "127.0.0.1",
                "port": 5037,
                "smart_mode": True,
                "auto_reconnect": True,
                "reconnect_interval": 5,
                "message_queue_size": 100,
                "ntwork": {
                    "device_id": "",
                    "ip": "127.0.0.1",
                    "port": 5037,
                    "smart_mode": True,
                },
                "webhook": {
                    "host": "0.0.0.0",
                    "port": 8080,
                    "token": "",
                    "path": "/webhook/wechat",
                },
                "uiautomation": {
                    "poll_interval": 0.5,
                    "max_history": 100,
                },
            },
            "llm": {"ollama_base_url": "", "anthropic_api_key": "", "openai_api_key": ""},
            "opencode": {},
            "feishu": {"app_id": "", "app_secret": "", "table_id": ""},
            "workflow": {"mode": "normal", "log_level": "INFO"},
            "logging": {"dir": "logs", "level": "INFO", "format": "%(levelname)s:%(name)s:%(message)s"},
            "task_filters": {"keywords": ["项目发布", "需求", "开发任务"], "regex_patterns": []},
        }
        def merge(d, u):
            for k, v in u.items():
                if isinstance(v, dict) and isinstance(d.get(k), dict):
                    merge(d[k], v)
                elif k not in d:
                    d[k] = v
        merge(self._config, defaults)
        self._config = self._config

    @property
    def logging_dir(self) -> str:
        return self._config.get("logging", {}).get("dir", "logs")

    @property
    def logging_level(self) -> str:
        return self._config.get("logging", {}).get("level", "INFO")

    @property
    def ollama_base_url(self) -> str:
        return self._config.get("llm", {}).get("ollama_base_url", "")

    @property
    def wechat(self) -> SimpleNamespace:
        w = self._config.get("wechat", {})
        ntwork_config = w.get("ntwork", {})
        webhook_config = w.get("webhook", {})
        uiautomation_config = w.get("uiautomation", {})
        
        return SimpleNamespace(
            listener_type=w.get("listener_type", "uiautomation"),
            platform=w.get("platform", "wework"),
            device_id=w.get("device_id", ""),
            ip=w.get("ip", "127.0.0.1"),
            port=w.get("port", 5037),
            smart_mode=w.get("smart_mode", True),
            auto_reconnect=w.get("auto_reconnect", True),
            reconnect_interval=w.get("reconnect_interval", 5),
            message_queue_size=w.get("message_queue_size", 100),
            ntwork=SimpleNamespace(
                device_id=ntwork_config.get("device_id", ""),
                ip=ntwork_config.get("ip", "127.0.0.1"),
                port=ntwork_config.get("port", 5037),
                smart_mode=ntwork_config.get("smart_mode", True),
            ),
            webhook=SimpleNamespace(
                host=webhook_config.get("host", "0.0.0.0"),
                port=webhook_config.get("port", 8080),
                token=webhook_config.get("token", ""),
                path=webhook_config.get("path", "/webhook/wechat"),
            ),
            uiautomation=SimpleNamespace(
                poll_interval=uiautomation_config.get("poll_interval", 0.5),
                max_history=uiautomation_config.get("max_history", 100),
            ),
        )

    @property
    def task_filters(self) -> SimpleNamespace:
        tf = self._config.get("task_filters", {})
        return SimpleNamespace(keywords=tf.get("keywords", []), regex_patterns=tf.get("regex_patterns", []))

    def get(self, section: str, key: str, default: Any = None) -> Any:
        return self._config.get(section, {}).get(key, default)

    def as_dict(self) -> Dict[str, Any]:
        return dict(self._config)
