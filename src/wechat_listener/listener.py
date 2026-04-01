"""WeChat listener module using NtWork."""

import asyncio
import threading
from queue import Queue, Empty
from typing import Optional, Callable, List
from dataclasses import dataclass, field

from .models import WeChatMessage, TaskMessage, MessageType, ConversationType
from .parser import MessageParser
from ..utils import get_logger
from ..exceptions import WeChatConnectionError, WeChatMessageError

logger = get_logger("wechat_listener")

NTWORK_AVAILABLE = False
try:
    import ntwork
    NTWORK_AVAILABLE = True
except ImportError:
    ntwork = None


@dataclass
class MessageCallback:
    """Callback for message events."""
    on_message: Optional[Callable] = None
    on_task_message: Optional[Callable] = None
    on_error: Optional[Callable] = None


class WeChatListener:
    """
    WeChat message listener using NtWork SDK.

    Listens for messages from WeChat and filters for project-related tasks.
    """

    def __init__(
        self,
        device_id: str = "",
        ip: str = "127.0.0.1",
        port: int = 5037,
        keywords: Optional[List[str]] = None,
        regex_patterns: Optional[List[str]] = None,
    ):
        """
        Initialize the WeChat listener.

        Args:
            device_id: WeChat device ID
            ip: ADB server IP
            port: ADB server port
            keywords: Keywords to filter for project tasks
            regex_patterns: Regex patterns to match task messages
        """
        self.device_id = device_id
        self.ip = ip
        self.port = port
        self.parser = MessageParser(keywords=keywords, regex_patterns=regex_patterns)
        self.callback = MessageCallback()
        self._message_queue: Queue = Queue()
        self._running = False
        self._listener_thread: Optional[threading.Thread] = None
        self._ntwork: Optional[object] = None

    def set_callback(self, callback: MessageCallback):
        """Set the message callback handler."""
        self.callback = callback

    async def connect(self) -> bool:
        """
        Connect to WeChat via NtWork.

        Returns:
            True if connection successful, False otherwise
        """
        if not NTWORK_AVAILABLE:
            raise WeChatConnectionError(
                "ntwork is not installed. Install with: pip install ntwork "
                "(requires Python 3.10 and WeCom 4.0.8.6027)"
            )

        try:
            logger.info(f"Connecting to WeChat at {self.ip}:{self.port}")

            self._ntwork = ntwork.WeWork()
            self._ntwork.open(smart=True)
            self._ntwork.wait_login()

            login_info = self._ntwork.get_login_info()
            logger.info(f"Logged in as: {login_info}")

            self._ntwork.on(ntwork.MT_ALL, self._handle_ntwork_message)

            self._running = True
            logger.info("WeChat listener connected")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to WeChat: {e}")
            raise WeChatConnectionError(f"Connection failed: {e}")

    def disconnect(self):
        """Disconnect from WeChat."""
        self._running = False
        if self._ntwork:
            try:
                ntwork.exit_()
            except Exception:
                pass
        logger.info("WeChat listener disconnected")

    def _handle_ntwork_message(self, wework_instance, message: dict):
        """
        Handle incoming message from NtWork.

        Args:
            wework_instance: WeWork instance
            message: Raw message data from NtWork
        """
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

            logger.debug(f"Message received: {wechat_message.msg_id} from {sender}")

        except Exception as e:
            logger.error(f"Error handling message: {e}")
            if self.callback.on_error:
                self.callback.on_error(e)

    async def get_next_message(self, timeout: float = 1.0) -> Optional[TaskMessage]:
        """
        Get the next task message from the queue.

        Args:
            timeout: Timeout in seconds

        Returns:
            TaskMessage if available, None otherwise
        """
        try:
            return self._message_queue.get(timeout=timeout)
        except Empty:
            return None

    async def start_listening(self):
        """Start the message listening loop."""
        await self.connect()

        while self._running:
            try:
                task_message = await self.get_next_message(timeout=1.0)

                if task_message:
                    if self.callback.on_message:
                        self.callback.on_message(task_message.original_message)

                    if task_message.is_project_task and self.callback.on_task_message:
                        self.callback.on_task_message(task_message)

            except Exception as e:
                logger.error(f"Error in listening loop: {e}")
                if self.callback.on_error:
                    self.callback.on_error(e)
                await asyncio.sleep(1)

    def start_background(self):
        """Start listening in a background thread."""
        if self._listener_thread and self._listener_thread.is_alive():
            logger.warning("Listener already running")
            return

        self._listener_thread = threading.Thread(target=self._run_background)
        self._listener_thread.daemon = True
        self._listener_thread.start()
        logger.info("WeChat listener started in background")

    def _run_background(self):
        """Run the listener loop in background."""
        asyncio.run(self.start_listening())

    def get_contacts(self) -> List[dict]:
        """Get internal contacts list."""
        if not self._ntwork:
            return []
        return self._ntwork.get_inner_contacts()

    def get_external_contacts(self) -> List[dict]:
        """Get external contacts list."""
        if not self._ntwork:
            return []
        return self._ntwork.get_external_contacts()

    def get_rooms(self) -> List[dict]:
        """Get room/group list."""
        if not self._ntwork:
            return []
        return self._ntwork.get_rooms()

    def send_text(self, conversation_id: str, content: str) -> bool:
        """Send a text message to a conversation."""
        if not self._ntwork:
            return False
        try:
            self._ntwork.send_text(conversation_id=conversation_id, content=content)
            return True
        except Exception as e:
            logger.error(f"Failed to send text: {e}")
            return False
