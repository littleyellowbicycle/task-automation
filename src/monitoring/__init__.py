"""Monitoring module for metrics collection and alerting."""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable

from ..utils import get_logger
from ..exceptions import WeChatAutomationError

logger = get_logger("monitoring")


class MonitoringError(WeChatAutomationError):
    """Base exception for monitoring errors."""
    pass


@dataclass
class MetricConfig:
    """Configuration for metrics collection."""
    enabled: bool = True
    prometheus_port: int = 9090
    metrics_retention: int = 3600  # seconds
    log_retention_days: int = 30


@dataclass
class AlertConfig:
    """Configuration for alerting."""
    enabled: bool = True
    feishu_webhook: str = ""
    queue_threshold: int = 15
    failure_threshold: int = 3
    llm_timeout_threshold: int = 30  # seconds
    resource_threshold: float = 90.0  # percentage
    service_failure_threshold: int = 3


class MetricsCollector:
    """Metrics collector for the system."""
    
    def __init__(self):
        self._metrics: Dict[str, float] = {}
        self._counters: Dict[str, int] = {}
        self._histograms: Dict[str, List[float]] = {}
        self._start_time = time.time()
    
    def increment_counter(self, name: str, value: int = 1):
        """Increment a counter metric."""
        self._counters[name] = self._counters.get(name, 0) + value
    
    def set_gauge(self, name: str, value: float):
        """Set a gauge metric."""
        self._metrics[name] = value
    
    def record_histogram(self, name: str, value: float):
        """Record a histogram metric."""
        if name not in self._histograms:
            self._histograms[name] = []
        self._histograms[name].append(value)
    
    def get_metrics(self) -> Dict[str, any]:
        """Get all metrics."""
        return {
            "counters": self._counters,
            "gauges": self._metrics,
            "histograms": self._histograms,
            "uptime_seconds": time.time() - self._start_time
        }
    
    def reset(self):
        """Reset all metrics."""
        self._metrics.clear()
        self._counters.clear()
        self._histograms.clear()


class AlertManager:
    """Alert manager for the system."""
    
    def __init__(self, config: AlertConfig):
        self.config = config
        self._alert_history: List[Dict[str, any]] = []
        self._consecutive_failures = 0
        self._consecutive_service_failures = 0
    
    async def check_alert_conditions(
        self,
        queue_size: int,
        failure_count: int,
        llm_inference_time: float,
        resource_usage: float,
        service_health: bool
    ) -> List[str]:
        """Check alert conditions and generate alerts."""
        alerts = []
        
        # Queue backlog alert
        if queue_size > self.config.queue_threshold:
            alerts.append(f"⚠️ 任务队列积压：当前队列大小 {queue_size}，阈值 {self.config.queue_threshold}")
        
        # Consecutive failures alert
        if failure_count > 0:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.config.failure_threshold:
                alerts.append(f"🚨 连续任务失败：已连续 {self._consecutive_failures} 个任务失败")
        else:
            self._consecutive_failures = 0
        
        # LLM timeout alert
        if llm_inference_time > self.config.llm_timeout_threshold:
            alerts.append(f"⏰ LLM 响应超时：{llm_inference_time:.2f}秒，阈值 {self.config.llm_timeout_threshold}秒")
        
        # Resource usage alert
        if resource_usage > self.config.resource_threshold:
            alerts.append(f"💻 系统资源紧张：{resource_usage:.1f}%，阈值 {self.config.resource_threshold}%")
        
        # Service health alert
        if not service_health:
            self._consecutive_service_failures += 1
            if self._consecutive_service_failures >= self.config.service_failure_threshold:
                alerts.append(f"🔌 服务不可用：已连续 {self._consecutive_service_failures} 次连接失败")
        else:
            self._consecutive_service_failures = 0
        
        # Add alerts to history
        for alert in alerts:
            self._alert_history.append({
                "message": alert,
                "timestamp": time.time()
            })
        
        # Keep only recent alerts
        if len(self._alert_history) > 100:
            self._alert_history = self._alert_history[-100:]
        
        return alerts
    
    async def send_alert(self, message: str):
        """Send an alert."""
        if not self.config.feishu_webhook:
            logger.warning("Feishu webhook not configured, cannot send alert")
            return
        
        try:
            import requests
            payload = {
                "msg_type": "text",
                "content": {
                    "text": message
                }
            }
            response = requests.post(
                self.config.feishu_webhook,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            logger.info(f"Alert sent successfully: {message}")
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
    
    async def send_alerts(self, alerts: List[str]):
        """Send multiple alerts."""
        for alert in alerts:
            await self.send_alert(alert)


class MonitoringService:
    """Monitoring service for the system."""
    
    def __init__(
        self,
        metric_config: Optional[MetricConfig] = None,
        alert_config: Optional[AlertConfig] = None
    ):
        self.metric_config = metric_config or MetricConfig()
        self.alert_config = alert_config or AlertConfig()
        self.metrics = MetricsCollector()
        self.alert_manager = AlertManager(self.alert_config)
        self._running = False
        self._prometheus_server = None
    
    async def start(self):
        """Start the monitoring service."""
        if not self.metric_config.enabled:
            logger.info("Monitoring service is disabled")
            return
        
        self._running = True
        logger.info("Starting monitoring service")
        
        # Start Prometheus server if enabled
        if self.metric_config.prometheus_port > 0:
            await self._start_prometheus_server()
        
        # Start health check task
        asyncio.create_task(self._health_check_task())
    
    async def stop(self):
        """Stop the monitoring service."""
        self._running = False
        logger.info("Stopping monitoring service")
        
        if self._prometheus_server:
            try:
                self._prometheus_server.close()
                await self._prometheus_server.wait_closed()
            except Exception as e:
                logger.error(f"Error stopping Prometheus server: {e}")
    
    async def _start_prometheus_server(self):
        """Start Prometheus server."""
        try:
            from prometheus_client import start_http_server
            start_http_server(self.metric_config.prometheus_port)
            logger.info(f"Prometheus server started on port {self.metric_config.prometheus_port}")
        except ImportError:
            logger.warning("prometheus_client not installed, Prometheus metrics disabled")
        except Exception as e:
            logger.error(f"Failed to start Prometheus server: {e}")
    
    async def _health_check_task(self):
        """Health check task."""
        while self._running:
            try:
                # Check system health
                await self._check_system_health()
            except Exception as e:
                logger.error(f"Health check failed: {e}")
            finally:
                await asyncio.sleep(60)  # Check every minute
    
    async def _check_system_health(self):
        """Check system health."""
        # Get queue size from workflow orchestrator
        queue_size = 0
        
        # Get failure count
        failure_count = self.metrics._counters.get("tasks_failed_total", 0)
        
        # Get LLM inference time
        llm_inference_time = self.metrics._metrics.get("llm_inference_duration", 0)
        
        # Get resource usage (mock for now)
        resource_usage = 0.0
        try:
            import psutil
            resource_usage = psutil.cpu_percent()
        except ImportError:
            pass
        
        # Check service health (mock for now)
        service_health = True
        
        # Check alerts
        alerts = await self.alert_manager.check_alert_conditions(
            queue_size,
            failure_count,
            llm_inference_time,
            resource_usage,
            service_health
        )
        
        # Send alerts
        if alerts:
            await self.alert_manager.send_alerts(alerts)
    
    def record_task_received(self):
        """Record a task received."""
        self.metrics.increment_counter("tasks_received_total")
    
    def record_task_completed(self):
        """Record a task completed."""
        self.metrics.increment_counter("tasks_completed_total")
    
    def record_task_failed(self):
        """Record a task failed."""
        self.metrics.increment_counter("tasks_failed_total")
    
    def record_task_duration(self, seconds: float):
        """Record task duration."""
        self.metrics.record_histogram("task_duration_seconds", seconds)
    
    def record_queue_size(self, size: int):
        """Record queue size."""
        self.metrics.set_gauge("queue_size", size)
    
    def record_llm_inference(self, seconds: float):
        """Record LLM inference time."""
        self.metrics.set_gauge("llm_inference_duration", seconds)
        self.metrics.record_histogram("llm_inference_duration_seconds", seconds)
    
    def record_opencode_execution(self, seconds: float):
        """Record OpenCode execution time."""
        self.metrics.set_gauge("opencode_execution_duration", seconds)
        self.metrics.record_histogram("opencode_execution_duration_seconds", seconds)
    
    def get_metrics(self) -> Dict[str, any]:
        """Get all metrics."""
        return self.metrics.get_metrics()
    
    def get_alert_history(self) -> List[Dict[str, any]]:
        """Get alert history."""
        return self.alert_manager._alert_history


# Global monitoring service instance
_monitoring_service: Optional[MonitoringService] = None


def get_monitoring_service() -> MonitoringService:
    """Get the global monitoring service instance."""
    global _monitoring_service
    if _monitoring_service is None:
        _monitoring_service = MonitoringService()
    return _monitoring_service


def initialize_monitoring(
    metric_config: Optional[MetricConfig] = None,
    alert_config: Optional[AlertConfig] = None
) -> MonitoringService:
    """Initialize the monitoring service."""
    global _monitoring_service
    _monitoring_service = MonitoringService(metric_config, alert_config)
    return _monitoring_service