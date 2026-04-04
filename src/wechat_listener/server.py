"""Legacy webhook server module (kept for backward compatibility)."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
from collections import deque
from queue import Queue
from typing import Any, Dict

from fastapi import FastAPI, Request

from .models import TaskMessage, WeChatMessage
from .parser import MessageParser

app = FastAPI(title="WeChat Webhook Receiver")

_message_queue: Queue = Queue()
WECHAT_HOOK_TOKEN = os.environ.get("WECHAT_HOOK_TOKEN", "")
_dedup_ids: deque = deque()
_dedup_set: set = set()
_dedup_lock: asyncio.Lock | None = None
_MAX_DEDUP = 200


def _ensure_lock() -> asyncio.Lock:
    global _dedup_lock
    if _dedup_lock is None:
        _dedup_lock = asyncio.Lock()
    return _dedup_lock


def _verify_signature_v1(signature: str, body: bytes) -> bool:
    if not WECHAT_HOOK_TOKEN:
        return True
    try:
        expected = hmac.new(WECHAT_HOOK_TOKEN.encode(), body, hashlib.sha256).hexdigest()
        return signature == expected
    except Exception:
        return False


async def _is_duplicate(msg_id: str) -> bool:
    lock = _ensure_lock()
    async with lock:
        if msg_id in _dedup_set:
            return True
        _dedup_set.add(msg_id)
        _dedup_ids.append(msg_id)
        if len(_dedup_ids) > _MAX_DEDUP:
            old = _dedup_ids.popleft()
            _dedup_set.discard(old)
        return False


def _extract_message(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not payload:
        return {"type": "unknown", "content": ""}
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
    body = await request.body()
    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        payload = {}
    sig = request.headers.get("X-WeChat-Signature", "")
    if not _verify_signature_v1(sig, body):
        return {"ok": False, "error": "invalid signature"}

    msg_id = str(payload.get("msg_id") or payload.get("id") or hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest())
    if await _is_duplicate(msg_id):
        return {"ok": True, "status": "duplicate", "task_id": msg_id}

    parser = MessageParser()
    wechat_message: WeChatMessage = parser.parse(payload)
    task_msg: TaskMessage = parser.parse_task_message(wechat_message)
    if task_msg.is_project_task:
        _message_queue.put(task_msg)
        logging.info(f"Queued task message {task_msg.original_message.msg_id}")
    return {"ok": True, "task_id": getattr(task_msg.original_message, 'msg_id', '')}
