"""Monitoring module for metrics, logging, and alerting."""

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
import threading

import requests

from ..utils import get_logger

logger = get_logger("monitoring")


@dataclass
class MetricValue:
    """A metric value with timestamp."""
    value: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class AlertRule:
    """An alert rule configuration."""
    name: str
    condition: Callable[[float], bool]
    message: str
    severity: str = "warning"  # info, warning, error, critical
    cooldown: int = 300  # seconds between alerts
    last_triggered: float = 0


@dataclass
class MonitoringConfig:
    """Configuration for monitoring."""
    enabled: bool = True
    prometheus_port: int = 9090
    metrics_retention: int = 3600  # 1 hour
    alert_webhook: str = ""
    log_retention_days: int = 30


class MetricsCollector:
    """
    Metrics collector for Prometheus-style metrics.
    
    Supported metric types:
    - Counter: Only increases
    - Gauge: Can increase or decrease
    - Histogram: Distribution of values
    """
    
    def __init__(self, retention: int = 3600):
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[MetricValue]] = defaultdict(list)
        self._retention = retention
        self._lock = threading.Lock()
    
    def counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        """Increment a counter."""
        key = self._make_key(name, labels)
        with self._lock:
            self._counters[key] += value
    
    def gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Set a gauge value."""
        key = self._make_key(name, labels)
        with self._lock:
            self._gauges[key] = value
    
    def histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Record a histogram value."""
        key = self._make_key(name, labels)
        with self._lock:
            self._histograms[key].append(MetricValue(value=value))
            self._cleanup_histogram(key)
    
    def _make_key(self, name: str, labels: Optional[Dict[str, str]] = None) -> str:
        """Make a metric key with labels."""
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"
    
    def _cleanup_histogram(self, key: str) -> None:
        """Clean up old histogram values."""
        cutoff = time.time() - self._retention
        self._histograms[key] = [
            v for v in self._histograms[key]
            if v.timestamp > cutoff
        ]
    
    def get_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """Get counter value."""
        key = self._make_key(name, labels)
        return self._counters.get(key, 0)
    
    def get_gauge(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """Get gauge value."""
        key = self._make_key(name, labels)
        return self._gauges.get(key, 0)
    
    def get_histogram_stats(
        self,
        name: str,
        labels: Optional[Dict[str, str]] = None,
    ) -> Dict[str, float]:
        """Get histogram statistics."""
        key = self._make_key(name, labels)
        values = [v.value for v in self._histograms.get(key, [])]
        
        if not values:
            return {"count": 0, "sum": 0, "avg": 0, "min": 0, "max": 0, "p50": 0, "p95": 0, "p99": 0}
        
        values.sort()
        count = len(values)
        
        return {
            "count": count,
            "sum": sum(values),
            "avg": sum(values) / count,
            "min": values[0],
            "max": values[-1],
            "p50": values[int(count * 0.5)] if count > 0 else 0,
            "p95": values[int(count * 0.95)] if count > 0 else 0,
            "p99": values[int(count * 0.99)] if count > 0 else 0,
        }
    
    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []
        
        with self._lock:
            for key, value in self._counters.items():
                lines.append(f"# TYPE {key.split('{')[0]} counter")
                lines.append(f"{key} {value}")
            
            for key, value in self._gauges.items():
                lines.append(f"# TYPE {key.split('{')[0]} gauge")
                lines.append(f"{key} {value}")
            
            for key in self._histograms:
                stats = self.get_histogram_stats(key.split('{')[0])
                base_name = key.split('{')[0]
                labels = '{' + key.split('{')[1] if '{' in key else ''
                
                lines.append(f"# TYPE {base_name} histogram")
                lines.append(f"{base_name}_count{labels} {stats['count']}")
                lines.append(f"{base_name}_sum{labels} {stats['sum']}")
                lines.append(f"{base_name}_avg{labels} {stats['avg']}")
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Export all metrics as dictionary."""
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {
                    key: self.get_histogram_stats(key.split('{')[0])
                    for key in self._histograms
                },
            }


class AlertManager:
    """
    Alert manager for sending alerts.
    """
    
    def __init__(self, webhook: str = ""):
        self.webhook = webhook
        self._rules: Dict[str, AlertRule] = {}
        self._alert_count = 0
    
    def add_rule(self, rule: AlertRule) -> None:
        """Add an alert rule."""
        self._rules[rule.name] = rule
        logger.info(f"Added alert rule: {rule.name}")
    
    def remove_rule(self, name: str) -> None:
        """Remove an alert rule."""
        self._rules.pop(name, None)
    
    def check(self, metrics: MetricsCollector) -> List[Dict[str, Any]]:
        """Check all rules and trigger alerts."""
        alerts = []
        
        for name, rule in self._rules.items():
            gauge_value = metrics.get_gauge(name)
            
            if rule.condition(gauge_value):
                now = time.time()
                
                if now - rule.last_triggered < rule.cooldown:
                    continue
                
                rule.last_triggered = now
                
                alert = {
                    "name": name,
                    "value": gauge_value,
                    "message": rule.message.format(value=gauge_value),
                    "severity": rule.severity,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                
                alerts.append(alert)
                self._send_alert(alert)
        
        return alerts
    
    def _send_alert(self, alert: Dict[str, Any]) -> None:
        """Send an alert notification."""
        self._alert_count += 1
        
        if not self.webhook:
            logger.warning(f"Alert (no webhook): {alert['message']}")
            return
        
        try:
            severity_emoji = {
                "info": "ℹ️",
                "warning": "⚠️",
                "error": "🚨",
                "critical": "🔥",
            }.get(alert["severity"], "📢")
            
            payload = {
                "msg_type": "text",
                "content": {
                    "text": f"{severity_emoji} {alert['message']}\n\n"
                            f"时间: {alert['timestamp']}\n"
                            f"严重程度: {alert['severity']}"
                },
            }
            
            response = requests.post(
                self.webhook,
                json=payload,
                timeout=10,
            )
            
            if response.status_code == 200:
                logger.info(f"Alert sent: {alert['name']}")
            else:
                logger.error(f"Failed to send alert: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get alert manager statistics."""
        return {
            "total_alerts": self._alert_count,
            "rules_count": len(self._rules),
        }


class MonitoringService:
    """
    Main monitoring service.
    """
    
    def __init__(self, config: Optional[MonitoringConfig] = None):
        self.config = config or MonitoringConfig()
        self.metrics = MetricsCollector(retention=self.config.metrics_retention)
        self.alerts = AlertManager(webhook=self.config.alert_webhook)
        self._setup_default_rules()
        self._running = False
    
    def _setup_default_rules(self) -> None:
        """Setup default alert rules."""
        self.alerts.add_rule(AlertRule(
            name="queue_size",
            condition=lambda v: v > 15,
            message="⚠️ 任务队列积压，当前 {value} 个任务等待处理",
            severity="warning",
        ))
        
        self.alerts.add_rule(AlertRule(
            name="consecutive_failures",
            condition=lambda v: v >= 3,
            message="🚨 连续任务失败，请检查系统状态",
            severity="error",
        ))
        
        self.alerts.add_rule(AlertRule(
            name="llm_latency_seconds",
            condition=lambda v: v > 30,
            message="⏰ LLM 响应超时，当前延迟 {value:.1f}s",
            severity="warning",
        ))
        
        self.alerts.add_rule(AlertRule(
            name="memory_usage_percent",
            condition=lambda v: v > 90,
            message="💻 系统资源紧张，内存使用 {value:.1f}%",
            severity="warning",
        ))
        
        self.alerts.add_rule(AlertRule(
            name="cpu_usage_percent",
            condition=lambda v: v > 90,
            message="💻 系统资源紧张，CPU 使用 {value:.1f}%",
            severity="warning",
        ))
    
    def record_task_received(self) -> None:
        """Record a received task."""
        self.metrics.counter("tasks_received_total")
    
    def record_task_completed(self, duration: float) -> None:
        """Record a completed task."""
        self.metrics.counter("tasks_completed_total")
        self.metrics.histogram("task_duration_seconds", duration)
    
    def record_task_failed(self) -> None:
        """Record a failed task."""
        self.metrics.counter("tasks_failed_total")
    
    def update_queue_size(self, size: int) -> None:
        """Update queue size gauge."""
        self.metrics.gauge("queue_size", size)
    
    def record_llm_inference(self, duration: float) -> None:
        """Record LLM inference duration."""
        self.metrics.histogram("llm_inference_duration_seconds", duration)
        self.metrics.gauge("llm_latency_seconds", duration)
    
    def record_executor_run(self, duration: float) -> None:
        """Record executor run duration."""
        self.metrics.histogram("opencode_execution_duration_seconds", duration)
    
    def update_system_metrics(self) -> None:
        """Update system resource metrics."""
        try:
            import psutil
            
            self.metrics.gauge("memory_usage_percent", psutil.virtual_memory().percent)
            self.metrics.gauge("cpu_usage_percent", psutil.cpu_percent(interval=1))
            
        except ImportError:
            pass
    
    def check_alerts(self) -> List[Dict[str, Any]]:
        """Check and trigger alerts."""
        self.update_system_metrics()
        return self.alerts.check(self.metrics)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all metrics."""
        return self.metrics.to_dict()
    
    def get_prometheus_export(self) -> str:
        """Get Prometheus export."""
        return self.metrics.export_prometheus()
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get monitoring statistics."""
        return {
            "metrics": self.get_metrics(),
            "alerts": self.alerts.stats,
        }


monitoring_service: Optional[MonitoringService] = None


def get_monitoring() -> MonitoringService:
    """Get the global monitoring service."""
    global monitoring_service
    if monitoring_service is None:
        monitoring_service = MonitoringService()
    return monitoring_service
