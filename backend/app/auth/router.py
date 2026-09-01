from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth.commands.login import LoginCommand
from app.auth.commands.logout import LogoutCommand
from app.auth.commands.refresh import RefreshCommand
from app.auth.commands.register import RegisterCommand
from app.auth.dependencies import get_current_user
from app.auth.model import User, UserRole
from app.auth.permissions import require_roles
from app.auth.schema import (
    LogoutRequest,
    MessageResponse,
    RefreshTokenRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserResponse,
)
from app.database.session import get_db

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=201,
)
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db),
):
    try:
        return RegisterCommand.execute(
            db=db,
            data=data,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    try:
        return LoginCommand.execute(
            db=db,
            email=form_data.username,
            password=form_data.password,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=200,
)
def refresh(
    data: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    try:
        return RefreshCommand.execute(
            db=db,
            data=data,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=401,
            detail=str(e),
        )


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=200,
)
def logout(
    data: LogoutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return LogoutCommand.execute(
            db=db,
            current_user=current_user,
            data=data,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=401,
            detail=str(e),
        )


@router.get("/me", response_model=UserResponse)
def me(
    current_user: User = Depends(get_current_user),
):
    return UserResponse.model_validate(current_user)


@router.get("/admin-test", response_model=MessageResponse)
def admin_test(
    current_user: User = Depends(require_roles(UserRole.OWNER, UserRole.ADMIN)),
):
    return MessageResponse(message="Admin access granted")


@router.get("/owner-test", response_model=MessageResponse)
def owner_test(
    current_user: User = Depends(require_roles(UserRole.OWNER)),
):
    return MessageResponse(message="Owner access granted")