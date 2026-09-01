from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.model import User, UserRole
from app.auth.permissions import require_roles
from app.auth.schema import MessageResponse
from app.database.session import get_db
from app.workspace.commands.add_member import AddMemberCommand
from app.workspace.commands.create_workspace_user import (
    CreateWorkspaceUserCommand,
)
from app.workspace.commands.delete_workspace_user import (
    DeleteWorkspaceUserCommand,
)
from app.workspace.commands.remove_member import RemoveMemberCommand
from app.workspace.commands.update import UpdateWorkspaceCommand
from app.workspace.commands.update_member import UpdateMemberCommand
from app.workspace.commands.update_workspace_user import (
    UpdateWorkspaceUserCommand,
)
from app.workspace.repositories.member_repository import MemberRepository
from app.workspace.repositories.workspace_repository import WorkspaceRepository
from app.workspace.repositories.workspace_user_repository import (
    WorkspaceUserRepository,
)
from app.workspace.schema import (
    AddMemberRequest,
    MemberResponse,
    UpdateMemberRoleRequest,
    WorkspaceResponse,
    WorkspaceUpdateRequest,
    WorkspaceUserCreateRequest,
    WorkspaceUserResponse,
    WorkspaceUserUpdateRequest,
)

router = APIRouter(
    prefix="/workspaces",
    tags=["Workspaces"],
)


# =====================================================================
# Workspace Endpoints (Me & Specific)
# =====================================================================


@router.get("/me", response_model=WorkspaceResponse)
def get_current_workspace(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace_repo = WorkspaceRepository()
    workspace = workspace_repo.get_by_id(
        db=db,
        obj_id=current_user.workspace_id,
    )

    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    return WorkspaceResponse.model_validate(workspace)


@router.patch("/me", response_model=WorkspaceResponse)
def update_current_workspace(
    data: WorkspaceUpdateRequest,
    current_user: User = Depends(require_roles(UserRole.OWNER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    try:
        return UpdateWorkspaceCommand.execute(
            db=db,
            current_user=current_user,
            workspace_id=current_user.workspace_id,
            data=data,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# =====================================================================
# Workspace Users Endpoints (/workspaces/users)
# =====================================================================


@router.get("/users", response_model=list[WorkspaceUserResponse])
def list_workspace_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_repo = WorkspaceUserRepository()
    users = user_repo.list_by_workspace(
        db=db,
        workspace_id=current_user.workspace_id,
    )
    return [WorkspaceUserResponse.model_validate(u) for u in users]


@router.post(
    "/users",
    response_model=WorkspaceUserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_workspace_user(
    data: WorkspaceUserCreateRequest,
    current_user: User = Depends(require_roles(UserRole.OWNER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    try:
        return CreateWorkspaceUserCommand.execute(
            db=db,
            current_user=current_user,
            data=data,
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.patch(
    "/users/{user_id}",
    response_model=WorkspaceUserResponse,
)
def update_workspace_user(
    user_id: UUID,
    data: WorkspaceUserUpdateRequest,
    current_user: User = Depends(require_roles(UserRole.OWNER)),
    db: Session = Depends(get_db),
):
    try:
        return UpdateWorkspaceUserCommand.execute(
            db=db,
            current_user=current_user,
            user_id=user_id,
            data=data,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete(
    "/users/{user_id}",
    response_model=MessageResponse,
)
def delete_workspace_user(
    user_id: UUID,
    current_user: User = Depends(require_roles(UserRole.OWNER)),
    db: Session = Depends(get_db),
):
    try:
        return DeleteWorkspaceUserCommand.execute(
            db=db,
            current_user=current_user,
            user_id=user_id,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# =====================================================================
# Legacy/ID-Scoped Endpoints
# =====================================================================


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
def get_workspace(
    workspace_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    workspace_repo = WorkspaceRepository()
    workspace = workspace_repo.get_by_id(
        db=db,
        obj_id=workspace_id,
    )

    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    return WorkspaceResponse.model_validate(workspace)


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
def update_workspace(
    workspace_id: UUID,
    data: WorkspaceUpdateRequest,
    current_user: User = Depends(require_roles(UserRole.OWNER)),
    db: Session = Depends(get_db),
):
    try:
        return UpdateWorkspaceCommand.execute(
            db=db,
            current_user=current_user,
            workspace_id=workspace_id,
            data=data,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/{workspace_id}/members", response_model=list[MemberResponse])
def list_workspace_members(
    workspace_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    member_repo = MemberRepository()
    members = member_repo.list_by_workspace(
        db=db,
        workspace_id=workspace_id,
    )

    return [MemberResponse.model_validate(m) for m in members]


@router.post(
    "/{workspace_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_workspace_member(
    workspace_id: UUID,
    data: AddMemberRequest,
    current_user: User = Depends(require_roles(UserRole.OWNER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    try:
        return AddMemberCommand.execute(
            db=db,
            current_user=current_user,
            workspace_id=workspace_id,
            data=data,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.patch(
    "/{workspace_id}/members/{user_id}",
    response_model=MemberResponse,
)
def update_workspace_member(
    workspace_id: UUID,
    user_id: UUID,
    data: UpdateMemberRoleRequest,
    current_user: User = Depends(require_roles(UserRole.OWNER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    try:
        return UpdateMemberCommand.execute(
            db=db,
            current_user=current_user,
            workspace_id=workspace_id,
            user_id=user_id,
            data=data,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete(
    "/{workspace_id}/members/{user_id}",
    response_model=MessageResponse,
)
def remove_workspace_member(
    workspace_id: UUID,
    user_id: UUID,
    current_user: User = Depends(require_roles(UserRole.OWNER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    try:
        return RemoveMemberCommand.execute(
            db=db,
            current_user=current_user,
            workspace_id=workspace_id,
            user_id=user_id,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
