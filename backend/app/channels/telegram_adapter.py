from typing import Any
from uuid import UUID
import httpx
from sqlalchemy.orm import Session

from app.ai.orchestrator import ConversationOrchestrator
from app.channels.base import BaseChannelAdapter
from app.channels.model import ChannelIdentity
from app.channels.schema import ChannelIncomingMessage, ChannelResponse, ChannelTypeEnum
from app.conversation.message_model import Message, MessageSenderType
from app.conversation.model import Conversation, ConversationStatus
from app.core.config import settings
from app.customer.model import Customer, CustomerStatus


class TelegramAdapter(BaseChannelAdapter):
    """Adapter for Telegram Bot API webhook updates and outbound message delivery."""

    # In-memory duplicate protection cache for recently processed Telegram update/message IDs
    _processed_message_ids: set[str] = set()


    def handle_incoming_message(
        self,
        db: Session,
        workspace_id: UUID,
        incoming: ChannelIncomingMessage,
    ) -> ChannelResponse:
        chat_id = incoming.channel_user_id

        # 1. Look up or create Customer identity for this Telegram user
        identity = (
            db.query(ChannelIdentity)
            .filter(
                ChannelIdentity.workspace_id == workspace_id,
                ChannelIdentity.channel_type == "telegram",
                ChannelIdentity.channel_user_id == str(chat_id),
            )
            .first()
        )

        customer = None
        if identity:
            customer = db.query(Customer).filter(Customer.id == identity.customer_id).first()

        if not customer:
            tg_username = incoming.metadata.get("username", "")
            display_name = incoming.customer_name or (f"@{tg_username}" if tg_username else f"Telegram User {chat_id}")
            tg_email = f"tg_{chat_id}@telegram.cortex"

            customer = Customer(
                workspace_id=workspace_id,
                full_name=display_name,
                email=tg_email,
                status=CustomerStatus.ACTIVE,
            )
            db.add(customer)
            db.flush()

            identity = ChannelIdentity(
                workspace_id=workspace_id,
                channel_type="telegram",
                channel_user_id=str(chat_id),
                customer_id=customer.id,
                metadata_json=incoming.metadata,
            )
            db.add(identity)
            db.flush()

        # 2. Find active conversation or create one
        conversation = (
            db.query(Conversation)
            .filter(
                Conversation.workspace_id == workspace_id,
                Conversation.customer_id == customer.id,
                Conversation.status.in_([ConversationStatus.OPEN, ConversationStatus.PENDING]),
            )
            .order_by(Conversation.created_at.desc())
            .first()
        )

        if not conversation:
            conversation = Conversation(
                workspace_id=workspace_id,
                customer_id=customer.id,
                subject=f"Telegram Chat with {customer.full_name}",
                status=ConversationStatus.OPEN,
                ai_enabled=True,
                ai_state="idle",
            )
            db.add(conversation)
            db.flush()

        # 3. Save incoming customer message
        customer_msg = Message(
            conversation_id=conversation.id,
            sender_type=MessageSenderType.CUSTOMER,
            content=incoming.content,
        )
        db.add(customer_msg)
        db.commit()
        db.refresh(conversation)

        # 4. Invoke Master AI Conversation Orchestrator
        response = ConversationOrchestrator.process_turn(
            db=db,
            workspace_id=workspace_id,
            conversation=conversation,
            customer_message_content=incoming.content,
            customer=customer,
        )

        # 5. Outbound Delivery back to Telegram
        self.send_telegram_message(chat_id=chat_id, text=response.content)

        return response

    @classmethod
    def send_telegram_message(cls, chat_id: str | int, text: str) -> bool:
        """Send message back to user via Telegram Bot API."""
        token = settings.TELEGRAM_BOT_TOKEN
        if not token:
            # Token not configured (e.g. in testing/mock mode); skip HTTP call
            return False

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
        }
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(url, json=payload)
                return res.status_code == 200
        except Exception:
            return False

    @classmethod
    def parse_webhook_payload(cls, payload: dict[str, Any]) -> ChannelIncomingMessage | None:
        """Parses a Telegram webhook update object with duplicate protection."""
        update_id = payload.get("update_id")
        if update_id is not None:
            update_key = f"update_{update_id}"
            if update_key in cls._processed_message_ids:
                return None  # Duplicate update ignored
            cls._processed_message_ids.add(update_key)

        message = payload.get("message") or payload.get("edited_message")
        if not message:
            return None

        chat = message.get("chat", {})
        chat_id = str(chat.get("id", ""))
        msg_id = message.get("message_id")

        if msg_id and chat_id:
            msg_key = f"msg_{chat_id}_{msg_id}"
            if msg_key in cls._processed_message_ids:
                return None  # Duplicate message ignored
            cls._processed_message_ids.add(msg_key)

        if len(cls._processed_message_ids) > 10000:
            cls._processed_message_ids.clear()

        text = message.get("text", "").strip()
        if not text:
            return None

        from_user = message.get("from", {})
        first_name = from_user.get("first_name", "")
        last_name = from_user.get("last_name", "")
        full_name = f"{first_name} {last_name}".strip() or from_user.get("username", "")

        return ChannelIncomingMessage(
            channel_type=ChannelTypeEnum.TELEGRAM,
            channel_user_id=chat_id,
            content=text,
            customer_name=full_name or f"Telegram User {chat_id}",
            metadata={
                "update_id": update_id,
                "message_id": msg_id,
                "username": from_user.get("username"),
                "is_bot": from_user.get("is_bot", False),
            },
        )


