from app.models import workspace
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import RegisterRequest


class AuthService:

    @staticmethod
    def register(
        db: Session,
        data: RegisterRequest,
    ) -> User:

        existing_user = UserRepository.get_by_email(
            db,
            data.email,
        )

        if existing_user:
            raise ValueError(
                "Email already exists"
            )
        
        user = User(
            workspace_id=data.workspace_id,
            full_name=data.full_name,
            email=data.email,
            hash_password=hash_password(
                data.password
            ),
        )

        return UserRepository.create(
            db,
            user,
        )