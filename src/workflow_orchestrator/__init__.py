"""Workflow orchestrator for the WeChat task automation system."""

import asyncio
import hashlib
import time
from enum import Enum
from typing import Optional, Callable, Dict, Any, List
from datetime import datetime, timezone

from ..wechat_listener.models import TaskMessage, WeChatMessage
from ..gateway import MessageGateway, StandardMessage
from ..filter import TaskFilter, FilterResult, DeduplicationResult
from ..queue import TaskQueue, QueueConfig, QueuedTask, TaskStatus, TaskPriority
from ..feishu_recorder.models import TaskRecord
from ..llm_router.router import LLMRouter
from ..task_analyzer import TaskAnalyzer
from ..code_executor import CodeExecutor
from ..feishu_recorder.client import FeishuClient
from ..feishu_recorder.feishu_bridge import FeishuBridge
from ..decision_manager import DecisionManager, Decision
from ..monitoring import get_monitoring_service
from ..utils import get_logger
from ..exceptions import WorkflowError

logger = get_logger("workflow_orchestrator")


class WorkflowState(str, Enum):
    IDLE = "idle"
    CAPTURING = "capturing"
    GATEWAY = "gateway"
    FILTERING = "filtering"
    QUEUING = "queuing"
    ANALYZING = "analyzing"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    EXECUTING = "executing"
    RECORDING = "recording"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowOrchestrator:
    """
    Main orchestrator for the WeChat task automation workflow.
    
    Coordinates the flow: Message Capture → Gateway → Filter → Queue → Analysis → Confirmation → Execution → Recording
    """
    
    def __init__(
        self,
        message_gateway: Optional[MessageGateway] = None,
        task_filter: Optional[TaskFilter] = None,
        task_queue: Optional[TaskQueue] = None,
        llm_router: Optional[LLMRouter] = None,
        code_executor: Optional[CodeExecutor] = None,
        feishu_client: Optional[FeishuClient] = None,
        feishu_bridge: Optional[FeishuBridge] = None,
        decision_manager: Optional[DecisionManager] = None,
        dry_run: bool = False,
    ):
        """
        Initialize the workflow orchestrator.
        
        Args:
            message_gateway: Message gateway instance
            task_filter: Task filter instance
            task_queue: Task queue instance
            llm_router: LLM router instance
            code_executor: Code executor instance
            feishu_client: Feishu client instance
            feishu_bridge: Feishu bridge instance
            decision_manager: Decision manager instance
            dry_run: If True, don't actually execute code
        """
        self.dry_run = dry_run
        
        # Initialize components
        self.message_gateway = message_gateway or MessageGateway()
        self.task_filter = task_filter or TaskFilter()
        self.task_queue = task_queue or TaskQueue(QueueConfig())
        self.llm_router = llm_router or LLMRouter()
        self.task_analyzer = TaskAnalyzer()
        self.code_executor = code_executor or CodeExecutor()
        self.feishu_client = feishu_client or FeishuClient()
        self.feishu_bridge = feishu_bridge or FeishuBridge()
        self.decision_manager = decision_manager or DecisionManager()
        
        # Monitoring service
        self.monitoring = get_monitoring_service()
        
        # State
        self.state = WorkflowState.IDLE
        self.current_task: Optional[TaskRecord] = None
        self._event_hooks: Dict[str, Callable] = {}
        
        # Register message handler
        self.message_gateway.register_handler(self._handle_standard_message)
        
        # Set queue processor
        self.task_queue.set_processor(self._process_queued_task)
        
        # Start queue processor if event loop is running
        try:
            asyncio.get_running_loop()
            asyncio.create_task(self.task_queue.process_async())
        except RuntimeError:
            # No event loop running, will start later
            pass
        
        logger.info("WorkflowOrchestrator initialized")
    
    def on(self, event: str, callback: Callable):
        """Register an event hook."""
        self._event_hooks[event] = callback
        logger.debug(f"Registered hook for event: {event}")
    
    async def _trigger_event(self, event: str, *args, **kwargs):
        """Trigger an event hook."""
        if event in self._event_hooks:
            try:
                await self._event_hooks[event](*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in event hook {event}: {e}")
    
    def _generate_task_id(self, message: str) -> str:
        """Generate a unique task ID."""
        unique_str = f"{message}_{datetime.now().isoformat()}"
        return f"task_{hashlib.md5(unique_str.encode()).hexdigest()[:8]}"
    
    async def _handle_standard_message(self, message: StandardMessage):
        """Handle standard message from gateway."""
        logger.info(f"Received standard message: {message.msg_id}")
        
        # Record task received
        self.monitoring.record_task_received()
        
        # Filter task
        self.state = WorkflowState.FILTERING
        filter_result, dedup_result = self.task_filter.filter(
            message.content,
            message.msg_id
        )
        
        if dedup_result.is_duplicate:
            logger.info(f"Duplicate message detected: {message.msg_id}")
            await self._trigger_event("on_message_duplicate", message, dedup_result)
            return
        
        if not filter_result.is_task:
            logger.info(f"Message is not a task: {message.msg_id}")
            await self._trigger_event("on_message_not_task", message, filter_result)
            return
        
        logger.info(f"Task detected: {message.msg_id}, confidence: {filter_result.confidence}")
        await self._trigger_event("on_task_detected", message, filter_result)
        
        # Create task record
        task_id = self._generate_task_id(message.content)
        task_record = TaskRecord(
            task_id=task_id,
            raw_message=message.content,
            summary="",
            tech_stack=[],
            core_features=[],
            status=TaskStatus.PENDING,
            user_id=message.sender.id,
            user_name=message.sender.name,
            created_at=datetime.now(timezone.utc),
        )
        
        # Enqueue task
        self.state = WorkflowState.QUEUING
        try:
            queued_task = self.task_queue.enqueue(
                task_id=task_id,
                data={
                    "standard_message": message.to_dict(),
                    "filter_result": filter_result.__dict__,
                    "task_record": task_record.__dict__
                },
                priority=TaskPriority.NORMAL if filter_result.confidence < 0.8 else TaskPriority.HIGH
            )
            # Record queue size
            self.monitoring.record_queue_size(self.task_queue.size)
            logger.info(f"Task enqueued: {task_id}")
            await self._trigger_event("on_task_enqueued", task_record, queued_task)
        except Exception as e:
            logger.error(f"Failed to enqueue task: {e}")
            await self._trigger_event("on_task_queue_failed", task_record, e)
    
    async def _process_queued_task(self, queued_task: QueuedTask):
        """Process a queued task."""
        start_time = time.time()
        task_id = queued_task.task_id
        
        try:
            task_data = queued_task.data
            
            # Reconstruct task record
            task_record = TaskRecord(**task_data["task_record"])
            self.current_task = task_record
            
            # Analysis
            self.state = WorkflowState.ANALYZING
            analysis_start = time.time()
            analysis = self.task_analyzer.analyze(task_record.raw_message)
            analysis_duration = time.time() - analysis_start
            
            # Record LLM inference time
            self.monitoring.record_llm_inference(analysis_duration)
            
            task_record.summary = analysis.get("summary", "")
            task_record.tech_stack = analysis.get("tech_stack", [])
            task_record.core_features = analysis.get("core_features", [])
            task_record.complexity = analysis.get("complexity", "simple")
            
            logger.info(f"Task analyzed: {task_id}, complexity: {task_record.complexity}, analysis time: {analysis_duration:.2f}s")
            await self._trigger_event("on_task_analyzed", task_record)
            
            # Send approval card
            if not self.dry_run:
                self.feishu_bridge.send_approval_card(task_record)
            
            # Confirmation
            self.state = WorkflowState.AWAITING_CONFIRMATION
            confirmation = await self.decision_manager.wait_confirmation(
                task_id, 
                task_record, 
                auto_confirm=self.dry_run
            )
            
            if confirmation == Decision.REJECTED:
                task_record.status = TaskStatus.CANCELLED
                await self._trigger_event("on_task_cancelled", task_record)
                self.state = WorkflowState.CANCELLED
                # Record task duration
                task_duration = time.time() - start_time
                self.monitoring.record_task_duration(task_duration)
                return
            
            if confirmation == Decision.TIMEOUT:
                task_record.status = TaskStatus.TIMEOUT
                await self._trigger_event("on_task_timeout", task_record)
                self.state = WorkflowState.FAILED
                # Record task failure
                self.monitoring.record_task_failed()
                # Record task duration
                task_duration = time.time() - start_time
                self.monitoring.record_task_duration(task_duration)
                return
            
            task_record.status = TaskStatus.APPROVED
            await self._trigger_event("on_task_confirmed", task_record)
            
            # Execution
            self.state = WorkflowState.EXECUTING
            task_record.status = TaskStatus.EXECUTING
            logger.info("Executing code generation...")
            
            execution_start = time.time()
            instruction = f"创建代码: {task_record.summary}"
            result = await self.code_executor.execute(instruction, dry_run=self.dry_run)
            execution_duration = time.time() - execution_start
            
            # Record OpenCode execution time
            self.monitoring.record_opencode_execution(execution_duration)
            
            task_record.executor_result = result.stdout if result.success else result.stderr
            if result.success:
                task_record.code_repo_url = self.code_executor.extract_repo_url(result.stdout)
            
            await self._trigger_event("on_task_executed", task_record, result)
            
            # Recording
            self.state = WorkflowState.RECORDING
            task_record.status = TaskStatus.COMPLETED if result.success else TaskStatus.FAILED
            task_record.completed_at = datetime.now(timezone.utc)
            
            if not self.dry_run:
                self.feishu_client.create_record(task_record)
                # Send notification card
                message = f"任务已{'成功完成' if result.success else '失败'}"
                self.feishu_bridge.send_notification_card(task_record, message)
            
            # Record task status
            if result.success:
                self.monitoring.record_task_completed()
            else:
                self.monitoring.record_task_failed()
            
            # Record task duration
            task_duration = time.time() - start_time
            self.monitoring.record_task_duration(task_duration)
            
            # Update queue size
            self.monitoring.record_queue_size(self.task_queue.size)
            
            await self._trigger_event("on_task_completed", task_record)
            
            self.state = WorkflowState.COMPLETED
            logger.info(f"Task completed: {task_id}, duration: {task_duration:.2f}s")
            
        except Exception as e:
            logger.error(f"Error processing task {task_id}: {e}")
            if self.current_task:
                self.current_task.status = TaskStatus.FAILED
                self.current_task.error_message = str(e)
            # Record task failure
            self.monitoring.record_task_failed()
            # Record task duration
            task_duration = time.time() - start_time
            self.monitoring.record_task_duration(task_duration)
            # Update queue size
            self.monitoring.record_queue_size(self.task_queue.size)
            await self._trigger_event("on_task_failed", self.current_task, e)
            raise
    
    async def process_raw_message(self, raw_message: Dict[str, Any], platform: str = "wework", listener_type: str = "unknown"):
        """Process a raw message through the workflow."""
        self.state = WorkflowState.CAPTURING
        logger.info(f"Processing raw message: {raw_message.get('msg_id', 'unknown')}")
        
        try:
            # Process through gateway
            self.state = WorkflowState.GATEWAY
            standard_message = self.message_gateway.process(
                raw_message, 
                platform=platform, 
                listener_type=listener_type
            )
            
            if standard_message:
                logger.info(f"Message processed through gateway: {standard_message.msg_id}")
                return standard_message
            else:
                logger.info("Message was filtered (duplicate or invalid)")
                return None
                
        except Exception as e:
            logger.error(f"Error processing raw message: {e}")
            await self._trigger_event("on_message_processing_failed", raw_message, e)
            raise
    
    async def run(self, task_message: TaskMessage) -> TaskRecord:
        """
        Execute the full workflow for a task message (backward compatibility).
        
        Args:
            task_message: The captured task message
            
        Returns:
            TaskRecord with final status
        """
        # Convert to raw message format
        raw_message = {
            "msg_id": task_message.original_message.msg_id,
            "content": task_message.original_message.content,
            "sender_id": task_message.original_message.sender_id,
            "sender_name": task_message.original_message.sender_name,
            "conversation_id": task_message.original_message.conversation_id,
            "conversation_type": task_message.original_message.conversation_type.value,
            "timestamp": task_message.original_message.timestamp,
            "msg_type": task_message.original_message.msg_type.value,
        }
        
        # Process through the new workflow
        await self.process_raw_message(raw_message)
        
        # For backward compatibility, create a task record
        task_id = self._generate_task_id(task_message.original_message.content)
        analysis = self.task_analyzer.analyze(task_message.raw_text)
        
        task_record = TaskRecord(
            task_id=task_id,
            raw_message=task_message.original_message.content,
            summary=analysis.get("summary", ""),
            tech_stack=analysis.get("tech_stack", []),
            core_features=analysis.get("core_features", []),
            status=TaskStatus.PENDING,
            user_id=task_message.original_message.sender_id,
            user_name=task_message.original_message.sender_name,
        )
        
        return task_record
    
    def get_state(self) -> WorkflowState:
        """Get current workflow state."""
        return self.state
    
    def get_current_task(self) -> Optional[TaskRecord]:
        """Get the current task being processed."""
        return self.current_task
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        return self.task_queue.stats
    
    def get_filter_stats(self) -> Dict[str, Any]:
        """Get filter statistics."""
        return self.task_filter.stats
    
    def get_gateway_stats(self) -> Dict[str, Any]:
        """Get gateway statistics."""
        return self.message_gateway.stats
