import uuid
from uuid import UUID
from sqlalchemy.orm import Session

from app.ai.orchestrator import ConversationOrchestrator
from app.channels.base import BaseChannelAdapter
from app.channels.model import ChannelIdentity
from app.channels.schema import ChannelIncomingMessage, ChannelResponse
from app.conversation.message_model import Message, MessageSenderType
from app.conversation.model import Conversation, ConversationStatus
from app.customer.model import Customer, CustomerStatus


class WebChatAdapter(BaseChannelAdapter):
    """Adapter for storefront website chat widget interactions."""

    def handle_incoming_message(
        self,
        db: Session,
        workspace_id: UUID,
        incoming: ChannelIncomingMessage,
    ) -> ChannelResponse:
        session_id = incoming.channel_user_id

        # 1. Look up channel identity to identify customer
        identity = (
            db.query(ChannelIdentity)
            .filter(
                ChannelIdentity.workspace_id == workspace_id,
                ChannelIdentity.channel_type == "webchat",
                ChannelIdentity.channel_user_id == session_id,
            )
            .first()
        )

        customer = None
        if identity:
            customer = db.query(Customer).filter(Customer.id == identity.customer_id).first()

        if not customer:
            # Check if customer already exists with this email in the workspace
            if incoming.customer_email:
                customer = (
                    db.query(Customer)
                    .filter(
                        Customer.workspace_id == workspace_id,
                        Customer.email.ilike(incoming.customer_email.strip()),
                    )
                    .first()
                )

            if not customer:
                guest_email = incoming.customer_email or f"guest_{session_id[:8]}@webchat.cortex"
                guest_name = incoming.customer_name or f"Web Visitor {session_id[:6]}"

                customer = Customer(
                    workspace_id=workspace_id,
                    full_name=guest_name,
                    email=guest_email,
                    status=CustomerStatus.ACTIVE,
                )
                db.add(customer)
                db.flush()

            identity = ChannelIdentity(
                workspace_id=workspace_id,
                channel_type="webchat",
                channel_user_id=session_id,
                customer_id=customer.id,
            )
            db.add(identity)
            db.flush()

        # 2. Find active open conversation or create one
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
            subject = incoming.content[:60] if len(incoming.content) > 10 else "Website Customer Inquiry"
            conversation = Conversation(
                workspace_id=workspace_id,
                customer_id=customer.id,
                subject=subject,
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

        return response
