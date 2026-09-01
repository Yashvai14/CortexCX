from sqlalchemy.orm import Session

from app.auth.model import RefreshToken
from app.common.repository import BaseRepository


class RefreshTokenRepository(BaseRepository[RefreshToken]):

    def __init__(self):
        super().__init__(RefreshToken)

    def get_by_token(
        self,
        db: Session,
        token: str,
    ) -> RefreshToken | None:

        return (
            db.query(RefreshToken)
            .filter(RefreshToken.token == token)
            .first()
        )

    def get_active_by_token(
        self,
        db: Session,
        token: str,
    ) -> RefreshToken | None:

        return (
            db.query(RefreshToken)
            .filter(
                RefreshToken.token == token,
                RefreshToken.is_revoked.is_(False),
            )
            .first()
        )

    def revoke(
        self,
        db: Session,
        refresh_token: RefreshToken,
    ) -> RefreshToken:

        refresh_token.is_revoked = True
        return refresh_token