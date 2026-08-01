from sqlalchemy.orm import Session

from app.auth.repositories.user_repository import UserRepository
from app.auth.schema import RegisterRequest
from app.workspace.repositories.workspace_repository import WorkspaceRepository
from app.workspace.model import Workspace



class RegisterCommand:

    @staticmethod
    def execute(
        db: Session,
        data: RegisterRequest,
    ):
        user_repo = UserRepository()

        existing_user = user_repo.get_by_email(
            db=db,
            email=data.email,
        )

        if existing_user:
            raise ValueError("Email already exists")

        Workspace_repo = WorkspaceRepository()


        existing_workspace = Workspace_repo.get_by_slug(
            db=db,
            slug=data.company_slug,
        )

        if existing_workspace:
            raise ValueError("Company slug already exists")
        
        Workspace = Workspace(
            name=data.company_name,
            slug=data.company_slug,
        )

        Workspace_repo.add(
            db=db,
            obj=Workspace,
        )

        db.flush()

        return{
            "message": "Workspace created successfully",
            "workspace_id": str(Workspace.id),
        }