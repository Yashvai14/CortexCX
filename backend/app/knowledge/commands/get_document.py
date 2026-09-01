from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.model import User
from app.knowledge.repositories.document_repository import DocumentRepository
from app.knowledge.schema import DocumentResponse


class GetDocumentCommand:

    @staticmethod
    def execute(
        db: Session,
        current_user: User,
        document_id: UUID,
    ) -> DocumentResponse:

        doc_repo = DocumentRepository()
        doc = doc_repo.get_by_id_and_workspace(
            db=db,
            document_id=document_id,
            workspace_id=current_user.workspace_id,
        )

        if not doc:
            raise LookupError("Document not found")

        response = DocumentResponse.model_validate(doc)
        response.chunk_count = len(doc.chunks) if doc.chunks else 0
        return response
