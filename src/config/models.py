"""Configuration models for WeChat Task Automation System."""

from typing import List
from pydantic import BaseModel, Field


class WeChatConfig(BaseModel):
    device_id: str = ""
    ip: str = "127.0.0.1"
    port: int = 5037
    auto_reconnect: bool = True
    reconnect_interval: int = 5
    message_queue_size: int = 100


class OllamaConfig(BaseModel):
    base_url: str = "http://localhost:11434"
    model: str = "llama3.2"
    timeout: int = 120
    stream: bool = True


class AnthropicConfig(BaseModel):
    api_key: str = ""
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096


class OpenAIConfig(BaseModel):
    api_key: str = ""
    model: str = "gpt-4o"
    max_tokens: int = 4096


class LLMConfig(BaseModel):
    default_provider: str = "ollama"
    complexity_threshold: str = "medium"
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    anthropic: AnthropicConfig = Field(default_factory=AnthropicConfig)
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)


class OpenCodeConfig(BaseModel):
    host: str = "localhost"
    port: int = 18792
    work_dir: str = "/tmp/opencode_workspace"
    timeout: int = 600
    allowed_commands: List[str] = ["create", "modify", "read"]
    forbidden_paths: List[str] = ["/etc", "/root", "/sys", "/proc"]


class FeishuConfig(BaseModel):
    app_id: str = ""
    app_secret: str = ""
    table_id: str = ""
    token_refresh_buffer: int = 300


class TaskFiltersConfig(BaseModel):
    keywords: List[str] = ["项目发布", "需求", "开发任务", "功能开发", "bug修复", "重构"]
    regex_patterns: List[str] = ["^项目发布[:：]", "^需求[:：]", "^开发[:：]"]


class WorkflowConfig(BaseModel):
    confirm_timeout: int = 300
    max_concurrent_tasks: int = 3
    retry_attempts: int = 3
    retry_delay: int = 5


class LoggingRotationConfig(BaseModel):
    max_size: str = "100 MB"
    retention: str = "7 days"


class LoggingConfig(BaseModel):
    level: str = "INFO"
    dir: str = "./logs"
    rotation: LoggingRotationConfig = Field(default_factory=LoggingRotationConfig)
    format: str = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"


class HealthCheckConfig(BaseModel):
    enabled: bool = True
    interval: int = 60
    components: List[str] = ["wechat", "llm", "feishu"]


class AppConfig(BaseModel):
    wechat: WeChatConfig = Field(default_factory=WeChatConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    opencode: OpenCodeConfig = Field(default_factory=OpenCodeConfig)
    feishu: FeishuConfig = Field(default_factory=FeishuConfig)
    task_filters: TaskFiltersConfig = Field(default_factory=TaskFiltersConfig)
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    health_check: HealthCheckConfig = Field(default_factory=HealthCheckConfig)
