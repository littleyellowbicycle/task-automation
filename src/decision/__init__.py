"""Decision Manager module for user confirmation via Feishu cards."""

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import requests

from ..utils import get_logger
from ..exceptions import WeChatAutomationError

logger = get_logger("decision")


class DecisionError(WeChatAutomationError):
    """Base exception for decision errors."""
    pass


class ConfirmationTimeoutError(DecisionError):
    """Raised when confirmation times out."""
    pass


class FeishuAPIError(DecisionError):
    """Raised when Feishu API call fails."""
    pass


class Decision(str, Enum):
    """User decision on a task."""
    APPROVED = "approved"
    REJECTED = "rejected"
    LATER = "later"
    TIMEOUT = "timeout"


class TaskStatus(str, Enum):
    """Task status for display."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PendingConfirmation:
    """A pending confirmation request."""
    task_id: str
    task_data: Dict[str, Any]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    decision: Optional[Decision] = None
    message_id: Optional[str] = None
    card_message_id: Optional[str] = None
    reminder_sent: bool = False


@dataclass
class DecisionConfig:
    """Configuration for decision manager."""
    timeout: int = 10800  # 3 hours
    poll_interval: int = 5  # seconds
    reminder_interval: int = 1800  # 30 minutes
    max_reminders: int = 3
    feishu_webhook: str = ""
    feishu_app_id: str = ""
    feishu_app_secret: str = ""


class FeishuCardBuilder:
    """Builder for Feishu interactive cards."""
    
    @staticmethod
    def build_task_confirmation_card(
        task_id: str,
        summary: str,
        tech_stack: List[str],
        features: List[str],
        complexity: str,
        source: str,
        queue_status: str,
        timeout_minutes: int,
    ) -> Dict[str, Any]:
        """Build a task confirmation card."""
        
        tech_str = ", ".join(tech_stack) if tech_stack else "未识别"
        features_str = "\n".join([f"• {f}" for f in features]) if features else "• 基础功能"
        
        complexity_emoji = {
            "simple": "🟢",
            "medium": "🟡",
            "complex": "🔴",
        }.get(complexity, "⚪")
        
        card = {
            "config": {
                "wide_screen_mode": True,
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**📋 任务确认**"
                    }
                },
                {
                    "tag": "hr"
                },
                {
                    "tag": "div",
                    "fields": [
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**📝 摘要**\n{summary}"
                            }
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**📊 复杂度**\n{complexity_emoji} {complexity}"
                            }
                        }
                    ]
                },
                {
                    "tag": "div",
                    "fields": [
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**🛠️ 技术栈**\n{tech_str}"
                            }
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**👤 来源**\n{source}"
                            }
                        }
                    ]
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**⚡ 功能点**\n{features_str}"
                    }
                },
                {
                    "tag": "hr"
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"📌 {queue_status}\n⏱️ 请在 {timeout_minutes // 60} 小时内确认，超时将自动取消"
                    }
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "✅ 确认"
                            },
                            "type": "primary",
                            "value": {
                                "task_id": task_id,
                                "action": "approve"
                            }
                        },
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "❌ 取消"
                            },
                            "type": "danger",
                            "value": {
                                "task_id": task_id,
                                "action": "reject"
                            }
                        },
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "⏸️ 稍后"
                            },
                            "type": "default",
                            "value": {
                                "task_id": task_id,
                                "action": "later"
                            }
                        }
                    ]
                },
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": f"任务ID: {task_id}"
                        }
                    ]
                }
            ]
        }
        
        return card
    
    @staticmethod
    def build_execution_progress_card(
        task_id: str,
        summary: str,
        status: str,
        progress: int,
        steps: List[Dict[str, Any]],
        elapsed_seconds: int,
        repo_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build an execution progress card."""
        
        status_emoji = {
            "executing": "⚙️",
            "completed": "✅",
            "failed": "❌",
            "waiting_input": "❓",
        }.get(status, "⏳")
        
        progress_bar = "█" * (progress // 10) + "░" * (10 - progress // 10)
        
        steps_str = "\n".join([
            f"{'✅' if s.get('done') else '🔄' if s.get('current') else '⬜'} {i+1}. {s.get('name', '')}"
            for i, s in enumerate(steps)
        ]) if steps else ""
        
        elapsed_min = elapsed_seconds // 60
        elapsed_sec = elapsed_seconds % 60
        
        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**{status_emoji} 任务{status}**"
                }
            },
            {
                "tag": "hr"
            },
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**📋 任务**: {summary}"
                }
            },
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**📊 进度**: {progress_bar} {progress}%"
                }
            },
        ]
        
        if steps_str:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**执行步骤**:\n{steps_str}"
                }
            })
        
        elements.extend([
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"⏱️ 已用时: {elapsed_min}分{elapsed_sec}秒"
                }
            },
        ])
        
        if repo_url:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"💾 代码仓库: [查看]({repo_url})"
                }
            })
        
        if status == "waiting_input":
            elements.extend([
                {
                    "tag": "hr"
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": "**❓ 需要您的确认**\n检测到需要人工介入，请查看详情"
                    }
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "查看详情"
                            },
                            "type": "primary",
                            "value": {
                                "task_id": task_id,
                                "action": "view_detail"
                            }
                        }
                    ]
                },
            ])
        
        return {
            "config": {
                "wide_screen_mode": True,
            },
            "elements": elements,
        }


class DecisionManager:
    """
    Decision Manager for user confirmation.
    
    Features:
    - Send confirmation requests via Feishu cards
    - Receive user decisions via callbacks
    - Timeout handling
    - Reminder notifications
    """
    
    def __init__(self, config: Optional[DecisionConfig] = None):
        self.config = config or DecisionConfig()
        self._pending: Dict[str, PendingConfirmation] = {}
        self._card_builder = FeishuCardBuilder()
        self._on_decision: Optional[Callable[[str, Decision], None]] = None
        self._stats = {
            "total_requests": 0,
            "approved": 0,
            "rejected": 0,
            "timeout": 0,
            "later": 0,
        }
    
    def on_decision(self, callback: Callable[[str, Decision], None]) -> None:
        """Set callback for when a decision is made."""
        self._on_decision = callback
    
    def _send_feishu_message(self, content: Dict[str, Any]) -> Optional[str]:
        """Send a message via Feishu webhook."""
        if not self.config.feishu_webhook:
            logger.warning("Feishu webhook not configured")
            return None
        
        try:
            payload = {
                "msg_type": "interactive",
                "card": content,
            }
            
            response = requests.post(
                self.config.feishu_webhook,
                json=payload,
                timeout=10,
            )
            
            if response.status_code != 200:
                raise FeishuAPIError(f"Feishu API returned {response.status_code}")
            
            result = response.json()
            if result.get("code") != 0:
                raise FeishuAPIError(f"Feishu API error: {result.get('msg')}")
            
            return result.get("data", {}).get("message_id")
            
        except Exception as e:
            logger.error(f"Failed to send Feishu message: {e}")
            raise FeishuAPIError(f"Failed to send message: {e}")
    
    def request_confirmation(
        self,
        task_id: str,
        task_data: Dict[str, Any],
    ) -> bool:
        """
        Request user confirmation for a task.
        
        Args:
            task_id: Unique task identifier
            task_data: Task data including summary, tech_stack, etc.
            
        Returns:
            True if request sent successfully
        """
        self._stats["total_requests"] += 1
        
        card = self._card_builder.build_task_confirmation_card(
            task_id=task_id,
            summary=task_data.get("summary", "未知任务"),
            tech_stack=task_data.get("tech_stack", []),
            features=task_data.get("core_features", []),
            complexity=task_data.get("complexity", "medium"),
            source=task_data.get("source", "未知来源"),
            queue_status=task_data.get("queue_status", ""),
            timeout_minutes=self.config.timeout // 60,
        )
        
        message_id = self._send_feishu_message(card)
        
        pending = PendingConfirmation(
            task_id=task_id,
            task_data=task_data,
            message_id=message_id,
        )
        
        self._pending[task_id] = pending
        
        logger.info(f"Confirmation requested for task {task_id}")
        
        return True
    
    def receive_decision(
        self,
        task_id: str,
        action: str,
    ) -> bool:
        """
        Receive a user decision.
        
        Args:
            task_id: Task identifier
            action: Action taken (approve/reject/later)
            
        Returns:
            True if decision was processed
        """
        pending = self._pending.get(task_id)
        if not pending:
            logger.warning(f"No pending confirmation for task {task_id}")
            return False
        
        action_map = {
            "approve": Decision.APPROVED,
            "reject": Decision.REJECTED,
            "later": Decision.LATER,
        }
        
        decision = action_map.get(action)
        if not decision:
            logger.warning(f"Unknown action: {action}")
            return False
        
        pending.decision = decision
        
        self._stats[decision.value] += 1
        
        logger.info(f"Decision received for task {task_id}: {decision.value}")
        
        if self._on_decision:
            try:
                self._on_decision(task_id, decision)
            except Exception as e:
                logger.error(f"Decision callback failed: {e}")
        
        return True
    
    def get_decision(self, task_id: str) -> Optional[Decision]:
        """Get the decision for a task."""
        pending = self._pending.get(task_id)
        return pending.decision if pending else None
    
    async def wait_confirmation(
        self,
        task_id: str,
        task_data: Dict[str, Any],
        auto_confirm: bool = False,
    ) -> Decision:
        """
        Wait for user confirmation.
        
        Args:
            task_id: Task identifier
            task_data: Task data
            auto_confirm: Auto-approve without waiting
            
        Returns:
            The user's decision
        """
        if auto_confirm:
            self._stats["approved"] += 1
            return Decision.APPROVED
        
        self.request_confirmation(task_id, task_data)
        
        start_time = time.time()
        reminder_count = 0
        
        while True:
            elapsed = time.time() - start_time
            
            if elapsed >= self.config.timeout:
                self._stats["timeout"] += 1
                self._pending.pop(task_id, None)
                logger.warning(f"Task {task_id} confirmation timed out")
                return Decision.TIMEOUT
            
            pending = self._pending.get(task_id)
            if pending and pending.decision:
                decision = pending.decision
                self._pending.pop(task_id, None)
                return decision
            
            if (self.config.reminder_interval > 0 and
                reminder_count < self.config.max_reminders and
                elapsed > (reminder_count + 1) * self.config.reminder_interval and
                pending and not pending.reminder_sent):
                
                self._send_reminder(task_id, pending)
                pending.reminder_sent = True
                reminder_count += 1
            
            await asyncio.sleep(self.config.poll_interval)
    
    def _send_reminder(self, task_id: str, pending: PendingConfirmation) -> None:
        """Send a reminder for a pending confirmation."""
        elapsed = (datetime.now(timezone.utc) - pending.created_at).total_seconds()
        remaining = self.config.timeout - elapsed
        
        if remaining <= 0:
            return
        
        reminder_text = (
            f"⏰ 任务确认提醒\n"
            f"任务 {task_id} 等待确认中\n"
            f"剩余时间: {int(remaining // 60)} 分钟"
        )
        
        try:
            payload = {
                "msg_type": "text",
                "content": {
                    "text": reminder_text,
                },
            }
            
            requests.post(
                self.config.feishu_webhook,
                json=payload,
                timeout=10,
            )
            
            logger.info(f"Reminder sent for task {task_id}")
            
        except Exception as e:
            logger.error(f"Failed to send reminder: {e}")
    
    def cancel_pending(self, task_id: str) -> bool:
        """Cancel a pending confirmation."""
        if task_id in self._pending:
            del self._pending[task_id]
            logger.info(f"Pending confirmation cancelled for task {task_id}")
            return True
        return False
    
    def get_pending_count(self) -> int:
        """Get count of pending confirmations."""
        return len(self._pending)
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get decision manager statistics."""
        return {
            **self._stats,
            "pending_count": len(self._pending),
        }
    
    def update_card(
        self,
        task_id: str,
        status: str,
        progress: int = 0,
        steps: Optional[List[Dict[str, Any]]] = None,
        elapsed_seconds: int = 0,
        repo_url: Optional[str] = None,
    ) -> bool:
        """
        Update the progress card for a task.
        
        Args:
            task_id: Task identifier
            status: Current status
            progress: Progress percentage (0-100)
            steps: List of execution steps
            elapsed_seconds: Elapsed time in seconds
            repo_url: Repository URL
            
        Returns:
            True if updated successfully
        """
        pending = self._pending.get(task_id)
        if not pending:
            return False
        
        card = self._card_builder.build_execution_progress_card(
            task_id=task_id,
            summary=pending.task_data.get("summary", "未知任务"),
            status=status,
            progress=progress,
            steps=steps or [],
            elapsed_seconds=elapsed_seconds,
            repo_url=repo_url,
        )
        
        self._send_feishu_message(card)
        
        return True
