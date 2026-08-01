from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.commands.register import RegisterCommand
from app.auth.schema import RegisterRequest
from app.database.session import get_db

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post("/register")
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db),
):
    return RegisterCommand.execute(
        db=db,
        data=data,
    )