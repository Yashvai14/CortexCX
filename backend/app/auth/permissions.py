from fastapi import Depends, HTTPException, status

from app.auth.dependencies import get_current_user
from app.auth.model import User, UserRole


class RoleChecker:

    def __init__(self, allowed_roles: tuple[UserRole, ...]):
        self.allowed_roles = allowed_roles

    def __call__(
        self,
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: insufficient permissions",
            )
        return current_user


def require_roles(*allowed_roles: UserRole) -> RoleChecker:
    return RoleChecker(allowed_roles)


require_owner = require_roles(UserRole.OWNER)
require_admin = require_roles(UserRole.OWNER, UserRole.ADMIN)
require_agent = require_roles(UserRole.OWNER, UserRole.ADMIN, UserRole.AGENT)
