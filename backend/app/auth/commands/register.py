from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.auth.jwt import (
    create_access_token,
    create_refresh_token,
)
from app.auth.model import (
    RefreshToken,
    User,
    UserRole,
)
from app.auth.repositories.refresh_token_repository import (
    RefreshTokenRepository,
)
from app.auth.repositories.user_repository import UserRepository
from app.auth.schema import (
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserResponse,
)
from app.auth.security import hash_password
from app.core.config import settings
from app.workspace.model import Workspace
from app.workspace.repositories.workspace_repository import WorkspaceRepository


class RegisterCommand:

    @staticmethod
    def execute(
        db: Session,
        data: RegisterRequest,
    ):

        user_repo = UserRepository()
        workspace_repo = WorkspaceRepository()
        refresh_token_repo = RefreshTokenRepository()

        existing_user = user_repo.get_by_email(
            db=db,
            email=data.email,
        )

        if existing_user:
            raise ValueError("Email already exists")

        existing_workspace = workspace_repo.get_by_slug(
            db=db,
            slug=data.company_slug,
        )

        if existing_workspace:
            raise ValueError("Company slug already exists")

        workspace = Workspace(
            name=data.company_name,
            slug=data.company_slug,
        )

        workspace_repo.add(
            db=db,
            obj=workspace,
        )

        db.flush()

        user = User(
            workspace_id=workspace.id,
            full_name=data.full_name,
            email=data.email,
            hashed_password=hash_password(data.password),
            role=UserRole.OWNER,
        )

        user_repo.add(
            db=db,
            obj=user,
        )

        db.flush()

        access_token = create_access_token(
            str(user.id)
        )

        refresh_token = create_refresh_token(
            str(user.id)
        )

        refresh_token_expires_at = (
            datetime.now(timezone.utc)
            + timedelta(
                minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES
            )
        )

        refresh_token_record = RefreshToken(
            user_id=user.id,
            token=refresh_token,
            expires_at=refresh_token_expires_at,
            is_revoked=False,
        )

        refresh_token_repo.add(
            db=db,
            obj=refresh_token_record,
        )

        db.commit()

        db.refresh(workspace)
        db.refresh(user)
        db.refresh(refresh_token_record)

        return RegisterResponse(
            message="Registration successful",

            workspace=workspace,

            user=UserResponse.model_validate(user),

            token=TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
            ),
        )