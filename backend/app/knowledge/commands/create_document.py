from sqlalchemy.orm import Session

from app.auth.model import User, UserRole
from app.knowledge.ingestion.pipeline import build_chunks
from app.knowledge.model import Document, DocumentChunk, DocumentStatus
from app.knowledge.repositories.document_chunk_repository import (
    DocumentChunkRepository,
)
from app.knowledge.repositories.document_repository import DocumentRepository
from app.knowledge.repositories.knowledge_source_repository import (
    KnowledgeSourceRepository,
)
from app.knowledge.schema import DocumentCreateRequest, DocumentResponse


class CreateDocumentCommand:

    @staticmethod
    def execute(
        db: Session,
        current_user: User,
        data: DocumentCreateRequest,
    ) -> DocumentResponse:

        # 1. RBAC Check: Only OWNER and ADMIN can create documents
        if current_user.role not in (UserRole.OWNER, UserRole.ADMIN):
            raise PermissionError("Only Owners and Admins can create documents")

        source_repo = KnowledgeSourceRepository()
        doc_repo = DocumentRepository()
        chunk_repo = DocumentChunkRepository()

        # 2. Verify Knowledge Source exists and belongs to current user's workspace
        source = source_repo.get_by_id_and_workspace(
            db=db,
            source_id=data.knowledge_source_id,
            workspace_id=current_user.workspace_id,
        )

        if not source:
            raise LookupError("Knowledge source not found")

        # 3. Content Validation
        if not data.content or not data.content.strip():
            raise ValueError("Document content cannot be empty")

        cleaned_content = data.content.strip()

        # 5. Create and persist Document record
        doc = Document(
            workspace_id=current_user.workspace_id,
            knowledge_source_id=source.id,
            title=data.title.strip(),
            filename=data.filename.strip() if data.filename else None,
            content=cleaned_content,
            metadata_json=data.metadata_json,
            status=DocumentStatus.PROCESSING,  # chunked; becomes COMPLETED once embeddings are stored
        )

        doc_repo.add(db, doc)
        db.flush()

        # 4-6. Normalize the text, split it on its own structure and persist the chunk rows
        # (embedding happens afterwards, in the background, so the upload returns quickly)
        try:
            chunk_models = build_chunks(db, doc)
        except ValueError:
            db.rollback()
            raise

        db.commit()
        db.refresh(doc)

        response = DocumentResponse.model_validate(doc)
        response.chunk_count = len(chunk_models)
        return response
