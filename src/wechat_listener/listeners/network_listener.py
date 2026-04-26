"""WeChat listener using NtWork SDK (Network-based implementation)."""

import asyncio
import threading
from queue import Queue, Empty
from typing import Optional, List

from ..base import BaseListener, ListenerType, Platform
from ..models import WeChatMessage, TaskMessage, MessageType, ConversationType
from ..parser import MessageParser
from ...utils import get_logger
from ...exceptions import WeChatConnectionError

logger = get_logger("wechat_listener.ntwork")

NTWORK_AVAILABLE = False
try:
    import ntwork
    NTWORK_AVAILABLE = True
except ImportError:
    ntwork = None


class NtWorkListener(BaseListener):
    """
    WeChat message listener using NtWork SDK.
    
    This implementation uses the NtWork library to directly connect to
    the WeChat/WeCom client and listen for messages via network hooks.
    
    Note: This method may risk account bans. Use with caution.
    """
    
    def __init__(
        self,
        platform: Platform = Platform.WEWORK,
        device_id: str = "",
        ip: str = "127.0.0.1",
        port: int = 5037,
        smart_mode: bool = True,
        keywords: Optional[List[str]] = None,
        regex_patterns: Optional[List[str]] = None,
    ):
        """
        Initialize the NtWork listener.
        
        Args:
            platform: The chat platform (WEWORK or WECHAT)
            device_id: WeChat device ID
            ip: ADB server IP
            port: ADB server port
            smart_mode: Use smart mode for connection
            keywords: Keywords to filter for project tasks
            regex_patterns: Regex patterns to match task messages
        """
        super().__init__(platform=platform, keywords=keywords, regex_patterns=regex_patterns)
        self.device_id = device_id
        self.ip = ip
        self.port = port
        self.smart_mode = smart_mode
        self.parser = MessageParser(keywords=keywords, regex_patterns=regex_patterns)
        self._message_queue: Queue = Queue()
        self._listener_thread: Optional[threading.Thread] = None
        self._ntwork: Optional[object] = None
    
    @property
    def listener_type(self) -> ListenerType:
        return ListenerType.NTWORK
    
    async def connect(self) -> bool:
        if not NTWORK_AVAILABLE:
            raise WeChatConnectionError(
                "ntwork is not installed. Install with: pip install ntwork "
                "(requires Python 3.10 and WeCom 4.0.8.6027)"
            )
        
        try:
            logger.info(f"Connecting to {self.platform.value} via NtWork at {self.ip}:{self.port}")
            
            if self.platform == Platform.WEWORK:
                self._ntwork = ntwork.WeWork()
            else:
                self._ntwork = ntwork.WeChat()
            
            self._ntwork.open(smart=self.smart_mode)
            self._ntwork.wait_login()

            login_info = self._ntwork.get_login_info()
            logger.info(f"Logged in as: {login_info}")

            self._ntwork.msg_register(ntwork.MT_RECV_TEXT_MSG, self._handle_ntwork_message)
            
            self._running = True
            logger.info(f"NtWork listener connected for {self.platform.value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect via NtWork: {e}")
            raise WeChatConnectionError(f"NtWork connection failed: {e}")
    
    def disconnect(self) -> None:
        self._running = False
        if self._ntwork:
            try:
                ntwork.exit_()
            except Exception:
                pass
        logger.info("NtWork listener disconnected")
    
    def _handle_ntwork_message(self, wework_instance, message: dict) -> None:
        try:
            msg_type = message.get("type", 0)
            if msg_type != ntwork.MT_RECV_TEXT_MSG:
                return
            
            data = message.get("data", {})
            sender = data.get("sender", "")
            content = data.get("content", "")
            conversation_id = data.get("conversation_id", "")
            
            if not content:
                return
            
            is_group = conversation_id.startswith("R:")
            msg_type_enum = MessageType.TEXT
            
            wechat_message = WeChatMessage(
                msg_id=data.get("msgid", str(hash(content))),
                msg_type=msg_type_enum,
                content=content,
                conversation_id=conversation_id,
                conversation_type=ConversationType.GROUP if is_group else ConversationType.PRIVATE,
                sender_id=sender,
                sender_name=sender,
                raw_data=message,
            )
            
            task_message = self.parser.parse_task_message(wechat_message)
            self._message_queue.put(task_message)
            
            self._on_message(wechat_message)
            if task_message.is_project_task:
                self._on_task_message(task_message)
            
            logger.debug(f"Message received: {wechat_message.msg_id} from {sender}")
            
        except Exception as e:
            logger.error(f"Error handling NtWork message: {e}")
            self._on_error(e)
    
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
                logger.error(f"Error in NtWork listening loop: {e}")
                self._on_error(e)
                await asyncio.sleep(1)
    
    def get_contacts(self) -> List[dict]:
        if not self._ntwork:
            return []
        if self.platform == Platform.WEWORK:
            return self._ntwork.get_inner_contacts()
        return self._ntwork.get_contacts()
    
    def get_external_contacts(self) -> List[dict]:
        if not self._ntwork:
            return []
        if self.platform == Platform.WEWORK:
            return self._ntwork.get_external_contacts()
        return []
    
    def get_rooms(self) -> List[dict]:
        if not self._ntwork:
            return []
        return self._ntwork.get_rooms()
    
    def send_text(self, conversation_id: str, content: str) -> bool:
        if not self._ntwork:
            return False
        try:
            self._ntwork.send_text(conversation_id=conversation_id, content=content)
            return True
        except Exception as e:
            logger.error(f"Failed to send text via NtWork: {e}")
            return False
