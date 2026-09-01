from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.model import User, UserRole
from app.auth.permissions import require_roles
from app.auth.schema import MessageResponse
from app.customer.commands.create_customer import CreateCustomerCommand
from app.customer.commands.delete_customer import DeleteCustomerCommand
from app.customer.commands.update_customer import UpdateCustomerCommand
from app.customer.repositories.customer_repository import CustomerRepository
from app.customer.schema import (
    CustomerCreateRequest,
    CustomerResponse,
    CustomerUpdateRequest,
)
from app.database.session import get_db

router = APIRouter(
    prefix="/customers",
    tags=["Customers"],
)


@router.get("", response_model=list[CustomerResponse])
def list_customers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    customer_repo = CustomerRepository()
    customers = customer_repo.get_all_by_workspace(
        db=db,
        workspace_id=current_user.workspace_id,
    )
    return [CustomerResponse.model_validate(c) for c in customers]


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    customer_repo = CustomerRepository()
    customer = customer_repo.get_by_id_and_workspace(
        db=db,
        customer_id=customer_id,
        workspace_id=current_user.workspace_id,
    )

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    return CustomerResponse.model_validate(customer)


@router.post(
    "",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_customer(
    data: CustomerCreateRequest,
    current_user: User = Depends(
        require_roles(UserRole.OWNER, UserRole.ADMIN, UserRole.AGENT)
    ),
    db: Session = Depends(get_db),
):
    try:
        return CreateCustomerCommand.execute(
            db=db,
            current_user=current_user,
            data=data,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.patch("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: UUID,
    data: CustomerUpdateRequest,
    current_user: User = Depends(
        require_roles(UserRole.OWNER, UserRole.ADMIN, UserRole.AGENT)
    ),
    db: Session = Depends(get_db),
):
    try:
        return UpdateCustomerCommand.execute(
            db=db,
            current_user=current_user,
            customer_id=customer_id,
            data=data,
        )

    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete("/{customer_id}", response_model=MessageResponse)
def delete_customer(
    customer_id: UUID,
    current_user: User = Depends(require_roles(UserRole.OWNER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    try:
        return DeleteCustomerCommand.execute(
            db=db,
            current_user=current_user,
            customer_id=customer_id,
        )

    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
