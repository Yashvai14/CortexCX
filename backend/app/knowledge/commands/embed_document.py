from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.model import User, UserRole
from app.knowledge.ingestion.pipeline import embed_document
from app.knowledge.model import DocumentStatus
from app.knowledge.repositories.document_chunk_repository import (
    DocumentChunkRepository,
)
from app.knowledge.repositories.document_repository import DocumentRepository
from app.knowledge.schema import DocumentResponse


class EmbedDocumentCommand:

    @staticmethod
    def execute(
        db: Session,
        current_user: User,
        document_id: UUID,
    ) -> DocumentResponse:

        # 1. RBAC check: only OWNER and ADMIN can embed documents
        if current_user.role not in (UserRole.OWNER, UserRole.ADMIN):
            raise PermissionError(
                "Only Owners and Admins can generate document embeddings"
            )

        doc_repo = DocumentRepository()
        chunk_repo = DocumentChunkRepository()

        # 2. Strict tenant boundary lookup
        document = doc_repo.get_by_id_and_workspace(
            db=db,
            document_id=document_id,
            workspace_id=current_user.workspace_id,
        )

        if not document:
            raise LookupError("Document not found")

        # 3. Embed (batched) and store vectors in pgvector; marks the document COMPLETED
        try:
            count = embed_document(db, document)
        except ValueError:
            raise
        except Exception as e:
            db.rollback()
            document.status = DocumentStatus.FAILED
            document.error_message = f"{type(e).__name__}: {e}"[:1000]
            db.commit()
            raise RuntimeError(
                f"Embedding provider failed to generate embeddings: {str(e)}"
            ) from None

        db.refresh(document)
        resp = DocumentResponse.model_validate(document)
        resp.chunk_count = count
        return resp
