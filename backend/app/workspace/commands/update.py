from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.model import User
from app.workspace.repositories.workspace_repository import WorkspaceRepository
from app.workspace.schema import (
    WorkspaceResponse,
    WorkspaceUpdateRequest,
)


class UpdateWorkspaceCommand:

    @staticmethod
    def execute(
        db: Session,
        current_user: User,
        workspace_id: UUID,
        data: WorkspaceUpdateRequest,
    ) -> WorkspaceResponse:

        workspace_repo = WorkspaceRepository()

        # 1. Tenant boundary: user can only modify their own workspace
        if current_user.workspace_id != workspace_id:
            raise LookupError("Workspace not found")

        workspace = workspace_repo.get_by_id(
            db=db,
            obj_id=workspace_id,
        )

        if not workspace:
            raise LookupError("Workspace not found")

        # 2. Slug uniqueness check if slug is provided and changed
        if data.slug and data.slug != workspace.slug:
            existing = workspace_repo.get_by_slug(
                db=db,
                slug=data.slug,
            )
            if existing and existing.id != workspace.id:
                raise ValueError("Workspace slug already in use")

        # 3. Update workspace attributes
        update_data = data.model_dump(exclude_unset=True)
        workspace_repo.update(
            db=db,
            workspace=workspace,
            data=update_data,
        )

        db.commit()
        db.refresh(workspace)

        return WorkspaceResponse.model_validate(workspace)
