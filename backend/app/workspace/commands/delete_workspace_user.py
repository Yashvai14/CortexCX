from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.model import User, UserRole
from app.auth.schema import MessageResponse
from app.workspace.repositories.workspace_user_repository import (
    WorkspaceUserRepository,
)


class DeleteWorkspaceUserCommand:

    @staticmethod
    def execute(
        db: Session,
        current_user: User,
        user_id: UUID,
    ) -> MessageResponse:

        user_repo = WorkspaceUserRepository()

        # 1. RBAC rules: only OWNER can delete workspace users under this endpoint
        if current_user.role != UserRole.OWNER:
            raise PermissionError("Only Owners can delete workspace users")

        # 2. Member lookup strictly within current user's workspace
        target_user = user_repo.get_by_id_and_workspace(
            db=db,
            user_id=user_id,
            workspace_id=current_user.workspace_id,
        )

        if not target_user:
            raise LookupError("User not found")

        # 3. Final Owner Protection (cannot delete the final active OWNER or self if only owner)
        if target_user.role == UserRole.OWNER:
            active_owners = user_repo.count_active_owners(
                db=db,
                workspace_id=current_user.workspace_id,
            )
            if active_owners <= 1:
                raise ValueError("Cannot delete the final workspace owner")

        # 4. Delete user record
        user_repo.delete(
            db=db,
            obj=target_user,
        )

        db.commit()

        return MessageResponse(
            message="User deleted successfully",
        )
