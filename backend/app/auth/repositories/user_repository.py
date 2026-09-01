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
        return (
            db.query(User)
            .filter(User.email == email)
            .first()
        )

    def get_by_id_and_workspace(
        self,
        db: Session,
        user_id,
        workspace_id,
    ) -> User | None:
        return (
            db.query(User)
            .filter(
                User.id == user_id,
                User.workspace_id == workspace_id,
            )
            .first()
        )

    def get_all_by_workspace(
        self,
        db: Session,
        workspace_id,
    ) -> list[User]:
        return (
            db.query(User)
            .filter(User.workspace_id == workspace_id)
            .order_by(User.created_at.desc())
            .all()
        )

    def update(
        self,
        db: Session,
        user: User,
        data: dict,
    ) -> User:
        for key, value in data.items():
            if value is not None and hasattr(user, key):
                setattr(user, key, value)
        return user
    