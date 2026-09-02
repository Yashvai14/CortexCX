from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.model import User, UserRole
from app.auth.permissions import require_roles
from app.database.session import get_db
from app.knowledge.commands.create_document import CreateDocumentCommand
from app.knowledge.commands.create_knowledge_source import (
    CreateKnowledgeSourceCommand,
)
from app.knowledge.commands.embed_document import EmbedDocumentCommand
from app.knowledge.commands.get_document import GetDocumentCommand
from app.knowledge.commands.get_knowledge_source import GetKnowledgeSourceCommand
from app.knowledge.commands.list_document_chunks import (
    ListDocumentChunksCommand,
)
from app.knowledge.commands.list_documents import ListDocumentsCommand
from app.knowledge.commands.list_knowledge_sources import (
    ListKnowledgeSourcesCommand,
)
from app.knowledge.commands.search_knowledge import SearchKnowledgeCommand
from app.knowledge.schema import (
    DocumentChunkResponse,
    DocumentCreateRequest,
    DocumentResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeSourceCreateRequest,
    KnowledgeSourceResponse,
)

router = APIRouter(
    prefix="/knowledge",
    tags=["Knowledge Base"],
)


# =====================================================================
# Knowledge Source Endpoints
# =====================================================================


@router.post(
    "/sources",
    response_model=KnowledgeSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_knowledge_source(
    data: KnowledgeSourceCreateRequest,
    current_user: User = Depends(
        require_roles(UserRole.OWNER, UserRole.ADMIN)
    ),
    db: Session = Depends(get_db),
):
    try:
        return CreateKnowledgeSourceCommand.execute(
            db=db,
            current_user=current_user,
            data=data,
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/sources",
    response_model=list[KnowledgeSourceResponse],
)
def list_knowledge_sources(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ListKnowledgeSourcesCommand.execute(
        db=db,
        current_user=current_user,
    )


@router.get(
    "/sources/{source_id}",
    response_model=KnowledgeSourceResponse,
)
def get_knowledge_source(
    source_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return GetKnowledgeSourceCommand.execute(
            db=db,
            current_user=current_user,
            source_id=source_id,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# =====================================================================
# Document Endpoints
# =====================================================================


@router.post(
    "/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_document(
    data: DocumentCreateRequest,
    current_user: User = Depends(
        require_roles(UserRole.OWNER, UserRole.ADMIN)
    ),
    db: Session = Depends(get_db),
):
    try:
        return CreateDocumentCommand.execute(
            db=db,
            current_user=current_user,
            data=data,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/documents",
    response_model=list[DocumentResponse],
)
def list_documents(
    knowledge_source_id: UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ListDocumentsCommand.execute(
        db=db,
        current_user=current_user,
        knowledge_source_id=knowledge_source_id,
    )


@router.get(
    "/documents/{document_id}",
    response_model=DocumentResponse,
)
def get_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return GetDocumentCommand.execute(
            db=db,
            current_user=current_user,
            document_id=document_id,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/documents/{document_id}/chunks",
    response_model=list[DocumentChunkResponse],
)
def list_document_chunks(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return ListDocumentChunksCommand.execute(
            db=db,
            current_user=current_user,
            document_id=document_id,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# =====================================================================
# Embedding & Semantic Search Endpoints (Milestone 12)
# =====================================================================


@router.post(
    "/documents/{document_id}/embed",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
)
def embed_document(
    document_id: UUID,
    current_user: User = Depends(
        require_roles(UserRole.OWNER, UserRole.ADMIN)
    ),
    db: Session = Depends(get_db),
):
    try:
        return EmbedDocumentCommand.execute(
            db=db,
            current_user=current_user,
            document_id=document_id,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
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


@router.post(
    "/search",
    response_model=KnowledgeSearchResponse,
    status_code=status.HTTP_200_OK,
)
def search_knowledge(
    data: KnowledgeSearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return SearchKnowledgeCommand.execute(
            db=db,
            current_user=current_user,
            data=data,
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
