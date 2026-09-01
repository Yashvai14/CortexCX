from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.model import User, UserRole
from app.auth.security import hash_password
from app.workspace.repositories.member_repository import MemberRepository
from app.workspace.schema import (
    AddMemberRequest,
    MemberResponse,
)


class AddMemberCommand:

    @staticmethod
    def execute(
        db: Session,
        current_user: User,
        workspace_id: UUID,
        data: AddMemberRequest,
    ) -> MemberResponse:

        member_repo = MemberRepository()

        # 1. Tenant boundary: caller can only add members to their own workspace
        if current_user.workspace_id != workspace_id:
            raise LookupError("Workspace not found")

        # 2. RBAC rules
        if current_user.role == UserRole.AGENT:
            raise PermissionError("Agents cannot add workspace members")

        if current_user.role == UserRole.ADMIN and data.role != UserRole.AGENT:
            raise PermissionError("Admins can only create Agent members")

        # 3. Email uniqueness
        existing_user = member_repo.get_by_email(
            db=db,
            email=data.email,
        )
        if existing_user:
            raise ValueError("User with this email already exists")

        # 4. Create new user member
        new_user = User(
            workspace_id=workspace_id,
            full_name=data.full_name.strip(),
            email=data.email.strip().lower(),
            hashed_password=hash_password(data.password),
            role=data.role,
            is_active=True,
            is_verified=False,
        )

        member_repo.add(
            db=db,
            obj=new_user,
        )

        db.commit()
        db.refresh(new_user)

        return MemberResponse.model_validate(new_user)
