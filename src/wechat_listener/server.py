from __future__ import annotations

from fastapi import FastAPI, Request
import logging
from typing import Any, Dict

app = FastAPI(title="WeChat Webhook Receiver")


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


@app.post("/webhook/wechat")
async def wechat_webhook(request: Request) -> Dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    message = _extract_message(payload)
    logging.info(f"WeChat webhook received: {payload!r} -> parsed: {message!r}")
    # In a real setup, forward to asynchronous processing pipeline here
    return {"ok": True, "message": message}
