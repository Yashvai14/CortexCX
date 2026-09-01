from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.model import User, UserRole
from app.auth.schema import MessageResponse
from app.workspace.repositories.member_repository import MemberRepository


class RemoveMemberCommand:

    @staticmethod
    def execute(
        db: Session,
        current_user: User,
        workspace_id: UUID,
        user_id: UUID,
    ) -> MessageResponse:

        member_repo = MemberRepository()

        # 1. Tenant boundary check for caller
        if current_user.workspace_id != workspace_id:
            raise LookupError("Workspace not found")

        # 2. Member lookup strictly within workspace
        target_user = member_repo.get_by_id_and_workspace(
            db=db,
            user_id=user_id,
            workspace_id=workspace_id,
        )

        if not target_user:
            raise LookupError("Member not found")

        # 3. RBAC rules
        if current_user.role == UserRole.AGENT:
            raise PermissionError("Agents cannot remove workspace members")

        if current_user.role == UserRole.ADMIN and target_user.role != UserRole.AGENT:
            raise PermissionError("Admins can only remove Agent members")

        # 4. Final Owner Protection (cannot delete final active OWNER)
        if target_user.role == UserRole.OWNER:
            active_owners = member_repo.count_active_owners(
                db=db,
                workspace_id=workspace_id,
            )
            if active_owners <= 1:
                raise ValueError("Cannot remove the final workspace owner")

        # 5. Delete member
        member_repo.delete(
            db=db,
            obj=target_user,
        )

        db.commit()

        return MessageResponse(
            message="Member removed successfully",
        )
