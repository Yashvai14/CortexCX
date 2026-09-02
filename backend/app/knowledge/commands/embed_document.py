from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.model import User, UserRole
from app.embeddings.factory import get_embedding_provider
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

        # 3. Retrieve chunks for the document
        chunks = chunk_repo.list_by_document_and_workspace(
            db=db,
            document_id=document.id,
            workspace_id=current_user.workspace_id,
        )

        if not chunks:
            raise ValueError("Document has no chunks to embed")

        # 4. Generate embeddings using configured provider
        provider = get_embedding_provider()
        texts = [chunk.content for chunk in chunks]

        try:
            embeddings = provider.embed_texts(texts)
        except Exception as e:
            raise RuntimeError(
                f"Embedding provider failed to generate embeddings: {str(e)}"
            ) from None

        # 5. Persist embeddings atomically
        for chunk, emb in zip(chunks, embeddings):
            chunk.embedding = emb

        document.status = DocumentStatus.COMPLETED
        db.commit()
        db.refresh(document)

        resp = DocumentResponse.model_validate(document)
        resp.chunk_count = len(chunks)
        return resp
