from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.model import User, UserRole
from app.workspace.repositories.member_repository import MemberRepository
from app.workspace.schema import (
    MemberResponse,
    UpdateMemberRoleRequest,
)


class UpdateMemberCommand:

    @staticmethod
    def execute(
        db: Session,
        current_user: User,
        workspace_id: UUID,
        user_id: UUID,
        data: UpdateMemberRoleRequest,
    ) -> MemberResponse:

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
            raise PermissionError("Agents cannot modify member roles")

        if current_user.role == UserRole.ADMIN:
            # Cannot modify the OWNER
            if target_user.role == UserRole.OWNER:
                raise PermissionError("Admins cannot modify the Workspace Owner")

            # Cannot promote any user to OWNER
            if data.role == UserRole.OWNER:
                raise PermissionError("Admins cannot promote users to Owner")

        # 4. Final Owner Protection (cannot demote or deactivate final active OWNER)
        if target_user.role == UserRole.OWNER:
            demoting = data.role is not None and data.role != UserRole.OWNER
            deactivating = data.is_active is False

            if demoting or deactivating:
                active_owners = member_repo.count_active_owners(
                    db=db,
                    workspace_id=workspace_id,
                )
                if active_owners <= 1:
                    raise ValueError(
                        "Cannot demote or deactivate the final workspace owner"
                    )

        # 5. Apply updates
        if data.role is not None:
            target_user.role = data.role

        if data.full_name is not None:
            target_user.full_name = data.full_name.strip()

        if data.is_active is not None:
            target_user.is_active = data.is_active

        db.commit()
        db.refresh(target_user)

        return MemberResponse.model_validate(target_user)
