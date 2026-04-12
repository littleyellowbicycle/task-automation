from __future__ import annotations

from fastapi import APIRouter, Request

from ...utils import get_logger

logger = get_logger("gateway.routes.feishu_callback")

router = APIRouter(prefix="/api/v1", tags=["feishu"])


@router.post("/feishu/callback")
async def feishu_callback(request: Request):
    app = request.app
    message_router = app.state.message_router

    try:
        body = await request.body()
        import json
        data = json.loads(body.decode("utf-8"))
    except Exception as e:
        logger.error(f"Failed to parse Feishu callback: {e}")
        return {"code": 400, "message": "Invalid request"}

    if data.get("type") == "url_verification":
        challenge = data.get("challenge", "")
        logger.info(f"URL verification challenge: {challenge}")
        return {"challenge": challenge}

    try:
        result = await message_router.route_feishu_callback(data)
        return result
    except Exception as e:
        logger.error(f"Failed to route Feishu callback: {e}")
        return {"code": 500, "message": str(e)}
