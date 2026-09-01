from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.auth.jwt import (
    create_access_token,
    create_refresh_token,
)
from app.auth.model import RefreshToken
from app.auth.repositories.refresh_token_repository import (
    RefreshTokenRepository,
)
from app.auth.repositories.user_repository import UserRepository
from app.auth.schema import (
    LoginRequest,
    LoginResponse,
    TokenResponse,
    UserResponse,
)
from app.auth.security import verify_password
from app.core.config import settings


class LoginCommand:

    @staticmethod
    def execute(
        db: Session,
        data: LoginRequest | None = None,
        email: str | None = None,
        password: str | None = None,
    ):
        user_email = email or (data.email if data else None)
        user_password = password or (data.password if data else None)

        if not user_email or not user_password:
            raise ValueError(
                "Invalid email or password"
            )

        user_repo = UserRepository()
        refresh_token_repo = RefreshTokenRepository()

        user = user_repo.get_by_email(
            db=db,
            email=user_email,
        )

        if not user:
            raise ValueError(
                "Invalid email or password"
            )

        if not verify_password(
            user_password,
            user.hashed_password,
        ):
            raise ValueError(
                "Invalid email or password"
            )

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

        db.refresh(user)

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            user=UserResponse.model_validate(user),
        )