from sqlalchemy.orm import Session

from app.auth.model import User, UserRole
from app.auth.security import hash_password
from app.workspace.repositories.workspace_user_repository import (
    WorkspaceUserRepository,
)
from app.workspace.schema import (
    WorkspaceUserCreateRequest,
    WorkspaceUserResponse,
)


class CreateWorkspaceUserCommand:

    @staticmethod
    def execute(
        db: Session,
        current_user: User,
        data: WorkspaceUserCreateRequest,
    ) -> WorkspaceUserResponse:

        user_repo = WorkspaceUserRepository()

        # 1. RBAC rules:
        if current_user.role == UserRole.AGENT:
            raise PermissionError("Agents cannot create workspace users")

        if current_user.role == UserRole.ADMIN and data.role == UserRole.OWNER:
            raise PermissionError("Admins cannot create Owner users")

        # 2. Email uniqueness
        existing_user = user_repo.get_by_email(
            db=db,
            email=data.email,
        )
        if existing_user:
            raise ValueError("User with this email already exists")

        # 3. Create user bound to current_user's workspace
        new_user = User(
            workspace_id=current_user.workspace_id,
            full_name=data.full_name.strip(),
            email=data.email.strip().lower(),
            hashed_password=hash_password(data.password),
            role=data.role,
            is_active=True,
            is_verified=False,
        )

        user_repo.add(
            db=db,
            obj=new_user,
        )

        db.commit()
        db.refresh(new_user)

        return WorkspaceUserResponse.model_validate(new_user)
