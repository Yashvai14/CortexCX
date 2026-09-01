from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.model import User
from app.knowledge.repositories.knowledge_source_repository import (
    KnowledgeSourceRepository,
)
from app.knowledge.schema import KnowledgeSourceResponse


class GetKnowledgeSourceCommand:

    @staticmethod
    def execute(
        db: Session,
        current_user: User,
        source_id: UUID,
    ) -> KnowledgeSourceResponse:

        source_repo = KnowledgeSourceRepository()
        source = source_repo.get_by_id_and_workspace(
            db=db,
            source_id=source_id,
            workspace_id=current_user.workspace_id,
        )

        if not source:
            raise LookupError("Knowledge source not found")

        return KnowledgeSourceResponse.model_validate(source)
