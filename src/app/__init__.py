"""Main Application Orchestrator for WeChat Task Automation."""

import asyncio
import signal
import sys
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from ..config.config_manager import ConfigManager
from ..gateway import MessageGateway, StandardMessage
from ..filter import TaskFilter, FilterResult, DeduplicationResult
from ..queue import TaskQueue, QueuedTask, TaskStatus
from ..decision import DecisionManager, Decision
from ..executor import CodeExecutor, ExecutionResult
from ..monitoring import get_monitoring, MonitoringService
from ..wechat_listener import ListenerFactory, ListenerType, Platform, BaseListener
from ..feishu_recorder.client import FeishuClient
from ..task_analyzer.analyzer import TaskAnalyzer
from ..utils import get_logger
from ..exceptions import WeChatAutomationError

logger = get_logger("orchestrator")


class ApplicationState(str):
    """Application states."""
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"


class Application:
    """
    Main Application Orchestrator.
    
    Coordinates all components:
    - Listener: Message capture
    - Gateway: Message validation and normalization
    - Filter: Task classification and deduplication
    - Queue: Task queue management
    - Analyzer: Task analysis
    - Decision: User confirmation
    - Executor: Code execution
    - Recorder: Result recording
    - Monitoring: Metrics and alerts
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_manager = ConfigManager(config_path)
        self.state = ApplicationState.INITIALIZING
        
        self._init_components()
        
        self._running = False
        self._tasks: Dict[str, QueuedTask] = {}
        self._consecutive_failures = 0
    
    def _init_components(self) -> None:
        """Initialize all components."""
        config = self.config_manager
        
        self.gateway = MessageGateway()
        
        self.task_filter = TaskFilter()
        
        queue_config = self._get_queue_config()
        self.queue = TaskQueue(queue_config)
        
        decision_config = self._get_decision_config()
        self.decision_manager = DecisionManager(decision_config)
        
        executor_config = self._get_executor_config()
        self.executor = CodeExecutor(executor_config)
        
        self.task_analyzer = TaskAnalyzer()
        
        feishu_config = config._config.get("feishu", {})
        self.feishu_client = FeishuClient(
            app_id=feishu_config.get("app_id", ""),
            app_secret=feishu_config.get("app_secret", ""),
            table_id=feishu_config.get("table_id", ""),
        )
        
        self.monitoring = get_monitoring()
        
        self.listener = self._create_listener()
        
        self._setup_callbacks()
        
        logger.info("All components initialized")
    
    def _get_queue_config(self):
        from ..queue import QueueConfig
        config = self.config_manager._config.get("queue", {})
        return QueueConfig(
            max_size=config.get("max_size", 20),
            confirmation_timeout=config.get("confirmation_timeout", 10800),
            processing_timeout=config.get("processing_timeout", 3600),
        )
    
    def _get_decision_config(self):
        from ..decision import DecisionConfig
        config = self.config_manager._config.get("decision", {})
        feishu = self.config_manager._config.get("feishu", {})
        return DecisionConfig(
            timeout=config.get("timeout", 10800),
            poll_interval=config.get("poll_interval", 5),
            reminder_interval=config.get("reminder_interval", 1800),
            max_reminders=config.get("max_reminders", 3),
            feishu_webhook=feishu.get("webhook_url", ""),
        )
    
    def _get_executor_config(self):
        from ..executor import ExecutorConfig
        config = self.config_manager._config.get("opencode", {})
        return ExecutorConfig(
            mode=config.get("mode", "remote"),
            work_dir=config.get("work_dir", "./workspace"),
            timeout=config.get("timeout", 3600),
            interaction_timeout=config.get("interaction_timeout", 1800),
            max_retries=config.get("max_retries", 3),
            cli_path=config.get("cli_path", "opencode"),
            api_url=config.get("api_url", ""),
            api_key=config.get("api_key", ""),
        )
    
    def _create_listener(self) -> BaseListener:
        """Create the appropriate listener."""
        wechat_config = self.config_manager.wechat
        
        listener_type = ListenerType(wechat_config.listener_type)
        platform = Platform(wechat_config.platform)
        
        kwargs = {}
        if listener_type == ListenerType.UIAUTOMATION:
            kwargs["poll_interval"] = wechat_config.uiautomation.poll_interval
            kwargs["max_history"] = wechat_config.uiautomation.max_history
        elif listener_type == ListenerType.WEBHOOK:
            kwargs["host"] = wechat_config.webhook.host
            kwargs["port"] = wechat_config.webhook.port
            kwargs["token"] = wechat_config.webhook.token
        elif listener_type == ListenerType.NTWORK:
            kwargs["device_id"] = wechat_config.ntwork.device_id
            kwargs["ip"] = wechat_config.ntwork.ip
            kwargs["port"] = wechat_config.ntwork.port
        
        return ListenerFactory.create(
            listener_type=listener_type,
            platform=platform,
            keywords=self.config_manager.task_filters.keywords,
            **kwargs,
        )
    
    def _setup_callbacks(self) -> None:
        """Setup component callbacks."""
        self.gateway.register_handler(self._on_message_received)
        
        self.queue.on_task_added(self._on_task_added)
        self.queue.on_task_started(self._on_task_started)
        self.queue.on_task_completed(self._on_task_completed)
        self.queue.on_task_failed(self._on_task_failed)
        
        self.decision_manager.on_decision(self._on_decision_received)
        
        self.executor.on_progress(self._on_execution_progress)
    
    def _on_message_received(self, message: StandardMessage) -> None:
        """Handle received message from gateway."""
        logger.debug(f"Message received: {message.msg_id}")
        
        self.monitoring.record_task_received()
        
        filter_result, dedup_result = self.task_filter.filter(
            message.content,
            message.msg_id,
        )
        
        if dedup_result.is_duplicate:
            logger.info(f"Duplicate message: {message.msg_id}")
            return
        
        if not filter_result.is_task:
            logger.debug(f"Not a task: {message.msg_id}")
            return
        
        task_id = f"task_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{message.msg_id[:8]}"
        
        task_data = {
            "message": message.to_dict(),
            "filter_result": {
                "confidence": filter_result.confidence,
                "category": filter_result.category,
                "reason": filter_result.reason,
            },
        }
        
        try:
            self.queue.enqueue(task_id, task_data)
            logger.info(f"Task enqueued: {task_id}")
        except Exception as e:
            logger.error(f"Failed to enqueue task: {e}")
    
    def _on_task_added(self, task: QueuedTask) -> None:
        """Handle task added to queue."""
        self.monitoring.update_queue_size(self.queue.size)
        self._tasks[task.task_id] = task
    
    def _on_task_started(self, task: QueuedTask) -> None:
        """Handle task started processing."""
        logger.info(f"Task started: {task.task_id}")
        task.update_status(TaskStatus.ANALYZING)
        
        message_data = task.data.get("message", {})
        content = message_data.get("content", "")
        
        analysis = self.task_analyzer.analyze(content)
        
        task.metadata["analysis"] = analysis
        task.update_status(TaskStatus.AWAITING_CONFIRMATION)
        
        queue_status = f"队列中还有 {self.queue.get_pending_count()} 个任务等待处理"
        
        task_data = {
            "summary": analysis.get("summary", ""),
            "tech_stack": analysis.get("tech_stack", []),
            "core_features": analysis.get("core_features", []),
            "complexity": analysis.get("estimated_complexity", "medium"),
            "source": message_data.get("sender", {}).get("name", "未知"),
            "queue_status": queue_status,
        }
        
        asyncio.create_task(self._wait_for_confirmation(task, task_data))
    
    async def _wait_for_confirmation(self, task: QueuedTask, task_data: Dict[str, Any]) -> None:
        """Wait for user confirmation."""
        decision = await self.decision_manager.wait_confirmation(
            task.task_id,
            task_data,
        )
        
        if decision == Decision.APPROVED:
            await self._execute_task(task)
        elif decision == Decision.LATER:
            self.queue.complete_task(task.task_id, success=False, error="Deferred by user")
        else:
            self.queue.complete_task(task.task_id, success=False, error=f"Rejected: {decision.value}")
    
    def _on_decision_received(self, task_id: str, decision: Decision) -> None:
        """Handle user decision."""
        logger.info(f"Decision received for {task_id}: {decision.value}")
    
    async def _execute_task(self, task: QueuedTask) -> None:
        """Execute a task."""
        task.update_status(TaskStatus.EXECUTING)
        
        analysis = task.metadata.get("analysis", {})
        summary = analysis.get("summary", task.data.get("message", {}).get("content", ""))
        
        instruction = f"创建代码: {summary}"
        
        try:
            result = await self.executor.execute_async(instruction, task.task_id)
            
            if result.success:
                task.metadata["execution_result"] = {
                    "repo_url": result.repo_url,
                    "files_created": result.files_created,
                    "files_modified": result.files_modified,
                    "duration": result.duration,
                }
                self.queue.complete_task(task.task_id, success=True)
                self._consecutive_failures = 0
            else:
                self.queue.complete_task(task.task_id, success=False, error=result.error_message)
                self._consecutive_failures += 1
                
        except Exception as e:
            self.queue.complete_task(task.task_id, success=False, error=str(e))
            self._consecutive_failures += 1
        
        self.monitoring.metrics.gauge("consecutive_failures", self._consecutive_failures)
    
    def _on_task_completed(self, task: QueuedTask) -> None:
        """Handle task completed."""
        logger.info(f"Task completed: {task.task_id}")
        
        self.monitoring.record_task_completed(task.processing_seconds or 0)
        self.monitoring.update_queue_size(self.queue.size)
        
        self._record_to_feishu(task)
    
    def _on_task_failed(self, task: QueuedTask) -> None:
        """Handle task failed."""
        logger.error(f"Task failed: {task.task_id} - {task.error_message}")
        
        self.monitoring.record_task_failed()
        self.monitoring.update_queue_size(self.queue.size)
        
        self._record_to_feishu(task)
    
    def _on_execution_progress(self, task_id: str, progress: int, steps: list) -> None:
        """Handle execution progress update."""
        task = self._tasks.get(task_id)
        if task:
            self.decision_manager.update_card(
                task_id,
                status="executing",
                progress=progress,
                steps=[{"name": s.name, "done": s.status == "completed", "current": s.status == "running"} for s in steps],
                elapsed_seconds=int(task.processing_seconds or 0),
            )
    
    def _record_to_feishu(self, task: QueuedTask) -> None:
        """Record task result to Feishu."""
        try:
            from ..feishu_recorder.models import TaskRecord, TaskStatus as FeishuTaskStatus
            
            analysis = task.metadata.get("analysis", {})
            execution = task.metadata.get("execution_result", {})
            
            status_map = {
                TaskStatus.COMPLETED: FeishuTaskStatus.COMPLETED,
                TaskStatus.FAILED: FeishuTaskStatus.FAILED,
                TaskStatus.CANCELLED: FeishuTaskStatus.FAILED,
                TaskStatus.TIMEOUT: FeishuTaskStatus.FAILED,
            }
            
            record = TaskRecord(
                task_id=task.task_id,
                raw_message=task.data.get("message", {}).get("content", ""),
                summary=analysis.get("summary", ""),
                tech_stack=analysis.get("tech_stack", []),
                core_features=analysis.get("core_features", []),
                status=status_map.get(task.status, FeishuTaskStatus.PENDING),
                code_repo_url=execution.get("repo_url"),
                error_message=task.error_message,
            )
            
            self.feishu_client.create_record(record)
            logger.info(f"Recorded to Feishu: {task.task_id}")
            
        except Exception as e:
            logger.error(f"Failed to record to Feishu: {e}")
    
    async def start(self) -> None:
        """Start the application."""
        logger.info("Starting application...")
        self.state = ApplicationState.INITIALIZING
        
        try:
            await self.listener.connect()
            logger.info("Listener connected")
            
            self._running = True
            self.state = ApplicationState.RUNNING
            
            self.queue.set_processor(self._process_task)
            
            asyncio.create_task(self._monitoring_loop())
            
            logger.info("Application started")
            
            await self.listener.start_listening()
            
        except Exception as e:
            logger.error(f"Failed to start application: {e}")
            self.state = ApplicationState.STOPPED
            raise
    
    def _process_task(self, task: QueuedTask) -> None:
        """Process a task (synchronous wrapper)."""
        pass
    
    async def _monitoring_loop(self) -> None:
        """Periodic monitoring tasks."""
        while self._running:
            try:
                self.monitoring.check_alerts()
                self.monitoring.update_queue_size(self.queue.size)
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
            
            await asyncio.sleep(60)
    
    async def stop(self) -> None:
        """Stop the application."""
        logger.info("Stopping application...")
        self.state = ApplicationState.STOPPING
        
        self._running = False
        
        self.listener.disconnect()
        self.queue.stop_processing()
        
        self.state = ApplicationState.STOPPED
        logger.info("Application stopped")
    
    def pause(self) -> None:
        """Pause processing."""
        if self.state == ApplicationState.RUNNING:
            self.state = ApplicationState.PAUSED
            logger.info("Application paused")
    
    def resume(self) -> None:
        """Resume processing."""
        if self.state == ApplicationState.PAUSED:
            self.state = ApplicationState.RUNNING
            logger.info("Application resumed")
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get application statistics."""
        return {
            "state": self.state,
            "queue": self.queue.stats,
            "gateway": self.gateway.stats,
            "filter": self.task_filter.stats,
            "decision": self.decision_manager.stats,
            "executor": self.executor.stats,
            "monitoring": self.monitoring.stats,
        }


async def main_async(config_path: Optional[str] = None) -> None:
    """Main async entry point."""
    app = Application(config_path)
    
    def signal_handler(sig, frame):
        logger.info("Received shutdown signal")
        asyncio.create_task(app.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await app.start()
    except KeyboardInterrupt:
        await app.stop()


def run(config_path: Optional[str] = None) -> None:
    """Run the application."""
    asyncio.run(main_async(config_path))
