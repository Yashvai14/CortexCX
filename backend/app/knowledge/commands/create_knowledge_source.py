from sqlalchemy.orm import Session

from app.auth.model import User, UserRole
from app.knowledge.model import KnowledgeSource, KnowledgeSourceStatus
from app.knowledge.repositories.knowledge_source_repository import (
    KnowledgeSourceRepository,
)
from app.knowledge.schema import (
    KnowledgeSourceCreateRequest,
    KnowledgeSourceResponse,
)


class CreateKnowledgeSourceCommand:

    @staticmethod
    def execute(
        db: Session,
        current_user: User,
        data: KnowledgeSourceCreateRequest,
    ) -> KnowledgeSourceResponse:

        # 1. RBAC Check: Only OWNER and ADMIN can create knowledge sources
        if current_user.role not in (UserRole.OWNER, UserRole.ADMIN):
            raise PermissionError(
                "Only Owners and Admins can create knowledge sources"
            )

        source_repo = KnowledgeSourceRepository()

        # 2. Instantiate and persist KnowledgeSource bound to current_user.workspace_id
        source = KnowledgeSource(
            workspace_id=current_user.workspace_id,
            name=data.name.strip(),
            source_type=data.source_type,
            source_url=data.source_url.strip() if data.source_url else None,
            status=KnowledgeSourceStatus.COMPLETED,
        )

        source_repo.add(db, source)
        db.commit()
        db.refresh(source)

        return KnowledgeSourceResponse.model_validate(source)
