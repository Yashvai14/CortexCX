import json
import queue
import threading
import time
from typing import Any
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.channels.schema import ChannelIncomingMessage, ChannelResponse, ChannelTypeEnum
from app.channels.telegram_adapter import TelegramAdapter
from app.channels.webchat_adapter import WebChatAdapter
from app.conversation.message_model import Message
from app.conversation.model import Conversation
from app.channels.model import ChannelIdentity
from app.core.config import settings
from app.ai.progress import reset_progress, set_progress
from app.database.database import SessionLocal
from app.database.session import get_db
from app.workspace.model import Workspace

router = APIRouter(
    prefix="/channels",
    tags=["Omnichannel Customer Integrations"],
)


class WebChatMessageRequest(BaseModel):
    workspace_id: UUID
    session_id: str
    content: str
    customer_name: str | None = None
    customer_email: str | None = None
    # Lets the client retry a send (network drop, timeout) without the customer's message being stored twice.
    client_message_id: str | None = Field(default=None, max_length=64)


# Finished replies by (workspace, session, client_message_id), kept briefly so a retry returns the same answer.
_RECENT: dict[tuple[str, str, str], tuple[float, dict]] = {}
_RECENT_LOCK = threading.Lock()
_RECENT_TTL = 15 * 60


def _recent_get(payload: "WebChatMessageRequest") -> dict | None:
    if not payload.client_message_id:
        return None
    key = (str(payload.workspace_id), payload.session_id, payload.client_message_id)
    with _RECENT_LOCK:
        hit = _RECENT.get(key)
        return hit[1] if hit and time.time() - hit[0] < _RECENT_TTL else None


def _recent_put(payload: "WebChatMessageRequest", result: dict) -> None:
    if not payload.client_message_id:
        return
    with _RECENT_LOCK:
        now = time.time()
        for k in [k for k, (t, _) in _RECENT.items() if now - t > _RECENT_TTL]:
            _RECENT.pop(k, None)
        if len(_RECENT) > 2000:
            _RECENT.pop(next(iter(_RECENT)), None)
        _RECENT[(str(payload.workspace_id), payload.session_id, payload.client_message_id)] = (now, result)


def _build_incoming(payload: "WebChatMessageRequest") -> ChannelIncomingMessage:
    return ChannelIncomingMessage(
        channel_type=ChannelTypeEnum.WEBCHAT,
        channel_user_id=payload.session_id,
        content=payload.content.strip(),
        customer_name=payload.customer_name,
        customer_email=payload.customer_email,
    )


@router.post("/webchat/message/stream")
def handle_webchat_message_stream(payload: WebChatMessageRequest):
    """Same as /webchat/message, but streams real pipeline stages as Server-Sent Events:

        event: stage   data: {"stage": "thinking" | "searching" | "writing"}
        event: final   data: <the ChannelResponse JSON>
        event: error   data: {"message": "..."}

    The answer itself is delivered whole, after validation (groundedness, citations), so the customer never sees
    an unchecked draft.
    """
    if not payload.content or not payload.content.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message content cannot be empty")
    check_db = SessionLocal()
    try:
        if not check_db.query(Workspace.id).filter(Workspace.id == payload.workspace_id).first():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    finally:
        check_db.close()

    def sse(event: str, data: Any) -> str:
        return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"

    cached = _recent_get(payload)
    if cached is not None:
        return StreamingResponse(iter([sse("final", cached)]), media_type="text/event-stream")

    q: "queue.Queue[tuple[str, Any]]" = queue.Queue()

    def worker() -> None:
        token = set_progress(lambda stage: q.put(("stage", {"stage": stage})))
        db = SessionLocal()
        try:
            response = WebChatAdapter().handle_incoming_message(
                db=db, workspace_id=payload.workspace_id, incoming=_build_incoming(payload)
            )
            result = response.model_dump(mode="json")
            _recent_put(payload, result)
            q.put(("final", result))
        except Exception as e:  # never leave the customer's chat hanging
            q.put(("error", {"message": "Sorry, something went wrong while preparing your answer."}))
            from loguru import logger
            logger.error(f"webchat stream failed: {type(e).__name__}: {e}")
        finally:
            db.close()
            reset_progress(token)
            q.put(("end", None))

    threading.Thread(target=worker, daemon=True).start()

    def gen():
        yield sse("stage", {"stage": "thinking"})
        while True:
            kind, data = q.get()
            if kind == "end":
                break
            yield sse(kind, data)

    return StreamingResponse(
        gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@router.post("/webchat/message", response_model=ChannelResponse)
def handle_webchat_message(
    payload: WebChatMessageRequest,
    db: Session = Depends(get_db),
):
    """Public customer endpoint for the storefront website chat widget."""
    ws = db.query(Workspace).filter(Workspace.id == payload.workspace_id).first()
    if not ws:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    if not payload.content or not payload.content.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message content cannot be empty")

    cached = _recent_get(payload)
    if cached is not None:
        return ChannelResponse(**cached)

    adapter = WebChatAdapter()
    response = adapter.handle_incoming_message(
        db=db,
        workspace_id=payload.workspace_id,
        incoming=_build_incoming(payload),
    )
    _recent_put(payload, response.model_dump(mode="json"))
    return response


@router.get("/webchat/history/{session_id}")
def get_webchat_history(
    session_id: str,
    workspace_id: UUID = Query(...),
    db: Session = Depends(get_db),
):
    """Retrieve message history for an active webchat visitor session."""
    identity = (
        db.query(ChannelIdentity)
        .filter(
            ChannelIdentity.workspace_id == workspace_id,
            ChannelIdentity.channel_type == "webchat",
            ChannelIdentity.channel_user_id == session_id,
        )
        .first()
    )
    if not identity:
        return {"messages": []}

    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.workspace_id == workspace_id,
            Conversation.customer_id == identity.customer_id,
        )
        .order_by(Conversation.created_at.desc())
        .first()
    )
    if not conversation:
        return {"messages": []}

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc())
        .all()
    )

    return {
        "conversation_id": conversation.id,
        "ai_state": conversation.ai_state,
        "messages": [
            {
                "id": str(m.id),
                "sender_type": m.sender_type.value if hasattr(m.sender_type, "value") else str(m.sender_type),
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


@router.post("/telegram/webhook")
def handle_telegram_webhook(
    update: dict[str, Any],
    workspace_id: UUID = Query(...),
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Webhook receiver endpoint for Telegram Bot API updates."""
    # Verify optional secret token header
    if settings.TELEGRAM_WEBHOOK_SECRET and x_telegram_bot_api_secret_token != settings.TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook secret token")

    ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not ws:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    incoming = TelegramAdapter.parse_webhook_payload(update)
    if not incoming:
        # Acknowledged update without text (e.g. status change or duplicate)
        return {"status": "ignored"}

    adapter = TelegramAdapter()
    adapter.handle_incoming_message(
        db=db,
        workspace_id=workspace_id,
        incoming=incoming,
    )

    return {"status": "ok"}
