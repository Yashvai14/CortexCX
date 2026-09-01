from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.model import User, UserRole
from app.workspace.repositories.workspace_user_repository import (
    WorkspaceUserRepository,
)
from app.workspace.schema import (
    WorkspaceUserResponse,
    WorkspaceUserUpdateRequest,
)


class UpdateWorkspaceUserCommand:

    @staticmethod
    def execute(
        db: Session,
        current_user: User,
        user_id: UUID,
        data: WorkspaceUserUpdateRequest,
    ) -> WorkspaceUserResponse:

        user_repo = WorkspaceUserRepository()

        # 1. RBAC rules: only OWNER can modify user roles/status under this endpoint
        if current_user.role != UserRole.OWNER:
            raise PermissionError(
                "Only Owners can modify workspace user roles and status"
            )

        # 2. Member lookup strictly within current user's workspace
        target_user = user_repo.get_by_id_and_workspace(
            db=db,
            user_id=user_id,
            workspace_id=current_user.workspace_id,
        )

        if not target_user:
            raise LookupError("User not found")

        # 3. Final Owner Protection (cannot demote or deactivate the final active OWNER)
        if target_user.role == UserRole.OWNER:
            demoting = data.role is not None and data.role != UserRole.OWNER
            deactivating = data.is_active is False

            if demoting or deactivating:
                active_owners = user_repo.count_active_owners(
                    db=db,
                    workspace_id=current_user.workspace_id,
                )
                if active_owners <= 1:
                    raise ValueError(
                        "Cannot demote or deactivate the final workspace owner"
                    )

        # 4. Apply updates
        if data.role is not None:
            target_user.role = data.role

        if data.is_active is not None:
            target_user.is_active = data.is_active

        if data.full_name is not None:
            target_user.full_name = data.full_name.strip()

        db.commit()
        db.refresh(target_user)

        return WorkspaceUserResponse.model_validate(target_user)
