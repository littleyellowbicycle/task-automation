"""Abstract base class for message listeners."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable, List

from .models import WeChatMessage, TaskMessage


class ListenerType(str, Enum):
    """Available listener implementation types."""
    NTWORK = "ntwork"
    WEBHOOK = "webhook"
    UIAUTOMATION = "uiautomation"


class Platform(str, Enum):
    """Supported chat platforms."""
    WEWORK = "wework"
    WECHAT = "wechat"


@dataclass
class MessageCallback:
    """Callback handlers for message events."""
    on_message: Optional[Callable[[WeChatMessage], None]] = None
    on_task_message: Optional[Callable[[TaskMessage], None]] = None
    on_error: Optional[Callable[[Exception], None]] = None


class BaseListener(ABC):
    """
    Abstract base class for all message listeners.
    
    All listener implementations must inherit from this class and implement
    the required abstract methods.
    """
    
    def __init__(
        self,
        platform: Platform = Platform.WEWORK,
        keywords: Optional[List[str]] = None,
        regex_patterns: Optional[List[str]] = None,
    ):
        """
        Initialize the base listener.
        
        Args:
            platform: The chat platform to listen on
            keywords: Keywords to filter for project tasks
            regex_patterns: Regex patterns to match task messages
        """
        self.platform = platform
        self.keywords = keywords or []
        self.regex_patterns = regex_patterns or []
        self._running = False
        self._callback: Optional[MessageCallback] = None
    
    @property
    @abstractmethod
    def listener_type(self) -> ListenerType:
        """Return the type of this listener."""
        pass
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        Connect to the chat platform.
        
        Returns:
            True if connection successful, False otherwise
        
        Raises:
            WeChatConnectionError: If connection fails
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the chat platform."""
        pass
    
    @abstractmethod
    async def start_listening(self) -> None:
        """
        Start the message listening loop.
        
        This method should run indefinitely until disconnect() is called
        or an unrecoverable error occurs.
        """
        pass
    
    @abstractmethod
    async def get_next_message(self, timeout: float = 1.0) -> Optional[TaskMessage]:
        """
        Get the next task message from the queue.
        
        Args:
            timeout: Timeout in seconds to wait for a message
            
        Returns:
            TaskMessage if available, None if timeout
        """
        pass
    
    @abstractmethod
    def send_text(self, conversation_id: str, content: str) -> bool:
        """
        Send a text message to a conversation.
        
        Args:
            conversation_id: Target conversation ID
            content: Message content to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        pass
    
    def set_callback(self, callback: MessageCallback) -> None:
        """
        Set the message callback handler.
        
        Args:
            callback: Callback handlers for message events
        """
        self._callback = callback
    
    def _on_message(self, message: WeChatMessage) -> None:
        """Invoke the on_message callback if set."""
        if self._callback and self._callback.on_message:
            self._callback.on_message(message)
    
    def _on_task_message(self, task_message: TaskMessage) -> None:
        """Invoke the on_task_message callback if set."""
        if self._callback and self._callback.on_task_message:
            self._callback.on_task_message(task_message)
    
    def _on_error(self, error: Exception) -> None:
        """Invoke the on_error callback if set."""
        if self._callback and self._callback.on_error:
            self._callback.on_error(error)
    
    @property
    def is_running(self) -> bool:
        """Check if the listener is currently running."""
        return self._running
    
    @abstractmethod
    def get_contacts(self) -> List[dict]:
        """
        Get the contact list.
        
        Returns:
            List of contact dictionaries
        """
        pass
    
    @abstractmethod
    def get_rooms(self) -> List[dict]:
        """
        Get the room/group list.
        
        Returns:
            List of room/group dictionaries
        """
        pass
    
    def start_background(self) -> None:
        """Start listening in a background thread."""
        import asyncio
        import threading
        
        if self._running:
            return
        
        def _run():
            asyncio.run(self._run_listening_loop())
        
        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
    
    async def _run_listening_loop(self) -> None:
        """Internal method to run the listening loop with callbacks."""
        await self.connect()
        await self.start_listening()
