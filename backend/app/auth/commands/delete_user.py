from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.model import User, UserRole
from app.auth.repositories.user_repository import UserRepository
from app.auth.schema import MessageResponse


class DeleteUserCommand:

    @staticmethod
    def execute(
        db: Session,
        current_user: User,
        user_id: UUID,
    ) -> MessageResponse:

        user_repo = UserRepository()

        # 1. Tenant boundary: user must exist within current user's workspace
        target_user = user_repo.get_by_id_and_workspace(
            db=db,
            user_id=user_id,
            workspace_id=current_user.workspace_id,
        )

        if not target_user:
            raise LookupError("User not found")

        # 2. Protection rules:
        if target_user.role == UserRole.OWNER:
            if current_user.role == UserRole.ADMIN:
                raise PermissionError("Admins cannot delete the OWNER")

            if current_user.id == target_user.id:
                raise ValueError("Cannot delete your own OWNER account")

        # 3. Delete user
        user_repo.delete(
            db=db,
            obj=target_user,
        )

        db.commit()

        return MessageResponse(
            message="User deleted successfully",
        )
