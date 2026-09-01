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

    def update(
        self,
        db: Session,
        workspace: Workspace,
        data: dict,
    ) -> Workspace:

        for key, value in data.items():
            if value is not None and hasattr(workspace, key):
                setattr(workspace, key, value)

        return workspace