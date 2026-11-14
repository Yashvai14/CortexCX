import threading
from contextlib import contextmanager
from typing import Any
from uuid import UUID
import httpx
from loguru import logger
from sqlalchemy.orm import Session

from app.ai.orchestrator import ConversationOrchestrator
from app.channels.base import BaseChannelAdapter
from app.channels.model import ChannelIdentity
from app.ai.composer import plain_text
from app.ai.handoff import INTERNAL_ERROR
from app.ai.routing.schema import Route, RouterIntent, decision as route_decision
from app.channels.idempotency import chat_locks, deduper
from app.channels.schema import ChannelIncomingMessage, ChannelResponse, ChannelTypeEnum
from app.conversation.message_model import Message, MessageSenderType
from app.conversation.model import Conversation, ConversationStatus
from app.core.config import settings
from app.customer.model import Customer, CustomerStatus
from app.workspace.model import Workspace

TELEGRAM_MAX_LEN = 4000  # Telegram rejects messages over 4096 characters
COMMANDS = ("/start", "/help")

# Inline-button taps: callback_data -> the text the AI pipeline receives
CALLBACK_TEXT = {
    "confirm:yes": "Yes, it's resolved",
    "confirm:no": "No, I still need help",
    "q:track": "I want to track my order",
    "q:returns": "What is your return policy?",
    "q:human": "I want to talk to a human",
}
CONFIRM_BUTTONS = [[("✅ Yes, it's resolved", "confirm:yes"), ("❌ No, I still need help", "confirm:no")]]
START_BUTTONS = [
    [("📦 Track my order", "q:track"), ("↩️ Return policy", "q:returns")],
    [("🙋 Talk to support", "q:human")],
]

# Button taps start their workflow explicitly; they are not re-interpreted from the callback text.
_BUTTON_ROUTES = {
    "q:track": lambda: route_decision(RouterIntent.ORDER_INFORMATION, 1.0, "button: track my order",
                                      route=Route.TOOLS, entities={"kind": "button"}),
    "q:returns": lambda: route_decision(RouterIntent.RETURN_POLICY, 1.0, "button: return policy",
                                        route=Route.RAG, entities={"kind": "button"}),
    "q:human": lambda: route_decision(RouterIntent.HUMAN_SUPPORT_REQUEST, 1.0, "button: talk to support",
                                      route=Route.ESCALATE, entities={"kind": "button"}),
}


def first_name(full_name: str | None) -> str:
    """Best-effort first name; empty for placeholder names like '@handle' or 'Telegram User 123'."""
    if not full_name or full_name.startswith(("Telegram User", "@", "Web Visitor")):
        return ""
    return full_name.split()[0]


class TelegramAdapter(BaseChannelAdapter):
    """Adapter for Telegram Bot API webhook updates and outbound message delivery."""



    def handle_incoming_message(
        self,
        db: Session,
        workspace_id: UUID,
        incoming: ChannelIncomingMessage,
    ) -> ChannelResponse:
        # One message per chat at a time: state is loaded after the previous turn finished, and a duplicate delivery
        # cannot interleave with the first. A failure gives the dedupe keys back so Telegram's retry is processed.
        with chat_locks.guard(incoming.channel_user_id):
            try:
                return self._handle_locked(db, workspace_id, incoming)
            except Exception as e:
                logger.exception(f"telegram turn failed ({type(e).__name__}); asking the customer to resend")
                try:
                    db.rollback()
                except Exception:
                    pass
                for key in incoming.metadata.get("dedupe_keys", []):
                    deduper.release(key)
                # An internal failure is NOT a handoff: say so plainly and never claim a person was contacted.
                self.send_telegram_message(chat_id=incoming.channel_user_id, text=INTERNAL_ERROR)
                return ChannelResponse(
                    conversation_id=incoming.metadata.get("conversation_id") or UUID(int=0), content=INTERNAL_ERROR,
                    ai_state="responded", decision="ERROR", confidence_score=0.0, sources=[], escalated=False,
                )

    def _handle_locked(
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

        # Bot commands are answered directly: they are not customer questions and must never reach the AI
        # (a bare "/start" would otherwise look like an unanswerable question and trigger a human handoff).
        command = incoming.content.strip().split()[0].split("@")[0].lower() if incoming.content.strip() else ""
        if command in COMMANDS:
            db.commit()
            returning = bool(conversation.messages)
            reply = self._command_reply(db, workspace_id, command, customer.full_name, returning)
            self.send_telegram_message(
                chat_id=chat_id, text=reply, buttons=START_BUTTONS if command == "/start" else None
            )
            return ChannelResponse(
                conversation_id=conversation.id,
                content=reply,
                ai_state=conversation.ai_state or "idle",
                decision="ANSWER",
                confidence_score=1.0,
                sources=[],
                escalated=False,
            )

        # 3. Save incoming customer message - unless this is a retry of one that was saved but never answered
        # (the previous attempt failed after saving): reusing it avoids a duplicate customer message.
        last = conversation.messages[-1] if conversation.messages else None
        is_retry = bool(
            last is not None and last.sender_type == MessageSenderType.CUSTOMER and last.content == incoming.content
        )  # under the chat lock a completed turn always ends with an AI reply, so this can only be a failed attempt
        if not is_retry:
            customer_msg = Message(
                conversation_id=conversation.id,
                sender_type=MessageSenderType.CUSTOMER,
                content=incoming.content,
            )
            db.add(customer_msg)
            db.commit()
        db.refresh(conversation)
        incoming.metadata["conversation_id"] = conversation.id

        # 4. Invoke Master AI Conversation Orchestrator (shows "typing…" while the model works)
        with self.typing_indicator(chat_id):
            response = ConversationOrchestrator.process_turn(
                db=db,
                workspace_id=workspace_id,
                conversation=conversation,
                customer_message_content=incoming.content,
                customer=customer,
                forced_route=(_BUTTON_ROUTES[incoming.metadata["button"]]() if incoming.metadata.get("button") in _BUTTON_ROUTES else None),
            )

        # 5. Outbound Delivery back to Telegram (answer + a compact line naming where it came from)
        reply_text = response.content
        if response.sources:
            places = [
                f"{s.get('section') or s.get('document_title')}" + (f" (p.{s['page']})" if s.get("page") else "")
                for s in response.sources
            ]
            reply_text += "\n\nSources: " + "; ".join(places)
        self.send_telegram_message(chat_id=chat_id, text=reply_text)

        return response

    @staticmethod
    def _command_reply(db: Session, workspace_id: UUID, command: str, name: str | None, returning: bool = False) -> str:
        ws = db.get(Workspace, workspace_id)
        store = ws.name if ws else "our store"
        first = first_name(name)
        if command == "/start":
            # Short and human. The capabilities are explained on /help or when the customer asks, not on every start.
            if returning:
                return f"Hey again{' ' + first if first else ''}! What can I help you with?"
            return f"Hey{' ' + first if first else ''}! Welcome to {store}. How can I help you today?"
        return "\n".join(
            [
                "I can help with:",
                "- Order tracking (send your order number)",
                "- Returns, refunds and shipping questions",
                "- Product availability and prices",
                "- Connecting you with support: just ask",
            ]
        )

    @classmethod
    def notify_customer(
        cls, db: Session, conversation: Conversation, text: str, buttons: list[list[tuple[str, str]]] | None = None
    ) -> bool:
        """Push a message (e.g. a human agent's reply) to the customer's Telegram chat, if they are on Telegram."""
        identity = (
            db.query(ChannelIdentity)
            .filter(
                ChannelIdentity.workspace_id == conversation.workspace_id,
                ChannelIdentity.channel_type == "telegram",
                ChannelIdentity.customer_id == conversation.customer_id,
            )
            .first()
        )
        if not identity:
            return False
        return cls.send_telegram_message(chat_id=identity.channel_user_id, text=text, buttons=buttons)

    @classmethod
    def answer_callback(cls, callback_id: str) -> None:
        token = settings.TELEGRAM_BOT_TOKEN
        if not token or not callback_id:
            return
        try:
            with httpx.Client(timeout=5.0) as client:
                client.post(
                    f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                    json={"callback_query_id": callback_id},
                )
        except Exception:
            pass

    @classmethod
    def send_chat_action(cls, chat_id: str | int, action: str = "typing") -> None:
        token = settings.TELEGRAM_BOT_TOKEN
        if not token:
            return
        try:
            with httpx.Client(timeout=5.0) as client:
                client.post(f"https://api.telegram.org/bot{token}/sendChatAction", json={"chat_id": chat_id, "action": action})
        except Exception:
            pass

    @classmethod
    @contextmanager
    def typing_indicator(cls, chat_id: str | int):
        """Keep the 'typing…' status visible (Telegram clears it after ~5s) while a slow reply is generated."""
        stop = threading.Event()

        def pump() -> None:
            while not stop.is_set():
                cls.send_chat_action(chat_id)
                stop.wait(4.0)

        t = None
        if settings.TELEGRAM_BOT_TOKEN:
            t = threading.Thread(target=pump, daemon=True)
            t.start()
        try:
            yield
        finally:
            stop.set()

    @classmethod
    def send_telegram_message(
        cls, chat_id: str | int, text: str, buttons: list[list[tuple[str, str]]] | None = None
    ) -> bool:
        """Send message back to user via Telegram Bot API (split if longer than Telegram's limit)."""
        token = settings.TELEGRAM_BOT_TOKEN
        if not token:
            # Token not configured (e.g. in testing/mock mode); skip HTTP call
            return False

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        text = plain_text(text)  # no parse_mode is set, so **bold** and "- " would show up literally
        parts = [text[i : i + TELEGRAM_MAX_LEN] for i in range(0, max(len(text), 1), TELEGRAM_MAX_LEN)]
        ok = True
        try:
            with httpx.Client(timeout=10.0) as client:
                for i, part in enumerate(parts):
                    body: dict[str, Any] = {"chat_id": chat_id, "text": part}
                    if buttons and i == len(parts) - 1:
                        body["reply_markup"] = {
                            "inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in buttons]
                        }
                    res = client.post(url, json=body)
                    if res.status_code != 200:
                        logger.error(f"Telegram sendMessage failed ({res.status_code}): {res.text[:200]}")
                        ok = False
        except Exception as e:
            logger.error(f"Telegram sendMessage error: {e}")
            return False
        return ok

    @classmethod
    def parse_webhook_payload(cls, payload: dict[str, Any]) -> ChannelIncomingMessage | None:
        """Parses a Telegram webhook update object with duplicate protection."""
        update_id = payload.get("update_id")
        keys: list[str] = []
        if update_id is not None:
            update_key = f"update_{update_id}"
            if not deduper.claim(update_key):
                return None  # duplicate delivery of the same update: already handled (or being handled)
            keys.append(update_key)

        callback = payload.get("callback_query")
        if callback:
            cls.answer_callback(callback.get("id", ""))  # stop the button's loading spinner
            cb_text = CALLBACK_TEXT.get(callback.get("data", ""))
            cb_chat = str((callback.get("message") or {}).get("chat", {}).get("id", ""))
            if not cb_text or not cb_chat:
                return None
            u = callback.get("from", {})
            return ChannelIncomingMessage(
                channel_type=ChannelTypeEnum.TELEGRAM,
                channel_user_id=cb_chat,
                content=cb_text,
                customer_name=f"{u.get('first_name', '')} {u.get('last_name', '')}".strip() or u.get("username", ""),
                metadata={"update_id": update_id, "username": u.get("username"), "callback": True,
                          "button": callback.get("data", ""), "dedupe_keys": keys},
            )

        message = payload.get("message") or payload.get("edited_message")
        if not message:
            return None

        chat = message.get("chat", {})
        chat_id = str(chat.get("id", ""))
        msg_id = message.get("message_id")

        if msg_id and chat_id:
            msg_key = f"msg_{chat_id}_{msg_id}"
            if not deduper.claim(msg_key):
                for k in keys:
                    deduper.release(k)  # leave no half-claimed update behind
                return None  # the same message arrived in a different update (e.g. an edit or a re-send)
            keys.append(msg_key)

        text = message.get("text", "").strip()
        if not text:
            # Photo, voice, sticker, file...: say so instead of leaving the customer with silence.
            cls.send_telegram_message(
                chat_id=chat_id,
                text="Sorry, I can only read text messages right now. Could you type your question?",
            )
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
                "dedupe_keys": keys,
                "username": from_user.get("username"),
                "is_bot": from_user.get("is_bot", False),
            },
        )


