from sqlalchemy.orm import Session

from app.auth.model import User
from app.knowledge.repositories.knowledge_source_repository import (
    KnowledgeSourceRepository,
)
from app.knowledge.schema import KnowledgeSourceResponse


class ListKnowledgeSourcesCommand:

    @staticmethod
    def execute(
        db: Session,
        current_user: User,
    ) -> list[KnowledgeSourceResponse]:

        source_repo = KnowledgeSourceRepository()
        sources = source_repo.list_by_workspace(
            db=db,
            workspace_id=current_user.workspace_id,
        )

        return [KnowledgeSourceResponse.model_validate(s) for s in sources]
