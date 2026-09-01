from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.model import User
from app.knowledge.repositories.document_chunk_repository import (
    DocumentChunkRepository,
)
from app.knowledge.repositories.document_repository import DocumentRepository
from app.knowledge.schema import DocumentChunkResponse


class ListDocumentChunksCommand:

    @staticmethod
    def execute(
        db: Session,
        current_user: User,
        document_id: UUID,
    ) -> list[DocumentChunkResponse]:

        doc_repo = DocumentRepository()
        chunk_repo = DocumentChunkRepository()

        # 1. Tenant boundary check: document must exist in caller's workspace
        doc = doc_repo.get_by_id_and_workspace(
            db=db,
            document_id=document_id,
            workspace_id=current_user.workspace_id,
        )

        if not doc:
            raise LookupError("Document not found")

        chunks = chunk_repo.list_by_document_and_workspace(
            db=db,
            document_id=document_id,
            workspace_id=current_user.workspace_id,
        )

        return [DocumentChunkResponse.model_validate(c) for c in chunks]
