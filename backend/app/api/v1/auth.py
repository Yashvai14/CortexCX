from alembic.util import status
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.auth.schema import (
    RegisterRequest,
    RegisterResponse,
)

from app.auth.service import AuthService

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
        return AuthService.register(
            db,
            data,
        )
    
    except ValueError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )