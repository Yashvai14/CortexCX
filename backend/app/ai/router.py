from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.commands.get_conversation_ai_status import (
    GetConversationAIStatusCommand,
)
from app.ai.commands.process_conversation_ai import ProcessConversationAICommand
from app.ai.commands.toggle_conversation_ai import ToggleConversationAICommand
from app.ai.schema import (
    AIConversationStatusResponse,
    AIProcessConversationRequest,
    AIProcessConversationResponse,
    AIToggleRequest,
)
from app.auth.dependencies import get_current_user
from app.auth.model import User, UserRole
from app.auth.permissions import require_roles
from app.database.session import get_db
from app.rag.schema import RAGProcessRequest, RAGProcessResponse
from app.rag.service import RAGService

router = APIRouter(
    prefix="/ai",
    tags=["AI Support Agent"],
)


@router.post(
    "/conversations/{conversation_id}/process",
    response_model=AIProcessConversationResponse,
    status_code=status.HTTP_200_OK,
)
def process_conversation_ai(
    conversation_id: UUID,
    data: AIProcessConversationRequest | None = None,
    current_user: User = Depends(
        require_roles(UserRole.OWNER, UserRole.ADMIN, UserRole.AGENT)
    ),
    db: Session = Depends(get_db),
):
    try:
        return ProcessConversationAICommand.execute(
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
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        )


@router.patch(
    "/conversations/{conversation_id}/toggle",
    response_model=AIConversationStatusResponse,
)
def toggle_conversation_ai(
    conversation_id: UUID,
    data: AIToggleRequest,
    current_user: User = Depends(
        require_roles(UserRole.OWNER, UserRole.ADMIN, UserRole.AGENT)
    ),
    db: Session = Depends(get_db),
):
    try:
        return ToggleConversationAICommand.execute(
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


@router.get(
    "/conversations/{conversation_id}/status",
    response_model=AIConversationStatusResponse,
)
def get_conversation_ai_status(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return GetConversationAIStatusCommand.execute(
            db=db,
            current_user=current_user,
            conversation_id=conversation_id,
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
    "/conversations/{conversation_id}/rag",
    response_model=RAGProcessResponse,
    status_code=status.HTTP_200_OK,
)
def process_conversation_rag(
    conversation_id: UUID,
    data: RAGProcessRequest | None = None,
    current_user: User = Depends(
        require_roles(UserRole.OWNER, UserRole.ADMIN, UserRole.AGENT)
    ),
    db: Session = Depends(get_db),
):
    try:
        return RAGService.execute(
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
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        )

