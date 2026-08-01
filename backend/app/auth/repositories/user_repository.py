from sqlalchemy.orm import Session
from app.auth.model import User
from app.common.repository import BaseRepository



class UserRepository(BaseRepository[User]):

    def __init__(self):
        super().__init__(User)

    def get_by_email(
        self,
        db: Session,
        email: str,
    ) -> User | None:
        return(
            db.query(User)
            .filter(User.email == email)
            .first()
        )
    