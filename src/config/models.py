"""Configuration models for WeChat Task Automation System."""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class NtWorkListenerConfig(BaseModel):
    device_id: str = ""
    ip: str = "127.0.0.1"
    port: int = 5037
    smart_mode: bool = True


class WebhookListenerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8080
    token: str = ""
    path: str = "/webhook/wechat"


class UIAutomationListenerConfig(BaseModel):
    poll_interval: float = 0.5
    max_history: int = 100


class OCRListenerConfig(BaseModel):
    poll_interval: float = 2.0
    crop_ratio: List[float] = [0.22, 0.0, 1.0, 0.92]
    message_region_height: int = 200


class WeChatConfig(BaseModel):
    listener_type: Literal["ntwork", "webhook", "uiautomation", "ocr"] = "ocr"
    platform: Literal["wework", "wechat"] = "wework"
    device_id: str = ""
    ip: str = "127.0.0.1"
    port: int = 5037
    smart_mode: bool = True
    auto_reconnect: bool = True
    reconnect_interval: int = 5
    message_queue_size: int = 100
    ntwork: NtWorkListenerConfig = Field(default_factory=NtWorkListenerConfig)
    webhook: WebhookListenerConfig = Field(default_factory=WebhookListenerConfig)
    uiautomation: UIAutomationListenerConfig = Field(default_factory=UIAutomationListenerConfig)
    ocr: OCRListenerConfig = Field(default_factory=OCRListenerConfig)


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
    mode: Literal["local", "remote", "api"] = "api"
    host: str = "localhost"
    port: int = 4096
    work_dir: str = "./workspace"
    timeout: int = 3600
    interaction_timeout: int = 1800
    max_retries: int = 3
    retry_delay: int = 60
    cli_path: str = "opencode"
    api_url: str = "http://localhost:4096"
    api_key: str = ""
    model_provider: str = "opencode"
    model_id: str = "minimax-m2.5-free"
    allowed_commands: List[str] = ["create", "modify", "read"]
    forbidden_paths: List[str] = ["/etc", "/root", "/sys", "/proc"]


class FeishuConfig(BaseModel):
    app_id: str = ""
    app_secret: str = ""
    table_id: str = ""
    webhook_url: str = ""
    user_id: str = ""
    token_refresh_buffer: int = 300


class GatewayConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    mode: Literal["standalone", "distributed"] = "standalone"
    dedup_enabled: bool = True
    dedup_max_cache: int = 1000
    dedup_ttl: int = 3600


class WorkerUrlsConfig(BaseModel):
    analysis_url: str = "http://localhost:8001"
    decision_url: str = "http://localhost:8002"
    execution_url: str = "http://localhost:8003"
    recording_url: str = "http://localhost:8004"


class FilterAnalysisWorkerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8001
    gateway_url: str = "http://localhost:8000"


class DecisionWorkerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8002
    gateway_url: str = "http://localhost:8000"


class ExecutionWorkerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8003
    gateway_url: str = "http://localhost:8000"
    opencode_host: str = "localhost"
    opencode_port: int = 4096
    opencode_api_url: str = "http://localhost:4096"
    work_dir: str = "./workspace"
    timeout: int = 600
    model_provider: str = "opencode"
    model_id: str = "minimax-m2.5-free"


class RecordingWorkerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8004
    gateway_url: str = "http://localhost:8000"


class ListenerPushConfig(BaseModel):
    gateway_url: str = "http://localhost:8000"
    timeout: float = 10.0
    max_retries: int = 3
    retry_delay: float = 1.0


class FilterConfig(BaseModel):
    model_name: str = "Qwen/Qwen3-0.6B"
    device: Literal["auto", "cpu", "cuda"] = "auto"
    task_threshold: float = 0.5
    dedup_threshold: float = 0.85
    max_history: int = 100
    cache_embeddings: bool = True
    timeout: float = 30.0


class QueueConfig(BaseModel):
    max_size: int = 20
    confirmation_timeout: int = 10800
    processing_timeout: int = 3600
    retry_delay: int = 60
    cleanup_interval: int = 300
    enable_priority: bool = False


class DecisionConfig(BaseModel):
    timeout: int = 10800
    poll_interval: int = 5
    reminder_interval: int = 1800
    max_reminders: int = 3


class MonitoringConfig(BaseModel):
    enabled: bool = True
    prometheus_port: int = 9090
    metrics_retention: int = 3600
    log_retention_days: int = 30
    alert_webhook: str = ""
    queue_threshold: int = 15
    failure_threshold: int = 3


class TaskFiltersConfig(BaseModel):
    keywords: List[str] = ["项目发布", "需求", "开发任务", "功能开发", "bug修复", "重构"]
    regex_patterns: List[str] = ["^项目发布[:：]", "^需求[:：]", "^开发[:：]"]


class WorkflowConfig(BaseModel):
    max_queue_size: int = 20
    confirmation_timeout: int = 10800
    max_concurrent_tasks: int = 1
    retry_attempts: int = 3
    retry_delay: int = 60


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
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    worker_urls: WorkerUrlsConfig = Field(default_factory=WorkerUrlsConfig)
    filter_analysis_worker: FilterAnalysisWorkerConfig = Field(default_factory=FilterAnalysisWorkerConfig)
    decision_worker: DecisionWorkerConfig = Field(default_factory=DecisionWorkerConfig)
    execution_worker: ExecutionWorkerConfig = Field(default_factory=ExecutionWorkerConfig)
    recording_worker: RecordingWorkerConfig = Field(default_factory=RecordingWorkerConfig)
    listener_push: ListenerPushConfig = Field(default_factory=ListenerPushConfig)
    filter: FilterConfig = Field(default_factory=FilterConfig)
    queue: QueueConfig = Field(default_factory=QueueConfig)
    decision: DecisionConfig = Field(default_factory=DecisionConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    task_filters: TaskFiltersConfig = Field(default_factory=TaskFiltersConfig)
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    health_check: HealthCheckConfig = Field(default_factory=HealthCheckConfig)
