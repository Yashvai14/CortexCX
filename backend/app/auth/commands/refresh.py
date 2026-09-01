from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.auth.model import RefreshToken
from app.auth.repositories.refresh_token_repository import (
    RefreshTokenRepository,
)
from app.auth.repositories.user_repository import UserRepository
from app.auth.schema import (
    RefreshTokenRequest,
    TokenResponse,
)
from app.core.config import settings


class RefreshCommand:

    @staticmethod
    def execute(
        db: Session,
        data: RefreshTokenRequest | None = None,
        token: str | None = None,
    ) -> TokenResponse:

        raw_token = token or (data.refresh_token if data else None)
        if not raw_token:
            raise ValueError("Refresh token is required")

        # 1. Validate JWT signature and structure
        payload = decode_token(raw_token)
        if not payload:
            raise ValueError("Invalid or expired refresh token")

        # 2. Ensure JWT type is 'refresh'
        token_type = payload.get("type")
        if token_type != "refresh":
            raise ValueError("Invalid token type: expected refresh token")

        # 3. Extract user ID from 'sub'
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise ValueError("Invalid token payload: missing subject")

        try:
            user_uuid = UUID(user_id_str)
        except (ValueError, TypeError):
            raise ValueError("Invalid user identifier in token")

        # 4 & 5. Find refresh token in PostgreSQL database
        refresh_token_repo = RefreshTokenRepository()
        token_record = refresh_token_repo.get_by_token(
            db=db,
            token=raw_token,
        )

        if not token_record:
            raise ValueError("Refresh token not found or already used")

        # 6. Ensure the database token is not revoked
        if token_record.is_revoked:
            raise ValueError("Refresh token has been revoked")

        # 7. Ensure database token has not expired
        now = datetime.now(timezone.utc)
        expires_at = token_record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at <= now:
            raise ValueError("Refresh token has expired")

        # 8 & 9. Find associated user and verify active status
        user_repo = UserRepository()
        user = user_repo.get_by_id(
            db=db,
            obj_id=token_record.user_id,
        )

        if not user or not user.is_active:
            raise ValueError("User not found or inactive")

        if user.id != user_uuid:
            raise ValueError("Token subject mismatch")

        # 10. Implement token rotation: revoke old refresh token
        refresh_token_repo.revoke(
            db=db,
            refresh_token=token_record,
        )

        # 11 & 12. Generate new access token and refresh token
        new_access_token = create_access_token(
            subject=str(user.id),
        )

        new_refresh_token = create_refresh_token(
            subject=str(user.id),
        )

        # 13. Create new refresh token database record
        new_refresh_token_expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

        new_refresh_token_record = RefreshToken(
            user_id=user.id,
            token=new_refresh_token,
            expires_at=new_refresh_token_expires_at,
            is_revoked=False,
        )

        refresh_token_repo.add(
            db=db,
            obj=new_refresh_token_record,
        )

        # 14. Commit transaction and return token pair
        db.commit()
        db.refresh(new_refresh_token_record)

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
        )
