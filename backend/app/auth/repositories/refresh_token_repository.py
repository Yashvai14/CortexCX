from app.auth.model import RefreshToken
from app.common.repository import BaseRepository


class RefreshTokenRepository(BaseRepository[RefreshToken]):

    def __init__(self):
        super().__init__(RefreshToken)