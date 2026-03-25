import os
from pathlib import Path
import textwrap

import pytest

from src.config.config_manager import ConfigManager


def test_config_loads_defaults_and_env_override(tmp_path, monkeypatch):
    # Prepare a minimal config YAML in a temp path
    config_file = tmp_path / "config.yaml"
    config_file.write_text(textwrap.dedent("""
    wechat:
      device_id: 'yaml-id'
    llm:
      ollama_base_url: 'http://localhost:11434'
    logging:
      dir: 'logs'
      level: 'INFO'
"""))

    # Set an environment variable to override
    monkeypatch.setenv("WECHAT_DEVICE_ID", "env-id-override")

    cm = ConfigManager(config_path=str(config_file))
    # The environment variable should override YAML value
    assert cm.wechat.device_id == "env-id-override"
    # Other defaults should still be loaded
    assert cm.ollama_base_url == cm.get('llm','ollama_base_url','')
    assert cm.logging_dir == "logs"

def test_config_defaults_without_yaml_and_env():
    # Create an empty ConfigManager with no config.yaml and no env override
    cm0 = ConfigManager(config_path="/nonexistent/path/config.yaml")
    # Should have default values
    assert cm0.logging_dir == cm0.get("logging", "dir", "logs")
    assert cm0.wechat.device_id == ""
