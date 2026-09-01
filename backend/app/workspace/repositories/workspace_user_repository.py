from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.model import User, UserRole
from app.common.repository import BaseRepository


class WorkspaceUserRepository(BaseRepository[User]):

    def __init__(self):
        super().__init__(User)

    def get_by_id_and_workspace(
        self,
        db: Session,
        user_id: UUID,
        workspace_id: UUID,
    ) -> User | None:
        return (
            db.query(User)
            .filter(
                User.id == user_id,
                User.workspace_id == workspace_id,
            )
            .first()
        )

    def get_by_email(
        self,
        db: Session,
        email: str,
    ) -> User | None:
        return (
            db.query(User)
            .filter(
                User.email == email,
            )
            .first()
        )

    def list_by_workspace(
        self,
        db: Session,
        workspace_id: UUID,
    ) -> list[User]:
        return (
            db.query(User)
            .filter(
                User.workspace_id == workspace_id,
            )
            .order_by(User.created_at.asc())
            .all()
        )

    def count_active_owners(
        self,
        db: Session,
        workspace_id: UUID,
    ) -> int:
        return (
            db.query(User)
            .filter(
                User.workspace_id == workspace_id,
                User.role == UserRole.OWNER,
                User.is_active == True,
            )
            .count()
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
