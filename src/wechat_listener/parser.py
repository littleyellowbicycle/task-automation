from __future__ import annotations

from typing import Dict, Any


def parse_message(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not payload:
        return {}
    if "Encrypt" in payload:
        return {"type": "text", "content": "encrypted"}
    if isinstance(payload.get("content"), str):
        return {"type": "text", "content": payload.get("content")}
    # Fallback: coerce to string
    return {"type": payload.get("type", "unknown"), "content": str(payload)}
