"""WeChat listener module using NtWork."""

import asyncio
import threading
from queue import Queue, Empty
from typing import Optional, Callable, List
from dataclasses import dataclass

from .models import WeChatMessage, TaskMessage
from .parser import MessageParser
from ..utils import get_logger
from ..exceptions import WeChatConnectionError

logger = get_logger("wechat_listener")


@dataclass
class MessageCallback:
    """Callback for message events."""
    on_message: Optional[Callable[[WeChatMessage], None]] = None
    on_task_message: Optional[Callable[[TaskMessage], None]] = None
    on_error: Optional[Callable[[Exception], None]] = None


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
        self._ntwork = None  # Will be initialized on connect
    
    def set_callback(self, callback: MessageCallback):
        """Set the message callback handler."""
        self.callback = callback
    
    async def connect(self) -> bool:
        """
        Connect to WeChat via NtWork.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Note: NtWork requires Windows + WeChat client
            # This is a placeholder that simulates connection
            logger.info(f"Connecting to WeChat at {self.ip}:{self.port}")
            
            # In real implementation, this would use ntwork:
            # from ntwork import WeWork
            # self._ntwork = WeWork()
            # self._ntwork.on_message = self._handle_message
            # self._ntwork.connect(self.ip, self.port, self.device_id)
            
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
            self._ntwork.disconnect()
        logger.info("WeChat listener disconnected")
    
    def _handle_message(self, message_data: dict):
        """
        Handle incoming message from NtWork.
        
        Args:
            message_data: Raw message data from NtWork
        """
        try:
            # Parse the message
            wechat_message = self.parser.parse(message_data)
            
            # Check if it's a task message
            task_message = self.parser.parse_task_message(wechat_message)
            
            # Queue the message for processing
            self._message_queue.put(task_message)
            
            logger.debug(f"Message received: {wechat_message.msg_id}")
            
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
                    # Call appropriate callback
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
