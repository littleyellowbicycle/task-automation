from __future__ import annotations

import os
from typing import Any, Dict, List
import yaml
from types import SimpleNamespace

from .models import AppConfig


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
        self._merge_env("OLLAMA_BASE_URL", path=["llm", "ollama"], key="base_url")
        self._merge_env("ANTHROPIC_API_KEY", path=["llm", "anthropic"], key="api_key")
        self._merge_env("OPENAI_API_KEY", path=["llm", "openai"], key="api_key")
        self._merge_env("FEISHU_APP_ID", path=["feishu"], key="app_id")
        self._merge_env("FEISHU_APP_SECRET", path=["feishu"], key="app_secret")
        self._merge_env("FEISHU_TABLE_ID", path=["feishu"], key="table_id")
        self._merge_env("FEISHU_WEBHOOK_URL", path=["feishu"], key="webhook_url")
        self._merge_env("OPENCODE_API_URL", path=["opencode"], key="api_url")
        self._merge_env("OPENCODE_API_KEY", path=["opencode"], key="api_key")
        self._merge_env("FEISHU_ALERT_WEBHOOK", path=["monitoring"], key="alert_webhook")

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
            "llm": {
                "default_provider": "ollama",
                "complexity_threshold": "medium",
                "ollama": {
                    "base_url": "http://localhost:11434",
                    "model": "llama3.2",
                    "timeout": 120,
                    "stream": True,
                },
                "anthropic": {
                    "api_key": "",
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 4096,
                },
                "openai": {
                    "api_key": "",
                    "model": "gpt-4o",
                    "max_tokens": 4096,
                },
            },
            "opencode": {
                "mode": "remote",
                "host": "localhost",
                "port": 18792,
                "work_dir": "./workspace",
                "timeout": 3600,
                "interaction_timeout": 1800,
                "max_retries": 3,
                "retry_delay": 60,
                "cli_path": "opencode",
                "api_url": "",
                "api_key": "",
                "allowed_commands": ["create", "modify", "read"],
                "forbidden_paths": ["/etc", "/root", "/sys", "/proc"],
            },
            "feishu": {
                "app_id": "",
                "app_secret": "",
                "table_id": "",
                "webhook_url": "",
                "token_refresh_buffer": 300,
            },
            "gateway": {
                "host": "0.0.0.0",
                "port": 8000,
                "mode": "standalone",
                "dedup_enabled": True,
                "dedup_max_cache": 1000,
                "dedup_ttl": 3600,
            },
            "worker_urls": {
                "analysis_url": "http://localhost:8001",
                "decision_url": "http://localhost:8002",
                "execution_url": "http://localhost:8003",
                "recording_url": "http://localhost:8004",
            },
            "filter_analysis_worker": {
                "host": "0.0.0.0",
                "port": 8001,
                "gateway_url": "http://localhost:8000",
            },
            "decision_worker": {
                "host": "0.0.0.0",
                "port": 8002,
                "gateway_url": "http://localhost:8000",
            },
            "execution_worker": {
                "host": "0.0.0.0",
                "port": 8003,
                "gateway_url": "http://localhost:8000",
                "opencode_host": "localhost",
                "opencode_port": 18792,
                "work_dir": "./workspace",
                "timeout": 600,
            },
            "recording_worker": {
                "host": "0.0.0.0",
                "port": 8004,
                "gateway_url": "http://localhost:8000",
            },
            "listener_push": {
                "gateway_url": "http://localhost:8000",
                "timeout": 10.0,
                "max_retries": 3,
                "retry_delay": 1.0,
            },
            "filter": {
                "model_name": "Qwen/Qwen3-0.6B",
                "device": "auto",
                "task_threshold": 0.5,
                "dedup_threshold": 0.85,
                "max_history": 100,
                "cache_embeddings": True,
                "timeout": 30.0,
            },
            "queue": {
                "max_size": 20,
                "confirmation_timeout": 10800,
                "processing_timeout": 3600,
                "retry_delay": 60,
                "cleanup_interval": 300,
                "enable_priority": False,
            },
            "decision": {
                "timeout": 10800,
                "poll_interval": 5,
                "reminder_interval": 1800,
                "max_reminders": 3,
            },
            "monitoring": {
                "enabled": True,
                "prometheus_port": 9090,
                "metrics_retention": 3600,
                "log_retention_days": 30,
                "alert_webhook": "",
                "queue_threshold": 15,
                "failure_threshold": 3,
            },
            "workflow": {
                "max_queue_size": 20,
                "confirmation_timeout": 10800,
                "max_concurrent_tasks": 1,
                "retry_attempts": 3,
                "retry_delay": 60,
            },
            "logging": {
                "dir": "logs",
                "level": "INFO",
                "rotation": {
                    "max_size": "100 MB",
                    "retention": "7 days",
                },
                "format": "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            },
            "health_check": {
                "enabled": True,
                "interval": 60,
                "components": ["wechat", "llm", "feishu"],
            },
            "task_filters": {
                "keywords": ["项目发布", "需求", "开发任务", "功能开发", "bug修复", "重构"],
                "regex_patterns": ["^项目发布[:：]", "^需求[:：]", "^开发[:：]"],
            },
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

    @property
    def monitoring(self) -> SimpleNamespace:
        m = self._config.get("monitoring", {})
        return SimpleNamespace(
            enabled=m.get("enabled", True),
            prometheus_port=m.get("prometheus_port", 9090),
            metrics_retention=m.get("metrics_retention", 3600),
            log_retention_days=m.get("log_retention_days", 30),
            alert_webhook=m.get("alert_webhook", ""),
            queue_threshold=m.get("queue_threshold", 15),
            failure_threshold=m.get("failure_threshold", 3),
        )

    @property
    def opencode(self) -> SimpleNamespace:
        o = self._config.get("opencode", {})
        return SimpleNamespace(
            mode=o.get("mode", "remote"),
            host=o.get("host", "localhost"),
            port=o.get("port", 18792),
            work_dir=o.get("work_dir", "./workspace"),
            timeout=o.get("timeout", 3600),
            interaction_timeout=o.get("interaction_timeout", 1800),
            max_retries=o.get("max_retries", 3),
            retry_delay=o.get("retry_delay", 60),
            cli_path=o.get("cli_path", "opencode"),
            api_url=o.get("api_url", ""),
            api_key=o.get("api_key", ""),
            allowed_commands=o.get("allowed_commands", ["create", "modify", "read"]),
            forbidden_paths=o.get("forbidden_paths", ["/etc", "/root", "/sys", "/proc"]),
        )

    @property
    def feishu(self) -> SimpleNamespace:
        f = self._config.get("feishu", {})
        return SimpleNamespace(
            app_id=f.get("app_id", ""),
            app_secret=f.get("app_secret", ""),
            table_id=f.get("table_id", ""),
            webhook_url=f.get("webhook_url", ""),
            token_refresh_buffer=f.get("token_refresh_buffer", 300),
        )

    @property
    def llm(self) -> SimpleNamespace:
        l = self._config.get("llm", {})
        ollama = l.get("ollama", {})
        anthropic = l.get("anthropic", {})
        openai = l.get("openai", {})
        return SimpleNamespace(
            default_provider=l.get("default_provider", "ollama"),
            complexity_threshold=l.get("complexity_threshold", "medium"),
            ollama=SimpleNamespace(
                base_url=ollama.get("base_url", "http://localhost:11434"),
                model=ollama.get("model", "llama3.2"),
                timeout=ollama.get("timeout", 120),
                stream=ollama.get("stream", True),
            ),
            anthropic=SimpleNamespace(
                api_key=anthropic.get("api_key", ""),
                model=anthropic.get("model", "claude-sonnet-4-20250514"),
                max_tokens=anthropic.get("max_tokens", 4096),
            ),
            openai=SimpleNamespace(
                api_key=openai.get("api_key", ""),
                model=openai.get("model", "gpt-4o"),
                max_tokens=openai.get("max_tokens", 4096),
            ),
        )

    def get(self, section: str, key: str, default: Any = None) -> Any:
        return self._config.get(section, {}).get(key, default)

    def as_dict(self) -> Dict[str, Any]:
        return dict(self._config)

    @property
    def config(self) -> AppConfig:
        return AppConfig(**self._config)
