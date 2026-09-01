from sqlalchemy.orm import Session

from app.auth.jwt import decode_token
from app.auth.model import User
from app.auth.repositories.refresh_token_repository import (
    RefreshTokenRepository,
)
from app.auth.schema import (
    LogoutRequest,
    MessageResponse,
)


class LogoutCommand:

    @staticmethod
    def execute(
        db: Session,
        current_user: User,
        data: LogoutRequest | None = None,
        refresh_token: str | None = None,
    ) -> MessageResponse:

        raw_token = refresh_token or (data.refresh_token if data else None)
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
        token_user_id_str = payload.get("sub")
        if not token_user_id_str:
            raise ValueError("Invalid token payload: missing subject")

        # 4. Find refresh token in PostgreSQL database
        refresh_token_repo = RefreshTokenRepository()
        token_record = refresh_token_repo.get_by_token(
            db=db,
            token=raw_token,
        )

        if not token_record:
            raise ValueError("Refresh token not found")

        # 5. Ensure the token is not already revoked
        if token_record.is_revoked:
            raise ValueError("Refresh token has already been revoked")

        # 6. Ensure the token belongs to the authenticated user
        if (
            str(token_record.user_id) != str(current_user.id)
            or token_user_id_str != str(current_user.id)
        ):
            raise ValueError(
                "Refresh token does not belong to the authenticated user"
            )

        # 7. Revoke the refresh token record in PostgreSQL
        refresh_token_repo.revoke(
            db=db,
            refresh_token=token_record,
        )

        # 8. Commit transaction
        db.commit()

        return MessageResponse(
            message="Logout successful",
        )
