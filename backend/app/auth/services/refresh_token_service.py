from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.auth.model import RefreshToken
from app.auth.repositories.refresh_token_repository import(
    RefreshTokenRepository
)
from app.core.config import settings


class RefreshTokenService:

    @staticmethod
    def create(
        db: Session,
        user_id,
        token: str,
    ) -> RefreshToken:

        repository = RefreshTokenRepository()

        refresh_token = RefreshToken(
            user_id=user_id,
            token=token,
            expires_at=datetime.now(timezone.utc)
            + timedelta(
                minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES
            ),
        )

        repository.add(
            db=db,
            obj=refresh_token,
        )

        db.flush()

        return refresh_token