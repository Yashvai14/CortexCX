from sqlalchemy.orm import Session

from app.auth.model import User
from app.conversation.model import Conversation, ConversationStatus
from app.conversation.repositories.conversation_repository import (
    ConversationRepository,
)
from app.conversation.schema import (
    ConversationCreateRequest,
    ConversationResponse,
)
from app.customer.repositories.customer_repository import CustomerRepository


class CreateConversationCommand:

    @staticmethod
    def execute(
        db: Session,
        current_user: User,
        data: ConversationCreateRequest,
    ) -> ConversationResponse:

        customer_repo = CustomerRepository()
        conversation_repo = ConversationRepository()

        # 1. Tenant boundary: Verify customer belongs to current user's workspace
        customer = customer_repo.get_by_id_and_workspace(
            db=db,
            customer_id=data.customer_id,
            workspace_id=current_user.workspace_id,
        )

        if not customer:
            raise LookupError("Customer not found")

        # 2. Create conversation bound to caller's workspace
        conversation = Conversation(
            workspace_id=current_user.workspace_id,
            customer_id=data.customer_id,
            subject=data.subject.strip(),
            status=ConversationStatus.OPEN,
        )

        conversation_repo.add(
            db=db,
            obj=conversation,
        )

        db.commit()
        db.refresh(conversation)

        return ConversationResponse.model_validate(conversation)
