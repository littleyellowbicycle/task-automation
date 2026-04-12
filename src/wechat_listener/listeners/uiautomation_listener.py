"""WeChat listener using UIAutomation (Windows UI automation implementation)."""

import asyncio
import threading
import time
import re
from queue import Queue, Empty
from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass, field

from ..base import BaseListener, ListenerType, Platform
from ..models import WeChatMessage, TaskMessage, MessageType, ConversationType
from ..parser import MessageParser
from ...utils import get_logger
from ...exceptions import WeChatConnectionError

logger = get_logger("wechat_listener.uiautomation")

UIAUTOMATION_AVAILABLE = False
try:
    import uiautomation as auto
    UIAUTOMATION_AVAILABLE = True
except ImportError:
    auto = None


@dataclass
class MessageCache:
    """Cache for processed messages to avoid duplicates."""
    max_size: int = 100
    _cache: Dict[str, float] = field(default_factory=dict)
    
    def add(self, msg_id: str) -> bool:
        if msg_id in self._cache:
            return False
        self._cache[msg_id] = time.time()
        self._cleanup()
        return True
    
    def _cleanup(self) -> None:
        if len(self._cache) > self.max_size:
            sorted_items = sorted(self._cache.items(), key=lambda x: x[1])
            for key, _ in sorted_items[:len(self._cache) - self.max_size]:
                del self._cache[key]


@dataclass
class ConversationInfo:
    """Information about a conversation window."""
    name: str
    conversation_id: str
    window: Any
    is_group: bool = False


class UIAutomationListener(BaseListener):
    """
    WeChat message listener using Windows UI Automation.
    
    This implementation uses the uiautomation library to monitor the WeChat
    window for new messages by periodically checking the message list control.
    
    This method is safer than network hooks as it doesn't modify the WeChat
    client, but it requires the WeChat window to be visible and active.
    """
    
    WINDOW_TITLES = {
        Platform.WEWORK: ["企业微信", "WeCom"],
        Platform.WECHAT: ["微信", "WeChat"],
    }
    
    MESSAGE_POLL_INTERVAL = 0.5
    MAX_RETRIES = 3
    RETRY_DELAY = 2.0
    
    def __init__(
        self,
        platform: Platform = Platform.WEWORK,
        poll_interval: float = 0.5,
        max_history: int = 100,
        keywords: Optional[List[str]] = None,
        regex_patterns: Optional[List[str]] = None,
    ):
        """
        Initialize the UIAutomation listener.
        
        Args:
            platform: The chat platform (WEWORK or WECHAT)
            poll_interval: Interval in seconds to poll for new messages
            max_history: Maximum number of messages to keep in history
            keywords: Keywords to filter for project tasks
            regex_patterns: Regex patterns to match task messages
        """
        super().__init__(platform=platform, keywords=keywords, regex_patterns=regex_patterns)
        self.poll_interval = poll_interval
        self.max_history = max_history
        self.parser = MessageParser(keywords=keywords, regex_patterns=regex_patterns)
        self._message_queue: Queue = Queue()
        self._cache = MessageCache(max_size=max_history)
        self._wechat_window: Optional[Any] = None
        self._message_list: Optional[Any] = None
        self._current_conversation: Optional[ConversationInfo] = None
        self._last_message_time: float = 0
        self._listener_thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
    
    @property
    def listener_type(self) -> ListenerType:
        return ListenerType.UIAUTOMATION
    
    async def connect(self) -> bool:
        if not UIAUTOMATION_AVAILABLE:
            raise WeChatConnectionError(
                "uiautomation is not installed. Install with: pip install uiautomation"
            )
        
        for attempt in range(self.MAX_RETRIES):
            try:
                logger.info(f"Attempting to connect to {self.platform.value} window (attempt {attempt + 1})")
                
                self._wechat_window = self._find_wechat_window()
                if not self._wechat_window:
                    raise WeChatConnectionError(
                        f"Could not find {self.platform.value} window. "
                        f"Please ensure {self.platform.value} is running and visible."
                    )
                
                self._message_list = self._find_message_list()
                if not self._message_list:
                    raise WeChatConnectionError(
                        f"Could not find message list in {self.platform.value} window. "
                        "Please open a conversation."
                    )
                
                self._running = True
                logger.info(f"UIAutomation listener connected to {self.platform.value}")
                return True
                
            except WeChatConnectionError:
                if attempt < self.MAX_RETRIES - 1:
                    logger.info(f"Retrying in {self.RETRY_DELAY} seconds...")
                    await asyncio.sleep(self.RETRY_DELAY)
                else:
                    raise
    
    def _find_wechat_window(self) -> Optional[Any]:
        titles = self.WINDOW_TITLES.get(self.platform, [])
        
        for title in titles:
            window = auto.WindowControl(Name=title, searchDepth=1)
            if window.Exists(0, 0):
                logger.info(f"Found {self.platform.value} window: {title}")
                return window
        
        all_windows = auto.GetRootControl().GetChildren()
        for window in all_windows:
            name = window.Name
            for title in titles:
                if title in name:
                    logger.info(f"Found {self.platform.value} window by partial match: {name}")
                    return window
        
        return None
    
    def _find_message_list(self) -> Optional[Any]:
        if not self._wechat_window:
            return None

        list_control = self._wechat_window.ListControl(Name="消息")
        if list_control.Exists(0, 0):
            logger.debug("Found message list by Name='消息'")
            return list_control

        for lc in self._wechat_window.GetChildren():
            if lc.ControlTypeName == "ListControl":
                children = lc.GetChildren()
                if len(children) > 0:
                    logger.debug(f"Found message list by type scan ({len(children)} items)")
                    return lc

        logger.warning("Could not find message list control")
        return None
    
    def _get_current_conversation(self) -> Optional[ConversationInfo]:
        if not self._wechat_window:
            return None
        
        try:
            name_control = self._wechat_window.TextControl(Name="聊天信息")
            if name_control.Exists(0, 0):
                name = name_control.Name
                is_group = "群" in name or "(" in name or "（" in name
                return ConversationInfo(
                    name=name,
                    conversation_id=name,
                    window=self._wechat_window,
                    is_group=is_group,
                )
        except Exception:
            pass
        
        return None
    
    def _parse_message_item(self, item: Any) -> Optional[WeChatMessage]:
        try:
            text_controls = item.GetTextControl()
            if not text_controls:
                return None
            
            texts = []
            for ctrl in text_controls:
                text = ctrl.Name.strip()
                if text:
                    texts.append(text)
            
            if not texts:
                return None
            
            content = "\n".join(texts)
            
            sender_name = ""
            message_content = content
            
            time_pattern = r'\d{1,2}:\d{2}'
            time_match = re.search(time_pattern, content)
            timestamp = datetime.now()
            
            if time_match:
                time_str = time_match.group()
                hour, minute = map(int, time_str.split(':'))
                timestamp = timestamp.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            if ":" in content or "：" in content:
                parts = re.split(r'[:：]', content, 1)
                if len(parts) >= 2:
                    sender_name = parts[0].strip()
                    message_content = parts[1].strip()
            
            msg_id = f"{sender_name}_{hash(content)}_{timestamp.timestamp()}"
            
            if not self._cache.add(msg_id):
                return None
            
            conversation = self._get_current_conversation()
            if not conversation:
                conversation = ConversationInfo(
                    name="unknown",
                    conversation_id="unknown",
                    window=self._wechat_window,
                    is_group=False,
                )
              
            return WeChatMessage(
                msg_id=msg_id,
                msg_type=MessageType.TEXT,
                content=message_content,
                conversation_id=conversation.conversation_id,
                conversation_type=ConversationType.GROUP if conversation.is_group else ConversationType.PRIVATE,
                sender_id=sender_name,
                sender_name=sender_name,
                timestamp=timestamp,
                raw_data={"raw_content": content, "texts": texts},
            )
            
        except Exception as e:
            logger.debug(f"Error parsing message item: {e}")
            return None
    
    def _poll_messages(self) -> None:
        if not self._message_list:
            self._message_list = self._find_message_list()
            if not self._message_list:
                return
        
        try:
            items = self._message_list.GetChildren()
            
            for item in reversed(items[-20:]):
                message = self._parse_message_item(item)
                if message:
                    task_message = self.parser.parse_task_message(message)
                    self._message_queue.put(task_message)
                    
                    self._on_message(message)
                    if task_message.is_project_task:
                        self._on_task_message(task_message)
                        logger.info(f"Detected task message from {message.sender_name}")
                        
        except Exception as e:
            logger.error(f"Error polling messages: {e}")
            self._on_error(e)
    
    def _run_polling_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        while self._running:
            try:
                self._poll_messages()
            except Exception as e:  
                logger.error(f"Error in polling loop: {e}")
                self._on_error(e)
            
            time.sleep(self.poll_interval)
    
    def disconnect(self) -> None:
        self._running = False
        logger.info("UIAutomation listener disconnected")
    
    async def get_next_message(self, timeout: float = 1.0) -> Optional[TaskMessage]:
        try:
            return self._message_queue.get(timeout=timeout)
        except Empty:
            return None
    
    async def start_listening(self) -> None:
        while self._running:
            try:
                task_message = await self.get_next_message(timeout=1.0)
                
                if task_message:
                    if self._callback and self._callback.on_message:
                        self._callback.on_message(task_message.original_message)
                    
                    if task_message.is_project_task and self._callback and self._callback.on_task_message:
                        self._callback.on_task_message(task_message)
                
            except Exception as e:
                logger.error(f"Error in listening loop: {e}")
                self._on_error(e)
                await asyncio.sleep(1)
    
    def start_background(self) -> None:
        if self._listener_thread and self._listener_thread.is_alive():
            logger.warning("UIAutomation listener already running")
            return
        
        self._listener_thread = threading.Thread(target=self._run_polling_loop, daemon=True)
        self._listener_thread.start()
        
        super().start_background()
        logger.info("UIAutomation listener started in background")
    
    def get_contacts(self) -> List[dict]:
        if not self._wechat_window:
            return []

        contacts = []
        try:
            contact_list = self._wechat_window.ListControl(Name="联系人")
            if contact_list and contact_list.Exists(0, 0):
                items = contact_list.GetChildren()
                for item in items:
                    name = item.Name
                    if name:
                        contacts.append({"name": name, "id": name})
        except Exception as e:
            logger.error(f"Error getting contacts: {e}")

        return contacts
    
    def get_rooms(self) -> List[dict]:
        if not self._wechat_window:
            return []

        rooms = []
        try:
            chat_list = self._wechat_window.ListControl(Name="聊天列表")
            if chat_list and chat_list.Exists(0, 0):
                items = chat_list.GetChildren()
                for item in items:
                    name = item.Name
                    if name and ("群" in name or "(" in name or "（" in name):
                        rooms.append({"name": name, "id": name})
            else:
                for child in self._wechat_window.GetChildren():
                    if child.ControlTypeName == "ListControl":
                        items = child.GetChildren()
                        for item in items:
                            name = item.Name
                            if name and ("群" in name or "(" in name or "（" in name):
                                rooms.append({"name": name, "id": name})
                        if rooms:
                            break
        except Exception as e:
            logger.error(f"Error getting rooms: {e}")

        return rooms
    
    def send_text(self, conversation_id: str, content: str) -> bool:
        if not self._wechat_window:
            return False
        
        try:
            edit_control = self._wechat_window.EditControl()
            if not edit_control.Exists(0, 0):
                logger.error("Could not find message input control")
                return False
            
            edit_control.SendKeys(content, waitTime=0.1)
            
            send_button = self._wechat_window.ButtonControl(Name="发送")
            if send_button.Exists(0, 0):
                send_button.Click()
            else:
                edit_control.SendKeys("{Enter}")
            
            logger.info(f"Sent message to {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False
    
    def switch_conversation(self, conversation_name: str) -> bool:
        if not self._wechat_window:
            return False
        
        try:
            search_box = self._wechat_window.EditControl(Name="搜索")
            if not search_box.Exists(0, 0):
                search_box = self._wechat_window.EditControl(SubName="搜索")
            
            if search_box.Exists(0, 0):
                search_box.Click()
                search_box.SendKeys("{Ctrl+A}")
                search_box.SendKeys(conversation_name)
                time.sleep(0.5)
                search_box.SendKeys("{Enter}")
                time.sleep(0.3)
                
                self._message_list = self._find_message_list()
                logger.info(f"Switched to conversation: {conversation_name}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to switch conversation: {e}")
            return False
