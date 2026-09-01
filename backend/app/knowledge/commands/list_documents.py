from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.model import User
from app.knowledge.repositories.document_repository import DocumentRepository
from app.knowledge.schema import DocumentResponse


class ListDocumentsCommand:

    @staticmethod
    def execute(
        db: Session,
        current_user: User,
        knowledge_source_id: UUID | None = None,
    ) -> list[DocumentResponse]:

        doc_repo = DocumentRepository()
        docs = doc_repo.list_by_workspace(
            db=db,
            workspace_id=current_user.workspace_id,
            knowledge_source_id=knowledge_source_id,
        )

        results: list[DocumentResponse] = []
        for doc in docs:
            resp = DocumentResponse.model_validate(doc)
            resp.chunk_count = len(doc.chunks) if doc.chunks else 0
            results.append(resp)

        return results
