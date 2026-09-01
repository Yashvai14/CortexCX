from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.model import User, UserRole
from app.auth.repositories.user_repository import UserRepository
from app.auth.schema import (
    UserResponse,
    UserUpdateRequest,
)
from app.auth.security import hash_password


class UpdateUserCommand:

    @staticmethod
    def execute(
        db: Session,
        current_user: User,
        user_id: UUID,
        data: UserUpdateRequest,
    ) -> UserResponse:

        user_repo = UserRepository()

        # 1. Tenant boundary: user must exist within current user's workspace
        target_user = user_repo.get_by_id_and_workspace(
            db=db,
            user_id=user_id,
            workspace_id=current_user.workspace_id,
        )

        if not target_user:
            raise LookupError("User not found")

        # 2. Privilege checks for ADMIN
        if current_user.role == UserRole.ADMIN:
            # Cannot modify an OWNER
            if target_user.role == UserRole.OWNER:
                raise PermissionError("Admins cannot modify the OWNER")

            # Cannot promote any user to OWNER
            if data.role == UserRole.OWNER:
                raise PermissionError("Admins cannot promote users to OWNER")

        # 3. Check email uniqueness if email is changing
        if data.email and data.email != target_user.email:
            existing = user_repo.get_by_email(
                db=db,
                email=data.email,
            )
            if existing and existing.id != target_user.id:
                raise ValueError("Email already in use")
            target_user.email = data.email

        # 4. Handle password hashing if password is provided
        if data.password:
            target_user.hashed_password = hash_password(data.password)

        # 5. Update remaining fields
        if data.full_name is not None:
            target_user.full_name = data.full_name

        if data.role is not None:
            target_user.role = data.role

        if data.is_active is not None:
            target_user.is_active = data.is_active

        db.commit()
        db.refresh(target_user)

        return UserResponse.model_validate(target_user)
