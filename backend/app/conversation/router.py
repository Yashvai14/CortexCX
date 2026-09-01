from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.model import User, UserRole
from app.auth.permissions import require_roles
from app.conversation.commands.create_conversation import (
    CreateConversationCommand,
)
from app.conversation.commands.create_message import CreateMessageCommand
from app.conversation.commands.get_conversation import GetConversationCommand
from app.conversation.commands.list_conversations import (
    ListConversationsCommand,
)
from app.conversation.commands.list_messages import ListMessagesCommand
from app.conversation.commands.update_conversation import (
    UpdateConversationCommand,
)
from app.conversation.model import ConversationStatus
from app.conversation.schema import (
    ConversationCreateRequest,
    ConversationResponse,
    ConversationUpdateRequest,
    MessageCreateRequest,
    MessageResponse,
)
from app.database.session import get_db

router = APIRouter(
    prefix="/conversations",
    tags=["Conversations"],
)


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    data: ConversationCreateRequest,
    current_user: User = Depends(
        require_roles(UserRole.OWNER, UserRole.ADMIN, UserRole.AGENT)
    ),
    db: Session = Depends(get_db),
):
    try:
        return CreateConversationCommand.execute(
            db=db,
            current_user=current_user,
            data=data,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("", response_model=list[ConversationResponse])
def list_conversations(
    customer_id: UUID | None = Query(None),
    status: ConversationStatus | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ListConversationsCommand.execute(
        db=db,
        current_user=current_user,
        customer_id=customer_id,
        status=status,
    )


@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return GetConversationCommand.execute(
            db=db,
            current_user=current_user,
            conversation_id=conversation_id,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.patch("/{conversation_id}", response_model=ConversationResponse)
def update_conversation(
    conversation_id: UUID,
    data: ConversationUpdateRequest,
    current_user: User = Depends(
        require_roles(UserRole.OWNER, UserRole.ADMIN, UserRole.AGENT)
    ),
    db: Session = Depends(get_db),
):
    try:
        return UpdateConversationCommand.execute(
            db=db,
            current_user=current_user,
            conversation_id=conversation_id,
            data=data,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_message(
    conversation_id: UUID,
    data: MessageCreateRequest,
    current_user: User = Depends(
        require_roles(UserRole.OWNER, UserRole.ADMIN, UserRole.AGENT)
    ),
    db: Session = Depends(get_db),
):
    try:
        return CreateMessageCommand.execute(
            db=db,
            current_user=current_user,
            conversation_id=conversation_id,
            data=data,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
def list_messages(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return ListMessagesCommand.execute(
            db=db,
            current_user=current_user,
            conversation_id=conversation_id,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
