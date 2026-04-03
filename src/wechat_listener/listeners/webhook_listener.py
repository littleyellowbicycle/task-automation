"""WeChat listener using Webhook (HTTP callback implementation)."""

import asyncio
import json
import hmac
import hashlib
import os
from collections import deque
from queue import Queue, Empty
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Request
import uvicorn

from ..base import BaseListener, ListenerType, Platform
from ..models import TaskMessage
from ..parser import MessageParser
from ...utils import get_logger
from ...exceptions import WeChatConnectionError

logger = get_logger("wechat_listener.webhook")


class WebhookListener(BaseListener):
    """
    WeChat message listener using Webhook HTTP callbacks.
    
    This implementation runs an HTTP server that receives message callbacks
    from WeChat/WeCom webhook integrations.
    
    Note: Requires proper webhook configuration and permissions on the
    WeChat/WeCom admin console.
    """
    
    def __init__(
        self,
        platform: Platform = Platform.WEWORK,
        host: str = "0.0.0.0",
        port: int = 8080,
        token: Optional[str] = None,
        path: str = "/webhook/wechat",
        keywords: Optional[List[str]] = None,
        regex_patterns: Optional[List[str]] = None,
    ):
        """
        Initialize the Webhook listener.
        
        Args:
            platform: The chat platform (WEWORK or WECHAT)
            host: HTTP server host
            port: HTTP server port
            token: Webhook verification token
            path: Webhook endpoint path
            keywords: Keywords to filter for project tasks
            regex_patterns: Regex patterns to match task messages
        """
        super().__init__(platform=platform, keywords=keywords, regex_patterns=regex_patterns)
        self.host = host
        self.port = port
        self.token = token or os.environ.get("WECHAT_HOOK_TOKEN", "")
        self.path = path
        self.parser = MessageParser(keywords=keywords, regex_patterns=regex_patterns)
        self._message_queue: Queue = Queue()
        self._app: Optional[FastAPI] = None
        self._server_task: Optional[asyncio.Task] = None
        self._dedup_ids: deque = deque()
        self._dedup_set: set = set()
        self._dedup_lock: Optional[asyncio.Lock] = None
        self._MAX_DEDUP = 200
    
    @property
    def listener_type(self) -> ListenerType:
        return ListenerType.WEBHOOK
    
    async def connect(self) -> bool:
        try:
            logger.info(f"Starting webhook server for {self.platform.value} on {self.host}:{self.port}")
            
            self._app = FastAPI(title=f"{self.platform.value} Webhook Receiver")
            self._setup_routes()
            
            self._running = True
            logger.info(f"Webhook listener ready for {self.platform.value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start webhook server: {e}")
            raise WeChatConnectionError(f"Webhook server start failed: {e}")
    
    def _setup_routes(self) -> None:
        @self._app.post(self.path)
        async def handle_webhook(request: Request) -> Dict[str, Any]:
            return await self._handle_webhook_request(request)
        
        @self._app.get("/health")
        async def health_check() -> Dict[str, str]:
            return {"status": "healthy", "platform": self.platform.value}
    
    async def _handle_webhook_request(self, request: Request) -> Dict[str, Any]:
        body = await request.body()
        
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            payload = {}
        
        sig = request.headers.get("X-WeChat-Signature", "")
        if not self._verify_signature(sig, body):
            logger.warning("Invalid webhook signature")
            return {"ok": False, "error": "invalid signature"}
        
        msg_id = str(payload.get("msg_id") or payload.get("id") or hash(str(payload)))
        if await self._is_duplicate(msg_id):
            return {"ok": True, "status": "duplicate", "task_id": msg_id}
        
        try:
            wechat_message = self.parser.parse(payload)
            task_message = self.parser.parse_task_message(wechat_message)
            
            self._message_queue.put(task_message)
            self._on_message(wechat_message)
            
            if task_message.is_project_task:
                self._on_task_message(task_message)
                logger.info(f"Queued task message {task_message.original_message.msg_id}")
            
            return {"ok": True, "task_id": task_message.original_message.msg_id}
            
        except Exception as e:
            logger.error(f"Error processing webhook message: {e}")
            self._on_error(e)
            return {"ok": False, "error": str(e)}
    
    def _verify_signature(self, signature: str, body: bytes) -> bool:
        if not self.token:
            return True
        
        try:
            expected = hmac.new(
                self.token.encode(),
                body,
                hashlib.sha256
            ).hexdigest()
            return signature == expected
        except Exception:
            return False
    
    async def _is_duplicate(self, msg_id: str) -> bool:
        if self._dedup_lock is None:
            self._dedup_lock = asyncio.Lock()
        
        async with self._dedup_lock:
            if msg_id in self._dedup_set:
                return True
            
            self._dedup_set.add(msg_id)
            self._dedup_ids.append(msg_id)
            
            if len(self._dedup_ids) > self._MAX_DEDUP:
                old = self._dedup_ids.popleft()
                self._dedup_set.discard(old)
            
            return False
    
    def disconnect(self) -> None:
        self._running = False
        if self._server_task:
            self._server_task.cancel()
        logger.info("Webhook listener disconnected")
    
    async def get_next_message(self, timeout: float = 1.0) -> Optional[TaskMessage]:
        try:
            return self._message_queue.get(timeout=timeout)
        except Empty:
            return None
    
    async def start_listening(self) -> None:
        config = uvicorn.Config(
            app=self._app,
            host=self.host,
            port=self.port,
            log_level="warning",
        )
        server = uvicorn.Server(config)
        
        try:
            await server.serve()
        except asyncio.CancelledError:
            logger.info("Webhook server stopped")
    
    def get_contacts(self) -> List[dict]:
        return []
    
    def get_rooms(self) -> List[dict]:
        return []
    
    def send_text(self, conversation_id: str, content: str) -> bool:
        logger.warning("Webhook listener does not support sending messages")
        return False
