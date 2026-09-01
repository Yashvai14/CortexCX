from sqlalchemy.orm import Session

from app.auth.model import User, UserRole
from app.auth.repositories.user_repository import UserRepository
from app.auth.schema import (
    UserCreateRequest,
    UserResponse,
)
from app.auth.security import hash_password


class CreateUserCommand:

    @staticmethod
    def execute(
        db: Session,
        current_user: User,
        data: UserCreateRequest,
    ) -> UserResponse:

        # 1. Privilege check: ADMIN cannot create an OWNER
        if (
            current_user.role == UserRole.ADMIN
            and data.role == UserRole.OWNER
        ):
            raise PermissionError("Admins cannot assign the OWNER role")

        user_repo = UserRepository()

        # 2. Check if email already exists
        existing_user = user_repo.get_by_email(
            db=db,
            email=data.email,
        )

        if existing_user:
            raise ValueError("Email already exists")

        # 3. Create user bound to current user's workspace
        new_user = User(
            workspace_id=current_user.workspace_id,
            full_name=data.full_name,
            email=data.email,
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

        return UserResponse.model_validate(new_user)
