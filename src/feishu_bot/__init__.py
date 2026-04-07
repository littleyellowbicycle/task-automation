"""Feishu Bot module for user interaction via private messages."""

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import requests

from ..utils import get_logger
from ..exceptions import WeChatAutomationError

logger = get_logger("feishu_bot")


class FeishuBotError(WeChatAutomationError):
    """Base exception for Feishu bot errors."""
    pass


@dataclass
class BotConfig:
    """Configuration for Feishu bot."""
    app_id: str = ""
    app_secret: str = ""
    base_url: str = "https://open.feishu.cn/open-apis"
    bind_file: str = ""  # 用户绑定信息存储文件
    
    def __post_init__(self):
        if not self.app_id:
            self.app_id = os.getenv("FEISHU_APP_ID", "")
        if not self.app_secret:
            self.app_secret = os.getenv("FEISHU_APP_SECRET", "")
        if not self.bind_file:
            self.bind_file = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "data", "feishu_bind.json"
            )


@dataclass
class BoundUser:
    """A bound user."""
    open_id: str
    user_id: Optional[str] = None
    name: Optional[str] = None
    bound_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class FeishuBot:
    """
    Feishu Bot for user interaction.
    
    Features:
    - Auto-bind user on first interaction
    - Send interactive cards
    - Handle user responses
    - Progress updates
    """
    
    def __init__(self, config: Optional[BotConfig] = None):
        self.config = config or BotConfig()
        self._tenant_access_token: Optional[str] = None
        self._token_expires_at: float = 0
        self._bound_users: Dict[str, BoundUser] = {}
        self._on_message: Optional[Callable[[Dict[str, Any]], None]] = None
        self._load_bound_users()
    
    def _load_bound_users(self) -> None:
        """Load bound users from file."""
        bind_file = Path(self.config.bind_file)
        if bind_file.exists():
            try:
                with open(bind_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for open_id, user_data in data.items():
                        self._bound_users[open_id] = BoundUser(
                            open_id=open_id,
                            user_id=user_data.get("user_id"),
                            name=user_data.get("name"),
                            bound_at=user_data.get("bound_at", datetime.now(timezone.utc).isoformat()),
                        )
                logger.info(f"Loaded {len(self._bound_users)} bound users")
            except Exception as e:
                logger.error(f"Failed to load bound users: {e}")
    
    def _save_bound_users(self) -> None:
        """Save bound users to file."""
        bind_file = Path(self.config.bind_file)
        bind_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            data = {
                open_id: {
                    "user_id": user.user_id,
                    "name": user.name,
                    "bound_at": user.bound_at,
                }
                for open_id, user in self._bound_users.items()
            }
            with open(bind_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(self._bound_users)} bound users")
        except Exception as e:
            logger.error(f"Failed to save bound users: {e}")
    
    def _get_tenant_access_token(self) -> Optional[str]:
        """Get tenant access token."""
        if self._tenant_access_token and time.time() < self._token_expires_at - 60:
            return self._tenant_access_token
        
        url = f"{self.config.base_url}/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json"}
        payload = {
            "app_id": self.config.app_id,
            "app_secret": self.config.app_secret,
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            data = response.json()
            
            if data.get("code") == 0:
                self._tenant_access_token = data.get("tenant_access_token")
                self._token_expires_at = time.time() + data.get("expire", 7200)
                logger.info("Feishu tenant access token obtained")
                return self._tenant_access_token
            else:
                logger.error(f"Failed to get token: {data}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting token: {e}")
            return None
    
    def bind_user(self, open_id: str, user_id: Optional[str] = None, name: Optional[str] = None) -> bool:
        """
        Bind a user.
        
        Args:
            open_id: User's open_id
            user_id: User's user_id (optional)
            name: User's name (optional)
            
        Returns:
            True if bound successfully
        """
        self._bound_users[open_id] = BoundUser(
            open_id=open_id,
            user_id=user_id,
            name=name,
        )
        self._save_bound_users()
        logger.info(f"User bound: {open_id}")
        return True
    
    def unbind_user(self, open_id: str) -> bool:
        """Unbind a user."""
        if open_id in self._bound_users:
            del self._bound_users[open_id]
            self._save_bound_users()
            logger.info(f"User unbound: {open_id}")
            return True
        return False
    
    def get_bound_users(self) -> List[BoundUser]:
        """Get all bound users."""
        return list(self._bound_users.values())
    
    def is_user_bound(self, open_id: str) -> bool:
        """Check if a user is bound."""
        return open_id in self._bound_users
    
    def _send_message(
        self,
        receive_id: str,
        content: Dict[str, Any],
        receive_id_type: str = "open_id",
        msg_type: str = "interactive",
    ) -> Optional[str]:
        """
        Send a message.
        
        Args:
            receive_id: The receiver's ID
            content: Message content
            receive_id_type: Type of receive_id (open_id, user_id, chat_id)
            msg_type: Message type (text, interactive, etc.)
            
        Returns:
            Message ID if successful
        """
        token = self._get_tenant_access_token()
        if not token:
            logger.error("No tenant access token available")
            return None
        
        url = f"{self.config.base_url}/im/v1/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        params = {"receive_id_type": receive_id_type}
        payload = {
            "receive_id": receive_id,
            "msg_type": msg_type,
            "content": json.dumps(content, ensure_ascii=False),
        }
        
        try:
            response = requests.post(
                url,
                params=params,
                json=payload,
                headers=headers,
                timeout=10,
            )
            
            data = response.json()
            
            if data.get("code") == 0:
                message_id = data.get("data", {}).get("message_id")
                logger.info(f"Message sent to {receive_id}: {message_id}")
                return message_id
            else:
                logger.error(f"Failed to send message: {data}")
                return None
                
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return None
    
    def send_to_bound_users(
        self,
        content: Dict[str, Any],
        msg_type: str = "interactive",
    ) -> Dict[str, Optional[str]]:
        """
        Send a message to all bound users.
        
        Args:
            content: Message content
            msg_type: Message type
            
        Returns:
            Dict mapping open_id to message_id
        """
        results = {}
        for open_id in self._bound_users:
            results[open_id] = self._send_message(
                receive_id=open_id,
                content=content,
                receive_id_type="open_id",
                msg_type=msg_type,
            )
        return results
    
    def send_text(self, text: str, open_id: Optional[str] = None) -> Optional[str]:
        """
        Send a text message.
        
        Args:
            text: Text content
            open_id: Specific user's open_id, or None to send to all bound users
            
        Returns:
            Message ID if sending to one user
        """
        content = {"text": text}
        
        if open_id:
            return self._send_message(open_id, content, msg_type="text")
        else:
            results = self.send_to_bound_users(content, msg_type="text")
            return list(results.values())[0] if results else None
    
    def send_card(
        self,
        card: Dict[str, Any],
        open_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Send an interactive card.
        
        Args:
            card: Card content
            open_id: Specific user's open_id, or None to send to all bound users
            
        Returns:
            Message ID if sending to one user
        """
        if open_id:
            return self._send_message(open_id, card, msg_type="interactive")
        else:
            results = self.send_to_bound_users(card, msg_type="interactive")
            return list(results.values())[0] if results else None
    
    def build_confirmation_card(
        self,
        task_id: str,
        summary: str,
        tech_stack: List[str],
        features: List[str],
        complexity: str = "medium",
        source: str = "系统",
    ) -> Dict[str, Any]:
        """Build a task confirmation card."""
        
        tech_str = ", ".join(tech_stack) if tech_stack else "未识别"
        features_str = "\n".join([f"• {f}" for f in features]) if features else "• 基础功能"
        
        complexity_emoji = {
            "simple": "🟢",
            "medium": "🟡",
            "complex": "🔴",
        }.get(complexity, "⚪")
        
        return {
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
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "✅ 确认执行"
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
    
    def build_progress_card(
        self,
        task_id: str,
        summary: str,
        status: str,
        progress: int = 0,
        steps: Optional[List[Dict[str, Any]]] = None,
        elapsed_seconds: int = 0,
        repo_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build a progress update card."""
        
        status_config = {
            "executing": ("⚙️ 执行中", "blue"),
            "completed": ("✅ 已完成", "green"),
            "failed": ("❌ 失败", "red"),
            "waiting_input": ("❓ 等待输入", "orange"),
        }
        status_text, status_color = status_config.get(status, ("⏳ 未知", "grey"))
        
        progress_bar = "█" * (progress // 10) + "░" * (10 - progress // 10)
        
        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**{status_text}**"
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
        
        if steps:
            steps_str = "\n".join([
                f"{'✅' if s.get('done') else '🔄' if s.get('current') else '⬜'} {s.get('name', '')}"
                for s in steps
            ])
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**执行步骤**:\n{steps_str}"
                }
            })
        
        elapsed_min = elapsed_seconds // 60
        elapsed_sec = elapsed_seconds % 60
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"⏱️ 已用时: {elapsed_min}分{elapsed_sec}秒"
            }
        })
        
        if repo_url:
            elements.append({
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "查看代码仓库"
                        },
                        "type": "default",
                        "url": repo_url
                    }
                ]
            })
        
        return {
            "config": {
                "wide_screen_mode": True,
            },
            "elements": elements,
        }
    
    def handle_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a Feishu event.
        
        Args:
            event: The event data from Feishu
            
        Returns:
            Response data
        """
        event_type = event.get("header", {}).get("event_type", "")
        event_data = event.get("event", {})
        
        if event_type == "im.message.receive_v1":
            return self._handle_message_event(event_data)
        else:
            logger.debug(f"Unhandled event type: {event_type}")
            return {"code": 0, "message": "Event ignored"}
    
    def _handle_message_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a message receive event."""
        message = event_data.get("message", {})
        sender = event_data.get("sender", {})
        
        open_id = sender.get("sender_id", {}).get("open_id", "")
        message_type = message.get("message_type", "")
        content = message.get("content", "")
        
        if message_type == "text":
            try:
                text_content = json.loads(content).get("text", "")
            except json.JSONDecodeError:
                text_content = content
            
            logger.info(f"Received message from {open_id}: {text_content}")
            
            if text_content.strip().lower() in ["/bind", "绑定"]:
                self.bind_user(open_id)
                self.send_text("✅ 绑定成功！您将收到任务通知。", open_id)
                return {"code": 0, "message": "User bound"}
            
            elif text_content.strip().lower() in ["/unbind", "解绑"]:
                self.unbind_user(open_id)
                self.send_text("✅ 已解绑。您将不再收到任务通知。", open_id)
                return {"code": 0, "message": "User unbound"}
            
            elif text_content.strip().lower() in ["/status", "状态"]:
                bound_count = len(self._bound_users)
                self.send_text(f"📊 当前绑定用户数: {bound_count}", open_id)
                return {"code": 0, "message": "Status sent"}
            
            elif text_content.strip().lower() in ["/help", "帮助"]:
                help_text = (
                    "🤖 机器人命令:\n"
                    "/bind - 绑定账号，接收任务通知\n"
                    "/unbind - 解绑账号\n"
                    "/status - 查看状态\n"
                    "/help - 显示帮助"
                )
                self.send_text(help_text, open_id)
                return {"code": 0, "message": "Help sent"}
            
            if self._on_message:
                self._on_message({
                    "open_id": open_id,
                    "content": text_content,
                    "message": message,
                    "sender": sender,
                })
        
        return {"code": 0, "message": "Message processed"}
    
    def on_message(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Set callback for received messages."""
        self._on_message = callback
    
    def reply_to_message(
        self,
        message_id: str,
        content: Dict[str, Any],
        msg_type: str = "text",
    ) -> Optional[str]:
        """
        Reply to a message.
        
        Args:
            message_id: The message ID to reply to
            content: Reply content
            msg_type: Message type
            
        Returns:
            Reply message ID
        """
        token = self._get_tenant_access_token()
        if not token:
            return None
        
        url = f"{self.config.base_url}/im/v1/messages/{message_id}/reply"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload = {
            "msg_type": msg_type,
            "content": json.dumps(content, ensure_ascii=False),
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            data = response.json()
            
            if data.get("code") == 0:
                return data.get("data", {}).get("message_id")
            else:
                logger.error(f"Failed to reply: {data}")
                return None
                
        except Exception as e:
            logger.error(f"Error replying: {e}")
            return None
