"""API and WebSocket Router for real-time team chat."""
from __future__ import annotations

import uuid
from fastapi import APIRouter, Form, WebSocket, WebSocketDisconnect

from core.database import utcnow
from core.security import session_manager
from core.state import ws_hub
from modules.chat.service import chat_service

router = APIRouter(tags=["chat"])


@router.post("/api/chat")
def post_chat(text: str = Form(...), token: str = Form(""), room: str = Form("team")):
    u = session_manager.get_user(token) or {"name": "Guest", "role": "guest", "username": "guest"}
    mid = chat_service.post_message(text=text, user_name=u["name"], user_role=u["role"], room=room)
    return {"ok": True, "id": mid}


@router.get("/api/chat")
def list_chat(room: str = "team"):
    return {"messages": chat_service.get_messages(room=room)}


@router.websocket("/ws")
async def chat_websocket(ws: WebSocket):
    await ws.accept()
    await ws_hub.connect(ws)
    try:
        while True:
            data = await ws.receive_json()
            if data.get("type") == "chat":
                token = data.get("token")
                u = session_manager.get_user(token) or {"name": "Guest", "role": "guest"}
                msg_text = str(data.get("text") or "")[:500]
                room = data.get("room") or "team"
                mid = chat_service.post_message(text=msg_text, user_name=u["name"], user_role=u["role"], room=room)
                await ws_hub.broadcast({
                    "type": "chat",
                    "id": mid,
                    "user": u["name"],
                    "role": u["role"],
                    "text": data.get("text"),
                    "created": utcnow(),
                    "room": room,
                })
            elif data.get("type") == "ping":
                await ws.send_json({"type": "pong", "clock": utcnow()})
    except WebSocketDisconnect:
        await ws_hub.disconnect(ws)
