from typing import Any
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.channels.schema import ChannelIncomingMessage, ChannelResponse, ChannelTypeEnum
from app.channels.telegram_adapter import TelegramAdapter
from app.channels.webchat_adapter import WebChatAdapter
from app.conversation.message_model import Message
from app.conversation.model import Conversation
from app.channels.model import ChannelIdentity
from app.core.config import settings
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

    incoming = ChannelIncomingMessage(
        channel_type=ChannelTypeEnum.WEBCHAT,
        channel_user_id=payload.session_id,
        content=payload.content.strip(),
        customer_name=payload.customer_name,
        customer_email=payload.customer_email,
    )

    adapter = WebChatAdapter()
    return adapter.handle_incoming_message(
        db=db,
        workspace_id=payload.workspace_id,
        incoming=incoming,
    )


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
