from __future__ import annotations

from fastapi import FastAPI, Request
import logging
import os
from typing import Any, Dict
from queue import Queue

app = FastAPI(title="WeChat Webhook Receiver")

# Lightweight in-process queue for task messages emitted by webhook
_message_queue: Queue = Queue()
WECHAT_HOOK_TOKEN = os.environ.get("WECHAT_HOOK_TOKEN", "")
from .parser import MessageParser
from .models import WeChatMessage, TaskMessage


def _extract_message(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Very lightweight extractor; real implementation should decrypt, verify, and parse XML/JSON payloads
    if not payload:
        return {"type": "unknown", "content": ""}
    # Common fields in webhook payloads
    if "Encrypt" in payload:
        return {"type": "text", "content": "encrypted"}
    if "content" in payload:
        return {"type": "text", "content": payload.get("content")}
    return {"type": "unknown", "content": str(payload)}


def _verify_signature(signature: str) -> bool:
    if not WECHAT_HOOK_TOKEN:
        return True
    return signature == WECHAT_HOOK_TOKEN


@app.post("/webhook/wechat")
async def wechat_webhook(request: Request) -> Dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    # Simple signature check (placeholder); replace with real signature verification as needed
    sig = request.headers.get("X-WeChat-Signature", "")
    if not _verify_signature(sig):
        return {"ok": False, "error": "invalid signature"}
    # Lightweight parsing using the in-module parser
    parser = MessageParser()
    wechat_message: WeChatMessage = parser.parse(payload)
    # Build a task message if applicable
    task_msg: TaskMessage = parser.parse_task_message(wechat_message)
    if task_msg.is_project_task:
        _message_queue.put(task_msg)
        logging.info(f"Queued task message {task_msg.original_message.msg_id}")
    return {"ok": True, "task_id": getattr(task_msg.original_message, 'msg_id', '')}
