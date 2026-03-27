"""Workflow orchestrator for the WeChat task automation system."""

from enum import Enum
from typing import Optional, Callable, Dict
from datetime import datetime

from ..wechat_listener.models import TaskMessage
from ..feishu_recorder.models import TaskRecord, TaskStatus
from ..llm_router.router import LLMRouter
from ..task_analyzer import TaskAnalyzer
from ..code_executor import CodeExecutor
from ..feishu_recorder.client import FeishuClient
from ..decision_manager import DecisionManager, ConfirmationResult
from ..utils import get_logger
from ..exceptions import WorkflowError

logger = get_logger("workflow_orchestrator")


class WorkflowState(str, Enum):
    IDLE = "idle"
    CAPTURING = "capturing"
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
    
    Coordinates the flow: Message Capture → LLM Analysis → User Confirmation → Execution → Recording
    """
    
    def __init__(
        self,
        llm_router: Optional[LLMRouter] = None,
        code_executor: Optional[CodeExecutor] = None,
        feishu_client: Optional[FeishuClient] = None,
        decision_manager: Optional[DecisionManager] = None,
        dry_run: bool = False,
    ):
        """
        Initialize the workflow orchestrator.
        
        Args:
            llm_router: LLM router instance
            code_executor: Code executor instance
            feishu_client: Feishu client instance
            decision_manager: Decision manager instance
            dry_run: If True, don't actually execute code
        """
        self.dry_run = dry_run
        
        # Initialize components
        self.llm_router = llm_router or LLMRouter()
        self.task_analyzer = TaskAnalyzer(self.llm_router)
        self.code_executor = code_executor or CodeExecutor()
        self.feishu_client = feishu_client or FeishuClient()
        self.decision_manager = decision_manager or DecisionManager()
        
        # State
        self.state = WorkflowState.IDLE
        self.current_task: Optional[TaskRecord] = None
        self._event_hooks: Dict[str, Callable] = {}
        
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
    
    async def run(self, task_message: TaskMessage) -> TaskRecord:
        """
        Execute the full workflow for a task message.
        
        Args:
            task_message: The captured task message
            
        Returns:
            TaskRecord with final status
        """
        logger.info(f"Starting workflow for task message: {task_message.original_message.msg_id}")
        
        try:
            # Step 1: Create initial task record
            self.state = WorkflowState.CAPTURING
            task_record = TaskRecord(
                task_id=f"task_{hash(task_message.original_message.content) % 1000000}",
                raw_message=task_message.original_message.content,
                user_id=task_message.original_message.sender_id,
                user_name=task_message.original_message.sender_name,
            )
            self.current_task = task_record
            await self._trigger_event("on_task_captured", task_record)
            
            # Step 2: Analyze with LLM
            self.state = WorkflowState.ANALYZING
            logger.info("Analyzing task with LLM...")
            task_record = await self.task_analyzer.analyze(task_message.raw_text)
            task_record.task_id = self.current_task.task_id
            task_record.user_id = self.current_task.user_id
            task_record.user_name = self.current_task.user_name
            await self._trigger_event("on_task_analyzed", task_record)
            
            # Step 3: Request user confirmation
            self.state = WorkflowState.AWAITING_CONFIRMATION
            confirmation = await self.decision_manager.request_confirmation(task_record)
            
            if confirmation == ConfirmationResult.CANCELLED:
                task_record.status = TaskStatus.CANCELLED
                await self._trigger_event("on_task_cancelled", task_record)
                self.state = WorkflowState.CANCELLED
                return task_record
            
            if confirmation == ConfirmationResult.TIMEOUT:
                task_record.status = TaskStatus.TIMEOUT
                await self._trigger_event("on_task_timeout", task_record)
                self.state = WorkflowState.FAILED
                return task_record
            
            task_record.status = TaskStatus.APPROVED
            await self._trigger_event("on_task_confirmed", task_record)
            
            # Step 4: Execute code generation
            self.state = WorkflowState.EXECUTING
            task_record.status = TaskStatus.EXECUTING
            logger.info("Executing code generation...")
            
            instruction = await self.task_analyzer.generate_instruction(task_record)
            result = await self.code_executor.execute(instruction, dry_run=self.dry_run)
            
            task_record.executor_result = result.stdout if result.success else result.stderr
            if result.success:
                task_record.code_repo_url = self.code_executor.extract_repo_url(result.stdout)
            
            await self._trigger_event("on_task_executed", task_record, result)
            
            # Step 5: Record to Feishu
            self.state = WorkflowState.RECORDING
            task_record.status = TaskStatus.COMPLETED if result.success else TaskStatus.FAILED
            task_record.completed_at = datetime.now()
            
            if not self.dry_run:
                await self.feishu_client.create_record(task_record)
            
            await self._trigger_event("on_task_completed", task_record)
            
            self.state = WorkflowState.COMPLETED
            logger.info(f"Workflow completed: {task_record.task_id}")
            
            return task_record
            
        except Exception as e:
            logger.error(f"Workflow error: {e}")
            self.state = WorkflowState.FAILED
            if self.current_task:
                self.current_task.status = TaskStatus.FAILED
                self.current_task.error_message = str(e)
            await self._trigger_event("on_task_failed", self.current_task, e)
            raise WorkflowError(f"Workflow failed: {e}")
    
    def get_state(self) -> WorkflowState:
        """Get current workflow state."""
        return self.state
    
    def get_current_task(self) -> Optional[TaskRecord]:
        """Get the current task being processed."""
        return self.current_task
