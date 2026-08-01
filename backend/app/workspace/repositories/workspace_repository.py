from sqlalchemy.orm import Session

from app.common.repository import BaseRepository
from app.workspace.model import Workspace


class WorkspaceRepository(BaseRepository[Workspace]):

    def __init__(self):
        super().__init__(Workspace)

    def get_by_slug(
        self,
        db: Session,
        slug: str,
    ) -> Workspace | None:

        return (
            db.query(Workspace)
            .filter(Workspace.slug == slug)
            .first()
        )